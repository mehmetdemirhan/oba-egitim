"""İŞ 2 — Bakım modu smoke testi.

Bakımda admin-dışı login → bakım yanıtı (503); admin girişi çalışır; açık oturum
503+bakım; webhook muaf; public durum ucu; mesaj güncelleme; kapatınca normal akış;
aç/kapa audit.
    cd appbackend
    .venv/Scripts/python.exe tests/test_bakim_smoke.py
"""
import asyncio
import os
import sys

TEST_DB = "oba_test_bakim_smoke"
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
    from core.auth import hash_password
    from core.bakim import bakim_cache_temizle

    db = server.db
    await server.client.drop_database(TEST_DB)

    SIFRE = "Parola12345"
    await db.users.insert_one({"id": "adm", "role": "admin", "ad": "Ad", "soyad": "Min",
                               "email": "adm@test.local", "password_hash": hash_password(SIFRE)})
    await db.users.insert_one({"id": "ogr", "role": "teacher", "ad": "Öğ", "soyad": "R",
                               "email": "ogr@test.local", "password_hash": hash_password(SIFRE)})

    def H(uid):
        return {"Authorization": f"Bearer {server.create_access_token({'sub': uid, 'role': 'admin' if uid == 'adm' else 'teacher'})}"}

    async with AsyncClient(transport=ASGITransport(app=server.app), base_url="http://test") as ac:
        # Oturumu açık öğretmen token'ı (bakımdan önce alınmış say)
        ogr_login = await ac.post("/api/auth/login", json={"email_or_phone": "ogr@test.local", "password": SIFRE})
        ogr_tok = {"Authorization": f"Bearer {ogr_login.json().get('access_token')}"}
        check(ogr_login.status_code == 200, "bakım öncesi öğretmen girişi çalışıyor")

        # 1) Public durum ucu (auth yok) — kapalıyken bakim=false
        r = await ac.get("/api/sistem/durum")
        check(r.status_code == 200 and r.json().get("bakim") is False, "public /sistem/durum kapalı=false")

        # 2) Öğretmen bakım aç/kapatamaz (403)
        r = await ac.put("/api/sistem/bakim", headers=H("ogr"), json={"aktif": True})
        check(r.status_code == 403, f"öğretmen bakım ayarlayamaz → 403 ({r.status_code})")

        # 3) Admin bakımı açar + mesaj
        r = await ac.put("/api/sistem/bakim", headers=H("adm"),
                         json={"aktif": True, "mesaj": "Yakında döneceğiz", "tahmini_bitis": "18:00"})
        check(r.status_code == 200 and r.json().get("aktif") is True, "admin bakımı açtı")
        bakim_cache_temizle()  # test içinde cache'i anında tazele

        # 4) Aç/kapa audit'e düştü
        log = await db.islem_log.find_one({"islem": "bakim_ac"})
        check(log is not None, "bakım açma audit'e düştü")

        # 5) Public durum artık bakim=true + mesaj
        r = await ac.get("/api/sistem/durum")
        check(r.status_code == 200 and r.json().get("bakim") is True and r.json().get("mesaj") == "Yakında döneceğiz",
              "public durum bakım + mesaj gösteriyor")

        # 6) Açık oturum öğretmen → korumalı uçta 503 + bakım yanıtı
        r = await ac.get("/api/gorevler", headers=ogr_tok)
        check(r.status_code == 503 and r.json().get("bakim") is True, f"öğretmen açık oturum → 503 bakım ({r.status_code})")

        # 7) Admin token → muaf (normal çalışır)
        r = await ac.get("/api/students", headers=H("adm"))
        check(r.status_code == 200, f"admin bakımda muaf, çalışıyor ({r.status_code})")

        # 8) Bakımda öğretmen LOGIN → bakım yanıtı (giriş yapamaz)
        r = await ac.post("/api/auth/login", json={"email_or_phone": "ogr@test.local", "password": SIFRE})
        check(r.status_code == 503 and r.json().get("bakim") is True, f"öğretmen login → 503 bakım ({r.status_code})")

        # 9) Bakımda ADMIN LOGIN → çalışır (kilitlenme yok)
        r = await ac.post("/api/auth/login", json={"email_or_phone": "adm@test.local", "password": SIFRE})
        check(r.status_code == 200 and r.json().get("access_token"), "admin bakımda login yapabiliyor")

        # 10) Webhook muaf (bakımda da erişilebilir — 503 DEĞİL)
        r = await ac.get("/api/funnel/whatsapp/webhook", params={"hub.mode": "subscribe",
                         "hub.verify_token": "x", "hub.challenge": "123"})
        check(r.status_code != 503, f"webhook bakımdan muaf (503 değil, status={r.status_code})")

        # 11) Kapatınca normal akış döner
        r = await ac.put("/api/sistem/bakim", headers=H("adm"), json={"aktif": False})
        check(r.status_code == 200 and r.json().get("aktif") is False, "admin bakımı kapattı")
        bakim_cache_temizle()
        r = await ac.get("/api/gorevler", headers=ogr_tok)
        check(r.status_code == 200, f"kapanınca öğretmen normal erişim ({r.status_code})")

    await server.client.drop_database(TEST_DB)


def main():
    asyncio.run(run())
    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    sys.exit(0 if _kalan == 0 else 1)


if __name__ == "__main__":
    main()
