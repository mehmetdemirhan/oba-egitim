"""Kullanıcı + il/harita istatistik modülü (/kullanici/il-guncelle, /istatistik/turkiye-harita).

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


@router.put("/kullanici/il-guncelle")
async def il_guncelle(req: Request, current_user=Depends(get_current_user)):
    """Kullanıcının il bilgisini güncelle (harita için anonim veri)."""
    data = await req.json()
    il = data.get("il", "").strip()
    if not il:
        raise HTTPException(status_code=400, detail="İl boş olamaz")
    await db.users.update_one({"id": current_user["id"]}, {"$set": {"il": il}})
    return {"ok": True, "il": il}


@router.get("/istatistik/turkiye-harita")
async def turkiye_okuma_haritasi():
    """İl bazında anonim okuma istatistikleri. Bireysel bilgi içermez."""
    try:
        # Kullanıcıların il bilgisi + okuma verileri — anonim aggregation
        pipeline = [
            {"$match": {"role": "student", "il": {"$exists": True, "$ne": ""}}},
            {"$group": {
                "_id": "$il",
                "okuyucu_sayisi": {"$sum": 1},
                "ogrenci_idler": {"$push": "$id"}
            }}
        ]
        il_gruplari = await db.users.aggregate(pipeline).to_list(length=None)

        # Öğrenci Dağılımı: CRM öğrencilerinin (db.students) il bazlı sayısı — anonim.
        # Arşivli/mezun dahil değil (aktif dağılım). Kimlik sızmaz, yalnız sayı.
        ogr_dagilim = await db.students.aggregate([
            {"$match": {"il": {"$exists": True, "$nin": [None, ""]}, "arsivli": {"$ne": True}}},
            {"$group": {"_id": "$il", "sayi": {"$sum": 1}}},
        ]).to_list(length=None)
        ogr_map = {g["_id"]: g["sayi"] for g in ogr_dagilim if g.get("_id")}

        # Öğretmen Dağılımı: db.teachers il bazlı sayı — anonim (arşivli hariç, kimlik sızmaz).
        ogt_dagilim = await db.teachers.aggregate([
            {"$match": {"il": {"$exists": True, "$nin": [None, ""]}, "arsivli": {"$ne": True}}},
            {"$group": {"_id": "$il", "sayi": {"$sum": 1}}},
        ]).to_list(length=None)
        ogt_map = {g["_id"]: g["sayi"] for g in ogt_dagilim if g.get("_id")}

        iller = []
        toplam_okuyucu = 0
        toplam_kelime_genel = 0
        aktif_il_sayisi = 0

        for grup in il_gruplari:
            il_adi = grup["_id"]
            if not il_adi:
                continue
            ogrenci_idler = grup.get("ogrenci_idler", [])
            okuyucu = len(ogrenci_idler)
            toplam_okuyucu += okuyucu

            # Bu ildeki öğrencilerin toplam kitap tamamlama sayısı
            kitap_sayisi = await db.gelisim_tamamlama.count_documents(
                {"ogrenci_id": {"$in": ogrenci_idler}}
            )

            # Kelime öğrenme sayısı
            kelime_sayisi = await db.kelime_evrimi.count_documents(
                {"ogrenci_id": {"$in": ogrenci_idler}, "kutu": {"$gte": 3}}
            )
            toplam_kelime_genel += kelime_sayisi

            # Streak ortalaması
            streak_data = await db.users.find(
                {"id": {"$in": ogrenci_idler}},
                {"streak": 1}
            ).to_list(length=None)
            avg_streak = round(
                sum(u.get("streak", 0) for u in streak_data) / len(streak_data)
            ) if streak_data else 0

            if kitap_sayisi > 0 or kelime_sayisi > 0:
                aktif_il_sayisi += 1

            iller.append({
                "il": il_adi,
                "okuyucu_sayisi": okuyucu,
                "kitap_sayisi": kitap_sayisi,
                "kelime_sayisi": kelime_sayisi,
                "avg_streak": avg_streak,
                "ogrenci_sayisi": ogr_map.pop(il_adi, 0),   # CRM öğrenci il dağılımı
                "ogretmen_sayisi": ogt_map.pop(il_adi, 0),  # CRM öğretmen il dağılımı
            })

        # Yalnız CRM'de (db.students / db.teachers) il'i olan ama users haritasında olmayan iller
        for il_adi in set(ogr_map) | set(ogt_map):
            iller.append({
                "il": il_adi, "okuyucu_sayisi": 0, "kitap_sayisi": 0,
                "kelime_sayisi": 0, "avg_streak": 0,
                "ogrenci_sayisi": ogr_map.get(il_adi, 0),
                "ogretmen_sayisi": ogt_map.get(il_adi, 0),
            })

        # Sırala: kitap sayısına göre
        iller.sort(key=lambda x: x["kitap_sayisi"], reverse=True)

        toplam_ogrenci = sum(i["ogrenci_sayisi"] for i in iller)
        en_yogun = sorted([i for i in iller if i["ogrenci_sayisi"] > 0],
                          key=lambda x: x["ogrenci_sayisi"], reverse=True)[:3]
        toplam_ogretmen = sum(i.get("ogretmen_sayisi", 0) for i in iller)
        en_yogun_ogt = sorted([i for i in iller if i.get("ogretmen_sayisi", 0) > 0],
                              key=lambda x: x["ogretmen_sayisi"], reverse=True)[:3]

        return {
            "iller": iller,
            "toplam_okuyucu": toplam_okuyucu,
            "toplam_kelime": toplam_kelime_genel,
            "aktif_il": aktif_il_sayisi,
            "toplam_ogrenci": toplam_ogrenci,
            "en_yogun_iller": [{"il": i["il"], "ogrenci_sayisi": i["ogrenci_sayisi"]} for i in en_yogun],
            "toplam_ogretmen": toplam_ogretmen,
            "en_yogun_iller_ogretmen": [{"il": i["il"], "ogretmen_sayisi": i["ogretmen_sayisi"]} for i in en_yogun_ogt],
            "guncelleme": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logging.error(f"[TURKİYE-HARİTA] Hata: {e}")
        return {"iller": [], "toplam_okuyucu": 0, "toplam_kelime": 0, "aktif_il": 0,
                "toplam_ogrenci": 0, "toplam_ogretmen": 0}
