"""FAZ 3 smoke — birleşik persona sohbeti leakage/RBAC sözleşmesi + zayıf dayanak guard.

GEMINI_API_KEY yok → LLM çağrısı yapılmaz; yetki (403/400) ve guard mantığı bu katmanda test edilir.

    cd appbackend
    PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe tests/test_ai_ceo_persona_sohbet_smoke.py
"""
import asyncio
import os
import sys

TEST_DB = "oba_test_persona_sohbet"
os.environ["MONGO_URL"] = os.environ.get("MONGO_URL_TEST", "mongodb://localhost:27017")
os.environ["DB_NAME"] = TEST_DB
os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ["GEMINI_API_KEY"] = ""  # LLM'i bilinçli kapat: yetki + guard katmanını izole test et
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
    from modules.ai_ceo import personalar, persona_sohbet as PS

    db = server.db
    await server.client.drop_database(TEST_DB)
    for u in [("admin1", "admin"), ("koord", "coordinator"), ("t1", "teacher"), ("acc", "accountant")]:
        await db.users.insert_one({"id": u[0], "role": u[1], "ad": "X", "soyad": "Y", "linked_id": u[0]})

    def H(u):
        return {"Authorization": f"Bearer {server.create_access_token({'sub': u})}"}

    # ── Leakage sözleşmesi (gorunur_mu) korunuyor ──
    check(personalar.gorunur_mu("ayda", "teacher") is False, "Ayda öğretmene görünmez")
    check(personalar.gorunur_mu("miran", "admin") is False, "Miran admin'e görünmez")
    check(personalar.gorunur_mu("deniz", "coordinator") is False, "Deniz koordinatöre görünmez (admin-only)")

    # ── _yetki_kontrol doğrudan ──
    import fastapi
    def yetki_403(persona, rol):
        try:
            PS._yetki_kontrol(persona, rol); return False
        except fastapi.HTTPException as e:
            return e.status_code == 403
    check(yetki_403("ayda", "teacher"), "yetki: Ayda'ya öğretmen erişemez (403)")
    check(yetki_403("deniz", "coordinator"), "yetki: Deniz'e koordinatör erişemez (403)")
    check(yetki_403("atlas", "teacher"), "yetki: Squad ajanına öğretmen erişemez (403)")

    # ── Zayıf dayanak (persona-bağımsız) mantığı ──
    d = PS._dayanak_genel("Tahsilat 999 arttı.", {"muhasebe": {"tahsil": 100}})
    check(d["zayif_dayanak"] is True and 999.0 in d["dogrulanamayan_sayilar"], "zayıf dayanak: bağlamda olmayan 999 yakalandı")
    d2 = PS._dayanak_genel("Tahsilat 100 oldu.", {"muhasebe": {"tahsil": 100}})
    check(d2["zayif_dayanak"] is False, "zayıf dayanak: bağlamdaki 100 doğrulandı")

    async with AsyncClient(transport=ASGITransport(app=server.app), base_url="http://test") as ac:
        # ── Endpoint yetki + doğrulama (LLM kapalı) ──
        r = await ac.post("/api/ai/ceo/persona-sor", json={"persona": "ayda", "soru": "test"}, headers=H("t1"))
        check(r.status_code == 403, "endpoint: öğretmen Ayda'ya soramaz (403)")

        r = await ac.post("/api/ai/ceo/persona-sor", json={"persona": "deniz", "soru": "test"}, headers=H("koord"))
        check(r.status_code == 403, "endpoint: koordinatör Deniz'e soramaz (403)")

        r = await ac.post("/api/ai/ceo/persona-sor", json={"persona": "yok", "soru": "test"}, headers=H("admin1"))
        check(r.status_code == 400, "endpoint: geçersiz persona → 400")

        r = await ac.post("/api/ai/ceo/persona-sor", json={"persona": "ayda", "soru": ""}, headers=H("admin1"))
        check(r.status_code == 400, "endpoint: boş soru → 400")

        # yetkili + LLM kapalı → 200 ok:false (yapılandırma yok) — yetki geçti demektir
        r = await ac.post("/api/ai/ceo/persona-sor", json={"persona": "ayda", "soru": "durum ne?"}, headers=H("admin1"))
        check(r.status_code == 200 and r.json()["ok"] is False and "yapılandır" in r.json()["sebep"], "endpoint: admin Ayda yetkili (LLM kapalı → ok:false)")

        r = await ac.post("/api/ai/ceo/persona-sor", json={"persona": "miran", "soru": "koçluk?"}, headers=H("t1"))
        check(r.status_code == 200 and r.json()["ok"] is False, "endpoint: öğretmen Miran'a yetkili (LLM kapalı → ok:false)")

        r = await ac.post("/api/ai/ceo/persona-sor", json={"persona": "atlas", "soru": "neden?"}, headers=H("admin1"))
        check(r.status_code == 200 and r.json()["ok"] is False, "endpoint: admin Atlas açıklamasına yetkili")

        # geçmiş ucu yetki
        r = await ac.get("/api/ai/ceo/persona-sohbet", params={"persona": "deniz"}, headers=H("t1"))
        check(r.status_code == 403, "geçmiş: öğretmen Deniz geçmişini göremez (403)")

    await server.client.drop_database(TEST_DB)


if __name__ == "__main__":
    asyncio.run(run())
    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    sys.exit(1 if _kalan else 0)
