"""Admin bakım/debug modülü (/admin/fix-ids, /admin/gemini-*, /admin/debug-*).

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


# ── Migration / Debug Endpoint ──
@router.post("/admin/fix-ids")
async def fix_missing_ids(current_user=Depends(require_role(UserRole.ADMIN))):
    """Eksik id alanlarını düzelt"""
    fixed = 0
    # analiz_metinler
    async for doc in db.analiz_metinler.find({"id": {"$exists": False}}):
        new_id = str(uuid.uuid4())
        await db.analiz_metinler.update_one({"_id": doc["_id"]}, {"$set": {"id": new_id}})
        fixed += 1
    # analiz_metinler - durum alanı yoksa ekle
    await db.analiz_metinler.update_many({"durum": {"$exists": False}}, {"$set": {"durum": "havuzda"}})
    # diagnostic_oturumlar
    async for doc in db.diagnostic_oturumlar.find({"id": {"$exists": False}}):
        await db.diagnostic_oturumlar.update_one({"_id": doc["_id"]}, {"$set": {"id": str(uuid.uuid4())}})
    return {"fixed": fixed, "message": "ID düzeltme tamamlandı"}


@router.get("/admin/gemini-test")
async def gemini_test(current_user=Depends(require_role(UserRole.ADMIN))):
    """Gemini API bağlantısını test et — sadece admin."""
    key = GEMINI_API_KEY
    if not key:
        return {"durum": "HATA", "sebep": "GEMINI_API_KEY environment variable tanımlı değil", "key_uzunluk": 0}
    try:
        yanit = await _gemini_call("Merhaba! Sadece 'Gemini çalışıyor' yaz.", max_tokens=50)
        return {"durum": "OK", "yanit": yanit, "key_uzunluk": len(key), "model": AI_MODEL}
    except Exception as e:
        return {"durum": "HATA", "sebep": str(e), "key_uzunluk": len(key), "model": AI_MODEL}


@router.get("/admin/gemini-modeller")
async def gemini_modeller():
    """Kullanılabilir Gemini modellerini listele — geçici public."""
    key = GEMINI_API_KEY
    if not key:
        return {"hata": "API key yok"}
    try:
        async with httpx.AsyncClient(timeout=15.0) as c:
            r = await c.get(f"https://generativelanguage.googleapis.com/v1beta/models?key={key}")
            data = r.json()
        modeller = []
        for m in data.get("models", []):
            if "generateContent" in m.get("supportedGenerationMethods", []):
                modeller.append(m.get("name", "").replace("models/", ""))
        return {"modeller": modeller, "toplam": len(modeller)}
    except Exception as e:
        return {"hata": str(e)}


@router.get("/admin/debug-metinler")
async def debug_metinler(current_user=Depends(require_role(UserRole.ADMIN))):
    """Tüm metinleri ham haliyle göster"""
    items = await db.analiz_metinler.find().to_list(length=None)
    result = []
    for item in items:
        item.pop("_id", None)
        result.append({"id": item.get("id","EKSİK"), "baslik": item.get("baslik","?"), "durum": item.get("durum","?")})
    return result


@router.get("/admin/debug-ogrenciler")
async def debug_ogrenciler(current_user=Depends(require_role(UserRole.ADMIN))):
    items = await db.students.find().to_list(length=None)
    result = []
    for item in items:
        item.pop("_id", None)
        result.append({"id": item.get("id","EKSİK"), "ad": item.get("ad","?"), "soyad": item.get("soyad","?")})
    return result
