"""SSS (/sss/*) smoke testi.

İzole test DB'sine karşı çalışır (oba_test_sss_smoke). Gerçek DB'ye dokunmaz.
    cd appbackend
    .venv/Scripts/python.exe tests/test_sss_smoke.py
"""
import asyncio
import os
import sys

TEST_DB = "oba_test_sss_smoke"
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

    # Kullanıcılar
    await db.users.insert_one({"id": "sss-admin", "role": "admin", "ad": "Yön", "soyad": "Etici", "email": "sa@test.local"})
    await db.users.insert_one({"id": "sss-veli", "role": "parent", "ad": "Ve", "soyad": "Li", "email": "sv@test.local"})
    await db.users.insert_one({"id": "sss-ogr", "role": "teacher", "ad": "Öğ", "soyad": "Retmen", "email": "so@test.local"})

    def tok(uid):
        return {"Authorization": f"Bearer {server.create_access_token({'sub': uid})}"}

    admin, veli, ogretmen = tok("sss-admin"), tok("sss-veli"), tok("sss-ogr")

    transport = ASGITransport(app=server.app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1) Rol bazlı görünürlük: yalnız öğretmene açık kayıt
        r = await ac.post("/api/sss", headers=admin, json={
            "soru": "Kur nasıl işler?", "cevap": "Şöyle işler.",
            "kategori": "Dersler/Kurlar", "roller": ["teacher"]})
        check(r.status_code == 200, "admin doğrudan SSS ekledi (öğretmene açık)")
        r = await ac.get("/api/sss", headers=ogretmen)
        check(any(k["soru"] == "Kur nasıl işler?" for k in r.json().get("kayitlar", [])),
              "öğretmen kendine açık kaydı görüyor")
        r = await ac.get("/api/sss", headers=veli)
        check(not any(k["soru"] == "Kur nasıl işler?" for k in r.json().get("kayitlar", [])),
              "veli, öğretmene açık kaydı GÖRMÜYOR")

        # 2) "herkes" kaydı her role görünür
        await ac.post("/api/sss", headers=admin, json={
            "soru": "Genel soru?", "cevap": "Genel cevap.", "kategori": "Genel", "roller": ["herkes"]})
        r = await ac.get("/api/sss", headers=veli)
        check(any(k["soru"] == "Genel soru?" for k in r.json().get("kayitlar", [])), "herkes kaydı veliye görünüyor")

        # 3) Soru gönderme → kuyruğa düşer, yayında görünmez
        r = await ac.post("/api/sss/soru", headers=veli, json={"kategori": "Ödemeler", "soru": "Ödememi nasıl yaparım?"})
        check(r.status_code == 200, "veli soru gönderdi")
        r = await ac.get("/api/sss", headers=veli)
        check(not any("Ödememi nasıl" in k["soru"] for k in r.json().get("kayitlar", [])),
              "gönderilen soru yayında GÖRÜNMÜYOR")
        r = await ac.get("/api/sss/bekleyen-sayisi", headers=admin)
        check(r.json().get("sayi") == 1, "bekleyen sayısı = 1")
        kuyruk = (await ac.get("/api/sss/bekleyen", headers=admin)).json()["kayitlar"]
        soru_id = kuyruk[0]["id"]

        # 4) Yayınla → yayına anonim girer (soran adı yok) + bildirim gider
        r = await ac.post(f"/api/sss/bekleyen/{soru_id}/yanitla", headers=admin, json={
            "aksiyon": "yayinla", "cevap": "Banka havalesiyle.",
            "kategori": "Ödemeler", "roller": ["parent"]})
        check(r.status_code == 200 and r.json().get("durum") == "yayinlandi", "soru yayınlandı")
        yeni = await db.sss.find_one({"cevap": "Banka havalesiyle."})
        check(yeni is not None and "soran_ad" not in yeni and "soran_id" not in yeni,
              "yayın kaydında soranın adı/kimliği YOK (anonim)")
        bil = await db.bildirimler.find_one({"alici_id": "sss-veli", "tur": "sss_yanit"})
        check(bil is not None, "sorana 'sss_yanit' bildirimi gitti")
        r = await ac.get("/api/sss/bekleyen-sayisi", headers=admin)
        check(r.json().get("sayi") == 0, "yayın sonrası bekleyen 0")

        # 5) "Sadece kişiye yanıtla" → yayına GİRMEZ
        await ac.post("/api/sss/soru", headers=ogretmen, json={"kategori": "Teknik", "soru": "Şifremi unuttum?"})
        kid = (await ac.get("/api/sss/bekleyen", headers=admin)).json()["kayitlar"][0]["id"]
        r = await ac.post(f"/api/sss/bekleyen/{kid}/yanitla", headers=admin, json={
            "aksiyon": "kisisel", "cevap": "Giriş ekranından sıfırlayın."})
        check(r.status_code == 200 and r.json().get("durum") == "kisisel", "kişiye yanıt verildi")
        check(await db.sss.find_one({"cevap": "Giriş ekranından sıfırlayın."}) is None,
              "kişisel yanıt YAYINA girmedi")
        check(await db.bildirimler.find_one({"alici_id": "sss-ogr", "tur": "sss_yanit"}) is not None,
              "kişisel yanıtta sorana bildirim gitti")

        # 6) Günlük limit (5) → 6. soru 429
        for i in range(4):  # veli zaten 1 sordu → +4 = 5
            await ac.post("/api/sss/soru", headers=veli, json={"kategori": "Genel", "soru": f"Soru {i}"})
        r = await ac.post("/api/sss/soru", headers=veli, json={"kategori": "Genel", "soru": "Fazladan"})
        check(r.status_code == 429, f"günlük limit aşımı 429 (status={r.status_code})")

        # 7) Düzenleme + yayından kaldırma (aktif=False → kullanıcıda görünmez)
        sid = yeni["id"]
        r = await ac.put(f"/api/sss/{sid}", headers=admin, json={"aktif": False})
        check(r.status_code == 200, "kayıt yayından kaldırıldı (aktif=False)")
        r = await ac.get("/api/sss", headers=veli)
        check(not any(k["id"] == sid for k in r.json().get("kayitlar", [])),
              "pasif kayıt kullanıcıda görünmüyor")

        # 8) Silme
        r = await ac.delete(f"/api/sss/{sid}", headers=admin)
        check(r.status_code == 200, "kayıt silindi")

        # 9) Yetki: veli yönetim ucuna erişemez
        r = await ac.get("/api/sss/bekleyen", headers=veli)
        check(r.status_code == 403, f"veli → /sss/bekleyen 403 (status={r.status_code})")

    await server.client.drop_database(TEST_DB)


def main():
    asyncio.run(run())
    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    sys.exit(0 if _kalan == 0 else 1)


if __name__ == "__main__":
    main()
