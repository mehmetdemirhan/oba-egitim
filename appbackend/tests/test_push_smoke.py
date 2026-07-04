"""Web Push modülü smoke testi (/push/*) — abonelik + ders hatırlatma motoru.

Gerçek push GÖNDERMEZ (gonder=false); yalnız hedef ders çözümleme + idempotency.

    cd appbackend
    .venv/Scripts/python.exe tests/test_push_smoke.py
"""
import asyncio
import os
import sys
import uuid
from datetime import datetime, timedelta

TEST_DB = "oba_test_push_smoke"
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
    from core.db import ensure_indexes
    from core.config import PUSH_CRON_TOKEN, PUSH_TZ_OFFSET_SAAT, PUSH_HATIRLATMA_DK
    from httpx import AsyncClient, ASGITransport

    await server.client.drop_database(TEST_DB)
    await ensure_indexes()

    # Hedef ders zamanı: şimdi(TR) + hatırlatma dk → o saatte başlayan ders bugün
    simdi_tr = datetime.utcnow() + timedelta(hours=PUSH_TZ_OFFSET_SAAT)
    hedef = simdi_tr + timedelta(minutes=PUSH_HATIRLATMA_DK)
    hedef_saat = hedef.strftime("%H:%M")
    gun_date = hedef.date()

    ogr_id, veli_uid, ogretmen_id = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
    await server.db.students.insert_one({"id": ogr_id, "ad": "Ece", "soyad": "Kaya", "veli_id": veli_uid})
    await server.db.users.insert_one({"id": veli_uid, "role": "parent", "linked_id": ogr_id, "ad": "Veli"})
    # Bugün, hedef saatte başlayan aktif ders serisi
    await server.db.ders_serileri.insert_one({
        "id": str(uuid.uuid4()), "ogretmen_id": ogretmen_id, "ogrenci_id": ogr_id, "ogrenci_ad": "Ece Kaya",
        "gun": gun_date.weekday(), "baslangic_saati": hedef_saat, "bitis_saati": "23:59",
        "baslangic_tarihi": "2020-01-01", "bitis_tarihi": None, "durum": "aktif"})

    veli_auth = {"Authorization": f"Bearer {create_access_token({'sub': veli_uid})}"}
    tok = f"?anahtar={PUSH_CRON_TOKEN}" if PUSH_CRON_TOKEN else ""

    transport = ASGITransport(app=server.app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # public key
        r = await ac.get("/api/push/vapid-public")
        check(r.status_code == 200 and "public_key" in r.json(), "vapid-public döndü")

        # abonelik kaydet
        sub = {"endpoint": "https://push.example/abc", "keys": {"p256dh": "x", "auth": "y"}}
        r = await ac.post("/api/push/abone", json={"subscription": sub}, headers=veli_auth)
        check(r.status_code == 200, f"abone kaydı 200 (status={r.status_code})")
        n = await server.db.push_abonelikleri.count_documents({"user_id": veli_uid})
        check(n == 1, "abonelik DB'ye yazıldı")

        # token korumalı (yanlış anahtar → 403, token varsa)
        if PUSH_CRON_TOKEN:
            r = await ac.post("/api/push/kontrol?anahtar=YANLIS")
            check(r.status_code == 403, f"yanlış anahtar 403 (status={r.status_code})")

        # kontrol: hedef ders bulunmalı, veli çözülmeli (gönderme kapalı)
        r = await ac.post(f"/api/push/kontrol{tok}{'&' if tok else '?'}gonder=false")
        d = r.json()
        check(r.status_code == 200, f"kontrol 200 (status={r.status_code})")
        check(d["ders_sayisi"] >= 1, f"hedef saatte ders bulundu ({d['ders_sayisi']}) @ {hedef_saat}")
        check(d["veli_sayisi"] >= 1, f"veli çözüldü ({d['veli_sayisi']})")

        # idempotent: ikinci kontrol aynı dersi tekrar işlemez (veli_sayisi=0)
        r2 = await ac.post(f"/api/push/kontrol{tok}{'&' if tok else '?'}gonder=false")
        check(r2.json()["veli_sayisi"] == 0, "ikinci kontrol idempotent (tekrar bildirilmez)")

    await server.client.drop_database(TEST_DB)
    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    return _kalan == 0


if __name__ == "__main__":
    ok = asyncio.run(run())
    sys.exit(0 if ok else 1)
