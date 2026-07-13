"""Görev atama (/gorevler, /gorevler/toplu) smoke testi.

Regresyon: toplu görev atama 500 (insert_one'ın eklediği _id ObjectId'sinin
response'a sızması) düzeltmesini korur.
    cd appbackend
    .venv/Scripts/python.exe tests/test_gorev_smoke.py
"""
import asyncio
import os
import sys

TEST_DB = "oba_test_gorev_smoke"
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

    db = server.db
    await server.client.drop_database(TEST_DB)

    await db.users.insert_one({"id": "g-adm", "role": "admin", "ad": "Ad", "soyad": "Min"})
    await db.users.insert_one({"id": "g-t1", "role": "teacher", "ad": "Öğ", "soyad": "Bir"})
    await db.users.insert_one({"id": "g-t2", "role": "teacher", "ad": "Öğ", "soyad": "İki"})
    await db.users.insert_one({"id": "g-t3", "role": "teacher", "ad": "Öğ", "soyad": "Üç"})
    H = {"Authorization": f"Bearer {server.create_access_token({'sub': 'g-adm'})}"}

    async with AsyncClient(transport=ASGITransport(app=server.app), base_url="http://test") as ac:
        # 1) Tekil görev atama 200 (_id sızıntısı yok)
        r = await ac.post("/api/gorevler", headers=H, json={
            "hedef_id": "g-t1", "hedef_tip": "ogretmen", "baslik": "Tekil görev"})
        check(r.status_code == 200, f"tekil görev atama 200 (status={r.status_code})")
        check("_id" not in r.json(), "tekil yanıtta _id sızmıyor")

        # 2) Toplu görev atama 200 — REGRESYON: eskiden 500 (ObjectId) verirdi
        r = await ac.post("/api/gorevler/toplu", headers=H, json={
            "hedef_tip": "ogretmen", "hedef_idler": ["g-t1", "g-t2", "g-t3"],
            "gorev": {"baslik": "Hizmet içi eğitim", "aciklama": "Toplu atama testi"}})
        check(r.status_code == 200, f"toplu görev atama 200 (status={r.status_code})")
        body = r.json()
        check(body.get("olusturulan") == 3, f"3 görev oluşturuldu ({body.get('olusturulan')})")
        check(all("_id" not in g for g in body.get("gorevler", [])), "toplu yanıtta _id sızmıyor")
        check(all(g.get("baslik") == "Hizmet içi eğitim" for g in body.get("gorevler", [])),
              "tüm görevlerde başlık doğru")

        # 3) DB'de gerçekten 3+1 görev var
        n = await db.gorevler.count_documents({})
        check(n == 4, f"DB'de 4 görev ({n})")

        # 4) Görevler listelenebiliyor (öğretmen kendi görevini görür)
        Ht1 = {"Authorization": f"Bearer {server.create_access_token({'sub': 'g-t1'})}"}
        r = await ac.get("/api/gorevler", headers=Ht1)
        check(r.status_code == 200, "görev listesi 200")

    await server.client.drop_database(TEST_DB)


def main():
    asyncio.run(run())
    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    sys.exit(0 if _kalan == 0 else 1)


if __name__ == "__main__":
    main()
