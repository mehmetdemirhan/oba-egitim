"""AI Squad Dağıtım Kuyruğu smoke — squad_deploy_queue görünürlük + manuel entegre işaretleme.

Kapsam: listele gerçek şemayı doğru eşler (id→queue_id, uretilen_kod→react_kodu); entegre-et → durum
+ pipeline 'tamamlandi'; zaten entegre → 400; bilinmeyen → 404; yalnız admin entegre eder; audit.

    cd appbackend
    PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe tests/test_ai_deploy_kuyrugu_smoke.py
"""
import asyncio
import os
import sys

TEST_DB = "oba_test_deploy_kuyrugu"
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


REACT = "export default function C(){return <div className='p-4'>Rapor</div>}"


async def run():
    import server
    from httpx import AsyncClient, ASGITransport

    db = server.db
    await server.client.drop_database(TEST_DB)
    await db.users.insert_one({"id": "adm", "role": "admin", "ad": "Ad", "soyad": "M"})
    await db.users.insert_one({"id": "koord", "role": "coordinator", "ad": "Ko", "soyad": "O"})
    await db.users.insert_one({"id": "t1", "role": "teacher", "ad": "Öğ", "soyad": "B"})

    # squad_deploy_queue GERÇEK şema (ayaz_koprusu'nun yazdığı gibi) + pipeline
    await db.squad_deploy_queue.insert_one({
        "id": "dq_abc123", "squad_task_id": "task_ok", "hedef_dosya": "frontend/src/components/Rapor.jsx",
        "uretilen_kod": REACT, "guvenlik_uyarilari": [], "admin_gerekce": "mobil uyum kritik; incelendi",
        "durum": "onaylandi_entegrasyon_bekliyor", "onaylayan": "adm", "tarih": "2026-07-19T10:00:00"})
    await db.ai_squad_pipeline_runs.insert_one({"task_id": "task_ok", "asama": "onaylandi_devir"})

    def H(u):
        return {"Authorization": f"Bearer {server.create_access_token({'sub': u})}"}

    async with AsyncClient(transport=ASGITransport(app=server.app), base_url="http://test") as ac:
        # ── Listele: gerçek şema → response eşlemesi ──
        r = await ac.get("/api/ai/squad/deploy-queue/listele", headers=H("koord"))
        items = r.json()
        check(r.status_code == 200 and len(items) == 1 and items[0]["queue_id"] == "dq_abc123" and items[0]["react_kodu"] == REACT and items[0]["task_id"] == "task_ok",
              "listele: id→queue_id, uretilen_kod→react_kodu, squad_task_id→task_id doğru eşlendi")
        check(items[0]["durum"] == "onaylandi_entegrasyon_bekliyor" and items[0]["olusturma_tarihi"] == "2026-07-19T10:00:00",
              "listele: durum + olusturma_tarihi (tarih) eşlemesi")
        check((await ac.get("/api/ai/squad/deploy-queue/listele", headers=H("t1"))).status_code == 403, "öğretmen kuyruğu göremez (403)")

        # ── Yetki: entegre yalnız admin ──
        check((await ac.post("/api/ai/squad/deploy-queue/entegre-et", headers=H("koord"), json={"queue_id": "dq_abc123", "gelistirici_notu": "commit abc123"})).status_code == 403,
              "koordinatör entegre işaretleyemez (403)")

        # ── Bilinmeyen → 404 ──
        check((await ac.post("/api/ai/squad/deploy-queue/entegre-et", headers=H("adm"), json={"queue_id": "dq_yok", "gelistirici_notu": "x commit"})).status_code == 404, "bilinmeyen kuyruk → 404")

        # ── Entegre et → durum + pipeline tamamlandi ──
        r = await ac.post("/api/ai/squad/deploy-queue/entegre-et", headers=H("adm"), json={"queue_id": "dq_abc123", "gelistirici_notu": "git 9e00140 + vercel prod"})
        check(r.status_code == 200 and r.json()["durum"] == "entegre_edildi", "admin entegre işaretledi → entegre_edildi")
        q = await db.squad_deploy_queue.find_one({"id": "dq_abc123"})
        check(q["durum"] == "entegre_edildi" and q["gelistirici_notu"].startswith("git 9e00140") and q.get("entegrasyon_tarihi"), "kuyruk mühürlendi (not + tarih)")
        p = await db.ai_squad_pipeline_runs.find_one({"task_id": "task_ok"})
        check(p["asama"] == "tamamlandi", "pipeline 'tamamlandi' olarak kapandı")
        check(await db.islem_log.find_one({"modul": "ai_squad", "islem": "kuyruk_entegre"}) is not None, "kuyruk_entegre islem_log'a düştü")

        # ── Zaten entegre → 400 ──
        check((await ac.post("/api/ai/squad/deploy-queue/entegre-et", headers=H("adm"), json={"queue_id": "dq_abc123", "gelistirici_notu": "tekrar dene"})).status_code == 400, "zaten entegre → 400")

    await server.client.drop_database(TEST_DB)


if __name__ == "__main__":
    asyncio.run(run())
    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    sys.exit(1 if _kalan else 0)
