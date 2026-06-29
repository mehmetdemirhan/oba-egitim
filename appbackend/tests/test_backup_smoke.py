"""Yedekleme (backup/restore) + sürüm/güncelleme smoke testi.

Amaç: server.py refactoring'i sırasında yedekleme davranışının BOZULMADIĞINI
otomatik kanıtlamak. pytest gerektirmez; doğrudan çalıştırılır:

    cd appbackend
    .venv/Scripts/python.exe tests/test_backup_smoke.py

GÜVENLİK: Gerçek 'oba_database' DB'sine ASLA dokunmaz. İzole bir test DB'si
(oba_test_smoke) kullanır ve test başında+sonunda onu siler. restore endpoint'i
koleksiyon sildiği için bu izolasyon zorunludur.

Çıkış kodu: 0 = tüm kontroller geçti, 1 = en az bir kontrol başarısız.
"""
import asyncio
import os
import sys

TEST_DB = "oba_test_smoke"

# server import edilmeden ÖNCE ortam sabitlenmeli (server modül seviyesinde okur)
os.environ["MONGO_URL"] = os.environ.get("MONGO_URL_TEST", "mongodb://localhost:27017")
os.environ["DB_NAME"] = TEST_DB
os.environ.setdefault("SECRET_KEY", "test-secret-key")
# GITHUB_* tanımsız kalsın → updates/check 'configured: False' dönmeli
os.environ.pop("GITHUB_REPO_OWNER", None)
os.environ.pop("GITHUB_REPO_NAME", None)

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

    # ── Temiz başlangıç: test DB'sini düşür ──
    await server.client.drop_database(TEST_DB)

    # ── Admin kullanıcı seed ──
    admin_id = "smoke-admin-1"
    await db.users.insert_one({
        "id": admin_id, "role": "admin", "ad": "Smoke", "soyad": "Admin",
        "email": "smoke@test.local",
    })
    # Geri yüklenince doğrulayacağımız demo veri
    await db.smoke_demo.insert_one({"id": "demo-1", "deger": "orijinal"})

    token = server.create_access_token({"sub": admin_id})
    auth = {"Authorization": f"Bearer {token}"}

    transport = ASGITransport(app=server.app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:

        # 1) Yetkisiz erişim reddedilmeli
        r = await ac.get("/api/admin/version")
        check(r.status_code in (401, 403), f"Token'sız /admin/version reddedildi (status={r.status_code})")

        # 2) Sürüm bilgisi
        r = await ac.get("/api/admin/version", headers=auth)
        check(r.status_code == 200, f"/admin/version 200 (status={r.status_code})")
        check("version" in r.json(), "/admin/version yanıtında 'version' var")

        # 3) Güncelleme kontrolü (GITHUB tanımsız → configured False)
        r = await ac.get("/api/admin/updates/check", headers=auth)
        check(r.status_code == 200, f"/admin/updates/check 200 (status={r.status_code})")
        check(r.json().get("configured") is False, "updates/check configured=False döndü")

        # 4) Yedek oluştur
        r = await ac.post("/api/admin/backup", headers=auth)
        check(r.status_code == 200, f"/admin/backup 200 (status={r.status_code})")
        backup = r.json()
        backup_id = backup.get("id")
        check(bool(backup_id), "backup yanıtında 'id' var")
        check(backup.get("etiket") == "manual", "backup etiketi 'manual'")
        check("_id" not in backup, "backup yanıtında Mongo _id sızmamış")

        # 5) Yedek listesi
        r = await ac.get("/api/admin/backups", headers=auth)
        check(r.status_code == 200, f"/admin/backups 200 (status={r.status_code})")
        ids = [b.get("id") for b in r.json()]
        check(backup_id in ids, "oluşturulan yedek listede görünüyor")

        # 6) Yedek indir — içeriğinde seed veri olmalı
        r = await ac.get(f"/api/admin/backups/{backup_id}/download", headers=auth)
        check(r.status_code == 200, f"/admin/backups/{{id}}/download 200 (status={r.status_code})")
        check("smoke_demo" in r.text and "orijinal" in r.text, "indirilen yedek seed veriyi içeriyor")

        # 7) Yanlış onay → restore reddedilmeli
        r = await ac.post(f"/api/admin/backups/{backup_id}/restore",
                          headers=auth, json={"onay": "yanlis"})
        check(r.status_code == 403, f"yanlış onayla restore 403 (status={r.status_code})")

        # 8) Yedekten SONRA fazladan veri ekle → restore bunu silmeli
        await db.smoke_demo.insert_one({"id": "demo-2", "deger": "restore-sonrasi-silinmeli"})
        check(await db.smoke_demo.count_documents({}) == 2, "restore öncesi 2 demo kayıt var")

        r = await ac.post(f"/api/admin/backups/{backup_id}/restore",
                          headers=auth, json={"onay": "GERI YUKLE"})
        check(r.status_code == 200, f"doğru onayla restore 200 (status={r.status_code})")
        body = r.json()
        check(body.get("ok") is True, "restore ok=True")
        check("pre_restore_backup_id" in body, "restore güvenlik yedeği (pre_restore) üretti")

        # 9) restore sonrası: demo orijinal haline döndü, admin korundu
        kalan = await db.smoke_demo.find({}).to_list(length=None)
        check(len(kalan) == 1 and kalan[0]["id"] == "demo-1",
              "restore demo koleksiyonunu orijinaline döndürdü (fazla kayıt silindi)")
        admin = await db.users.find_one({"id": admin_id})
        check(admin is not None and admin.get("role") == "admin",
              "restore sonrası admin kullanıcı korundu")

        # 10) Yedek sil
        r = await ac.delete(f"/api/admin/backups/{backup_id}", headers=auth)
        check(r.status_code == 200, f"/admin/backups/{{id}} DELETE 200 (status={r.status_code})")
        r = await ac.get("/api/admin/backups", headers=auth)
        check(backup_id not in [b.get("id") for b in r.json()], "silinen yedek listeden kalktı")

    # ── Temizlik ──
    await server.client.drop_database(TEST_DB)


def main():
    asyncio.run(run())
    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    sys.exit(0 if _kalan == 0 else 1)


if __name__ == "__main__":
    main()
