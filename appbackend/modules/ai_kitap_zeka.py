"""AI kitap zekası modülü (/ai/kitap-zeka/*, /ai/kitap-zeka-haritasi, /ai/kitap-oyun).

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


ZEKA_BOYUTLARI = ["soyutluk", "kelime_zorlugu", "hayal_gucu", "felsefi_derinlik", "aksiyon", "duygusal_yogunluk", "hedef_kelime_yogunlugu"]


def _dna_ile_kitap_eslesme(dna: dict, profil: dict) -> float:
    """Öğrencinin DNA'sı ile kitap profilinin uyum skoru (0-100)."""
    if not dna or not profil:
        return 50.0
    # DNA boyutları → kitap boyutu eşleştirmesi
    eslesmeler = [
        (dna.get("kelime_gucu", 50), profil.get("kelime_zorlugu", 5), False),      # kelime gücü yüksekse zor kitap iyi
        (dna.get("anlama_derinligi", 50), profil.get("soyutluk", 5), False),         # anlama derinliği yüksekse soyut kitap iyi
        (dna.get("anlama_derinligi", 50), profil.get("felsefi_derinlik", 5), False), # aynı
        (dna.get("akicilik", 50), profil.get("aksiyon", 5), True),                   # akıcı okuyucu aksiyon kitabı sever
    ]
    toplam = 0.0
    for dna_val, kitap_val, dogrusal in eslesmeler:
        kitap_norm = kitap_val * 10  # 1-10 → 0-100
        if dogrusal:
            fark = abs(dna_val - kitap_norm)
            toplam += max(0, 100 - fark)
        else:
            # DNA yüksekse yüksek kitap değeri iyi
            uyum = min(dna_val, kitap_norm) / max(dna_val, kitap_norm, 1) * 100
            toplam += uyum
    return round(toplam / len(eslesmeler), 1)


@router.post("/ai/kitap-zeka/analiz")
async def kitap_zeka_analiz(request: Request, current_user=Depends(get_current_user)):
    """
    Kitap adı ve yazardan 7 boyutlu Zekâ Haritası üret.
    Varsa cache'den döner, yoksa Claude ile üretir.
    """
    body = await request.json()
    kitap_adi = body.get("kitap_adi", "").strip()
    yazar = body.get("yazar", "").strip()
    kitap_id = body.get("kitap_id", "")
    sinif = int(body.get("sinif", 3))

    if not kitap_adi:
        raise HTTPException(status_code=400, detail="Kitap adı gerekli")

    # Cache kontrolü
    cache_key = f"{kitap_adi.lower()}_{yazar.lower()}"
    mevcut = await db.kitap_zeka_profilleri.find_one({"cache_key": cache_key})
    if mevcut:
        mevcut.pop("_id", None)
        return mevcut

    # Claude ile 7 boyut analizi
    boyutlar = {}
    ai_aciklama = ""

    if GEMINI_API_KEY:
        try:
            prompt = f"""Kitap: "{kitap_adi}" — Yazar: {yazar or 'bilinmiyor'} — Hedef sınıf: {sinif}

Bu kitabı 7 boyutta 1-10 arası puan ver (1=çok düşük, 10=çok yüksek):
1. soyutluk — Soyut kavramlar, metafor kullanımı
2. kelime_zorlugu — Kelime hazinesi güçlüğü
3. hayal_gucu — Hayal gücü ve yaratıcılık gerektirme
4. felsefi_derinlik — Felsefi ve ahlaki sorular
5. aksiyon — Aksiyon, macera, hız
6. duygusal_yogunluk — Duygusal etki, empati
7. hedef_kelime_yogunlugu — MEB hedef kelime yoğunluğu

Ayrıca 1 cümle Türkçe açıklama yaz.

SADECE JSON döndür:
{{"soyutluk":5,"kelime_zorlugu":4,"hayal_gucu":8,"felsefi_derinlik":3,"aksiyon":7,"duygusal_yogunluk":6,"hedef_kelime_yogunlugu":5,"aciklama":"..."}}"""

            result = await call_claude("Sen bir kitap analisti ve eğitim uzmanısın.", prompt, model="haiku", max_tokens=300)
            if result.get("parsed"):
                p = result["parsed"]
                boyutlar = {k: int(p.get(k, 5)) for k in ZEKA_BOYUTLARI}
                ai_aciklama = p.get("aciklama", "")
        except Exception as e:
            logging.warning(f"Kitap zeka analiz hatası: {e}")

    # Fallback — kural bazlı tahmin
    if not boyutlar:
        import random
        random.seed(hash(kitap_adi))
        boyutlar = {k: random.randint(3, 8) for k in ZEKA_BOYUTLARI}
        ai_aciklama = f"'{kitap_adi}' için otomatik profil oluşturuldu."

    # Genel zorluk skoru (1-10)
    genel_zorluk = round(sum([boyutlar["soyutluk"], boyutlar["kelime_zorlugu"], boyutlar["felsefi_derinlik"]]) / 3, 1)

    kayit = {
        "id": str(uuid.uuid4()),
        "cache_key": cache_key,
        "kitap_adi": kitap_adi,
        "yazar": yazar,
        "kitap_id": kitap_id,
        "sinif": sinif,
        "boyutlar": boyutlar,
        "genel_zorluk": genel_zorluk,
        "aciklama": ai_aciklama,
        "olusturma_tarihi": datetime.utcnow().isoformat(),
    }
    await db.kitap_zeka_profilleri.insert_one(kayit)
    kayit.pop("_id", None)
    return kayit


@router.get("/ai/kitap-zeka/tavsiye")
async def kitap_zeka_tavsiye(current_user=Depends(get_current_user)):
    """
    Öğrencinin DNA profiline göre en uygun kitapları öner.
    kitap_zeka_profilleri + okuma_kayitlari + dna karşılaştırması.
    """
    ogrenci_id = current_user.get("linked_id") or current_user.get("id")

    # DNA profili
    dna = await db.okuma_dna.find_one({"ogrenci_id": ogrenci_id})
    dna_boyutlar = dna or {}

    # Daha önce okunanlar
    okunanlar = await db.okuma_kayitlari.distinct("kitap_adi", {"ogrenci_id": ogrenci_id})
    okunanlar_set = {k.lower() for k in okunanlar if k}

    # Tüm profilli kitaplar
    tum_profiller = await db.kitap_zeka_profilleri.find({}).to_list(length=100)

    # Her kitap için uyum skoru hesapla
    skorlu = []
    for p in tum_profiller:
        p.pop("_id", None)
        if p["kitap_adi"].lower() in okunanlar_set:
            continue  # zaten okunan
        uyum = _dna_ile_kitap_eslesme(dna_boyutlar, p.get("boyutlar", {}))
        skorlu.append({**p, "uyum_skoru": uyum})

    # Uyum skoruna göre sırala, top 5
    skorlu.sort(key=lambda x: x["uyum_skoru"], reverse=True)
    return {"tavsiyeler": skorlu[:5], "dna_var": bool(dna)}


@router.get("/ai/kitap-zeka/profil/{kitap_id}")
async def kitap_zeka_profil(kitap_id: str, current_user=Depends(get_current_user)):
    """Kaydedilmiş kitap zekâ profilini getir."""
    profil = await db.kitap_zeka_profilleri.find_one({"kitap_id": kitap_id})
    if not profil:
        profil = await db.kitap_zeka_profilleri.find_one({"id": kitap_id})
    if not profil:
        raise HTTPException(status_code=404, detail="Profil bulunamadı")
    profil.pop("_id", None)
    return profil


@router.get("/ai/kitap-zeka/liste")
async def kitap_zeka_liste(current_user=Depends(get_current_user)):
    """Tüm profilli kitapları listele (admin/öğretmen)."""
    profiller = await db.kitap_zeka_profilleri.find({}).sort("olusturma_tarihi", -1).to_list(length=200)
    for p in profiller:
        p.pop("_id", None)
    return {"profiller": profiller}


@router.post("/ai/kitap-zeka-haritasi")
async def kitap_zeka_haritasi(req: Request, current_user=Depends(get_current_user)):
    """Her kitap için 7 boyutlu AI profil üretir."""
    data = await req.json()
    kitap_adi = data.get("kitap_adi", "")
    yazar = data.get("yazar", "")
    sinif = data.get("sinif", 3)
    icerik_id = data.get("icerik_id", "")

    # Cache (kalıcı — kitap değişmez)
    cache = await db.kitap_zeka_haritasi.find_one({"icerik_id": icerik_id})
    if cache:
        cache.pop("_id", None)
        return cache

    # Metin varsa ekle
    metin_ek = ""
    icerik = await db.gelisim_icerik.find_one({"id": icerik_id})
    if icerik and icerik.get("okuma_metni"):
        metin_ek = f"\n\nMetin özeti (ilk 1000 kelime):\n{icerik['okuma_metni'][:2000]}"

    prompt = f"""Sen bir çocuk edebiyatı analistisin. "{kitap_adi}"{f" - {yazar}" if yazar else ""} için 7 boyutlu profil oluştur.{metin_ek}

Her boyutu 1-10 arasında puan ver. SADECE JSON döndür:
{{
  "kitap_adi": "{kitap_adi}",
  "boyutlar": {{
    "soyutluk": {{"puan": 5, "aciklama": "..."}},
    "kelime_zorlugu": {{"puan": 5, "aciklama": "..."}},
    "hayal_gucu": {{"puan": 5, "aciklama": "..."}},
    "felsefi_derinlik": {{"puan": 5, "aciklama": "..."}},
    "aksiyon": {{"puan": 5, "aciklama": "..."}},
    "duygusal_yogunluk": {{"puan": 5, "aciklama": "..."}},
    "hedef_kelime_yogunlugu": {{"puan": 5, "aciklama": "..."}}
  }},
  "sinif_uyumu": {sinif},
  "tavsiye_profil": "Bu kitap hangi öğrenciye uygundur? (2-3 cümle)",
  "tur_etiketleri": ["macera", "arkadaşlık"],
  "okuma_suresi_dk": 30
}}"""

    try:
        raw = await _gemini_call(prompt, max_tokens=1000)
        import json as _json, re as _re
        raw = raw.strip()
        if "```" in raw:
            m = _re.search(r"```(?:json)?\s*([\s\S]*?)```", raw)
            raw = m.group(1).strip() if m else _re.sub(r"```(?:json)?", "", raw).replace("```", "").strip()
        bs = raw.find("{"); be = raw.rfind("}")
        if bs != -1 and be != -1: raw = raw[bs:be+1]
        raw = _re.sub(r",\s*([}\]])", r"\1", raw)
        result = _json.loads(raw)
    except Exception as e:
        logging.error(f"[ZEKA-HARITA] Hata: {e}")
        result = {
            "kitap_adi": kitap_adi,
            "boyutlar": {
                "soyutluk": {"puan": 5, "aciklama": "Orta düzey soyut kavramlar içeriyor"},
                "kelime_zorlugu": {"puan": 5, "aciklama": "Yaş grubuna uygun kelime zenginliği"},
                "hayal_gucu": {"puan": 6, "aciklama": "Hayal gücünü geliştiren sahneler mevcut"},
                "felsefi_derinlik": {"puan": 4, "aciklama": "Temel değer sorgulamaları var"},
                "aksiyon": {"puan": 6, "aciklama": "Tempolu ve heyecanlı sahneler"},
                "duygusal_yogunluk": {"puan": 7, "aciklama": "Güçlü duygusal bağ kurduruyor"},
                "hedef_kelime_yogunlugu": {"puan": 5, "aciklama": "MEB müfredatına uygun kelimeler"}
            },
            "sinif_uyumu": sinif,
            "tavsiye_profil": "Okuma alışkanlığı kazanmaya başlayan, macera seven öğrencilere uygundur.",
            "tur_etiketleri": ["macera", "gelişim", "arkadaşlık"],
            "okuma_suresi_dk": sinif * 8
        }

    result["icerik_id"] = icerik_id
    result["olusturma_tarihi"] = datetime.utcnow().isoformat()
    await db.kitap_zeka_haritasi.update_one(
        {"icerik_id": icerik_id}, {"$set": result}, upsert=True
    )
    return result


@router.post("/ai/kitap-oyun")
async def kitap_oyun_uret(req: Request, current_user=Depends(get_current_user)):
    """Kitap/metin içeriğinden oyun soruları üretir."""
    data = await req.json()
    kitap_adi = data.get("kitap_adi", "")
    icerik_id = data.get("icerik_id", "")
    oyun_turu = data.get("tur", "karakter_tahmini")  # karakter_tahmini, hikaye_devam, bosluk, eslestirme
    sinif = data.get("sinif", 3)

    # Metni al
    metin = ""
    icerik = await db.gelisim_icerik.find_one({"id": icerik_id})
    if icerik:
        metin = icerik.get("okuma_metni", "") or icerik.get("aciklama", "")
    if not metin:
        return {"oyun": None, "mesaj": "İçerik metni bulunamadı"}

    metin_kisalt = metin[:2500]

    if oyun_turu == "karakter_tahmini":
        prompt = f""""{kitap_adi}" metninden karakter tahmini oyunu oluştur.

Metin: {metin_kisalt}

SADECE JSON döndür. Metindeki gerçek karakterleri kullan:
{{
  "tur": "karakter_tahmini",
  "baslik": "🎭 Kim O?",
  "aciklama": "İpuçlarından karakteri bul!",
  "sorular": [
    {{
      "ipuclari": ["İpucu 1", "İpucu 2", "İpucu 3"],
      "dogru_karakter": "...",
      "secenekler": ["...", "...", "...", "..."]
    }}
  ],
  "xp": 8
}}"""

    elif oyun_turu == "hikaye_devam":
        prompt = f""""{kitap_adi}" metninden hikâye devam ettirme oyunu oluştur.

Metin: {metin_kisalt}

SADECE JSON döndür:
{{
  "tur": "hikaye_devam",
  "baslik": "📖 Hikâye Devam Ediyor",
  "aciklama": "Doğru devamı seç!",
  "sorular": [
    {{
      "metin_parcasi": "Metinden alınan bir paragraf...",
      "soru": "Bundan sonra ne oldu?",
      "secenekler": ["A seçeneği", "B seçeneği", "C seçeneği", "D seçeneği"],
      "dogru_idx": 0,
      "aciklama": "Neden bu doğru?"
    }}
  ],
  "xp": 10
}}"""

    elif oyun_turu == "eslestirme":
        prompt = f""""{kitap_adi}" metninden karakter-özellik eşleştirme oyunu oluştur.

Metin: {metin_kisalt}

SADECE JSON döndür:
{{
  "tur": "eslestirme",
  "baslik": "🎲 Kim Nasıl?",
  "aciklama": "Karakterleri özellikleriyle eşleştir!",
  "ciftler": [
    {{"sol": "Karakter adı", "sag": "Özelliği/yaptığı şey"}},
    {{"sol": "...", "sag": "..."}},
    {{"sol": "...", "sag": "..."}},
    {{"sol": "...", "sag": "..."}}
  ],
  "xp": 6
}}"""

    else:  # bosluk
        prompt = f""""{kitap_adi}" metninden boşluk doldurma oyunu oluştur. Metinden gerçek cümleler kullan.

Metin: {metin_kisalt}

SADECE JSON döndür:
{{
  "tur": "bosluk_doldurma",
  "baslik": "⬜ Boşluğu Doldur",
  "aciklama": "Metindeki eksik kelimeyi bul!",
  "sorular": [
    {{
      "cumle_bos": "Metinden alınan cümle ___ kelime yerine boş",
      "dogru": "doğru kelime",
      "secenekler": ["doğru kelime", "yanlış1", "yanlış2", "yanlış3"]
    }}
  ],
  "xp": 7
}}"""

    try:
        raw = await _gemini_call(prompt, max_tokens=1200)
        import json as _json, re as _re
        raw = raw.strip()
        if "```" in raw:
            m = _re.search(r"```(?:json)?\s*([\s\S]*?)```", raw)
            raw = m.group(1).strip() if m else _re.sub(r"```(?:json)?", "", raw).replace("```", "").strip()
        bs = raw.find("{"); be = raw.rfind("}")
        if bs != -1 and be != -1: raw = raw[bs:be+1]
        raw = _re.sub(r",\s*([}\]])", r"\1", raw)
        result = _json.loads(raw)
        return {"oyun": result}
    except Exception as e:
        logging.error(f"[KITAP-OYUN] Hata: {e}")
        return {"oyun": None, "mesaj": f"Oyun üretilemedi: {str(e)}"}
