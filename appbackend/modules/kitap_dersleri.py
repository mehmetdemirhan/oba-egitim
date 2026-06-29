"""Kitap dersleri (sınıf bazlı parça/soru havuzu) modülü (/kitap-dersleri/*).

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


@router.get("/kitap-dersleri/siniflar")
async def kitap_dersleri_siniflar(current_user=Depends(get_current_user)):
    """Parça bulunan sınıf listesini döner."""
    siniflar = await db.ai_okuma_parcalari.distinct("sinif")
    return sorted([s for s in siniflar if s])


@router.get("/kitap-dersleri/kitaplar/{sinif}")
async def kitap_dersleri_kitaplar(sinif: int, current_user=Depends(get_current_user)):
    """Belirtilen sınıfa ait kitap listesini döner."""
    kitaplar = await db.ai_okuma_parcalari.distinct("kitap_adi", {"sinif": sinif})
    sonuc = []
    for k in kitaplar:
        parca_sayisi = await db.ai_okuma_parcalari.count_documents({"sinif": sinif, "kitap_adi": k})
        soru_sayisi = await db.ai_uretilen_sorular.count_documents({"sinif": sinif, "kitap_adi": k})
        sonuc.append({"kitap_adi": k, "parca_sayisi": parca_sayisi, "soru_sayisi": soru_sayisi})
    return sonuc


@router.get("/kitap-dersleri/parcalar/{sinif}/{kitap_adi}")
async def kitap_dersleri_parcalar(sinif: int, kitap_adi: str, current_user=Depends(get_current_user)):
    """Belirtilen kitabın okuma parçalarını ve sorularını döner."""
    from urllib.parse import unquote
    kitap_adi = unquote(kitap_adi)
    parcalar = await db.ai_okuma_parcalari.find(
        {"sinif": sinif, "kitap_adi": kitap_adi}
    ).sort("bolum", 1).to_list(length=None)
    for p in parcalar:
        p.pop("_id", None)
        # Her parçanın sorularını ekle
        sorular = await db.ai_uretilen_sorular.find(
            {"sinif": sinif, "kitap_adi": kitap_adi, "bolum": p.get("bolum", 0)}
        ).to_list(length=None)
        for s in sorular:
            s.pop("_id", None)
        p["sorular"] = sorular
    return parcalar


@router.post("/kitap-dersleri/cevapla")
async def kitap_dersleri_cevapla(payload: dict = Body(...), current_user=Depends(get_current_user)):
    """Öğrencinin soru cevabını kaydet ve XP ver."""
    soru_id = payload.get("soru_id")
    cevap = payload.get("cevap")
    kitap_adi = payload.get("kitap_adi", "")
    sinif = payload.get("sinif", 0)

    soru = await db.ai_uretilen_sorular.find_one({"id": soru_id})
    if not soru:
        raise HTTPException(status_code=404, detail="Soru bulunamadı")

    dogru = soru.get("dogru_cevap") == cevap
    xp = 5 if dogru else 1

    # Cevabı kaydet
    await db.ai_soru_cevaplari.insert_one({
        "id": str(uuid.uuid4()),
        "ogrenci_id": current_user.get("linked_id") or current_user["id"],
        "soru_id": soru_id,
        "kitap_adi": kitap_adi,
        "sinif": sinif,
        "cevap": cevap,
        "dogru": dogru,
        "xp": xp,
        "tarih": datetime.utcnow().isoformat(),
    })

    # XP ver
    if dogru:
        ogrenci_id = current_user.get("linked_id") or current_user["id"]
        await db.students.update_one({"id": ogrenci_id}, {"$inc": {"xp": xp}})
        await db.xp_logs.insert_one({
            "id": str(uuid.uuid4()),
            "ogrenci_id": ogrenci_id,
            "eylem": "kitap_sorusu",
            "xp": xp,
            "aciklama": f"📚 {kitap_adi} — doğru cevap",
            "tarih": datetime.utcnow().isoformat(),
        })

    return {"dogru": dogru, "xp_kazanildi": xp, "dogru_cevap": soru.get("dogru_cevap")}


@router.put("/kitap-dersleri/parca/{parca_id}")
async def kitap_parca_guncelle(
    parca_id: str,
    payload: dict = Body(...),
    current_user=Depends(require_role(UserRole.ADMIN))
):
    """Okuma parçasını güncelle."""
    guncelle = {}
    for alan in ["baslik", "ozet", "metin_kesit", "tema", "kelime_sayisi"]:
        if alan in payload:
            guncelle[alan] = payload[alan]
    if not guncelle:
        raise HTTPException(status_code=400, detail="Güncellenecek alan yok")
    await db.ai_okuma_parcalari.update_one({"id": parca_id}, {"$set": guncelle})
    return {"ok": True}


@router.delete("/kitap-dersleri/parca/{parca_id}")
async def kitap_parca_sil(parca_id: str, current_user=Depends(require_role(UserRole.ADMIN))):
    """Okuma parçasını sil."""
    await db.ai_okuma_parcalari.delete_one({"id": parca_id})
    return {"ok": True}


@router.put("/kitap-dersleri/soru/{soru_id}")
async def kitap_soru_guncelle(
    soru_id: str,
    payload: dict = Body(...),
    current_user=Depends(require_role(UserRole.ADMIN))
):
    """Soruyu güncelle."""
    guncelle = {}
    for alan in ["soru", "secenekler", "dogru_cevap", "taksonomi"]:
        if alan in payload:
            guncelle[alan] = payload[alan]
    if not guncelle:
        raise HTTPException(status_code=400, detail="Güncellenecek alan yok")
    await db.ai_uretilen_sorular.update_one({"id": soru_id}, {"$set": guncelle})
    return {"ok": True}


@router.delete("/kitap-dersleri/soru/{soru_id}")
async def kitap_soru_sil(soru_id: str, current_user=Depends(require_role(UserRole.ADMIN))):
    """Soruyu sil."""
    await db.ai_uretilen_sorular.delete_one({"id": soru_id})
    return {"ok": True}


@router.post("/kitap-dersleri/soru-ekle")
async def kitap_soru_ekle(
    payload: dict = Body(...),
    current_user=Depends(require_role(UserRole.ADMIN))
):
    """Parçaya yeni soru ekle."""
    yeni_soru = {
        "id": str(uuid.uuid4()),
        "yukleme_id": payload.get("yukleme_id", ""),
        "kitap_adi": payload.get("kitap_adi", ""),
        "sinif": payload.get("sinif", 0),
        "bolum": payload.get("bolum", 0),
        "soru": payload.get("soru", ""),
        "secenekler": payload.get("secenekler", []),
        "dogru_cevap": payload.get("dogru_cevap", 0),
        "taksonomi": payload.get("taksonomi", "bilgi"),
        "tarih": datetime.utcnow().isoformat(),
    }
    await db.ai_uretilen_sorular.insert_one(yeni_soru)
    yeni_soru.pop("_id", None)
    return yeni_soru


@router.post("/kitap-dersleri/parca-ekle")
async def kitap_parca_ekle(
    payload: dict = Body(...),
    current_user=Depends(require_role(UserRole.ADMIN))
):
    """Kitaba yeni okuma parçası ekle."""
    yeni_parca = {
        "id": str(uuid.uuid4()),
        "yukleme_id": payload.get("yukleme_id", "manuel"),
        "kitap_adi": payload.get("kitap_adi", ""),
        "sinif": payload.get("sinif", 0),
        "bolum": payload.get("bolum", 0),
        "baslik": payload.get("baslik", ""),
        "ozet": payload.get("ozet", ""),
        "metin_kesit": payload.get("metin_kesit", ""),
        "tema": payload.get("tema", ""),
        "kelime_sayisi": payload.get("kelime_sayisi", 0),
        "tarih": datetime.utcnow().isoformat(),
    }
    await db.ai_okuma_parcalari.insert_one(yeni_parca)
    yeni_parca.pop("_id", None)
    return yeni_parca


@router.post("/kitap-dersleri/havuza-ekle/{parca_id}")
async def kitap_parca_havuza_ekle(parca_id: str, current_user=Depends(get_current_user)):
    """Okuma parçasını gelişim içerik havuzuna ekle."""
    parca = await db.ai_okuma_parcalari.find_one({"id": parca_id})
    if not parca:
        raise HTTPException(status_code=404, detail="Parça bulunamadı")
    mevcut = await db.gelisim_icerikleri.find_one({"kaynak_parca_id": parca_id})
    if mevcut:
        raise HTTPException(status_code=409, detail="Bu parça zaten içerik havuzunda")
    sorular = await db.ai_uretilen_sorular.find(
        {"yukleme_id": parca.get("yukleme_id"), "bolum": parca.get("bolum", 0)}
    ).to_list(length=None)
    soru_listesi = [{"id": str(uuid.uuid4()), "soru": s.get("soru",""), "secenekler": s.get("secenekler",[]), "dogru_cevap": s.get("dogru_cevap",0), "taksonomi": s.get("taksonomi","bilgi")} for s in sorular]
    icerik = {
        "id": str(uuid.uuid4()),
        "baslik": f"{parca.get('kitap_adi','')} — {parca.get('baslik','')}",
        "tur": "okuma_parcasi",
        "aciklama": parca.get("ozet",""),
        "hedef_kitle": "ogrenci",
        "okuma_metni": parca.get("metin_kesit",""),
        "okuma_seviye": "orta",
        "okuma_sure": max(1, len((parca.get("metin_kesit") or "").split()) // 200),
        "sorular": soru_listesi,
        "kaynak": "ai_bilgi_tabani",
        "kaynak_parca_id": parca_id,
        "kaynak_kitap": parca.get("kitap_adi",""),
        "sinif": parca.get("sinif"),
        "tema": parca.get("tema",""),
        "yukleyen_id": current_user["id"],
        "yukleyen_ad": f"{current_user.get('ad','')} {current_user.get('soyad','')}".strip(),
        "durum": "yayinda",
        "onayli": True,
        "oylama_sayisi": 0,
        "olumlu_oy": 0,
        "tarih": datetime.utcnow().isoformat(),
    }
    await db.gelisim_icerikleri.insert_one(icerik)
    icerik.pop("_id", None)
    return {"ok": True, "icerik_id": icerik["id"], "mesaj": "✅ İçerik havuzuna eklendi!"}
