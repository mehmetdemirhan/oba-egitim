"""AI CEO — Deniz 'Kontrol Et' kök-neden temizliği + Miran muhasebe deep-link.

(1) tekrarlanan_oneri: 3 açık kopya → bulgu üretilir → 'Kontrol Et' yinelenenleri birleştirir
    (cozuldu) → yeniden denetimde bulgu ARTIK üretilmez.
(2) Miran muhasebe notu: işaretsiz(damgasız)/yaşlanan öneriler tıklanınca gidilecek öğrenci
    id'lerini (odak_idler) + hedef taşır.

    cd appbackend
    PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe tests/test_ai_ceo_deniz_kontrol_smoke.py
"""
import asyncio
import os
import sys

TEST_DB = "oba_test_ai_ceo_deniz_kontrol"
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
    import modules.ai_ceo.deniz as deniz_mod
    import modules.ai_ceo.miran as miran_mod

    db = server.db
    await server.client.drop_database(TEST_DB)
    await db.users.insert_one({"id": "adm", "role": "admin", "ad": "A", "soyad": "M"})
    await db.users.insert_one({"id": "acc", "role": "accountant", "ad": "Mu", "soyad": "Ha"})

    def H(u):
        return {"Authorization": f"Bearer {server.create_access_token({'sub': u})}"}

    async with AsyncClient(transport=ASGITransport(app=server.app), base_url="http://test") as ac:
        # ── FIX 1: tekrarlanan_oneri 'Kontrol Et' ile çözülür ──
        deniz_mod.GEMINI_API_KEY = ""
        for i in range(3):
            await db.ai_ceo_oneriler.insert_one({"id": f"tk{i}", "baslik": "Tahsilat süreçlerinin otomasyonu",
                "kategori": "tahsilat", "oncelik": "orta", "ozet": "x", "zayif_dayanak": False,
                "durum": "yeni", "tarih": f"2026-07-0{i+1}T00:00:00"})
        r = await ac.post("/api/ai/ceo/deniz/denetle", headers=H("adm"))
        bulgu = next((b for b in r.json()["bulgular"] if b["tur"] == "tekrarlanan_oneri"), None)
        check(bulgu is not None, "3 açık kopya → 'tekrarlanan_oneri' bulgusu üretildi")

        r = await ac.post(f"/api/ai/ceo/deniz/bulgu/{bulgu['id']}/kontrol", headers=H("adm"))
        check(r.json().get("durum") == "cozuldu", f"'Kontrol Et' → çözüldü ({r.json().get('durum')})")
        acik = await db.ai_ceo_oneriler.count_documents({"baslik": "Tahsilat süreçlerinin otomasyonu", "durum": "yeni"})
        ertel = await db.ai_ceo_oneriler.count_documents({"baslik": "Tahsilat süreçlerinin otomasyonu", "durum": "ertelendi"})
        check(acik == 1 and ertel == 2, f"yinelenenler tek örneğe indi (açık=1, ertelendi=2) ({acik}/{ertel})")
        # yeniden denetim → bulgu artık YOK
        r = await ac.post("/api/ai/ceo/deniz/denetle", headers=H("adm"))
        check("tekrarlanan_oneri" not in {b["tur"] for b in r.json()["bulgular"]}, "yeniden denetimde 'tekrarlanan_oneri' üretilmiyor (kök neden giderildi)")

        # ── FIX 2: Miran muhasebe notu deep-link (odak_idler + hedef) ──
        miran_mod.GEMINI_API_KEY = ""  # deterministik → öngörülebilir başlıklar
        await db.kur_ucretleri.insert_one({"id": "k1", "ogrenci_id": "s1", "tutar": 1000, "yapilan_odeme": 1000})  # damgasız
        await db.kur_ucretleri.insert_one({"id": "k2", "ogrenci_id": "s2", "tutar": 1000, "yapilan_odeme": 0, "baslangic_tarihi": "2026-01-01T00:00:00"})  # 60+ yaşlanan
        r = await ac.get("/api/ai/ceo/miran/muhasebe", headers=H("acc"))
        oneriler = r.json()["miran"]["icerik"]["oneriler"]
        dmg = next((o for o in oneriler if o.get("hedef") == "damgasiz"), None)
        yas = next((o for o in oneriler if o.get("hedef") == "borclu"), None)
        check(dmg is not None and "s1" in (dmg.get("odak_idler") or []), f"işaretsiz ödeme notu → s1 öğrencisine deep-link ({dmg and dmg.get('odak_idler')})")
        check(yas is not None and "s2" in (yas.get("odak_idler") or []), f"yaşlanan alacak notu → s2 (borçlu) deep-link ({yas and yas.get('odak_idler')})")

    await server.client.drop_database(TEST_DB)


if __name__ == "__main__":
    asyncio.run(run())
    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    sys.exit(1 if _kalan else 0)
