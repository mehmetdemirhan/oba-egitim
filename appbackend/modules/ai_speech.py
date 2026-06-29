"""AI konuşma/okuma analizi modülü (/ai/speech/*).

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


SPEECH_OKUMA_METİNLERİ = {
    1: [
        {"id": "s1_1", "baslik": "Küçük Kedi", "metin": "Küçük kedi bahçede oynadı. Güneş parlıyordu. Kedi mutluydu.", "kelime_sayisi": 10, "sinif": 1},
        {"id": "s1_2", "baslik": "Renkli Balonlar", "metin": "Ali kırmızı balon aldı. Ayşe sarı balon aldı. İkisi de çok sevindi.", "kelime_sayisi": 12, "sinif": 1},
    ],
    2: [
        {"id": "s2_1", "baslik": "Yağmur", "metin": "Sabah kalktığımda pencereden baktım. Dışarıda yağmur yağıyordu. Annem şemsiyemi hazırladı ve okula gittim.", "kelime_sayisi": 20, "sinif": 2},
        {"id": "s2_2", "baslik": "Kitap Kurdu", "metin": "Her gün en az bir kitap okuyorum. Kitaplar bana yeni dünyalar açıyor. En sevdiğim yer kütüphane.", "kelime_sayisi": 18, "sinif": 2},
    ],
    3: [
        {"id": "s3_1", "baslik": "Ormanda Bir Gün", "metin": "Ormanın içinde yürürken ağaçların arasından süzülen güneş ışığını seyrettim. Kuşlar şakıyor, yapraklar hışırdıyordu. Bu sessizlik içinde kendimi huzurlu hissettim.", "kelime_sayisi": 30, "sinif": 3},
        {"id": "s3_2", "baslik": "Dürüstlük", "metin": "Pazarda yürürken yerde bir cüzdan buldum. İçinde para ve kimlik vardı. Hemen karakola götürdüm. Görevli bana teşekkür etti ve sahibini bulacaklarını söyledi.", "kelime_sayisi": 32, "sinif": 3},
    ],
    4: [
        {"id": "s4_1", "baslik": "Göç Eden Kuşlar", "metin": "Her sonbahar leylekler uzun bir yolculuğa çıkar. Binlerce kilometre uçarak sıcak ülkelere göç ederler. Pusula gibi çalışan içgüdüleri sayesinde yollarını şaşırmazlar. Bu muhteşem yolculuk nesiller boyunca sürmektedir.", "kelime_sayisi": 38, "sinif": 4},
    ],
    5: [
        {"id": "s5_1", "baslik": "Anadolu Medeniyetleri", "metin": "Anadolu, tarihin en eski medeniyetlerine ev sahipliği yapmıştır. Hitit, Frigya, Lidya ve daha pek çok uygarlık bu topraklarda yaşamış, eserler bırakmıştır. Bu zengin miras günümüze kadar ulaşmıştır.", "kelime_sayisi": 35, "sinif": 5},
    ],
}


def _speech_mock_analiz(transkript: str, beklenen_metin: str, sure_sn: float, sinif: int) -> dict:
    """Web Speech API transkriptini beklenen metinle karşılaştırarak analiz üret."""
    import difflib
    import re

    def normalize(s):
        """Noktalama ve büyük/küçük harf normalize et."""
        s = s.lower()
        s = re.sub(r'[.,!?;:"\'-]', '', s)
        return s.split()

    b_kelimeler = normalize(beklenen_metin)
    gercek_transkript = transkript.strip() if transkript else ""

    # Transkript yoksa (kullanıcı hiç okumadı) — düşük skor
    if not gercek_transkript:
        return {
            "transkript": "",
            "telaffuz_skoru": 0,
            "akicilik_skoru": 0,
            "wpm": 0,
            "norm_wpm": {1:50,2:75,3:95,4:115,5:130}.get(sinif,95),
            "duraklama_sayisi": 0,
            "tonlama_skoru": 0,
            "vurgu_skoru": 0,
            "genel_skor": 0,
            "seviye": "geliştirilmeli",
            "guclu_yonler": [],
            "gelisim_alanlari": ["Okumaya başla — mikrofon sesi almadı"],
            "telaffuz_hatalar": [],
            "mock": True,
        }

    t_kelimeler = normalize(gercek_transkript)

    # ── Kelime bazlı diff ile yanlış/atlanmış kelimeleri bul ──
    matcher = difflib.SequenceMatcher(None, b_kelimeler, t_kelimeler, autojunk=False)
    dogru = 0
    yanlis_kelimeler = []
    atlanan_kelimeler = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            dogru += (i2 - i1)
        elif tag == "replace":
            # Beklenen kelimeler yanlış okunmuş
            for k in b_kelimeler[i1:i2]:
                yanlis_kelimeler.append(k)
        elif tag == "delete":
            # Beklenen kelimeler hiç okunmamış
            for k in b_kelimeler[i1:i2]:
                atlanan_kelimeler.append(k)

    toplam = len(b_kelimeler)
    telaffuz_skoru = round((dogru / toplam) * 100) if toplam > 0 else 0

    # Yanlış okunan kelimelerin orijinal (normalize edilmemiş) hallerini bul
    b_orijinal = beklenen_metin.split()
    telaffuz_hata_listesi = []
    for yanlis in set(yanlis_kelimeler + atlanan_kelimeler):
        # Orijinal metinde bu kelimeye yakın olanı bul
        for kel in b_orijinal:
            if normalize(kel) and normalize(kel)[0] == yanlis:
                telaffuz_hata_listesi.append(kel.strip('.,!?;:"\'-'))
                break
        else:
            telaffuz_hata_listesi.append(yanlis)

    # ── WPM hesapla ──
    sure_dk = max(sure_sn / 60, 0.1)
    # Transkriptteki kelime sayısından WPM
    wpm = round(len(t_kelimeler) / sure_dk)
    norm = {1: 50, 2: 75, 3: 95, 4: 115, 5: 130, 6: 145, 7: 155, 8: 165}.get(sinif, 95)
    akicilik_skoru = min(100, round(wpm / norm * 100))

    # ── Duraksama tahmini — WPM'e göre ──
    duraklama_sayisi = max(0, int((norm - wpm) / 15)) if wpm < norm else 0

    # ── Tonlama: noktalama işaretlerinde durup durmadığına bakılamaz,
    #    ancak cümle sonlarındaki kelime oranına bak ──
    noktalama_kelimeler = [w for w in beklenen_metin.split() if w[-1] in '.!?,;' if len(w) > 1]
    tonlama_skoru = min(100, telaffuz_skoru + 3)
    vurgu_skoru = min(100, akicilik_skoru + 2)

    seviye = "çok iyi" if telaffuz_skoru >= 85 else "iyi" if telaffuz_skoru >= 70 else "orta" if telaffuz_skoru >= 55 else "geliştirilmeli"

    guclu = []
    gelisim = []
    if telaffuz_skoru >= 80: guclu.append("Kelime telaffuzu başarılı")
    if akicilik_skoru >= 80: guclu.append("Okuma hızı sınıf normuna uygun")
    if len(telaffuz_hata_listesi) == 0 and telaffuz_skoru >= 70: guclu.append("Tüm kelimeleri doğru okudun")
    if akicilik_skoru < 70: gelisim.append(f"Okuma hızını artır (hedef: {norm} kelime/dk)")
    if len(telaffuz_hata_listesi) > 3: gelisim.append("Yanlış okunan kelimeleri tekrar çalış")
    if len(atlanan_kelimeler) > 2: gelisim.append("Bazı kelimeleri atladın, dikkatli oku")

    return {
        "transkript": gercek_transkript,
        "telaffuz_skoru": telaffuz_skoru,
        "akicilik_skoru": akicilik_skoru,
        "wpm": wpm,
        "norm_wpm": norm,
        "duraklama_sayisi": duraklama_sayisi,
        "tonlama_skoru": tonlama_skoru,
        "vurgu_skoru": vurgu_skoru,
        "genel_skor": round((telaffuz_skoru * 0.6 + akicilik_skoru * 0.4)),
        "seviye": seviye,
        "guclu_yonler": guclu,
        "gelisim_alanlari": gelisim,
        "telaffuz_hatalar": telaffuz_hata_listesi[:8],  # max 8 kelime göster
        "atlanan_kelimeler": atlanan_kelimeler[:5],
        "mock": False,  # Artık gerçek transkript analizi
    }


@router.get("/ai/speech/metinler")
async def speech_okuma_metinleri(sinif: int = 3, current_user=Depends(get_current_user)):
    """Sınıfa göre sesli okuma metinleri getir."""
    metinler = SPEECH_OKUMA_METİNLERİ.get(sinif, SPEECH_OKUMA_METİNLERİ.get(3, []))
    if not metinler:
        # En yakın sınıfı bul
        for s in range(sinif, 0, -1):
            if s in SPEECH_OKUMA_METİNLERİ:
                metinler = SPEECH_OKUMA_METİNLERİ[s]
                break
    return {"metinler": metinler, "sinif": sinif}


@router.post("/ai/speech/analiz")
async def speech_analiz(
    ses_dosyasi: UploadFile = File(None),
    metin_id: str = Form(""),
    ogrenci_id: str = Form(""),
    sure_sn: float = Form(30.0),
    sinif: int = Form(3),
    transkript_input: str = Form(""),  # Web Speech API'den gelen transkript
    current_user=Depends(get_current_user)
):
    """Sesli okuma kaydını analiz et: WPM + telaffuz + tonlama + duraklama."""
    # Hedef metni bul
    beklenen_metin = ""
    metin_baslik = ""
    for s_list in SPEECH_OKUMA_METİNLERİ.values():
        for m in s_list:
            if m["id"] == metin_id:
                beklened_metin = m["metin"]
                beklenen_metin = m["metin"]
                metin_baslik = m["baslik"]
                sinif = m.get("sinif", sinif)
                break

    transkript = transkript_input.strip()  # Web Speech API'den gelen
    whisper_kullanildi = False

    # Whisper API — varsa kullan
    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
    if ses_dosyasi and OPENAI_API_KEY:
        try:
            ses_bytes = await ses_dosyasi.read()
            # Dosya uzantısını ve mime type'ı belirle
            filename = ses_dosyasi.filename or "ses.webm"
            content_type = ses_dosyasi.content_type or "audio/webm"
            # Whisper desteklenen formatlar: mp4, webm, mp3, wav, m4a, ogg
            if "mp4" in content_type or filename.endswith(".mp4"):
                mime = "audio/mp4"
                ext = "mp4"
            else:
                mime = "audio/webm"
                ext = "webm"
            async with httpx.AsyncClient(timeout=90.0) as c:
                resp = await c.post(
                    "https://api.openai.com/v1/audio/transcriptions",
                    headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
                    files={"file": (f"ses.{ext}", ses_bytes, mime)},
                    data={"model": "whisper-1", "language": "tr"},
                )
                if resp.status_code == 200:
                    transkript = resp.json().get("text", "")
                    whisper_kullanildi = True
                else:
                    logging.warning(f"Whisper API yanıt: {resp.status_code} — {resp.text[:200]}")
        except Exception as e:
            logging.warning(f"Whisper API hatası: {e}")

    # Analiz
    analiz = _speech_mock_analiz(transkript, beklenen_metin, sure_sn, sinif)
    analiz["whisper_kullanildi"] = whisper_kullanildi

    # Claude ile derin analiz (API key varsa)
    if GEMINI_API_KEY and beklenen_metin and transkript:
        ai_prompt = f"""Öğrenci okuma analizi (Sınıf: {sinif}):

Beklenen metin: {beklenen_metin}
Öğrenci okuması (transkript): {transkript}
Süre: {sure_sn:.0f} saniye
WPM: {analiz['wpm']}

Analiz et ve şu JSON'u döndür:
{{
  "guclu_yonler": ["...", "..."],
  "gelisim_alanlari": ["...", "..."],
  "ogretmen_notu": "Öğretmene 1-2 cümle öneri",
  "ogrenci_mesaj": "Öğrenciye motive edici 1 cümle (sen diliyle)",
  "telaffuz_hatalar": ["yanlış okunan kelime varsa listele"],
  "tonlama_degerlendirme": "iyi/orta/geliştirilmeli"
}}

SADECE JSON döndür."""
        ai_result = await call_claude(
            "Sen ilkokul Türkçe okuma uzmanısın. Çocukların okuma becerilerini değerlendirirsin.",
            ai_prompt, model="haiku", max_tokens=500
        )
        if ai_result.get("parsed"):
            p = ai_result["parsed"]
            analiz["guclu_yonler"] = p.get("guclu_yonler", analiz["guclu_yonler"])
            analiz["gelisim_alanlari"] = p.get("gelisim_alanlari", analiz["gelisim_alanlari"])
            analiz["ogretmen_notu"] = p.get("ogretmen_notu", "")
            analiz["ogrenci_mesaj"] = p.get("ogrenci_mesaj", "")
            analiz["telaffuz_hatalar"] = p.get("telaffuz_hatalar", [])
            analiz["tonlama_degerlendirme"] = p.get("tonlama_degerlendirme", "")
            analiz["mock"] = False

    # Varsayılan mesajlar (AI yoksa)
    if "ogretmen_notu" not in analiz:
        analiz["ogretmen_notu"] = f"Öğrenci {analiz['wpm']} kelime/dk hızında okudu. " + (
            "Akıcılığını artırmak için tekrarlı okuma egzersizleri önerilebilir." if analiz["akicilik_skoru"] < 70
            else "Okuma hızı sınıf normuna uygun."
        )
    if "ogrenci_mesaj" not in analiz:
        mesajlar = {
            "çok iyi": "Harika okudun! Sen gerçek bir okuma şampiyonusun! 🏆",
            "iyi": "Çok güzel okudun! Her gün biraz daha iyileşiyorsun! ⭐",
            "orta": "İyi bir başlangıç! Pratik yaptıkça daha da güzelleşecek! 💪",
            "geliştirilmeli": "Okumaya devam et, her gün daha iyisi olacaksın! 🌱",
        }
        analiz["ogrenci_mesaj"] = mesajlar.get(analiz["seviye"], "Harika iş çıkardın!")

    # Veritabanına kaydet
    gercek_ogrenci_id = ogrenci_id or current_user.get("linked_id") or current_user.get("id")
    kayit_id = str(uuid.uuid4())
    await db.speech_logs.insert_one({
        "id": kayit_id,
        "ogrenci_id": gercek_ogrenci_id,
        "metin_id": metin_id,
        "metin_baslik": metin_baslik,
        "metin": beklenen_metin,
        "sinif": sinif,
        "sure_sn": sure_sn,
        "analiz": analiz,
        "tarih": datetime.utcnow().isoformat(),
    })

    # XP ver
    xp = 15 if analiz["genel_skor"] >= 80 else 10 if analiz["genel_skor"] >= 60 else 5
    ogrenci = await db.students.find_one({"id": gercek_ogrenci_id})
    if not ogrenci:
        ogrenci = await db.users.find_one({"id": gercek_ogrenci_id})
    if ogrenci:
        await db.students.update_one({"id": gercek_ogrenci_id}, {"$inc": {"toplam_xp": xp}})
        await db.xp_logs.insert_one({
            "id": str(uuid.uuid4()), "ogrenci_id": gercek_ogrenci_id,
            "eylem": "sesli_okuma", "xp": xp,
            "aciklama": f"Sesli okuma: {metin_baslik} — {analiz['genel_skor']}/100",
            "tarih": datetime.utcnow().isoformat(),
        })

    return {**analiz, "id": kayit_id, "xp_kazanildi": xp}


@router.get("/ai/speech/gecmis/{ogrenci_id}")
async def speech_gecmis(ogrenci_id: str, current_user=Depends(get_current_user)):
    """Öğrencinin sesli okuma geçmişi."""
    kayitlar = await db.speech_logs.find(
        {"ogrenci_id": ogrenci_id}
    ).sort("tarih", -1).to_list(length=50)
    for k in kayitlar:
        k.pop("_id", None)
    return kayitlar


@router.get("/ai/speech/istatistik/{ogrenci_id}")
async def speech_istatistik(ogrenci_id: str, current_user=Depends(get_current_user)):
    """Öğrencinin sesli okuma gelişim istatistikleri."""
    kayitlar = await db.speech_logs.find(
        {"ogrenci_id": ogrenci_id}
    ).sort("tarih", 1).to_list(length=None)
    for k in kayitlar:
        k.pop("_id", None)

    if not kayitlar:
        return {"toplam": 0, "ort_wpm": 0, "ort_skor": 0, "gelisim": [], "en_iyi": None}

    wpm_list = [k["analiz"].get("wpm", 0) for k in kayitlar]
    skor_list = [k["analiz"].get("genel_skor", 0) for k in kayitlar]

    # Son 10 kayıt grafik için
    gelisim = [
        {
            "tarih": k["tarih"][:10],
            "wpm": k["analiz"].get("wpm", 0),
            "skor": k["analiz"].get("genel_skor", 0),
            "metin": k.get("metin_baslik", ""),
        }
        for k in kayitlar[-10:]
    ]

    en_iyi = max(kayitlar, key=lambda k: k["analiz"].get("genel_skor", 0))

    return {
        "toplam": len(kayitlar),
        "ort_wpm": round(sum(wpm_list) / len(wpm_list)),
        "ort_skor": round(sum(skor_list) / len(skor_list)),
        "son_wpm": wpm_list[-1] if wpm_list else 0,
        "son_skor": skor_list[-1] if skor_list else 0,
        "gelisim": gelisim,
        "en_iyi": {
            "metin": en_iyi.get("metin_baslik", ""),
            "skor": en_iyi["analiz"].get("genel_skor", 0),
            "wpm": en_iyi["analiz"].get("wpm", 0),
            "tarih": en_iyi["tarih"][:10],
        },
    }
