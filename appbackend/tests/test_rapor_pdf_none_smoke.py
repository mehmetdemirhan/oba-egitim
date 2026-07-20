"""Analiz raporu PDF — None/eksik alanlı raporlarda ÇÖKMEDEN üretim (regresyon).

Kök neden: rapor.get(key, 0) alanda None SAKLIYSA None döner (default yalnız eksik
anahtarda geçerli) → round(None)/int(None)/None.get()/None.split() ile 500 çöküyordu.
Bazı kullanıcıların (eksik alanlı) raporları bu yüzden PDF indirilemiyordu.

İzole test DB'sine karşı çalışır. Gerçek DB'ye dokunmaz.
    cd appbackend
    .venv/Scripts/python.exe tests/test_rapor_pdf_none_smoke.py
"""
import asyncio
import os
import sys
import uuid

TEST_DB = "oba_test_rapor_pdf_none"
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
    tid = str(uuid.uuid4()); sid = str(uuid.uuid4())
    await server.db.users.insert_one({"id": tid, "role": "teacher", "ad": "Tuğba", "soyad": "Yurduseven"})
    await server.db.students.insert_one({"id": sid, "ad": "Öğr", "soyad": "Enci", "sinif": "4"})
    H = {"Authorization": f"Bearer {create_access_token({'sub': tid})}"}
    T = "2026-01-01T00:00:00"

    senaryolar = {
        "ölçüm: tüm sayısal alanlar None": {
            "ogrenci_id": sid, "ogretmen_id": tid, "rapor_tipi": "olcum",
            "wpm": None, "anlama_yuzde": None, "prozodik_toplam": None, "dogruluk_yuzde": None,
            "kelime_sayisi": None, "sure_saniye": None, "anlama": None, "prozodik": None,
            "hata_sayilari": None, "metin_baslik": None, "metin_adi": None, "olusturma_tarihi": T},
        "ölçüm: sadece kimlikler": {
            "ogrenci_id": sid, "ogretmen_id": tid, "rapor_tipi": "olcum", "olusturma_tarihi": T},
        "gelişim: metin adları + özet None": {
            "ogrenci_id": sid, "ogretmen_id": tid, "rapor_tipi": "gelisim",
            "ilk_metin_adi": None, "son_metin_adi": None, "ozet_tablo": None,
            "hata_analizi": None, "ogretmen_notu": None, "olusturma_tarihi": T},
    }

    transport = ASGITransport(app=server.app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        for ad, doc in senaryolar.items():
            rid = str(uuid.uuid4()); doc = dict(doc); doc["id"] = rid
            await server.db.diagnostic_raporlar.insert_one(doc)
            r = await ac.get(f"/api/diagnostic/rapor/{rid}/pdf", headers=H)
            ok = r.status_code == 200 and r.content[:4] == b"%PDF"
            check(ok, f"{ad} → geçerli PDF ({r.status_code})")

    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    await server.client.drop_database(TEST_DB)
    return _kalan == 0


if __name__ == "__main__":
    sys.exit(0 if asyncio.run(run()) else 1)
