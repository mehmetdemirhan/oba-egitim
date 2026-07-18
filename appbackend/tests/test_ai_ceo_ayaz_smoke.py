"""Ayaz v1.5 (GÜVENLİ sürüm) smoke.

Kapsam: doğal dil → kod taslağı + STATİK güvenlik (patch_security AST) → 'incelemede'; tehlikeli
kod → 'guvenlik_reddetti'; yetki ayrımı (öğretmen 403, koordinatör üretir/okur, uygula/reddet admin);
insan onaylı uygula MEVCUT install_patch pipeline'ına gider (test'te MOCK — gerçek dosya sistemi
mutasyonu YOK); süreç-içi exec/otomatik deploy YOK.

    cd appbackend
    PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe tests/test_ai_ceo_ayaz_smoke.py
"""
import asyncio
import os
import sys

TEST_DB = "oba_test_ai_ceo_ayaz"
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


SAFE_KOD = (
    "from fastapi import APIRouter\n"
    "from core.db import db\n"
    "router = APIRouter()\n\n"
    "@router.get('/api/ayaz-demo/rapor')\n"
    "async def rapor():\n"
    "    n = await db.students.count_documents({})\n"
    "    return {'ogrenci_sayisi': n}\n"
)
DANGER_KOD = (
    "import subprocess\n"  # patch_security TEHLIKELI_IMPORTLAR → reddedilir
    "from fastapi import APIRouter\n"
    "router = APIRouter()\n\n"
    "@router.get('/api/x')\n"
    "async def x():\n"
    "    return subprocess.check_output(['ls'])\n"
)


def _cc(kod):
    async def fake(system, user, max_tokens=3500, ozellik=""):
        return {"parsed": {"kod": kod, "aciklama": "test modülü", "degisen_dosyalar": ["modules/x.py"],
                           "risk_seviyesi": "dusuk", "etki_alani": "rapor", "tahmini_sure_dk": 10},
                "text": "", "error": None}
    return fake


async def run():
    import server
    from httpx import AsyncClient, ASGITransport
    import modules.ai_ceo.ayaz_v1 as az
    import core.patch_manager as pm

    db = server.db
    await server.client.drop_database(TEST_DB)
    await db.users.insert_one({"id": "adm", "role": "admin", "ad": "Ad", "soyad": "M"})
    await db.users.insert_one({"id": "koord", "role": "coordinator", "ad": "Ko", "soyad": "O"})
    await db.users.insert_one({"id": "t1", "role": "teacher", "ad": "Öğ", "soyad": "B"})

    def H(u):
        return {"Authorization": f"Bearer {server.create_access_token({'sub': u})}"}

    # install_patch'i MOCK'la (gerçek kurulum yapma)
    kurulmus = {}
    def fake_install(data):
        kurulmus["called"] = True
        return {"ok": True, "name": "ayaz_x", "version": "1.0.0", "placed_files": ["modules/ayaz_x.py"], "warnings": [], "errors": []}
    pm.install_patch = fake_install

    async with AsyncClient(transport=ASGITransport(app=server.app), base_url="http://test") as ac:
        # ── Güvenli kod → incelemede ──
        az.call_claude = _cc(SAFE_KOD)
        r = await ac.post("/api/ai/ayaz/talep-uret", headers=H("koord"), json={"talep": "Öğrenci sayısı raporu ekle"})
        t = r.json()["task"]
        check(r.status_code == 200 and t["durum"] == "incelemede" and not t["guvenlik"]["errors"],
              f"güvenli kod → 'incelemede' (statik AST temiz) ({r.status_code})")
        safe_id = t["id"]
        check((await ac.post("/api/ai/ayaz/talep-uret", headers=H("t1"), json={"talep": "herhangi bir şey"})).status_code == 403,
              "öğretmen talep üretemez (403)")

        # ── Tehlikeli kod (import os) → guvenlik_reddetti (exec YOK, sadece statik) ──
        az.call_claude = _cc(DANGER_KOD)
        r = await ac.post("/api/ai/ayaz/talep-uret", headers=H("adm"), json={"talep": "dosyaları listele"})
        td = r.json()["task"]
        check(r.status_code == 200 and td["durum"] == "guvenlik_reddetti" and any("import" in e for e in td["guvenlik"]["errors"]),
              "tehlikeli kod (import os) statik taramada YAKALANDI → guvenlik_reddetti (çalıştırılmadan)")
        danger_id = td["id"]

        # ── Yetki: uygula/reddet yalnız admin ──
        check((await ac.post(f"/api/ai/ayaz/gorev/{safe_id}/uygula", headers=H("koord"))).status_code == 403,
              "koordinatör uygulayamaz (yalnız admin) (403)")
        # guvenlik_reddetti uygulanamaz
        check((await ac.post(f"/api/ai/ayaz/gorev/{danger_id}/uygula", headers=H("adm"))).status_code == 400,
              "guvenlik_reddetti görev uygulanamaz (400)")

        # ── İnsan onaylı uygula → mevcut install_patch pipeline (mock) → canlida ──
        r = await ac.post(f"/api/ai/ayaz/gorev/{safe_id}/uygula", headers=H("adm"))
        check(r.status_code == 200 and r.json()["durum"] == "canlida" and kurulmus.get("called"),
              "admin (kodu gördükten sonra) uyguladı → install_patch pipeline'ından geçti → canlida")
        detay = await db.ai_programmer_tasks.find_one({"id": safe_id})
        check(detay.get("modul_adi", "").startswith("ayaz_") and detay.get("canliya_alan") == "adm",
              "canlıya alma audit'lendi (modul_adi + canliya_alan)")
        check(await db.islem_log.find_one({"modul": "ayaz", "islem": "uygula"}) is not None, "uygula islem_log'a düştü")

        # ── Reddet ──
        az.call_claude = _cc(SAFE_KOD)
        r2 = await ac.post("/api/ai/ayaz/talep-uret", headers=H("adm"), json={"talep": "başka rapor"})
        rid = r2.json()["task"]["id"]
        check((await ac.post(f"/api/ai/ayaz/gorev/{rid}/reddet", headers=H("koord"))).status_code == 403, "koordinatör reddedemez (403)")
        check((await ac.post(f"/api/ai/ayaz/gorev/{rid}/reddet", headers=H("adm"))).json().get("durum") == "reddedildi", "admin reddetti → reddedildi")

        # ── Liste ──
        r = await ac.get("/api/ai/ayaz/gorevler", headers=H("koord"))
        check(r.status_code == 200 and len(r.json()["tasks"]) >= 3, "koordinatör görev listesini okur")

    await server.client.drop_database(TEST_DB)


if __name__ == "__main__":
    asyncio.run(run())
    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    sys.exit(1 if _kalan else 0)
