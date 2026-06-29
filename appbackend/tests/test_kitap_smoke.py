"""Kitap modülü (/kitaplar/*) smoke testi.

İki tarihsel kitap bloğunun erişilebilir yollarını doğrular:
  - Klasik kitaplar koleksiyonu (POST/GET/PUT/DELETE /kitaplar, admin-karar, oy)
  - Bölüm bazlı soru havuzu (/kitaplar/{id}/sorular, /test/*, /havuz)
İzole test DB'sine karşı çalışır. Gerçek DB'ye dokunmaz.
    cd appbackend
    .venv/Scripts/python.exe tests/test_kitap_smoke.py
"""
import asyncio
import os
import sys
import uuid

TEST_DB = "oba_test_kitap_smoke"
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

    # Admin kullanıcı + token
    admin_id = str(uuid.uuid4())
    await server.db.users.insert_one({
        "id": admin_id, "ad": "Admin", "soyad": "Test",
        "role": "admin", "puan": 0,
    })
    token = create_access_token({"sub": admin_id})
    H = {"Authorization": f"Bearer {token}"}

    transport = ASGITransport(app=server.app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # ── Blok A: klasik kitaplar ──
        r = await ac.post("/api/kitaplar", json={
            "baslik": "Define Kitabı", "yazar": "Yazar X",
            "yas_grubu": "8-10", "zorluk": "orta", "bolum_sayisi": 3,
        }, headers=H)
        check(r.status_code == 200, f"kitap eklendi (status={r.status_code})")
        kitap = r.json()
        kitap_id = kitap["id"]
        check(kitap.get("durum") == "oylama", "admin eklediği kitap 'oylama' durumunda")

        r = await ac.get("/api/kitaplar", headers=H)
        check(r.status_code == 200 and any(k["id"] == kitap_id for k in r.json()),
              "kitap listede görünüyor")

        r = await ac.put(f"/api/kitaplar/{kitap_id}", json={"baslik": "Yeni Ad"}, headers=H)
        check(r.status_code == 200, "kitap güncellendi")
        d = await server.db.kitaplar.find_one({"id": kitap_id})
        check(d and d.get("baslik") == "Yeni Ad", "güncelleme DB'ye yazıldı")

        # Oy ver (durum oylama) → katkı puanı
        r = await ac.post(f"/api/kitaplar/{kitap_id}/oy", json={"onay": True}, headers=H)
        check(r.status_code == 200, "kitap oyu kaydedildi")
        u = await server.db.users.find_one({"id": admin_id})
        check(u.get("puan", 0) == 3, "oy verince katkı puanı +3")

        # admin-karar (blok A öncelikli — durum güncelle)
        r = await ac.post(f"/api/kitaplar/{kitap_id}/admin-karar",
                          json={"onay": True, "direkt": True}, headers=H)
        check(r.status_code == 200, "admin-karar çalıştı")

        # ── Blok B: bölüm bazlı soru havuzu ──
        # Havuz kitabı doğrudan ekle (POST /kitaplar blok A'ya gider, bu yüzden DB'ye direkt)
        havuz_kitap_id = str(uuid.uuid4())
        await server.db.kitap_havuzu.insert_one({
            "id": havuz_kitap_id, "baslik": "Havuz Kitabı", "durum": "yayinda", "oylar": {},
        })

        r = await ac.post(f"/api/kitaplar/{havuz_kitap_id}/sorular", json={
            "bolum": 1, "soru": "2+2?", "secenekler": ["3", "4", "5"],
            "dogru_cevap": 1, "taksonomi": "uygulama",
        }, headers=H)
        check(r.status_code == 200, "bölüm sorusu eklendi")
        soru_id = r.json()["id"]

        r = await ac.get(f"/api/kitaplar/{havuz_kitap_id}/sorular", headers=H)
        check(r.status_code == 200 and len(r.json()) == 1, "kitabın soruları listelendi")

        r = await ac.get(f"/api/kitaplar/test/{havuz_kitap_id}/1", headers=H)
        check(r.status_code == 200 and len(r.json()) == 1, "bölüm testi çekildi")

        r = await ac.post("/api/kitaplar/test/tamamla", json={
            "kitap_id": havuz_kitap_id, "bolum": 1,
            "cevaplar": [{"soru_id": soru_id, "secilen_cevap": 1}],
        }, headers=H)
        check(r.status_code == 200, "bölüm testi tamamlandı")
        body = r.json()
        check(body["sonuc"]["yuzde"] == 100 and body["xp_kazanilan"] > 0,
              "test sonucu %100 + XP kazanıldı")

        r = await ac.get("/api/kitaplar/havuz", headers=H)
        check(r.status_code == 200 and any(k["id"] == havuz_kitap_id for k in r.json()),
              "yayındaki kitap havuzda listeleniyor")

        r = await ac.delete(f"/api/kitaplar/sorular/{soru_id}", headers=H)
        check(r.status_code == 200, "bölüm sorusu silindi")
        check(await server.db.kitap_sorulari.count_documents({"id": soru_id}) == 0,
              "soru DB'den silindi")

        # Klasik kitap sil → soruları da silinmeli
        r = await ac.delete(f"/api/kitaplar/{kitap_id}", headers=H)
        check(r.status_code == 200, "klasik kitap silindi")

    await server.client.drop_database(TEST_DB)


def main():
    asyncio.run(run())
    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    sys.exit(0 if _kalan == 0 else 1)


if __name__ == "__main__":
    main()
