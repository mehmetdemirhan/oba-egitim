"""Mesaj arşivleme smoke testi (madde 6).

Kapsar:
- Alıcı okunmuş mesajı arşivler (PUT /mesajlar/{id}/arsiv {arsiv:true}).
- Arşivlenen mesaj okunmamış sayısına dahil edilmez (zaten okundu) ve arsiv=True olur.
- Arşivden geri alma (arsiv:false) çalışır.
- Alıcı olmayan kullanıcı arşivleyemez (404). Mesaj SİLİNMEZ (kayıt durur).

İzole test DB'sine karşı çalışır. Gerçek DB'ye dokunmaz.
    cd appbackend
    .venv/Scripts/python.exe tests/test_mesaj_arsiv_smoke.py
"""
import asyncio
import os
import sys
import uuid

TEST_DB = "oba_test_mesaj_arsiv"
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

    alici = str(uuid.uuid4())
    gonderen = str(uuid.uuid4())
    baskasi = str(uuid.uuid4())
    for uid, rol in ((alici, "teacher"), (gonderen, "admin"), (baskasi, "teacher")):
        await server.db.users.insert_one({"id": uid, "role": rol, "ad": "K", "soyad": "U"})
    H_alici = {"Authorization": f"Bearer {create_access_token({'sub': alici})}"}
    H_baskasi = {"Authorization": f"Bearer {create_access_token({'sub': baskasi})}"}

    mid = str(uuid.uuid4())
    await server.db.mesajlar.insert_one({
        "id": mid, "gonderen_id": gonderen, "gonderen_ad": "Yönetim", "gonderen_rol": "admin",
        "alici_id": alici, "alici_ad": "K U", "alici_rol": "teacher",
        "konu": "Test", "icerik": "Merhaba", "okundu": True, "arsiv": False,
        "tarih": "2026-01-01T00:00:00"})

    transport = ASGITransport(app=server.app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # ── 1) Başkası arşivleyemez ──
        r = await ac.put(f"/api/mesajlar/{mid}/arsiv", json={"arsiv": True}, headers=H_baskasi)
        check(r.status_code == 404, f"alıcı olmayan arşivleyemez ({r.status_code})")

        # ── 2) Alıcı arşivler ──
        r = await ac.put(f"/api/mesajlar/{mid}/arsiv", json={"arsiv": True}, headers=H_alici)
        check(r.status_code == 200 and r.json().get("arsiv") is True, f"alıcı mesajı arşivledi ({r.status_code})")
        m = await server.db.mesajlar.find_one({"id": mid})
        check(m is not None and m.get("arsiv") is True, "mesaj arsiv=True (SİLİNMEDİ)")

        # ── 3) Geri alma ──
        r = await ac.put(f"/api/mesajlar/{mid}/arsiv", json={"arsiv": False}, headers=H_alici)
        check(r.status_code == 200 and r.json().get("arsiv") is False, "arşivden geri alındı")
        m = await server.db.mesajlar.find_one({"id": mid})
        check(m.get("arsiv") is False, "mesaj arsiv=False")

        # ── 4) Okunmamış sayısı arşivi hariç tutar ──
        mid2 = str(uuid.uuid4())
        await server.db.mesajlar.insert_one({
            "id": mid2, "gonderen_id": gonderen, "alici_id": alici, "icerik": "x",
            "okundu": False, "arsiv": True, "tarih": "2026-01-02T00:00:00"})
        r = await ac.get("/api/mesajlar/okunmamis-sayisi", headers=H_alici)
        # mid: okundu=True (sayılmaz), mid2: arsiv=True (hariç) → 0
        check(r.status_code == 200 and r.json().get("sayi") == 0, f"arşivli okunmamış sayıya girmiyor ({r.json()})")

    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    await server.client.drop_database(TEST_DB)
    return _kalan == 0


if __name__ == "__main__":
    ok = asyncio.run(run())
    sys.exit(0 if ok else 1)
