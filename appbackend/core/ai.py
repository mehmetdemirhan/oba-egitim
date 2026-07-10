"""AI çağrı çekirdeği — Gemini API erişimi ve öğrenci AI verisi toplama.

server.py'dan BİREBİR taşındı; davranış değişmedi. Tüm AI modülleri (ai_*)
bu dosyadan import eder. Böylece AI altyapısı tek noktada, modüller bağımsız.
"""
import logging
import uuid
import httpx
from datetime import datetime, timedelta

from core.db import db
from core.config import (
    GEMINI_API_KEY, GEMINI_API_KEY_2, GEMINI_API_KEY_3,
    GEMINI_MODELS, AI_MODEL, AI_MAX_DAILY_REQUESTS,
)


# GEMINI AI YARDIMCI FONKSİYONLAR
# ─────────────────────────────────────────────

async def _gemini_call(prompt: str, system: str = "", max_tokens: int = 4000) -> str:
    """Gemini API çağrısı — model rotasyonu + çoklu key desteği."""
    all_keys = [k for k in [GEMINI_API_KEY, GEMINI_API_KEY_2, GEMINI_API_KEY_3] if k]
    if not all_keys:
        raise Exception("GEMINI_API_KEY tanımlı değil")

    full_prompt = f"{system}\n\n{prompt}" if system else prompt
    last_error = "Bilinmeyen hata"

    for key in all_keys:
        for model in GEMINI_MODELS:
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
                payload = {
                    "contents": [{"parts": [{"text": full_prompt}]}],
                    "generationConfig": {"maxOutputTokens": max_tokens, "temperature": 0.7}
                }
                async with httpx.AsyncClient(timeout=60.0) as c:
                    r = await c.post(url, json=payload)
                    data = r.json()

                if "candidates" in data:
                    logging.info(f"[GEMINI] ✅ Başarılı: model={model}")
                    return data["candidates"][0]["content"]["parts"][0]["text"]

                err_code = data.get("error", {}).get("code", 0)
                err_msg = str(data.get("error", {}).get("message", data))
                last_error = f"{model}: {err_msg[:200]}"
                is_quota = (err_code == 429 or "RESOURCE_EXHAUSTED" in err_msg or "quota" in err_msg.lower())
                if is_quota:
                    logging.warning(f"[GEMINI] ⚠️ Kota ({model}) → sonraki deneniyor")
                    continue
                logging.error(f"[GEMINI] ❌ Kalıcı hata {err_code}: {err_msg[:100]}")
                break

            except Exception as ex:
                last_error = str(ex)[:200]
                logging.warning(f"[GEMINI] Exception ({model}): {last_error[:80]}")
                continue

    raise Exception(f"Tüm Gemini modelleri başarısız. Son hata: {last_error}")


async def _gemini_call_multimodal(prompt: str, images: list, system: str = "",
                                  max_tokens: int = 4000) -> str:
    """Gemini multimodal çağrısı — metin + görsel(ler). `_gemini_call` ile aynı
    key/model rotasyonunu kullanır; yalnızca `parts` dizisine `inline_data` ekler.

    images: [(mime_type, base64_str), ...]  (örn. ("image/png", "<b64>"))
    """
    all_keys = [k for k in [GEMINI_API_KEY, GEMINI_API_KEY_2, GEMINI_API_KEY_3] if k]
    if not all_keys:
        raise Exception("GEMINI_API_KEY tanımlı değil")

    full_prompt = f"{system}\n\n{prompt}" if system else prompt
    parts = [{"text": full_prompt}]
    for mime, b64 in images:
        parts.append({"inline_data": {"mime_type": mime, "data": b64}})

    last_error = "Bilinmeyen hata"
    for key in all_keys:
        for model in GEMINI_MODELS:
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
                payload = {
                    "contents": [{"parts": parts}],
                    "generationConfig": {"maxOutputTokens": max_tokens, "temperature": 0.7},
                }
                async with httpx.AsyncClient(timeout=90.0) as c:
                    r = await c.post(url, json=payload)
                    data = r.json()

                if "candidates" in data:
                    logging.info(f"[GEMINI-MM] ✅ Başarılı: model={model}")
                    return data["candidates"][0]["content"]["parts"][0]["text"]

                err_code = data.get("error", {}).get("code", 0)
                err_msg = str(data.get("error", {}).get("message", data))
                last_error = f"{model}: {err_msg[:200]}"
                is_quota = (err_code == 429 or "RESOURCE_EXHAUSTED" in err_msg or "quota" in err_msg.lower())
                if is_quota:
                    logging.warning(f"[GEMINI-MM] ⚠️ Kota ({model}) → sonraki deneniyor")
                    continue
                logging.error(f"[GEMINI-MM] ❌ Kalıcı hata {err_code}: {err_msg[:100]}")
                break
            except Exception as ex:
                last_error = str(ex)[:200]
                logging.warning(f"[GEMINI-MM] Exception ({model}): {last_error[:80]}")
                continue

    raise Exception(f"Tüm Gemini modelleri başarısız (multimodal). Son hata: {last_error}")


def _mock_bilgi_tabani_response(user_message: str) -> dict:
    """API key yokken bilgi tabanı için mock veri üret."""
    import re as _re
    sinif_match = _re.search(r"Sınıf: (\d+)", user_message)
    sinif = int(sinif_match.group(1)) if sinif_match else 3
    kitap_match = _re.search(r"Kitap: (.+?)\n", user_message)
    kitap = kitap_match.group(1).strip() if kitap_match else "Kitap"
    bolum_match = _re.search(r"Bölüm (\d+)", user_message)
    bolum = int(bolum_match.group(1)) if bolum_match else 1
    metin_match = _re.search(r"METİN:\n(.{0,200})", user_message, _re.DOTALL)
    metin_kesit = metin_match.group(1).strip() if metin_match else ""
    kelimeler_demo = [
        {"kelime": "macera", "anlam": "Heyecan verici ve tehlikeli olay", "ornek_cumle": "Çocuklar ormanda büyük bir macera yaşadı.", "zorluk": sinif},
        {"kelime": "keşif", "anlam": "Bilinmeyeni ilk kez bulma", "ornek_cumle": "Bilim insanı önemli bir keşif yaptı.", "zorluk": sinif},
        {"kelime": "merak", "anlam": "Bir şeyi öğrenmek isteme", "ornek_cumle": "Meraklı çocuk her şeyi sorar.", "zorluk": max(1, sinif-1)},
        {"kelime": "cesaret", "anlam": "Korkmadan hareket edebilme", "ornek_cumle": "Cesur kahraman engeli aştı.", "zorluk": sinif},
        {"kelime": "azim", "anlam": "Bir işi bitirme kararlılığı", "ornek_cumle": "Azimle çalışan başarıya ulaştı.", "zorluk": sinif+1},
    ]
    parsed = {
        "hedef_kelimeler": kelimeler_demo,
        "okuma_parcasi": {
            "baslik": f"{kitap} — Bölüm {bolum}",
            "ozet": f"Bu bölümde {kitap} kitabından seçilmiş bir metin yer almaktadır. Öğrenciler metni okuyarak yeni kelimeler öğrenir.",
            "tema": "Genel",
            "kelime_sayisi": len(metin_kesit.split()) if metin_kesit else 50,
        },
        "sorular": [
            {"soru": "Metinde geçen en önemli olay nedir?", "secenekler": ["A seçeneği", "B seçeneği", "C seçeneği", "D seçeneği"], "dogru_cevap": 0, "taksonomi": "bilgi"},
            {"soru": "Bu metinden ne anladınız?", "secenekler": ["Ana fikri bulduk", "Sadece okudum", "Hiç anlamadım", "Çok zordu"], "dogru_cevap": 0, "taksonomi": "kavrama"},
            {"soru": "Metindeki karakterin davranışını nasıl değerlendirirsiniz?", "secenekler": ["Doğru davrandı", "Yanlış davrandı", "Kararsızım", "Önemli değil"], "dogru_cevap": 0, "taksonomi": "degerlendirme"},
        ],
    }
    import json as _json
    text = _json.dumps(parsed, ensure_ascii=False)
    return {"text": text, "parsed": parsed, "tokens": 0, "maliyet": 0, "error": None, "mock": True}


async def call_claude(system_prompt: str, user_message: str, model: str = "sonnet", max_tokens: int = 2000) -> dict:
    """AI API çağrısı — Gemini Flash kullanır."""
    if not GEMINI_API_KEY:
        if "hedef_kelimeler" in user_message or "METİN:" in user_message:
            return _mock_bilgi_tabani_response(user_message)
        return {"error": "GEMINI_API_KEY tanımlı değil", "text": ""}

    bugun = datetime.utcnow().strftime("%Y-%m-%d")
    gunluk_istek = await db.ai_request_log.count_documents({"tarih": {"$regex": f"^{bugun}"}})
    if gunluk_istek >= AI_MAX_DAILY_REQUESTS:
        return {"error": "Günlük AI istek limiti doldu", "text": ""}

    try:
        text = await _gemini_call(user_message, system=system_prompt, max_tokens=max_tokens)
        await db.ai_request_log.insert_one({
            "id": str(uuid.uuid4()),
            "model": AI_MODEL,
            "tarih": datetime.utcnow().isoformat(),
        })

        # Try to parse JSON from response
        import json as json_mod
        parsed = None
        try:
            clean = text.strip()
            if clean.startswith("```"):
                clean = clean.split("\n", 1)[1] if "\n" in clean else clean[3:]
                if clean.endswith("```"):
                    clean = clean[:-3]
                clean = clean.strip()
            parsed = json_mod.loads(clean)
        except:
            parsed = None

        return {"text": text, "parsed": parsed, "tokens": 0, "maliyet": 0, "error": None}

    except httpx.TimeoutException:
        return {"error": "AI yanıt süresi aşıldı. Lütfen tekrar deneyin.", "text": ""}
    except Exception as e:
        logging.error(f"Gemini API error: {e}")
        return {"error": f"AI hatası: {str(e)[:100]}", "text": ""}


async def get_ogrenci_ai_verileri(ogrenci_id: str) -> dict:
    """Bir öğrencinin tüm AI-beslenme verilerini toplar (8 kaynak)."""
    ogrenci = await db.students.find_one({"id": ogrenci_id})
    if not ogrenci:
        ogrenci = await db.users.find_one({"id": ogrenci_id})
    if not ogrenci:
        return {}

    # 1. Okuma kayıtları (son 30 gün)
    otuz_gun_once = (datetime.utcnow() - timedelta(days=30)).isoformat()
    logs = await db.reading_logs.find({"ogrenci_id": ogrenci_id, "tarih": {"$gte": otuz_gun_once}}).to_list(length=None)
    toplam_dk = sum(l.get("sure_dakika", 0) for l in logs)
    gun_sayisi = len(set(l.get("tarih", "")[:10] for l in logs))
    kitap_sayisi = len(set(l.get("kitap_adi", "") for l in logs if l.get("kitap_adi")))

    # 2. Streak hesaplama
    tum_logs = await db.reading_logs.find({"ogrenci_id": ogrenci_id}).to_list(length=None)
    tarihler = sorted(set(l.get("tarih", "")[:10] for l in tum_logs), reverse=True)
    streak = 0
    for i, t in enumerate(tarihler):
        beklenen = (datetime.utcnow() - timedelta(days=i)).strftime("%Y-%m-%d")
        if t == beklenen:
            streak += 1
        else:
            break

    # 3. Risk skoru
    risk_data = {}
    try:
        # Basit risk hesaplama
        risk_skor = 0
        if gun_sayisi < 3: risk_skor += 30
        elif gun_sayisi < 5: risk_skor += 15
        if toplam_dk < 30: risk_skor += 15
        elif toplam_dk < 60: risk_skor += 8
        if streak == 0: risk_skor += 10
        gorev_geciken = await db.gorevler.count_documents({"hedef_id": ogrenci_id, "durum": "bekliyor", "son_tarih": {"$lt": datetime.utcnow().isoformat()}})
        if gorev_geciken > 0: risk_skor += 15
        risk_seviye = "yuksek" if risk_skor > 60 else "orta" if risk_skor > 30 else "dusuk"
        risk_data = {"skor": min(risk_skor, 100), "seviye": risk_seviye}
    except:
        risk_data = {"skor": 0, "seviye": "dusuk"}

    # 4. XP + Lig
    xp_data = {}
    try:
        toplam_xp = ogrenci.get("toplam_xp", 0)
        lig_esikleri = {"bronz": 0, "gumus": 200, "altin": 500, "elmas": 1000}
        lig = "bronz"
        for l, e in sorted(lig_esikleri.items(), key=lambda x: x[1], reverse=True):
            if toplam_xp >= e:
                lig = l
                break
        xp_data = {"toplam": toplam_xp, "lig": lig}
    except:
        xp_data = {"toplam": 0, "lig": "bronz"}

    # 5. Görevler
    gorevler = await db.gorevler.find({"hedef_id": ogrenci_id}).to_list(length=None)
    gorev_ozet = {
        "toplam": len(gorevler),
        "tamamlanan": len([g for g in gorevler if g.get("durum") == "tamamlandi"]),
        "bekleyen": len([g for g in gorevler if g.get("durum") == "bekliyor"]),
        "suresi_gecen": len([g for g in gorevler if g.get("durum") == "bekliyor" and g.get("son_tarih", "9") < datetime.utcnow().isoformat()]),
    }

    # 6. Giriş analizi (son rapor)
    son_rapor = await db.diagnostic_raporlar.find({"ogrenci_id": ogrenci_id}).sort("olusturma_tarihi", -1).to_list(length=1)
    analiz_data = {}
    if son_rapor:
        r = son_rapor[0]
        analiz_data = {
            "wpm": r.get("okuma_hizi", {}).get("wpm", 0),
            "dogruluk": r.get("dogru_okuma", {}).get("dogruluk_orani", 0),
            "prozodi": r.get("prozodik_okuma", {}).get("toplam", 0),
        }
        # Bloom puanları
        anlama = r.get("okudugunu_anlama", {})
        if anlama:
            analiz_data["bloom"] = {
                "bilgi": anlama.get("bilgi", 0),
                "kavrama": anlama.get("kavrama", 0),
                "uygulama": anlama.get("uygulama", 0),
                "analiz": anlama.get("analiz", 0),
                "sentez": anlama.get("sentez", 0),
                "degerlendirme": anlama.get("degerlendirme", 0),
            }

    # 7. Test sonuçları
    test_sonuclari = await db.kitap_test_sonuclari.find({"ogrenci_id": ogrenci_id}).to_list(length=None)
    test_ozet = {"toplam_test": len(test_sonuclari), "ort_yuzde": 0}
    if test_sonuclari:
        test_ozet["ort_yuzde"] = round(sum(t.get("yuzde", 0) for t in test_sonuclari) / len(test_sonuclari))

    return {
        "ogrenci": {
            "ad": ogrenci.get("ad", ""),
            "soyad": ogrenci.get("soyad", ""),
            "sinif": ogrenci.get("sinif", 0),
            "kur": ogrenci.get("kur", ""),
        },
        "okuma_ozet": {
            "son_30_gun_toplam_dk": toplam_dk,
            "gun_sayisi": gun_sayisi,
            "ort_gunluk_dk": round(toplam_dk / max(gun_sayisi, 1), 1),
            "kitap_sayisi": kitap_sayisi,
        },
        "streak": {"mevcut": streak, "en_uzun": max(streak, ogrenci.get("en_uzun_streak", 0))},
        "risk": risk_data,
        "xp": xp_data,
        "gorevler": gorev_ozet,
        "analiz": analiz_data,
        "test": test_ozet,
    }
