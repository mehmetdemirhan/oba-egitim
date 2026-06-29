"""Tanılama (diagnostic) modülü smoke testi.

Norm tablosu, metin havuzu (oy), analiz oturumu, rapor oluşturma ve PDF
çıktısı akışını uçtan uca doğrular. İzole test DB'sine karşı çalışır.
    cd appbackend
    .venv/Scripts/python.exe tests/test_diagnostic_smoke.py
"""
import asyncio
import os
import sys
import uuid

TEST_DB = "oba_test_diagnostic_smoke"
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
    from core.auth import create_access_token
    from httpx import AsyncClient, ASGITransport

    await server.client.drop_database(TEST_DB)

    admin_id = str(uuid.uuid4())
    await server.db.users.insert_one({"id": admin_id, "ad": "Admin", "soyad": "T", "role": "admin", "puan": 0})
    H = {"Authorization": f"Bearer {create_access_token({'sub': admin_id})}"}

    transport = ASGITransport(app=server.app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Norm tablosu
        r = await ac.get("/api/diagnostic/normlar", headers=H)
        check(r.status_code == 200, f"norm tablosu okundu (status={r.status_code})")

        # /ayarlar/puanlar (server.py'de kaldı, ama get_puan_ayarlari core'dan)
        r = await ac.get("/api/ayarlar/puanlar", headers=H)
        check(r.status_code == 200 and "metin_ekleme" in r.json(), "puan ayarları core'dan döndü")

        # Metin oluştur (admin → doğrudan havuza/onaylı)
        r = await ac.post("/api/diagnostic/texts", json={
            "baslik": "Test Metni", "icerik": "Bir varmış bir yokmuş, uzun zaman önce.",
            "sinif_seviyesi": "4", "tur": "hikaye",
        }, headers=H)
        check(r.status_code == 200, f"metin oluşturuldu (status={r.status_code})")
        metin = r.json()
        metin_id = metin["id"]

        r = await ac.get("/api/diagnostic/texts", headers=H)
        check(r.status_code == 200 and any(m["id"] == metin_id for m in r.json()), "metin listede")

        # Oturum başlat
        ogr_id = str(uuid.uuid4())
        await server.db.students.insert_one({"id": ogr_id, "ad": "Ali", "soyad": "Veli", "sinif": "4", "toplam_xp": 0})
        r = await ac.post("/api/diagnostic/sessions", json={
            "ogrenci_id": ogr_id, "metin_id": metin_id,
        }, headers=H)
        check(r.status_code == 200, f"oturum başlatıldı (status={r.status_code})")
        oturum_id = r.json()["id"]

        r = await ac.get("/api/diagnostic/sessions", headers=H)
        check(r.status_code == 200 and len(r.json()) >= 1, "oturumlar listelendi")

        # Oturum tamamla
        r = await ac.post(f"/api/diagnostic/sessions/{oturum_id}/complete", json={
            "sure_saniye": 60, "kelime_sayisi": 100, "hatalar": [],
        }, headers=H)
        check(r.status_code == 200, f"oturum tamamlandı (status={r.status_code})")

        # Rapor oluştur (RaporOlusturCreate: oturum_id + anlama + prozodik)
        r = await ac.post("/api/diagnostic/rapor", json={
            "oturum_id": oturum_id,
            "anlama": {"genel_yuzde": 80},
            "prozodik": {"noktalama": 3, "vurgu": 3, "tonlama": 3, "akicilik": 3, "anlamli_gruplama": 3},
            "ogretmen_notu": "İyi gidiyor.",
        }, headers=H)
        check(r.status_code == 200, f"rapor oluşturuldu (status={r.status_code})")
        rapor_id = r.json()["id"]

        r = await ac.get(f"/api/diagnostic/rapor/{rapor_id}", headers=H)
        check(r.status_code == 200 and r.json()["id"] == rapor_id, "rapor getirildi")

        r = await ac.get(f"/api/diagnostic/rapor/ogrenci/{ogr_id}", headers=H)
        check(r.status_code == 200 and len(r.json()) >= 1, "öğrenci raporları listelendi")

        # PDF üretimi (reportlab) — 200 + PDF içerik tipi
        r = await ac.get(f"/api/diagnostic/rapor/{rapor_id}/pdf", headers=H)
        check(r.status_code == 200, f"PDF üretildi (status={r.status_code})")
        check(r.content[:4] == b"%PDF", "çıktı geçerli PDF (magic %PDF)")

        # Metin sil
        r = await ac.delete(f"/api/diagnostic/texts/{metin_id}", headers=H)
        check(r.status_code == 200, "metin silindi")

    await server.client.drop_database(TEST_DB)


def main():
    asyncio.run(run())
    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    sys.exit(0 if _kalan == 0 else 1)


if __name__ == "__main__":
    main()
