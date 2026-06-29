"""Örnek modül — yama sistemi referansı.

Kurallar:
- `router = APIRouter()` tanımla, endpoint'leri @router ile ekle.
- DB/auth/ayar erişimini YALNIZCA core üzerinden yap (from core.db import db,
  from core.auth import get_current_user, ...). server.py'den import ETME.
- os.system/subprocess/eval/exec, dosya silme, socket/urllib YASAK (güvenlik
  taraması reddeder). API çağrısı gerekiyorsa core.ai kullan.
"""
from fastapi import APIRouter, Depends

from core.db import db
from core.auth import get_current_user

router = APIRouter()


@router.get("/ornek/selam")
async def selam():
    return {"mesaj": "Merhaba! Örnek modül çalışıyor.", "surum": "1.0.0"}


@router.get("/ornek/profilim")
async def profilim(current_user=Depends(get_current_user)):
    return {"ad": current_user.get("ad", ""), "rol": current_user.get("role", "")}
