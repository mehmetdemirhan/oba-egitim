"""Bildirim (/bildirimler/*) smoke testi.

İzole test DB'sine karşı çalışır (oba_test_bildirim_smoke). Gerçek DB'ye dokunmaz.
    cd appbackend
    .venv/Scripts/python.exe tests/test_bildirim_smoke.py
"""
import asyncio
import os
import sys

TEST_DB = "oba_test_bildirim_smoke"
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

    await db.users.insert_one({
        "id": "bil-user-1", "role": "student", "ad": "Test", "soyad": "Öğrenci",
        "email": "bil@test.local",
    })
    token = server.create_access_token({"sub": "bil-user-1"})
    auth = {"Authorization": f"Bearer {token}"}

    # bildirim_olustur paylaşılan fonksiyonu (modules.bildirim'den) çalışmalı
    from modules.bildirim import bildirim_olustur
    await bildirim_olustur("bil-user-1", "mesaj_geldi", "Test bildirimi")
    await bildirim_olustur("bil-user-1", "risk_yuksek", "Risk bildirimi")

    transport = ASGITransport(app=server.app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1) Liste
        r = await ac.get("/api/bildirimler", headers=auth)
        check(r.status_code == 200 and len(r.json()) == 2, "2 bildirim listelendi")
        check(r.json()[0].get("baslik") in ("✉️ Yeni Mesaj", "🚨 Yüksek Risk"),
              "BILDIRIM_TURLERI başlığı doğru uygulandı")

        # 2) Okunmamış sayısı
        r = await ac.get("/api/bildirimler/okunmamis", headers=auth)
        check(r.status_code == 200 and r.json().get("sayi") == 2, "okunmamış sayısı 2")

        # 3) Birini oku
        bid = (await ac.get("/api/bildirimler", headers=auth)).json()[0]["id"]
        r = await ac.put(f"/api/bildirimler/{bid}/okundu", headers=auth)
        check(r.status_code == 200, "bildirim okundu işaretlendi")
        r = await ac.get("/api/bildirimler/okunmamis", headers=auth)
        check(r.json().get("sayi") == 1, "okunmamış sayısı 1'e düştü")

        # 4) Tümünü oku
        r = await ac.put("/api/bildirimler/tumunu-oku", headers=auth)
        check(r.status_code == 200, "tümünü oku 200")
        r = await ac.get("/api/bildirimler/okunmamis", headers=auth)
        check(r.json().get("sayi") == 0, "tümü okundu → 0")

        # 5) Sil
        r = await ac.delete(f"/api/bildirimler/{bid}", headers=auth)
        check(r.status_code == 200, "bildirim silindi")
        r = await ac.get("/api/bildirimler", headers=auth)
        check(len(r.json()) == 1, "silme sonrası 1 bildirim kaldı")

        # 6) /bildirimler/kontrol öğrenci için yetkisiz olmalı
        r = await ac.post("/api/bildirimler/kontrol", headers=auth)
        check(r.status_code == 403, f"öğrenci için /kontrol 403 (status={r.status_code})")

    await server.client.drop_database(TEST_DB)


def main():
    asyncio.run(run())
    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    sys.exit(0 if _kalan == 0 else 1)


if __name__ == "__main__":
    main()
