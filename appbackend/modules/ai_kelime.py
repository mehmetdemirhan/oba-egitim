"""AI kelime evrimi modülü (/ai/kelime-evrimi/*).

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
)
from core.ai import _gemini_call, call_claude, _mock_bilgi_tabani_response, get_ogrenci_ai_verileri

router = APIRouter()


@router.get("/ai/kelime-evrimi/{ogrenci_id}")
async def kelime_evrimi_listesi(ogrenci_id: str, current_user=Depends(get_current_user)):
    """Öğrencinin kelime tekrar programı — bugün tekrar edilmesi gerekenler."""
    simdi = datetime.utcnow()
    # Bugün veya geçmiş tarihli tekrar bekleyenler
    bekleyenler = await db.kelime_tekrar.find({
        "ogrenci_id": ogrenci_id,
        "sonraki_gosterim": {"$lte": simdi.isoformat()}
    }).sort("sonraki_gosterim", 1).to_list(length=20)

    for k in bekleyenler:
        k.pop("_id", None)

    # İstatistik
    toplam = await db.kelime_tekrar.count_documents({"ogrenci_id": ogrenci_id})
    ogrenilmis = await db.kelime_tekrar.count_documents({"ogrenci_id": ogrenci_id, "kutu": {"$gte": 4}})

    return {"bekleyenler": bekleyenler, "toplam": toplam, "ogrenilmis": ogrenilmis, "bugun_tekrar": len(bekleyenler)}


@router.post("/ai/kelime-evrimi/cevapla")
async def kelime_evrimi_cevapla(payload: dict, current_user=Depends(get_current_user)):
    """Kelime tekrarına doğru/yanlış cevap — Leitner Box algoritması."""
    kelime_id = payload.get("kelime_id", "")
    dogru = payload.get("dogru", False)
    ogrenci_id = current_user["id"]

    kayit = await db.kelime_tekrar.find_one({"id": kelime_id, "ogrenci_id": ogrenci_id})
    if not kayit:
        raise HTTPException(status_code=404, detail="Kelime kaydı bulunamadı")

    mevcut_kutu = kayit.get("kutu", 1)
    simdi = datetime.utcnow()

    # Yaş bazlı aralıklar
    sinif = kayit.get("sinif", 3)
    if sinif <= 2:  # 6-8 yaş
        araliklar = {1: 1, 2: 2, 3: 5, 4: 12, 5: 30}
    elif sinif <= 5:  # 9-11 yaş
        araliklar = {1: 1, 2: 3, 3: 7, 4: 21, 5: 45}
    else:  # 12+ yaş
        araliklar = {1: 1, 2: 3, 3: 7, 4: 30, 5: 60}

    if dogru:
        yeni_kutu = min(5, mevcut_kutu + 1)
        xp = 2
    else:
        yeni_kutu = 1  # Yanlış → ilk kutuya geri
        xp = 1

    sonraki_gun = araliklar.get(yeni_kutu, 7)
    sonraki = (simdi + timedelta(days=sonraki_gun)).isoformat()

    await db.kelime_tekrar.update_one({"id": kelime_id}, {"$set": {
        "kutu": yeni_kutu,
        "son_gosterim": simdi.isoformat(),
        "sonraki_gosterim": sonraki,
        "tekrar_sayisi": kayit.get("tekrar_sayisi", 0) + 1,
        "dogru_sayisi": kayit.get("dogru_sayisi", 0) + (1 if dogru else 0),
    }})

    # XP
    try:
        await db.users.update_one({"id": ogrenci_id}, {"$inc": {"toplam_xp": xp}})
    except:
        pass

    return {"dogru": dogru, "yeni_kutu": yeni_kutu, "sonraki_gun": sonraki_gun, "xp": xp}


@router.post("/ai/kelime-evrimi/ekle")
async def kelime_evrimi_ekle(payload: dict, current_user=Depends(get_current_user)):
    """Öğrenciye kelime tekrar programına kelime ekler."""
    ogrenci_id = payload.get("ogrenci_id", current_user["id"])
    kelimeler = payload.get("kelimeler", [])  # [{"kelime": "...", "anlam": "...", "sinif": 3}]

    eklenen = 0
    for k in kelimeler[:20]:  # max 20 kelime bir seferde
        mevcut = await db.kelime_tekrar.find_one({"ogrenci_id": ogrenci_id, "kelime": k.get("kelime", "").lower()})
        if not mevcut:
            await db.kelime_tekrar.insert_one({
                "id": str(uuid.uuid4()),
                "ogrenci_id": ogrenci_id,
                "kelime": k.get("kelime", "").lower(),
                "anlam": k.get("anlam", ""),
                "ornek_cumle": k.get("ornek_cumle", ""),
                "sinif": k.get("sinif", 3),
                "kutu": 1,
                "tekrar_sayisi": 0,
                "dogru_sayisi": 0,
                "son_gosterim": None,
                "sonraki_gosterim": datetime.utcnow().isoformat(),
                "tarih": datetime.utcnow().isoformat(),
            })
            eklenen += 1

    return {"eklenen": eklenen, "toplam_gonderilen": len(kelimeler)}
