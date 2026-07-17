"""AI CEO — Stratejik Vizyon: Üç Aylık Stratejik Plan.

3-5 ölçülebilir hedef, gerekçeli. Admin düzenler/onaylar; onaylı plan sonraki analizlerde
REFERANS olur ("bu öneri Hedef 2'ye hizmet eder"). Ayda yönetir ama KARAR VERMEZ — plan
onayı admin'e aittir; onaysız uygulama yok (API guard).
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException

from core.db import db
from core.auth import require_role, UserRole
from core.zaman import iso

router = APIRouter()
_ADMIN = require_role(UserRole.ADMIN, UserRole.COORDINATOR)


async def onayli_plan() -> dict | None:
    """Sonraki analizlere referans olacak en güncel ONAYLI plan."""
    return await db.ai_ceo_planlar.find_one({"durum": "onayli"}, {"_id": 0}, sort=[("onay_tarih", -1)])


@router.post("/ai/ceo/plan")
async def plan_ekle(govde: dict, current_user=Depends(_ADMIN)):
    hedefler = govde.get("hedefler") or []
    if not isinstance(hedefler, list) or not (3 <= len(hedefler) <= 5):
        raise HTTPException(status_code=400, detail="Plan 3-5 ölçülebilir hedef içermeli")
    kayit = {
        "id": str(uuid.uuid4()),
        "baslik": str(govde.get("baslik", "Üç Aylık Stratejik Plan"))[:200],
        "donem": str(govde.get("donem", ""))[:20],
        "gerekce": str(govde.get("gerekce", ""))[:2000],
        "hedefler": [{"ad": str(h.get("ad", ""))[:200], "metrik": str(h.get("metrik", ""))[:80],
                      "mevcut": h.get("mevcut"), "hedef": h.get("hedef")} for h in hedefler][:5],
        "durum": "taslak",   # taslak | onayli
        "tarih": iso(),
    }
    await db.ai_ceo_planlar.insert_one({**kayit})
    kayit.pop("_id", None)
    return {"ok": True, "plan": kayit}


@router.put("/ai/ceo/plan/{plan_id}")
async def plan_duzenle(plan_id: str, govde: dict, current_user=Depends(_ADMIN)):
    guncelle = {}
    for alan in ("baslik", "donem", "gerekce"):
        if alan in govde:
            guncelle[alan] = str(govde[alan])[:2000]
    if "hedefler" in govde and isinstance(govde["hedefler"], list):
        guncelle["hedefler"] = govde["hedefler"][:5]
    # Onaylı plan düzenlenemez (yeniden onay gerekir)
    r = await db.ai_ceo_planlar.update_one({"id": plan_id, "durum": "taslak"}, {"$set": guncelle})
    if r.matched_count == 0:
        raise HTTPException(status_code=404, detail="Taslak plan bulunamadı (onaylı olabilir)")
    return {"ok": True}


@router.post("/ai/ceo/plan/{plan_id}/onayla")
async def plan_onayla(plan_id: str, current_user=Depends(_ADMIN)):
    p = await db.ai_ceo_planlar.find_one({"id": plan_id})
    if not p:
        raise HTTPException(status_code=404, detail="Plan bulunamadı")
    if p.get("durum") == "onayli":
        return {"ok": True, "zaten_onayli": True}
    await db.ai_ceo_planlar.update_one({"id": plan_id}, {"$set": {
        "durum": "onayli", "onaylayan": current_user.get("id"), "onay_tarih": iso()}})
    # Yönetim skoru: plan onayı puanı
    try:
        from .yonetim import puan_kaydet
        await puan_kaydet(current_user.get("id"), "plan_onaylandi", "", plan_id)
    except Exception:
        pass
    return {"ok": True, "onaylandi": True}


@router.get("/ai/ceo/planlar")
async def planlar(current_user=Depends(_ADMIN)):
    docs = await db.ai_ceo_planlar.find({}, {"_id": 0}).sort("tarih", -1).to_list(length=100)
    return {"planlar": docs}
