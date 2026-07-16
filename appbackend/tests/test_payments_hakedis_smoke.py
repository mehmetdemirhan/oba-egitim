"""Ödeme satırı (POST/PUT/DELETE /payments) → muhasebe ile AYNI hakediş zinciri smoke.

"Ödeme satırı ekle/düzelt/sil" yolu artık muhasebe PATCH ile aynı ortak fonksiyondan
(_odeme_sonrasi_islem) geçer: kalan=0 → tamamlanma damgası + hakediş tetiği; azaltma/
silme kalan'ı >0'a çıkarırsa geri-alma (henüz ödenmemiş kurun damgası kalkar); zaten
ödenmiş döneme (odendi_donem) girmiş kur otomatik geri alınmaz → "hakedis_uyari" loglanır.

    cd appbackend
    PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe tests/test_payments_hakedis_smoke.py
"""
import asyncio
import os
import sys

TEST_DB = "oba_test_payments_hakedis"
os.environ["MONGO_URL"] = os.environ.get("MONGO_URL_TEST", "mongodb://localhost:27017")
os.environ["DB_NAME"] = TEST_DB
os.environ.setdefault("SECRET_KEY", "test-secret-key")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_gecen = _kalan = 0


def check(kosul, mesaj):
    global _gecen, _kalan
    if kosul:
        _gecen += 1; print(f"  [GECTI] {mesaj}")
    else:
        _kalan += 1; print(f"  [KALDI] {mesaj}")


async def run():
    import server
    from httpx import AsyncClient, ASGITransport

    db = server.db
    await server.client.drop_database(TEST_DB)

    await db.users.insert_one({"id": "adm", "role": "admin", "ad": "Ad", "soyad": "Min"})
    await db.users.insert_one({"id": "acc", "role": "accountant", "ad": "Mu", "soyad": "Hasebe"})
    await db.teachers.insert_one({"id": "t1", "ad": "Öğ", "soyad": "Bir", "yapilan_odeme": 0})
    await db.sistem_ayarlari.insert_one({"tip": "ogretmen_paylari", "degerler": {"genel": 500, "turler": {}}})
    await db.students.insert_one({"id": "s1", "ad": "Ö", "soyad": "1", "aldigi_egitim": "Genel",
                                  "kur": "1", "ogretmen_id": "t1",
                                  "yapilmasi_gereken_odeme": 1000, "yapilan_odeme": 0})
    await db.kur_ucretleri.insert_one({"id": "k1", "ogrenci_id": "s1", "kur_adi": "1",
                                       "tutar": 1000, "egitim_turu": "Genel", "ogretmen_pay": 500, "durum": "acik"})

    def H(uid):
        return {"Authorization": f"Bearer {server.create_access_token({'sub': uid})}"}

    async def hakediste(kur_id):
        r = await ac.get("/api/muhasebe/ogretmen-donem", headers=H("adm"))
        grup = next((g for g in r.json().get("ogretmenler", []) if g["ogretmen_id"] == "t1"), None)
        return kur_id in [x["kur_ucreti_id"] for x in (grup or {}).get("kurlar", [])]

    async def odenen():
        s = await db.students.find_one({"id": "s1"})
        return s.get("yapilan_odeme")

    async with AsyncClient(transport=ASGITransport(app=server.app), base_url="http://test") as ac:
        # 1) POST kısmi ödeme → damga YOK
        r = await ac.post("/api/payments", headers=H("acc"), json={"tip": "ogrenci", "kisi_id": "s1", "miktar": 400})
        check(r.status_code == 200 and await odenen() == 400, f"POST 400 → yapilan_odeme=400 ({await odenen()})")
        k1 = await db.kur_ucretleri.find_one({"id": "k1"})
        check(not k1.get("odeme_tamamlanma_tarihi"), "kısmi ödeme satırı → damga YOK")
        check(not await hakediste("k1"), "kısmi → k1 hakedişte değil")

        # 2) POST kalanı tamamla → kalan=0 → damga + hakediş tetiği
        r = await ac.post("/api/payments", headers=H("acc"), json={"tip": "ogrenci", "kisi_id": "s1", "miktar": 600})
        pid_600 = r.json().get("id")
        check(r.status_code == 200 and await odenen() == 1000, "POST 600 → yapilan_odeme=1000")
        k1 = await db.kur_ucretleri.find_one({"id": "k1"})
        check(bool(k1.get("odeme_tamamlanma_tarihi")), "tam ödeme satırı → damga KONDU")
        check(await hakediste("k1"), "tam → k1 hakedişe girdi")

        # 3) DELETE → kalan tekrar >0 → geri alma (damga kalkar), hakedişten düşer
        r = await ac.delete(f"/api/payments/{pid_600}", headers=H("acc"))
        check(r.status_code == 200 and await odenen() == 400, "DELETE 600 → yapilan_odeme=400")
        k1 = await db.kur_ucretleri.find_one({"id": "k1"})
        check(not k1.get("odeme_tamamlanma_tarihi"), "silme → damga KALKTI (geri alma)")
        check(not await hakediste("k1"), "silme → k1 hakedişten düştü")

        # 4) PUT: bir ödeme satırının miktarını artır → kalan=0 → tekrar tetik
        r = await ac.post("/api/payments", headers=H("acc"), json={"tip": "ogrenci", "kisi_id": "s1", "miktar": 100})
        pid_100 = r.json().get("id")
        r = await ac.put(f"/api/payments/{pid_100}", headers=H("acc"), json={"miktar": 600})
        check(r.status_code == 200 and await odenen() == 1000, "PUT 100→600 → yapilan_odeme=1000")
        k1 = await db.kur_ucretleri.find_one({"id": "k1"})
        check(bool(k1.get("odeme_tamamlanma_tarihi")), "PUT ile tam ödeme → damga KONDU")

        # 5) Ödenmiş döneme girmiş kur: silme geri alamaz → damga kalır + hakedis_uyari
        await db.kur_ucretleri.update_one({"id": "k1"}, {"$set": {"odendi_donem": "2026-07-15"}})
        r = await ac.delete(f"/api/payments/{pid_100}", headers=H("acc"))  # 600 sil → kalan>0
        check(r.status_code == 200, "ödenmiş dönem kuru için silme 200")
        k1 = await db.kur_ucretleri.find_one({"id": "k1"})
        check(bool(k1.get("odeme_tamamlanma_tarihi")), "ödenmiş dönem → damga otomatik KALKMADI")
        check(await db.islem_log.find_one({"hedef_id": "k1", "alan": "hakedis_uyari"}) is not None,
              "ödenmiş dönem silme denemesi 'hakedis_uyari' loglandı")

    await server.client.drop_database(TEST_DB)


if __name__ == "__main__":
    asyncio.run(run())
    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    sys.exit(1 if _kalan else 0)
