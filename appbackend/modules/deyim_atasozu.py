"""Deyim, Atasözü ve Tekerleme modülü.

MEB Kelimeleri'nin yanında ikinci bir dil-varlığı havuzu: deyim/atasözü (anlam
odaklı) ve tekerleme (akıcı okuma odaklı). Yönetici/koordinatör manuel veya toplu
girer; deyim/atasözü için anlam boşsa arka planda AI ile doldurulur. Bu havuz,
Egzersiz Motoru'nda `deyim_*`/`tekerleme_*` tiplerine kaynak olur (egzersiz_motoru).

Koleksiyon: `db.deyim_atasozu`
  id, tur ("deyim"|"atasozu"|"tekerleme"), icerik, anlam, ornek_cumle,
  sinif_seviyesi, durum ("aktif"|"arsivli"), kullanim_sayisi,
  yukleyen_id, yukleyen_ad, tarih, ai_uretim_tarihi

Yollar (api_router prefix=/api):
  GET    /deyim/turler
  GET    /deyim/liste            (eğitimci — sayfalı/filtreli)
  POST   /deyim/ekle             (admin/koord — tek veya toplu {ogeler:[...]})
  PUT    /deyim/{id}             (eğitimci — anlam/örnek/içerik düzelt)
  DELETE /deyim/{id}             (admin/koord — soft delete)
  POST   /deyim/ai-anlam         (admin/koord — boş anlamları AI ile doldur)
  GET    /deyim/istatistik       (eğitimci — özet)
"""
import uuid
import asyncio
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query

from core.db import db
from core.auth import require_role, UserRole
from core.ai import call_claude

router = APIRouter()

_YAZMA = require_role(UserRole.ADMIN, UserRole.COORDINATOR)
_OKUMA = require_role(UserRole.ADMIN, UserRole.COORDINATOR, UserRole.TEACHER)

TUR_TANIMLARI = [
    {"id": "deyim", "ad": "Deyim", "anlam_gerekli": True},
    {"id": "atasozu", "ad": "Atasözü", "anlam_gerekli": True},
    {"id": "tekerleme", "ad": "Tekerleme", "anlam_gerekli": False},
]
_GECERLI_TUR = {t["id"] for t in TUR_TANIMLARI}


@router.get("/deyim/turler")
async def deyim_turler():
    return {"turler": TUR_TANIMLARI}


@router.post("/deyim/ekle")
async def deyim_ekle(data: dict, current_user=Depends(_YAZMA)):
    """Tek öğe veya toplu ekleme. Tek: {tur, icerik, anlam, ornek_cumle, sinif_seviyesi}.
    Toplu: {ogeler: [ {tur, icerik, ...}, ... ]}. Aynı (tur + içerik) varsa atlanır."""
    ogeler = data.get("ogeler")
    if not ogeler:
        ogeler = [data]
    ad = f"{current_user.get('ad', '')} {current_user.get('soyad', '')}".strip()
    now = datetime.utcnow().isoformat()
    yeni, atlanan, hatali = 0, 0, 0
    ai_gerek = False
    for o in ogeler:
        tur = str(o.get("tur", "")).strip()
        icerik = str(o.get("icerik", "")).strip()
        if tur not in _GECERLI_TUR or len(icerik) < 2:
            hatali += 1
            continue
        try:
            sinif = int(o.get("sinif_seviyesi", o.get("sinif", 3)))
        except Exception:
            sinif = 3
        mevcut = await db.deyim_atasozu.find_one({"tur": tur, "icerik": icerik})
        if mevcut:
            atlanan += 1
            continue
        anlam = str(o.get("anlam", "")).strip()
        await db.deyim_atasozu.insert_one({
            "id": str(uuid.uuid4()),
            "tur": tur,
            "icerik": icerik,
            "anlam": anlam,
            "ornek_cumle": str(o.get("ornek_cumle", "")).strip(),
            "sinif_seviyesi": sinif,
            "durum": "aktif",
            "kullanim_sayisi": 0,
            "yukleyen_id": current_user.get("id"),
            "yukleyen_ad": ad,
            "tarih": now,
            "ai_uretim_tarihi": None,
        })
        yeni += 1
        # deyim/atasözü'nde anlam boşsa AI ile doldurulacak
        if tur in ("deyim", "atasozu") and not anlam:
            ai_gerek = True

    if ai_gerek:
        asyncio.create_task(_ai_anlam_kuyrugu())

    return {"yeni_eklenen": yeni, "mevcut_atlanan": atlanan, "hatali": hatali}


@router.get("/deyim/liste")
async def deyim_liste(
    tur: str | None = Query(None),
    sinif: int | None = Query(None),
    durum: str = Query("aktif"),
    ara: str | None = Query(None),
    sayfa: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    current_user=Depends(_OKUMA),
):
    sorgu: dict = {}
    if tur and tur in _GECERLI_TUR:
        sorgu["tur"] = tur
    if sinif is not None:
        sorgu["sinif_seviyesi"] = int(sinif)
    if durum and durum != "hepsi":
        sorgu["durum"] = durum
    if ara:
        sorgu["icerik"] = {"$regex": ara, "$options": "i"}
    toplam = await db.deyim_atasozu.count_documents(sorgu)
    docs = await db.deyim_atasozu.find(sorgu).sort("tarih", -1) \
        .skip((sayfa - 1) * limit).limit(limit).to_list(length=limit)
    for d in docs:
        d.pop("_id", None)
    return {
        "ogeler": docs, "toplam": toplam, "sayfa": sayfa,
        "sayfa_sayisi": (toplam + limit - 1) // limit,
    }


@router.put("/deyim/{oge_id}")
async def deyim_guncelle(oge_id: str, data: dict, current_user=Depends(_OKUMA)):
    guncelle = {}
    for alan in ("icerik", "anlam", "ornek_cumle"):
        if alan in data:
            guncelle[alan] = str(data[alan]).strip()
    if "sinif_seviyesi" in data:
        try:
            guncelle["sinif_seviyesi"] = int(data["sinif_seviyesi"])
        except Exception:
            pass
    if not guncelle:
        raise HTTPException(status_code=400, detail="Güncellenecek alan yok")
    r = await db.deyim_atasozu.update_one({"id": oge_id}, {"$set": guncelle})
    if r.matched_count == 0:
        raise HTTPException(status_code=404, detail="Öğe bulunamadı")
    return {"ok": True}


@router.delete("/deyim/{oge_id}")
async def deyim_sil(oge_id: str, current_user=Depends(_YAZMA)):
    r = await db.deyim_atasozu.update_one({"id": oge_id}, {"$set": {"durum": "arsivli"}})
    if r.matched_count == 0:
        raise HTTPException(status_code=404, detail="Öğe bulunamadı")
    return {"ok": True}


@router.post("/deyim/ai-anlam")
async def deyim_ai_anlam(data: dict = None, current_user=Depends(_YAZMA)):
    """Anlamı boş deyim/atasözü için AI üretimini tetikler."""
    bekleyen = await db.deyim_atasozu.count_documents(
        {"tur": {"$in": ["deyim", "atasozu"]}, "durum": "aktif",
         "$or": [{"anlam": ""}, {"anlam": None}]})
    if bekleyen:
        asyncio.create_task(_ai_anlam_kuyrugu())
    return {"kuyrukta": bekleyen}


@router.get("/deyim/istatistik")
async def deyim_istatistik(current_user=Depends(_OKUMA)):
    ozet = {}
    for t in TUR_TANIMLARI:
        tid = t["id"]
        toplam = await db.deyim_atasozu.count_documents({"tur": tid, "durum": "aktif"})
        if t["anlam_gerekli"]:
            anlamli = await db.deyim_atasozu.count_documents(
                {"tur": tid, "durum": "aktif", "anlam": {"$nin": [None, ""]}})
            ozet[tid] = {"ad": t["ad"], "toplam": toplam,
                         "anlam_hazir": anlamli, "anlam_bekleyen": toplam - anlamli}
        else:
            # Tekerleme anlam gerektirmez.
            ozet[tid] = {"ad": t["ad"], "toplam": toplam,
                         "anlam_hazir": toplam, "anlam_bekleyen": 0}
    return {"tur_bazli": ozet}


# ── AI anlam üretimi (arka plan) ─────────────────────────────────────────────
async def _ai_anlam_kuyrugu():
    """Anlamı boş deyim/atasözü kayıtlarını AI ile doldurur (batch)."""
    try:
        bekleyenler = await db.deyim_atasozu.find(
            {"tur": {"$in": ["deyim", "atasozu"]}, "durum": "aktif",
             "$or": [{"anlam": ""}, {"anlam": None}]}).to_list(length=200)
        for oge in bekleyenler:
            tur_ad = "deyim" if oge["tur"] == "deyim" else "atasözü"
            sistem = ("Sen bir Türkçe öğretmenisin. Verilen " + tur_ad +
                      " için ilkokul/ortaokul öğrencisinin anlayacağı sade bir anlam "
                      "ve bir örnek cümle üret. SADECE şu JSON: "
                      '{"anlam":"...","ornek_cumle":"..."}')
            try:
                sonuc = await call_claude(sistem, oge["icerik"], max_tokens=300)
                anlam = (sonuc or {}).get("anlam", "") if isinstance(sonuc, dict) else ""
                ornek = (sonuc or {}).get("ornek_cumle", "") if isinstance(sonuc, dict) else ""
                if anlam:
                    guncelle = {"anlam": anlam, "ai_uretim_tarihi": datetime.utcnow().isoformat()}
                    if ornek and not oge.get("ornek_cumle"):
                        guncelle["ornek_cumle"] = ornek
                    await db.deyim_atasozu.update_one({"id": oge["id"]}, {"$set": guncelle})
            except Exception as ex:
                logging.warning(f"[deyim ai-anlam] üretim hatası ({oge.get('icerik')}): {ex}")
    except Exception as ex:
        logging.error(f"[deyim ai-anlam] kuyruk hatası: {ex}")


async def deyim_ogeler(sinif: int, turler: list[str], limit: int = 30) -> list[dict]:
    """Egzersiz üretimi için: sınıf<=sinif, anlamlı (deyim/atasözü) veya tekerleme
    öğelerini döner (en az kullanılan önce). egzersiz_motoru tarafından çağrılır."""
    sorgu: dict = {"tur": {"$in": turler}, "durum": "aktif",
                   "sinif_seviyesi": {"$lte": int(sinif)}}
    # deyim/atasözü egzersizleri anlam gerektirir; tekerleme gerektirmez.
    if "tekerleme" not in turler:
        sorgu["anlam"] = {"$nin": [None, ""]}
    try:
        docs = await db.deyim_atasozu.find(sorgu).sort("kullanim_sayisi", 1).to_list(length=limit)
        for d in docs:
            d.pop("_id", None)
        return docs
    except Exception as ex:
        logging.warning(f"[deyim_ogeler] {ex}")
        return []
