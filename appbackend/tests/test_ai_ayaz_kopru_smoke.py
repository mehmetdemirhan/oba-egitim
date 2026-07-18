"""AI Squad Ayaz Köprüsü smoke — insan-onaylı devir; otomatik deploy YOK, sahte Ayaz görevi YOK.

Kapsam: deploy_bekliyor pipeline + Lina 'tamam' kodu → admin onayı → squad_deploy_queue kaydı +
pipeline 'onaylandi_devir'; deploy_bekliyor olmayan → 400; Lina kodu yok → 422; yalnız admin onaylar;
SAHTE Ayaz 'canlida' görevi (ai_programmer_tasks) YAZILMAZ; kuyruk ucu.

    cd appbackend
    PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe tests/test_ai_ayaz_kopru_smoke.py
"""
import asyncio
import os
import sys

TEST_DB = "oba_test_ayaz_kopru"
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


REACT = "export default function C(){return <div className='p-4 grid grid-cols-1'>Rapor</div>}"


async def run():
    import server
    from httpx import AsyncClient, ASGITransport

    db = server.db
    await server.client.drop_database(TEST_DB)
    await db.users.insert_one({"id": "adm", "role": "admin", "ad": "Ad", "soyad": "M"})
    await db.users.insert_one({"id": "koord", "role": "coordinator", "ad": "Ko", "soyad": "O"})

    def H(u):
        return {"Authorization": f"Bearer {server.create_access_token({'sub': u})}"}

    # deploy_bekliyor pipeline + Lina 'tamam' raporu (gerçek şema: tasarim.react_kodu)
    await db.ai_squad_pipeline_runs.insert_one({"task_id": "task_ok", "asama": "deploy_bekliyor"})
    await db.ai_lina_reports.insert_one({"task_id": "task_ok", "durum": "tamam", "tarih": "2026-07-19T10:00:00",
                                         "tasarim": {"react_kodu": REACT, "hedef_dosya": "frontend/src/components/Rapor.jsx"}})
    # deploy_bekliyor DEĞİL
    await db.ai_squad_pipeline_runs.insert_one({"task_id": "task_erken", "asama": "nova"})

    async with AsyncClient(transport=ASGITransport(app=server.app), base_url="http://test") as ac:
        gerekce = {"admin_gerekce": "Mobil uyum kritik; incelendi ve uygun bulundu."}

        # ── Yetki: yalnız admin onaylar ──
        check((await ac.post("/api/ai/squad/ayaz-kopru/onayla", headers=H("koord"), json={"task_id": "task_ok", **gerekce})).status_code == 403,
              "koordinatör onaylayamaz (403)")

        # ── Onay → kuyruk + pipeline güncel ──
        r = await ac.post("/api/ai/squad/ayaz-kopru/onayla", headers=H("adm"), json={"task_id": "task_ok", **gerekce})
        body = r.json()
        check(r.status_code == 200 and body["durum"] == "onaylandi_devir" and body["kuyruk_id"].startswith("dq_") and "manuel" in body["mesaj"].lower(),
              "admin onayı → onaylandi_devir + kuyruk_id + manuel-entegrasyon notu")
        q = await db.squad_deploy_queue.find_one({"squad_task_id": "task_ok"})
        check(q and q["uretilen_kod"] == REACT and q["durum"] == "onaylandi_entegrasyon_bekliyor" and q["onaylayan"] == "adm",
              "squad_deploy_queue: Lina'nın GERÇEK kodu + gerekçe + onaylayan mühürlendi")
        p = await db.ai_squad_pipeline_runs.find_one({"task_id": "task_ok"})
        check(p["asama"] == "onaylandi_devir" and p["devir"]["kuyruk_id"] == q["id"], "pipeline 'onaylandi_devir' + devir bağlandı")

        # ── SAHTE Ayaz 'canlida' görevi YAZILMADI (kritik) ──
        check(await db.ai_programmer_tasks.count_documents({}) == 0, "SAHTE Ayaz 'canlida' görevi enjekte EDİLMEDİ (otomatik deploy yok)")

        # ── Tekrar onay → artık deploy_bekliyor değil → 400 ──
        check((await ac.post("/api/ai/squad/ayaz-kopru/onayla", headers=H("adm"), json={"task_id": "task_ok", **gerekce})).status_code == 400,
              "zaten devredilmiş akış tekrar onaylanamaz (400)")

        # ── deploy_bekliyor değil → 400 ──
        check((await ac.post("/api/ai/squad/ayaz-kopru/onayla", headers=H("adm"), json={"task_id": "task_erken", **gerekce})).status_code == 400,
              "deploy_bekliyor olmayan akış → 400")

        # ── Lina kodu yok → 422 ──
        await db.ai_squad_pipeline_runs.insert_one({"task_id": "task_nolina", "asama": "deploy_bekliyor"})
        check((await ac.post("/api/ai/squad/ayaz-kopru/onayla", headers=H("adm"), json={"task_id": "task_nolina", **gerekce})).status_code == 422,
              "Lina kodu olmayan akış → 422")

        # ── Kuyruk ucu ──
        r = await ac.get("/api/ai/squad/ayaz-kopru/kuyruk", headers=H("koord"))
        check(r.status_code == 200 and len(r.json()["kuyruk"]) == 1, "kuyruk ucu devredilen işi listeliyor")
        check(await db.islem_log.find_one({"modul": "ai_squad", "islem": "kopru_onayla"}) is not None, "kopru_onayla islem_log'a düştü")

    await server.client.drop_database(TEST_DB)


if __name__ == "__main__":
    asyncio.run(run())
    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    sys.exit(1 if _kalan else 0)
