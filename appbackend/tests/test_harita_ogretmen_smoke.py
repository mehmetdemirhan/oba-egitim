"""TR Harita — Öğretmen Dağılımı agregasyonu smoke testi.

Doğrular: /api/istatistik/turkiye-harita öğretmenleri il bazında ANONİM sayar;
toplam_ogretmen + per-il ogretmen_sayisi + en_yogun_iller_ogretmen döner; arşivli ve
ili boş öğretmenler hariç; uçtan kimlik (id/ad) dönmez.

    cd appbackend
    PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe tests/test_harita_ogretmen_smoke.py
"""
import asyncio
import os
import sys

TEST_DB = "oba_test_harita_ogretmen"
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

    def ogt(oid, il, arsivli=False):
        return {"id": oid, "ad": "Öğ", "soyad": oid, "brans": "T", "seviye": "yeni",
                "il": il, "arsivli": arsivli}
    await db.teachers.insert_many([
        ogt("o1", "İstanbul"), ogt("o2", "İstanbul"), ogt("o3", "Ankara"),
        ogt("o4", "İzmir", arsivli=True),          # arşivli → hariç
        {"id": "o5", "ad": "Ö", "soyad": "5", "brans": "T", "seviye": "yeni"},  # ilsiz → hariç
    ])

    async with AsyncClient(transport=ASGITransport(app=server.app), base_url="http://test") as ac:
        r = await ac.get("/api/istatistik/turkiye-harita")
        check(r.status_code == 200, "turkiye-harita 200")
        j = r.json()
        check(j.get("toplam_ogretmen") == 3, f"toplam_ogretmen=3 (arşivli+ilsiz hariç) ({j.get('toplam_ogretmen')})")
        ist = next((i for i in j["iller"] if i["il"] == "İstanbul"), None)
        check(ist and ist.get("ogretmen_sayisi") == 2, f"İstanbul ogretmen_sayisi=2 ({ist and ist.get('ogretmen_sayisi')})")
        izm = next((i for i in j["iller"] if i["il"] == "İzmir"), None)
        check(izm is None or izm.get("ogretmen_sayisi", 0) == 0, "arşivli öğretmen dağılımda yok (İzmir=0)")
        eyo = j.get("en_yogun_iller_ogretmen", [])
        check(len(eyo) >= 1 and eyo[0]["il"] == "İstanbul" and eyo[0]["ogretmen_sayisi"] == 2,
              f"en yoğun il = İstanbul(2) ({eyo[:1]})")
        # Anonimlik: iller kayıtlarında kimlik alanı olmamalı
        kimlik_sizdi = any(("id" in i) or ("ad" in i) or ("soyad" in i) for i in j["iller"])
        check(not kimlik_sizdi, "uçtan kimlik (id/ad/soyad) dönmüyor — yalnız agregat")

    await server.client.drop_database(TEST_DB)


if __name__ == "__main__":
    asyncio.run(run())
    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    sys.exit(1 if _kalan else 0)
