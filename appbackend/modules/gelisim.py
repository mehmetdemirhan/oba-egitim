"""Öğretmen gelişim içerikleri modülü (/gelisim/*).

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


class SoruModel(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    soru: str
    secenekler: List[str]
    dogru_cevap: int

class IcerikCreate(BaseModel):
    baslik: str
    tur: str  # hizmetici, film, kitap, makale, okuma_parcasi
    aciklama: str = ""
    hedef_kitle: str  # ogretmen, ogrenci, hepsi
    sorular: List[SoruModel] = []
    # Makale alanları
    makale_link: Optional[str] = None
    makale_dosya_turu: Optional[str] = None  # pdf, word, link
    # Kitap ek alanlar
    kitap_yazar: Optional[str] = None
    kitap_isbn: Optional[str] = None
    kitap_yayinevi: Optional[str] = None
    kitap_sayfa: Optional[str] = None
    kitap_yas_grubu: Optional[str] = None
    kitap_link: Optional[str] = None
    kitap_kapak: Optional[str] = None
    kitap_bolum_sayisi: Optional[int] = None
    # Kitap/makale dosya (base64)
    dosya_b64: Optional[str] = None
    dosya_adi: Optional[str] = None
    dosya_turu: Optional[str] = None  # pdf, docx
    # Okuma parçası
    okuma_metni: Optional[str] = None
    okuma_seviye: Optional[str] = None  # kolay, orta, zor
    okuma_sure: Optional[int] = None  # dakika

class IcerikModel(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    baslik: str
    tur: str
    aciklama: str = ""
    hedef_kitle: str
    sorular: List[SoruModel] = []
    makale_link: Optional[str] = None
    makale_dosya_turu: Optional[str] = None
    kitap_yazar: Optional[str] = None
    kitap_isbn: Optional[str] = None
    kitap_yayinevi: Optional[str] = None
    kitap_sayfa: Optional[str] = None
    kitap_yas_grubu: Optional[str] = None
    kitap_link: Optional[str] = None
    kitap_kapak: Optional[str] = None
    kitap_bolum_sayisi: Optional[int] = None
    dosya_b64: Optional[str] = None
    dosya_adi: Optional[str] = None
    dosya_turu: Optional[str] = None
    okuma_metni: Optional[str] = None
    okuma_seviye: Optional[str] = None
    okuma_sure: Optional[int] = None
    ekleyen_id: str = ""
    ekleyen_ad: str = ""
    durum: str = "beklemede"  # beklemede, oylama, yayinda, reddedildi
    oylar: dict = Field(default_factory=dict)
    olusturma_tarihi: datetime = Field(default_factory=datetime.utcnow)
    yayin_tarihi: Optional[datetime] = None

class OyCreate(BaseModel):
    icerik_id: str
    onay: bool
    sebep: str = ""  # Red durumunda zorunlu

class TamamlamaCreate(BaseModel):
    icerik_id: str
    kullanici_id: str
    test_cevaplari: Optional[List[int]] = None

class TamamlamaModel(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    kullanici_id: str
    icerik_id: str
    test_yapildi: bool = False
    dogru_sayisi: int = 0
    toplam_soru: int = 0
    kazanilan_puan: int = 0
    tarih: datetime = Field(default_factory=datetime.utcnow)


# Dosya yükleme endpoint — kitap PDF/Word gelişim içeriğine eklenir
@router.post("/gelisim/dosya-yukle")
async def gelisim_dosya_yukle(
    dosya: UploadFile = File(...),
    current_user=Depends(get_current_user)
):
    role = current_user.get("role", "")
    if role not in ["admin", "coordinator", "teacher"]:
        raise HTTPException(status_code=403, detail="Yetkisiz")
    import os, base64
    ext = os.path.splitext(dosya.filename)[1].lower()
    if ext not in [".pdf", ".docx", ".doc", ".txt"]:
        raise HTTPException(status_code=400, detail=f"Desteklenmeyen format: {ext}. Desteklenen: .pdf, .docx, .doc, .txt")
    icerik = await dosya.read()
    if len(icerik) > 20 * 1024 * 1024:  # 20MB
        raise HTTPException(status_code=400, detail="Dosya 20MB'dan büyük olamaz")
    dosya_b64 = base64.b64encode(icerik).decode("utf-8")
    dosya_turu = "pdf" if ext == ".pdf" else "docx"
    return {
        "dosya_b64": dosya_b64,
        "dosya_adi": dosya.filename,
        "dosya_turu": dosya_turu,
        "boyut_kb": len(icerik) // 1024
    }


# İçerik ekleme (admin veya öğretmen)
@router.post("/gelisim/icerik")
async def create_icerik(icerik: IcerikCreate, current_user=Depends(get_current_user)):
    role = current_user.get("role", "")
    if role not in ["admin", "coordinator", "teacher"]:
        raise HTTPException(status_code=403, detail="Yetkisiz")
    
    # Admin/Koordinatör eklerse direkt yayında, öğretmen eklerse oylama
    durum = "yayinda" if role in ["admin", "coordinator"] else "oylama"
    
    model = IcerikModel(
        **icerik.dict(),
        ekleyen_id=current_user["id"],
        ekleyen_ad=f"{current_user.get('ad','')} {current_user.get('soyad','')}",
        durum=durum
    )
    data = model.dict()
    data["olusturma_tarihi"] = data["olusturma_tarihi"].isoformat()
    if data.get("yayin_tarihi"):
        data["yayin_tarihi"] = data["yayin_tarihi"].isoformat()

    # "Neden bu kitap?" alanı → +3 puan bonusu
    neden = data.get("neden_bu_icerik", "")
    if neden and len(neden.strip()) >= 20:
        data["neden_bonus"] = True
        try:
            await db.users.update_one({"id": current_user["id"]}, {"$inc": {"toplam_puan": 3}})
        except: pass

    # Test soruları bonusu → her soru +2 puan, max +20
    sorular = data.get("sorular", [])
    soru_bonus = min(len(sorular) * 2, 20)
    if soru_bonus > 0:
        data["soru_bonus"] = soru_bonus
        try:
            await db.users.update_one({"id": current_user["id"]}, {"$inc": {"toplam_puan": soru_bonus}})
        except: pass

    await db.gelisim_icerik.insert_one(data)

    # Kitap türünde içerik eklendiyse kitap havuzuna da kaydet (bölüm bazlı soru için)
    if data.get("tur") == "kitap":
        mevcut = await db.kitap_havuzu.find_one({"baslik": data.get("baslik", ""), "yazar": data.get("kitap_yazar", "")})
        if not mevcut:
            await db.kitap_havuzu.insert_one({
                "id": str(uuid.uuid4()),
                "baslik": data.get("baslik", ""),
                "yazar": data.get("kitap_yazar", ""),
                "yas_grubu": data.get("kitap_yas_grubu", ""),
                "zorluk": "orta",
                "bolum_sayisi": data.get("kitap_bolum_sayisi", 10),
                "kapak_url": data.get("kitap_kapak", ""),
                "ekleyen_id": current_user["id"],
                "ekleyen_ad": f"{current_user.get('ad','')} {current_user.get('soyad','')}",
                "durum": durum,
                "oylar": {},
                "gelisim_icerik_id": data.get("id"),
                "olusturma_tarihi": datetime.utcnow().isoformat(),
            })

    return data


# İçerikleri listele
@router.get("/gelisim/icerik")
async def get_icerik_list(current_user=Depends(get_current_user)):
    role = current_user.get("role", "")
    user_id = current_user.get("id", "")
    
    items = await db.gelisim_icerik.find().sort("olusturma_tarihi", -1).to_list(length=None)
    result = []
    for item in items:
        item.pop("_id", None)
        durum = item.get("durum", "")
        hedef = item.get("hedef_kitle", "hepsi")
        
        # Kitap türü ise bölüm bazlı soru sayısını ekle
        if item.get("tur") == "kitap":
            item["_soru_sayisi"] = await db.kitap_sorulari.count_documents({"kitap_id": item["id"]})
        
        # Admin her şeyi görür
        if role in ["admin", "coordinator"]:
            result.append(item)
        elif role == "teacher":
            if item.get("ekleyen_id") == user_id:
                result.append(item)
            elif durum == "oylama":
                result.append(item)
            elif durum == "yayinda" and hedef in ["hepsi", "ogretmen"]:
                result.append(item)
        elif role == "student":
            if durum == "yayinda" and hedef in ["hepsi", "ogrenci"]:
                result.append(item)
    
    return result


# Admin onay/red (beklemede → oylama veya reddedildi)
@router.post("/gelisim/icerik/{icerik_id}/admin-karar")
async def admin_karar(icerik_id: str, karar: dict, current_user=Depends(require_role(UserRole.ADMIN, UserRole.COORDINATOR))):
    # direkt=True → oylama atla, direkt yayına al
    onay = karar.get("onay", False)
    direkt = karar.get("direkt", False)
    if not onay:
        yeni_durum = "reddedildi"
    elif direkt:
        yeni_durum = "yayinda"
        icerik = await db.gelisim_icerik.find_one({"id": icerik_id})
        puanlar = await get_puan_ayarlari()
        if icerik and icerik.get("ekleyen_id"):
            await db.users.update_one({"id": icerik["ekleyen_id"]}, {"$inc": {"puan": puanlar.get("icerik_ekleme", 5)}})
    else:
        yeni_durum = "oylama"
    await db.gelisim_icerik.update_one(
        {"id": icerik_id},
        {"$set": {"durum": yeni_durum, **({"yayin_tarihi": datetime.utcnow().isoformat()} if yeni_durum == "yayinda" else {})}}
    )
    return {"durum": yeni_durum}


# Öğretmen oylama
@router.post("/gelisim/oy")
async def oy_ver(oy: OyCreate, current_user=Depends(get_current_user)):
    role = current_user.get("role", "")
    if role not in ["admin", "coordinator", "teacher"]:
        raise HTTPException(status_code=403, detail="Sadece öğretmenler oy verebilir")
    
    if not oy.onay and not oy.sebep:
        raise HTTPException(status_code=400, detail="Red için sebep belirtmelisiniz")
    
    icerik = await db.gelisim_icerik.find_one({"id": oy.icerik_id})
    if not icerik:
        raise HTTPException(status_code=404, detail="İçerik bulunamadı")
    if icerik.get("durum") != "oylama":
        raise HTTPException(status_code=400, detail="Bu içerik oylamada değil")
    
    user_id = current_user["id"]
    oylar = icerik.get("oylar", {})
    
    if user_id in oylar:
        raise HTTPException(status_code=400, detail="Zaten oy kullandınız")
    
    # Oyu kaydet
    oylar[user_id] = {"onay": oy.onay, "sebep": oy.sebep}
    await db.gelisim_icerik.update_one({"id": oy.icerik_id}, {"$set": {"oylar": oylar}})
    
    # Oy veren öğretmene puan (dinamik)
    puanlar = await get_puan_ayarlari()
    await db.users.update_one({"id": user_id}, {"$inc": {"puan": puanlar.get("icerik_oylama", 2)}})
    
    # %60 kontrolü
    ogretmenler = await db.users.find({"role": {"$in": ["teacher", "coordinator", "admin"]}}).to_list(length=None)
    toplam_ogretmen = len(ogretmenler)
    onay_sayisi = sum(1 for v in oylar.values() if v.get("onay"))
    oy_sayisi = len(oylar)
    
    yeni_durum = icerik.get("durum")
    
    if toplam_ogretmen > 0:
        onay_orani = onay_sayisi / toplam_ogretmen
        # Herkes oy kullandı veya onay oranı %60 geçti
        if onay_orani >= 0.6:
            yeni_durum = "yayinda"
            await db.gelisim_icerik.update_one(
                {"id": oy.icerik_id},
                {"$set": {"durum": "yayinda", "yayin_tarihi": datetime.utcnow().isoformat()}}
            )
            # İçerik ekleyene bonus puan (dinamik)
            ekleyen_id = icerik.get("ekleyen_id")
            if ekleyen_id:
                await db.users.update_one({"id": ekleyen_id}, {"$inc": {"puan": puanlar.get("icerik_ekleme", 5)}})
        elif oy_sayisi == toplam_ogretmen and onay_orani < 0.6:
            yeni_durum = "reddedildi"
            await db.gelisim_icerik.update_one({"id": oy.icerik_id}, {"$set": {"durum": "reddedildi"}})
    
    return {
        "mesaj": "Oyunuz kaydedildi (+2 puan)",
        "durum": yeni_durum,
        "onay_orani": round(onay_sayisi / max(toplam_ogretmen, 1) * 100),
        "oy_sayisi": oy_sayisi,
        "toplam": toplam_ogretmen
    }


# Tamamlama
@router.post("/gelisim/tamamla")
async def tamamla_icerik(data: TamamlamaCreate, current_user=Depends(get_current_user)):
    existing = await db.gelisim_tamamlama.find_one({"kullanici_id": data.kullanici_id, "icerik_id": data.icerik_id})
    if existing:
        raise HTTPException(status_code=400, detail="Bu içerik zaten tamamlandı")
    
    icerik = await db.gelisim_icerik.find_one({"id": data.icerik_id})
    if not icerik:
        raise HTTPException(status_code=404, detail="İçerik bulunamadı")
    
    sorular = icerik.get("sorular", [])
    toplam = len(sorular)
    dogru = 0
    test_yapildi = False
    puan = 1
    
    if data.test_cevaplari and toplam > 0:
        test_yapildi = True
        for i, cevap in enumerate(data.test_cevaplari):
            if i < toplam and cevap == sorular[i].get("dogru_cevap"):
                dogru += 1
        puan = max(1, round((dogru / toplam) * 10))
    
    tamamlama = TamamlamaModel(
        kullanici_id=data.kullanici_id,
        icerik_id=data.icerik_id,
        test_yapildi=test_yapildi,
        dogru_sayisi=dogru,
        toplam_soru=toplam,
        kazanilan_puan=puan
    )
    t_data = tamamlama.dict()
    t_data["tarih"] = t_data["tarih"].isoformat()
    await db.gelisim_tamamlama.insert_one(t_data)
    await db.users.update_one({"id": data.kullanici_id}, {"$inc": {"puan": puan}})
    
    return {"puan": puan, "dogru": dogru, "toplam": toplam, "test_yapildi": test_yapildi}


# Kullanıcının tamamlamaları
@router.get("/gelisim/tamamlama/{kullanici_id}")
async def get_tamamlamalar(kullanici_id: str, current_user=Depends(get_current_user)):
    items = await db.gelisim_tamamlama.find({"kullanici_id": kullanici_id}).to_list(length=None)
    for item in items:
        item.pop("_id", None)
    return items


# Puan tablosu
@router.get("/gelisim/puan-tablosu")
async def get_puan_tablosu(current_user=Depends(get_current_user)):
    users = await db.users.find().to_list(length=None)
    tablo = []
    for u in users:
        tablo.append({
            "ad": u.get("ad", ""), "soyad": u.get("soyad", ""),
            "role": u.get("role", ""), "puan": u.get("puan", 0)
        })
    tablo.sort(key=lambda x: x["puan"], reverse=True)
    return tablo


# İçerik sil
@router.delete("/gelisim/icerik/{icerik_id}")
async def delete_icerik(icerik_id: str, current_user=Depends(require_role(UserRole.ADMIN, UserRole.COORDINATOR))):
    await db.gelisim_icerik.delete_one({"id": icerik_id})
    return {"message": "Silindi"}


@router.get("/gelisim/icerik/{icerik_id}/etki")
async def icerik_etki_istatistikleri(icerik_id: str, current_user=Depends(get_current_user)):
    """Bir içeriğin etkisini göster: kaç öğrenci tamamladı, materyal, oyun, post-reading."""
    tamamlayan = await db.gelisim_tamamlama.count_documents({"icerik_id": icerik_id})
    materyal_sayisi = await db.ai_materyal_log.count_documents({"icerik_id": icerik_id})
    oyun_sayisi = await db.ai_oyun_log.count_documents({"icerik_id": icerik_id})
    post_reading = await db.post_reading_cache.count_documents({"icerik_id": icerik_id})
    zeka_harita = await db.kitap_zeka_haritasi.count_documents({"icerik_id": icerik_id})

    # Bloom ortalaması
    testler = await db.kitap_test_sonuclari.find({"icerik_id": icerik_id}).to_list(length=100)
    bloom_ort = 0
    if testler:
        dogru_list = [t.get("dogru", 0) for t in testler if t.get("toplam", 0) > 0]
        if dogru_list:
            toplam_list = [t.get("toplam", 1) for t in testler if t.get("toplam", 0) > 0]
            bloom_ort = round(sum(d/t for d,t in zip(dogru_list, toplam_list)) / len(dogru_list) * 100)

    return {
        "icerik_id": icerik_id,
        "tamamlayan_ogrenci": tamamlayan,
        "uretilen_materyal": materyal_sayisi,
        "oynanan_oyun": oyun_sayisi,
        "post_reading_analiz": post_reading,
        "zeka_harita": 1 if zeka_harita > 0 else 0,
        "bloom_ort": bloom_ort,
    }


@router.get("/gelisim/etki-ozet")
async def etki_ozet(current_user=Depends(get_current_user)):
    """Öğretmenin eklediği tüm içeriklerin toplam etkisi."""
    user_id = current_user.get("id", "")
    icerikler = await db.gelisim_icerik.find({"ekleyen_id": user_id}).to_list(length=None)
    icerik_idler = [i["id"] for i in icerikler if i.get("id")]

    toplam_tamamlayan = 0
    toplam_materyal = 0
    en_cok = None
    en_cok_sayi = 0

    for ic in icerikler:
        iid = ic.get("id", "")
        sayi = await db.gelisim_tamamlama.count_documents({"icerik_id": iid})
        toplam_tamamlayan += sayi
        mat = await db.ai_materyal_log.count_documents({"icerik_id": iid})
        toplam_materyal += mat
        if sayi > en_cok_sayi:
            en_cok_sayi = sayi
            en_cok = ic.get("baslik", "")

    return {
        "toplam_icerik": len(icerikler),
        "toplam_tamamlayan": toplam_tamamlayan,
        "toplam_materyal": toplam_materyal,
        "en_populer_icerik": en_cok,
        "en_populer_tamamlayan": en_cok_sayi,
    }




