"""SPEC B — Ödeme-bazlı öğretmen hakedişi + pay snapshot + gruplu görünüm smoke testi.

Hakediş yalnız veli ödemesi TAMAMLANAN (kalan=0) kurlardan; kısmi ödeme hakediş
doğurmaz; pay snapshot + satır-içi düzeltme (audit); öğretmen pay ucuna erişemez (403);
öğretmene-göre gruplu görünüm; geçiş backfill'i.
    cd appbackend
    .venv/Scripts/python.exe tests/test_hakedis_odeme_smoke.py
"""
import asyncio
import os
import sys

TEST_DB = "oba_test_hakedis_odeme_smoke"
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
    await server.client.drop_database(TEST_DB)

    await db.users.insert_one({"id": "adm", "role": "admin", "ad": "Ad", "soyad": "Min"})
    await db.users.insert_one({"id": "acc", "role": "accountant", "ad": "Mu", "soyad": "Hasebe"})
    await db.users.insert_one({"id": "t1", "role": "teacher", "ad": "Öğ", "soyad": "Bir"})
    await db.teachers.insert_one({"id": "t1", "ad": "Öğ", "soyad": "Bir", "yapilan_odeme": 0})
    # Öğretmen payı tanımı: genel 500
    await db.sistem_ayarlari.insert_one({"tip": "ogretmen_paylari", "degerler": {"genel": 500, "turler": {}}})

    def ogr(oid, gereken, yapilan):
        return {"id": oid, "ad": "Ö", "soyad": oid, "sinif": "5", "veli_ad": "V", "veli_soyad": "L",
                "veli_telefon": "5", "aldigi_egitim": "Genel", "kur": "1", "ogretmen_id": "t1",
                "yapilmasi_gereken_odeme": gereken, "yapilan_odeme": yapilan}
    # s1: kısmi ödeyecek; s2: tam ödeyecek
    await db.students.insert_one(ogr("s1", 1000, 0))
    await db.students.insert_one(ogr("s2", 1000, 0))
    for sid in ("s1", "s2"):
        await db.kur_ucretleri.insert_one({"id": f"{sid}k1", "ogrenci_id": sid, "kur_adi": "1",
                                           "tutar": 1000, "egitim_turu": "Genel", "ogretmen_pay": 500,
                                           "durum": "acik"})

    def H(uid):
        return {"Authorization": f"Bearer {server.create_access_token({'sub': uid})}"}

    async with AsyncClient(transport=ASGITransport(app=server.app), base_url="http://test") as ac:
        # 1) KISMİ ödeme → hakediş doğmaz (odeme_tamamlanma_tarihi damgalanmaz)
        r = await ac.patch("/api/muhasebe/kisi/ogrenci/s1", headers=H("acc"), json={"yapilan_odeme": 400})
        check(r.status_code == 200, "s1 kısmi ödeme kaydedildi")
        k = await db.kur_ucretleri.find_one({"id": "s1k1"})
        check(not k.get("odeme_tamamlanma_tarihi"), "kısmi ödeme → damga YOK")

        # 2) TAM ödeme → damga konur (hakediş tetikleyici)
        r = await ac.patch("/api/muhasebe/kisi/ogrenci/s2", headers=H("acc"), json={"yapilan_odeme": 1000})
        check(r.status_code == 200, "s2 tam ödeme kaydedildi")
        k2 = await db.kur_ucretleri.find_one({"id": "s2k1"})
        check(bool(k2.get("odeme_tamamlanma_tarihi")), "tam ödeme → damga KONDU")

        # 3) Dönem hakedişi: yalnız tam ödenen s2 (pay 500) girer, s1 girmez
        r = await ac.get("/api/muhasebe/ogretmen-donem", headers=H("adm"))
        check(r.status_code == 200, "dönem listesi 200")
        grup = next((g for g in r.json().get("ogretmenler", []) if g["ogretmen_id"] == "t1"), None)
        check(grup is not None and abs(grup["toplam"] - 500) < 0.01, f"hakediş=500 (yalnız tam ödenen) ({grup and grup.get('toplam')})")
        kur_idler = [x["kur_ucreti_id"] for x in (grup or {}).get("kurlar", [])]
        check("s2k1" in kur_idler and "s1k1" not in kur_idler, "yalnız s2k1 hakedişte, s1k1 yok")

        # 4) s1 kalanını tamamla → artık hakedişe girer
        await ac.patch("/api/muhasebe/kisi/ogrenci/s1", headers=H("acc"), json={"yapilan_odeme": 1000})
        r = await ac.get("/api/muhasebe/ogretmen-donem", headers=H("adm"))
        grup = next((g for g in r.json().get("ogretmenler", []) if g["ogretmen_id"] == "t1"), None)
        check(grup and abs(grup["toplam"] - 1000) < 0.01, f"iki kur tam ödendi → hakediş=1000 ({grup and grup.get('toplam')})")

        # 5) Satır-içi pay düzeltme (admin/muhasebe) + audit
        r = await ac.patch("/api/muhasebe/kur-ucreti/s1k1/pay", headers=H("acc"), json={"ogretmen_pay": 700})
        check(r.status_code == 200 and r.json().get("ogretmen_pay") == 700, "pay 700'e düzeltildi")
        log = await db.islem_log.find_one({"hedef_id": "s1k1", "alan": "ogretmen_pay"})
        check(log is not None, "pay değişikliği audit'e düştü")
        r = await ac.get("/api/muhasebe/ogretmen-donem", headers=H("adm"))
        grup = next((g for g in r.json().get("ogretmenler", []) if g["ogretmen_id"] == "t1"), None)
        check(grup and abs(grup["toplam"] - 1200) < 0.01, f"düzeltilen snapshot hakedişe yansıdı=1200 ({grup and grup.get('toplam')})")

        # 6) Öğretmen pay ucuna ERİŞEMEZ (403)
        r = await ac.patch("/api/muhasebe/kur-ucreti/s2k1/pay", headers=H("t1"), json={"ogretmen_pay": 999})
        check(r.status_code == 403, f"öğretmen pay düzeltemez → 403 ({r.status_code})")

        # 7) Gruplu görünüm: öğretmen özeti (öğrenci sayısı, toplamlar, bu dönem hakediş)
        r = await ac.get("/api/muhasebe/ogretmen-gruplu", headers=H("adm"))
        check(r.status_code == 200, "gruplu görünüm 200")
        g = next((x for x in r.json().get("gruplar", []) if x["ogretmen_id"] == "t1"), None)
        check(g and g["ogrenci_sayisi"] == 2, f"t1 grubunda 2 öğrenci ({g and g.get('ogrenci_sayisi')})")
        check(g and abs(g["beklenen"] - 2000) < 0.01 and abs(g["odenen"] - 2000) < 0.01 and abs(g["kalan"]) < 0.01,
              "grup toplamları: beklenen 2000, ödenen 2000, kalan 0")
        check(g and abs(g["bu_donem_hakedis"] - 1200) < 0.01, "grup bu dönem hakediş=1200")

        # 8) Öğretmen pay ucuna erişemez — teacher gruplu görünüme de erişemez (403)
        r = await ac.get("/api/muhasebe/ogretmen-gruplu", headers=H("t1"))
        check(r.status_code == 403, f"öğretmen gruplu görünüme erişemez → 403 ({r.status_code})")

        # 9) Geçiş backfill: eldeki tam-ödenmiş ama damgasız kur → damgalanır (idempotent)
        await db.kur_ucretleri.insert_one({"id": "eskik", "ogrenci_id": "s2", "kur_adi": "0",
                                           "tutar": 0, "egitim_turu": "Genel", "durum": "tamamlandi"})
        r = await ac.post("/api/muhasebe/gecis/odeme-tarihi-backfill", headers=H("adm"))
        check(r.status_code == 200 and r.json().get("damgalanan_kur", -1) >= 0, "backfill çalıştı")

    await server.client.drop_database(TEST_DB)


def main():
    asyncio.run(run())
    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    sys.exit(0 if _kalan == 0 else 1)


if __name__ == "__main__":
    main()
