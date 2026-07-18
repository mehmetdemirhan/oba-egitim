"""AI Squad Lina Motoru smoke — LLM tasarım üretimi + GERÇEK statik JSX süzgeci (uydurma yok).

Kapsam: GEMINI yok → llm_gerekli (uydurma tasarım YOK); güvenli tasarım → tamam; dangerouslySetInnerHTML
→ guvenlik_reddetti; harici CDN/<script> → reddet; geçersiz hedef_dosya yolu → reddet; yetki (öğretmen
403); islem_log audit; raporlar ucu.

    cd appbackend
    PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe tests/test_ai_lina_motoru_smoke.py
"""
import asyncio
import os
import sys

TEST_DB = "oba_test_lina"
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


def design(react_kodu, hedef="frontend/src/components/Foo.jsx"):
    return {"eski_gorunum_ozeti": "e", "yeni_gorunum_ozeti": "y", "react_kodu": react_kodu,
            "tailwind_siniflari": ["p-4"], "hedef_dosya": hedef, "risk_seviyesi": "dusuk"}


SAFE = design("export default function C(){return <div className='p-4 bg-slate-900 text-white'>OBA</div>}")
XSS = design("export default function C(){return <div dangerouslySetInnerHTML={{__html: x}} />}")
CDN = design("export default function C(){return <div><script src='https://cdn.tailwindcss.com'></script></div>}")
BADPATH = design("export default function C(){return <div className='p-4'>x</div>}", hedef="appbackend/modules/x.py")


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
        async def fake(system, user, max_tokens=2500, ozellik=""):
            return {"parsed": dict(out), "text": "", "error": None}
        return fake

    async with AsyncClient(transport=ASGITransport(app=server.app), base_url="http://test") as ac:
        # ── GEMINI yok → llm_gerekli (uydurma yok) ──
        ai_mod.GEMINI_API_KEY = ""
        r = await ac.post("/api/ai/squad/lina/tasarla", headers=H("koord"), json={"task_id": "task_l0", "talep": "kart tasarla"})
        check(r.status_code == 200 and r.json()["durum"] == "llm_gerekli", "GEMINI yok → llm_gerekli (uydurma tasarım üretilmedi)")

        ai_mod.GEMINI_API_KEY = "k"
        # ── Güvenli tasarım → tamam ──
        ai_mod.call_claude = cc(SAFE)
        r = await ac.post("/api/ai/squad/lina/tasarla", headers=H("koord"), json={"task_id": "task_ok", "talep": "kart tasarla"})
        rap = r.json()["rapor"]
        check(r.status_code == 200 and rap["durum"] == "tamam" and not rap["guvenlik_bloklari"], "güvenli JSX + geçerli yol → tamam")

        # ── dangerouslySetInnerHTML → reddet ──
        ai_mod.call_claude = cc(XSS)
        rap = (await ac.post("/api/ai/squad/lina/tasarla", headers=H("koord"), json={"task_id": "task_xss", "talep": "tasarim yap"})).json()["rapor"]
        check(rap["durum"] == "guvenlik_reddetti" and any("dangerouslySetInnerHTML" in b for b in rap["guvenlik_bloklari"]),
              "dangerouslySetInnerHTML → guvenlik_reddetti (patch_security JSX)")

        # ── Harici CDN/<script> → reddet ──
        ai_mod.call_claude = cc(CDN)
        rap = (await ac.post("/api/ai/squad/lina/tasarla", headers=H("koord"), json={"task_id": "task_cdn", "talep": "tasarim yap"})).json()["rapor"]
        check(rap["durum"] == "guvenlik_reddetti" and any("script" in b.lower() or "harici url" in b.lower() for b in rap["guvenlik_bloklari"]),
              "harici CDN <script> → guvenlik_reddetti")

        # ── Geçersiz hedef_dosya yolu → reddet ──
        ai_mod.call_claude = cc(BADPATH)
        rap = (await ac.post("/api/ai/squad/lina/tasarla", headers=H("koord"), json={"task_id": "task_path", "talep": "tasarim yap"})).json()["rapor"]
        check(rap["durum"] == "guvenlik_reddetti" and any("hedef_dosya" in b for b in rap["guvenlik_bloklari"]),
              "backend/.py hedef yolu → guvenlik_reddetti (yol doğrulaması)")

        # ── Yetki + audit + raporlar ──
        ai_mod.call_claude = cc(SAFE)
        check((await ac.post("/api/ai/squad/lina/tasarla", headers=H("t1"), json={"task_id": "task_z", "talep": "tasarim yap"})).status_code == 403,
              "öğretmen Lina'yı çağıramaz (403)")
        check(await db.islem_log.find_one({"modul": "ai_squad", "islem": "lina_tasarla"}) is not None, "lina_tasarla islem_log'a düştü")
        r = await ac.get("/api/ai/squad/lina/raporlar/task_ok", headers=H("koord"))
        check(r.status_code == 200 and len(r.json()["raporlar"]) == 1, "raporlar ucu task tasarımını döndürüyor")

    await server.client.drop_database(TEST_DB)


if __name__ == "__main__":
    asyncio.run(run())
    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    sys.exit(1 if _kalan else 0)
