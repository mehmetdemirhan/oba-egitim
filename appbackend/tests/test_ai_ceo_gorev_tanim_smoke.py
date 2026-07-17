"""AI CEO — Görev tanımı yönetimi (D2/E2): admin Ayarlar'dan görev listelerini + HEDEF
düzenler; değişiklik öğretmen keşif yoluna / yönetici adımlarına yansır.

    cd appbackend
    PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe tests/test_ai_ceo_gorev_tanim_smoke.py
"""
import asyncio
import os
import sys

TEST_DB = "oba_test_ai_ceo_gorev_tanim"
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
    await db.teachers.insert_one({"id": "t1"})

    def H(u):
        return {"Authorization": f"Bearer {server.create_access_token({'sub': u})}"}

    async with AsyncClient(transport=ASGITransport(app=server.app), base_url="http://test") as ac:
        # ── D2: öğretmen deneyim görev tanımı + HEDEF admin'ce düzenlenir ──
        r = await ac.get("/api/ai/ceo/deneyim/tanimlar", headers=H("adm"))
        gorevler = r.json()["gorevler"]
        # yeni bir görev ekle (özel hedef) + mevcut birinin hedefini değiştir
        gorevler.append({"id": "ozel", "baslik": "Özel görev", "aciklama": "test", "xp": 25, "sira": 99, "aktif": True, "hedef": "mesajlar"})
        r = await ac.put("/api/ai/ceo/deneyim/tanimlar", headers=H("adm"), json={"gorevler": gorevler})
        check(r.status_code == 200, "admin öğretmen görev listesini kaydetti")
        r = await ac.get("/api/ai/ceo/deneyim/tanimlar", headers=H("adm"))
        ozel = next((g for g in r.json()["gorevler"] if g["id"] == "ozel"), None)
        check(ozel and ozel["hedef"] == "mesajlar", "özel görev + HEDEF kaydedildi")
        # öğretmen keşif yoluna yansıyor (hedef dahil)
        r = await ac.get("/api/ai/ceo/deneyim/benim", headers=H("t1"))
        ozel_t = next((g for g in r.json()["deneyim"]["gorevler"] if g["id"] == "ozel"), None)
        check(ozel_t and ozel_t.get("hedef") == "mesajlar", "yeni görev+hedef öğretmen ekranına yansıdı")

        # ── E2: yönetici kurulum görev tanımı + HEDEF ──
        r = await ac.get("/api/ai/ceo/yonetici-adimlar/tanimlar", headers=H("adm"))
        yg = r.json()["gorevler"]
        yg.append({"id": "denetim_bak", "baslik": "Denetimi incele", "aciklama": "x", "puan": 7, "sira": 99, "aktif": True, "hedef": "ai-deniz"})
        r = await ac.put("/api/ai/ceo/yonetici-adimlar/tanimlar", headers=H("adm"), json={"gorevler": yg})
        check(r.status_code == 200, "admin yönetici görev listesini kaydetti")
        r = await ac.get("/api/ai/ceo/yonetici-adimlar", headers=H("adm"))
        yeni = next((k for k in r.json()["kurulum"] if k["id"] == "denetim_bak"), None)
        check(yeni and yeni["hedef"] == "ai-deniz", "yeni yönetici görevi+hedef adımlara yansıdı")

        # ── yetki: öğretmen tanım düzenleyemez ──
        r = await ac.put("/api/ai/ceo/deneyim/tanimlar", headers=H("t1"), json={"gorevler": []})
        check(r.status_code == 403, "öğretmen görev tanımı düzenleyemez → 403")

    await server.client.drop_database(TEST_DB)


if __name__ == "__main__":
    asyncio.run(run())
    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    sys.exit(1 if _kalan else 0)
