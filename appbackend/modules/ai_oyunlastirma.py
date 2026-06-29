"""AI oyunlaştırma & gelişim modülü (/ai/evren/*, /ai/okuma-evreni, /ai/gelisim-simulasyon, /ai/okuma-terapisi).

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


EVREN_BOLGELER = [
    {"id":"orman","sira":1,"ad":"Orman Kitaplığı","emoji":"🌲","renk":"green","aciklama":"Okuma serüvenin burada başlıyor!","kosul":"Başlangıç — herkese açık","kilitAc":None},
    {"id":"daglar","sira":2,"ad":"Kelime Dağları","emoji":"⛰️","renk":"blue","aciklama":"50 kelime öğrenince dağlara tırmanırsın!","kosul":"50 kelime öğren","kilitAc":{"tip":"kelime","deger":50}},
    {"id":"liman","sira":3,"ad":"Hikâye Limanı","emoji":"⚓","renk":"cyan","aciklama":"5 kitap okuyunca limana yanaşırsın!","kosul":"5 kitap oku","kilitAc":{"tip":"kitap","deger":5}},
    {"id":"kutuphane","sira":4,"ad":"Bilgelik Kütüphanesi","emoji":"🏰","renk":"purple","aciklama":"Bloom testlerinde %60 başarı sağla!","kosul":"Bloom skoru %60+","kilitAc":{"tip":"bloom","deger":60}},
    {"id":"galaksi","sira":5,"ad":"Hayal Galaksisi","emoji":"🚀","renk":"orange","aciklama":"Her şeyi tamamlayınca galaksiye uçarsın!","kosul":"Hepsini tamamla","kilitAc":{"tip":"hepsi","deger":0}},
]

OKUMA_EVRENI_BOLGELER = [
    {
        "id": "orman",
        "ad": "Orman Kitaplığı",
        "emoji": "🌲",
        "renk": "#22c55e",
        "aciklama": "Okuma yolculuğuna başladın!",
        "kriter": "baslangic",  # Herkes başlar
        "min_kitap": 0, "min_kelime": 0, "min_streak": 0, "min_bloom": 0,
    },
    {
        "id": "kelime_dag",
        "ad": "Kelime Dağları",
        "emoji": "⛰️",
        "renk": "#f59e0b",
        "aciklama": "50 kelime öğrendin!",
        "kriter": "kelime",
        "min_kitap": 0, "min_kelime": 50, "min_streak": 0, "min_bloom": 0,
    },
    {
        "id": "hikaye_limani",
        "ad": "Hikâye Limanı",
        "emoji": "⚓",
        "renk": "#3b82f6",
        "aciklama": "5 kitap/içerik tamamladın!",
        "kriter": "kitap",
        "min_kitap": 5, "min_kelime": 0, "min_streak": 0, "min_bloom": 0,
    },
    {
        "id": "bilgelik_kutuphane",
        "ad": "Bilgelik Kütüphanesi",
        "emoji": "🏰",
        "renk": "#8b5cf6",
        "aciklama": "Bloom %60 anlama seviyesine ulaştın!",
        "kriter": "bloom",
        "min_kitap": 5, "min_kelime": 100, "min_streak": 7, "min_bloom": 60,
    },
    {
        "id": "hayal_galaksisi",
        "ad": "Hayal Galaksisi",
        "emoji": "🚀",
        "renk": "#ec4899",
        "aciklama": "Tüm evrenin fethettdin! En yüksek seviye.",
        "kriter": "tumu",
        "min_kitap": 20, "min_kelime": 300, "min_streak": 30, "min_bloom": 80,
    },
]


async def _evren_hesapla(ogrenci_id: str) -> dict:
    kelime_sayisi = await db.kelime_tekrar.count_documents({"ogrenci_id": ogrenci_id, "seviye": {"$gte": 3}})
    if kelime_sayisi == 0:
        kelime_sayisi = await db.kelime_tekrar.count_documents({"ogrenci_id": ogrenci_id})
    kitaplar = await db.okuma_kayitlari.distinct("kitap_adi", {"ogrenci_id": ogrenci_id, "kitap_adi": {"$exists": True, "$ne": ""}})
    kitap_sayisi = len([k for k in kitaplar if k and k.strip()])
    bloom_kayitlar = await db.ai_uretilen_sorular.find({"ogrenci_id": ogrenci_id, "cevaplandi": True}).sort("tarih", -1).to_list(length=30)
    bloom_skoru = 0
    if bloom_kayitlar:
        dogru = sum(1 for k in bloom_kayitlar if k.get("dogru_mu"))
        bloom_skoru = round(dogru / len(bloom_kayitlar) * 100)

    bolgeler_durum = []
    aktif_bolge = "orman"
    for b in EVREN_BOLGELER:
        acik = True; ilerleme = 100; kac_kaldi = ""
        kil = b["kilitAc"]
        if kil:
            if kil["tip"] == "kelime":
                acik = kelime_sayisi >= kil["deger"]; ilerleme = min(100, round(kelime_sayisi/kil["deger"]*100))
                kac_kaldi = f"{max(0,kil['deger']-kelime_sayisi)} kelime daha" if not acik else ""
            elif kil["tip"] == "kitap":
                acik = kitap_sayisi >= kil["deger"]; ilerleme = min(100, round(kitap_sayisi/kil["deger"]*100))
                kac_kaldi = f"{max(0,kil['deger']-kitap_sayisi)} kitap daha" if not acik else ""
            elif kil["tip"] == "bloom":
                acik = bloom_skoru >= kil["deger"]; ilerleme = min(100, bloom_skoru)
                kac_kaldi = f"%{max(0,kil['deger']-bloom_skoru)} daha" if not acik else ""
            elif kil["tip"] == "hepsi":
                acik = kelime_sayisi >= 50 and kitap_sayisi >= 5 and bloom_skoru >= 60
                ilerleme = round((min(100,kelime_sayisi/50*100)+min(100,kitap_sayisi/5*100)+min(100,bloom_skoru/60*100))/3)
                kac_kaldi = "" if acik else "Önceki bölgeleri tamamla"
        bolgeler_durum.append({**{k: v for k,v in b.items() if k != "kilitAc"}, "acik": acik, "ilerleme": ilerleme, "kac_kaldi": kac_kaldi})
        if acik:
            aktif_bolge = b["id"]

    return {
        "aktif_bolge": aktif_bolge,
        "bolgeler": bolgeler_durum,
        "istatistikler": {"kelime_sayisi": kelime_sayisi, "kitap_sayisi": kitap_sayisi, "bloom_skoru": bloom_skoru},
    }


@router.get("/ai/evren/durum/{ogrenci_id}")
async def evren_durum(ogrenci_id: str, current_user=Depends(get_current_user)):
    return await _evren_hesapla(ogrenci_id)


@router.get("/ai/evren/durum-me")
async def evren_durum_me(current_user=Depends(get_current_user)):
    ogrenci_id = current_user.get("linked_id") or current_user.get("id")
    return await _evren_hesapla(ogrenci_id)


@router.get("/ai/okuma-evreni/{ogrenci_id}")
async def okuma_evreni(ogrenci_id: str, current_user=Depends(get_current_user)):
    """Öğrencinin Okuma Evreni bölgesini ve ilerleme durumunu hesapla."""
    # İstatistikler
    logs = await db.reading_logs.find({"ogrenci_id": ogrenci_id}).to_list(length=None)
    tamamlananlar = await db.gelisim_tamamlananlar.find({"kullanici_id": ogrenci_id}).to_list(length=None)
    kelime_ogrenilen = await db.kelime_tekrar.count_documents({"ogrenci_id": ogrenci_id, "kutu": {"$gte": 3}})
    test_sonuclari = await db.kitap_test_sonuclari.find({"ogrenci_id": ogrenci_id}).to_list(length=None)

    # Streak hesapla
    from datetime import timedelta
    simdi = datetime.utcnow()
    tarihler = sorted(set(l.get("tarih", "")[:10] for l in logs), reverse=True)
    streak = 0
    for i in range(90):
        gun = (simdi - timedelta(days=i)).strftime("%Y-%m-%d")
        if gun in tarihler:
            streak += 1
        elif i > 0:
            break

    # Bloom ortalaması
    bloom_ortalama = 0
    if test_sonuclari:
        bloom_ortalama = sum(t.get("basari_yuzdesi", 0) for t in test_sonuclari) / len(test_sonuclari)

    # Tamamlanan içerik sayısı
    tamamlanan_sayi = len(tamamlananlar)

    # Mevcut bölgeyi hesapla
    aktif_bolge = OKUMA_EVRENI_BOLGELER[0]
    for bolge in reversed(OKUMA_EVRENI_BOLGELER):
        if (tamamlanan_sayi >= bolge["min_kitap"] and
            kelime_ogrenilen >= bolge["min_kelime"] and
            streak >= bolge["min_streak"] and
            bloom_ortalama >= bolge["min_bloom"]):
            aktif_bolge = bolge
            break

    # Sıradaki bölge
    aktif_idx = next((i for i, b in enumerate(OKUMA_EVRENI_BOLGELER) if b["id"] == aktif_bolge["id"]), 0)
    sonraki_bolge = OKUMA_EVRENI_BOLGELER[aktif_idx + 1] if aktif_idx < len(OKUMA_EVRENI_BOLGELER) - 1 else None

    # Sonraki bölgeye ilerleme yüzdesi
    ilerleme = {}
    if sonraki_bolge:
        hedefler = [
            ("kitap", tamamlanan_sayi, sonraki_bolge["min_kitap"]),
            ("kelime", kelime_ogrenilen, sonraki_bolge["min_kelime"]),
            ("streak", streak, sonraki_bolge["min_streak"]),
            ("bloom", round(bloom_ortalama), sonraki_bolge["min_bloom"]),
        ]
        for ad, mevcut, hedef in hedefler:
            if hedef > 0:
                ilerleme[ad] = {"mevcut": mevcut, "hedef": hedef, "yuzde": min(100, round(mevcut / hedef * 100))}

    return {
        "ogrenci_id": ogrenci_id,
        "aktif_bolge": aktif_bolge,
        "aktif_bolge_idx": aktif_idx,
        "sonraki_bolge": sonraki_bolge,
        "ilerleme": ilerleme,
        "tum_bolgeler": OKUMA_EVRENI_BOLGELER,
        "istatistikler": {
            "tamamlanan": tamamlanan_sayi,
            "kelime": kelime_ogrenilen,
            "streak": streak,
            "bloom": round(bloom_ortalama),
        }
    }


@router.get("/ai/gelisim-simulasyon/{ogrenci_id}")
async def gelisim_simulasyon(ogrenci_id: str, current_user=Depends(get_current_user)):
    """Mevcut verilerden 6 aylık gelişim projeksiyonu üretir."""
    v = await get_ogrenci_ai_verileri(ogrenci_id)
    if not v:
        return {"hata": "Öğrenci verisi bulunamadı"}

    streak = v["streak"].get("mevcut", 0)
    avg_dk = v["okuma_ozet"].get("ort_gunluk_dk", 0)
    kelime_sayisi = await db.kelime_tekrar.count_documents({"ogrenci_id": ogrenci_id})
    test_kayitlar = await db.kitap_test_sonuclari.find({"ogrenci_id": ogrenci_id}).sort("tarih", -1).to_list(length=20)
    bloom_ort = 0
    if test_kayitlar:
        bloom_ort = round(sum(k.get("basari_yuzdesi", 0) for k in test_kayitlar) / len(test_kayitlar))

    # Hedef okuma süreleri → projeksiyon
    senaryolar = []
    for hedef_dk in [5, 10, 15, 20]:
        gunluk = hedef_dk
        aylik_dk = gunluk * 22  # Haftada 5 gün
        alti_ay_dk = aylik_dk * 6
        mevcut = avg_dk or 1
        artis_oran = min(80, round((hedef_dk / max(mevcut, 1) - 1) * 30 + 15))
        kelime_kazanim = round(hedef_dk * 0.8 * 180)  # dk * kelime_hizi * gun
        bloom_artis = min(95, bloom_ort + round(artis_oran * 0.4))
        kitap_sayisi = round(alti_ay_dk / 90)  # Ortalama 90dk / kitap
        senaryolar.append({
            "hedef_dk": hedef_dk,
            "artis_yuzdesi": artis_oran,
            "kelime_kazanim": kelime_kazanim,
            "tahmini_kitap": kitap_sayisi,
            "bloom_tahmini": bloom_artis,
            "alti_ay_toplam_dk": alti_ay_dk,
        })

    # 6 aylık aylık projeksiyon (seçili hedef = 10 dk)
    aylik_projeksiyon = []
    baz_bloom = bloom_ort
    baz_kelime = kelime_sayisi
    for ay in range(1, 7):
        baz_bloom = min(95, baz_bloom + round((95 - baz_bloom) * 0.12))
        baz_kelime = baz_kelime + round(10 * 0.8 * 22 * ay * 0.15)
        aylik_projeksiyon.append({
            "ay": ay,
            "bloom_tahmini": baz_bloom,
            "kelime_tahmini": baz_kelime,
            "okunan_dk": 10 * 22 * ay,
        })

    return {
        "mevcut": {
            "streak": streak,
            "avg_dk": avg_dk,
            "kelime": kelime_sayisi,
            "bloom_ort": bloom_ort,
        },
        "senaryolar": senaryolar,
        "aylik_projeksiyon": aylik_projeksiyon,
        "ozet_mesaj": f"Şu an günde ortalama {avg_dk} dk okuyorsun. 10 dk/gün hedefiyle 6 ayda yaklaşık %{senaryolar[1]['artis_yuzdesi']} gelişim sağlarsın!",
    }


@router.get("/ai/okuma-terapisi/{ogrenci_id}")
async def okuma_terapisi(ogrenci_id: str, current_user=Depends(get_current_user)):
    """Öğrenci verilerinden okuma güçlüğü sinyallerini tespit eder. TANI KOYMAZ, yönlendirir."""
    v = await get_ogrenci_ai_verileri(ogrenci_id)
    if not v:
        return {"sinyaller": [], "risk_seviyesi": "belirsiz", "oneri": "Veri yetersiz"}

    sinyaller = []
    risk_puan = 0

    # Streak düşüklüğü
    streak = v["streak"].get("mevcut", 0)
    if streak == 0:
        sinyaller.append({"tip": "motivasyon", "mesaj": "Son günlerde okuma aktivitesi yok", "agirlik": 2})
        risk_puan += 2

    # Okuma hızı analizi
    avg_dk = v["okuma_ozet"].get("ort_gunluk_dk", 0)
    if 0 < avg_dk < 5:
        sinyaller.append({"tip": "dikkat", "mesaj": "Çok kısa okuma süreleri (5 dk altı)", "agirlik": 3})
        risk_puan += 3

    # Test başarısı düşüklüğü
    test_kayitlar = await db.kitap_test_sonuclari.find({"ogrenci_id": ogrenci_id}).sort("tarih", -1).to_list(length=10)
    if test_kayitlar:
        bloom_ort = sum(k.get("basari_yuzdesi", 0) for k in test_kayitlar) / len(test_kayitlar)
        if bloom_ort < 40:
            sinyaller.append({"tip": "anlama", "mesaj": f"Anlama testlerinde düşük başarı (ort. %{round(bloom_ort)})", "agirlik": 4})
            risk_puan += 4
        # Bilgi ve kavrama basamaklarında bile düşüklük → potansiyel kelime zorluğu
        bilgi_sorulari = [k for k in test_kayitlar if k.get("taksonomi") in ["bilgi", "kavrama"]]
        if bilgi_sorulari:
            bilgi_ort = sum(k.get("dogru_mu", False) for k in bilgi_sorulari) / len(bilgi_sorulari) * 100
            if bilgi_ort < 50:
                sinyaller.append({"tip": "kelime_kacinma", "mesaj": "Temel anlama sorularında zorluk — kelime dağarcığı desteği gerekebilir", "agirlik": 3})
                risk_puan += 3

    # Kelime tekrar analizi
    kelime_sayisi = await db.kelime_tekrar.count_documents({"ogrenci_id": ogrenci_id})
    tekrar_yuksek = await db.kelime_tekrar.count_documents({"ogrenci_id": ogrenci_id, "tekrar_sayisi": {"$gte": 5}})
    if kelime_sayisi > 0 and tekrar_yuksek / max(kelime_sayisi, 1) > 0.4:
        sinyaller.append({"tip": "kelime_hafiza", "mesaj": "Kelimeleri hatırlamada tekrar eden güçlük", "agirlik": 2})
        risk_puan += 2

    # Okuma kayıtlarında geri dönüş / kısa oturum patikası
    okuma_log = await db.reading_logs.find({"ogrenci_id": ogrenci_id}).sort("tarih", -1).to_list(length=20)
    if len(okuma_log) >= 5:
        kisa_oturumlar = [l for l in okuma_log if (l.get("sure_dakika", 10)) < 3]
        if len(kisa_oturumlar) > len(okuma_log) * 0.5:
            sinyaller.append({"tip": "dikkat_suresi", "mesaj": "Okuma oturumları çok kısa kesiyor (dikkat dağılması belirtisi)", "agirlik": 3})
            risk_puan += 3

    # Risk seviyesi hesapla
    if risk_puan >= 8:
        risk_seviyesi = "yuksek"
        oneri = "Bu öğrenci için uzman yönlendirmesi düşünülebilir. Okuma güçlüğü belirtileri gözlemleniyor — lütfen bir okuma uzmanı veya rehber öğretmenle görüşün."
    elif risk_puan >= 4:
        risk_seviyesi = "orta"
        oneri = "Öğrencinin okuma alışkanlıkları dikkat gerektiriyor. Birebir destek ve farklı materyaller deneyin."
    elif risk_puan >= 1:
        risk_seviyesi = "dusuk"
        oneri = "Küçük sinyaller var. Düzenli takip ve teşvik yeterli olabilir."
    else:
        risk_seviyesi = "normal"
        oneri = "Belirgin bir okuma güçlüğü sinyali tespit edilmedi."

    return {
        "ogrenci_id": ogrenci_id,
        "risk_seviyesi": risk_seviyesi,
        "risk_puan": risk_puan,
        "sinyaller": sinyaller,
        "oneri": oneri,
        "uyari": "⚠️ Bu sistem TANI KOYMAZ. Sadece gözlem ve yönlendirme aracıdır.",
        "tarih": datetime.utcnow().isoformat(),
    }
