"""Egzersiz Motoru (/egzersiz/* yeni motor) smoke testi.

Tip listesi → içerik üret → oturum başlat → cevap → bitir → geçmiş → içerikler
akışını uçtan uca doğrular. AI key yokken mock içerik kullanılır (deterministik).
İzole test DB'sine karşı çalışır.
    cd appbackend
    .venv/Scripts/python.exe tests/test_egzersiz_motoru_smoke.py
"""
import asyncio
import os
import sys
import uuid

TEST_DB = "oba_test_egzersiz_motoru_smoke"
os.environ["MONGO_URL"] = os.environ.get("MONGO_URL_TEST", "mongodb://localhost:27017")
os.environ["DB_NAME"] = TEST_DB
os.environ.setdefault("SECRET_KEY", "test-secret-key")
# AI key'lerini boşalt → deterministik mock içerik (load_dotenv mevcut env'i ezmez)
for _k in ("GEMINI_API_KEY", "GEMINI_API_KEY_2", "GEMINI_API_KEY_3", "ANTHROPIC_API_KEY"):
    os.environ[_k] = ""
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
    await server.db.users.insert_one({"id": uid, "ad": "Ogr", "soyad": "Test", "role": "student"})
    await server.db.students.insert_one({"id": uid, "ad": "Ogr", "soyad": "Test", "sinif": 3, "toplam_xp": 0})
    H = {"Authorization": f"Bearer {create_access_token({'sub': uid})}"}

    transport = ASGITransport(app=server.app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Tip listesi
        r = await ac.get("/api/egzersiz/tipler", headers=H)
        check(r.status_code == 200, f"tipler 200 (status={r.status_code})")
        tipler = r.json().get("tipler", [])
        check(any(t["id"] == "demo" for t in tipler), "demo tipi listede")

        # sınıf filtresi
        r = await ac.get("/api/egzersiz/tipler?sinif=3", headers=H)
        check(r.status_code == 200 and any(t["id"] == "demo" for t in r.json()["tipler"]), "sınıf filtresi çalıştı")

        # 2. İçerik üret
        r = await ac.post("/api/egzersiz/uret", json={"tip": "demo", "sinif": 3}, headers=H)
        check(r.status_code == 200, f"içerik üret 200 (status={r.status_code})")
        icerik_doc = r.json()
        check("sorular" in icerik_doc.get("icerik", {}) and len(icerik_doc["icerik"]["sorular"]) == 3, "üretilen içerikte 3 soru var")
        icerik_id = icerik_doc["id"]

        # bilinmeyen tip reddedilir
        r = await ac.post("/api/egzersiz/uret", json={"tip": "yok_boyle", "sinif": 3}, headers=H)
        check(r.status_code == 400, "bilinmeyen tip 400 döndü")

        # 3. Oturum başlat (verilen içerikle)
        r = await ac.post("/api/egzersiz/oturum", json={"tip": "demo", "sinif": 3, "icerik_id": icerik_id}, headers=H)
        check(r.status_code == 200, f"oturum başlat 200 (status={r.status_code})")
        oturum = r.json()
        oturum_id = oturum["oturum_id"]
        check(oturum["toplam_soru"] == 3, "oturum toplam_soru=3")

        # 4. Cevap — doğru (mock'ta soru 0'ın doğrusu indeks 0)
        r = await ac.post(f"/api/egzersiz/oturum/{oturum_id}/cevap", json={"soru_no": 0, "cevap": 0}, headers=H)
        check(r.status_code == 200 and r.json()["dogru"] is True, "doğru cevap doğru işaretlendi")
        # Cevap — yanlış (soru 1'in doğrusu indeks 1, biz 3 veriyoruz)
        r = await ac.post(f"/api/egzersiz/oturum/{oturum_id}/cevap", json={"soru_no": 1, "cevap": 3}, headers=H)
        check(r.status_code == 200 and r.json()["dogru"] is False, "yanlış cevap yanlış işaretlendi")

        # 5. Bitir
        r = await ac.post(f"/api/egzersiz/oturum/{oturum_id}/bitir", json={"sure_sn": 42}, headers=H)
        check(r.status_code == 200, f"bitir 200 (status={r.status_code})")
        sonuc = r.json()
        check(sonuc["dogru_sayisi"] == 1 and sonuc["toplam_soru"] == 3, "puanlama doğru (1/3)")
        check(sonuc["xp"] >= 0, "xp hesaplandı")

        # XP öğrenciye eklendi mi
        st = await server.db.students.find_one({"id": uid})
        check(st.get("toplam_xp", 0) == sonuc["xp"], "XP öğrenciye eklendi")

        # 6. Geçmiş
        r = await ac.get(f"/api/egzersiz/gecmis/{uid}", headers=H)
        check(r.status_code == 200 and len(r.json()["oturumlar"]) == 1, "geçmişte 1 oturum")
        check(r.json()["oturumlar"][0]["durum"] == "tamamlandi", "oturum tamamlandı")

        # 7. İçerikler (öğretmen kütüphanesi)
        r = await ac.get("/api/egzersiz/icerikler?tip=demo&sinif=3", headers=H)
        check(r.status_code == 200 and len(r.json()["icerikler"]) >= 1, "içerikler listelendi")

    await server.client.drop_database(TEST_DB)


def main():
    asyncio.run(run())
    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    sys.exit(0 if _kalan == 0 else 1)


if __name__ == "__main__":
    main()
