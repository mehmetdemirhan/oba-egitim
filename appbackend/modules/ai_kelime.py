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
from core.kelime_durum import leitner_ilerlet, durum_etiket, OGRENILDI_KUTU

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
    # kelime_tekrar öğrenci RECORD id (linked_id) ile tutulur; XP ise user'a yazılır.
    ogrenci_id = current_user.get("linked_id") or current_user["id"]

    kayit = await db.kelime_tekrar.find_one({"id": kelime_id, "ogrenci_id": ogrenci_id})
    if not kayit:
        raise HTTPException(status_code=404, detail="Kelime kaydı bulunamadı")

    mevcut_kutu = kayit.get("kutu", 1)
    onceki_kutu = kayit.get("kutu", 0)
    simdi = datetime.utcnow()

    # Leitner ilerlemesi — merkezî algoritma (core.kelime_durum, tek kaynak).
    sinif = kayit.get("sinif", 3)
    yeni_kutu, sonraki, xp = leitner_ilerlet(mevcut_kutu, dogru, sinif)

    set_alan = {
        "kutu": yeni_kutu,
        "son_gosterim": simdi.isoformat(),
        "sonraki_gosterim": sonraki,
    }
    # İlk kez öğrenildi eşiğine (kutu>=4) ulaştıysa tarihini damgala (bir kez).
    if yeni_kutu >= OGRENILDI_KUTU and onceki_kutu < OGRENILDI_KUTU and not kayit.get("ogrenildi_tarihi"):
        set_alan["ogrenildi_tarihi"] = simdi.isoformat()

    await db.kelime_tekrar.update_one({"id": kelime_id}, {
        "$set": set_alan,
        "$inc": {
            "tekrar_sayisi": 1,
            "dogru_sayisi": 1 if dogru else 0,
            "yanlis_sayisi": 0 if dogru else 1,
        },
    })

    # XP → kullanıcı hesabına (user id; kelime_tekrar linked_id iken XP user'da).
    try:
        await db.users.update_one({"id": current_user["id"]}, {"$inc": {"toplam_xp": xp}})
    except:
        pass

    return {"dogru": dogru, "yeni_kutu": yeni_kutu, "durum": durum_etiket(yeni_kutu), "xp": xp}


@router.post("/ai/kelime-evrimi/ekle")
async def kelime_evrimi_ekle(payload: dict, current_user=Depends(get_current_user)):
    """Öğrenciye kelime tekrar programına kelime ekler.

    `kelimeler` açıkça verilirse aynen eklenir (mevcut davranış). Verilmez ama
    `adet` verilirse, kelimeler MEB müfredatı ÖNCELİKLİ (core/kelime_secici) olarak
    otomatik seçilir — böylece Leitner havuzu MEB kelimelerini önceler.
    """
    # kelime_tekrar öğrenci RECORD id (linked_id) ile tutulur — engine ve öğretmen
    # paneliyle tutarlı olsun diye varsayılan da linked_id (user id DEĞİL).
    ogrenci_id = payload.get("ogrenci_id") or current_user.get("linked_id") or current_user["id"]
    kelimeler = payload.get("kelimeler", [])  # [{"kelime": "...", "anlam": "...", "sinif": 3}]

    # Otomatik doldurma: MEB öncelikli + öğrencinin ÖĞRENDİĞİ (kutu>=4) kelimeler
    # hariç (rotasyona tekrar sokulmasın). core.kelime_durum.ogrenci_kelime_sec.
    if not kelimeler and payload.get("adet"):
        try:
            from core.kelime_durum import ogrenci_kelime_sec
            sinif = int(payload.get("sinif", 3))
            secilenler = await ogrenci_kelime_sec(ogrenci_id, sinif, int(payload["adet"]))
            kelimeler = [{
                "kelime": s["kelime"], "anlam": s.get("anlam", ""),
                "ornek_cumle": s.get("ornek_cumle", ""), "sinif": sinif,
            } for s in secilenler]
        except Exception as ex:
            logging.warning(f"[ai_kelime] otomatik doldurma hatası: {ex}")

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
