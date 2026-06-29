"""AI koçluk, DNA & motivasyon modülü (/ai/dna, /ai/kocluk/*, /ai/motivasyon/*).

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


AI_KOCLUK_SYSTEM_PROMPT = """Sen deneyimli bir ilkokul okuma koçusun. Türkiye'de çalışıyorsun. MEB Türkçe müfredatını ve Bloom taksonomisini biliyorsun.
Görevin: Verilen öğrenci verilerini analiz ederek kişiselleştirilmiş koçluk raporu üretmek.
DİL: Türkçe. Pozitif ve yapıcı dil kullan. Öğretmene yardımcı ol, öğrenciyi motive et.
FORMAT: Yanıtını SADECE JSON olarak ver, başka metin ekleme. Markdown code block kullanma."""


@router.get("/ai/dna/{ogrenci_id}")
async def get_okuma_dna(ogrenci_id: str, current_user=Depends(get_current_user)):
    """7 boyutlu Okuma DNA profili hesapla (Claude API kullanmaz — mevcut verilerden)."""
    v = await get_ogrenci_ai_verileri(ogrenci_id)
    if not v:
        raise HTTPException(status_code=404, detail="Öğrenci bulunamadı")

    ok = v["okuma_ozet"]
    # 1. Kelime Gücü (0-100)
    sinif_raw = v["ogrenci"].get("sinif", 3)
    try:
        sinif = int(sinif_raw)
    except (ValueError, TypeError):
        sinif = 3
    hedef_kelime = {1:150, 2:300, 3:500, 4:700, 5:1000, 6:1300, 7:1600, 8:2000}.get(sinif, 500)
    bilinen = await db.kelime_bankasi.count_documents({"ogrenci_id": ogrenci_id, "ogrenildi": True}) if await db.kelime_bankasi.count_documents({}) > 0 else int(hedef_kelime * 0.5)
    kelime_gucu = min(100, round(bilinen / hedef_kelime * 100))

    # 2. Akıcılık (0-100)
    wpm = v["analiz"].get("wpm", 0)
    norm_wpm = {1:50, 2:75, 3:95, 4:115, 5:130, 6:145, 7:155, 8:165}.get(sinif, 95)
    akicilik = min(100, round(wpm / norm_wpm * 100)) if wpm > 0 else 50

    # 3. Anlama Derinliği (0-100)
    bloom = v["analiz"].get("bloom", {})
    if bloom:
        anlama = round((bloom.get("bilgi",0)*0.1 + bloom.get("kavrama",0)*0.15 + bloom.get("uygulama",0)*0.2 + bloom.get("analiz",0)*0.25 + bloom.get("sentez",0)*0.15 + bloom.get("degerlendirme",0)*0.15))
    else:
        anlama = v["test"].get("ort_yuzde", 50)

    # 4. Dikkat Süresi (0-100)
    ort_dk = ok.get("ort_gunluk_dk", 0)
    dikkat = min(100, round(ort_dk / 20 * 100)) if ort_dk > 0 else 30

    # 5. Zorluk Toleransı (0-100)
    zorluk_tol = 50  # Varsayılan, zor metinlerdeki başarı verisi birikince geliştirilecek

    # 6. Kelime Tekrar İhtiyacı (0-100, yüksek = çok tekrara ihtiyacı var)
    tekrar_ihtiyac = max(0, 100 - kelime_gucu)

    # 7. Okuma Psikolojisi
    toplam_kitap = ok.get("kitap_sayisi", 0)
    streak_m = v["streak"].get("mevcut", 0)
    if toplam_kitap >= 3 and streak_m >= 5:
        psikoloji = "keşifçi"
    elif streak_m < 2 and ok.get("gun_sayisi", 0) < 5:
        psikoloji = "kararsız"
    else:
        psikoloji = "güvenli"

    # Profil tipi
    if akicilik > 70 and anlama < 50:
        profil_tipi = "hızlı_okuyucu"
    elif akicilik < 40 and anlama > 70:
        profil_tipi = "analitik_okuyucu"
    elif bloom and bloom.get("sentez", 0) > 60:
        profil_tipi = "hayalci_okuyucu"
    elif streak_m < 3 and ok.get("gun_sayisi", 0) < 10:
        profil_tipi = "başlangıç_okuyucu"
    else:
        profil_tipi = "dengeli_okuyucu"

    profil_label = {"hızlı_okuyucu": "📖 Hızlı Okuyucu", "analitik_okuyucu": "🔍 Analitik Okuyucu", "hayalci_okuyucu": "🌈 Hayalci Okuyucu", "başlangıç_okuyucu": "🌱 Başlangıç Okuyucu", "dengeli_okuyucu": "⚖️ Dengeli Okuyucu"}

    dna = {
        "ogrenci_id": ogrenci_id,
        "boyutlar": {
            "kelime_gucu": kelime_gucu,
            "akicilik": akicilik,
            "anlama_derinligi": anlama,
            "dikkat_suresi": dikkat,
            "zorluk_toleransi": zorluk_tol,
            "kelime_tekrar_ihtiyaci": tekrar_ihtiyac,
            "okuma_psikolojisi": psikoloji,
        },
        "profil_tipi": profil_tipi,
        "profil_label": profil_label.get(profil_tipi, "📖 Okuyucu"),
        "sinif": sinif,
        "son_guncelleme": datetime.utcnow().isoformat(),
    }

    # Cache'e kaydet
    await db.okuma_dna.update_one({"ogrenci_id": ogrenci_id}, {"$set": dna}, upsert=True)
    return dna


@router.post("/ai/kocluk/{ogrenci_id}")
async def ai_kocluk(ogrenci_id: str, current_user=Depends(get_current_user)):
    """Tam AI koçluk raporu (10 modül). 24 saat cache."""
    # Cache kontrolü
    cache = await db.ai_kocluk_cache.find_one({
        "ogrenci_id": ogrenci_id,
        "tarih": {"$gte": (datetime.utcnow() - timedelta(hours=AI_CACHE_HOURS)).isoformat()}
    })
    if cache:
        cache.pop("_id", None)
        return cache

    # Veri topla
    v = await get_ogrenci_ai_verileri(ogrenci_id)
    if not v or not v.get("ogrenci", {}).get("ad"):
        raise HTTPException(status_code=404, detail="Öğrenci bulunamadı")

    # DNA hesapla
    dna = None
    try:
        dna_response = await get_okuma_dna(ogrenci_id, current_user)
        dna = dna_response
    except:
        dna = {"profil_tipi": "bilinmiyor", "boyutlar": {}}

    import json as json_mod
    user_message = f"""Öğrenci verileri:
{json_mod.dumps(v, ensure_ascii=False, indent=2)}

Okuma DNA:
{json_mod.dumps(dna, ensure_ascii=False, indent=2) if dna else "Hesaplanamadı"}

Şu 8 modülü JSON olarak üret:
{{
  "durum_degerlendirmesi": {{"guclu_yonler": ["..."], "gelisim_alanlari": ["..."]}},
  "risk_analizi": {{"seviye": "düşük|orta|yüksek", "faktorler": ["..."], "aciliyet": "..."}},
  "mudahale_plani": {{"hafta_1": "...", "hafta_2": "...", "hafta_3": "...", "hafta_4": "..."}},
  "veliye_mesaj": "...",
  "haftalik_gorevler": [{{"gun": "Pazartesi", "gorev": "...", "bloom": "..."}}],
  "kitap_tavsiyeleri": [{{"ad": "...", "yazar": "...", "neden": "..."}}],
  "motivasyon_mesaji": "...",
  "kelime_mudahale": "...",
  "metin_recetesi": {{"paragraf_uzunlugu": "...", "soyutluk": "...", "aksiyon": "...", "hedef_kelime_orani": "..."}}
}}"""

    result = await call_claude(AI_KOCLUK_SYSTEM_PROMPT, user_message, model="sonnet", max_tokens=3000)

    if result.get("error"):
        raise HTTPException(status_code=503, detail=result["error"])

    rapor = {
        "id": str(uuid.uuid4()),
        "ogrenci_id": ogrenci_id,
        "dna": dna,
        "veriler": v,
        "ai_analiz": result.get("parsed") or result.get("text", ""),
        "ai_ham_metin": result.get("text", ""),
        "model": AI_DEFAULT_MODEL,
        "token": result.get("tokens", 0),
        "maliyet": result.get("maliyet", 0),
        "tarih": datetime.utcnow().isoformat(),
    }

    await db.ai_kocluk_cache.insert_one(rapor)
    rapor.pop("_id", None)
    return rapor


@router.get("/ai/kocluk/{ogrenci_id}/motivasyon")
async def ai_motivasyon(ogrenci_id: str, current_user=Depends(get_current_user)):
    """Günlük kişisel motivasyon mesajı (Haiku — hızlı ve ucuz)."""
    v = await get_ogrenci_ai_verileri(ogrenci_id)
    if not v:
        return {"mesaj": "Bugün okumak için harika bir gün! 📚"}

    ad = v["ogrenci"].get("ad", "Öğrenci")
    streak = v["streak"].get("mevcut", 0)
    bugun_dk = v["okuma_ozet"].get("ort_gunluk_dk", 0)

    prompt = f"{ad}, streak: {streak} gün, ortalama {bugun_dk} dk/gün okuyor. 1 cümle motivasyon mesajı yaz. Türkçe, sıcak, kişisel. Sadece mesaj metni ver, başka bir şey yazma."

    result = await call_claude("Sen çocuklara motivasyon veren sıcak bir okuma koçusun.", prompt, model="haiku", max_tokens=100)
    mesaj = result.get("text", f"Harika gidiyorsun {ad}! 🔥 Streak'in {streak} gün!")

    return {"mesaj": mesaj.strip().strip('"')}


@router.get("/ai/motivasyon/giris")
async def motivasyon_giris(current_user=Depends(get_current_user)):
    """
    Her girişte çağrılır.
    - Streak durumu + risk tespiti
    - Geçmiş performansa göre adaptif hedef önerisi (5/10/15 dk)
    - AI mesajı (varsa)
    """
    ogrenci_id = current_user.get("linked_id") or current_user.get("id")
    bugun = datetime.utcnow().strftime("%Y-%m-%d")
    dun = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")

    # Bugün zaten hedef seçilmiş mi?
    hedef_kayit = await db.motivasyon_hedefler.find_one({"ogrenci_id": ogrenci_id, "tarih": bugun})
    bugun_hedef = hedef_kayit.get("hedef_dk") if hedef_kayit else None

    # Streak hesapla
    son_7_gun = []
    for i in range(7):
        gun = (datetime.utcnow() - timedelta(days=i)).strftime("%Y-%m-%d")
        var = await db.okuma_kayitlari.find_one({
            "ogrenci_id": ogrenci_id,
            "tarih": {"$gte": gun, "$lt": (datetime.utcnow() - timedelta(days=i-1)).strftime("%Y-%m-%d")}
        })
        son_7_gun.append(bool(var))
    mevcut_streak = 0
    for g in son_7_gun:
        if g: mevcut_streak += 1
        else: break

    # Streak riski: dün okumadıysa ve streak > 0
    dun_okuma = await db.okuma_kayitlari.find_one({
        "ogrenci_id": ogrenci_id,
        "tarih": {"$gte": dun, "$lt": bugun}
    })
    streak_risk = mevcut_streak > 2 and not dun_okuma

    # Son 7 günün ortalama okuma süresi
    son_okumalar = await db.okuma_kayitlari.find(
        {"ogrenci_id": ogrenci_id}
    ).sort("tarih", -1).to_list(length=7)
    ort_sure = 0
    if son_okumalar:
        ort_sure = sum(k.get("sure_dakika", 0) for k in son_okumalar) / len(son_okumalar)

    # Adaptif hedef önerisi
    if ort_sure < 5:
        onerilen_hedef = 5
        hedef_label = "Küçük bir adım büyük fark yaratır!"
    elif ort_sure < 12:
        onerilen_hedef = 10
        hedef_label = "İyi gidiyorsun, biraz daha uzat!"
    else:
        onerilen_hedef = 15
        hedef_label = "Harika performans, zirvede kal!"

    # AI mesajı
    ad = current_user.get("ad", "")
    ai_mesaj = ""
    if GEMINI_API_KEY:
        try:
            prompt = f"""Öğrenci adı: {ad}, streak: {mevcut_streak} gün, ortalama okuma: {ort_sure:.0f} dk/gün.
Ona tek cümle, sıcak ve motive edici Türkçe bir mesaj yaz. Max 20 kelime."""
            r = await call_claude("Kısa ve motive edici.", prompt, model="haiku", max_tokens=60)
            ai_mesaj = r.get("text", "").strip()
        except Exception:
            pass

    if not ai_mesaj:
        # Mock mesajlar — streak'e göre
        if streak_risk:
            ai_mesaj = f"🔥 {mevcut_streak} günlük serinini korumak için bugün sadece 5 dakika oku!"
        elif mevcut_streak >= 7:
            ai_mesaj = f"Süper! {mevcut_streak} gün üst üste okudun, dur­ma! 🚀"
        elif mevcut_streak >= 3:
            ai_mesaj = f"🎯 {mevcut_streak} günlük seri harika gidiyor, devam et!"
        else:
            ai_mesaj = f"Merhaba {ad}! Bugün {onerilen_hedef} dakika okumaya ne dersin? 📖"

    return {
        "bugun_hedef": bugun_hedef,
        "onerilen_hedef": onerilen_hedef,
        "hedef_label": hedef_label,
        "streak": mevcut_streak,
        "streak_risk": streak_risk,
        "streak_mesaji": f"🔥 {mevcut_streak} günlük seriniz kırılmak üzere!" if streak_risk else "",
        "streak_alt_mesaj": "Bugün okuma yapmadın, hemen başla!" if streak_risk else "",
        "ai_mesaj": ai_mesaj,
        "ort_sure_dk": round(ort_sure, 1),
    }


@router.post("/ai/motivasyon/hedef-sec")
async def motivasyon_hedef_sec(request: Request, current_user=Depends(get_current_user)):
    """Öğrencinin seçtiği günlük hedefi kaydet."""
    body = await request.json()
    hedef_dk = int(body.get("hedef_dk", 10))
    if hedef_dk not in [5, 10, 15]:
        hedef_dk = 10
    ogrenci_id = current_user.get("linked_id") or current_user.get("id")
    bugun = datetime.utcnow().strftime("%Y-%m-%d")
    await db.motivasyon_hedefler.update_one(
        {"ogrenci_id": ogrenci_id, "tarih": bugun},
        {"$set": {"hedef_dk": hedef_dk, "tarih": bugun, "ogrenci_id": ogrenci_id}},
        upsert=True
    )
    return {"ok": True, "hedef_dk": hedef_dk}


@router.get("/ai/motivasyon/{ogrenci_id}")
async def ai_motivasyon(ogrenci_id: str, current_user=Depends(get_current_user)):
    """Giriş ekranı için kişiselleştirilmiş mikro hedef + motivasyon mesajı üretir."""
    from datetime import timedelta
    simdi = datetime.utcnow()

    # Son okuma kayıtları
    logs = await db.reading_logs.find({"ogrenci_id": ogrenci_id}).sort("tarih", -1).to_list(length=30)
    bugun = simdi.strftime("%Y-%m-%d")
    dun = (simdi - timedelta(days=1)).strftime("%Y-%m-%d")
    bugun_dk = sum(l.get("sure_dakika", 0) for l in logs if l.get("tarih", "").startswith(bugun))
    dun_dk = sum(l.get("sure_dakika", 0) for l in logs if l.get("tarih", "").startswith(dun))

    # Streak
    tarihler = sorted(set(l.get("tarih", "")[:10] for l in logs), reverse=True)
    streak = 0
    for i in range(60):
        gun = (simdi - timedelta(days=i)).strftime("%Y-%m-%d")
        if gun in tarihler:
            streak += 1
        elif i > 0:
            break

    # Ortalama günlük okuma (son 7 gün)
    son7 = [(simdi - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]
    ort_dk = round(sum(
        sum(l.get("sure_dakika", 0) for l in logs if l.get("tarih", "").startswith(g))
        for g in son7
    ) / 7)

    # Profil belirle
    user_data = await db.users.find_one({"id": ogrenci_id})
    ad = user_data.get("ad", "Okuyucu") if user_data else "Okuyucu"

    # Durum analizi
    streak_risk = streak > 0 and bugun_dk == 0  # Streak var ama bugün okumamış
    yeni_baslayanlar = streak == 0 and len(logs) < 3
    hedef_dk = max(5, min(30, ort_dk + 5)) if ort_dk > 0 else 10

    # Mikro hedef seç
    if bugun_dk >= hedef_dk:
        mikro_hedef = None  # Bugün tamamlandı
        durum = "tamamlandi"
    elif streak_risk:
        mikro_hedef = {"dk": max(5, hedef_dk - bugun_dk), "tip": "streak_koruma", "icon": "🔥"}
        durum = "streak_risk"
    elif yeni_baslayanlar:
        mikro_hedef = {"dk": 5, "tip": "baslangic", "icon": "🌱"}
        durum = "yeni"
    else:
        mikro_hedef = {"dk": max(5, hedef_dk - bugun_dk), "tip": "gunluk", "icon": "📚"}
        durum = "devam"

    # Mesaj üret (Gemini değil — hızlı olmalı, sabit mesaj havuzu)
    mesajlar = {
        "tamamlandi": [
            f"Harika {ad}! Bugünkü hedefinizi tamamladınız 🎉",
            f"Mükemmel! Bugün {bugun_dk} dakika okudunuz. Devam edin! 💪",
            f"Süpersin {ad}! Bugün harika bir okuma günüydü 📚",
        ],
        "streak_risk": [
            f"🔥 {streak} günlük serinizi koruyun! Sadece {mikro_hedef['dk'] if mikro_hedef else 5} dakika daha gerekiyor.",
            f"Dikkat {ad}! {streak} günlük seriniz tehlikede. Hemen okumaya başla! 🔥",
            f"Bugün henüz okumadınız. {streak} günlük serinizi kırmayın! ⚡",
        ],
        "yeni": [
            f"Merhaba {ad}! Okuma yolculuğuna hoş geldin 🌱",
            f"Başlamak için en iyi zaman şimdi! Sadece 5 dakika ile başla 📖",
            f"Her büyük okuyucu bir ilk sayfayla başladı. Seninki hangisi? 🌟",
        ],
        "devam": [
            f"Bugün {hedef_dk} dakika okuma hedefin var {ad}! Hadi başlayalım 📚",
            f"{'Dün ' + str(dun_dk) + ' dakika okudun.' if dun_dk > 0 else 'Her gün biraz daha ilerle.'} Bugün {mikro_hedef['dk'] if mikro_hedef else hedef_dk} dakika kaldı!",
            f"{'🔥 ' + str(streak) + ' günlük serin devam ediyor!' if streak > 1 else ''} Bugünkü hedefe ulaş! 💫",
        ],
    }

    import random as _random
    mesaj = _random.choice(mesajlar.get(durum, mesajlar["devam"]))

    return {
        "ad": ad,
        "durum": durum,
        "mesaj": mesaj,
        "mikro_hedef": mikro_hedef,
        "streak": streak,
        "bugun_dk": bugun_dk,
        "hedef_dk": hedef_dk,
        "ort_dk": ort_dk,
    }
