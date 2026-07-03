"""Tema modülü CRUD + çözümleme smoke testi (FAZ 2 + FAZ 3).

    cd appbackend
    .venv/Scripts/python.exe tests/test_tema_crud_smoke.py
"""
import asyncio
import os
import sys
import uuid

TEST_DB = "oba_test_tema_crud_smoke"
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
    from core.tema_varsayilan import TEMALAR
    from httpx import AsyncClient, ASGITransport

    await server.client.drop_database(TEST_DB)
    await ensure_indexes()
    for t in TEMALAR:
        await server.db.theme_configs.insert_one({**t})

    adm, tea, stu = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
    await server.db.users.insert_one({"id": adm, "ad": "Admin", "role": "admin"})
    await server.db.users.insert_one({"id": tea, "ad": "Ayşe", "role": "teacher"})
    await server.db.users.insert_one({"id": stu, "ad": "Ali", "role": "student"})
    HA = {"Authorization": f"Bearer {create_access_token({'sub': adm})}"}
    HT = {"Authorization": f"Bearer {create_access_token({'sub': tea})}"}
    HS = {"Authorization": f"Bearer {create_access_token({'sub': stu})}"}

    transport = ASGITransport(app=server.app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Public hazır
        r = await ac.get("/api/tema/hazir")
        check(r.status_code == 200 and len(r.data if False else r.json()) == 5, f"hazır tema 5 (status={r.status_code})")

        # Çözümleme: öğrenci → ogrenci_cream
        r = await ac.get("/api/tema/aktif", headers=HS)
        check(r.status_code == 200 and r.json()["tema"]["kod"] == "ogrenci_cream", f"öğrenci aktif=ogrenci_cream (gelen {r.json()['tema']['kod']})")
        # öğretmen → deniz (sistem varsayılan)
        r = await ac.get("/api/tema/aktif", headers=HT)
        check(r.json()["tema"]["kod"] == "deniz", f"öğretmen aktif=deniz (gelen {r.json()['tema']['kod']})")

        # Kullanıcı tercih kaydet → orman/dark
        r = await ac.post("/api/tema/kullanici/tercih", json={"tema_kodu": "orman", "mod": "dark"}, headers=HT)
        check(r.status_code == 200 and r.json()["cozumlenen"]["tema"]["kod"] == "orman", "tercih kaydedildi (orman)")
        r = await ac.get("/api/tema/aktif", headers=HT)
        check(r.json()["tema"]["kod"] == "orman" and r.json()["mod"] == "dark", "tercih sonrası aktif=orman/dark")
        # geçersiz tema → 400
        r = await ac.post("/api/tema/kullanici/tercih", json={"tema_kodu": "yok_boyle", "mod": "light"}, headers=HT)
        check(r.status_code == 400, f"geçersiz tema kodu 400 (status={r.status_code})")

        # Admin: tümü
        r = await ac.get("/api/tema/tumu", headers=HA)
        check(r.status_code == 200 and len(r.json()["temalar"]) == 5, "admin tümü 5 tema")
        # öğretmen tümü → 403
        r = await ac.get("/api/tema/tumu", headers=HT)
        check(r.status_code == 403, f"öğretmen /tema/tumu 403 (status={r.status_code})")

        # Admin: yeni özel tema
        yeni = {"kod": "ozel_test", "ad": "Özel Test", "kategori": "ozel",
                "modlar": {"light": {"primary": "#111111"}, "dark": {"primary": "#eeeeee"}}}
        r = await ac.post("/api/tema", json=yeni, headers=HA)
        check(r.status_code == 200 and r.json()["kod"] == "ozel_test", f"özel tema oluştu (status={r.status_code})")
        # duplicate → 409
        r = await ac.post("/api/tema", json=yeni, headers=HA)
        check(r.status_code == 409, "aynı kod 409")
        # öğretmen oluşturamaz
        r = await ac.post("/api/tema", json={**yeni, "kod": "x2"}, headers=HT)
        check(r.status_code == 403, "öğretmen tema oluşturamaz 403")

        # PUT güncelle
        r = await ac.put("/api/tema/ozel_test", json={"ad": "Güncellendi"}, headers=HA)
        check(r.status_code == 200 and r.json()["ad"] == "Güncellendi", "PUT güncelleme")

        # aktif-yap
        r = await ac.post("/api/tema/aktif-yap/gun_batimi", headers=HA)
        check(r.status_code == 200 and r.json()["sistem_aktif"] == "gun_batimi", "sistem aktif=gun_batimi")
        # yeni öğretmen (tercihsiz) artık gun_batimi görmeli
        tea2 = str(uuid.uuid4())
        await server.db.users.insert_one({"id": tea2, "role": "teacher"})
        r = await ac.get("/api/tema/aktif", headers={"Authorization": f"Bearer {create_access_token({'sub': tea2})}"})
        check(r.json()["tema"]["kod"] == "gun_batimi", f"sistem varsayılan değişti (gelen {r.json()['tema']['kod']})")

        # export/import
        r = await ac.get("/api/tema/export", headers=HA)
        check(r.status_code == 200 and len(r.json()["temalar"]) >= 6, "export >= 6 tema")
        r = await ac.post("/api/tema/import", json={"temalar": [{"kod": "imp1", "ad": "İçe", "modlar": {"light": {"primary": "#123456"}}}]}, headers=HA)
        check(r.status_code == 200 and r.json()["eklenen"] == 1, "import 1 ekledi")

        # DELETE: özel silinebilir, hazır silinemez
        r = await ac.delete("/api/tema/ozel_test", headers=HA)
        check(r.status_code == 200 and r.json()["ok"], "özel tema silindi")
        r = await ac.delete("/api/tema/deniz", headers=HA)
        check(r.status_code == 400, f"hazır tema silinemez 400 (status={r.status_code})")
        r = await ac.delete("/api/tema/ogrenci_cream", headers=HA)
        check(r.status_code == 400, "rol-default tema silinemez 400")

    await server.client.drop_database(TEST_DB)
    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    return _kalan == 0


if __name__ == "__main__":
    ok = asyncio.run(run())
    sys.exit(0 if ok else 1)
