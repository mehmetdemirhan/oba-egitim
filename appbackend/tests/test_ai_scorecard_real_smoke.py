"""AI Squad gerçek Karne smoke — sabit/uydurma veri YOK; boşsa 0/veri_yok, doluysa gerçek sayım.

    cd appbackend
    PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe tests/test_ai_scorecard_real_smoke.py
"""
import asyncio
import os
import sys

TEST_DB = "oba_test_scorecard_real"
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


def agent(d):
    return {a["agent_id"]: a for a in d["agent_matrix"]}


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
        # ── BOŞ DB → dürüstçe 0 / veri_yok (sahte %100 yok) ──
        d = (await ac.get("/api/ai/squad/scorecard/ozet", headers=H("koord"))).json()
        am = agent(d)
        check(d["total_pipeline_runs"] == 0 and d["average_squad_performance"] == 0.0, "boş DB → pipeline 0, ortalama 0.0")
        check(all(am[a]["toplam"] == 0 and am[a]["risk"] == "veri_yok" and am[a]["overall_score"] == 0 for a in ("atlas", "lina", "nova", "ayaz")),
              "boş DB → tüm ajanlar 0 + risk 'veri_yok' (sahte %100 YOK)")

        # ── GERÇEK veri tohumla ──
        await db.ai_atlas_reports.insert_many([
            {"rapor_id": "ra1", "mimari_onay": True, "tarih": "2026-07-19T10:00:00"},
            {"rapor_id": "ra2", "durum": "reddedildi", "tarih": "2026-07-19T11:00:00"},  # mimari_onay yok
        ])
        await db.ai_lina_reports.insert_many([
            {"rapor_id": "rl1", "durum": "tamam", "tarih": "2026-07-19T10:00:00"},
            {"rapor_id": "rl2", "durum": "guvenlik_reddetti", "tarih": "2026-07-19T11:00:00"},
        ])
        await db.ai_nova_reports.insert_one({"rapor_id": "rn1", "deploy_onayi": True, "tarih": "2026-07-19T10:00:00"})
        await db.ai_programmer_tasks.insert_many([
            {"id": "t_a", "durum": "canlida", "tarih": "2026-07-19T10:00:00"},
            {"id": "t_b", "durum": "geri_alindi", "tarih": "2026-07-19T11:00:00"},
        ])
        await db.ai_squad_pipeline_runs.insert_many([
            {"task_id": "p1", "asama": "deploy_bekliyor"},
            {"task_id": "p2", "asama": "reddedildi"},
            {"task_id": "p3", "asama": "durduruldu"},
        ])

        d = (await ac.get("/api/ai/squad/scorecard/ozet", headers=H("koord"))).json()
        am = agent(d)
        check(d["total_pipeline_runs"] == 3 and d["total_rejected_runs"] == 1 and d["total_deploy_waiting"] == 1 and d["total_durduruldu"] == 1,
              "pipeline KPI gerçek sayım (3 toplam / 1 red / 1 bekleyen / 1 durduruldu)")
        check(am["atlas"]["toplam"] == 2 and am["atlas"]["olumlu"] == 1 and am["atlas"]["engelleme"] == 1 and am["atlas"]["overall_score"] == 50 and am["atlas"]["risk"] == "critical",
              "Atlas: 2 rapor, 1 onay/1 red → skor 50 (mimari_onay True sayımı)")
        check(am["lina"]["olumlu"] == 1 and am["lina"]["engelleme"] == 1, "Lina: 1 tamam / 1 güvenlik_reddetti")
        check(am["nova"]["olumlu"] == 1 and am["nova"]["overall_score"] == 100 and am["nova"]["risk"] == "safe", "Nova: 1 vize → skor 100 safe")
        check(am["ayaz"]["olumlu"] == 1 and am["ayaz"]["engelleme"] == 1 and am["ayaz"]["overall_score"] == 50, "Ayaz: 1 canlida / 1 geri_alindi → skor 50")
        check(am["atlas"]["son_not"].startswith("son: ") and am["nova"]["yeterli_veri"] is True, "son_not gerçek rapor kimliğinden + yeterli_veri True")

        # ── Yetki ──
        check((await ac.get("/api/ai/squad/scorecard/ozet", headers=H("t1"))).status_code == 403, "öğretmen karneyi göremez (403)")

    await server.client.drop_database(TEST_DB)


if __name__ == "__main__":
    asyncio.run(run())
    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    sys.exit(1 if _kalan else 0)
