"""Giriş logu + Loglar (/loglar/*, /auth/*) smoke testi.

İzole test DB'sine karşı çalışır (oba_test_giris_log_smoke). Gerçek DB'ye dokunmaz.
    cd appbackend
    .venv/Scripts/python.exe tests/test_giris_log_smoke.py
"""
import asyncio
import os
import sys

TEST_DB = "oba_test_giris_log_smoke"
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

    db = server.db
    await server.client.drop_database(TEST_DB)

    SIFRE = "GizliParola123"
    await db.users.insert_one({
        "id": "gl-admin", "role": "admin", "ad": "Log", "soyad": "Yönetici",
        "email": "gl-admin@test.local", "password_hash": hash_password(SIFRE),
    })
    await db.users.insert_one({
        "id": "gl-teacher", "role": "teacher", "ad": "Öğr", "soyad": "Menen",
        "email": "gl-teacher@test.local", "password_hash": hash_password(SIFRE),
    })
    await db.users.insert_one({
        "id": "gl-acc", "role": "accountant", "ad": "Mu", "soyad": "Hasebe",
        "email": "gl-acc@test.local", "password_hash": hash_password(SIFRE),
    })

    transport = ASGITransport(app=server.app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # TTL index'i uygula (startup event ASGITransport ile tetiklenmeyebilir)
        try:
            from core.db import ensure_indexes
            await ensure_indexes()
        except Exception:
            pass

        # 1) Başarılı giriş → giris_log'a düşer
        r = await ac.post("/api/auth/login", json={"email_or_phone": "gl-admin@test.local", "password": SIFRE})
        check(r.status_code == 200, f"admin girişi 200 (status={r.status_code})")
        token = r.json().get("access_token")
        auth = {"Authorization": f"Bearer {token}"}
        n = await db.giris_log.count_documents({"tip": "login_basarili", "user_id": "gl-admin"})
        check(n == 1, f"başarılı giriş loglandı ({n})")

        # 2) Başarısız giriş → denenen e-posta + IP loglanır, ŞİFRE loglanmaz
        r = await ac.post("/api/auth/login", json={"email_or_phone": "gl-admin@test.local", "password": "yanlis"})
        check(r.status_code == 401, "yanlış şifre 401")
        fail = await db.giris_log.find_one({"tip": "login_basarisiz"})
        check(fail is not None and fail.get("denenen_email") == "gl-admin@test.local",
              "başarısız girişte denenen e-posta loglandı")

        # 3) GÜVENLİK: hiçbir giris_log kaydında şifre/token sızmıyor
        sizinti = False
        async for d in db.giris_log.find({}):
            blob = str(d).lower()
            if SIFRE.lower() in blob or "password" in blob or (token and token.lower() in blob):
                sizinti = True
                break
        check(not sizinti, "şifre/token giris_log'a sızmıyor")

        # 4) Yetki: teacher & accountant → /loglar/ozet 403
        for uid, rol in (("gl-teacher", "teacher"), ("gl-acc", "accountant")):
            lr = await ac.post("/api/auth/login", json={"email_or_phone": f"{uid}@test.local", "password": SIFRE})
            t2 = lr.json().get("access_token")
            rr = await ac.get("/api/loglar/ozet", headers={"Authorization": f"Bearer {t2}"})
            check(rr.status_code == 403, f"{rol} → /loglar/ozet 403 (status={rr.status_code})")

        # 5) Admin → /loglar/ozet 200 ve beklenen anahtarlar
        r = await ac.get("/api/loglar/ozet", headers=auth)
        check(r.status_code == 200, "admin → /loglar/ozet 200")
        j = r.json()
        check(all(k in j for k in ("gunluk_aktif", "isi_haritasi", "bugun_rol",
                                   "basarisiz_gunluk", "islem_hacmi", "uyarilar")),
              "ozet tüm grafik anahtarlarını içeriyor")

        # 6) Tablo: filtre + sayfalama
        r = await ac.get("/api/loglar/giris", headers=auth, params={"tip": "login_basarili", "limit": 10})
        check(r.status_code == 200 and r.json().get("toplam", 0) >= 1, "giriş tablosu filtreli döndü")
        r2 = await ac.get("/api/loglar/giris", headers=auth, params={"tip": "login_basarisiz"})
        check(all(k["tip"] == "login_basarisiz" for k in r2.json().get("kayitlar", [])),
              "tip filtresi yalnız başarısızları döndürdü")

        # 7) TTL index mevcut ve saklama ayarı çalışıyor
        idx = await db.giris_log.index_information()
        check(any("expireAfterSeconds" in v for v in idx.values()), "giris_log TTL index'i mevcut")
        r = await ac.put("/api/loglar/saklama", headers=auth, json={"gun": 30})
        check(r.status_code == 200 and r.json().get("gun") == 30, "saklama süresi 30 güne ayarlandı")
        r = await ac.get("/api/loglar/saklama", headers=auth)
        check(r.json().get("gun") == 30, "saklama süresi okundu = 30")

        # 8) Logout loglanıyor
        r = await ac.post("/api/auth/logout", json={"refresh_token": ""})
        check(r.status_code == 200, "logout 200")
        n = await db.giris_log.count_documents({"tip": "logout"})
        check(n >= 1, f"logout loglandı ({n})")

    await server.client.drop_database(TEST_DB)


def main():
    asyncio.run(run())
    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    sys.exit(0 if _kalan == 0 else 1)


if __name__ == "__main__":
    main()
