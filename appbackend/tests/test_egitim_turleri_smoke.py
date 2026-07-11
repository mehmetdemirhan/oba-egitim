"""Dinamik eğitim türleri (CRUD + migration + pasif) smoke testi.
İzole DB (oba_test_egitim_turleri).
"""
import asyncio
import os
import sys

TEST_DB = "oba_test_egitim_turleri"
os.environ["MONGO_URL"] = os.environ.get("MONGO_URL_TEST", "mongodb://localhost:27017")
os.environ["DB_NAME"] = TEST_DB
os.environ.setdefault("SECRET_KEY", "test-secret-key")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_gecen = _kalan = 0


def check(kosul, mesaj):
    global _gecen, _kalan
    if kosul:
        _gecen += 1; print(f"  [GECTI] {mesaj}")
    else:
        _kalan += 1; print(f"  [KALDI] {mesaj}")


async def run():
    import uuid
    import server
    from core.auth import create_access_token
    from httpx import AsyncClient, ASGITransport

    await server.client.drop_database(TEST_DB)
    admin_id, teacher_id = str(uuid.uuid4()), str(uuid.uuid4())
    await server.db.users.insert_many([
        {"id": admin_id, "ad": "Yön", "soyad": "Etici", "role": "admin"},
        {"id": teacher_id, "ad": "Öğr", "soyad": "T", "role": "teacher", "linked_id": "t1"},
    ])
    # Mevcut öğrenci — migration bunun eğitim türünü de listeye eklemeli
    await server.db.students.insert_one({"id": str(uuid.uuid4()), "ad": "X", "soyad": "Y", "aldigi_egitim": "Özel Program"})
    H_admin = {"Authorization": f"Bearer {create_access_token({'sub': admin_id})}"}
    H_teacher = {"Authorization": f"Bearer {create_access_token({'sub': teacher_id})}"}

    transport = ASGITransport(app=server.app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1) Migration: ilk GET varsayılan 8 + mevcut "Özel Program" seed eder
        r = await ac.get("/api/egitim-turleri", headers=H_teacher)
        adlar = [t["ad"] for t in r.json()["turler"]]
        check(r.status_code == 200 and "Hızlı Okuma" in adlar, "varsayılan türler seed edildi (Hızlı Okuma)")
        check("Özel Program" in adlar, "migration mevcut öğrenci eğitim türünü ekledi")

        # 2) Admin branş dersi ekler
        r = await ac.post("/api/egitim-turleri", headers=H_admin, json={"ad": "Matematik", "kategori": "brans"})
        check(r.status_code == 200 and r.json()["tur"]["kategori"] == "brans", "admin branş dersi ekledi (Matematik)")
        mat_id = r.json()["tur"]["id"]
        # Mükerrer → 400
        check((await ac.post("/api/egitim-turleri", headers=H_admin, json={"ad": "Matematik"})).status_code == 400, "mükerrer tür 400")
        # Öğretmen ekleyemez → 403
        check((await ac.post("/api/egitim-turleri", headers=H_teacher, json={"ad": "Z"})).status_code == 403, "öğretmen tür ekleyemez (403)")

        # 3) Pasife al → aktif listede yok, dahil_pasif'te var
        check((await ac.delete(f"/api/egitim-turleri/{mat_id}", headers=H_admin)).status_code == 200, "tür pasife alındı")
        aktif = [t["ad"] for t in (await ac.get("/api/egitim-turleri", headers=H_admin)).json()["turler"]]
        check("Matematik" not in aktif, "pasif tür aktif listede görünmez")
        hepsi = [t["ad"] for t in (await ac.get("/api/egitim-turleri?dahil_pasif=true", headers=H_admin)).json()["turler"]]
        check("Matematik" in hepsi, "pasif tür dahil_pasif listesinde görünür")

        # 4) Düzenle (ad)
        check((await ac.put(f"/api/egitim-turleri/{mat_id}", headers=H_admin, json={"ad": "İleri Matematik", "durum": "aktif"})).status_code == 200, "tür düzenlendi")
        adlar2 = [t["ad"] for t in (await ac.get("/api/egitim-turleri", headers=H_admin)).json()["turler"]]
        check("İleri Matematik" in adlar2, "düzenlenen tür güncel")

    await server.client.drop_database(TEST_DB)


if __name__ == "__main__":
    asyncio.run(run())
    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    sys.exit(1 if _kalan else 0)
