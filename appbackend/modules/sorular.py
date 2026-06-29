"""Soru CRUD modülü (/sorular/*).

server.py'dan BİREBİR taşındı; yollar ve davranış değişmedi. Klasik `sorular`
koleksiyonu üzerinde çalışır (kitap havuzu soruları modules/kitap.py'dedir).
"""
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from core.db import db
from core.auth import get_current_user

router = APIRouter()


class SoruCreate(BaseModel):
    kitap_id: str
    bolum: int = 1
    soru_metni: str
    secenekler: list = []
    dogru_cevap: int = 0

@router.post("/sorular")
async def soru_ekle(data: SoruCreate, current_user=Depends(get_current_user)):
    soru = {
        "id": str(uuid.uuid4()),
        "kitap_id": data.kitap_id,
        "bolum": data.bolum,
        "soru_metni": data.soru_metni,
        "secenekler": data.secenekler,
        "dogru_cevap": data.dogru_cevap,
        "ekleyen_id": current_user["id"],
        "ekleyen_ad": f"{current_user.get('ad','')} {current_user.get('soyad','')}".strip(),
        "kullanim_sayisi": 0,
        "olusturma_tarihi": datetime.utcnow().isoformat(),
    }
    await db.sorular.insert_one(soru)
    soru.pop("_id", None)
    return soru

@router.get("/sorular/{kitap_id}")
async def soru_listele(kitap_id: str, bolum: int = None, current_user=Depends(get_current_user)):
    filtre = {"kitap_id": kitap_id}
    if bolum is not None:
        filtre["bolum"] = bolum
    sorular = await db.sorular.find(filtre).sort("bolum", 1).to_list(length=None)
    for s in sorular:
        s.pop("_id", None)
    return sorular

@router.put("/sorular/{soru_id}")
async def soru_guncelle(soru_id: str, data: dict, current_user=Depends(get_current_user)):
    update = {k: v for k, v in data.items() if k in ("soru_metni", "secenekler", "dogru_cevap", "bolum")}
    if update:
        await db.sorular.update_one({"id": soru_id}, {"$set": update})
    return {"message": "Güncellendi"}

@router.delete("/sorular/{soru_id}")
async def soru_sil(soru_id: str, current_user=Depends(get_current_user)):
    await db.sorular.delete_one({"id": soru_id})
    return {"message": "Silindi"}
