"""AI Squad Nova Motoru smoke — GERÇEK deterministik kapı + LLM tahmini (uydurma yok, sahte ölçüm yok).

Kapsam: deterministik-only (GEMINI yok); çift-katman; RBAC'sız rota → LLM 'onay' dese bile deploy_onayi
FALSE (gerçek kapı ezmesi); XSS deseni → deploy False; lighthouse/a11y 'llm_tahmini' altında + olcum_uyarisi
(top-level ölçüm gibi sunulmaz); yetki 403; audit; raporlar.

    cd appbackend
    PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe tests/test_ai_nova_motoru_smoke.py
"""
import asyncio
import os
import sys

TEST_DB = "oba_test_nova"
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


NOVA_ONAY = {"test_senaryolari": ["giriş testi"], "regresyon_riski": "dusuk",
             "lighthouse_tahmini_performans": 88, "a11y_uyumluluk_skoru": 90, "deploy_onayi": True, "engelleme_nedenleri": []}
GUVENLI_ROTA = "@router.get('/x')\nasync def x(current_user=Depends(get_current_user)):\n    return {}\n"
RBACSIZ_ROTA = "@router.get('/x')\nasync def x():\n    return {}\n"
XSS_KOD = "export default function C(){return <div dangerouslySetInnerHTML={{__html: y}} />}\n"


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

    def cc(out):
        async def fake(system, user, max_tokens=1500, ozellik=""):
            return {"parsed": dict(out), "text": "", "error": None}
        return fake

    async with AsyncClient(transport=ASGITransport(app=server.app), base_url="http://test") as ac:
        # ── GEMINI yok → deterministik-only, sahte skor yok ──
        ai_mod.GEMINI_API_KEY = ""
        rap = (await ac.post("/api/ai/squad/nova/incele", headers=H("koord"), json={"task_id": "task_d", "kod_blogu": GUVENLI_ROTA})).json()["rapor"]
        check(rap["kaynak"] == "deterministik" and rap["llm_tahmini"] is None and rap["deploy_onayi"] is True,
              "GEMINI yok → deterministik-only (llm_tahmini None, sahte lighthouse/a11y yok)")

        ai_mod.GEMINI_API_KEY = "k"
        # ── Çift katman: güvenli+auth'lu rota + LLM onay → deploy True, skorlar 'tahmin' etiketli ──
        ai_mod.call_claude = cc(NOVA_ONAY)
        rap = (await ac.post("/api/ai/squad/nova/incele", headers=H("koord"), json={"task_id": "task_ok", "kod_blogu": GUVENLI_ROTA})).json()["rapor"]
        check(rap["kaynak"] == "cift_katman" and rap["deploy_onayi"] is True, "güvenli+auth rota + LLM onay → deploy_onayi True")
        check(rap["llm_tahmini"]["lighthouse_tahmini_performans"] == 88 and "TAHMİN" in rap["olcum_uyarisi"] and "değildir" in rap["olcum_uyarisi"],
              "lighthouse/a11y 'llm_tahmini' altında + olcum_uyarisi (top-level ölçüm gibi sunulmuyor)")
        check("lighthouse_tahmini_performans" not in rap, "skorlar rapor top-level'ında DEĞİL (sahte ölçüm süsü yok)")

        # ── RBAC'sız rota: LLM 'onay' dese bile deterministik kapı ezer → deploy False ──
        ai_mod.call_claude = cc(NOVA_ONAY)  # LLM deploy_onayi=True
        rap = (await ac.post("/api/ai/squad/nova/incele", headers=H("koord"), json={"task_id": "task_rbac", "kod_blogu": RBACSIZ_ROTA})).json()["rapor"]
        check(rap["deterministik_gercek"]["rbac_riski"] is True and rap["deploy_onayi"] is False and any("RBAC" in e for e in rap["engelleme_nedenleri"]),
              "RBAC'sız rota: LLM onay verse de deploy_onayi FALSE (gerçek kapı ezmesi)")

        # ── XSS deseni → deploy False ──
        ai_mod.call_claude = cc(NOVA_ONAY)
        rap = (await ac.post("/api/ai/squad/nova/incele", headers=H("koord"), json={"task_id": "task_xss", "kod_blogu": XSS_KOD})).json()["rapor"]
        check(rap["deploy_onayi"] is False and any("dangerouslySetInnerHTML" in e for e in rap["engelleme_nedenleri"]),
              "XSS deseni → deploy_onayi False (deterministik)")

        # ── Yetki + audit + raporlar ──
        check((await ac.post("/api/ai/squad/nova/incele", headers=H("t1"), json={"task_id": "task_z", "kod_blogu": GUVENLI_ROTA})).status_code == 403,
              "öğretmen Nova'yı çağıramaz (403)")
        check(await db.islem_log.find_one({"modul": "ai_squad", "islem": "nova_incele"}) is not None, "nova_incele islem_log'a düştü")
        r = await ac.get("/api/ai/squad/nova/raporlar/task_ok", headers=H("koord"))
        check(r.status_code == 200 and len(r.json()["raporlar"]) == 1, "raporlar ucu task incelemesini döndürüyor")

    await server.client.drop_database(TEST_DB)


if __name__ == "__main__":
    asyncio.run(run())
    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    sys.exit(1 if _kalan else 0)
