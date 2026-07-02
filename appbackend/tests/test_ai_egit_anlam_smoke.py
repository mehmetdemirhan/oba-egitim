"""AI Eğit — ham kitap kelimelerine anlam üretimi (batch+dedupe) smoke testi.

    cd appbackend
    .venv/Scripts/python.exe tests/test_ai_egit_anlam_smoke.py

Kapsam:
  - Anlamı boş kelimelere AI (mock) ile anlam üretilir
  - Aynı kelime birden çok sınıfta boşsa TEK çağrıyla üretilir (dedupe), tüm boş
    kayıtlara yazılır
  - Zaten anlamı olan kelime KORUNUR (üzerine yazılmaz)
  - /anlam-uret endpoint'i ilerleme alanları döndürür + öğrenci 403
"""
import asyncio
import os
import sys
import uuid

TEST_DB = "oba_test_ai_egit_anlam_smoke"
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


async def run():
    import server  # noqa
    import modules.ai_bilgi_tabani as bt
    from core.db import db
    from core.auth import create_access_token
    from httpx import AsyncClient, ASGITransport

    await server.client.drop_database(TEST_DB)

    # ── Türkçe kök bulma (stemmer) birim testleri ──
    kok = bt._turkce_kok
    check(kok("yansımasını") == "yansıma", f"kök: yansımasını→yansıma (gelen {kok('yansımasını')})")
    check(kok("ilkbaharda") == "ilkbahar", f"kök: ilkbaharda→ilkbahar (gelen {kok('ilkbaharda')})")
    check(kok("kelebekler") == "kelebek", f"kök: kelebekler→kelebek (gelen {kok('kelebekler')})")
    check(kok("evlerinden") == "ev", f"kök: evlerinden→ev (gelen {kok('evlerinden')})")
    check(kok("haritası") == "harita", f"kök: haritası→harita (gelen {kok('haritası')})")
    check(kok("kapıyı") == "kapı", f"kök: kapıyı→kapı (gelen {kok('kapıyı')})")
    check(kok("kapıya") == "kapı", f"kök: kapıya→kapı (gelen {kok('kapıya')})")
    # Korunması gerekenler (over-stemming YOK)
    check(kok("kelime") == "kelime", f"koru: kelime (gelen {kok('kelime')})")
    check(kok("papatya") == "papatya", f"koru: papatya (gelen {kok('papatya')})")
    check(kok("doğa") == "doğa", f"koru: doğa (gelen {kok('doğa')})")
    check(kok("oda") == "oda", f"koru: oda (gelen {kok('oda')})")
    # _tum_kelimeleri_cikar köke indirip tekilleştiriyor
    cikan = bt._tum_kelimeleri_cikar("kelebekler kelebeği kelebek ilkbaharda ilkbahar")
    check(cikan.count("kelebek") == 1 and "ilkbahar" in cikan, f"tarama köke indirip tekilleştiriyor (gelen {cikan})")
    # Filtreler: özel isim + ünlüsüz artefakt (küçük metin eşiği)
    c2 = bt._tum_kelimeleri_cikar("Ali kitap okudu. Ali kitap sever. Betül geldi. kfç xyz kalem kalem.")
    check("ali" not in c2 and "betül" not in c2, f"özel isimler elendi (gelen {c2})")
    check("kfç" not in c2 and "xyz" not in c2, "ünlüsüz artefaktlar elendi")
    check("kitap" in c2 and "kalem" in c2, "gerçek kelimeler kaldı")
    # Min sıklık (büyük metin → eşik 2): tek geçen kelime elenir
    c3 = bt._tum_kelimeleri_cikar("kalem defter " * 210 + " nadirkelimeburada")
    check("kalem" in c3 and "nadirkelimeburada" not in c3, "min sıklık: tek geçen kelime elendi (büyük metin)")
    # Stopword + şapkalı harf normalizasyonu
    check(bt._turkce_kok("millî") == "milli", f"şapkalı: millî→milli (gelen {bt._turkce_kok('millî')})")
    c4 = bt._tum_kelimeleri_cikar("ve kitap ve kalem ve millî millî bayram bayram")
    check("ve" not in c4 and "milli" in c4, f"stopword elendi + şapkalı normalize (gelen {c4})")
    # Ünsüz yumuşaması geri-döndürme (ünlü-başlı ek soyulunca): kitab→kitap, sözcüğ→sözcük
    check(kok("kitabından") == "kitap", f"yumuşama: kitabından→kitap (gelen {kok('kitabından')})")
    check(kok("ağacından") == "ağaç", f"yumuşama: ağacından→ağaç (gelen {kok('ağacından')})")
    check(kok("kanadından") == "kanat", f"yumuşama: kanadından→kanat (gelen {kok('kanadından')})")
    # İyelik+belirtme (-ını/-ini) ve çoğul+hâl (-lere/-lerle/-lerdeki) birleşmeleri
    check(kok("adını") == "ad", f"ek: adını→ad (gelen {kok('adını')})")
    check(kok("sözcüğünü") == "sözcük", f"ek: sözcüğünü→sözcük (gelen {kok('sözcüğünü')})")
    check(kok("sözcüklere") == "sözcük" and kok("sözcüklerle") == "sözcük",
          f"ek: sözcüklere/lerle→sözcük (gelen {kok('sözcüklere')}, {kok('sözcüklerle')})")
    check(kok("görsellerdeki") == "görsel", f"ek: görsellerdeki→görsel (gelen {kok('görsellerdeki')})")
    # Yeni eklerin over-stem YAPMADIĞI (loanword/kök korunur)
    check(kok("kod") == "kod" and kok("cümle") == "cümle", f"koru: kod/cümle (gelen {kok('kod')}, {kok('cümle')})")
    # Fragman kök + ğ-sonu elemesi (daki, mek, ları, geldiğ → havuza girmez)
    c5 = bt._tum_kelimeleri_cikar("daki mek ları geldiğ kalem kalem defter defter")
    check(all(f not in c5 for f in ("daki", "mek", "ları", "geldiğ")) and "kalem" in c5,
          f"fragman/ğ-sonu elendi (gelen {c5})")
    # KANITLI kök birleştirme: çıplak çekim biçimi, kök metinde varsa köke akıtılır
    c6 = bt._tum_kelimeleri_cikar("kelebek kelebek kelebeği büyüteç büyüteç büyüteci büyüteçle")
    check(c6.count("kelebek") == 1 and "kelebeği" not in c6, f"kanıtlı: kelebeği→kelebek (gelen {c6})")
    check(c6.count("büyüteç") == 1 and "büyüteci" not in c6 and "büyüteçle" not in c6,
          f"kanıtlı: büyüteci/büyüteçle→büyüteç (gelen {c6})")
    # Kanıtsız hedef DOKUNULMAZ (over-stem yok): mill yok → milli korunur
    c7 = bt._tum_kelimeleri_cikar("milli milli sürücü sürücü")
    check("milli" in c7 and "sürücü" in c7 and "mill" not in c7, f"kanıtsız hedef korundu (gelen {c7})")
    # Guard: kısa çift-kanıtlı biçim birleşmez (kapı ≠ kap)
    c8 = bt._tum_kelimeleri_cikar("kapı kapı kap kap")
    check("kapı" in c8 and "kap" in c8, f"guard: kapı≠kap (len<5) (gelen {c8})")
    # PDF satır-sonu tireleme onarımı (_pdf_metin_birlestir)
    nb = bt._pdf_metin_birlestir
    check(nb("ör­\nnekteki") == "örnekteki", f"soft-hyphen birleşti (gelen {nb(chr(0x00ad))!r})")
    check(nb("içe-\nriklere") == "içeriklere", "normal tireleme birleşti")
    check(nb("-A-\namaç") == "-A-\namaç", "sözlük harf başlığı (-A-) korundu")
    # Onarım sonrası kök: örnekteki→örnek, bölünmüş kelime köke iniyor
    check(kok("örnekteki") == "örnek", f"ek: örnekteki→örnek (gelen {kok('örnekteki')})")
    c9 = bt._tum_kelimeleri_cikar("belir­\nleyerek örnek örnek belirle belirle")
    check("leyerek" not in c9, f"tireleme artefaktı (leyerek) havuza girmedi (gelen {c9})")

    # Ham kelimeler (anlam boş) — iletisim iki sınıfta, sorumluluk bir sınıfta
    for s in (3, 5):
        await db.meb_kelime_haritasi.insert_one({"id": str(uuid.uuid4()), "sinif": s, "kelime": "iletisim", "anlam": "", "kaynak_tip": "tam_tarama"})
    await db.meb_kelime_haritasi.insert_one({"id": str(uuid.uuid4()), "sinif": 3, "kelime": "sorumluluk", "anlam": "", "kaynak_tip": "tam_tarama"})
    # Zaten anlamı olan kelime — korunmalı
    await db.meb_kelime_haritasi.insert_one({"id": str(uuid.uuid4()), "sinif": 3, "kelime": "elma", "anlam": "bir meyve", "kaynak_tip": "ai_secili"})

    # Mock AI (yeni prompt: "- kelime (X. sınıf)")
    cagrilar = []
    async def sahte(system, user, model="sonnet", max_tokens=3500):
        import re
        cagrilar.append(user)
        kls = re.findall(r"^- ([a-zçğıöşü]+)", user, re.MULTILINE)
        return {"parsed": [{"kelime": k, "anlam": f"{k} anlamı", "ornek_cumle": f"Bir {k}.", "zorluk": 4} for k in kls]}
    bt.call_claude = sahte
    bt.AI_HARITA_BEKLEME = 0

    await bt._harita_anlam_uret(None)  # global

    # iletisim iki sınıfta da doldu mu?
    ilet = await db.meb_kelime_haritasi.find({"kelime": "iletisim"}).to_list(length=10)
    check(len(ilet) == 2 and all(x.get("anlam") == "iletisim anlamı" for x in ilet), "dedupe: iletisim 2 sınıfta da dolduruldu")
    ilet_cagri = sum(1 for u in cagrilar if "- iletisim" in u)
    check(ilet_cagri == 1, f"dedupe: iletisim TEK AI çağrısında (gelen {ilet_cagri})")

    sor = await db.meb_kelime_haritasi.find_one({"kelime": "sorumluluk"})
    check(sor.get("anlam") == "sorumluluk anlamı", "sorumluluk anlam üretildi")

    elma = await db.meb_kelime_haritasi.find_one({"kelime": "elma"})
    check(elma.get("anlam") == "bir meyve", "mevcut anlamlı kelime KORUNDU")

    bos_kalan = await db.meb_kelime_haritasi.count_documents({"anlam": {"$in": [None, ""]}})
    check(bos_kalan == 0, f"tüm ham kelimeler dolduruldu (kalan boş: {bos_kalan})")

    # ── Endpoint: ilerleme alanları + yetki ──
    adm = str(uuid.uuid4()); stu = str(uuid.uuid4())
    await db.users.insert_one({"id": adm, "ad": "A", "soyad": "Y", "role": "admin"})
    await db.users.insert_one({"id": stu, "ad": "S", "soyad": "Y", "role": "student"})
    # yeni boş kelime ekle ki endpoint kuyruk başlatsın
    await db.meb_kelime_haritasi.insert_one({"id": str(uuid.uuid4()), "sinif": 4, "kelime": "cevre", "anlam": "", "kaynak_tip": "tam_tarama"})
    HA = {"Authorization": f"Bearer {create_access_token({'sub': adm})}"}
    HS = {"Authorization": f"Bearer {create_access_token({'sub': stu})}"}
    transport = ASGITransport(app=server.app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.post("/api/ai/bilgi-tabani/anlam-uret", headers=HS, json={})
        check(r.status_code == 403, f"öğrenci anlam-uret 403 (status={r.status_code})")
        r = await ac.post("/api/ai/bilgi-tabani/anlam-uret", headers=HA, json={})
        d = r.json()
        check(r.status_code == 200 and all(x in d for x in ("bekleyen_kelime", "benzersiz_kelime", "toplam_batch", "tahmini_kalan_sure_sn")),
              f"anlam-uret ilerleme alanları (gelen {list(d.keys()) if r.status_code==200 else r.status_code})")

    await server.client.drop_database(TEST_DB)


if __name__ == "__main__":
    print("=" * 56)
    print("AI EGIT ANLAM URETIM SMOKE TEST")
    print("=" * 56)
    asyncio.run(run())
    print("\n" + "=" * 56)
    print(f"SONUC: {_g}/{_g + _k} kontrol gecti")
    print("=" * 56)
    sys.exit(0 if _k == 0 else 1)
