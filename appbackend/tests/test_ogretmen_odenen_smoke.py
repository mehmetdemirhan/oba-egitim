"""Muhasebe — kur-bazlı 'Öğr. Ödenen' (avans/erken ödeme) + hakediş netleme + tek kaynak.

Kapsam: (1) avans PATCH → kur.ogretmen_odenen + teachers.yapilan_odeme DELTA $inc + audit +
kalan hesabı; (2) öğretmen 403; (3) avans girilmiş kurda otomatik tetik ateşlenince hakedişe
yalnız NET (pay−avans) girer (mükerrer yok); (4) dönem ödemesi → skaler = avans + net = pay,
kur ogretmen_odenen=pay (mühürlü), mühürlü kurda avans düzeltilemez; (5) özet 'Ödenen' TEK
KAYNAK (teachers.yapilan_odeme) + avans_toplam kırılımı.

    cd appbackend
    PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe tests/test_ogretmen_odenen_smoke.py
"""
import asyncio
import os
import sys

TEST_DB = "oba_test_ogretmen_odenen"
os.environ["MONGO_URL"] = os.environ.get("MONGO_URL_TEST", "mongodb://localhost:27017")
os.environ["DB_NAME"] = TEST_DB
os.environ.setdefault("SECRET_KEY", "test-secret-key")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_gecen = _kalan = 0


def check(k, m):
    global _gecen, _kalan
    if k:
        _gecen += 1; print(f"  [GECTI] {m}")
    else:
        _kalan += 1; print(f"  [KALDI] {m}")


async def run():
    import server
    from httpx import AsyncClient, ASGITransport

    db = server.db
    await server.client.drop_database(TEST_DB)
    await db.users.insert_one({"id": "adm", "role": "admin", "ad": "Ad", "soyad": "Min"})
    await db.users.insert_one({"id": "acc", "role": "accountant", "ad": "Mu", "soyad": "Ha"})
    await db.users.insert_one({"id": "t1", "role": "teacher", "ad": "Öğ", "soyad": "Bir"})
    await db.teachers.insert_one({"id": "t1", "ad": "Öğ", "soyad": "Bir", "yapilan_odeme": 0, "yapilmasi_gereken_odeme": 1000})
    await db.sistem_ayarlari.insert_one({"tip": "ogretmen_paylari", "degerler": {"genel": 1000, "turler": {}}})
    await db.students.insert_one({"id": "s1", "ad": "Ö", "soyad": "s1", "sinif": "5", "aldigi_egitim": "Genel",
                                  "kur": "1", "ogretmen_id": "t1", "yapilmasi_gereken_odeme": 1000, "yapilan_odeme": 0})
    await db.kur_ucretleri.insert_one({"id": "s1k1", "ogrenci_id": "s1", "kur_adi": "1", "tutar": 1000,
                                       "egitim_turu": "Genel", "ogretmen_pay": 1000, "durum": "acik"})

    def H(u):
        return {"Authorization": f"Bearer {server.create_access_token({'sub': u})}"}

    async with AsyncClient(transport=ASGITransport(app=server.app), base_url="http://test") as ac:
        # ── 1) Avans girişi → kur alanı + skaler $inc + audit ──
        r = await ac.patch("/api/muhasebe/kur-ucreti/s1k1/odenen", headers=H("acc"), json={"ogretmen_odenen": 300})
        check(r.status_code == 200 and r.json().get("ogretmen_odenen") == 300 and r.json().get("delta") == 300, f"avans 300 kaydedildi ({r.status_code})")
        t = await db.teachers.find_one({"id": "t1"})
        check(abs((t.get("yapilan_odeme") or 0) - 300) < 0.01, f"teachers.yapilan_odeme += 300 ({t.get('yapilan_odeme')})")
        check(await db.islem_log.find_one({"hedef_id": "s1k1", "alan": "ogretmen_odenen"}) is not None, "avans değişikliği audit'e düştü")
        # kalan (öğretmene) = 1000-300 = 700, /muhasebe/kisiler satırında
        r = await ac.get("/api/muhasebe/kisiler", headers=H("adm"))
        row = next((x for x in r.json()["ogrenciler"] if x.get("kur_ucreti_id") == "s1k1"), None)
        check(row and abs(row["ogretmen_odenen"] - 300) < 0.01 and abs(row["ogretmen_kalan"] - 700) < 0.01, f"kur satırı: ödenen 300, kalan 700 ({row and (row.get('ogretmen_odenen'), row.get('ogretmen_kalan'))})")
        og = next((x for x in r.json()["ogretmenler"] if x["kisi_id"] == "t1"), None)
        check(og and abs(og.get("avans_toplam", 0) - 300) < 0.01 and abs(og["yapilan_odeme"] - 300) < 0.01, f"öğretmen özeti: Ödenen 300 (tek kaynak) + avans_toplam 300 ({og and (og.get('yapilan_odeme'), og.get('avans_toplam'))})")

        # ── 2) Öğretmen bu ucu kullanamaz (403) ──
        check((await ac.patch("/api/muhasebe/kur-ucreti/s1k1/odenen", headers=H("t1"), json={"ogretmen_odenen": 500})).status_code == 403, "öğretmen avans düzeltemez → 403")

        # ── 3) Otomatik tetik: tam ödeme → hakedişe yalnız NET (1000-300=700) ──
        await ac.patch("/api/muhasebe/kisi/ogrenci/s1", headers=H("acc"), json={"yapilan_odeme": 1000})
        k = await db.kur_ucretleri.find_one({"id": "s1k1"})
        check(bool(k.get("odeme_tamamlanma_tarihi")), "tam ödeme → damga kondu")
        r = await ac.get("/api/muhasebe/ogretmen-donem", headers=H("adm"))
        donem = r.json()["donem"]
        grup = next((g for g in r.json()["ogretmenler"] if g["ogretmen_id"] == "t1"), None)
        check(grup and abs(grup["toplam"] - 700) < 0.01, f"hakediş = NET 700 (avans düşüldü, mükerrer yok) ({grup and grup.get('toplam')})")

        # ── 4) Dönem ödemesi → skaler = avans + net = 1000; kur mühürlenir + ödenen=pay ──
        r = await ac.post("/api/muhasebe/ogretmen-donem/ode", headers=H("adm"), json={"ogretmen_id": "t1", "donem": donem})
        check(r.status_code == 200 and abs(r.json()["toplam"] - 700) < 0.01, f"dönem ödemesi net 700 ({r.json().get('toplam')})")
        t = await db.teachers.find_one({"id": "t1"})
        check(abs(t["yapilan_odeme"] - 1000) < 0.01, f"skaler Ödenen = avans 300 + net 700 = 1000 (mükerrer yok) ({t['yapilan_odeme']})")
        k = await db.kur_ucretleri.find_one({"id": "s1k1"})
        check(k.get("odendi_donem") == donem and abs(_num(k.get("ogretmen_odenen")) - 1000) < 0.01, f"kur mühürlendi + ogretmen_odenen=pay 1000 ({k.get('ogretmen_odenen')})")
        # mühürlü kurda avans düzeltilemez
        check((await ac.patch("/api/muhasebe/kur-ucreti/s1k1/odenen", headers=H("acc"), json={"ogretmen_odenen": 50})).status_code == 400, "hakedişe girmiş kurda avans düzeltilemez → 400")

        # ── 5) Avans azaltma DELTA'sı skalere doğru yansır (yeni kur) ──
        await db.kur_ucretleri.insert_one({"id": "s1k2", "ogrenci_id": "s1", "kur_adi": "2", "tutar": 1000, "egitim_turu": "Genel", "ogretmen_pay": 1000, "durum": "acik"})
        await ac.patch("/api/muhasebe/kur-ucreti/s1k2/odenen", headers=H("acc"), json={"ogretmen_odenen": 400})
        await ac.patch("/api/muhasebe/kur-ucreti/s1k2/odenen", headers=H("acc"), json={"ogretmen_odenen": 100})  # 400→100, delta -300
        t = await db.teachers.find_one({"id": "t1"})
        check(abs(t["yapilan_odeme"] - 1100) < 0.01, f"delta doğru: 1000 + (400) + (-300) = 1100 ({t['yapilan_odeme']})")

    await server.client.drop_database(TEST_DB)


def _num(x):
    try:
        return float(x or 0)
    except (TypeError, ValueError):
        return 0.0


if __name__ == "__main__":
    asyncio.run(run())
    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    sys.exit(1 if _kalan else 0)
