"""AI Squad Orkestratör smoke — GERÇEK zincir (Atlas→Lina→Nova), gerçek kapılar, uydurma başarı YOK.

Kapsam: tam geçiş → deploy_bekliyor (Ayaz OTOMATİK değil); Atlas reddi → durur; Lina güvenlik reddi →
durur; Nova vize vermez → durur; GEMINI yok → Lina'da durduruldu; yetki 403; adımlar GERÇEK motor
çağrılarından (rapor_id'ler) gelir; pipeline durum ucu.

    cd appbackend
    PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe tests/test_ai_squad_orkestrator_smoke.py
"""
import asyncio
import os
import sys

TEST_DB = "oba_test_orkestrator"
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


ATLAS_OK = {"kod_kalitesi_notu": 85, "solid_uyumluluk_durumu": "Uyumlu", "teknik_borc_analizi": "az",
            "refactoring_onerileri": [], "mimari_onay": True}
ATLAS_RED = {**ATLAS_OK, "mimari_onay": False}
LINA_SAFE = {"eski_gorunum_ozeti": "e", "yeni_gorunum_ozeti": "y",
             "react_kodu": "export default function C(){return <div className='p-4 bg-slate-900 text-white'>OBA panel</div>}",
             "tailwind_siniflari": ["p-4"], "hedef_dosya": "frontend/src/components/Panel.jsx", "risk_seviyesi": "dusuk"}
LINA_XSS = {**LINA_SAFE, "react_kodu": "export default function C(){return <div dangerouslySetInnerHTML={{__html: z}} />}"}
NOVA_OK = {"test_senaryolari": ["render"], "regresyon_riski": "dusuk", "lighthouse_tahmini_performans": 90,
           "a11y_uyumluluk_skoru": 92, "deploy_onayi": True, "engelleme_nedenleri": []}
NOVA_RED = {**NOVA_OK, "deploy_onayi": False, "engelleme_nedenleri": ["regresyon riski yüksek"]}


def make_cc(atlas, lina, nova):
    async def fake(system, user, max_tokens=1500, ozellik=""):
        out = {"atlas": atlas, "lina": lina, "nova": nova}.get(ozellik.replace("ai_squad_", ""), {})
        return {"parsed": dict(out), "text": "", "error": None}
    return fake


async def run():
    import server
    from httpx import AsyncClient, ASGITransport
    import core.ai as ai_mod

    db = server.db
    await server.client.drop_database(TEST_DB)
    await db.users.insert_one({"id": "koord", "role": "coordinator", "ad": "Ko", "soyad": "O"})
    await db.users.insert_one({"id": "t1", "role": "teacher", "ad": "Öğ", "soyad": "B"})

    def H(u):
        return {"Authorization": f"Bearer {server.create_access_token({'sub': u})}"}

    async def tetikle(u, tid, talep="Öğrenci panelini yenile"):
        return await AC.post("/api/ai/squad/orkestrator/pipeline-tetikle", headers=H(u), json={"task_id": tid, "talep_metni": talep})

    async with AsyncClient(transport=ASGITransport(app=server.app), base_url="http://test") as AC:
        ai_mod.GEMINI_API_KEY = "k"

        # ── Tam geçiş → deploy_bekliyor (Ayaz otomatik DEĞİL) ──
        ai_mod.call_claude = make_cc(ATLAS_OK, LINA_SAFE, NOVA_OK)
        d = (await tetikle("koord", "task_full")).json()
        check(d["asama"] == "deploy_bekliyor" and d["atlas_onay"] and d["lina_uretim"] and d["nova_vize"] and d["deploy_hazir"],
              "Atlas+Lina+Nova gerçek geçiş → deploy_bekliyor")
        check(len(d["adimlar"]) == 3 and all(a.get("rapor_id") for a in d["adimlar"]),
              "adımlar GERÇEK motor raporlarından geldi (3 rapor_id)")
        # Ayaz otomatik deploy YAPMADI: hiçbir ayaz modülü kurulmadı
        check(await db.ai_programmer_tasks.count_documents({}) == 0, "Ayaz OTOMATİK deploy etmedi (insan onayı bekliyor)")

        # ── Atlas reddi → durur, Lina çağrılmaz ──
        ai_mod.call_claude = make_cc(ATLAS_RED, LINA_SAFE, NOVA_OK)
        d = (await tetikle("koord", "task_ared")).json()
        check(d["asama"] == "reddedildi" and not d["atlas_onay"] and not d["lina_uretim"], "Atlas reddi → akış durdu (Lina'ya geçmedi)")

        # ── Lina güvenlik reddi (XSS) → durur, Nova çağrılmaz ──
        ai_mod.call_claude = make_cc(ATLAS_OK, LINA_XSS, NOVA_OK)
        d = (await tetikle("koord", "task_lred")).json()
        check(d["asama"] == "reddedildi" and d["atlas_onay"] and not d["lina_uretim"] and not d["nova_vize"], "Lina XSS reddi → akış durdu (Nova'ya geçmedi)")

        # ── Nova vize vermez → durur ──
        ai_mod.call_claude = make_cc(ATLAS_OK, LINA_SAFE, NOVA_RED)
        d = (await tetikle("koord", "task_nred")).json()
        check(d["asama"] == "reddedildi" and d["lina_uretim"] and not d["nova_vize"], "Nova vize vermedi → deploy_bekliyor'a geçmedi")

        # ── GEMINI yok → Lina'da durduruldu (uydurma tasarım yok) ──
        ai_mod.GEMINI_API_KEY = ""
        d = (await tetikle("koord", "task_nolm")).json()
        check(d["asama"] == "durduruldu" and d["atlas_onay"] and not d["lina_uretim"], "GEMINI yok → Lina'da 'durduruldu' (uydurma yok)")
        ai_mod.GEMINI_API_KEY = "k"

        # ── Lina AI HATASI (geçersiz anahtar/kota) → 'durduruldu' (pipeline 500 ile ÇÖKMEZ) ──
        ai_mod.call_claude = make_cc(ATLAS_OK, {}, NOVA_OK)  # lina parse başarısız → ai_hatasi
        d = (await tetikle("koord", "task_aihata")).json()
        check(d["asama"] == "durduruldu" and d["atlas_onay"] and not d["lina_uretim"], "Lina AI hatası → 'durduruldu' (500 çökmesi ÖNLENDİ — asıl prod bug'ı)")

        # ── Yetki + durum ucu ──
        check((await tetikle("t1", "task_403")).status_code == 403, "öğretmen orkestratörü tetikleyemez (403)")
        r = await AC.get("/api/ai/squad/orkestrator/durum/task_full", headers=H("koord"))
        check(r.status_code == 200 and r.json()["pipeline"]["asama"] == "deploy_bekliyor", "durum ucu pipeline'ı döndürüyor")
        check(await db.islem_log.find_one({"modul": "ai_squad", "islem": "pipeline"}) is not None, "pipeline islem_log'a düştü")

    await server.client.drop_database(TEST_DB)


if __name__ == "__main__":
    asyncio.run(run())
    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    sys.exit(1 if _kalan else 0)
