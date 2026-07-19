from pydantic import BaseModel, Field
from typing import Optional


class PipelineExecutionRequest(BaseModel):
    task_id: str = Field(..., min_length=5, max_length=50, description="Korelasyon/izlenebilirlik ID'si")
    talep_metni: str = Field(..., min_length=10, description="Geliştirilecek özellik/hata tanımı")
    baslangic_kodu: Optional[str] = Field(None, description="Refactor edilecek mevcut kaynak (varsa)")
    # FAZ 1 — Yaşam Döngüsü Zinciri korelasyonu: bu üretim hangi Ayda önerisinden/kararından doğdu.
    # Geriye dönük kayıtlarda boş kalabilir; zincir görünümü None'ı 'bağımsız üretim' sayar.
    kaynak_oneri_id: Optional[str] = Field(None, description="Zincir kaynağı (ai_ceo_oneriler.id veya karar id)")
