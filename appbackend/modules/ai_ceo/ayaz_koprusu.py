"""AI Squad v1.5 — İnsan-onaylı devir köprüsü (deploy_bekliyor → onaylı entegrasyon kuyruğu).

MİMARİ GERÇEK (dürüstlük): Orkestratör hattında Lina FRONTEND JSX üretir. Canlı frontend Vercel
(git-tabanlı) çalışır; mevcut Ayaz/patch_manager BACKEND modül deployer'ıdır ve bir dosyayı backend
sunucusunun diskine yazar — canlı Vercel frontend'ini DEPLOY ETMEZ. Bu yüzden 'Ayaz Lina'nın JSX'ini
otomatik canlıya alır' bu mimaride mümkün DEĞİLDİR; fiili frontend entegrasyonu MANUEL bir git+Vercel
adımıdır.

Bu köprü OTOMATİK DEPLOY YAPMAZ ve sahte Ayaz 'canlida' YAZMAZ. Yalnızca: admin deploy_bekliyor bir
pipeline'ı inceleyip ONAYLAR → Lina'nın GERÇEK JSX'i + gerekçe, yeniden güvenlik taranıp
squad_deploy_queue'ya (audit'li) mühürlenir; pipeline 'onaylandi_devir' olur. Bir geliştirici bu onaylı
kaydı manuel entegre eder. Uçlar /ai/squad/ayaz-kopru/*."""
import uuid

from fastapi import APIRouter, Depends, HTTPException

from core.db import db
from core.auth import require_role, UserRole
from core.zaman import iso
from core.audit import islem_kaydet
from core import patch_security
from .ayaz_kopru_semalar import DeployApprovalRequest, DeployApprovalResponse

router = APIRouter()
_ADMIN = require_role(UserRole.ADMIN)
_KOORD = require_role(UserRole.ADMIN, UserRole.COORDINATOR)


@router.post("/ai/squad/ayaz-kopru/onayla", response_model=DeployApprovalResponse)
async def deploy_onayla(govde: DeployApprovalRequest, current_user=Depends(_ADMIN)):
    """deploy_bekliyor pipeline'ı admin onayıyla entegrasyon kuyruğuna devreder. Otomatik deploy YOK."""
    tid = govde.task_id
    pipeline = await db.ai_squad_pipeline_runs.find_one({"task_id": tid})
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline kaydı bulunamadı.")
    if pipeline.get("asama") != "deploy_bekliyor":
        raise HTTPException(status_code=400, detail=f"Akış devre hazır değil (asama: {pipeline.get('asama')}).")

    lina = await db.ai_lina_reports.find_one({"task_id": tid, "durum": "tamam"}, sort=[("tarih", -1)])
    react_kodu = ((lina or {}).get("tasarim") or {}).get("react_kodu")
    if not react_kodu:
        raise HTTPException(status_code=422, detail="Lina 'tamam' kod çıktısı bulunamadı.")
    hedef_dosya = (lina.get("tasarim") or {}).get("hedef_dosya", "frontend/src/components/SquadPatch.jsx")

    # Devir öncesi GERÇEK yeniden güvenlik taraması (JSX)
    tarama = patch_security.scan_jsx_source(react_kodu, "kopru.jsx")

    kuyruk_id = f"dq_{uuid.uuid4().hex[:8]}"
    await db.squad_deploy_queue.insert_one({
        "id": kuyruk_id, "squad_task_id": tid, "hedef_dosya": hedef_dosya, "uretilen_kod": react_kodu,
        "guvenlik_uyarilari": tarama["warnings"], "admin_gerekce": govde.admin_gerekce,
        "durum": "onaylandi_entegrasyon_bekliyor", "onaylayan": current_user.get("id"), "tarih": iso(),
        # FAZ 1 — zincir korelasyonu: üretimi tetikleyen pipeline'dan taşınır (yoksa None).
        "kaynak_oneri_id": pipeline.get("kaynak_oneri_id"),
        "not": "FRONTEND entegrasyonu MANUEL (git+Vercel); backend patch_manager canlı frontend'i deploy etmez.",
    })
    await db.ai_squad_pipeline_runs.update_one({"task_id": tid}, {"$set": {
        "asama": "onaylandi_devir", "devir": {"kuyruk_id": kuyruk_id, "onaylayan": current_user.get("id")},
        "son_not": f"Admin onayladı → entegrasyon kuyruğuna devredildi ({kuyruk_id}). Otomatik deploy yok."}})
    await islem_kaydet(current_user, "ai_squad", "kopru_onayla", "pipeline_run", tid, "asama", "deploy_bekliyor", "onaylandi_devir")

    return DeployApprovalResponse(
        task_id=tid, durum="onaylandi_devir", kuyruk_id=kuyruk_id,
        mesaj=("Onaylandı ve entegrasyon kuyruğuna alındı. NOT: Frontend (Lina JSX) canlıya alma otomatik "
               "DEĞİL — bir geliştiricinin git commit + Vercel adımıyla manuel entegrasyonu gerekir."))


@router.get("/ai/squad/ayaz-kopru/kuyruk")
async def kopru_kuyruk(current_user=Depends(_KOORD)):
    items = await db.squad_deploy_queue.find({}, {"_id": 0}).sort("tarih", -1).to_list(length=200)
    return {"kuyruk": items}
