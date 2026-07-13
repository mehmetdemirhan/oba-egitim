"""SPEC A — "Eğitimi Tamamladı" (mezuniyet) akışı smoke testi.

Borçsuz tamamlama → arşiv; borçlu → arşive kalkmaz (muhasebede kalır) → borç kapanınca
otomatik arşiv; geri alma; başkasının öğrencisi 403; bildirim + audit; mezun filtresi.
    cd appbackend
    .venv/Scripts/python.exe tests/test_egitim_tamamla_smoke.py
"""
import asyncio
import os
import sys

TEST_DB = "oba_test_egitim_tamamla_smoke"
os.environ["MONGO_URL"] = os.environ.get("MONGO_URL_TEST", "mongodb://localhost:27017")
os.environ["DB_NAME"] = TEST_DB
os.environ.setdefault("SECRET_KEY", "test-secret-key")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_gecen = 0
_kalan = 0


def check(kosul, mesaj):
    global _gecen, _kalan
    if kosul:
        _gecen += 1
        print(f"  [GECTI] {mesaj}")
    else:
        _kalan += 1
        print(f"  [KALDI] {mesaj}")


async def run():
    import server
    from httpx import AsyncClient, ASGITransport

    db = server.db
    await db.client.drop_database(TEST_DB) if hasattr(db, "client") else await server.client.drop_database(TEST_DB)

    # Kullanıcılar: admin, 2 öğretmen, muhasebe
    await db.users.insert_one({"id": "adm", "role": "admin", "ad": "Ad", "soyad": "Min"})
    await db.users.insert_one({"id": "t1", "role": "teacher", "ad": "Öğ", "soyad": "Bir"})
    await db.users.insert_one({"id": "t2", "role": "teacher", "ad": "Öğ", "soyad": "İki"})
    await db.teachers.insert_one({"id": "t1", "ad": "Öğ", "soyad": "Bir"})
    await db.teachers.insert_one({"id": "t2", "ad": "Öğ", "soyad": "İki"})
    # Öğrenciler: borçsuz (s1, t1), borçlu (s2, t1)
    def ogr(oid, ad, gereken, yapilan):
        return {"id": oid, "ad": ad, "soyad": "Ö", "sinif": "5", "veli_ad": "V", "veli_soyad": "Li",
                "veli_telefon": "5550000000", "aldigi_egitim": "Genel", "kur": "1", "ogretmen_id": "t1",
                "yapilmasi_gereken_odeme": gereken, "yapilan_odeme": yapilan}
    await db.students.insert_one(ogr("s1", "Borçsuz", 1000, 1000))
    await db.students.insert_one(ogr("s2", "Borçlu", 1000, 400))
    await db.kur_ucretleri.insert_one({"id": "s2k1", "ogrenci_id": "s2", "kur_adi": "1", "tutar": 1000, "durum": "acik"})

    def H(uid):
        return {"Authorization": f"Bearer {server.create_access_token({'sub': uid})}"}

    async with AsyncClient(transport=ASGITransport(app=server.app), base_url="http://test") as ac:
        # 1) Başka öğretmenin öğrencisini tamamlayamaz (403)
        r = await ac.post("/api/students/s1/egitim-tamamla", headers=H("t2"))
        check(r.status_code == 403, f"başkasının öğrencisi → 403 ({r.status_code})")

        # 2) Borçsuz tamamlama → mezun + arşiv
        r = await ac.post("/api/students/s1/egitim-tamamla", headers=H("t1"))
        check(r.status_code == 200 and r.json().get("arsivlendi") is True, "borçsuz tamamlama → arşivlendi")
        s1 = await db.students.find_one({"id": "s1"})
        check(s1.get("mezun") and s1.get("arsivli"), "s1 mezun + arsivli")
        check(s1.get("tamamlama_tarihi") and s1.get("tamamlayan_id") == "t1", "tamamlama tarihi + tamamlayan kaydedildi")

        # 3) Audit + bildirim
        log = await db.islem_log.find_one({"hedef_id": "s1", "islem": "egitim_tamamla"})
        check(log is not None, "tamamlama islem_log'a düştü")
        bil = await db.bildirimler.find_one({"alici_id": "adm", "tur": "egitim_tamamla"})
        check(bil is not None and "borç: yok" in (bil.get("icerik") or ""), "admin'e bildirim (borç: yok)")

        # 4) Mezun filtresi: aktif listede yok, mezun listesinde var
        aktif = (await ac.get("/api/students", headers=H("adm"))).json()
        check(not any(x["id"] == "s1" for x in aktif), "s1 aktif listede yok")
        mezunlar = (await ac.get("/api/students", headers=H("adm"), params={"durum": "mezun"})).json()
        check(any(x["id"] == "s1" for x in mezunlar), "s1 Eğitimi Tamamlayanlar listesinde")

        # 5) Zaten mezun → 409
        r = await ac.post("/api/students/s1/egitim-tamamla", headers=H("t1"))
        check(r.status_code == 409, f"zaten mezun → 409 ({r.status_code})")

        # 6) Borçlu tamamlama → mezun ama arşive KALKMAZ
        r = await ac.post("/api/students/s2/egitim-tamamla", headers=H("t1"))
        check(r.status_code == 200 and r.json().get("arsivlendi") is False, "borçlu tamamlama → arşivlenmedi")
        s2 = await db.students.find_one({"id": "s2"})
        check(s2.get("mezun") and not s2.get("arsivli"), "s2 mezun ama arsivli DEĞİL (muhasebede kalır)")
        bil2 = await db.bildirimler.find_one({"alici_id": "adm", "tur": "egitim_tamamla", "ilgili_id": "s2"})
        check(bil2 and "₺600" in (bil2.get("icerik") or ""), "admin'e bildirim (borç ₺600)")

        # 7) Borç kapanınca otomatik arşiv (muhasebe ödeme akışı hook'u)
        r = await ac.patch("/api/muhasebe/kisi/ogrenci/s2", headers=H("adm"), json={"yapilan_odeme": 1000})
        check(r.status_code == 200, "borç kapatma ödemesi kaydedildi")
        s2b = await db.students.find_one({"id": "s2"})
        check(s2b.get("arsivli") is True, "borç kapanınca s2 OTOMATİK arşivlendi")

        # 8) Geri alma: admin her zaman
        r = await ac.post("/api/students/s1/egitim-tamamla-geri-al", headers=H("adm"))
        check(r.status_code == 200, "admin geri alma 200")
        s1b = await db.students.find_one({"id": "s1"})
        check(not s1b.get("mezun") and not s1b.get("arsivli"), "s1 aktife döndü")
        glog = await db.islem_log.find_one({"hedef_id": "s1", "islem": "egitim_tamamla_geri_al"})
        check(glog is not None, "geri alma loglandı")

        # 9) Öğretmen 7 gün sonrası geri alamaz (eski tamamlama tarihi)
        await db.students.update_one({"id": "s2"}, {"$set": {
            "mezun": True, "arsivli": False, "tamamlayan_id": "t1", "tamamlayan_rol": "teacher",
            "tamamlama_tarihi": "2020-01-01T00:00:00+00:00"}})
        r = await ac.post("/api/students/s2/egitim-tamamla-geri-al", headers=H("t1"))
        check(r.status_code == 403, f"öğretmen 7 gün sonrası geri alamaz → 403 ({r.status_code})")

    await server.client.drop_database(TEST_DB)


def main():
    asyncio.run(run())
    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    sys.exit(0 if _kalan == 0 else 1)


if __name__ == "__main__":
    main()
