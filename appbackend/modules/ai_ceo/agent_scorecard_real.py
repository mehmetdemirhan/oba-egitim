"""AI Squad v1.3 — %100 DÜRÜST Ajan Karnesi (CQRS read-model, gerçek sayım).

Hiçbir `raw_agents` sabiti YOK. Tüm sayaçlar canlı koleksiyonlardan (count_documents) gelir; DB boşsa
dürüstçe 0 + risk 'veri_yok' (sıfır iş yapana sahte %100 verilmez). Her ajan KENDİ rapor
koleksiyonundan doğru semantikle sayılır:
  Atlas → ai_atlas_reports (olumlu=mimari_onay True), Lina → ai_lina_reports (olumlu=durum 'tamam'),
  Nova → ai_nova_reports (olumlu=deploy_onayi True), Ayaz → ai_programmer_tasks (olumlu=durum 'canlida',
  engelleme=guvenlik_reddetti/geri_alindi/kurulum_hatasi). Pipeline KPI'ları ai_squad_pipeline_runs'tan
  (asama alanı — orkestratörle uyumlu). Uçlar /ai/squad/scorecard/*."""
import logging

from fastapi import APIRouter, Depends, HTTPException

from core.db import db
from core.auth import require_role, UserRole
from core.zaman import iso
from .scorecard_real_semalar import RealDashboardSummaryResponse, RealAgentMetrics

router = APIRouter()
_KOORD = require_role(UserRole.ADMIN, UserRole.COORDINATOR)


def _skor_risk(olumlu: int, engelleme: int):
    toplam = olumlu + engelleme
    if toplam == 0:
        return 0, "veri_yok", False
    score = round(olumlu * 100 / toplam)
    risk = "safe" if score >= 80 else ("warning" if score >= 60 else "critical")
    return score, risk, True


async def _son_not(koleksiyon, filtre=None) -> str:
    d = await koleksiyon.find_one(filtre or {}, {"_id": 0, "tarih": 1, "rapor_id": 1, "id": 1}, sort=[("tarih", -1)])
    if not d:
        return "henüz kayıt yok"
    return f"son: {d.get('rapor_id') or d.get('id') or '—'} @ {(d.get('tarih') or '')[:16]}"


@router.get("/ai/squad/scorecard/ozet", response_model=RealDashboardSummaryResponse)
async def scorecard_ozet(current_user=Depends(_KOORD)):
    """Gerçek koleksiyonlardan canlı agregasyon. Sabit/uydurma veri YOK; boşsa 0."""
    try:
        # Pipeline KPI (asama alanı — orkestratörle uyumlu)
        total_pipelines = await db.ai_squad_pipeline_runs.count_documents({})
        total_rejected = await db.ai_squad_pipeline_runs.count_documents({"asama": "reddedildi"})
        total_waiting = await db.ai_squad_pipeline_runs.count_documents({"asama": "deploy_bekliyor"})
        total_durduruldu = await db.ai_squad_pipeline_runs.count_documents({"asama": "durduruldu"})

        # Atlas
        a_top = await db.ai_atlas_reports.count_documents({})
        a_ol = await db.ai_atlas_reports.count_documents({"mimari_onay": True})
        a_eng = a_top - a_ol
        a_score, a_risk, a_var = _skor_risk(a_ol, a_eng)

        # Lina
        l_ol = await db.ai_lina_reports.count_documents({"durum": "tamam"})
        l_eng = await db.ai_lina_reports.count_documents({"durum": "guvenlik_reddetti"})
        l_score, l_risk, l_var = _skor_risk(l_ol, l_eng)

        # Nova
        n_ol = await db.ai_nova_reports.count_documents({"deploy_onayi": True})
        n_eng = await db.ai_nova_reports.count_documents({"deploy_onayi": False})
        n_score, n_risk, n_var = _skor_risk(n_ol, n_eng)

        # Ayaz (gerçek operasyonel patch tablosu)
        y_ol = await db.ai_programmer_tasks.count_documents({"durum": "canlida"})
        y_eng = await db.ai_programmer_tasks.count_documents({"durum": {"$in": ["guvenlik_reddetti", "geri_alindi", "kurulum_hatasi"]}})
        y_score, y_risk, y_var = _skor_risk(y_ol, y_eng)

        matrix = [
            RealAgentMetrics(agent_id="atlas", agent_name="Atlas", role="Yazılım Mimarı", toplam=a_ol + a_eng,
                             olumlu=a_ol, engelleme=a_eng, overall_score=a_score, risk=a_risk, yeterli_veri=a_var,
                             son_not=await _son_not(db.ai_atlas_reports)),
            RealAgentMetrics(agent_id="lina", agent_name="Lina", role="UI/UX Tasarımcısı", toplam=l_ol + l_eng,
                             olumlu=l_ol, engelleme=l_eng, overall_score=l_score, risk=l_risk, yeterli_veri=l_var,
                             son_not=await _son_not(db.ai_lina_reports)),
            RealAgentMetrics(agent_id="nova", agent_name="Nova", role="Test ve Kalite Güvence", toplam=n_ol + n_eng,
                             olumlu=n_ol, engelleme=n_eng, overall_score=n_score, risk=n_risk, yeterli_veri=n_var,
                             son_not=await _son_not(db.ai_nova_reports)),
            RealAgentMetrics(agent_id="ayaz", agent_name="Ayaz", role="Uygulama ve Deploy", toplam=y_ol + y_eng,
                             olumlu=y_ol, engelleme=y_eng, overall_score=y_score, risk=y_risk, yeterli_veri=y_var,
                             son_not=await _son_not(db.ai_programmer_tasks)),
        ]
        veri_olanlar = [a.overall_score for a in matrix if a.yeterli_veri]
        avg = round(sum(veri_olanlar) / len(veri_olanlar), 1) if veri_olanlar else 0.0

        return RealDashboardSummaryResponse(
            total_active_agents=len(matrix), total_pipeline_runs=total_pipelines,
            total_rejected_runs=total_rejected, total_deploy_waiting=total_waiting,
            total_durduruldu=total_durduruldu, average_squad_performance=avg,
            agent_matrix=matrix, timestamp=iso())
    except Exception as e:
        logging.exception(f"[scorecard_real] karne hesaplanamadı: {e}")
        raise HTTPException(status_code=500, detail="Karne metrikleri derlenemedi.")
