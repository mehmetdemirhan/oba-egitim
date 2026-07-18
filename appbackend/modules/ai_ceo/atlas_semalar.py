from pydantic import BaseModel, Field
from typing import List


class AtlasArchitectureResponse(BaseModel):
    """Atlas LLM katmanının JSON süzgecinden geçecek katı sözleşmesi (squad_prompts ATLAS ile uyumlu)."""
    kod_kalitesi_notu: int = Field(..., ge=0, le=100)
    solid_uyumluluk_durumu: str
    teknik_borc_analizi: str
    refactoring_onerileri: List[str] = Field(default_factory=list)
    mimari_onay: bool


class AtlasAnalysisRequest(BaseModel):
    task_id: str = Field(..., min_length=5, max_length=50)
    kod_blogu: str = Field(..., min_length=10, description="Analiz edilecek ham kaynak kod veya talep metni")
