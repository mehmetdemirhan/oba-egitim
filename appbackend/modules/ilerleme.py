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
from pymongo.errors import DuplicateKeyError
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
    get_ogretmen_rozetleri, get_ogrenci_rozetleri, get_ogretmen_puan_agirliklari,
    XP_TABLOSU_DEFAULT, LIG_ESIKLERI_DEFAULT, LIG_SIRA,
)
from core.rozet_helpers import (
    rozet_odul_puan, rozet_puan_haritasi, rozet_bildirim_gonder,
)
from core.rozet_motor import rozet_degerlendir, rozet_tetikle
from core.ai import _gemini_call, call_claude, _mock_bilgi_tabani_response, get_ogrenci_ai_verileri

router = APIRouter()

# ── Öğretmen XP bileşen ağırlıkları ──
# Etkinlik puanı (içerik/test/oylama) ve rozet puanına EK olarak; öğretmenin
# gerçek çıktıları (aldığı öğrenci, kur atlattığı, veli memnuniyeti) de XP'ye etki eder.
PUAN_OGRENCI_BASI = 5    # alınan her öğrenci başına
PUAN_KUR_BASI = 7        # her kur atlatma olayı başına
PUAN_VELI_YILDIZ = 2     # veli anketinde ortalama yıldız başına (5 yıldız = +10/anket)


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

    # Event: kur atlatma öğretmenin kur_* rozetlerini tetikler (fire-and-forget)
    asyncio.create_task(rozet_tetikle(current_user["id"], "kur_atlama"))

    return {"ok": True, "yeni_kur": yeni_kur, "eski_kur": eski_kur}


# Birleştirilmiş Puan Tablosu (gelişim + rozet puanları)
@router.get("/puan-tablosu/birlesik")
async def get_birlesik_puan_tablosu(current_user=Depends(get_current_user)):
    users = await db.users.find().to_list(length=None)
    # Rozet ödül puanı haritası (kod→puan) döngü dışında BİR kez çekilir
    rozet_puan_map = await rozet_puan_haritasi()
    tablo = []
    for u in users:
        uid = u["id"]
        gelisim_puan = u.get("puan", 0)

        # Rozet puanları
        rozetler = await db.kazanilan_rozetler.find({"kullanici_id": uid}).to_list(length=None)
        rozet_kodlar = [r["rozet_kodu"] for r in rozetler]
        rozet_puan = sum(rozet_puan_map.get(rk, 0) for rk in rozet_kodlar)

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


# ── Role göre puan tablosu (her rol kendi kategorisinde sıralanır) ──
def _norm_rol(rol: str) -> Optional[str]:
    r = (rol or "").strip().lower()
    if r in ("ogrenci", "öğrenci", "student"):
        return "student"
    if r in ("ogretmen", "öğretmen", "teacher"):
        return "teacher"
    return None


async def _ogrenci_puan_tablosu(current_user) -> dict:
    """role=student olan tüm kullanıcıları XP'ye göre sıralar (isimli, kendini vurgular)."""
    ogrenci_id = current_user.get("linked_id") or current_user.get("id")
    students = await db.students.find({"arsivli": {"$ne": True}}).to_list(length=None)
    students.sort(key=lambda s: s.get("toplam_xp", 0), reverse=True)
    liste = []
    for i, s in enumerate(students):
        xp = s.get("toplam_xp", 0)
        ad = f"{s.get('ad', '')} {s.get('soyad', '')}".strip() or "Öğrenci"
        liste.append({
            "sira": i + 1,
            "id": s.get("id"),
            "ad_soyad": ad,
            "puan": xp,
            "xp": xp,
            "streak": s.get("streak", 0),
            "rol": "student",
            "ben": s.get("id") == ogrenci_id,
        })
    return {"rol": "ogrenci", "toplam": len(liste), "siralama": liste}


async def _ogretmen_puan_tablosu(current_user) -> dict:
    """role=teacher olanları puana göre sıralar; İSİM/SIRA LİSTESİ DÖNMEZ.
    Sadece kendi konumun + isimsiz agrega istatistikler + motivasyon mesajı."""
    # Rozet ödül puanı haritası (birlesik endpoint'iyle aynı puanlama)
    rozet_puan_map = await rozet_puan_haritasi()

    # XP bileşen ağırlıkları (admin panelinden ayarlanabilir; yoksa varsayılan)
    ag = await get_ogretmen_puan_agirliklari()
    w_ogr = int(ag.get("ogrenci_basi", PUAN_OGRENCI_BASI))
    w_kur = int(ag.get("kur_basi", PUAN_KUR_BASI))
    w_veli = float(ag.get("veli_yildiz", PUAN_VELI_YILDIZ))

    teachers = await db.users.find({"role": "teacher"}).to_list(length=None)

    # ── Bileşen verileri: tek sorguyla çekilip Python'da gruplanır (öğretmen sayısı×sorgu değil) ──
    def _ogr_id(u):
        return u.get("linked_id") or u["id"]

    # Rozet puanı (kullanici_id bazlı)
    rozet_by_user = {}
    for r in await db.kazanilan_rozetler.find({}).to_list(length=None):
        uid = r.get("kullanici_id")
        rozet_by_user[uid] = rozet_by_user.get(uid, 0) + rozet_puan_map.get(r.get("rozet_kodu"), 0)

    # Alınan öğrenci sayısı (ogretmen_id bazlı)
    ogr_say = {}
    for s in await db.students.find({}, {"ogretmen_id": 1}).to_list(length=None):
        tid = s.get("ogretmen_id")
        if tid:
            ogr_say[tid] = ogr_say.get(tid, 0) + 1

    # Kur atlatma sayısı (ogretmen_id bazlı)
    kur_say = {}
    for k in await db.kur_atlamalari.find({}, {"ogretmen_id": 1}).to_list(length=None):
        tid = k.get("ogretmen_id")
        if tid:
            kur_say[tid] = kur_say.get(tid, 0) + 1

    # Veli anket bonusu (ogretmen_id bazlı) = Σ (anketin ortalama yıldızı × PUAN_VELI_YILDIZ)
    veli_bonus = {}
    for a in await db.veli_anketleri.find({}).to_list(length=None):
        tid = a.get("ogretmen_id")
        if not tid:
            continue
        py = [y.get("puan", 0) for y in a.get("yanitlar", []) if y.get("puan")]
        if py:
            veli_bonus[tid] = veli_bonus.get(tid, 0) + (sum(py) / len(py)) * w_veli

    puanlar = []
    benim_kirilim = None
    for u in teachers:
        oid = _ogr_id(u)
        kirilim = {
            "etkinlik": u.get("puan", 0),
            "rozet": rozet_by_user.get(u["id"], 0),
            "ogrenci": ogr_say.get(oid, 0) * w_ogr,
            "kur": kur_say.get(oid, 0) * w_kur,
            "veli": round(veli_bonus.get(oid, 0)),
        }
        toplam = sum(kirilim.values())
        puanlar.append({"id": u["id"], "toplam": toplam})
        if u["id"] == current_user.get("id"):
            benim_kirilim = kirilim
    puanlar.sort(key=lambda x: x["toplam"], reverse=True)

    M = len(puanlar)
    benim_id = current_user.get("id")
    benim_sira = None
    benim_puan = 0
    for i, p in enumerate(puanlar):
        if p["id"] == benim_id:
            benim_sira = i + 1
            benim_puan = p["toplam"]
            break

    degerler = [p["toplam"] for p in puanlar]
    if M > 0:
        ortalama = round(sum(degerler) / M)
        en_yuksek = max(degerler)
        en_dusuk = min(degerler)
        sirali = sorted(degerler)
        mid = M // 2
        medyan = sirali[mid] if M % 2 == 1 else round((sirali[mid - 1] + sirali[mid]) / 2)
    else:
        ortalama = en_yuksek = en_dusuk = medyan = 0

    # Motivasyon mesajı (isim vermeden, konuma göre)
    if M <= 1:
        mesaj = "Sen tek öğretmensin, harika iş çıkarıyorsun! 🌟"
    elif benim_sira:
        yuzde = benim_sira / M  # küçük = üst
        if yuzde <= 0.25:
            mesaj = "Harika iş çıkarıyorsun! Öğretmenlerin ilk %25'indesin. 🏆"
        elif yuzde <= 0.75:
            mesaj = "İyi gidiyorsun. Öğretmenlerin ortalamasının civarındasın — biraz daha içerikle üste çıkabilirsin. 💪"
        else:
            mesaj = "Küçük adımlarla ilerlemek büyük fark yaratır. İçerik ekleyerek puanını hızla artırabilirsin. 🚀"
    else:
        mesaj = "Puan tablosunda yerini almak için içerik ekleyip oylamalara katıl. 🚀"

    return {
        "rol": "ogretmen",
        "kullanicinin_sirasi": benim_sira,
        "toplam_ogretmen": M,
        "kullanicinin_puani": benim_puan,
        "istatistikler": {
            "ortalama_puan_ogretmen": ortalama,
            "en_yuksek_puan": en_yuksek,
            "en_dusuk_puan": en_dusuk,
            "medyan": medyan,
        },
        "motivasyon_mesaji": mesaj,
        "puan_kirilim": benim_kirilim or {"etkinlik": 0, "rozet": 0, "ogrenci": 0, "kur": 0, "veli": 0},
        "puan_agirliklari": {"ogrenci_basi": w_ogr, "kur_basi": w_kur, "veli_yildiz": w_veli},
    }


@router.get("/puan-tablosu")
async def get_puan_tablosu_rol(rol: str, current_user=Depends(get_current_user)):
    """Role göre puan tablosu.
      rol=ogrenci → öğrenciler arası isimli sıralama (öğrenci/admin/coordinator)
      rol=ogretmen → öğretmenler arası agrega (isimsiz); yalnız kendi konum (öğretmen/admin/coordinator)
    """
    hedef = _norm_rol(rol)
    if not hedef:
        raise HTTPException(status_code=400, detail="Geçersiz rol. 'ogrenci' veya 'ogretmen' olmalı.")

    kullanici_rol = current_user.get("role", "")
    hepsine_yetkili = kullanici_rol in ("admin", "coordinator")
    if hedef == "student" and not (hepsine_yetkili or kullanici_rol == "student"):
        raise HTTPException(status_code=403, detail="Bu tabloya erişim yetkiniz yok.")
    if hedef == "teacher" and not (hepsine_yetkili or kullanici_rol == "teacher"):
        raise HTTPException(status_code=403, detail="Bu tabloya erişim yetkiniz yok.")

    if hedef == "student":
        return await _ogrenci_puan_tablosu(current_user)
    return await _ogretmen_puan_tablosu(current_user)


@router.get("/ogretmen/basarilarim")
async def ogretmen_basarilarim(current_user=Depends(get_current_user)):
    """Öğretmene özel başarı özeti: puan konumu, rozetler, veli değerlendirmesi,
    öğrenci/içerik/kur özetleri ve son 12 haftalık zaman serisi. Yalnız teacher."""
    if current_user.get("role", "") != "teacher":
        raise HTTPException(status_code=403, detail="Bu sayfa yalnızca öğretmenler içindir.")

    user_id = current_user["id"]
    ogretmen_id = current_user.get("linked_id") or user_id
    ad_soyad = f"{current_user.get('ad', '')} {current_user.get('soyad', '')}".strip()
    simdi = datetime.utcnow()

    # ── Puan bilgisi (mevcut hesaplayıcıdan) ──
    pt = await _ogretmen_puan_tablosu(current_user)
    ist = pt["istatistikler"]
    puan_bilgisi = {
        "toplam_xp": pt["kullanicinin_puani"],
        "sira": pt["kullanicinin_sirasi"],
        "toplam_ogretmen": pt["toplam_ogretmen"],
        "ortalama_puan": ist["ortalama_puan_ogretmen"],
        "en_yuksek": ist["en_yuksek_puan"],
        "en_dusuk": ist["en_dusuk_puan"],
        "motivasyon_mesaji": pt["motivasyon_mesaji"],
        "kirilim": pt.get("puan_kirilim"),
        "agirliklar": pt.get("puan_agirliklari"),
    }

    # ── Rozetler ──
    ogretmen_rozet_list = await get_ogretmen_rozetleri()
    rozet_def = {r["kod"]: r for r in ogretmen_rozet_list}
    kazanilan = await db.kazanilan_rozetler.find({"kullanici_id": user_id}).to_list(length=None)
    kazanilan_sirali = sorted(kazanilan, key=lambda r: r.get("kazanma_tarihi", ""), reverse=True)
    son_kazanilanlar = []
    for r in kazanilan_sirali[:5]:
        d = rozet_def.get(r.get("rozet_kodu"), {})
        son_kazanilanlar.append({
            "ad": d.get("ad", r.get("rozet_kodu", "Rozet")),
            "ikon": d.get("ikon") or d.get("emoji") or "🎖️",
            "kazanma_tarihi": r.get("kazanma_tarihi"),
        })
    rozetler = {
        "kazanilan_sayisi": len(kazanilan),
        "toplam_rozet": len(ogretmen_rozet_list),
        "son_kazanilanlar": son_kazanilanlar,
    }

    # ── Veli değerlendirmesi ──
    try:
        anketler = await db.veli_anketleri.find({"ogretmen_id": ogretmen_id}).to_list(length=None)
        anket_puanlari = []
        for a in anketler:
            py = [y.get("puan", 0) for y in (a.get("yanitlar") or []) if isinstance(y, dict) and y.get("puan")]
            if py:
                anket_puanlari.append(sum(py) / len(py))
        veli_degerlendirmesi = {
            "ortalama": round(sum(anket_puanlari) / len(anket_puanlari), 1) if anket_puanlari else 0,
            "toplam_anket": len(anketler),
        }
    except Exception as ex:
        logging.warning(f"[basarilarim] veli değerlendirmesi hatası: {ex}")
        veli_degerlendirmesi = {"ortalama": 0, "toplam_anket": 0}

    # ── Öğrenci özet (aktif = son 7 gün okuma kaydı olan) ──
    ogrenciler = await db.students.find({"ogretmen_id": ogretmen_id, "arsivli": {"$ne": True}}).to_list(length=None)
    yedi_gun_once = (simdi - timedelta(days=7)).strftime("%Y-%m-%d")
    aktif = 0
    for s in ogrenciler:
        son = await db.reading_logs.find({"ogrenci_id": s["id"]}).sort("tarih", -1).to_list(length=1)
        if son and son[0].get("tarih", "")[:10] >= yedi_gun_once:
            aktif += 1
    # Şimdiye kadar alınan toplam öğrenci (arşivlenmiş/ayrılmış dahil)
    toplam_tum = await db.students.count_documents({"ogretmen_id": ogretmen_id})
    ogrenci_ozet = {
        "toplam_ogrenci": len(ogrenciler),       # şu an aktif kayıtlı
        "toplam_ogrenci_tum": toplam_tum,        # tüm zamanlar (arşivli dahil)
        "aktif_ogrenci": aktif,                  # son 7 günde okuma yapan
    }

    # ── İçerik özet ──
    tum_icerik = await db.gelisim_icerik.find().to_list(length=None)
    olusturulan = sum(1 for ic in tum_icerik if ic.get("ekleyen_id") == user_id)
    onaylanan = sum(1 for ic in tum_icerik if ic.get("ekleyen_id") == user_id and ic.get("durum") == "yayinda")
    oy_verdigi = sum(1 for ic in tum_icerik if user_id in (ic.get("oylar") or {}))
    icerik_ozet = {"olusturulan_icerik": olusturulan, "onaylanan_icerik": onaylanan, "oy_verdigi_icerik": oy_verdigi}

    # ── Kur başarıları (kur_atlamalari koleksiyonundan) ──
    def _guvenli_uc(degerler, en_kucuk):
        """Karışık tip (str/int) kur değerlerinde min/max patlamasın diye güvenli uç."""
        if not degerler:
            return None
        try:
            return min(degerler) if en_kucuk else max(degerler)
        except TypeError:
            try:
                s = sorted(degerler, key=lambda x: str(x))
                return s[0] if en_kucuk else s[-1]
            except Exception:
                return degerler[0]
    try:
        kurlar = await db.kur_atlamalari.find({"ogretmen_id": ogretmen_id}).to_list(length=None)
        gruplar = {}
        for k in kurlar:
            gruplar.setdefault(k.get("ogrenci_id"), []).append(k)
        en_uzun_takip = None
        for oid, kayitlar in gruplar.items():
            adet = len(kayitlar)
            if en_uzun_takip is None or adet > en_uzun_takip["kur_sayisi"]:
                eskiler = [k.get("eski_kur") for k in kayitlar if k.get("eski_kur") is not None]
                yeniler = [k.get("yeni_kur") for k in kayitlar if k.get("yeni_kur") is not None]
                st = await db.students.find_one({"id": oid})
                en_uzun_takip = {
                    "kur_sayisi": adet,
                    "ogrenci_adi": f"{(st or {}).get('ad', '')} {(st or {}).get('soyad', '')}".strip() or "Öğrenci",
                    "baslangic_kur": _guvenli_uc(eskiler, True),
                    "mevcut_kur": _guvenli_uc(yeniler, False),
                }
        kur_basarilari = {
            "toplam_kur_atlatma": len(kurlar),                 # tüm kur atlatma olaylarının toplamı
            "kur_atlatilan_ogrenci_sayisi": len(gruplar),      # kaç farklı öğrenci
            "en_uzun_takip": en_uzun_takip,
        }
    except Exception as ex:
        logging.warning(f"[basarilarim] kur başarıları hatası: {ex}")
        kur_basarilari = {"toplam_kur_atlatma": 0, "kur_atlatilan_ogrenci_sayisi": 0, "en_uzun_takip": None}

    # ── Zaman serisi (son 12 hafta) ──
    # Öğretmenlerin xp_logs kaydı yoktur (xp_logs öğrenci-özeldir); bu yüzden seri,
    # rozet kazanımları (kazanma_tarihi) ve öğretmenin eklediği içeriklerin tarihinden
    # türetilir. Son nokta gerçek toplam puana sabitlenir (anchor).
    HAFTA = 12
    d_xp = [0] * HAFTA
    d_rozet = [0] * HAFTA
    base_xp = 0
    base_rozet = 0
    rozet_puan_map = {r["kod"]: rozet_odul_puan(r) for r in ogretmen_rozet_list}

    def _parse_dt(s):
        """ISO tarihi NAIVE (tz-siz) datetime'a çevirir. tz-aware ise UTC'ye
        çevirip tzinfo düşürülür — `simdi` (utcnow, naive) ile çıkarma güvenli olsun."""
        try:
            d = datetime.fromisoformat((s or "").replace("Z", "+00:00"))
        except Exception:
            return None
        if d.tzinfo is not None:
            d = d.astimezone(timezone.utc).replace(tzinfo=None)
        return d

    def _bucketle(d, xp_puan, rozet_mi):
        nonlocal base_xp, base_rozet
        if not d:
            base_xp += xp_puan
            if rozet_mi:
                base_rozet += 1
            return
        wi = HAFTA - 1 - ((simdi - d).days // 7)
        if wi < 0:
            base_xp += xp_puan
            if rozet_mi:
                base_rozet += 1
        elif wi <= HAFTA - 1:
            d_xp[wi] += xp_puan
            if rozet_mi:
                d_rozet[wi] += 1

    try:
        for r in kazanilan:
            _bucketle(_parse_dt(r.get("kazanma_tarihi")), rozet_puan_map.get(r.get("rozet_kodu"), 0), True)
        for ic in tum_icerik:
            if ic.get("ekleyen_id") != user_id:
                continue
            d = _parse_dt(ic.get("tarih") or ic.get("olusturma_tarihi") or ic.get("created_at"))
            _bucketle(d, 5 if ic.get("durum") == "yayinda" else 1, False)
    except Exception as ex:
        logging.warning(f"[basarilarim] zaman serisi bucketleme hatası: {ex}")
        d_xp = [0] * HAFTA
        d_rozet = [0] * HAFTA
        base_xp = 0
        base_rozet = len(kazanilan)

    # Son kümülatif değeri gerçek toplam puana sabitle
    ofset = (puan_bilgisi.get("toplam_xp") or 0) - (base_xp + sum(d_xp))
    if ofset > 0:
        base_xp += ofset

    xp_gelisim, rozet_gelisim = [], []
    cx, cr = base_xp, base_rozet
    for i in range(HAFTA):
        cx += d_xp[i]
        cr += d_rozet[i]
        xp_gelisim.append(cx)
        rozet_gelisim.append(cr)
    zaman_serisi = {
        "etiketler": [f"Hafta {i + 1}" for i in range(HAFTA)],
        "xp_gelisim": xp_gelisim,
        "rozet_gelisim": rozet_gelisim,
    }

    # ── EK METRİKLER (çıktı / bağlılık / kalite) + dinamik ipuçları ──
    # Hepsi mevcut koleksiyonlardan; her adım güvenli (bölme/tip hataları yutulur).
    ek_metrikler = {}
    ipuclari = []
    try:
        ogrenci_ids = [s["id"] for s in ogrenciler]
        n_ogr = len(ogrenci_ids)

        # reading_logs (tek sorgu) → aktif oran, risk, streak, haftalık dakika
        loglar = await db.reading_logs.find({"ogrenci_id": {"$in": ogrenci_ids}}).to_list(length=None) if ogrenci_ids else []
        log_by = {}
        for l in loglar:
            log_by.setdefault(l.get("ogrenci_id"), []).append(l)
        yedi = (simdi - timedelta(days=7)).strftime("%Y-%m-%d")
        ondort = (simdi - timedelta(days=14)).strftime("%Y-%m-%d")
        aktif_say = risk_say = streak_top = haftalik_dk_top = 0
        for oid in ogrenci_ids:
            ls = log_by.get(oid, [])
            gunler = sorted({(l.get("tarih", "") or "")[:10] for l in ls if l.get("tarih")}, reverse=True)
            son_gun = gunler[0] if gunler else ""
            if son_gun >= yedi:
                aktif_say += 1
            if not son_gun or son_gun < ondort:
                risk_say += 1
            st = 0
            for i in range(60):
                g = (simdi - timedelta(days=i)).strftime("%Y-%m-%d")
                if g in gunler:
                    st += 1
                elif i > 0:
                    break
            streak_top += st
            haftalik_dk_top += sum(l.get("sure_dakika", 0) for l in ls if (l.get("tarih", "") or "")[:10] >= yedi)
        baglilik = {
            "aktif_oran": round(aktif_say / n_ogr * 100) if n_ogr else 0,
            "risk_ogrenci": risk_say,
            "ortalama_streak": round(streak_top / n_ogr, 1) if n_ogr else 0,
            "haftalik_ort_dakika": round(haftalik_dk_top / n_ogr) if n_ogr else 0,
        }

        # Okuma gelişimi (diagnostic_oturumlar: ilk vs son wpm/doğruluk)
        wpm_artis, dog_artis = [], []
        if ogrenci_ids:
            diag = await db.diagnostic_oturumlar.find({"ogrenci_id": {"$in": ogrenci_ids}, "durum": "tamamlandi"}).to_list(length=None)
            diag_by = {}
            for dd in diag:
                diag_by.setdefault(dd.get("ogrenci_id"), []).append(dd)
            for _oid, ses in diag_by.items():
                ses.sort(key=lambda x: x.get("tamamlama_tarihi", "") or "")
                if len(ses) >= 2:
                    wpm_artis.append((ses[-1].get("wpm", 0) or 0) - (ses[0].get("wpm", 0) or 0))
                    dog_artis.append((ses[-1].get("dogruluk_yuzde", 0) or 0) - (ses[0].get("dogruluk_yuzde", 0) or 0))
        okuma_gelisim = {
            "wpm_artis": round(sum(wpm_artis) / len(wpm_artis), 1) if wpm_artis else 0,
            "dogruluk_artis": round(sum(dog_artis) / len(dog_artis), 1) if dog_artis else 0,
            "olculen_ogrenci": len(wpm_artis),
        }

        # Anlama (gelisim_tamamlama; öğrenci user-id eşlemesiyle)
        anlama_yuzde, anlama_test = 0, 0
        if ogrenci_ids:
            ogr_users = await db.users.find({"role": "student", "linked_id": {"$in": ogrenci_ids}}).to_list(length=None)
            ogr_user_ids = [u["id"] for u in ogr_users]
            if ogr_user_ids:
                tamamlar = await db.gelisim_tamamlama.find({"kullanici_id": {"$in": ogr_user_ids}, "test_yapildi": True}).to_list(length=None)
                td = sum(t.get("dogru_sayisi", 0) for t in tamamlar)
                ts = sum(t.get("toplam_soru", 0) for t in tamamlar)
                anlama_test = len(tamamlar)
                anlama_yuzde = round(td / ts * 100) if ts else 0
        anlama = {"ortalama_yuzde": anlama_yuzde, "test_sayisi": anlama_test}

        # Görev tamamlama oranı
        gorevlerim = await db.gorevler.find({"atayan_id": user_id}).to_list(length=None)
        g_atanan = len(gorevlerim)
        g_tamam = sum(1 for g in gorevlerim if g.get("durum") == "tamamlandi")
        gorev = {"atanan": g_atanan, "tamamlanan": g_tamam, "oran": round(g_tamam / g_atanan * 100) if g_atanan else 0}

        # İçerik kalitesi + etki
        benim_icerikler = [ic for ic in tum_icerik if ic.get("ekleyen_id") == user_id]
        oy_oranlari = []
        for ic in benim_icerikler:
            oylar = ic.get("oylar") or {}
            if oylar:
                onay = sum(1 for o in oylar.values() if (o or {}).get("onay"))
                oy_oranlari.append(onay / len(oylar) * 100)
        benim_icerik_ids = [ic.get("id") for ic in benim_icerikler if ic.get("id")]
        etki_ogr = set()
        if benim_icerik_ids:
            etki_t = await db.gelisim_tamamlama.find({"icerik_id": {"$in": benim_icerik_ids}}).to_list(length=None)
            etki_ogr = {t.get("kullanici_id") for t in etki_t if t.get("kullanici_id")}
        icerik_kalitesi = {
            "onay_orani": round(onaylanan / olusturulan * 100) if olusturulan else 0,
            "ortalama_oy": round(sum(oy_oranlari) / len(oy_oranlari)) if oy_oranlari else 0,
            "etki_ogrenci_sayisi": len(etki_ogr),
        }

        # Veli ilişkisi (yanıt oranı + tavsiye oranı)
        veli_ids = {s.get("veli_id") for s in ogrenciler if s.get("veli_id")}
        yanitlayan = len({a.get("veli_id") for a in anketler if a.get("veli_id")}) or len(anketler)
        tavsiye_say = sum(1 for a in anketler if a.get("tavsiye"))
        veli = {
            "yanit_orani": round(min(yanitlayan, len(veli_ids)) / len(veli_ids) * 100) if veli_ids else 0,
            "tavsiye_orani": round(tavsiye_say / len(anketler) * 100) if anketler else 0,
        }

        # İletişim (cevaplanan gönderen oranı)
        gelen = await db.mesajlar.find({"alici_id": user_id}).to_list(length=None)
        giden = await db.mesajlar.find({"gonderen_id": user_id}).to_list(length=None)
        gelen_kisi = {m.get("gonderen_id") for m in gelen if m.get("gonderen_id")}
        giden_kisi = {m.get("alici_id") for m in giden if m.get("alici_id")}
        iletisim = {
            "yanit_orani": round(len(gelen_kisi & giden_kisi) / len(gelen_kisi) * 100) if gelen_kisi else 0,
            "gelen_mesaj": len(gelen),
        }

        # Kur hızı (ardışık atlamalar arası ortalama gün) — bağımsız sorgu
        kur_gaplar = []
        kur_kayit = await db.kur_atlamalari.find({"ogretmen_id": ogretmen_id}).to_list(length=None)
        kur_grup = {}
        for k in kur_kayit:
            kur_grup.setdefault(k.get("ogrenci_id"), []).append(k)
        for _oid, kayitlar in kur_grup.items():
            tarihli = sorted(d for d in (_parse_dt(k.get("tarih")) for k in kayitlar) if d)
            for a, b in zip(tarihli, tarihli[1:]):
                kur_gaplar.append((b - a).days)
        kur_hizi = {"ortalama_gun": round(sum(kur_gaplar) / len(kur_gaplar)) if kur_gaplar else 0}

        ek_metrikler = {
            "okuma_gelisim": okuma_gelisim,
            "anlama": anlama,
            "gorev": gorev,
            "baglilik": baglilik,
            "icerik_kalitesi": icerik_kalitesi,
            "veli": veli,
            "iletisim": iletisim,
            "kur_hizi": kur_hizi,
        }

        # ── Dinamik ipuçları (öncelik puanına göre en zayıf noktalar önce) ──
        aday = []
        if baglilik["risk_ogrenci"] > 0:
            aday.append((90, {"ikon": "🚨", "baslik": "Riskli öğrencilere ulaş",
                "mesaj": f"{baglilik['risk_ogrenci']} öğrencin 2 haftadır okuma yapmadı. Kısa bir mesaj ya da küçük bir görev onları geri kazanabilir."}))
        if g_atanan > 0 and gorev["oran"] < 60:
            aday.append((80, {"ikon": "📌", "baslik": "Görevleri küçült",
                "mesaj": f"Atadığın görevlerin yalnızca %{gorev['oran']}'ı tamamlanmış. Daha kısa ve ulaşılabilir görevler tamamlanma oranını yükseltir."}))
        if n_ogr > 0 and baglilik["aktif_oran"] < 60:
            aday.append((75, {"ikon": "🔥", "baslik": "Sürekliliği artır",
                "mesaj": f"Aktif öğrenci oranın %{baglilik['aktif_oran']}. Günlük 10 dakikalık küçük okuma hedefleri aktifliği ve seriyi büyütür."}))
        if olusturulan >= 3 and icerik_kalitesi["onay_orani"] < 70:
            aday.append((70, {"ikon": "📝", "baslik": "İçerik kalitesini yükselt",
                "mesaj": f"İçeriklerinin %{icerik_kalitesi['onay_orani']}'i yayında. Reddedilenleri gözden geçirmek hem puan hem etki kazandırır."}))
        if okuma_gelisim["olculen_ogrenci"] > 0 and okuma_gelisim["wpm_artis"] <= 0:
            aday.append((68, {"ikon": "📈", "baslik": "Okuma hızını çalıştır",
                "mesaj": "Öğrencilerinin okuma hızında belirgin artış görünmüyor. Tekrarlı okuma ve sesli okuma egzersizleri hızı yükseltir."}))
        if veli_ids and veli["yanit_orani"] < 50:
            aday.append((60, {"ikon": "⭐", "baslik": "Veli görüşü topla",
                "mesaj": f"Velilerin %{veli['yanit_orani']}'i anket doldurmuş. Veli geri bildirimi güven oluşturur ve rozet kazandırır."}))
        if n_ogr > 0 and baglilik["ortalama_streak"] < 3:
            aday.append((55, {"ikon": "📅", "baslik": "Günlük alışkanlık kur",
                "mesaj": "Öğrencilerinin ortalama okuma serisi düşük. Kısa günlük hatırlatmalar seriyi belirgin şekilde büyütür."}))
        if gelen_kisi and iletisim["yanit_orani"] < 70:
            aday.append((50, {"ikon": "💬", "baslik": "Mesajlara dönüş yap",
                "mesaj": f"Sana yazanların %{iletisim['yanit_orani']}'ine dönüş yapmışsın. Hızlı geri bildirim öğrenci/veli bağını güçlendirir."}))
        # Evergreen öneriler (liste asla boş kalmasın)
        aday.append((20, {"ikon": "🧠", "baslik": "Sokratik sorular sor",
            "mesaj": "Okuma sonrası 'neden/nasıl' soruları anlama derinliğini artırır — Kitap Dersi ve Sokratik araçlarını dene."}))
        aday.append((15, {"ikon": "🎯", "baslik": "Küçük hedefler koy",
            "mesaj": "Haftalık ölçülebilir küçük hedefler (2 kitap, 3 egzersiz) hem öğrenciyi hem metriklerini ileri taşır."}))
        aday.sort(key=lambda x: x[0], reverse=True)
        ipuclari = [t for _, t in aday[:5]]
    except Exception as ex:
        logging.warning(f"[basarilarim] ek metrik/ipucu hatası: {ex}")
        if not ipuclari:
            ipuclari = [{"ikon": "🎯", "baslik": "Küçük hedefler koy",
                         "mesaj": "Haftalık küçük ve ölçülebilir hedefler öğrenci gelişimini hızlandırır."}]

    return {
        "ogretmen_id": user_id,
        "ad_soyad": ad_soyad,
        "puan_bilgisi": puan_bilgisi,
        "rozetler": rozetler,
        "veli_degerlendirmesi": veli_degerlendirmesi,
        "ogrenci_ozet": ogrenci_ozet,
        "icerik_ozet": icerik_ozet,
        "kur_basarilari": kur_basarilari,
        "zaman_serisi": zaman_serisi,
        "ek_metrikler": ek_metrikler,
        "ipuclari": ipuclari,
    }


@router.get("/gelisim/peer-rozet")
async def get_peer_rozet(current_user=Depends(get_current_user)):
    """Kullanıcının haftalık oy sayısı ve toplam peer-review rozeti.

    (Eskiden pasif arşivdeydi; frontend arka planda çağırdığı için 404 dönüyordu.
    Aktif modüle taşındı; hata durumunda güvenli varsayılan döner.)
    """
    try:
        haftanin_basi = datetime.utcnow() - timedelta(days=datetime.utcnow().weekday())
        haftanin_basi = haftanin_basi.replace(hour=0, minute=0, second=0, microsecond=0)

        haftalik = await db.gelisim_oylar.count_documents({
            "kullanici_id": current_user["id"],
            "tarih": {"$gte": haftanin_basi},
        })
        toplam = await db.gelisim_oylar.count_documents({"kullanici_id": current_user["id"]})

        rozet = "Bronz Onaycı"
        if toplam >= 50:
            rozet = "Platin Uzman"
        elif toplam >= 20:
            rozet = "Altın Moderatör"
        elif toplam >= 5:
            rozet = "Gümüş Değerlendirici"

        return {
            "haftalik_oy": haftalik,
            "haftalik_limit": 5,
            "toplam_oy": toplam,
            "rozet": rozet,
            "kalan": max(0, 5 - haftalik),
        }
    except Exception as e:
        logging.warning(f"[peer-rozet] {e}")
        return {"haftalik_oy": 0, "haftalik_limit": 5, "toplam_oy": 0, "rozet": "Bronz Onaycı", "kalan": 5}


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
    """Kullanicinin hak ettigi rozetleri degerlendirir (veri-odakli motor).

    Geriye donuk uyumlu: eski frontend dashboard yuklemesinde cagirilir. Kosullar
    artik sabit if-else yerine core.rozet_motor uzerinden veri-odakli islenir."""
    user_id = current_user["id"]
    yeni_rozetler = await rozet_degerlendir(user_id, tetikleyen_event="kontrol")
    toplam = await db.kazanilan_rozetler.count_documents({"kullanici_id": user_id})
    return {"yeni_rozetler": yeni_rozetler, "toplam": toplam}




