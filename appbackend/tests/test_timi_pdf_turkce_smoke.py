"""TIMI PDF — Türkçe karakterli öğrenci adı 500 vermemeli (Content-Disposition latin-1 bug).

Bug: öğrenci adı doğrudan HTTP başlığına konunca (ör. 'Öğrenci Şşğ') latin-1 encode hatası → 500,
'PDF indirilemiyor'. Fix: _ascii_dosya ile ASCII güvenli ada çevir.

    cd appbackend
    PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe tests/test_timi_pdf_turkce_smoke.py
"""
import asyncio
import os
import sys

TEST_DB = "oba_test_timi_pdf"
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
    from modules.timi import KATEGORI_SIRASI

    db = server.db
    await server.client.drop_database(TEST_DB)
    await db.users.insert_one({"id": "t1", "role": "teacher", "ad": "Tuba", "soyad": "Yurduseven"})
    # Türkçe karakterli öğrenci adı — başlık latin-1 bug'ını tetikler
    await db.students.insert_one({"id": "o1", "ad": "Ömer Şükrü", "soyad": "Çağdaş Iğdır", "sinif": "5"})
    await db.timi_sonuclar.insert_one({
        "id": "s1", "ogrenci_id": "o1", "ogretmen_id": "t1", "durum": "tamamlandi",
        "sinif_seviyesi": "5", "uygulama_tarihi": "2026-07-19T10:00:00+00:00",
        "kategori_puanlari": {k: 5 for k in KATEGORI_SIRASI},
        "baskin_zeka_alanlari": KATEGORI_SIRASI[:2],
    })

    def H(u):
        return {"Authorization": f"Bearer {server.create_access_token({'sub': u})}"}

    async with AsyncClient(transport=ASGITransport(app=server.app), base_url="http://test") as ac:
        r = await ac.get("/api/timi/s1/pdf", headers=H("t1"))
        check(r.status_code == 200, f"Türkçe adlı öğrenci → PDF 200 (was 500). status={r.status_code}")
        check(r.headers.get("content-type") == "application/pdf", "content-type application/pdf")
        cd = r.headers.get("content-disposition", "")
        check(cd.encode("latin-1", "strict") and "TIMI_Raporu_" in cd, "Content-Disposition latin-1 güvenli (ASCII ad)")
        check(len(r.content) > 800, "PDF gövdesi üretildi (boş değil)")

    await server.client.drop_database(TEST_DB)


if __name__ == "__main__":
    asyncio.run(run())
    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    sys.exit(1 if _kalan else 0)
