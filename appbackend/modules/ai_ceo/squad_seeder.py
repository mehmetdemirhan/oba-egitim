"""AI Squad v1.4 — "İlk Kıvılcım": gerçek orkestratörü örnek bir talep ile tetikler.

DÜRÜSTLÜK: Bu uç SADECE gerçek pipeline_tetikle'yi çağırır (Atlas→Lina→Nova fiilen koşar, gerçek
raporlar + gerçek pipeline_run üretir). SAHTE veri ENJEKTE ETMEZ:
  - `ai_programmer_tasks`'e sahte 'canlida' Ayaz görevi YAZMAZ (deploy insan-onaylı; olmadan sayılmaz).
    Ayaz sayacı GERÇEK deploy olana dek dürüstçe 0/'—' kalır.
  - Var olmayan 'ai_squad_cryptographic_audit' + sahte 'hash-chain' iddiası YOK; denetim islem_kaydet.
Not: GEMINI yoksa Lina 'llm_gerekli' → pipeline 'durduruldu' (yine gerçek; uydurma yok). Uç
/ai/squad/seeder/atesle (yalnız admin)."""
import logging
import uuid

from fastapi import APIRouter, Depends

from core.auth import require_role, UserRole
from core.audit import islem_kaydet
from .squad_orkestrator import pipeline_tetikle
from .orkestrator_semalar import PipelineExecutionRequest

router = APIRouter()
_ADMIN = require_role(UserRole.ADMIN)

_ORNEK_TALEP = ("Öğrenci rapor ekranını mobil uyumlu, responsive grid yapısına göre güncelle. "
                "Admin RBAC vizesini zorunlu kıl.")
_ORNEK_KOD = "export default function RaporEkrani() { return <div className='grid grid-cols-1'>Rapor</div>; }"


@router.post("/ai/squad/seeder/atesle")
async def seeder_atesle(current_user=Depends(_ADMIN)):
    """Gerçek orkestrasyon akışını örnek bir kurumsal talep ile bir kez çalıştırır (canlı LLM çağrıları).
    Karne sayaçları bu GERÇEK akıştan dolar; sahte veri enjekte edilmez."""
    req = PipelineExecutionRequest(
        task_id=f"task_seed_{uuid.uuid4().hex[:6]}", talep_metni=_ORNEK_TALEP, baslangic_kodu=_ORNEK_KOD)
    logging.info(f"[squad_seeder] İlk kıvılcım: {req.task_id} orkestratöre veriliyor (gerçek motorlar).")
    sonuc = await pipeline_tetikle(req, current_user=current_user)  # gerçek Atlas→Lina→Nova
    await islem_kaydet(current_user, "ai_squad", "seeder_atesle", "pipeline_run", req.task_id, None, None, sonuc.get("asama"))
    return {
        "durum": "kivilcim_ateslendi",
        "task_id": req.task_id,
        "orkestrasyon_sonucu": sonuc,
        "not": ("Atlas/Lina/Nova sayaçları bu gerçek akıştan doldu. Ayaz sayacı, GERÇEK bir insan-onaylı "
                "deploy olana dek dürüstçe 0/'—' kalır — sahte 'canlida' görev yazılmadı."),
    }
