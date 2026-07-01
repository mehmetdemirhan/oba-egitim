"""MEB kelime modülü smoke testi (izole test DB).

    cd appbackend
    .venv/Scripts/python.exe tests/test_meb_kelime_smoke.py

Kapsam:
  - DOCX parse + /meb-kelime/yukle önizleme (admin), teacher → 403
  - /meb-kelime/onayla → DB'ye yazma, tekrar onayla → atlanan
  - AI üretimi (mock call_claude) → anlam dolar, durum aktif
  - kelime_secici: MEB (anlamlı) öncelikli döner
  - liste + istatistik
"""
import asyncio
import io
import os
import sys
import uuid

TEST_DB = "oba_test_meb_kelime_smoke"
os.environ["MONGO_URL"] = os.environ.get("MONGO_URL_TEST", "mongodb://localhost:27017")
os.environ["DB_NAME"] = TEST_DB
os.environ.setdefault("SECRET_KEY", "test-secret-key")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_g = 0
_k = 0


def check(kosul, mesaj):
    global _g, _k
    if kosul:
        _g += 1; print(f"  [GECTI] {mesaj}")
    else:
        _k += 1; print(f"  [KALDI] {mesaj}")


def _docx_bytes(metin):
    from docx import Document
    d = Document()
    for satir in metin.split("\n"):
        d.add_paragraph(satir)
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


async def run():
    import server
    import modules.meb_kelime as mk
    from core.auth import create_access_token
    from core.kelime_secici import kelime_sec, meb_kelime_stringleri
    from httpx import AsyncClient, ASGITransport

    await server.client.drop_database(TEST_DB)

    adm = str(uuid.uuid4())
    tch = str(uuid.uuid4())
    await server.db.users.insert_one({"id": adm, "ad": "Admin", "soyad": "Yön", "role": "admin"})
    await server.db.users.insert_one({"id": tch, "ad": "Ali", "soyad": "Hoca", "role": "teacher", "linked_id": str(uuid.uuid4())})
    HA = {"Authorization": f"Bearer {create_access_token({'sub': adm})}"}
    HT = {"Authorization": f"Bearer {create_access_token({'sub': tch})}"}

    # ── Parser birim testi ──
    kelimeler = mk._kelimeleri_ayir("Elma, armut; muz 123 a  PORTAKAL\nçilek çilek kayısı!")
    check("çilek" in kelimeler and kelimeler.count("çilek") == 1, "parser tekilleştiriyor")
    check("portakal" in kelimeler, "parser Türkçe küçük harfe çeviriyor")
    check("123" not in kelimeler and "a" not in kelimeler, "sayı ve tek harf atlanıyor")

    transport = ASGITransport(app=server.app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        docx = _docx_bytes("elma armut muz\nportakal çilek\nkitap kalem defter")

        # teacher yükleyemez → 403
        r = await ac.post("/api/meb-kelime/yukle", headers=HT,
                          files={"dosya": ("liste.docx", docx, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
                          data={"sinif": "1"})
        check(r.status_code == 403, f"öğretmen yukle 403 (status={r.status_code})")

        # admin önizleme
        r = await ac.post("/api/meb-kelime/yukle", headers=HA,
                          files={"dosya": ("liste.docx", docx, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
                          data={"sinif": "1"})
        check(r.status_code == 200, f"admin yukle 200 (status={r.status_code})")
        onizleme = r.json().get("onizleme", [])
        check(len(onizleme) == 8, f"8 kelime bulundu (gelen {len(onizleme)})")
        check("elma" in onizleme and "defter" in onizleme, "beklenen kelimeler var")

        # ── AI mock'u onayla'dan ÖNCE kur (arka plan görevi mock ile çalışsın) ──
        async def sahte_ai(system, user, model="sonnet", max_tokens=3500):
            import re
            # Yeni prompt: her kelime "- kelime (X. sınıf, Ders)" satırında; DÜZ DİZİ döndür
            kls = re.findall(r"^- ([a-zçğıöşü]+)", user, re.MULTILINE)
            return {"parsed": [{"kelime": k, "anlam": f"{k} anlamı", "ornek_cumle": f"Bir {k}.", "etiketler": ["test"]} for k in kls], "text": "", "error": None}
        mk.call_claude = sahte_ai
        mk.AI_BEKLEME_SN = 0  # testte bekleme yok

        # onayla → DB (+ arka plan AI görevi tetiklenir)
        r = await ac.post("/api/meb-kelime/onayla", headers=HA,
                          json={"kelimeler": onizleme, "sinif": 1, "kaynak_dosya": "liste.docx"})
        check(r.status_code == 200 and r.json()["yeni_eklenen"] == 8, f"8 yeni eklendi (gelen {r.json()})")

        # tekrar onayla → hepsi atlanır (yeni=0 → yeni AI görevi tetiklemez)
        r = await ac.post("/api/meb-kelime/onayla", headers=HA,
                          json={"kelimeler": onizleme, "sinif": 1, "kaynak_dosya": "liste.docx"})
        check(r.json()["yeni_eklenen"] == 0 and r.json()["mevcut_atlanan"] == 8, "tekrar onayda hepsi atlandı")

        # Arka plan AI görevlerinin bitmesini bekle (guard anahtarı (sinif,ders))
        for _ in range(200):
            if not mk._ai_aktif:
                break
            await asyncio.sleep(0.02)
        dolu = await server.db.meb_kelimeleri.count_documents({"sinif": 1, "anlam": {"$nin": [None, ""]}})
        check(dolu == 8, f"AI 8 kelimeye anlam üretti (gelen {dolu})")
        ornek = await server.db.meb_kelimeleri.find_one({"sinif": 1, "kelime": "elma"})
        check(ornek.get("anlam") and ornek.get("durum") == "aktif", "elma anlam+aktif")

        # ── kelime_secici önceliği ──
        secim = await kelime_sec(1, 5, meb_orani=1.0)
        check(len(secim) == 5, "kelime_sec 5 döndürdü")
        check(all(s["kaynak"] == "meb" for s in secim), "meb_orani=1.0 → hepsi MEB (öncelik)")
        # Varsayılan meb_orani (0.7) → çoğunluk MEB, kalan havuz
        karisik = await kelime_sec(1, 5)
        check(sum(1 for s in karisik if s["kaynak"] == "meb") >= 3, "varsayılan oranda MEB çoğunlukta")
        # sınıf 2'de MEB yok → havuzdan
        secim2 = await kelime_sec(2, 3)
        check(len(secim2) == 3 and all(s["kaynak"] == "havuz" for s in secim2), "MEB yoksa havuzdan tamamlandı")

        # ── liste + istatistik ──
        r = await ac.get("/api/meb-kelime/liste?sinif=1&durum=aktif&limit=50", headers=HA)
        check(r.status_code == 200 and r.json()["toplam"] == 8, "liste 8 kelime")
        r = await ac.get("/api/meb-kelime/istatistik?sinif=1", headers=HA)
        d = r.json()
        check(d["toplam_kelime"] == 8 and d["ai_uretimi_tamamlanan"] == 8, "istatistik doğru")

        # ── düzenle + soft delete ──
        kid = ornek["id"]
        r = await ac.put(f"/api/meb-kelime/{kid}", headers=HA, json={"anlam": "elle düzeltilmiş"})
        check(r.status_code == 200, "PUT düzenleme 200")
        r = await ac.delete(f"/api/meb-kelime/{kid}", headers=HA)
        check(r.status_code == 200 and r.json()["durum"] == "arsivli", "soft delete arsivli")
        r = await ac.delete(f"/api/meb-kelime/{kid}", headers=HT)
        check(r.status_code == 403, f"öğretmen silemez 403 (status={r.status_code})")

        # ── 5 DERS DESTEĞİ ──
        r = await ac.get("/api/meb-kelime/dersler", headers=HA)
        check(r.status_code == 200 and len(r.json().get("dersler", {})) == 5, "5 ders sabiti dönüyor")

        # Türkçe s4 'vatan' + Sosyal Bilgiler s4 'vatan' → ikisi de kabul (unique kelime+sinif+ders)
        r = await ac.post("/api/meb-kelime/onayla", headers=HA, json={"kelimeler": ["vatan"], "sinif": 4, "ders": "turkce"})
        check(r.json().get("yeni_eklenen") == 1, "türkçe s4 'vatan' eklendi")
        r = await ac.post("/api/meb-kelime/onayla", headers=HA, json={"kelimeler": ["vatan"], "sinif": 4, "ders": "sosyal_bilgiler"})
        check(r.json().get("yeni_eklenen") == 1, "sosyal bilgiler s4 'vatan' eklendi (çakışmadı)")
        say = await server.db.meb_kelimeleri.count_documents({"kelime": "vatan", "sinif": 4})
        check(say == 2, f"vatan 2 kayıt (türkçe + sosyal) (gelen {say})")

        # Hayat Bilgisi 5. sınıf → 400 (sınıf uyumsuz)
        r = await ac.post("/api/meb-kelime/onayla", headers=HA, json={"kelimeler": ["oyun"], "sinif": 5, "ders": "hayat_bilgisi"})
        check(r.status_code == 400, f"onayla hayat bilgisi s5 → 400 (status={r.status_code})")
        r = await ac.post("/api/meb-kelime/yukle", headers=HA,
                          files={"dosya": ("x.docx", docx, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
                          data={"sinif": "5", "ders": "hayat_bilgisi"})
        check(r.status_code == 400, f"yukle hayat bilgisi s5 → 400 (status={r.status_code})")

        # ders_filtre: sadece sosyal_bilgiler MEB döner
        await server.db.meb_kelimeleri.update_many({"kelime": "vatan", "sinif": 4}, {"$set": {"anlam": "yurt"}})
        s_flt = await kelime_sec(4, 1, ders_filtre=["sosyal_bilgiler"])
        check(len(s_flt) == 1 and s_flt[0]["kaynak"] == "meb" and s_flt[0]["ders"] == "sosyal_bilgiler",
              f"ders_filtre sosyal_bilgiler çalışıyor (gelen {s_flt})")

        # istatistik ders_bazli + ders_x_sinif
        r = await ac.get("/api/meb-kelime/istatistik", headers=HA)
        st = r.json()
        check("ders_bazli" in st and "ders_x_sinif" in st, "istatistik ders_bazli + ders_x_sinif var")
        check(st["ders_bazli"].get("sosyal_bilgiler", {}).get("toplam", 0) >= 1, "sosyal_bilgiler istatistiği")
        check(st["ders_x_sinif"].get("sosyal_bilgiler_4", 0) >= 1, "ders_x_sinif sosyal_bilgiler_4")

        # ── DEDUPE: aynı kelime çoklu sınıfta TEK AI çağrısı ──
        cagri_promptlari = []
        async def sayan_ai(system, user, model="sonnet", max_tokens=3500):
            cagri_promptlari.append(user)
            import re
            kls = re.findall(r"^- ([a-zçğıöşü]+)", user, re.MULTILINE)
            return {"parsed": [{"kelime": k, "anlam": f"{k} anlamı", "ornek_cumle": f"Bir {k}."} for k in kls], "text": "", "error": None}
        mk.call_claude = sayan_ai
        for s in (1, 2, 3):
            await server.db.meb_kelimeleri.insert_one({"id": str(uuid.uuid4()), "kelime": "iletisim", "sinif": s, "ders": "turkce", "anlam": "", "ornek_cumle": "", "durum": "aktif", "kullanim_sayisi": 0})
        await mk._ai_kuyrugu_isle(None, "turkce")
        ilet_docs = await server.db.meb_kelimeleri.find({"kelime": "iletisim"}).to_list(length=10)
        check(len(ilet_docs) == 3 and all(d.get("anlam") == "iletisim anlamı" for d in ilet_docs), "dedupe: 3 iletisim dokümanı da dolduruldu")
        ilet_cagri = sum(1 for p in cagri_promptlari if "- iletisim" in p)
        check(ilet_cagri == 1, f"dedupe: iletisim TEK AI çağrısında (gelen {ilet_cagri})")

        # ── toplu-ai-yenile ilerleme alanları ──
        r = await ac.post("/api/meb-kelime/toplu-ai-yenile", headers=HA, json={"ders": "turkce"})
        pd = r.json()
        check(all(k in pd for k in ("toplam_batch", "tamamlanan_batch", "tahmini_kalan_sure_sn", "benzersiz_kelime")),
              f"toplu-ai-yenile ilerleme alanları mevcut (gelen {list(pd.keys())})")

        # ── KÖPRÜ: AI Eğit (meb_kelime_haritasi) kelimeleri egzersizde de öncelikli ──
        await server.db.meb_kelime_haritasi.insert_one({
            "id": str(uuid.uuid4()), "sinif": 6, "kelime": "fotosentez",
            "anlam": "bitkilerin besin üretmesi", "ornek_cumle": "Yaprak fotosentez yapar.",
        })
        s6 = await kelime_sec(6, 1)  # sınıf 6'da meb_kelimeleri yok → harita'dan gelmeli
        check(len(s6) == 1 and s6[0]["kelime"] == "fotosentez" and s6[0]["kaynak"] == "meb",
              f"köprü: harita kelimesi egzersizde MEB önceliğinde (gelen {s6})")
        s6_str = await meb_kelime_stringleri(6, sadece_anlamli=False)
        check("fotosentez" in s6_str, "köprü: harita kelimesi bulmaca kelime listesinde")

        # ── KÜMÜLATİF SINIF: kitap kelimesi yüklendiği sınıf VE üstünde kullanılır, altında değil ──
        await server.db.meb_kelime_haritasi.insert_one({
            "id": str(uuid.uuid4()), "sinif": 3, "kelime": "gozlem", "anlam": "dikkatle bakma"})
        g1 = await meb_kelime_stringleri(1, sadece_anlamli=True)
        g3 = await meb_kelime_stringleri(3, sadece_anlamli=True)
        g5 = await meb_kelime_stringleri(5, sadece_anlamli=True)
        check("gozlem" not in g1, "3. sınıf kitap kelimesi 1. sınıfta YOK")
        check("gozlem" in g3, "3. sınıf kitap kelimesi 3. sınıfta VAR")
        check("gozlem" in g5, "3. sınıf kitap kelimesi üst sınıfta (5) VAR")
        # Aynı kelime 1. sınıf kitabında da varsa → 1. sınıfta kullanılabilir
        await server.db.meb_kelime_haritasi.insert_one({
            "id": str(uuid.uuid4()), "sinif": 1, "kelime": "ayna", "anlam": "yansıtan cam"})
        await server.db.meb_kelime_haritasi.insert_one({
            "id": str(uuid.uuid4()), "sinif": 3, "kelime": "ayna", "anlam": "yansıtan cam"})
        g1b = await meb_kelime_stringleri(1, sadece_anlamli=True)
        check("ayna" in g1b, "kelime 1. sınıf kitabında da varsa 1. sınıfta kullanılabilir")

        # ── Migration idempotency (mantık testi) ──
        await server.db.meb_kelimeleri.insert_one({"id": str(uuid.uuid4()), "kelime": "eski", "sinif": 1, "durum": "aktif", "anlam": "x", "kullanim_sayisi": 0})
        m1 = await server.db.meb_kelimeleri.update_many({"$or": [{"ders": {"$exists": False}}, {"ders": None}, {"ders": ""}]}, {"$set": {"ders": "turkce"}})
        m2 = await server.db.meb_kelimeleri.update_many({"$or": [{"ders": {"$exists": False}}, {"ders": None}, {"ders": ""}]}, {"$set": {"ders": "turkce"}})
        check(m1.modified_count >= 1 and m2.modified_count == 0, f"migration idempotent (1.={m1.modified_count}, 2.={m2.modified_count})")


if __name__ == "__main__":
    print("=" * 56)
    print("MEB KELIME SMOKE TEST")
    print("=" * 56)
    asyncio.run(run())
    print("\n" + "=" * 56)
    print(f"SONUC: {_g}/{_g + _k} kontrol gecti")
    print("=" * 56)
    sys.exit(0 if _k == 0 else 1)
