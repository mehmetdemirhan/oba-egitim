"""Tamamlanmış analiz raporu silme smoke testi (öğrenci profilinden).

Kapsar:
- admin / koordinatör / raporu oluşturan öğretmen SİLEBİLİR.
- Başka bir öğretmen (sahip değil) silemez (403).
- Silince rapor + bağlı oturum + oturuma bağlı diğer raporlar (gelişim) da temizlenir.

İzole test DB'sine karşı çalışır. Gerçek DB'ye dokunmaz.
    cd appbackend
    .venv/Scripts/python.exe tests/test_analiz_rapor_sil_smoke.py
"""
import asyncio
import os
import sys
import uuid

TEST_DB = "oba_test_analiz_rapor_sil"
os.environ["MONGO_URL"] = os.environ.get("MONGO_URL_TEST", "mongodb://localhost:27017")
os.environ["DB_NAME"] = TEST_DB
os.environ.setdefault("SECRET_KEY", "test-secret-key")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_gecen = 0
_kalan = 0


def check(kosul, mesaj):
    global _gecen, _kalan
    _gecen += 1 if kosul else 0
    _kalan += 0 if kosul else 1
    print(f"  [{'GECTI' if kosul else 'KALDI'}] {mesaj}")


async def run():
    import server
    from core.auth import create_access_token
    from httpx import AsyncClient, ASGITransport

    await server.client.drop_database(TEST_DB)
    ogr_tid = str(uuid.uuid4()); baska_tid = str(uuid.uuid4())
    coord = str(uuid.uuid4()); admin = str(uuid.uuid4()); sid = str(uuid.uuid4())
    await server.db.users.insert_many([
        {"id": ogr_tid, "role": "teacher", "ad": "Sahip", "soyad": "Öğr"},
        {"id": baska_tid, "role": "teacher", "ad": "Başka", "soyad": "Öğr"},
        {"id": coord, "role": "coordinator", "ad": "Koor", "soyad": "Din"},
        {"id": admin, "role": "admin", "ad": "Ad", "soyad": "Min"},
    ])
    H = lambda uid: {"Authorization": f"Bearer {create_access_token({'sub': uid})}"}
    T = "2026-01-01T00:00:00"

    async def yeni_rapor():
        oid = str(uuid.uuid4()); rid = str(uuid.uuid4()); gid = str(uuid.uuid4())
        await server.db.diagnostic_oturumlar.insert_one(
            {"id": oid, "ogrenci_id": sid, "ogretmen_id": ogr_tid, "durum": "tamamlandi", "olusturma_tarihi": T})
        await server.db.diagnostic_raporlar.insert_one(
            {"id": rid, "oturum_id": oid, "ogrenci_id": sid, "ogretmen_id": ogr_tid, "rapor_tipi": "olcum", "olusturma_tarihi": T})
        await server.db.diagnostic_raporlar.insert_one(
            {"id": gid, "oturum_id": oid, "ogrenci_id": sid, "ogretmen_id": ogr_tid, "rapor_tipi": "gelisim", "olusturma_tarihi": T})
        return oid, rid, gid

    transport = ASGITransport(app=server.app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1) Sahip olmayan öğretmen → 403
        oid, rid, gid = await yeni_rapor()
        r = await ac.delete(f"/api/diagnostic/rapor/{rid}", headers=H(baska_tid))
        check(r.status_code == 403, f"sahip olmayan öğretmen silemez ({r.status_code})")
        check(await server.db.diagnostic_raporlar.find_one({"id": rid}) is not None, "403 sonrası rapor duruyor")

        # 2) Sahip öğretmen → siler + cascade
        r = await ac.delete(f"/api/diagnostic/rapor/{rid}", headers=H(ogr_tid))
        check(r.status_code == 200, f"sahip öğretmen siler ({r.status_code})")
        check(await server.db.diagnostic_raporlar.find_one({"id": rid}) is None, "rapor silindi")
        check(await server.db.diagnostic_raporlar.find_one({"id": gid}) is None, "aynı oturumun gelişim raporu da silindi")
        check(await server.db.diagnostic_oturumlar.find_one({"id": oid}) is None, "bağlı oturum da silindi")

        # 3) Koordinatör siler
        oid, rid, gid = await yeni_rapor()
        r = await ac.delete(f"/api/diagnostic/rapor/{rid}", headers=H(coord))
        check(r.status_code == 200 and await server.db.diagnostic_raporlar.find_one({"id": rid}) is None, "koordinatör siler")

        # 4) Admin siler
        oid, rid, gid = await yeni_rapor()
        r = await ac.delete(f"/api/diagnostic/rapor/{rid}", headers=H(admin))
        check(r.status_code == 200 and await server.db.diagnostic_raporlar.find_one({"id": rid}) is None, "admin siler")

        # 5) Olmayan rapor → 404
        r = await ac.delete(f"/api/diagnostic/rapor/yok-boyle-id", headers=H(admin))
        check(r.status_code == 404, f"olmayan rapor 404 ({r.status_code})")

    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    await server.client.drop_database(TEST_DB)
    return _kalan == 0


if __name__ == "__main__":
    sys.exit(0 if asyncio.run(run()) else 1)
