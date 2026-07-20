"""Girişsiz (token'lı) veli memnuniyet anketi smoke testi (madde 1).

Kapsar:
- Öğretmen POST /anketler/token → link + raw token üretir (hash DB'de).
- PUBLIC GET /anketler/anket/{token} → geçerli, sorular döner (auth YOK).
- PUBLIC POST /anketler/anket/{token} → db.veli_anketleri'ne yazar (mevcut şema:
  ogretmen_id + yanitlar[].puan/kategori + tavsiye) → dashboard özetine akar.
- Token tek kullanımlık: 2. GET/POST → 410. Geçersiz token → 404. Süresi dolmuş → 410.

İzole test DB'sine karşı çalışır. Gerçek DB'ye dokunmaz.
    cd appbackend
    .venv/Scripts/python.exe tests/test_veli_anket_token_smoke.py
"""
import asyncio
import os
import sys
import uuid

TEST_DB = "oba_test_veli_anket_token"
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
    from core.zaman import simdi
    from datetime import timedelta
    from httpx import AsyncClient, ASGITransport

    await server.client.drop_database(TEST_DB)

    teacher_id = str(uuid.uuid4())
    await server.db.users.insert_one({"id": teacher_id, "role": "teacher", "ad": "Ög", "soyad": "Retmen"})
    H_t = {"Authorization": f"Bearer {create_access_token({'sub': teacher_id})}"}
    ogrenci_id = str(uuid.uuid4())

    transport = ASGITransport(app=server.app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # ── 1) Token üret (öğretmen) ──
        r = await ac.post("/api/anketler/token", json={
            "ogretmen_id": teacher_id, "ogrenci_id": ogrenci_id,
            "ogrenci_ad": "Ali Veli", "veli_ad": "Veli", "gonder": False,
        }, headers=H_t)
        check(r.status_code == 200 and r.json().get("token") and "/veli-anket?token=" in r.json().get("link", ""),
              f"öğretmen anket linki üretti ({r.status_code})")
        raw = r.json()["token"]
        # Ham token DB'de düz saklanmıyor (yalnız hash)
        t_doc = await server.db.veli_anket_tokenlari.find_one({"ogrenci_id": ogrenci_id})
        check(t_doc and "token_hash" in t_doc and t_doc.get("token") is None, "token DB'de hash'li saklandı (raw yok)")

        # ── 2) PUBLIC doğrulama (auth header YOK) ──
        r = await ac.get(f"/api/anketler/anket/{raw}")
        check(r.status_code == 200 and r.json().get("gecerli") and len(r.json().get("sorular", [])) > 0,
              f"public GET geçerli + sorular döndü ({r.status_code})")

        # ── 3) PUBLIC gönderim → veli_anketleri'ne yazılır ──
        r = await ac.post(f"/api/anketler/anket/{raw}", json={
            "yanitlar": [{"soru_no": 1, "puan": 5, "kategori": "genel"},
                         {"soru_no": 2, "puan": 4, "kategori": "icerik"}],
            "tavsiye": True, "not_text": "Teşekkürler",
        })
        check(r.status_code == 200 and r.json().get("ok"), f"public gönderim kaydedildi ({r.status_code})")
        kayit = await server.db.veli_anketleri.find_one({"ogretmen_id": teacher_id})
        check(kayit and kayit.get("tavsiye") is True and len(kayit.get("yanitlar", [])) == 2 and kayit.get("kaynak") == "public_token",
              "anket db.veli_anketleri'ne mevcut şemayla yazıldı")

        # ── 4) Özet endpoint bu anketi görüyor (dashboard akışı) ──
        r = await ac.get(f"/api/anketler/ogretmen/{teacher_id}/ozet", headers=H_t)
        check(r.status_code == 200 and r.json().get("anket_sayisi", 0) >= 1, "öğretmen özeti anketi sayıyor")

        # ── 5) Tek kullanımlık: tekrar GET/POST → 410 ──
        r = await ac.get(f"/api/anketler/anket/{raw}")
        check(r.status_code == 410, f"kullanılmış token GET 410 ({r.status_code})")
        r = await ac.post(f"/api/anketler/anket/{raw}", json={"yanitlar": [], "tavsiye": False})
        check(r.status_code == 410, f"kullanılmış token POST 410 ({r.status_code})")

        # ── 6) Geçersiz token → 404 ──
        r = await ac.get("/api/anketler/anket/gecersiz-token-xyz")
        check(r.status_code == 404, f"geçersiz token 404 ({r.status_code})")

        # ── 7) Süresi dolmuş token → 410 ──
        import hashlib
        raw2 = "expired-" + uuid.uuid4().hex
        await server.db.veli_anket_tokenlari.insert_one({
            "id": str(uuid.uuid4()), "token_hash": hashlib.sha256(raw2.encode()).hexdigest(),
            "ogretmen_id": teacher_id, "ogrenci_id": ogrenci_id, "donem": "2026-D07",
            "gecerlilik": (simdi() - timedelta(days=1)).isoformat(), "kullanildi": False})
        r = await ac.get(f"/api/anketler/anket/{raw2}")
        check(r.status_code == 410, f"süresi dolmuş token 410 ({r.status_code})")

    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    await server.client.drop_database(TEST_DB)
    return _kalan == 0


if __name__ == "__main__":
    ok = asyncio.run(run())
    sys.exit(0 if ok else 1)
