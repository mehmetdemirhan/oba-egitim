"""Mesajlaşma sistemi endpoint'leri (/mesajlar/*) ve modelleri.

server.py'dan birebir taşındı. Yollar ve davranış değişmedi.
Bildirim üretimi için modules.bildirim.bildirim_olustur kullanılır.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core.db import db
from core.auth import get_current_user
from core.zaman import iso
from modules.bildirim import bildirim_olustur

router = APIRouter()


class MesajCreate(BaseModel):
    alici_id: str
    alici_tip: str = ""  # user id veya teacher/student ref
    icerik: str
    konu: str = ""

class MesajModel(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    gonderen_id: str
    gonderen_ad: str = ""
    gonderen_rol: str = ""
    alici_id: str
    alici_ad: str = ""
    alici_rol: str = ""
    konu: str = ""
    icerik: str
    okundu: bool = False
    arsiv: bool = False   # alıcı okunmuş mesajı arşivleyebilir (gelen kutusundan gizlenir, silinmez)
    tarih: str = Field(default_factory=iso)


@router.post("/mesajlar")
async def create_mesaj(mesaj: MesajCreate, current_user=Depends(get_current_user)):
    gonderen_ad = f"{current_user.get('ad', '')} {current_user.get('soyad', '')}".strip()
    gonderen_rol = current_user.get("role", "")

    # Alıcı bilgisini bul
    alici = await db.users.find_one({"id": mesaj.alici_id})
    alici_ad = ""
    alici_rol = ""
    if alici:
        alici_ad = f"{alici.get('ad', '')} {alici.get('soyad', '')}".strip()
        alici_rol = alici.get("role", "")

    model = MesajModel(
        gonderen_id=current_user["id"],
        gonderen_ad=gonderen_ad,
        gonderen_rol=gonderen_rol,
        alici_id=mesaj.alici_id,
        alici_ad=alici_ad,
        alici_rol=alici_rol,
        konu=mesaj.konu,
        icerik=mesaj.icerik,
    )
    data = model.dict()
    await db.mesajlar.insert_one(data)
    # Bildirim gönder
    try: await bildirim_olustur(data.get("alici_id"), "mesaj_geldi", f"{data.get('gonderen_ad', '')} size mesaj gönderdi: {data.get('konu', '')}")
    except: pass
    return data


@router.get("/mesajlar")
async def get_mesajlar(current_user=Depends(get_current_user)):
    user_id = current_user["id"]
    mesajlar = await db.mesajlar.find({
        "$or": [{"gonderen_id": user_id}, {"alici_id": user_id}]
    }).sort("tarih", -1).to_list(length=None)
    for m in mesajlar:
        m.pop("_id", None)
    return mesajlar


@router.put("/mesajlar/{mesaj_id}/okundu")
async def mesaj_okundu(mesaj_id: str, current_user=Depends(get_current_user)):
    await db.mesajlar.update_one({"id": mesaj_id, "alici_id": current_user["id"]}, {"$set": {"okundu": True}})
    return {"ok": True}


class ArsivIstek(BaseModel):
    arsiv: bool = True


@router.put("/mesajlar/{mesaj_id}/arsiv")
async def mesaj_arsivle(mesaj_id: str, istek: ArsivIstek = ArsivIstek(), current_user=Depends(get_current_user)):
    """Alıcı, gelen kutusundaki bir mesajı arşivler (arsiv=True) veya geri alır (arsiv=False).
    Mesaj silinmez; yalnız gelen kutusundan gizlenip Arşiv görünümüne taşınır."""
    sonuc = await db.mesajlar.update_one(
        {"id": mesaj_id, "alici_id": current_user["id"]},
        {"$set": {"arsiv": bool(istek.arsiv)}},
    )
    if sonuc.matched_count == 0:
        raise HTTPException(status_code=404, detail="Mesaj bulunamadı veya arşivleme yetkiniz yok")
    return {"ok": True, "arsiv": bool(istek.arsiv)}


@router.get("/mesajlar/okunmamis-sayisi")
async def okunmamis_sayisi(current_user=Depends(get_current_user)):
    # Arşivlenmiş mesajlar okunmamış sayısına dahil edilmez.
    sayi = await db.mesajlar.count_documents(
        {"alici_id": current_user["id"], "okundu": False, "arsiv": {"$ne": True}}
    )
    return {"sayi": sayi}
