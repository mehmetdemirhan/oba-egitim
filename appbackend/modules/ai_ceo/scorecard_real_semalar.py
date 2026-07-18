from pydantic import BaseModel, Field
from typing import List


class RealAgentMetrics(BaseModel):
    """Bir ajanın GERÇEK rapor/görev koleksiyonundan sayılan metrikleri (uydurma yok)."""
    agent_id: str
    agent_name: str
    role: str
    toplam: int = Field(..., ge=0, description="Ajanın ürettiği toplam karar/görev sayısı (DB'den)")
    olumlu: int = Field(..., ge=0, description="Olumlu karar (Atlas onay / Lina tamam / Nova vize / Ayaz canlıda)")
    engelleme: int = Field(..., ge=0, description="Olumsuz/engelleme (red / rollback / kurulum hatası)")
    overall_score: int = Field(..., ge=0, le=100, description="olumlu/toplam*100 (veri yoksa 0)")
    risk: str = Field(..., pattern="^(safe|warning|critical|veri_yok)$")
    yeterli_veri: bool
    son_not: str


class RealDashboardSummaryResponse(BaseModel):
    total_active_agents: int
    total_pipeline_runs: int
    total_rejected_runs: int
    total_deploy_waiting: int
    total_durduruldu: int
    average_squad_performance: float
    agent_matrix: List[RealAgentMetrics]
    timestamp: str
