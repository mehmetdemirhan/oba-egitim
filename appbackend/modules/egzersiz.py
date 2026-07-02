"""Egzersiz puan sistemi endpoint'leri (/egzersiz/*).

server.py'dan birebir taşındı. Yollar ve davranış değişmedi.
"""
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException

from core.db import db
from core.auth import get_current_user

router = APIRouter()


# ── Egzersiz Puan Sistemi ──
@router.get("/egzersiz/puanlar")
async def get_egzersiz_puanlari():
    doc = await db.ayarlar.find_one({"tip": "egzersiz_puanlari"})
    if doc:
        doc.pop("_id", None)
        doc.pop("tip", None)
        return doc.get("puanlar", {})
    return {}

@router.post("/egzersiz/puan-ayarla")
async def set_egzersiz_puanlari(data: dict, current_user=Depends(get_current_user)):
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Yetki yok")
    puanlar = data.get("puanlar", {})
    await db.ayarlar.update_one(
        {"tip": "egzersiz_puanlari"},
        {"$set": {"tip": "egzersiz_puanlari", "puanlar": puanlar}},
        upsert=True
    )
    return {"message": "Puanlar kaydedildi"}

@router.post("/egzersiz/tamamla")
async def egzersiz_tamamla(data: dict, current_user=Depends(get_current_user)):
    kullanici_id = data.get("kullanici_id", current_user.get("id"))
    egzersiz_id = data.get("egzersiz_id", "")
    if not egzersiz_id:
        raise HTTPException(status_code=400, detail="Egzersiz ID gerekli")
    # Bugün zaten yaptı mı?
    bugun = datetime.utcnow().strftime("%Y-%m-%d")
    mevcut = await db.egzersiz_kayitlari.find_one({
        "kullanici_id": kullanici_id,
        "egzersiz_id": egzersiz_id,
        "tarih": bugun
    })
    if mevcut:
        raise HTTPException(status_code=409, detail="Bu egzersiz bugün zaten tamamlandı")
    # Puan hesapla
    ayar = await db.ayarlar.find_one({"tip": "egzersiz_puanlari"})
    puanlar = ayar.get("puanlar", {}) if ayar else {}
    kazanilan = puanlar.get(egzersiz_id, 2)  # varsayılan 2 puan (egzersiz XP tarifesi)
    # Kaydet
    await db.egzersiz_kayitlari.insert_one({
        "id": str(uuid.uuid4()),
        "kullanici_id": kullanici_id,
        "egzersiz_id": egzersiz_id,
        "tarih": bugun,
        "kazanilan_puan": kazanilan,
        "zaman": datetime.utcnow().isoformat()
    })
    # Kullanıcı puanını güncelle
    await db.users.update_one({"id": kullanici_id}, {"$inc": {"puan": kazanilan}})
    return {"kazanilan_puan": kazanilan, "egzersiz_id": egzersiz_id}
