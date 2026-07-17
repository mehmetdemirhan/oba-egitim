"""AI CEO — Öğretmen Deneyim Görevleri (S2) smoke testi.

Kapsar: otomatik tamamlanma (eylemden), geriye dönük migration (zaten yapılmış eylemler
tamamlanmış sayılır), XP kazanımı (ayardan) + idempotent, aşamalı sıradaki görev, ziyaret
beacon ("yaptım" butonu yok), admin tanım yönetimi, öğretmen-only.

    cd appbackend
    PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe tests/test_ai_ceo_deneyim_smoke.py
"""
import asyncio
import os
import sys

TEST_DB = "oba_test_ai_ceo_deneyim"
os.environ["MONGO_URL"] = os.environ.get("MONGO_URL_TEST", "mongodb://localhost:27017")
os.environ["DB_NAME"] = TEST_DB
os.environ.setdefault("SECRET_KEY", "test-secret-key")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_gecen = _kalan = 0


def check(k, m):
    global _gecen, _kalan
    if k:
        _gecen += 1; print(f"  [GECTI] {m}")
    else:
        _kalan += 1; print(f"  [KALDI] {m}")


async def run():
    import server
    from httpx import AsyncClient, ASGITransport

    db = server.db
    await server.client.drop_database(TEST_DB)
    await db.users.insert_one({"id": "adm", "role": "admin", "ad": "A", "soyad": "M"})
    await db.users.insert_one({"id": "t1", "role": "teacher", "ad": "T", "soyad": "1"})
    # Geriye dönük: t1 ZATEN öğrenci eklemiş, profilini doldurmuş, ders planı girmiş, Miran'a geri bildirim vermiş
    await db.teachers.insert_one({"id": "t1", "ad": "T", "soyad": "1", "atanan_ogrenciler": ["s1"],
                                  "il": "Ankara", "ilce": "Çankaya", "universite": "ODTÜ"})
    await db.ders_programi.insert_one({"id": "d1", "ogretmen_id": "t1"})
    await db.ai_ceo_miran_geribildirim.insert_one({"miran_id": "m1", "ogretmen_id": "t1", "faydali": True})

    def H(u):
        return {"Authorization": f"Bearer {server.create_access_token({'sub': u})}"}

    async with AsyncClient(transport=ASGITransport(app=server.app), base_url="http://test") as ac:
        # ── geriye dönük migration + otomatik tamamlanma ──
        r = await ac.get("/api/ai/ceo/deneyim/benim", headers=H("t1"))
        d = r.json()["deneyim"]
        check(r.status_code == 200, "deneyim/benim 200 (öğretmen)")
        bitmis = {g["id"] for g in d["gorevler"] if g["tamamlandi"]}
        check({"ilk_ogrenci", "profil_tamam", "ders_plani", "miran_geri_bildirim"} <= bitmis,
              f"geçmiş eylemler otomatik tamamlandı (migration) ({sorted(bitmis)})")
        check(d["biten"] == 4 and d["toplam"] == 7, f"4/7 görev bitti ({d['biten']}/{d['toplam']})")
        check(d["kazanilan_xp"] == 50 + 40 + 60 + 30, f"XP ayardan toplandı=180 ({d['kazanilan_xp']})")
        check(d["siradaki"] and d["siradaki"]["id"] == "timi_uygula", f"aşamalı: sıradaki 'timi_uygula' ({d['siradaki'] and d['siradaki']['id']})")

        # ── XP idempotent (tekrar değerlendirme çift XP vermez) ──
        d2 = (await ac.get("/api/ai/ceo/deneyim/benim", headers=H("t1"))).json()["deneyim"]
        check(d2["kazanilan_xp"] == d["kazanilan_xp"], "tekrar değerlendirmede XP çiftlenmiyor (idempotent)")

        # ── ziyaret beacon (yaptım butonu değil): sss_bak ──
        r = await ac.post("/api/ai/ceo/deneyim/ziyaret/sss_bak", headers=H("t1"))
        check(r.status_code == 200, "SSS ziyaret beacon kaydedildi")
        d3 = (await ac.get("/api/ai/ceo/deneyim/benim", headers=H("t1"))).json()["deneyim"]
        check(any(g["id"] == "sss_bak" and g["tamamlandi"] for g in d3["gorevler"]), "ziyaret → sss_bak otomatik tamamlandı")
        check(d3["kazanilan_xp"] == 180 + 20, f"ziyaret XP eklendi=200 ({d3['kazanilan_xp']})")

        # ── admin tanım yönetimi ──
        r = await ac.get("/api/ai/ceo/deneyim/tanimlar", headers=H("adm"))
        check(r.status_code == 200 and len(r.json()["gorevler"]) >= 5, "admin görev tanımlarını görür")
        yeni = r.json()["gorevler"][:2]
        yeni[0]["xp"] = 999
        r = await ac.put("/api/ai/ceo/deneyim/tanimlar", headers=H("adm"), json={"gorevler": yeni})
        check(r.status_code == 200, "admin görev listesini güncelledi")
        r = await ac.get("/api/ai/ceo/deneyim/tanimlar", headers=H("adm"))
        check(len(r.json()["gorevler"]) == 2 and r.json()["gorevler"][0]["xp"] == 999, "güncel tanım (2 görev, XP 999) kaydedildi")

        # ── yetki ──
        r = await ac.get("/api/ai/ceo/deneyim/benim", headers=H("adm"))
        check(r.status_code == 403, "admin öğretmen görev ekranına giremez → 403")

    await server.client.drop_database(TEST_DB)


if __name__ == "__main__":
    asyncio.run(run())
    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    sys.exit(1 if _kalan else 0)
