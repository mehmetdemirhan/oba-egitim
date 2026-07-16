"""AI CEO — Hedef takibi (gauge). Admin hedef koyar; her fotoğrafta ilerleme + sapma.

AI YOK — deterministik. Sapma neden analizi Ayda raporlarında bağlanır (opsiyonel).
"""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from core.db import db
from core.auth import require_role, UserRole

from .fotograf import son_fotograf
from .ortak import metrik_al

router = APIRouter()
_ADMIN = require_role(UserRole.ADMIN, UserRole.COORDINATOR)

# Hedef tipi → fotoğraftaki güncel değer yolu
HEDEF_METRIK = {
    "kur_satisi": None,  # dönem içi satış — özel hesap (aşağıda)
    "yenileme_orani": "ogretmen.yenileme_orani_yuzde",
    "tahsilat": "muhasebe.tahsil_edilen",
    "aktif_ogrenci": "ogrenci.aktif",
    "veli_memnuniyeti": "ogretmen.veli_memnuniyeti_5uzerinden",
}


def _guncel_deger(tip: str, fotograf: dict):
    yol = HEDEF_METRIK.get(tip)
    if yol:
        return metrik_al(fotograf, yol)
    if tip == "kur_satisi":
        # Bu ay satılan kur ~ son ay tahsilat trendindeki hareket yerine kayıt sayısı yaklaşımı
        env = metrik_al(fotograf, "envanter.koleksiyonlar", {}) or {}
        ku = env.get("kur_ucretleri") or {}
        return ku.get("son_30gun")
    return None


def _gauge(guncel, hedef) -> dict:
    try:
        g = float(guncel); h = float(hedef)
        oran = round(min(100.0, max(0.0, g * 100 / h)), 1) if h else 0.0
        return {"guncel": g, "hedef": h, "ilerleme_yuzde": oran, "sapma": round(g - h, 2),
                "durum": "ulasildi" if g >= h else ("yolda" if oran >= 60 else "geride")}
    except (TypeError, ValueError):
        return {"guncel": guncel, "hedef": hedef, "ilerleme_yuzde": None, "sapma": None, "durum": "olcumsuz"}


@router.post("/ai/ceo/hedef")
async def hedef_ekle(govde: dict, current_user=Depends(_ADMIN)):
    tip = govde.get("tip")
    if tip not in HEDEF_METRIK:
        raise HTTPException(status_code=400, detail=f"Geçersiz tip. Seçenekler: {list(HEDEF_METRIK)}")
    try:
        hedef_deger = float(govde.get("hedef_deger"))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="hedef_deger sayısal olmalı")
    kayit = {
        "id": str(uuid.uuid4()),
        "ad": str(govde.get("ad", tip))[:120],
        "tip": tip,
        "hedef_deger": hedef_deger,
        "donem": str(govde.get("donem", ""))[:20],
        "aktif": True,
        "tarih": datetime.now(timezone.utc).isoformat(),
    }
    await db.ai_ceo_hedefler.insert_one({**kayit})
    kayit.pop("_id", None)
    return {"ok": True, "hedef": kayit}


@router.get("/ai/ceo/hedefler")
async def hedef_listesi(current_user=Depends(_ADMIN)):
    foto = await son_fotograf()
    hedefler = await db.ai_ceo_hedefler.find({"aktif": True}, {"_id": 0}).sort("tarih", -1).to_list(length=100)
    for h in hedefler:
        h["gauge"] = _gauge(_guncel_deger(h["tip"], foto or {}), h["hedef_deger"])
    return {"hedefler": hedefler, "fotograf_tarih": foto.get("tarih") if foto else None}


@router.delete("/ai/ceo/hedef/{hedef_id}")
async def hedef_sil(hedef_id: str, current_user=Depends(_ADMIN)):
    await db.ai_ceo_hedefler.update_one({"id": hedef_id}, {"$set": {"aktif": False}})
    return {"ok": True}
