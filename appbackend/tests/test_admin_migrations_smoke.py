"""Admin migration endpoint smoke — /admin/migrations (ust-kur-xp).

Doğrular:
  - Yetki: yalnız admin (GET liste + POST çalıştır); non-admin → 403.
  - dry_run=true → HİÇBİR ŞEY YAZMAZ, ne yapacağını raporlar.
  - Gerçek çalıştırma → kur>1 öğrencilere üst-kur XP kaydı + etkilenen öğretmenler.
  - İdempotent: ikinci çağrıda olusturulan=0.
  - Bilinmeyen migration → 404. İşlem islem_log'a düşer.

İzole DB (oba_test_admin_migrations). Çalıştırma:
  cd appbackend && PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe tests/test_admin_migrations_smoke.py
"""
import asyncio
import os
import sys

TEST_DB = "oba_test_admin_migrations"
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
    import uuid
    import server
    from core.auth import create_access_token
    from httpx import AsyncClient, ASGITransport

    await server.client.drop_database(TEST_DB)

    admin_id, tuser_id = str(uuid.uuid4()), str(uuid.uuid4())
    tid = str(uuid.uuid4())
    await server.db.users.insert_many([
        {"id": admin_id, "ad": "Yon", "soyad": "Etici", "role": "admin"},
        {"id": tuser_id, "ad": "Zeynep", "soyad": "Hoca", "role": "teacher", "linked_id": tid},
    ])
    await server.db.teachers.insert_one({"id": tid, "ad": "Zeynep", "soyad": "Hoca"})
    # 2 kur>1 (kayıtsız) + 1 kur=1 (yok sayılmalı)
    await server.db.students.insert_many([
        {"id": str(uuid.uuid4()), "ad": "A", "soyad": "A", "kur": "3", "ogretmen_id": tid, "olusturma_tarihi": "2026-05-01T00:00:00"},
        {"id": str(uuid.uuid4()), "ad": "B", "soyad": "B", "kur": "Kur 2", "ogretmen_id": tid, "olusturma_tarihi": "2026-05-02T00:00:00"},
        {"id": str(uuid.uuid4()), "ad": "C", "soyad": "C", "kur": "1", "ogretmen_id": tid, "olusturma_tarihi": "2026-05-03T00:00:00"},
    ])

    H_admin = {"Authorization": f"Bearer {create_access_token({'sub': admin_id})}"}
    H_teacher = {"Authorization": f"Bearer {create_access_token({'sub': tuser_id})}"}

    transport = ASGITransport(app=server.app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Liste — admin / non-admin
        r = await ac.get("/api/admin/migrations", headers=H_admin)
        adlar = [m["ad"] for m in r.json().get("migrationlar", [])]
        check(r.status_code == 200 and "ust-kur-xp" in adlar, f"admin migration listesi ({r.status_code}, {adlar})")
        r = await ac.get("/api/admin/migrations", headers=H_teacher)
        check(r.status_code == 403, f"non-admin liste → 403 ({r.status_code})")

        # DRY-RUN → hiçbir şey yazmaz
        r = await ac.post("/api/admin/migrations/ust-kur-xp?dry_run=true", headers=H_admin)
        d = r.json()
        check(r.status_code == 200 and d.get("dry_run") is True and d["sonuc"]["olusturulan"] == 2,
              f"dry_run: olusturulan=2 raporlandı ({d.get('sonuc', {}).get('olusturulan')})")
        n_after_dry = await server.db.kur_atlamalari.count_documents({})
        check(n_after_dry == 0, f"dry_run HİÇBİR ŞEY YAZMADI (kur_atlamalari=0) ({n_after_dry})")

        # GERÇEK çalıştırma
        r = await ac.post("/api/admin/migrations/ust-kur-xp", headers=H_admin)
        d = r.json()
        check(r.status_code == 200 and d["sonuc"]["olusturulan"] == 2 and d["sonuc"]["zaten_var"] == 0,
              f"gerçek: 2 oluşturuldu ({d.get('sonuc', {}).get('olusturulan')})")
        check(d["sonuc"]["etkilenen_ogretmen_sayisi"] == 1
              and d["sonuc"]["etkilenen_ogretmenler"][0]["ad"] == "Zeynep Hoca"
              and d["sonuc"]["etkilenen_ogretmenler"][0]["kayit_sayisi"] == 2,
              "etkilenen öğretmen raporu (Zeynep Hoca, 2 kayıt)")
        kayitlar = await server.db.kur_atlamalari.find({"kaynak": "migrasyon"}).to_list(length=None)
        check(len(kayitlar) == 2 and all(k.get("tarih", "").startswith("2026-05") for k in kayitlar),
              f"2 migrasyon kaydı (tarih=kayıt tarihi) ({len(kayitlar)})")

        # İDEMPOTENT
        r = await ac.post("/api/admin/migrations/ust-kur-xp", headers=H_admin)
        d = r.json()
        check(d["sonuc"]["olusturulan"] == 0 and d["sonuc"]["zaten_var"] == 2,
              f"idempotent: ikinci çağrı olusturulan=0, zaten_var=2 ({d['sonuc']['olusturulan']},{d['sonuc']['zaten_var']})")
        n_final = await server.db.kur_atlamalari.count_documents({})
        check(n_final == 2, f"toplam kur_atlamalari hâlâ 2 (mükerrer yok) ({n_final})")

        # Yetki + 404
        r = await ac.post("/api/admin/migrations/ust-kur-xp", headers=H_teacher)
        check(r.status_code == 403, f"non-admin çalıştırma → 403 ({r.status_code})")
        r = await ac.post("/api/admin/migrations/olmayan-migration", headers=H_admin)
        check(r.status_code == 404, f"bilinmeyen migration → 404 ({r.status_code})")

        # islem_log
        log = await server.db.islem_log.find_one({"modul": "admin_migration", "islem": "calistir"})
        check(log is not None and log.get("hedef_id") == "ust-kur-xp" and log.get("kullanici_id") == admin_id,
              "islem_log kaydı (kim/ne çalıştırdı)")

    await server.client.drop_database(TEST_DB)


def main():
    asyncio.run(run())
    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    sys.exit(0 if _kalan == 0 else 1)


if __name__ == "__main__":
    main()
