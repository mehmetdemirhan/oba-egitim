"""Veli anketleri modülü (/anketler/*).

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
    get_xp_tablosu, get_puan_ayarlari, get_lig_esikleri, get_anket_sorulari,
    XP_TABLOSU_DEFAULT, LIG_ESIKLERI_DEFAULT, LIG_SIRA,
)
from core.ai import _gemini_call, call_claude, _mock_bilgi_tabani_response, get_ogrenci_ai_verileri

router = APIRouter()


@router.get("/anketler/sorular")
async def get_anket_sorulari_endpoint():
    return await get_anket_sorulari()


@router.post("/anketler")
async def create_anket(payload: dict, current_user=Depends(get_current_user)):
    if current_user.get("role") != "parent":
        raise HTTPException(status_code=403, detail="Sadece veliler anket doldurabilir")

    ogretmen_id = payload.get("ogretmen_id", "")
    ogrenci_id = payload.get("ogrenci_id", "")
    yanitlar = payload.get("yanitlar", [])
    tavsiye = payload.get("tavsiye", None)
    not_text = payload.get("not_text", "")
    donem = payload.get("donem", datetime.utcnow().strftime("%Y-D%m"))

    # Aynı dönem + aynı öğretmen kontrolü
    mevcut = await db.veli_anketleri.find_one({
        "veli_id": current_user["id"], "ogretmen_id": ogretmen_id, "donem": donem
    })
    if mevcut:
        raise HTTPException(status_code=409, detail="Bu dönem için zaten anket doldurdunuz")

    doc = {
        "id": str(uuid.uuid4()),
        "veli_id": current_user["id"],
        "veli_ad": f"{current_user.get('ad', '')} {current_user.get('soyad', '')}".strip(),
        "ogretmen_id": ogretmen_id,
        "ogrenci_id": ogrenci_id,
        "donem": donem,
        "yanitlar": yanitlar,
        "tavsiye": tavsiye,
        "not_text": not_text,
        "tarih": datetime.utcnow().isoformat(),
    }
    await db.veli_anketleri.insert_one(doc)
    return doc


@router.get("/anketler/ogretmen/{ogretmen_id}/ozet")
async def anket_ozet(ogretmen_id: str, current_user=Depends(get_current_user)):
    anketler = await db.veli_anketleri.find({"ogretmen_id": ogretmen_id}).to_list(length=None)
    if not anketler:
        return {"anket_sayisi": 0, "ortalama": 0, "tavsiye_oran": 0, "kategoriler": {}, "son_anketler": []}

    puanlar = []
    tavsiyeler = 0
    kategori_toplam = {}
    kategori_sayac = {}

    for a in anketler:
        for y in a.get("yanitlar", []):
            if y.get("puan"):
                puanlar.append(y["puan"])
                kat = y.get("kategori", "genel")
                kategori_toplam[kat] = kategori_toplam.get(kat, 0) + y["puan"]
                kategori_sayac[kat] = kategori_sayac.get(kat, 0) + 1
        if a.get("tavsiye"):
            tavsiyeler += 1

    ortalama = round(sum(puanlar) / max(len(puanlar), 1), 1)
    tavsiye_oran = round((tavsiyeler / len(anketler)) * 100)
    kategoriler = {k: round(kategori_toplam[k] / kategori_sayac[k], 1) for k in kategori_toplam}

    # Öğretmen isimleri görmez
    role = current_user.get("role", "")
    son_anketler = []
    for a in sorted(anketler, key=lambda x: x.get("tarih", ""), reverse=True)[:10]:
        a.pop("_id", None)
        entry = {"donem": a.get("donem"), "tarih": a.get("tarih"), "tavsiye": a.get("tavsiye")}
        puan_yanitlar = [y.get("puan") for y in a.get("yanitlar", []) if y.get("puan")]
        entry["ortalama"] = round(sum(puan_yanitlar) / max(len(puan_yanitlar), 1), 1) if puan_yanitlar else 0
        if role in ["admin", "coordinator"]:
            entry["veli_ad"] = a.get("veli_ad", "")
            entry["not_text"] = a.get("not_text", "")
        son_anketler.append(entry)

    return {
        "anket_sayisi": len(anketler), "ortalama": ortalama, "tavsiye_oran": tavsiye_oran,
        "kategoriler": kategoriler, "son_anketler": son_anketler,
    }


@router.get("/anketler/veli/{veli_id}")
async def veli_anketleri(veli_id: str, current_user=Depends(get_current_user)):
    anketler = await db.veli_anketleri.find({"veli_id": veli_id}).to_list(length=None)
    for a in anketler:
        a.pop("_id", None)
    return anketler
