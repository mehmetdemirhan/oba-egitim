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
import secrets
import hashlib
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
from core.config import FRONTEND_URL
from core.zaman import iso, simdi, aware

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


# ═══════════════════════════════════════════════════════════════════
# TOKEN TABANLI GİRİŞSİZ VELİ ANKETİ
# Veli panele girmeden, tek-kullanımlık süreli link ile anket doldurur.
# Doldurulan anket AYNI db.veli_anketleri koleksiyonuna yazılır → mevcut
# "Veli Değerlendirme Özeti" / dashboard aggregation'ına otomatik akar.
# Şablon: auth_api şifre-sıfırlama (hash-in-DB, raw-in-link) deseni.
# ═══════════════════════════════════════════════════════════════════

_ANKET_TOKEN_KOL = "veli_anket_tokenlari"


def _anket_token_hash(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


class AnketTokenIstek(BaseModel):
    ogretmen_id: str
    ogrenci_id: str
    ogrenci_ad: str = ""
    veli_ad: str = ""
    veli_telefon: str = ""
    donem: Optional[str] = None
    gecerlilik_gun: int = 14
    gonder: bool = False           # True → linki WhatsApp/SMS ile gönder
    kanal: str = "sms"             # sms | whatsapp


@router.post("/anketler/token")
async def anket_token_olustur(
    istek: AnketTokenIstek,
    current_user=Depends(require_role(UserRole.ADMIN, UserRole.COORDINATOR, UserRole.TEACHER)),
):
    """Girişsiz anket linki üretir (öğretmen/koordinatör/admin). İstenirse linki
    velinin telefonuna WhatsApp/SMS ile gönderir. Token hash'lenerek saklanır."""
    donem = istek.donem or simdi().strftime("%Y-D%m")
    raw = secrets.token_urlsafe(32)
    doc = {
        "id": str(uuid.uuid4()),
        "token_hash": _anket_token_hash(raw),
        "ogretmen_id": istek.ogretmen_id,
        "ogrenci_id": istek.ogrenci_id,
        "ogrenci_ad": istek.ogrenci_ad,
        "veli_ad": istek.veli_ad,
        "veli_telefon": istek.veli_telefon,
        "donem": donem,
        "olusturan_id": current_user["id"],
        "gecerlilik": iso_gun_sonra(istek.gecerlilik_gun),
        "kullanildi": False,
        "olusturma": iso(),
    }
    await db[_ANKET_TOKEN_KOL].insert_one(doc)
    link = f"{FRONTEND_URL}/veli-anket?token={raw}"

    gonderim = None
    if istek.gonder and istek.veli_telefon:
        gonderim = await _anket_link_gonder(istek.kanal, istek.veli_telefon, istek.ogrenci_ad, link)

    return {"ok": True, "token": raw, "link": link, "donem": donem, "gonderim": gonderim}


async def _anket_link_gonder(kanal_ad: str, telefon: str, ogrenci_ad: str, link: str) -> dict:
    """Anket linkini mevcut mesaj kanalı altyapısı (Netgsm SMS / WhatsApp Cloud)
    üzerinden gönderir. Kanal yapılandırılmamışsa hata KanalSonuc'u döner (link yine
    üretilmiştir; elle paylaşılabilir)."""
    try:
        from core.mesaj_kanallari import kanal_al
        kanal = kanal_al(kanal_ad)
        metin = (
            f"Merhaba, {ogrenci_ad or 'öğrencimiz'} için öğretmen memnuniyet "
            f"anketini doldurabilirsiniz (giriş gerektirmez): {link}"
        )
        sonuc = await kanal.gonder(telefon, metin, "hizmet")
        return {"ok": bool(getattr(sonuc, "ok", False)), "durum": getattr(sonuc, "durum", None),
                "hata": getattr(sonuc, "hata", None), "kanal": kanal_ad}
    except Exception as e:
        return {"ok": False, "hata": str(e), "kanal": kanal_ad}


def iso_gun_sonra(gun: int) -> str:
    return (simdi() + timedelta(days=max(1, int(gun or 14)))).isoformat()


async def _anket_token_getir(token: str) -> dict:
    t = await db[_ANKET_TOKEN_KOL].find_one({"token_hash": _anket_token_hash(token)})
    if not t:
        raise HTTPException(status_code=404, detail="Geçersiz anket bağlantısı")
    if t.get("kullanildi"):
        raise HTTPException(status_code=410, detail="Bu anket bağlantısı zaten kullanıldı")
    son = t.get("gecerlilik")
    if son and aware(son) < simdi():
        raise HTTPException(status_code=410, detail="Anket bağlantısının süresi dolmuş")
    return t


@router.get("/anketler/anket/{token}")
async def anket_token_dogrula(token: str):
    """PUBLIC (girişsiz): token geçerliyse anket sorularını + bağlam bilgisini döner."""
    t = await _anket_token_getir(token)
    sorular = await get_anket_sorulari()
    return {
        "gecerli": True,
        "ogrenci_ad": t.get("ogrenci_ad", ""),
        "veli_ad": t.get("veli_ad", ""),
        "donem": t.get("donem", ""),
        "sorular": sorular,
    }


@router.post("/anketler/anket/{token}")
async def anket_token_gonder(token: str, payload: dict = Body(...)):
    """PUBLIC (girişsiz): token ile anket gönderimi. Mevcut db.veli_anketleri
    şemasına yazar, token'ı tek-kullanımlık olarak geçersiz kılar."""
    t = await _anket_token_getir(token)
    kayit = {
        "id": str(uuid.uuid4()),
        "veli_id": f"token:{t['id']}",     # girişsiz veli — token kimliği
        "veli_ad": t.get("veli_ad", "") or "Veli",
        "ogretmen_id": t.get("ogretmen_id"),
        "ogrenci_id": t.get("ogrenci_id"),
        "donem": t.get("donem"),
        "yanitlar": payload.get("yanitlar", []),
        "tavsiye": payload.get("tavsiye"),
        "not_text": payload.get("not_text", ""),
        "tarih": iso(),
        "kaynak": "public_token",
    }
    await db.veli_anketleri.insert_one(kayit)
    await db[_ANKET_TOKEN_KOL].update_one(
        {"id": t["id"]},
        {"$set": {"kullanildi": True, "kullanim_tarihi": iso()}},
    )
    return {"ok": True, "mesaj": "Değerlendirmeniz kaydedildi. Teşekkür ederiz!"}
