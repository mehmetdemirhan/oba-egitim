"""Soru CRUD modülü (/sorular/*) smoke testi.

Klasik `sorular` koleksiyonu üzerinde ekle/listele/güncelle/sil akışını doğrular.
İzole test DB'sine karşı çalışır. Gerçek DB'ye dokunmaz.
    cd appbackend
    .venv/Scripts/python.exe tests/test_sorular_smoke.py
"""
import asyncio
import os
import sys
import uuid

TEST_DB = "oba_test_sorular_smoke"
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

    uid = str(uuid.uuid4())
    await server.db.users.insert_one({"id": uid, "ad": "Ogr", "soyad": "Test", "role": "teacher"})
    H = {"Authorization": f"Bearer {create_access_token({'sub': uid})}"}

    transport = ASGITransport(app=server.app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.post("/api/sorular", json={
            "kitap_id": "K1", "bolum": 2, "soru_metni": "Başkent neresi?",
            "secenekler": ["Ankara", "İzmir"], "dogru_cevap": 0,
        }, headers=H)
        check(r.status_code == 200, f"soru eklendi (status={r.status_code})")
        soru = r.json()
        soru_id = soru["id"]
        check(soru["bolum"] == 2 and soru["kullanim_sayisi"] == 0, "soru alanları doğru")

        r = await ac.get("/api/sorular/K1", headers=H)
        check(r.status_code == 200 and len(r.json()) == 1, "kitabın soruları listelendi")

        r = await ac.get("/api/sorular/K1?bolum=2", headers=H)
        check(r.status_code == 200 and len(r.json()) == 1, "bölüm filtresi çalıştı")
        r = await ac.get("/api/sorular/K1?bolum=9", headers=H)
        check(r.status_code == 200 and len(r.json()) == 0, "boş bölüm filtresi 0 döndü")

        r = await ac.put(f"/api/sorular/{soru_id}", json={"dogru_cevap": 1, "bolum": 3}, headers=H)
        check(r.status_code == 200, "soru güncellendi")
        d = await server.db.sorular.find_one({"id": soru_id})
        check(d["dogru_cevap"] == 1 and d["bolum"] == 3, "güncelleme DB'ye yazıldı")

        r = await ac.delete(f"/api/sorular/{soru_id}", headers=H)
        check(r.status_code == 200, "soru silindi")
        check(await server.db.sorular.count_documents({"id": soru_id}) == 0, "soru DB'den silindi")

    await server.client.drop_database(TEST_DB)


def main():
    asyncio.run(run())
    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    sys.exit(0 if _kalan == 0 else 1)


if __name__ == "__main__":
    main()
