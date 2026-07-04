"""Sistem ayarları modülü (/ayarlar/*, /ayarlar/puanlar, /ayarlar/ozellikler, /ayarlar/{tip}).

server.py'dan BİREBİR taşındı; yollar ve davranış değişmedi. AI çağrıları
core.ai üzerinden yapılır; modül DB/auth/ayar erişimini yalnızca core'dan alır.
"""
import os
import io
import re
import json
import base64
import uuid
import asyncio
import logging
import random
import math
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Body, UploadFile, File, Form
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field

from core.db import db, prepare_for_mongo, parse_from_mongo
from core.auth import get_current_user, require_role, UserRole
from core.config import (
    GEMINI_API_KEY, GEMINI_API_KEY_2, GEMINI_API_KEY_3, GEMINI_MODELS,
    AI_MODEL, AI_DEFAULT_MODEL, AI_HAIKU_MODEL, AI_MAX_DAILY_REQUESTS,
    AI_CACHE_HOURS, YANDEX_DISK_TOKEN, ANTHROPIC_API_KEY,
)
from core.sistem import (
    get_xp_tablosu, get_puan_ayarlari, get_lig_esikleri,
    XP_TABLOSU_DEFAULT, LIG_ESIKLERI_DEFAULT, LIG_SIRA,
    OGRETMEN_ROZETLERI_DEFAULT, OGRENCI_ROZETLERI_DEFAULT, ANKET_SORULARI_DEFAULT,
    OZELLIK_TANIMLARI, get_ozellik_ayarlari, OGRETMEN_PUAN_AGIRLIKLARI_DEFAULT,
)
from core.ai import _gemini_call, call_claude, _mock_bilgi_tabani_response, get_ogrenci_ai_verileri

router = APIRouter()


@router.get("/ayarlar/puanlar")
async def get_puanlar(current_user=Depends(get_current_user)):
    return await get_puan_ayarlari()


@router.put("/ayarlar/puanlar")
async def update_puanlar(data: dict = Body(...), current_user=Depends(require_role(UserRole.ADMIN, UserRole.COORDINATOR))):
    await db.sistem_ayarlari.update_one(
        {"tip": "puan_ayarlari"},
        {"$set": {"tip": "puan_ayarlari", "puanlar": data}},
        upsert=True
    )
    return {"message": "Puan ayarları güncellendi", "puanlar": data}


# ÖNEMLİ: /ayarlar/ozellikler, /ayarlar/{tip}'den ÖNCE tanımlanmalı
@router.get("/ayarlar/ozellikler")
async def get_ozellik_ayarlari_public():
    doc = await db.sistem_ayarlari.find_one({"tip": "ozellik_ayarlari"})
    varsayilan = {f["id"]: {"aktif": True, "roller": {"ogretmen": True, "ogrenci": True, "veli": True}} for f in OZELLIK_TANIMLARI}
    ayarlar = doc.get("degerler", varsayilan) if doc else varsayilan
    for f in OZELLIK_TANIMLARI:
        if f["id"] not in ayarlar:
            ayarlar[f["id"]] = {"aktif": True, "roller": {"ogretmen": True, "ogrenci": True, "veli": True}}
    return {"tanimlar": OZELLIK_TANIMLARI, "ayarlar": ayarlar}


@router.get("/ayarlar/{tip}")
async def get_ayar(tip: str, current_user=Depends(get_current_user)):
    doc = await db.sistem_ayarlari.find_one({"tip": tip})
    if doc:
        doc.pop("_id", None)
        return doc
    # Varsayılan değerleri döndür
    defaults = {
        "xp_tablosu": XP_TABLOSU_DEFAULT,
        "lig_esikleri": LIG_ESIKLERI_DEFAULT,
        "ogretmen_rozetleri": OGRETMEN_ROZETLERI_DEFAULT,
        "ogrenci_rozetleri": OGRENCI_ROZETLERI_DEFAULT,
        "anket_sorulari": ANKET_SORULARI_DEFAULT,
        "ogretmen_puan_agirliklari": OGRETMEN_PUAN_AGIRLIKLARI_DEFAULT,
    }
    return {"tip": tip, "degerler": defaults.get(tip, {})}


@router.put("/ayarlar/{tip}")
async def update_ayar(tip: str, payload: dict, current_user=Depends(get_current_user)):
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Sadece admin ayar değiştirebilir")
    degerler = payload.get("degerler", {})
    await db.sistem_ayarlari.update_one(
        {"tip": tip},
        {"$set": {"tip": tip, "degerler": degerler, "guncelleme_tarihi": datetime.utcnow().isoformat(), "guncelleyen": current_user.get("ad", "")}},
        upsert=True
    )
    return {"ok": True, "tip": tip}


@router.get("/ayarlar")
async def get_tum_ayarlar(current_user=Depends(get_current_user)):
    if current_user.get("role") not in ["admin", "coordinator"]:
        raise HTTPException(status_code=403, detail="Yetkisiz")
    ayarlar = await db.sistem_ayarlari.find().to_list(length=None)
    for a in ayarlar:
        a.pop("_id", None)
    return ayarlar


@router.get("/ayarlar/ozellikler")
async def get_ozellik_ayarlari_endpoint():
    ayarlar = await get_ozellik_ayarlari()
    return {"tanimlar": OZELLIK_TANIMLARI, "ayarlar": ayarlar}


@router.put("/ayarlar/ozellikler")
async def update_ozellik_ayarlari(
    payload: dict = Body(...),
    current_user=Depends(require_role(UserRole.ADMIN, UserRole.COORDINATOR))
):
    ayarlar = payload.get("ayarlar", {})
    gecerli_idler = {f["id"] for f in OZELLIK_TANIMLARI}
    temiz = {k: v for k, v in ayarlar.items() if k in gecerli_idler}
    await db.sistem_ayarlari.update_one(
        {"tip": "ozellik_ayarlari"},
        {"$set": {
            "tip": "ozellik_ayarlari",
            "degerler": temiz,
            "guncelleme_tarihi": datetime.utcnow().isoformat(),
            "guncelleyen": f"{current_user.get('ad', '')} {current_user.get('soyad', '')}".strip()
        }},
        upsert=True
    )
    return {"ok": True, "guncellenen": len(temiz)}
