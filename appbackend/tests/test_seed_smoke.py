"""Başlangıç seed (create_default_admin) smoke testi.

modules/seed.py'ye taşınan startup hook'unun hatasız çalıştığını ve varsayılan
admin + sistem verisini oluşturduğunu doğrular. İzole test DB'sine çalışır.
    cd appbackend
    .venv/Scripts/python.exe tests/test_seed_smoke.py
"""
import asyncio
import os
import sys

TEST_DB = "oba_test_seed_smoke"
os.environ["MONGO_URL"] = os.environ.get("MONGO_URL_TEST", "mongodb://localhost:27017")
os.environ["DB_NAME"] = TEST_DB
os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ["ADMIN_EMAIL"] = "admin@test.local"
os.environ["ADMIN_PASSWORD"] = "test1234"
os.environ["ADMIN_AD"] = "Test"
os.environ["ADMIN_SOYAD"] = "Admin"
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
    from modules.seed import create_default_admin

    await server.client.drop_database(TEST_DB)

    # Startup seed'i iki kez çağır (idempotent olmalı, ikinci çağrı patlamamalı)
    await create_default_admin()
    await create_default_admin()

    admin = await server.db.users.find_one({"email": "admin@test.local"})
    check(admin is not None, "varsayılan admin oluşturuldu")
    check(admin and admin.get("role") == "admin", "admin rolü doğru")

    # Aynı e-posta ile tek admin (idempotent)
    say = await server.db.users.count_documents({"email": "admin@test.local"})
    check(say == 1, f"admin tekil (idempotent) — adet={say}")

    # server.app startup event handler'ına bağlı mı?
    handlers = server.app.router.on_startup
    check(any(getattr(h, "__name__", "") == "create_default_admin" for h in handlers),
          "create_default_admin app startup'a bağlı")

    await server.client.drop_database(TEST_DB)


def main():
    asyncio.run(run())
    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    sys.exit(0 if _kalan == 0 else 1)


if __name__ == "__main__":
    main()
