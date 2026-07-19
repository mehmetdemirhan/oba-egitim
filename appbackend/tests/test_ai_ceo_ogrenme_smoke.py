"""FAZ 4 smoke — geri bildirim + RAG öğrenme enjeksiyonu + dürüst öğrenme metrikleri.

Dürüstlük: veri <5 → yeterli_veri=false ("henüz öğrenecek kadar veri yok"). Enjeksiyon = bağlam,
model eğitimi DEĞİL. Metrikler yalnız gerçek sayım.

    cd appbackend
    PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe tests/test_ai_ceo_ogrenme_smoke.py
"""
import asyncio
import os
import sys

TEST_DB = "oba_test_ogrenme"
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
    from modules.ai_ceo.ogrenme import ogrenme_enjeksiyonu

    db = server.db
    await server.client.drop_database(TEST_DB)
    await db.users.insert_one({"id": "admin1", "role": "admin", "ad": "A", "soyad": "B"})
    await db.users.insert_one({"id": "t1", "role": "teacher", "ad": "T", "soyad": "C"})

    def H(u):
        return {"Authorization": f"Bearer {server.create_access_token({'sub': u})}"}

    async with AsyncClient(transport=ASGITransport(app=server.app), base_url="http://test") as ac:
        # ── Boş → yeterli_veri false ──
        r = (await ac.get("/api/ai/ceo/ogrenme/metrikler", headers=H("admin1"))).json()
        check(r["yeterli_veri"] is False and r["toplam_geri_bildirim"] == 0, "boş → öğrenme metrikleri yetersiz")

        # ── Enjeksiyon boşken boş string ──
        check(await ogrenme_enjeksiyonu("ayda") == "", "ders yokken enjeksiyon boş")

        # ── Geçersiz puan → 400 ──
        r = await ac.post("/api/ai/ceo/geri-bildirim", json={"ajan": "ayda", "puan": "belki"}, headers=H("admin1"))
        check(r.status_code == 400, "geçersiz puan → 400")

        # ── Olumlu geri bildirim ──
        r = await ac.post("/api/ai/ceo/geri-bildirim", json={"ajan": "ayda", "puan": "olumlu", "kaynak_id": "o1", "kaynak_tur": "oneri"}, headers=H("admin1"))
        check(r.status_code == 200 and r.json()["ok"], "olumlu geri bildirim kaydedildi")

        # ── Olumsuz + düzeltme (enjekte edilebilir ders) ──
        for i in range(2):
            await ac.post("/api/ai/ceo/geri-bildirim", json={
                "ajan": "ayda", "puan": "olumsuz", "kategori": "tahsilat",
                "duzeltme_metni": f"Tahsilat önerisi gerçekçi değildi ({i}).", "kaynak_id": f"o{i+2}"}, headers=H("admin1"))

        # ── Enjeksiyon artık ders içeriyor ──
        enj = await ogrenme_enjeksiyonu("ayda")
        check("RAG hafıza" in enj and "Tahsilat önerisi gerçekçi değildi" in enj, "enjeksiyon geçmiş dersi içeriyor (RAG, ağırlık değişmez)")
        check("değişmez" in enj.lower() or "DEĞİŞMEZ" in enj, "enjeksiyon metni model ağırlığı değişmediğini belirtiyor")

        # ── 5+ kayıt → yeterli_veri true + enjekte ders sayısı ──
        for i in range(3):
            await ac.post("/api/ai/ceo/geri-bildirim", json={"ajan": "deniz", "puan": "olumsuz", "kategori": "x", "duzeltme_metni": "y"}, headers=H("admin1"))
        r = (await ac.get("/api/ai/ceo/ogrenme/metrikler", headers=H("admin1"))).json()
        check(r["yeterli_veri"] is True and r["toplam_geri_bildirim"] == 6, "6 kayıt → yeterli_veri true")
        check(r["enjekte_edilen_ders"] == 5, "enjekte edilebilir ders sayısı = 5 (olumsuz+düzeltmeli)")
        check("ayda" in r["ajan_sayim"] and r["ajan_sayim"]["ayda"]["olumsuz"] == 2, "ajan başına sayım doğru (ayda 2 olumsuz)")
        check("model ağırlıkları değişmiyor" in r["not"], "metrik yanıtı dürüstlük notu taşıyor")

        # ── Ajan filtreli metrik ──
        r = (await ac.get("/api/ai/ceo/ogrenme/metrikler", params={"ajan": "deniz"}, headers=H("admin1"))).json()
        check(r["enjekte_edilen_ders"] == 3, "ajan=deniz filtresi: 3 enjekte ders")

        # ── RBAC ──
        check((await ac.get("/api/ai/ceo/ogrenme/metrikler", headers=H("t1"))).status_code == 403, "öğretmen öğrenme metriklerini göremez (403)")
        check((await ac.get("/api/ai/ceo/geri-bildirim", headers=H("t1"))).status_code == 403, "öğretmen geri bildirim listesini göremez (403)")

    await server.client.drop_database(TEST_DB)


if __name__ == "__main__":
    asyncio.run(run())
    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    sys.exit(1 if _kalan else 0)
