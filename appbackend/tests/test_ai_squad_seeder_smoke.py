"""AI Squad Seeder ('İlk Kıvılcım') smoke — gerçek orkestratörü tetikler, SAHTE veri enjekte ETMEZ.

Kapsam: atesle → gerçek Atlas/Lina/Nova raporları + pipeline_run oluşur (deploy_bekliyor); SAHTE Ayaz
'canlida' görevi YAZILMAZ (ai_programmer_tasks 0); karne bu gerçek akıştan dolar ama Ayaz 'veri_yok'
kalır; yalnız admin.

    cd appbackend
    PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe tests/test_ai_squad_seeder_smoke.py
"""
import asyncio
import os
import sys

TEST_DB = "oba_test_seeder"
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


ATLAS_OK = {"kod_kalitesi_notu": 85, "solid_uyumluluk_durumu": "Uyumlu", "teknik_borc_analizi": "az", "refactoring_onerileri": [], "mimari_onay": True}
LINA_SAFE = {"eski_gorunum_ozeti": "e", "yeni_gorunum_ozeti": "y",
             "react_kodu": "export default function C(){return <div className='p-4 grid grid-cols-1'>Rapor</div>}",
             "tailwind_siniflari": ["p-4"], "hedef_dosya": "frontend/src/components/Rapor.jsx", "risk_seviyesi": "dusuk"}
NOVA_OK = {"test_senaryolari": ["render"], "regresyon_riski": "dusuk", "lighthouse_tahmini_performans": 90, "a11y_uyumluluk_skoru": 92, "deploy_onayi": True, "engelleme_nedenleri": []}


async def run():
    import server
    from httpx import AsyncClient, ASGITransport
    import core.ai as ai_mod

    db = server.db
    await server.client.drop_database(TEST_DB)
    await db.users.insert_one({"id": "adm", "role": "admin", "ad": "Ad", "soyad": "M"})
    await db.users.insert_one({"id": "koord", "role": "coordinator", "ad": "Ko", "soyad": "O"})

    def H(u):
        return {"Authorization": f"Bearer {server.create_access_token({'sub': u})}"}

    ai_mod.GEMINI_API_KEY = "k"
    async def fake(system, user, max_tokens=1500, ozellik=""):
        out = {"atlas": ATLAS_OK, "lina": LINA_SAFE, "nova": NOVA_OK}.get(ozellik.replace("ai_squad_", ""), {})
        return {"parsed": dict(out), "text": "", "error": None}
    ai_mod.call_claude = fake

    async with AsyncClient(transport=ASGITransport(app=server.app), base_url="http://test") as ac:
        # ── Yetki: yalnız admin ──
        check((await ac.post("/api/ai/squad/seeder/atesle", headers=H("koord"))).status_code == 403, "koordinatör seeder'ı tetikleyemez (403)")

        # ── Kıvılcım: gerçek orkestrasyon koşar ──
        r = await ac.post("/api/ai/squad/seeder/atesle", headers=H("adm"))
        body = r.json()
        check(r.status_code == 200 and body["durum"] == "kivilcim_ateslendi" and body["orkestrasyon_sonucu"]["asama"] == "deploy_bekliyor",
              "seeder gerçek akışı koşturdu → deploy_bekliyor")

        # ── Gerçek raporlar oluştu ──
        check(await db.ai_atlas_reports.count_documents({}) == 1 and await db.ai_lina_reports.count_documents({}) == 1 and await db.ai_nova_reports.count_documents({}) == 1,
              "Atlas/Lina/Nova GERÇEK raporları oluştu (her biri 1)")
        check(await db.ai_squad_pipeline_runs.count_documents({"asama": "deploy_bekliyor"}) == 1, "pipeline_run gerçek kaydedildi (deploy_bekliyor)")

        # ── SAHTE Ayaz görevi YAZILMADI (kritik dürüstlük) ──
        check(await db.ai_programmer_tasks.count_documents({}) == 0, "SAHTE 'canlida' Ayaz görevi enjekte EDİLMEDİ (ai_programmer_tasks 0)")

        # ── Karne bu gerçek akıştan doldu; Ayaz dürüstçe veri_yok ──
        sc = (await ac.get("/api/ai/squad/scorecard/ozet", headers=H("adm"))).json()
        am = {a["agent_id"]: a for a in sc["agent_matrix"]}
        check(am["atlas"]["olumlu"] == 1 and am["lina"]["olumlu"] == 1 and am["nova"]["olumlu"] == 1, "karne: Atlas/Lina/Nova gerçek sayımla doldu (—'dan çıktı)")
        check(am["ayaz"]["risk"] == "veri_yok" and am["ayaz"]["toplam"] == 0, "karne: Ayaz dürüstçe 'veri_yok' (gerçek deploy yok → sahte doldurulmadı)")

    await server.client.drop_database(TEST_DB)


if __name__ == "__main__":
    asyncio.run(run())
    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    sys.exit(1 if _kalan else 0)
