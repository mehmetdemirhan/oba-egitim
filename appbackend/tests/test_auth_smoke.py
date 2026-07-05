"""Auth (/auth/*) smoke testi — login/me/change-password/users davranışı.

İzole test DB'sine karşı çalışır (oba_test_auth_smoke). Gerçek DB'ye dokunmaz.
    cd appbackend
    .venv/Scripts/python.exe tests/test_auth_smoke.py
"""
import asyncio
import os
import sys

TEST_DB = "oba_test_auth_smoke"
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
    from datetime import datetime, timezone

    db = server.db
    await server.client.drop_database(TEST_DB)

    # Admin kullanıcı (parola hash'i ile)
    await db.users.insert_one({
        "id": "auth-admin-1", "role": "admin", "ad": "Yetkili", "soyad": "Admin",
        "email": "admin@test.local", "telefon": "5550001122",
        "password_hash": server.hash_password("gizli123"),
        "olusturma_tarihi": datetime.now(timezone.utc).isoformat(),
    })

    transport = ASGITransport(app=server.app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1) Yanlış şifre → 401
        r = await ac.post("/api/auth/login", json={"email_or_phone": "admin@test.local", "password": "yanlis"})
        check(r.status_code == 401, f"yanlış şifre 401 (status={r.status_code})")

        # 2) Doğru şifre → token
        r = await ac.post("/api/auth/login", json={"email_or_phone": "admin@test.local", "password": "gizli123"})
        check(r.status_code == 200, f"doğru şifre 200 (status={r.status_code})")
        token = r.json().get("access_token")
        check(bool(token), "login token döndürdü")
        check(r.json().get("user", {}).get("role") == "admin", "login user.role=admin")
        auth = {"Authorization": f"Bearer {token}"}

        # 3) Telefon ile login
        r = await ac.post("/api/auth/login", json={"email_or_phone": "5550001122", "password": "gizli123"})
        check(r.status_code == 200, f"telefon ile login 200 (status={r.status_code})")

        # 4) /auth/me
        r = await ac.get("/api/auth/me", headers=auth)
        check(r.status_code == 200 and r.json().get("id") == "auth-admin-1", "/auth/me doğru kullanıcı")

        # 5) Admin öğretmen oluşturur — şifre VERMEDEN (otomatik güçlü geçici şifre)
        r = await ac.post("/api/auth/users", headers=auth, json={
            "ad": "Yeni", "soyad": "Öğretmen", "email": "ogr@test.local", "role": "teacher",
        })
        j = r.json()
        check(r.status_code == 200 and j.get("role") == "teacher", "admin yeni öğretmen oluşturdu")
        check(bool(j.get("gecici_sifre")) and j.get("gecici_sifre_uretildi") is True,
              "otomatik geçici şifre üretildi ve döndü")
        check(j.get("sifre_degistirme_zorunlu") is True, "yeni kullanıcı şifre değiştirme zorunlu")
        check(bool(j.get("teacher_id")), "öğretmen için teachers kaydı otomatik oluştu")
        ogr_gecici = j["gecici_sifre"]
        trec = await db.teachers.find_one({"id": j["teacher_id"]})
        check(trec is not None and trec.get("user_id") == j["id"], "teacher.user_id = user.id (köprü)")

        # 5b) İlk giriş: geçici şifre → must_change_password=true; değiştirince düşer
        r = await ac.post("/api/auth/login", json={"email_or_phone": "ogr@test.local", "password": ogr_gecici})
        check(r.status_code == 200 and r.json().get("must_change_password") is True,
              "geçici şifre login must_change=true")
        ogr_auth = {"Authorization": f"Bearer {r.json()['access_token']}"}
        r = await ac.post("/api/auth/change-password", headers=ogr_auth,
                          json={"old_password": ogr_gecici, "new_password": "kalici789"})
        check(r.status_code == 200, "öğretmen ilk-giriş şifresini değiştirdi")
        r = await ac.post("/api/auth/login", json={"email_or_phone": "ogr@test.local", "password": "kalici789"})
        check(r.status_code == 200 and r.json().get("must_change_password") is False,
              "değiştirdikten sonra must_change=false")

        # 5c) Koordinatör de teachers'a eklenir (req: koord/yönetici de ders anlatır)
        r = await ac.post("/api/auth/users", headers=auth, json={
            "ad": "Koord", "soyad": "İnan", "email": "koord@test.local", "role": "coordinator",
        })
        check(r.status_code == 200 and r.json().get("teacher_id"), "koordinatör için de teachers kaydı oluştu")

        # 6) Aynı email tekrar → 400
        r = await ac.post("/api/auth/users", headers=auth, json={
            "ad": "X", "soyad": "Y", "email": "ogr@test.local", "password": "p", "role": "teacher",
        })
        check(r.status_code == 400, f"duplike email 400 (status={r.status_code})")

        # 7) Liste (admin + öğretmen + koordinatör = 3)
        r = await ac.get("/api/auth/users", headers=auth)
        check(r.status_code == 200 and len(r.json()) == 3, f"kullanıcı listesi 3 kayıt ({len(r.json())})")

        # 8) change-password sonra yeni şifre ile login
        r = await ac.post("/api/auth/change-password", headers=auth,
                          json={"old_password": "gizli123", "new_password": "yeni456"})
        check(r.status_code == 200, f"change-password 200 (status={r.status_code})")
        r = await ac.post("/api/auth/login", json={"email_or_phone": "admin@test.local", "password": "yeni456"})
        check(r.status_code == 200, "yeni şifre ile login çalışıyor")

        # 9) Token'sız korumalı uç → 403
        r = await ac.get("/api/auth/users")
        check(r.status_code in (401, 403), f"token'sız /auth/users reddedildi (status={r.status_code})")

        # 10) Koordinatör yetki sınırları (daraltılmış)
        r = await ac.post("/api/auth/users", headers=auth, json={
            "ad": "K", "soyad": "Rd", "email": "krd@test.local", "role": "coordinator"})
        koord_sifre = r.json()["gecici_sifre"]
        r = await ac.post("/api/auth/login", json={"email_or_phone": "krd@test.local", "password": koord_sifre})
        koord_auth = {"Authorization": f"Bearer {r.json()['access_token']}"}
        # a) koordinatör öğretmen/kullanıcı oluşturabilir
        r = await ac.post("/api/auth/users", headers=koord_auth, json={
            "ad": "Yeni", "soyad": "Öğr2", "email": "ogr2@test.local", "role": "teacher"})
        check(r.status_code == 200, f"koordinatör kullanıcı oluşturabildi (status={r.status_code})")
        # b) koordinatör ADMIN hesabı oluşturamaz → 403
        r = await ac.post("/api/auth/users", headers=koord_auth, json={
            "ad": "Sahte", "soyad": "Admin", "email": "sahteadmin@test.local", "role": "admin"})
        check(r.status_code == 403, f"koordinatör admin oluşturamaz 403 (status={r.status_code})")
        # c) koordinatör kullanıcı SİLEMEZ → 403
        r = await ac.delete("/api/auth/users/auth-admin-1", headers=koord_auth)
        check(r.status_code == 403, f"koordinatör kullanıcı silemez 403 (status={r.status_code})")
        # d) admin silebilir (yeni öğretmeni silelim)
        ogr2 = await db.users.find_one({"email": "ogr2@test.local"})
        r = await ac.delete(f"/api/auth/users/{ogr2['id']}", headers=auth)
        check(r.status_code == 200, f"admin kullanıcı silebilir (status={r.status_code})")

        # 11) Admin kullanıcı DÜZENLEME (PUT /auth/users/{id})
        r = await ac.post("/api/auth/users", headers=auth, json={
            "ad": "Duz", "soyad": "En", "email": "duzen@test.local", "role": "parent"})
        uid = r.json()["id"]
        r = await ac.put(f"/api/auth/users/{uid}", headers=auth, json={
            "ad": "Yeni Ad", "role": "teacher", "password": "resetsifre1"})
        check(r.status_code == 200, f"admin kullanıcı düzenledi (status={r.status_code})")
        u = await db.users.find_one({"id": uid})
        check(u["ad"] == "Yeni Ad" and u["role"] == "teacher", "ad + rol güncellendi")
        check(u.get("sifre_degistirme_zorunlu") is True, "admin şifre değişince zorunlu bayrağı set")
        check(bool(u.get("linked_id")), "rol teacher'a dönünce teachers köprüsü kuruldu")
        r = await ac.post("/api/auth/login", json={"email_or_phone": "duzen@test.local", "password": "resetsifre1"})
        check(r.status_code == 200, "admin'in belirlediği yeni şifre ile login")
        # koordinatör düzenleyemez → 403
        r = await ac.put(f"/api/auth/users/{uid}", headers=koord_auth, json={"ad": "X"})
        check(r.status_code == 403, f"koordinatör kullanıcı düzenleyemez 403 (status={r.status_code})")

        # 12) Kalıcı oturum: login refresh döner, /auth/refresh yeni access verir, logout iptal eder
        r = await ac.post("/api/auth/login", json={"email_or_phone": "admin@test.local", "password": "yeni456"})
        refresh = r.json().get("refresh_token")
        check(bool(refresh), "login refresh_token döndürdü")
        r = await ac.post("/api/auth/refresh", json={"refresh_token": refresh})
        check(r.status_code == 200 and bool(r.json().get("access_token")), "refresh yeni access verdi")
        # yeni access ile /auth/me çalışır
        r2 = await ac.get("/api/auth/me", headers={"Authorization": f"Bearer {r.json()['access_token']}"})
        check(r2.status_code == 200, "yenilenmiş access geçerli")
        # logout → refresh iptal → tekrar refresh 401
        await ac.post("/api/auth/logout", json={"refresh_token": refresh})
        r = await ac.post("/api/auth/refresh", json={"refresh_token": refresh})
        check(r.status_code == 401, f"logout sonrası refresh 401 (status={r.status_code})")
        r = await ac.post("/api/auth/refresh", json={"refresh_token": "gecersiz"})
        check(r.status_code == 401, "geçersiz refresh 401")

    await server.client.drop_database(TEST_DB)


def main():
    asyncio.run(run())
    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    sys.exit(0 if _kalan == 0 else 1)


if __name__ == "__main__":
    main()
