"""AI Squad v1.6 — Dağıtım Kuyruğu (squad_deploy_queue) görünürlük + manuel entegrasyon işaretleme.

Otomatik deploy YOK. squad_deploy_queue'daki (ayaz_koprusu'nun onayladığı) işleri listeler; bir
geliştirici kodu MANUEL git+Vercel'e entegre edip Git SHA/Vercel referansıyla 'entegre_edildi'
işaretler → pipeline 'tamamlandi' olur. Sahte 'kriptografik zincir' iddiası YOK; denetim islem_log.
Uçlar /ai/squad/deploy-queue/*."""
import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException

from core.db import db
from core.auth import require_role, UserRole
from core.zaman import iso
from core.audit import islem_kaydet
from .deploy_kuyruk_semalar import QueueIntegrateRequest, QueueItemResponse

router = APIRouter()
_KOORD = require_role(UserRole.ADMIN, UserRole.COORDINATOR)
_ADMIN = require_role(UserRole.ADMIN)


def _map(item: dict) -> QueueItemResponse:
    return QueueItemResponse(
        queue_id=item.get("id", ""), task_id=item.get("squad_task_id", ""), durum=item.get("durum", "onaylandi_entegrasyon_bekliyor"),
        hedef_dosya=item.get("hedef_dosya", ""), react_kodu=item.get("uretilen_kod", ""), admin_gerekce=item.get("admin_gerekce", ""),
        guvenlik_uyarilari=item.get("guvenlik_uyarilari", []), olusturma_tarihi=item.get("tarih", ""),
        entegrasyon_tarihi=item.get("entegrasyon_tarihi"), gelistirici_notu=item.get("gelistirici_notu"))


@router.get("/ai/squad/deploy-queue/listele", response_model=List[QueueItemResponse])
async def deploy_queue_listele(current_user=Depends(_KOORD)):
    """Canlı squad_deploy_queue'yu listeler (uydurma yok; boşsa boş liste)."""
    items = await db.squad_deploy_queue.find({}).sort("tarih", -1).to_list(length=200)
    return [_map(i) for i in items]


@router.post("/ai/squad/deploy-queue/entegre-et")
async def deploy_queue_entegre_et(govde: QueueIntegrateRequest, current_user=Depends(_ADMIN)):
    """Geliştirici manuel Git/Vercel entegrasyonunu tamamladığında durumu mühürler. Otomatik deploy YOK."""
    item = await db.squad_deploy_queue.find_one({"id": govde.queue_id})
    if not item:
        raise HTTPException(status_code=404, detail="Kuyruk öğesi bulunamadı.")
    if item.get("durum") == "entegre_edildi":
        raise HTTPException(status_code=400, detail="Bu öğe zaten entegre edilmiş.")
    try:
        await db.squad_deploy_queue.update_one({"id": govde.queue_id}, {"$set": {
            "durum": "entegre_edildi", "entegrasyon_tarihi": iso(), "gelistirici_notu": govde.gelistirici_notu,
            "entegre_eden": current_user.get("id")}})
        await db.ai_squad_pipeline_runs.update_one({"task_id": item.get("squad_task_id")}, {"$set": {
            "asama": "tamamlandi", "son_not": f"Geliştirici manuel Git/Vercel entegrasyonunu tamamladı: {govde.gelistirici_notu[:120]}"}})
        await islem_kaydet(current_user, "ai_squad", "kuyruk_entegre", "deploy_queue", govde.queue_id, "durum", "onaylandi_entegrasyon_bekliyor", "entegre_edildi")
        return {"durum": "entegre_edildi", "queue_id": govde.queue_id, "mesaj": "Manuel entegrasyon tamamlandı olarak mühürlendi."}
    except HTTPException:
        raise
    except Exception as e:
        logging.exception(f"[deploy_kuyrugu] durum güncellenemedi: {e}")
        raise HTTPException(status_code=500, detail="Kuyruk durumu güncellenemedi.")
