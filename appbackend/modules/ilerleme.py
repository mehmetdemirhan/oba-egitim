"""İlerleme/oyunlaştırma modülü (/xp/*, /kur/*, /rozetler/*, /sezon/*, /puan-tablosu/birlesik).

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
    get_ogretmen_rozetleri, get_ogrenci_rozetleri,
    XP_TABLOSU_DEFAULT, LIG_ESIKLERI_DEFAULT, LIG_SIRA,
)
from core.ai import _gemini_call, call_claude, _mock_bilgi_tabani_response, get_ogrenci_ai_verileri

router = APIRouter()


async def _get_toplam_xp(ogrenci_id):
    student = await db.students.find_one({"id": ogrenci_id})
    return student.get("toplam_xp", 0) if student else 0


# XP kazan
@router.post("/xp/kazan")
async def xp_kazan(payload: dict, current_user=Depends(get_current_user)):
    ogrenci_id = current_user.get("linked_id") or current_user.get("id")
    eylem = payload.get("eylem", "")
    xp = (await get_xp_tablosu()).get(eylem, 0)
    if xp == 0:
        return {"xp": 0, "mesaj": "Bilinmeyen eylem"}

    log = {
        "id": str(uuid.uuid4()),
        "ogrenci_id": ogrenci_id,
        "eylem": eylem,
        "xp": xp,
        "tarih": datetime.utcnow().isoformat(),
    }
    await db.xp_logs.insert_one(log)

    # Toplam XP güncelle
    await db.students.update_one({"id": ogrenci_id}, {"$inc": {"toplam_xp": xp}})

    return {"xp": xp, "toplam": await _get_toplam_xp(ogrenci_id)}


# XP durumu
@router.get("/xp/durum/{ogrenci_id}")
async def xp_durum(ogrenci_id: str, current_user=Depends(get_current_user)):
    toplam = await _get_toplam_xp(ogrenci_id)
    # Lig hesapla
    lig = "bronz"
    for l in reversed(LIG_SIRA):
        if toplam >= (await get_lig_esikleri()).get(l, 0):
            lig = l
            break
    # Sonraki lig
    idx = LIG_SIRA.index(lig)
    sonraki_lig = LIG_SIRA[idx + 1] if idx < len(LIG_SIRA) - 1 else None
    sonraki_esik = (await get_lig_esikleri()).get(sonraki_lig, 0) if sonraki_lig else 0
    kalan = max(0, sonraki_esik - toplam)

    # Son XP kayıtları
    son_xp = await db.xp_logs.find({"ogrenci_id": ogrenci_id}).sort("tarih", -1).to_list(length=10)
    for x in son_xp:
        x.pop("_id", None)

    return {
        "toplam_xp": toplam,
        "lig": lig,
        "lig_label": {"bronz": "🥉 Bronz", "gumus": "🥈 Gümüş", "altin": "🥇 Altın", "elmas": "💎 Elmas"}.get(lig, lig),
        "sonraki_lig": sonraki_lig,
        "sonraki_esik": sonraki_esik,
        "kalan_xp": kalan,
        "son_xp": son_xp,
    }


# Lig sıralaması (anonim)
@router.get("/xp/lig-siralama")
async def lig_siralama(current_user=Depends(get_current_user)):
    ogrenci_id = current_user.get("linked_id") or current_user.get("id")
    students = await db.students.find().to_list(length=None)
    siralama = sorted(students, key=lambda s: s.get("toplam_xp", 0), reverse=True)

    tablo = []
    benim_siram = None
    for i, s in enumerate(siralama):
        sira = i + 1
        xp = s.get("toplam_xp", 0)
        lig = "bronz"
        for l in reversed(LIG_SIRA):
            if xp >= (await get_lig_esikleri()).get(l, 0):
                lig = l
                break
        ben = s.get("id") == ogrenci_id
        if ben:
            benim_siram = sira
        tablo.append({
            "sira": sira,
            "xp": xp,
            "lig": lig,
            "lig_label": {"bronz": "🥉", "gumus": "🥈", "altin": "🥇", "elmas": "💎"}.get(lig, ""),
            "ben": ben,
            "ad": "Sen 🌟" if ben else f"Öğrenci #{sira}",
        })

    return {"siralama": tablo[:30], "benim_siram": benim_siram or len(tablo) + 1, "toplam": len(siralama)}


# Kur atlama kontrolü
@router.get("/kur/kontrol/{ogrenci_id}")
async def kur_kontrol(ogrenci_id: str, current_user=Depends(get_current_user)):
    # Kriterleri kontrol et
    gorevler = await db.gorevler.find({"hedef_id": ogrenci_id, "durum": "tamamlandi"}).to_list(length=None)
    reading_logs = await db.reading_logs.find({"ogrenci_id": ogrenci_id}).to_list(length=None)
    kitaplar = set(l.get("kitap_adi", "") for l in reading_logs if l.get("kitap_adi"))

    # Streak
    from datetime import timedelta
    simdi = datetime.utcnow()
    tarihler = sorted(set(l.get("tarih", "")[:10] for l in reading_logs), reverse=True)
    streak = 0
    for i in range(60):
        gun = (simdi - timedelta(days=i)).strftime("%Y-%m-%d")
        if gun in tarihler:
            streak += 1
        elif i > 0:
            break

    tamamlanan_gorev = len(gorevler)
    kitap_sayisi = len(kitaplar)

    # Anlama yüzdesi (gelişim tamamlamalardan)
    tamamlamalar = await db.gelisim_tamamlama.find({"kullanici_id": ogrenci_id}).to_list(length=None)
    if tamamlamalar:
        toplam_dogru = sum(t.get("dogru_sayisi", 0) for t in tamamlamalar if t.get("test_yapildi"))
        toplam_soru = sum(t.get("toplam_soru", 0) for t in tamamlamalar if t.get("test_yapildi"))
        anlama_yuzdesi = round((toplam_dogru / max(toplam_soru, 1)) * 100)
    else:
        anlama_yuzdesi = 0

    kriterler = {
        "gorev_12": {"gerekli": 12, "mevcut": tamamlanan_gorev, "tamam": tamamlanan_gorev >= 12},
        "anlama_75": {"gerekli": 75, "mevcut": anlama_yuzdesi, "tamam": anlama_yuzdesi >= 75},
        "kitap_4": {"gerekli": 4, "mevcut": kitap_sayisi, "tamam": kitap_sayisi >= 4},
        "streak_10": {"gerekli": 10, "mevcut": streak, "tamam": streak >= 10},
    }

    hepsi_tamam = all(k["tamam"] for k in kriterler.values())

    return {
        "kriterler": kriterler,
        "kur_atlayabilir": hepsi_tamam,
        "mevcut_kur": (await db.students.find_one({"id": ogrenci_id}) or {}).get("kur", ""),
    }


# Kur atla (öğretmen onayı ile)
@router.post("/kur/atla")
async def kur_atla(payload: dict, current_user=Depends(get_current_user)):
    role = current_user.get("role", "")
    if role not in ["admin", "coordinator", "teacher"]:
        raise HTTPException(status_code=403, detail="Sadece öğretmen/yönetici kur atlatabilir")

    ogrenci_id = payload.get("ogrenci_id")
    yeni_kur = payload.get("yeni_kur", "")

    # Mevcut kuru al
    student = await db.students.find_one({"id": ogrenci_id})
    eski_kur = student.get("kur", "") if student else ""

    # Kur güncelle
    await db.students.update_one({"id": ogrenci_id}, {"$set": {"kur": yeni_kur}})

    # Kur atlama kaydı (rozet sistemi için)
    ogretmen_id = current_user.get("linked_id") or current_user.get("id")
    await db.kur_atlamalari.insert_one({
        "id": str(uuid.uuid4()),
        "ogrenci_id": ogrenci_id,
        "ogretmen_id": ogretmen_id,
        "eski_kur": eski_kur,
        "yeni_kur": yeni_kur,
        "tarih": datetime.utcnow().isoformat(),
    })

    return {"ok": True, "yeni_kur": yeni_kur, "eski_kur": eski_kur}


# Birleştirilmiş Puan Tablosu (gelişim + rozet puanları)
@router.get("/puan-tablosu/birlesik")
async def get_birlesik_puan_tablosu(current_user=Depends(get_current_user)):
    users = await db.users.find().to_list(length=None)
    tablo = []
    for u in users:
        uid = u["id"]
        gelisim_puan = u.get("puan", 0)

        # Rozet puanları
        rozetler = await db.kazanilan_rozetler.find({"kullanici_id": uid}).to_list(length=None)
        rozet_kodlar = [r["rozet_kodu"] for r in rozetler]

        ogretmen_rozet_list = await get_ogretmen_rozetleri()
        ogrenci_rozet_list = await get_ogrenci_rozetleri()
        tum_rozetler = ogretmen_rozet_list + ogrenci_rozet_list

        rozet_puan = 0
        for rk in rozet_kodlar:
            tanim = next((r for r in tum_rozetler if r["kod"] == rk), None)
            if tanim:
                rozet_puan += tanim.get("puan", tanim.get("xp", 0))

        toplam = gelisim_puan + rozet_puan

        tablo.append({
            "ad": u.get("ad", ""), "soyad": u.get("soyad", ""),
            "role": u.get("role", ""),
            "gelisim_puan": gelisim_puan,
            "rozet_puan": rozet_puan,
            "rozet_sayisi": len(rozet_kodlar),
            "toplam_puan": toplam,
        })
    tablo.sort(key=lambda x: x["toplam_puan"], reverse=True)
    return tablo


@router.get("/rozetler/tanim")
async def rozet_tanimlari():
    return {"ogretmen": await get_ogretmen_rozetleri(), "ogrenci": await get_ogrenci_rozetleri()}


@router.get("/rozetler/{user_id}")
async def get_rozetler(user_id: str, current_user=Depends(get_current_user)):
    rozetler = await db.kazanilan_rozetler.find({"kullanici_id": user_id}).to_list(length=None)
    for r in rozetler:
        r.pop("_id", None)
    return rozetler


@router.post("/rozetler/kontrol")
async def rozet_kontrol(current_user=Depends(get_current_user)):
    user_id = current_user["id"]
    role = current_user.get("role", "")
    linked_id = current_user.get("linked_id", "")

    mevcut = await db.kazanilan_rozetler.find({"kullanici_id": user_id}).to_list(length=None)
    mevcut_kodlar = set(r["rozet_kodu"] for r in mevcut)
    yeni_rozetler = []

    if role == "teacher":
        ogretmen_id = linked_id or user_id
        # İçerik sayısı
        icerikler = await db.gelisim_icerik.count_documents({"ekleyen_id": user_id, "durum": "yayinda"})
        # Oylama sayısı
        tum_icerikler = await db.gelisim_icerik.find({"durum": {"$in": ["yayinda", "oylama"]}}).to_list(length=None)
        oy_sayisi = sum(1 for ic in tum_icerikler if user_id in (ic.get("oylar") or {}))
        # Görev atama
        gorevler = await db.gorevler.find({"atayan_id": user_id}).to_list(length=None)
        gorev_sayisi = len(gorevler)
        tamamlanan_gorev = len([g for g in gorevler if g.get("durum") == "tamamlandi"])
        # Öğrenci streak ortalaması
        ogrenciler = await db.students.find({"ogretmen_id": ogretmen_id, "arsivli": {"$ne": True}}).to_list(length=None)
        from datetime import timedelta
        simdi = datetime.utcnow()
        streakler = []
        for s in ogrenciler:
            logs = await db.reading_logs.find({"ogrenci_id": s["id"]}).to_list(length=None)
            tarihler = sorted(set(l.get("tarih", "")[:10] for l in logs), reverse=True)
            st = 0
            for i in range(60):
                gun = (simdi - timedelta(days=i)).strftime("%Y-%m-%d")
                if gun in tarihler: st += 1
                elif i > 0: break
            streakler.append(st)
        ort_streak = sum(streakler) / max(len(streakler), 1)
        # Kur atlama
        kur_sayisi = await db.kur_atlamalari.count_documents({"ogretmen_id": ogretmen_id})
        # Gelişim tamamlama
        gelisim_tam = await db.gelisim_tamamlama.count_documents({"kullanici_id": user_id})
        # Mesaj
        mesajlar = await db.mesajlar.find({"gonderen_id": user_id}).to_list(length=None)
        mesaj_sayisi = len(mesajlar)
        mesaj_roller = set(m.get("alici_rol", "") for m in mesajlar)
        # Egzersiz
        egz_tam = await db.egzersiz_tamamlama.find({"kullanici_id": user_id}).to_list(length=None)
        egz_turler = set(e.get("egzersiz_id", "") for e in egz_tam)
        # Veli anketi
        anketler = await db.veli_anketleri.find({"ogretmen_id": ogretmen_id}).to_list(length=None)
        anket_sayisi = len(anketler)
        anket_ort = 0
        tavsiye_oran = 0
        if anket_sayisi > 0:
            puanlar = []
            tavsiyeler = 0
            for a in anketler:
                yanitlar = a.get("yanitlar", [])
                puan_yanitlar = [y.get("puan", 0) for y in yanitlar if y.get("puan")]
                if puan_yanitlar:
                    puanlar.append(sum(puan_yanitlar) / len(puan_yanitlar))
                if a.get("tavsiye"):
                    tavsiyeler += 1
            anket_ort = sum(puanlar) / max(len(puanlar), 1)
            tavsiye_oran = (tavsiyeler / anket_sayisi) * 100

        # Kontrol
        checks = [
            ("icerik_ilk", icerikler >= 1), ("icerik_5", icerikler >= 5), ("icerik_20", icerikler >= 20), ("icerik_50", icerikler >= 50),
            ("oy_ilk", oy_sayisi >= 1), ("oy_20", oy_sayisi >= 20), ("oy_50", oy_sayisi >= 50),
            ("gorev_ilk", gorev_sayisi >= 1), ("gorev_20", gorev_sayisi >= 20 and tamamlanan_gorev >= 10),
            ("ilham_veren", ort_streak >= 7), ("yildiz_egitimci", ort_streak >= 10),
            ("kur_ilk", kur_sayisi >= 1), ("kur_20", kur_sayisi >= 20), ("kur_30", kur_sayisi >= 30), ("kur_50", kur_sayisi >= 50), ("kur_100", kur_sayisi >= 100),
            ("veli_ilk", anket_sayisi >= 1 and anket_ort >= 4), ("veli_20", anket_sayisi >= 20 and anket_ort >= 4.5),
            ("veli_30", anket_sayisi >= 30 and anket_ort >= 4.5 and tavsiye_oran >= 90),
            ("veli_100", anket_sayisi >= 100 and anket_ort >= 4.8 and tavsiye_oran >= 95),
            ("gelisim_ilk", gelisim_tam >= 1), ("gelisim_10", gelisim_tam >= 10), ("gelisim_uzman", gelisim_tam >= 30),
            ("mesaj_ilk", mesaj_sayisi >= 1), ("kopru_kurucu", "student" in mesaj_roller and "parent" in mesaj_roller),
            ("egz_ilk", len(egz_turler) >= 1), ("egz_tamset", len(egz_turler) >= 14),
        ]
        for kod, kosul in checks:
            if kosul and kod not in mevcut_kodlar:
                doc = {"id": str(uuid.uuid4()), "kullanici_id": user_id, "rozet_kodu": kod, "kazanma_tarihi": datetime.utcnow().isoformat()}
                await db.kazanilan_rozetler.insert_one(doc)
                rozet_bilgi = next((r for r in (await get_ogretmen_rozetleri()) if r["kod"] == kod), None)
                yeni_rozetler.append({**doc, "rozet": rozet_bilgi})

    elif role == "student":
        ogrenci_id = linked_id or user_id
        logs = await db.reading_logs.find({"ogrenci_id": ogrenci_id}).to_list(length=None)
        toplam_dk = sum(l.get("sure_dakika", 0) for l in logs)
        kitaplar = set(l.get("kitap_adi", "") for l in logs if l.get("kitap_adi"))
        from datetime import timedelta
        simdi = datetime.utcnow()
        tarihler = sorted(set(l.get("tarih", "")[:10] for l in logs), reverse=True)
        streak = 0
        for i in range(60):
            gun = (simdi - timedelta(days=i)).strftime("%Y-%m-%d")
            if gun in tarihler: streak += 1
            elif i > 0: break
        gorevler_tam = await db.gorevler.count_documents({"hedef_id": ogrenci_id, "durum": "tamamlandi"})
        egz_tam = await db.egzersiz_tamamlama.find({"kullanici_id": user_id}).to_list(length=None)
        egz_turler = set(e.get("egzersiz_id", "") for e in egz_tam)
        egz_toplam = len(egz_tam)
        agac_sayisi = toplam_dk  # 1 dk = 1 ağaç
        student = await db.students.find_one({"id": ogrenci_id})
        toplam_xp = student.get("toplam_xp", 0) if student else 0

        checks = [
            ("okuma_ilk", len(logs) >= 1), ("okuma_100", toplam_dk >= 100), ("okuma_500", toplam_dk >= 500), ("okuma_2000", toplam_dk >= 2000),
            ("streak_3", streak >= 3), ("streak_7", streak >= 7), ("streak_21", streak >= 21), ("streak_60", streak >= 60),
            ("kitap_1", len(kitaplar) >= 1), ("kitap_5", len(kitaplar) >= 5), ("kitap_15", len(kitaplar) >= 15), ("kitap_30", len(kitaplar) >= 30),
            ("gorev_ilk", gorevler_tam >= 1), ("gorev_10", gorevler_tam >= 10), ("gorev_30", gorevler_tam >= 30), ("gorev_100", gorevler_tam >= 100),
            ("egz_ilk", egz_toplam >= 1), ("egz_20", egz_toplam >= 20), ("egz_14", len(egz_turler) >= 14),
            ("orman_ilk", agac_sayisi >= 1), ("orman_50", agac_sayisi >= 50), ("orman_200", agac_sayisi >= 200),
            ("lig_gumus", toplam_xp >= 200), ("lig_altin", toplam_xp >= 500), ("lig_elmas", toplam_xp >= 1000),
        ]
        for kod, kosul in checks:
            if kosul and kod not in mevcut_kodlar:
                doc = {"id": str(uuid.uuid4()), "kullanici_id": user_id, "rozet_kodu": kod, "kazanma_tarihi": datetime.utcnow().isoformat()}
                await db.kazanilan_rozetler.insert_one(doc)
                rozet_bilgi = next((r for r in (await get_ogrenci_rozetleri()) if r["kod"] == kod), None)
                yeni_rozetler.append({**doc, "rozet": rozet_bilgi})

    return {"yeni_rozetler": yeni_rozetler, "toplam": len(mevcut_kodlar) + len(yeni_rozetler)}




