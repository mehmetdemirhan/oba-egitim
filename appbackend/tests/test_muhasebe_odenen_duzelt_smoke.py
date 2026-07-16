"""Muhasebe — "Ödenen" satır-içi düzeltme zinciri smoke testi.

Öğrenci "Ödenen" hücresi öğrencinin TOPLAM ödemesini (yapilan_odeme) düzenler; FIFO
en-eski-borç-önce dağıtır. Bu uç, hem DÜZ LİSTE hem ÖĞRETMENE GÖRE görünümün çağırdığı
TEK backend yoludur (PATCH /muhasebe/kisi/ogrenci/{id}) — görünüme göre fark yoktur.

Doğrular:
  1) Kısmi ödeme → kalan güncellenir, hakediş damgası YOK.
  2) Tam ödeme (kalan=0) → hakediş tetiği: kur damgalanır, dönem hakedişine girer.
  3) Her elle değişiklik audit'e düşer (yapilan_odeme + odeme_tamamlanma).
  4) Geri alma: ödenen azaltılıp kalan>0 → damga KALKAR (henüz ödenmemiş dönem),
     kur hakedişten düşer, audit'e "odeme_tamamlanma_geri" düşer.
  5) Fazla ödeme (beklenen aşılır) → 200, ENGELLENMEZ; kalan=0.
  6) Zaten ödenmiş döneme (odendi_donem) girmiş kur geri alınırsa damga KALMAYA
     devam eder + "hakedis_uyari" loglanır (otomatik geri alınmaz).
  7) "Öğr. Payı" düzeltme (diğer düzenlenebilir sütun) + audit; öğretmen 403 (iki uç).

    cd appbackend
    PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe tests/test_muhasebe_odenen_duzelt_smoke.py
"""
import asyncio
import os
import sys

TEST_DB = "oba_test_muhasebe_odenen_duzelt"
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
    await db.users.insert_one({"id": "t1", "role": "teacher", "ad": "Öğ", "soyad": "Bir"})
    await db.teachers.insert_one({"id": "t1", "ad": "Öğ", "soyad": "Bir", "yapilan_odeme": 0})
    await db.sistem_ayarlari.insert_one({"tip": "ogretmen_paylari", "degerler": {"genel": 500, "turler": {}}})

    def ogr(oid, gereken):
        return {"id": oid, "ad": "Ö", "soyad": oid, "sinif": "5", "veli_ad": "V", "veli_soyad": "L",
                "veli_telefon": "5", "aldigi_egitim": "Genel", "kur": "1", "ogretmen_id": "t1",
                "yapilmasi_gereken_odeme": gereken, "yapilan_odeme": 0}
    # sA: Ödenen düzeltme + tetik/geri-al senaryosu; sB: Öğr.Payı + yetki senaryosu
    await db.students.insert_one(ogr("sA", 1000))
    await db.students.insert_one(ogr("sB", 1000))
    await db.kur_ucretleri.insert_one({"id": "kA", "ogrenci_id": "sA", "kur_adi": "1",
                                       "tutar": 1000, "egitim_turu": "Genel", "ogretmen_pay": 500, "durum": "acik"})
    await db.kur_ucretleri.insert_one({"id": "kB", "ogrenci_id": "sB", "kur_adi": "1",
                                       "tutar": 1000, "egitim_turu": "Genel", "ogretmen_pay": 500, "durum": "acik"})

    def H(uid):
        return {"Authorization": f"Bearer {server.create_access_token({'sub': uid})}"}

    async def hakediste(oid, kur_id):
        r = await ac.get("/api/muhasebe/ogretmen-donem", headers=H("adm"))
        grup = next((g for g in r.json().get("ogretmenler", []) if g["ogretmen_id"] == oid), None)
        return kur_id in [x["kur_ucreti_id"] for x in (grup or {}).get("kurlar", [])]

    async with AsyncClient(transport=ASGITransport(app=server.app), base_url="http://test") as ac:
        # 1) KISMİ ödeme → kalan güncellenir, damga YOK
        r = await ac.patch("/api/muhasebe/kisi/ogrenci/sA", headers=H("acc"), json={"yapilan_odeme": 400})
        check(r.status_code == 200 and abs(r.json().get("kalan", -1) - 600) < 0.01, f"kısmi ödeme kalan=600 ({r.json().get('kalan')})")
        kA = await db.kur_ucretleri.find_one({"id": "kA"})
        check(not kA.get("odeme_tamamlanma_tarihi"), "kısmi → hakediş damgası YOK")
        check(not await hakediste("t1", "kA"), "kısmi → kA hakedişte değil")

        # 2) TAM ödeme (kalan=0) → hakediş tetiği: damga + döneme girer
        r = await ac.patch("/api/muhasebe/kisi/ogrenci/sA", headers=H("acc"), json={"yapilan_odeme": 1000})
        check(r.status_code == 200 and abs(r.json().get("kalan", -1)) < 0.01, "tam ödeme kalan=0")
        kA = await db.kur_ucretleri.find_one({"id": "kA"})
        check(bool(kA.get("odeme_tamamlanma_tarihi")), "tam → hakediş damgası KONDU")
        check(await hakediste("t1", "kA"), "tam → kA hakedişe girdi")

        # 3) Audit: yapilan_odeme değişikliği + tamamlanma damgası
        log_odeme = await db.islem_log.find_one({"hedef_id": "sA", "alan": "yapilan_odeme"})
        check(log_odeme is not None, "yapilan_odeme değişikliği audit'e düştü (kim/eski→yeni)")
        log_tetik = await db.islem_log.find_one({"hedef_id": "kA", "alan": "odeme_tamamlanma"})
        check(log_tetik is not None, "hakediş tetiği audit'e düştü")

        # 4) GERİ ALMA: ödenen azaltılıp kalan>0 → damga KALKAR, hakedişten düşer, audit
        r = await ac.patch("/api/muhasebe/kisi/ogrenci/sA", headers=H("acc"), json={"yapilan_odeme": 500})
        check(r.status_code == 200 and abs(r.json().get("kalan", -1) - 500) < 0.01, "geri alma kalan=500")
        kA = await db.kur_ucretleri.find_one({"id": "kA"})
        check(not kA.get("odeme_tamamlanma_tarihi"), "geri alma → damga KALKTI")
        check(not await hakediste("t1", "kA"), "geri alma → kA hakedişten düştü")
        log_geri = await db.islem_log.find_one({"hedef_id": "kA", "alan": "odeme_tamamlanma_geri"})
        check(log_geri is not None, "hakediş geri alma audit'e düştü")

        # 5) FAZLA ödeme → 200 (ENGELLENMEZ), kalan=0
        r = await ac.patch("/api/muhasebe/kisi/ogrenci/sA", headers=H("acc"), json={"yapilan_odeme": 1500})
        check(r.status_code == 200 and abs(r.json().get("kalan", -1)) < 0.01, "fazla ödeme engellenmedi, kalan=0")

        # 6) Zaten ödenmiş döneme girmiş kur geri alınırsa: damga KALIR + uyarı loglanır
        await db.kur_ucretleri.update_one({"id": "kA"}, {"$set": {"odendi_donem": "2026-07-15"}})
        r = await ac.patch("/api/muhasebe/kisi/ogrenci/sA", headers=H("acc"), json={"yapilan_odeme": 100})
        check(r.status_code == 200, "ödenmiş dönem kuru geri alma isteği 200")
        kA = await db.kur_ucretleri.find_one({"id": "kA"})
        check(bool(kA.get("odeme_tamamlanma_tarihi")), "ödenmiş dönem → damga otomatik KALKMADI")
        log_uyari = await db.islem_log.find_one({"hedef_id": "kA", "alan": "hakedis_uyari"})
        check(log_uyari is not None, "ödenmiş dönem geri alma denemesi 'hakedis_uyari' loglandı")

        # 7) "Öğr. Payı" düzeltme (diğer düzenlenebilir sütun) + audit; öğretmen 403 (iki uç)
        r = await ac.patch("/api/muhasebe/kur-ucreti/kB/pay", headers=H("acc"), json={"ogretmen_pay": 700})
        check(r.status_code == 200 and r.json().get("ogretmen_pay") == 700, "Öğr. Payı 700'e düzeltildi")
        check(await db.islem_log.find_one({"hedef_id": "kB", "alan": "ogretmen_pay"}) is not None, "pay değişikliği audit'e düştü")
        r = await ac.patch("/api/muhasebe/kur-ucreti/kB/pay", headers=H("t1"), json={"ogretmen_pay": 999})
        check(r.status_code == 403, f"öğretmen Öğr. Payı düzeltemez → 403 ({r.status_code})")
        r = await ac.patch("/api/muhasebe/kisi/ogrenci/sB", headers=H("t1"), json={"yapilan_odeme": 999})
        check(r.status_code == 403, f"öğretmen Ödenen düzeltemez → 403 ({r.status_code})")

    await server.client.drop_database(TEST_DB)


if __name__ == "__main__":
    asyncio.run(run())
    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    sys.exit(1 if _kalan else 0)
