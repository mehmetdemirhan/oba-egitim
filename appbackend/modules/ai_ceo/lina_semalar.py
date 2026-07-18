from pydantic import BaseModel, Field
from typing import List


class LinaDesignResponse(BaseModel):
    """Lina LLM katmanının JSON süzgecinden geçecek sözleşmesi (squad_prompts LINA ile uyumlu)."""
    eski_gorunum_ozeti: str = Field(default="")
    yeni_gorunum_ozeti: str = Field(default="")
    react_kodu: str = Field(..., min_length=1)
    tailwind_siniflari: List[str] = Field(default_factory=list)
    hedef_dosya: str = Field(..., min_length=1)
    risk_seviyesi: str = Field(default="orta", pattern="^(dusuk|orta|yuksek)$")


class LinaDesignRequest(BaseModel):
    task_id: str = Field(..., min_length=5, max_length=50)
    talep: str = Field(..., min_length=5, max_length=4000)
    hedef_dosya_ipucu: str = Field(default="", max_length=300)
