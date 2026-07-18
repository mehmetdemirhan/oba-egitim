from pydantic import BaseModel, Field
from typing import Optional, List


class QueueIntegrateRequest(BaseModel):
    queue_id: str = Field(..., min_length=5, max_length=50, description="Entegre işaretlenecek kuyruk id'si")
    gelistirici_notu: str = Field(..., min_length=5, max_length=1000, description="Git commit SHA / Vercel deploy referansı")


class QueueItemResponse(BaseModel):
    queue_id: str
    task_id: str
    durum: str = Field(..., pattern="^(onaylandi_entegrasyon_bekliyor|entegre_edildi)$")
    hedef_dosya: str = ""
    react_kodu: str
    admin_gerekce: str
    guvenlik_uyarilari: List[str] = Field(default_factory=list)
    olusturma_tarihi: str
    entegrasyon_tarihi: Optional[str] = None
    gelistirici_notu: Optional[str] = None
