from pydantic import BaseModel, Field
from typing import List


class NovaQAResponse(BaseModel):
    """Nova LLM katmanının sözleşmesi (squad_prompts NOVA ile uyumlu).

    UYARI: lighthouse_tahmini_performans / a11y_uyumluluk_skoru GERÇEK ÖLÇÜM DEĞİL, LLM tahminidir
    (bu backend'de Playwright/Lighthouse yok). Tüketen katman bunları 'tahmin' olarak sunmalıdır."""
    test_senaryolari: List[str] = Field(default_factory=list)
    regresyon_riski: str = Field(default="orta", pattern="^(yok|dusuk|orta|yuksek)$")
    lighthouse_tahmini_performans: int = Field(default=0, ge=0, le=100)
    a11y_uyumluluk_skoru: int = Field(default=0, ge=0, le=100)
    deploy_onayi: bool = Field(default=False)
    engelleme_nedenleri: List[str] = Field(default_factory=list)


class NovaReviewRequest(BaseModel):
    task_id: str = Field(..., min_length=5, max_length=50)
    kod_blogu: str = Field(..., min_length=10, description="İncelenecek kaynak kod (backend rota / JSX)")
