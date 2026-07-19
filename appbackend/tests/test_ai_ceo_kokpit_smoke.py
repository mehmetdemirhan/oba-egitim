"""AI Yönetim Kokpiti (FAZ 1) smoke — durum şeridi + zincir korelasyonu + öncelik kuyruğu.

Dürüstlük: boş DB → None/0 (uydurma yok). Zincir kaynak_oneri_id ile bağlanır. RBAC korunur.

    cd appbackend
    PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe tests/test_ai_ceo_kokpit_smoke.py
"""
import asyncio
import os
import sys

TEST_DB = "oba_test_kokpit"
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

    db = server.db
    await server.client.drop_database(TEST_DB)
    await db.users.insert_one({"id": "koord", "role": "coordinator", "ad": "Ko", "soyad": "O"})
    await db.users.insert_one({"id": "t1", "role": "teacher", "ad": "Öğ", "soyad": "B"})

    def H(u):
        return {"Authorization": f"Bearer {server.create_access_token({'sub': u})}"}

    async with AsyncClient(transport=ASGITransport(app=server.app), base_url="http://test") as ac:
        # ── BOŞ DB → dürüst varsayılanlar ──
        o = (await ac.get("/api/ai/ceo/kokpit/ozet", headers=H("koord"))).json()
        check(o["ayda_saglik"] is None, "boş DB → Ayda sağlık None (uydurma yok)")
        check(o["squad_aktif_pipeline"] == 0 and o["deploy_bekleyen"] == 0, "boş DB → squad/deploy sayaç 0")
        check(o["deniz"]["acik_bulgu"] == 0 and o["deniz"]["son_denetim_tarih"] is None, "boş DB → Deniz açık bulgu 0")

        p = (await ac.get("/api/ai/ceo/kokpit/oncelik", headers=H("koord"))).json()
        check(p["toplam"] == 0, "boş DB → öncelik kuyruğu boş")

        z = (await ac.get("/api/ai/ceo/kokpit/zincir", headers=H("koord"))).json()
        check(z["sayi"] == 0, "boş DB → zincir boş")

        # ── GERÇEK veri tohumla: bağlı bir zincir ──
        KOK = "oneri-abc"
        await db.ai_ceo_oneriler.insert_one({"id": KOK, "baslik": "Tahsilatı artır", "durum": "yeni", "tarih": "2026-07-18T10:00:00+00:00"})
        await db.ai_ceo_proposals.insert_one({"id": "karar-1", "title": "Tahsilat pilotu", "status": "awaiting_decision",
                                              "kaynak_oneri_id": KOK, "tarih": "2026-07-18T11:00:00+00:00"})
        await db.ai_squad_pipeline_runs.insert_one({"task_id": "task-1", "asama": "lina", "kaynak_oneri_id": KOK,
                                                    "guncelleme_tarihi": "2026-07-18T12:00:00+00:00"})
        await db.squad_deploy_queue.insert_one({"id": "dq-1", "durum": "onaylandi_entegrasyon_bekliyor",
                                                "kaynak_oneri_id": KOK, "hedef_dosya": "frontend/x.jsx",
                                                "tarih": "2026-07-18T13:00:00+00:00"})
        # yaşlanmış deploy (7 günden eski) — öncelik kuyruğuna girmeli
        await db.squad_deploy_queue.insert_one({"id": "dq-old", "durum": "onaylandi_entegrasyon_bekliyor",
                                                "hedef_dosya": "frontend/eski.jsx", "tarih": "2020-01-01T00:00:00+00:00"})
        # Deniz kritik bulgu
        await db.ai_ceo_deniz_bulgular.insert_one({"id": "b1", "durum": "yeni", "onem": "kritik", "ozet": "Kanıt zayıf",
                                                   "tur": "kanit", "tarih": "2026-07-18T09:00:00+00:00"})
        await db.ai_ceo_denetimler.insert_one({"id": "den-1", "tarih": "2026-07-18T09:00:00+00:00"})

        o = (await ac.get("/api/ai/ceo/kokpit/ozet", headers=H("koord"))).json()
        check(o["squad_aktif_pipeline"] == 1, "aktif pipeline 1 (asama=lina)")
        check(o["deploy_bekleyen"] == 2 and o["deniz"]["kritik_bulgu"] == 1, "deploy bekleyen 2 + 1 kritik bulgu")

        z = (await ac.get("/api/ai/ceo/kokpit/zincir", headers=H("koord"))).json()
        zin = z["zincirler"][0]
        check(z["sayi"] == 1 and zin["kaynak_oneri_id"] == KOK, "zincir tek + kök kaynak_oneri_id doğru")
        check(zin["oneri"]["var"] and zin["karar"]["var"] and zin["uretim"]["var"] and zin["deploy"]["var"],
              "zincir 4 aşama da kaynak_oneri_id ile bağlandı (Öneri→Karar→Üretim→Deploy)")
        check(zin["uretim"]["id"] == "task-1" and zin["deploy"]["id"] == "dq-1", "üretim+deploy doğru kayda bağlı")

        p = (await ac.get("/api/ai/ceo/kokpit/oncelik", headers=H("koord"))).json()
        turler = {x["kaynak"] for x in p["ogeler"]}
        check({"ayda", "deniz", "deploy"} <= turler, "öncelik kuyruğunda ayda+deniz+yaşlanmış deploy var")
        check(p["ogeler"][0]["kaynak"] == "deniz", "kritik Deniz bulgusu en üstte (önem sırası)")
        check(all(x["id"] != "dq-1" for x in p["ogeler"] if x["kaynak"] == "deploy"), "taze deploy (dq-1) kuyruğa girmez, sadece yaşlanmış")

        # ── RBAC ──
        check((await ac.get("/api/ai/ceo/kokpit/ozet", headers=H("t1"))).status_code == 403, "öğretmen kokpit özetini göremez (403)")
        check((await ac.get("/api/ai/ceo/kokpit/oncelik", headers=H("t1"))).status_code == 403, "öğretmen öncelik kuyruğunu göremez (403)")

    await server.client.drop_database(TEST_DB)


if __name__ == "__main__":
    asyncio.run(run())
    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    sys.exit(1 if _kalan else 0)
