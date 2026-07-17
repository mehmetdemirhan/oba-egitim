"""AI CEO — Keşif yolu hedefleri + Yönetici Sıradaki Adımlar (P4/P5) smoke.

Kapsar: öğretmen görevlerinde hedef (tıkla→git) alanı; admin kurulum görevleri iki kaynak
(kurulum + dinamik) + oto-algılama/migration + Yönetim Skoru puanı + ziyaret beacon +
yönlendirme hedefleri; yetki (öğretmen 403).

    cd appbackend
    PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe tests/test_ai_ceo_adimlar_smoke.py
"""
import asyncio
import os
import sys

TEST_DB = "oba_test_ai_ceo_adimlar"
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
    await db.teachers.insert_one({"id": "t1", "ad": "T", "soyad": "1"})

    def H(u):
        return {"Authorization": f"Bearer {server.create_access_token({'sub': u})}"}

    async with AsyncClient(transport=ASGITransport(app=server.app), base_url="http://test") as ac:
        # ── P4: öğretmen görevlerinde hedef (tıkla→git) ──
        r = await ac.get("/api/ai/ceo/deneyim/benim", headers=H("t1"))
        gorevler = {g["id"]: g for g in r.json()["deneyim"]["gorevler"]}
        check(gorevler["ilk_ogrenci"].get("hedef") == "ogrencilerim", "öğretmen görevi 'İlk öğrenci' hedef=ogrencilerim")
        check(gorevler["profil_tamam"].get("hedef") == "profilim", "'Profilini tamamla' hedef=profilim")
        check(all(g.get("hedef") for g in gorevler.values()), "tüm görevlerde hedef var")

        # ── P5: yönetici sıradaki adımlar (kurulum + dinamik) ──
        r = await ac.get("/api/ai/ceo/yonetici-adimlar", headers=H("adm"))
        j = r.json()
        check(r.status_code == 200, "yonetici-adimlar 200 (admin)")
        kurulum = {k["id"]: k for k in j["kurulum"]}
        check(kurulum["kur_ucret"]["hedef"] == "payments", "kurulum görevi hedef=payments")
        check(j["siradaki"] and j["siradaki"]["id"] == "kur_ucret", "sıradaki kurulum görevi = kur_ucret")
        check(not kurulum["kur_ucret"]["tamamlandi"], "kur_ucret başta tamamlanmamış")

        # oto-algılama + migration: kur ücreti ayarı gir → görev tamamlanır + Yönetim Skoru puanı
        await db.sistem_ayarlari.insert_one({"tip": "kur_ucretleri", "degerler": {"genel": 14400}})
        r = await ac.get("/api/ai/ceo/yonetici-adimlar", headers=H("adm"))
        kur2 = {k["id"]: k for k in r.json()["kurulum"]}
        check(kur2["kur_ucret"]["tamamlandi"], "kur ücreti tanımlanınca görev OTOMATİK tamamlandı (migration)")
        sk = (await ac.get("/api/ai/ceo/yonetim-skoru", headers=H("adm"))).json()["skor"]
        check(sk["kirilim"].get("kurulum", 0) == 8, f"kurulum görevi Yönetim Skoru'na +8 ({sk['kirilim'].get('kurulum')})")

        # ziyaret beacon (yaptım butonu yok) → vergi görevi tamamlanır
        await ac.post("/api/ai/ceo/yonetici-adimlar/ziyaret/vergi", headers=H("adm"))
        r = await ac.get("/api/ai/ceo/yonetici-adimlar", headers=H("adm"))
        kur3 = {k["id"]: k for k in r.json()["kurulum"]}
        check(kur3["vergi"]["tamamlandi"], "ziyaret beacon → vergi görevi tamamlandı")

        # dinamik bekleyen işler (Gözden Kaçan Yok ile aynı kaynak) + hedefler
        await db.ai_ceo_oneriler.insert_one({"id": "o1", "durum": "yeni", "kategori": "tahsilat", "oncelik": "orta", "ozet": "x", "tarih": "2026-07-16T00:00:00"})
        await db.ai_ceo_deniz_bulgular.insert_one({"id": "b1", "durum": "yeni", "tur": "x", "onem": "orta", "ozet": "x", "tarih": "2026-07-16T00:00:00"})
        r = await ac.get("/api/ai/ceo/yonetici-adimlar", headers=H("adm"))
        dinamik = {d["tip"]: d for d in r.json()["dinamik"]}
        check(dinamik.get("karar", {}).get("hedef") == "ai-ceo", "dinamik: karar bekleyen → ai-ceo")
        check(dinamik.get("bulgu", {}).get("hedef") == "ai-deniz", "dinamik: değerlendirilmemiş bulgu → ai-deniz")
        check("Sıradaki" in r.json()["mesaj"] or "hazır" in r.json()["mesaj"], "Ayda sesiyle mesaj")

        # E3: 7 gün+ bekleyen öğe ayrı dinamik madde olarak yüzeye çıkar (kuyruk ile aynı kaynak)
        await db.ai_ceo_oneriler.insert_one({"id": "eski1", "durum": "yeni", "kategori": "buyume", "oncelik": "orta", "ozet": "x", "tarih": "2026-06-01T00:00:00"})
        r = await ac.get("/api/ai/ceo/yonetici-adimlar", headers=H("adm"))
        dinamik2 = {d["tip"]: d for d in r.json()["dinamik"]}
        gk = dinamik2.get("gozden_kaciyor", {})
        check(gk.get("hedef") == "ai-ceo" and "7+" in gk.get("baslik", ""), f"dinamik: 7 gün+ bekleyen öğe yüzeye çıktı ({gk.get('baslik')})")

        # ── yetki: öğretmen yönetici adımlarına giremez ──
        r = await ac.get("/api/ai/ceo/yonetici-adimlar", headers=H("t1"))
        check(r.status_code == 403, "öğretmen yönetici adımlarına erişemez → 403")

    await server.client.drop_database(TEST_DB)


if __name__ == "__main__":
    asyncio.run(run())
    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    sys.exit(1 if _kalan else 0)
