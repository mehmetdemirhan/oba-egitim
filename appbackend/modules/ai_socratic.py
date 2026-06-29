"""AI sokratik diyalog modülü (/ai/socratic-soru, /ai/socratic-cevap, /ai/socratic-log).

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


@router.get("/ai/socratic-log")
async def ai_socratic_log_listesi(current_user=Depends(get_current_user)):
    """Socratic Reading loglarını listeler."""
    loglar = await db.ai_socratic_log.find({}).sort("tarih", -1).to_list(length=100)
    for l in loglar:
        l.pop("_id", None)
    # Öğrenci adlarını ekle
    for l in loglar:
        ogr = await db.users.find_one({"id": l.get("ogrenci_id", "")})
        if not ogr:
            ogr = await db.students.find_one({"id": l.get("ogrenci_id", "")})
        l["ogrenci_ad"] = f"{ogr.get('ad', '')} {ogr.get('soyad', '')}" if ogr else "Bilinmiyor"
    return loglar


@router.post("/ai/socratic-soru")
async def ai_socratic_soru(payload: dict, current_user=Depends(get_current_user)):
    """Okuma kaydı sonrası Sokratik soru üretir."""
    kitap_adi = payload.get("kitap_adi", "")
    bolum = payload.get("bolum", "")
    sure_dk = payload.get("sure_dk", 10)
    sinif = payload.get("sinif", 3)

    prompt = f"""Kitap: {kitap_adi or 'bilinmiyor'}
Bölüm: {bolum or 'bilinmiyor'}
Sınıf: {sinif}
Okuma süresi: {sure_dk} dk

Bu öğrenci az önce okuma yaptı. Okuduğu hakkında düşünmesini sağlayacak 1 Sokratik soru sor.
Soru kısa, merak uyandırıcı ve Türkçe olsun. Çocuğa uygun dil kullan.
SADECE JSON döndür: {{"soru": "...", "ipucu": "...", "bloom": "kavrama|analiz|sentez|degerlendirme"}}"""

    result = await call_claude(
        "Sen çocuklara Sokratik sorular soran sevecen bir okuma koçusun. Düşünmeye teşvik edersin.",
        prompt, model="haiku", max_tokens=200
    )

    if result.get("parsed"):
        soru_data = result["parsed"]
    else:
        soru_data = {"soru": f"Az önce okuduğun bölümde en çok ne dikkatini çekti?", "ipucu": "Karakterlerin davranışlarını düşün", "bloom": "kavrama"}

    # Log
    await db.ai_socratic_log.insert_one({
        "id": str(uuid.uuid4()),
        "ogrenci_id": current_user["id"],
        "kitap_adi": kitap_adi,
        "bolum": bolum,
        "soru": soru_data.get("soru", ""),
        "bloom": soru_data.get("bloom", "kavrama"),
        "tarih": datetime.utcnow().isoformat(),
    })

    return soru_data


@router.post("/ai/socratic-cevap")
async def ai_socratic_cevap(payload: dict, current_user=Depends(get_current_user)):
    """Öğrencinin Sokratik soruya verdiği cevabı değerlendirir."""
    soru = payload.get("soru", "")
    cevap = payload.get("cevap", "")

    if len(cevap) < 5:
        return {"puan": 1, "geri_bildirim": "Biraz daha düşünüp detaylı cevap vermeyi dener misin? 🤔", "xp": 2}

    prompt = f"""Soru: {soru}
Öğrenci cevabı: {cevap}

Bu cevabı 1-5 arası puanla. Kısa, pozitif geri bildirim ver. Türkçe. Çocuğa uygun.
SADECE JSON: {{"puan": 1-5, "geri_bildirim": "..."}}"""

    result = await call_claude("Sen yapıcı geri bildirim veren bir okuma koçusun.", prompt, model="haiku", max_tokens=150)

    if result.get("parsed"):
        r = result["parsed"]
        puan = min(5, max(1, r.get("puan", 3)))
        geri = r.get("geri_bildirim", "Güzel düşünmüşsün! 👏")
    else:
        puan = 3
        geri = "Düşüncelerini paylaştığın için teşekkürler! 👏"

    xp = {1: 2, 2: 3, 3: 5, 4: 7, 5: 10}.get(puan, 5)

    # XP ver
    try:
        await db.users.update_one({"id": current_user["id"]}, {"$inc": {"toplam_xp": xp}})
    except:
        pass

    return {"puan": puan, "geri_bildirim": geri, "xp": xp}
