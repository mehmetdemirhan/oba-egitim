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
    from core.kelime_secici import kelime_sec
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
        async def sahte_ai(system, user, model="sonnet", max_tokens=2000):
            import re
            kls = re.findall(r"[a-zçğıöşü]+", user.split("içindir:")[1].split("\n")[0]) if "içindir:" in user else []
            return {"parsed": {"sonuclar": [{"kelime": k, "anlam": f"{k} anlamı", "ornek_cumle": f"Bir {k}.", "etiketler": ["test"]} for k in kls]}, "text": "", "error": None}
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

        # Arka plan AI görevinin bitmesini bekle
        for _ in range(100):
            if 1 not in mk._ai_aktif:
                break
            await asyncio.sleep(0.05)
        dolu = await server.db.meb_kelimeleri.count_documents({"sinif": 1, "anlam": {"$nin": [None, ""]}})
        check(dolu == 8, f"AI 8 kelimeye anlam üretti (gelen {dolu})")
        ornek = await server.db.meb_kelimeleri.find_one({"sinif": 1, "kelime": "elma"})
        check(ornek.get("anlam") and ornek.get("durum") == "aktif", "elma anlam+aktif")

        # ── kelime_secici önceliği ──
        secim = await kelime_sec(1, 5)
        check(len(secim) == 5, "kelime_sec 5 döndürdü")
        check(all(s["kaynak"] == "meb" for s in secim), "hepsi MEB kaynaklı (öncelik)")
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


if __name__ == "__main__":
    print("=" * 56)
    print("MEB KELIME SMOKE TEST")
    print("=" * 56)
    asyncio.run(run())
    print("\n" + "=" * 56)
    print(f"SONUC: {_g}/{_g + _k} kontrol gecti")
    print("=" * 56)
    sys.exit(0 if _k == 0 else 1)
