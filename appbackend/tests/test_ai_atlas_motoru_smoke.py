"""AI Squad Atlas Motoru smoke — çift katman (deterministik statik + LLM), uydurma yok.

Kapsam: güvenlik ihlali (patch_security) → LLM'siz reddet; GEMINI yokken deterministik-only (uydurma
LLM analizi YOK); GEMINI + geçerli JSON → çift-katman + Pydantic sözleşme; geçersiz LLM → deterministik
fallback; yetki (öğretmen 403); islem_log audit; raporlar ucu.

    cd appbackend
    PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe tests/test_ai_atlas_motoru_smoke.py
"""
import asyncio
import os
import sys

TEST_DB = "oba_test_atlas"
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


SAFE_KOD = "from fastapi import APIRouter\nrouter = APIRouter()\n\n@router.get('/x')\nasync def x():\n    return {}\n"
DANGER_KOD = "import subprocess\nx = 1\n"
ATLAS_OUT = {"kod_kalitesi_notu": 82, "solid_uyumluluk_durumu": "Uyumlu", "teknik_borc_analizi": "düşük borç",
             "refactoring_onerileri": ["fonksiyonu böl"], "mimari_onay": True}


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

    async with AsyncClient(transport=ASGITransport(app=server.app), base_url="http://test") as ac:
        # ── Güvenlik ihlali → LLM'siz reddet ──
        ai_mod.GEMINI_API_KEY = "k"
        cagrildi = {"n": 0}
        async def fake_cc(system, user, max_tokens=1500, ozellik=""):
            cagrildi["n"] += 1
            return {"parsed": dict(ATLAS_OUT), "text": "", "error": None}
        ai_mod.call_claude = fake_cc
        r = await ac.post("/api/ai/squad/atlas/analiz-et", headers=H("koord"), json={"task_id": "task_sec1", "kod_blogu": DANGER_KOD})
        rap = r.json()["rapor"]
        check(r.status_code == 200 and rap["durum"] == "reddedildi" and any("subprocess" in n for n in rap["statik_olcumler"]["guvenlik_hatalari"]),
              "tehlikeli import (subprocess) → LLM'siz REDDEDİLDİ (patch_security)")
        check(cagrildi["n"] == 0, "güvenlik reddinde LLM çağrılmadı (deterministik kapı)")

        # ── Çift katman: GEMINI + geçerli JSON ──
        r = await ac.post("/api/ai/squad/atlas/analiz-et", headers=H("koord"), json={"task_id": "task_ok1", "kod_blogu": SAFE_KOD})
        rap = r.json()["rapor"]
        check(r.status_code == 200 and rap["durum"] == "tamam" and rap["kaynak"] == "cift_katman" and rap["llm_analizi"]["kod_kalitesi_notu"] == 82,
              "güvenli kod + geçerli LLM → çift-katman rapor (Pydantic sözleşmesi geçti)")
        check(rap["mimari_onay"] is True, "mimari_onay LLM'den geldi")

        # ── Geçersiz LLM çıktısı → deterministik fallback (uydurma yok) ──
        async def fake_bad(system, user, max_tokens=1500, ozellik=""):
            return {"parsed": {"eksik_alan": 1}, "text": "", "error": None}
        ai_mod.call_claude = fake_bad
        r = await ac.post("/api/ai/squad/atlas/analiz-et", headers=H("koord"), json={"task_id": "task_bad", "kod_blogu": SAFE_KOD})
        rap = r.json()["rapor"]
        check(rap["kaynak"] == "deterministik" and rap["llm_analizi"] is None,
              "geçersiz LLM JSON → deterministik-only (sahte analiz üretilmedi)")

        # ── GEMINI yok → deterministik-only ──
        ai_mod.GEMINI_API_KEY = ""
        r = await ac.post("/api/ai/squad/atlas/analiz-et", headers=H("koord"), json={"task_id": "task_det", "kod_blogu": SAFE_KOD})
        rap = r.json()["rapor"]
        check(rap["kaynak"] == "deterministik" and rap["mimari_onay"] is True and rap["statik_olcumler"]["import_count"] >= 1,
              "GEMINI yok → deterministik statik ölçüm + türetilmiş onay")

        # ── Yetki ──
        check((await ac.post("/api/ai/squad/atlas/analiz-et", headers=H("t1"), json={"task_id": "task_x", "kod_blogu": SAFE_KOD})).status_code == 403,
              "öğretmen Atlas'ı çağıramaz (403)")

        # ── Audit + raporlar ──
        check(await db.islem_log.find_one({"modul": "ai_squad", "islem": "atlas_analiz"}) is not None, "atlas_analiz islem_log'a düştü")
        r = await ac.get("/api/ai/squad/atlas/raporlar/task_ok1", headers=H("koord"))
        check(r.status_code == 200 and len(r.json()["raporlar"]) == 1, "raporlar ucu task raporunu döndürüyor")

    await server.client.drop_database(TEST_DB)


if __name__ == "__main__":
    asyncio.run(run())
    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    sys.exit(1 if _kalan else 0)
