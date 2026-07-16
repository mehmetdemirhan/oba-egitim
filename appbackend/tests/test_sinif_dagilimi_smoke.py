"""Dashboard — Öğrenci Sınıf Dağılımı smoke testi.

Doğrular: /api/dashboard/sinif-dagilimi aktif öğrencileri (arşivli + mezun HARİÇ)
sınıf seviyesine göre sayar; 1-8 kovaları + parse edilemeyen/boş için '?' kovası;
yüzdeler tutarlı; toplam DB ile uyumlu; öğretmen 403.

    cd appbackend
    PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe tests/test_sinif_dagilimi_smoke.py
"""
import asyncio
import os
import sys

TEST_DB = "oba_test_sinif_dagilimi"
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

    await db.users.insert_one({"id": "adm", "role": "admin", "ad": "A", "soyad": "M"})
    await db.users.insert_one({"id": "t1", "role": "teacher", "ad": "T", "soyad": "1"})

    def ogr(oid, sinif, arsivli=False, mezun=False):
        return {"id": oid, "ad": "Ö", "soyad": oid, "sinif": sinif, "arsivli": arsivli, "mezun": mezun}
    # Aktif: 3,3,5,"","abc" → 3:2, 5:1, ?:2 (toplam 5). Arşivli 3 + mezun 5 HARİÇ.
    await db.students.insert_many([
        ogr("s1", "3"), ogr("s2", "3"), ogr("s3", "5"), ogr("s4", ""), ogr("s5", "abc"),
        ogr("s6", "3", arsivli=True), ogr("s7", "5", mezun=True),
    ])

    def H(uid):
        return {"Authorization": f"Bearer {server.create_access_token({'sub': uid})}"}

    async with AsyncClient(transport=ASGITransport(app=server.app), base_url="http://test") as ac:
        r = await ac.get("/api/dashboard/sinif-dagilimi", headers=H("adm"))
        check(r.status_code == 200, f"sinif-dagilimi 200 ({r.status_code})")
        j = r.json()
        check(j.get("toplam") == 5, f"toplam=5 (arşivli+mezun hariç) ({j.get('toplam')})")
        kova = {d["sinif"]: d for d in j.get("dagilim", [])}
        check(kova.get("3", {}).get("sayi") == 2, f"3. sınıf=2 ({kova.get('3', {}).get('sayi')})")
        check(kova.get("5", {}).get("sayi") == 1, f"5. sınıf=1 ({kova.get('5', {}).get('sayi')})")
        check(kova.get("?", {}).get("sayi") == 2, f"'?' (boş+geçersiz)=2 ({kova.get('?', {}).get('sayi')})")
        check(kova.get("1", {}).get("sayi") == 0, "1. sınıf=0 (öğrenci yok)")
        check(abs(kova.get("3", {}).get("yuzde", 0) - 40.0) < 0.01, f"3. sınıf yüzde=40 ({kova.get('3', {}).get('yuzde')})")
        # 1-8 + '?' = 9 kova hepsi mevcut
        check(len(j.get("dagilim", [])) == 9, f"9 kova (1-8 + ?) ({len(j.get('dagilim', []))})")

        # Öğretmen erişemez → 403
        r = await ac.get("/api/dashboard/sinif-dagilimi", headers=H("t1"))
        check(r.status_code == 403, f"öğretmen 403 ({r.status_code})")

    await server.client.drop_database(TEST_DB)


if __name__ == "__main__":
    asyncio.run(run())
    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    sys.exit(1 if _kalan else 0)
