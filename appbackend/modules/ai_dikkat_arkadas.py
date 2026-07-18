"""AI dikkat takibi + arkadaş sohbeti modülü (/ai/dikkat/*, /ai/arkadas/*).

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
from core.zaman import iso

router = APIRouter()


AI_ARKADAS_KARAKTERLER = {
    "baykus": {
        "id": "baykus",
        "ad": "Bilge Baykuş",
        "emoji": "🦉",
        "renk": "purple",
        "tanim": "Derin sorular soran, düşündüren",
        "sistem_prompt": """Sen Bilge Baykuş'sun. İlkokul öğrencilerine okuma konusunda yardım eden bilge ve meraklı bir baykussun.
Özelliğin: Derin, düşündürücü sorular sorarsın. Bloom taksonomisinin analiz ve değerlendirme basamaklarını kullanırsın.
Kurallar:
- Her yanıtta 1-2 cümle konuş, sonra 1 soru sor
- Türkçe konuş, sade ve anlaşılır
- Asla kişisel bilgi sorma
- Sadece kitap, okuma, öğrenme hakkında konuş
- Yanıt max 3 cümle olsun
- Sen bir baykussun, bazen "Huu huu!" diyebilirsin""",
    },
    "robot": {
        "id": "robot",
        "ad": "Robot Kaptan",
        "emoji": "🤖",
        "renk": "blue",
        "tanim": "Heyecanlı, eğlenceli, macera dolu",
        "sistem_prompt": """Sen Robot Kaptan'sın! İlkokul öğrencileriyle konuşan süper heyecanlı bir robotsun!
Özelliğin: Her şeyi macera ve keşif olarak görürsün. Okumayı bir uzay yolculuğuna benzetirsin.
Kurallar:
- Heyecanlı konuş! Bazen "SÜPER!" veya "İNANILMAZ!" diyebilirsin
- Her yanıt max 3 cümle
- Türkçe konuş
- Sadece kitap ve okuma hakkında konuş
- Asla kişisel bilgi sorma
- Bazen robotça sesler çıkarabilirsin: bip bop!""",
    },
    "dede": {
        "id": "dede",
        "ad": "Kütüphane Dedesi",
        "emoji": "📖",
        "renk": "amber",
        "tanim": "Hikâye anlatan, sıcak, bilge",
        "sistem_prompt": """Sen Kütüphane Dedesi'sin. Yıllarca kütüphanede çalışmış, binlerce kitap okumuş, çok sevilen bir dedesin.
Özelliğin: Her konuya bağlantılı bir hikâye veya kitap hatırlarsın. Sıcak ve sevecensin.
Kurallar:
- "Ah, bir keresinde bir kitapta..." diye başlayabilirsin
- Her yanıt max 3 cümle
- Türkçe konuş, samimi ve sıcak ol
- Sadece kitap, okuma, hikâye hakkında konuş
- Asla kişisel bilgi sorma
- Bazen "Güzel kitaplar güzel rüyalar getirir" gibi atasözü söyleyebilirsin""",
    },
    "kedi": {
        "id": "kedi",
        "ad": "Gezgin Kedi",
        "emoji": "🐱",
        "renk": "green",
        "tanim": "Hayal gücü yüksek, yaratıcı, eğlenceli",
        "sistem_prompt": """Sen Gezgin Kedi'sin! Dünyanın her yerine seyahat etmiş, her kitabın içine girmiş bir kedisin.
Özelliğin: Hayal gücünü kullanırsın. Kitapların içindeki dünyaları canlandırırsın.
Kurallar:
- "Miyav! Bir keresinde o kitabın içine girmiştim ve..." diyebilirsin
- Her yanıt max 3 cümle
- Türkçe konuş, eğlenceli ve yaratıcı ol
- Sadece kitap, okuma, hayal gücü hakkında konuş
- Asla kişisel bilgi sorma
- Bazen "Miyav!" diyebilirsin""",
    },
}

# Günlük sohbet limiti
AI_ARKADAS_GUNLUK_LIMIT = 20
AI_ARKADAS_MODERASYON_ESIK = 50  # Her 50 mesajda moderasyon


def _dikkat_skoru_hesapla(metrikler: dict) -> dict:
    """Davranış metriklerinden dikkat skoru üret."""
    sure_sn = metrikler.get("sure_sn", 0)
    kelime_sayisi = metrikler.get("kelime_sayisi", 100)
    geri_scroll_sayisi = metrikler.get("geri_scroll_sayisi", 0)
    zorluk_kelimeler = metrikler.get("zorluk_kelimeler", [])
    duraklamalar = metrikler.get("duraklamalar", 0)  # anormal duraklamalar

    # Beklenen okuma süresi (sinif normuna göre WPM)
    sinif = metrikler.get("sinif", 3)
    norm_wpm = {1:50, 2:75, 3:95, 4:115, 5:130}.get(sinif, 95)
    beklenen_sure = (kelime_sayisi / norm_wpm) * 60  # saniye

    # 1. Süre skoru — çok hızlı veya çok yavaş ise düşük
    if beklenen_sure > 0:
        oran = sure_sn / beklenen_sure
        if 0.7 <= oran <= 1.5:
            sure_skoru = 100
        elif 0.5 <= oran < 0.7 or 1.5 < oran <= 2.0:
            sure_skoru = 70
        elif oran < 0.5:
            sure_skoru = 40  # çok hızlı — atlıyor olabilir
        else:
            sure_skoru = 50  # çok yavaş — zorlanıyor
    else:
        sure_skoru = 60

    # 2. Geri scroll — dikkatin dağıldığı veya anlamadığı bölümler
    max_scroll = max(1, kelime_sayisi // 50)
    scroll_skoru = max(0, 100 - (geri_scroll_sayisi / max_scroll) * 30)

    # 3. Zorluk kelimeleri — tıklamak pozitif (merak) ama çok fazlası zorlandığını gösterir
    if len(zorluk_kelimeler) == 0:
        zorluk_skoru = 80  # hiç tıklamadı — anlıyor olabilir veya ilgisiz
    elif len(zorluk_kelimeler) <= 3:
        zorluk_skoru = 95  # meraklı — sağlıklı
    elif len(zorluk_kelimeler) <= 6:
        zorluk_skoru = 75  # biraz zorlanıyor
    else:
        zorluk_skoru = 55  # çok zorlanıyor

    # 4. Duraklamalar
    duraklama_skoru = max(40, 100 - duraklamalar * 10)

    # Genel dikkat skoru (ağırlıklı ortalama)
    dikkat = round(
        sure_skoru * 0.35 +
        scroll_skoru * 0.30 +
        zorluk_skoru * 0.20 +
        duraklama_skoru * 0.15
    )

    # Yorum
    if dikkat >= 80:
        yorum = "Harika konsantrasyon! Metni akıcı okudun."
        oneri = None
    elif dikkat >= 65:
        yorum = "İyi odaklanma. Birkaç bölümde zorlandın."
        oneri = "Zorlandığın kelimeleri not et ve tekrar bak." if zorluk_kelimeler else "Biraz daha yavaş okumayı dene."
    elif dikkat >= 50:
        yorum = "Dikkat dağınıklığı var. Bazı bölümleri tekrar okumalısın."
        oneri = "Sessiz bir ortamda okumayı dene. Kısa molalar ver."
    else:
        yorum = "Bu bölümü anlamakta zorlandın. Tekrar okumalısın."
        oneri = "Bu metni bir daha yavaşça oku. Zor kelimelerin anlamına bak."

    return {
        "dikkat_skoru": dikkat,
        "alt_skorlar": {
            "sure": round(sure_skoru),
            "scroll": round(scroll_skoru),
            "zorluk": round(zorluk_skoru),
            "duraklama": round(duraklama_skoru),
        },
        "yorum": yorum,
        "oneri": oneri,
        "zorluk_kelimeler": zorluk_kelimeler[:10],
        "geri_oku_onerisi": dikkat < 60,
    }


@router.post("/ai/dikkat/kaydet")
async def dikkat_kaydet(request: Request, current_user=Depends(get_current_user)):
    """Okuma oturumunun dikkat metriklerini kaydet ve analiz et."""
    body = await request.json()
    ogrenci_id = current_user.get("linked_id") or current_user.get("id")

    metrikler = {
        "sure_sn": body.get("sure_sn", 0),
        "kelime_sayisi": body.get("kelime_sayisi", 100),
        "geri_scroll_sayisi": body.get("geri_scroll_sayisi", 0),
        "zorluk_kelimeler": body.get("zorluk_kelimeler", []),
        "duraklamalar": body.get("duraklamalar", 0),
        "sinif": body.get("sinif", 3),
    }

    analiz = _dikkat_skoru_hesapla(metrikler)

    # Veritabanına kaydet
    kayit_id = str(uuid.uuid4())
    await db.dikkat_log.insert_one({
        "id": kayit_id,
        "ogrenci_id": ogrenci_id,
        "kitap_adi": body.get("kitap_adi", ""),
        "bolum": body.get("bolum", ""),
        "metrikler": metrikler,
        "analiz": analiz,
        "tarih": iso(),
    })

    # DNA dikkat boyutunu güncelle — son 5 oturumun ortalaması
    son_kayitlar = await db.dikkat_log.find(
        {"ogrenci_id": ogrenci_id}
    ).sort("tarih", -1).to_list(length=5)
    for k in son_kayitlar:
        k.pop("_id", None)

    if son_kayitlar:
        ort_dikkat = round(sum(k["analiz"]["dikkat_skoru"] for k in son_kayitlar) / len(son_kayitlar))
        await db.okuma_dna.update_one(
            {"ogrenci_id": ogrenci_id},
            {"$set": {"boyutlar.dikkat_suresi": ort_dikkat, "son_guncelleme": iso()}},
        )

    return {**analiz, "id": kayit_id}


@router.get("/ai/dikkat/gecmis/{ogrenci_id}")
async def dikkat_gecmis(ogrenci_id: str, current_user=Depends(get_current_user)):
    """Öğrencinin dikkat analizi geçmişi."""
    kayitlar = await db.dikkat_log.find(
        {"ogrenci_id": ogrenci_id}
    ).sort("tarih", -1).to_list(length=20)
    for k in kayitlar:
        k.pop("_id", None)
    return kayitlar


# NOT: Bu iki route (POST /ai/dikkat/kaydet, GET /ai/dikkat/gecmis) daha önce dosyada İKİŞER kez
# tanımlıydı. FastAPI ilk kayıtlı route'u eşleştirdiği için yukarıdaki (iç içe metrikler/analiz
# şeması + _dikkat_skoru_hesapla + okuma_dna.boyutlar.dikkat_suresi) canlı olan KANONİK sürümdür;
# buradaki ikinci (gölgede kalıp hiç çalışmayan) tanımlar kullanıcı kararıyla kaldırıldı.


def _arkadas_icerik_kontrol(mesaj: str) -> bool:
    """Çocuk güvenliği: uygunsuz içerik filtresi."""
    yasak_kelimeler = ["şifre", "adres", "telefon", "ev", "okul adresi", "nerede oturuyorsun"]
    mesaj_lower = mesaj.lower()
    return not any(k in mesaj_lower for k in yasak_kelimeler)


@router.get("/ai/arkadas/karakterler")
async def arkadas_karakterler(current_user=Depends(get_current_user)):
    """4 AI arkadaş karakterini getir."""
    return {
        "karakterler": [
            {k: v for k, v in kar.items() if k != "sistem_prompt"}
            for kar in AI_ARKADAS_KARAKTERLER.values()
        ]
    }


@router.post("/ai/arkadas/sohbet")
async def arkadas_sohbet(request: Request, current_user=Depends(get_current_user)):
    """Seçili karakterle sohbet et."""
    body = await request.json()
    karakter_id = body.get("karakter_id", "baykus")
    mesaj = body.get("mesaj", "").strip()
    gecmis = body.get("gecmis", [])  # [{rol: "user"|"assistant", icerik: "..."}]
    kitap_baglami = body.get("kitap_baglami", "")  # isteğe bağlı kitap adı

    if not mesaj:
        raise HTTPException(status_code=400, detail="Mesaj boş olamaz")
    if len(mesaj) > 500:
        raise HTTPException(status_code=400, detail="Mesaj çok uzun")
    if not _arkadas_icerik_kontrol(mesaj):
        raise HTTPException(status_code=400, detail="Bu tür bilgileri paylaşma — güvenliğin önemli!")

    karakter = AI_ARKADAS_KARAKTERLER.get(karakter_id, AI_ARKADAS_KARAKTERLER["baykus"])
    ogrenci_id = current_user.get("linked_id") or current_user.get("id")

    # Günlük limit kontrolü
    bugun = datetime.utcnow().strftime("%Y-%m-%d")
    gunluk_sayac = await db.ai_arkadas_log.count_documents({
        "ogrenci_id": ogrenci_id,
        "tarih": {"$gte": bugun}
    })
    if gunluk_sayac >= AI_ARKADAS_GUNLUK_LIMIT:
        return {
            "yanit": f"Bugün çok yoruldum! {karakter['emoji']} Yarın tekrar konuşalım. Bugün {AI_ARKADAS_GUNLUK_LIMIT} mesaj hakkın bitti.",
            "limit_doldu": True,
        }

    # Claude API ile yanıt
    sistem = karakter["sistem_prompt"]
    if kitap_baglami:
        sistem += f"\n\nÖğrenci şu an '{kitap_baglami}' kitabı hakkında konuşmak istiyor."

    # Sohbet geçmişini mesaj formatına çevir
    claude_mesajlar = []
    for h in gecmis[-6:]:  # son 6 mesaj (3 tur)
        claude_mesajlar.append({
            "role": "user" if h["rol"] == "user" else "assistant",
            "content": h["icerik"]
        })
    claude_mesajlar.append({"role": "user", "content": mesaj})

    yanit_metni = ""
    if GEMINI_API_KEY:
        try:
            result = await call_claude(sistem, mesaj, model="haiku", max_tokens=200)
            # call_claude single-turn, multi-turn için direkt API çağrısı
            if len(claude_mesajlar) > 1:
                # Multi-turn: tüm geçmişi tek prompt olarak gönder
                gecmis = "\n".join([f"{m['role'].upper()}: {m['content'] if isinstance(m['content'], str) else m['content'][0].get('text','')}" for m in claude_mesajlar])
                multi_prompt = f"{sistem}\n\nKONUŞMA GEÇMİŞİ:\n{gecmis}\n\nASISTAN:"
                yanit_metni = await _gemini_call(multi_prompt, max_tokens=200)
            else:
                yanit_metni = result.get("text", "")
        except Exception as e:
            logging.warning(f"AI Arkadaş API hatası: {e}")

    # API yoksa veya hata varsa — karakter bazlı mock yanıt
    if not yanit_metni:
        mock_yanitlar = {
            "baykus": [
                f"Huu huu! '{mesaj[:20]}...' çok ilginç bir düşünce! Peki, bu sana ne hissettiriyor?",
                "Harika bir soru! Kitaplar bize çok şey öğretir. Sen ne düşünüyorsun?",
                "Huu huu! Okumak zihnimizi açar. Bu kitapta en çok hangi bölümü sevdin?",
            ],
            "robot": [
                "BİP BOP! SÜPER düşünce! Bu kitap gerçekten bir uzay macerası gibi! Devam et!",
                "İNANILMAZ! Okumak bir zaman makinesi gibi, her sayfada yeni bir dünyaya gidiyorsun!",
                "SÜPER! Bip bop! Seninle okuma macerası yapmak çok eğlenceli!",
            ],
            "dede": [
                "Ah, güzel bir düşünce. Bir keresinde benzer bir kitap okumuştum, çok etkileyiciydi.",
                "Güzel kitaplar güzel rüyalar getirir. Okumaya devam et, çok işine yarayacak.",
                "Ah, biliyor musun, bu bana eski bir hikâyeyi hatırlattı. Kitaplar hayatımızı zenginleştirir.",
            ],
            "kedi": [
                f"Miyav! Ben de o kitabın içine girmiştim! Çok heyecanlıydı! Sen de hayal et!",
                "Miyav miyav! Kitaplar beni yeni dünyalara götürüyor. Sen hangi dünyaya gitmek istersin?",
                "Miyav! Hayal gücün çok güçlü! Her kitap yeni bir macera kapısı açar!",
            ],
        }
        import random
        yanit_metni = random.choice(mock_yanitlar.get(karakter_id, mock_yanitlar["baykus"]))

    # Veritabanına kaydet
    await db.ai_arkadas_log.insert_one({
        "id": str(uuid.uuid4()),
        "ogrenci_id": ogrenci_id,
        "karakter_id": karakter_id,
        "mesaj": mesaj,
        "yanit": yanit_metni,
        "kitap_baglami": kitap_baglami,
        "tarih": datetime.utcnow().strftime("%Y-%m-%d"),
        "tarih_tam": datetime.utcnow().isoformat(),
    })

    return {
        "yanit": yanit_metni,
        "karakter": {k: v for k, v in karakter.items() if k != "sistem_prompt"},
        "gunluk_kalan": max(0, AI_ARKADAS_GUNLUK_LIMIT - gunluk_sayac - 1),
        "limit_doldu": False,
    }


@router.get("/ai/arkadas/gecmis/{ogrenci_id}")
async def arkadas_gecmis(ogrenci_id: str, karakter_id: str = "", current_user=Depends(get_current_user)):
    """Öğrencinin belirli karakterle veya tüm sohbet geçmişi."""
    filtre = {"ogrenci_id": ogrenci_id}
    if karakter_id:
        filtre["karakter_id"] = karakter_id
    kayitlar = await db.ai_arkadas_log.find(filtre).sort("tarih_tam", -1).to_list(length=100)
    for k in kayitlar:
        k.pop("_id", None)
    return kayitlar
