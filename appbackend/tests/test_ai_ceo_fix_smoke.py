"""AI CEO — Deniz bulgu düzeltmeleri: tekrarlanan öneri dedup + vergi backfill smoke.

Kapsar: (1) aynı başlıklı öneri yeniden üretilmez + mevcut açık kopyalar tek örneğe indirilir
→ 'tekrarlanan_oneri' bulgusu tekrar üretilmez; (2) vergi'siz ödemelere backfill + yeni
ödemede vergi garanti.

    cd appbackend
    PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe tests/test_ai_ceo_fix_smoke.py
"""
import asyncio
import os
import sys

TEST_DB = "oba_test_ai_ceo_fix"
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
    import modules.ai_ceo.analiz as analiz_mod
    import modules.ai_ceo.deniz as deniz_mod

    db = server.db
    await server.client.drop_database(TEST_DB)
    await db.users.insert_one({"id": "adm", "role": "admin", "ad": "A", "soyad": "M"})
    await db.users.insert_one({"id": "acc", "role": "accountant", "ad": "Mu", "soyad": "Ha"})
    await db.students.insert_one({"id": "s1", "yapilmasi_gereken_odeme": 1000, "yapilan_odeme": 0})
    await db.ai_ceo_fotograflar.insert_one({"id": "f1", "tarih": "2026-07-16T00:00:00", "ogrenci": {"aktif": 1}})

    def H(u):
        return {"Authorization": f"Bearer {server.create_access_token({'sub': u})}"}

    async with AsyncClient(transport=ASGITransport(app=server.app), base_url="http://test") as ac:
        # ── FIX 1: tekrarlanan öneri dedup ──
        for i in range(3):  # 3 açık kopya (aynı başlık)
            await db.ai_ceo_oneriler.insert_one({"id": f"tk{i}", "analiz_id": "a", "baslik": "Tahsilat süreçlerinin otomasyonu",
                "kategori": "tahsilat", "oncelik": "orta", "ozet": "x", "zayif_dayanak": False,
                "dayanaklar": [], "durum": "yeni", "tarih": f"2026-07-0{i+1}T00:00:00"})
        analiz_mod.GEMINI_API_KEY = "k"

        async def sahte(system, user, max_tokens=4000):
            return {"error": None, "parsed": {"ozet": "s", "oneriler": [
                {"baslik": "Yeni Öneri", "kategori": "buyume", "oncelik": "orta", "ozet": "y", "beklenen_etki": "?",
                 "dayanak_metrikler": [{"metrik": "aktif", "deger": 1}]}]}}
        analiz_mod.call_claude = sahte
        await ac.post("/api/ai/ceo/analiz/calistir", headers=H("adm"))
        acik = await db.ai_ceo_oneriler.count_documents({"baslik": "Tahsilat süreçlerinin otomasyonu", "durum": "yeni"})
        ertel = await db.ai_ceo_oneriler.count_documents({"baslik": "Tahsilat süreçlerinin otomasyonu", "durum": "ertelendi"})
        check(acik == 1, f"mevcut açık kopyalar tek örneğe indirildi (açık=1) ({acik})")
        check(ertel == 2, f"eski kopyalar ertelendi/birleştirildi (2) ({ertel})")
        # aynı analiz tekrar → 'Yeni Öneri' YENİDEN üretilmez (açık kopya var)
        await ac.post("/api/ai/ceo/analiz/calistir", headers=H("adm"))
        yeni_say = await db.ai_ceo_oneriler.count_documents({"baslik": "Yeni Öneri", "durum": "yeni"})
        check(yeni_say == 1, f"aynı başlık yeniden üretilmedi (açık 'Yeni Öneri'=1) ({yeni_say})")
        # Deniz: tekrarlanan_oneri bulgusu artık üretilmez (açık kopya <3)
        deniz_mod.GEMINI_API_KEY = ""
        r = await ac.post("/api/ai/ceo/deniz/denetle", headers=H("adm"))
        check("tekrarlanan_oneri" not in {b["tur"] for b in r.json()["bulgular"]}, "'tekrarlanan_oneri' bulgusu artık üretilmiyor (kök neden giderildi)")

        # ── FIX 2: vergi backfill ──
        await db.payments.insert_one({"id": "pa", "tip": "ogrenci", "kisi_id": "s1", "miktar": 1000, "vergi": None, "vergi_orani": 20})
        await db.payments.insert_one({"id": "pb", "tip": "ogrenci", "kisi_id": "s1", "miktar": 500, "vergi": None})  # oran yok → güncel (15)
        await db.payments.insert_one({"id": "pc", "tip": "ogretmen", "kisi_id": "t1", "miktar": 300})  # etkilenmez
        r = await ac.post("/api/muhasebe/gecis/vergi-backfill", headers=H("acc"))
        check(r.status_code == 200 and r.json()["guncellenen_odeme"] == 2, f"2 vergi'siz ödeme backfill edildi ({r.json().get('guncellenen_odeme')})")
        pa = await db.payments.find_one({"id": "pa"}); pb = await db.payments.find_one({"id": "pb"})
        check(pa.get("vergi") == 200.0, f"kayıtlı oranla (20%) vergi = 200 ({pa.get('vergi')})")
        check(pb.get("vergi") == 75.0, f"oransız → güncel (15%) vergi = 75 ({pb.get('vergi')})")
        kalan = await db.payments.count_documents({"tip": "ogrenci", "$or": [{"vergi": None}, {"vergi": {"$exists": False}}]})
        check(kalan == 0, f"vergi'siz öğrenci ödemesi kalmadı (0) ({kalan})")
        # yeni ödeme garanti: vergi ile kaydedilir
        r = await ac.post("/api/payments", headers=H("acc"), json={"tip": "ogrenci", "kisi_id": "s1", "miktar": 1000})
        check(r.json().get("vergi") is not None and r.json()["vergi"] == 150.0, f"yeni ödeme vergi ile kaydedildi (15% → 150) ({r.json().get('vergi')})")

    await server.client.drop_database(TEST_DB)


if __name__ == "__main__":
    asyncio.run(run())
    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    sys.exit(1 if _kalan else 0)
