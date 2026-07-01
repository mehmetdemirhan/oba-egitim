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
    # Korunması gerekenler (over-stemming YOK)
    check(kok("kelime") == "kelime", f"koru: kelime (gelen {kok('kelime')})")
    check(kok("papatya") == "papatya", f"koru: papatya (gelen {kok('papatya')})")
    check(kok("doğa") == "doğa", f"koru: doğa (gelen {kok('doğa')})")
    check(kok("oda") == "oda", f"koru: oda (gelen {kok('oda')})")
    # _tum_kelimeleri_cikar köke indirip tekilleştiriyor
    cikan = bt._tum_kelimeleri_cikar("kelebekler kelebeği kelebek ilkbaharda ilkbahar")
    check(cikan.count("kelebek") == 1 and "ilkbahar" in cikan, f"tarama köke indirip tekilleştiriyor (gelen {cikan})")

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
