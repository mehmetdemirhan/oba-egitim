"""Muhasebe modülü — sade ödeme paneli için kısıtlı uçlar.

Muhasebe (accountant) rolü YALNIZCA ödeme verisine erişir; CRM detayına (veli
bilgisi, notlar, eğitim verileri) erişmez. Bu modül, ödeme paneli için gereken iki
dar-kapsamlı ucu sunar:

  GET /muhasebe/kisiler  → öğrenci/öğretmen listesi, SADECE ad-soyad + ödeme alanları
  GET /muhasebe/ozet     → KPI özeti (beklenen/tahsil/bekleyen; ödenecek/ödenen)

Erişim: admin + accountant. KPI'lar kişi alanlarından (yapilmasi_gereken_odeme /
yapilan_odeme) hesaplanır — db.payments tahakkuk+tahsilatı karıştırdığı için işlem
toplamı değil kişi bakiyeleri esas alınır. Ödeme geçmişi için /payments kullanılır.
"""
import uuid
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException

from core.db import db
from core.auth import require_role, UserRole

router = APIRouter()

_ERISIM = require_role(UserRole.ADMIN, UserRole.ACCOUNTANT)

# Satır içi düzenlemede izin verilen alanlar (whitelist) — tip bazlı.
_DUZENLENEBILIR = {
    "ogrenci": {"ad", "soyad", "veli_ad", "veli_soyad", "veli_telefon",
                "yapilmasi_gereken_odeme", "yapilan_odeme", "muhasebe_notu"},
    "ogretmen": {"ad", "soyad", "yapilmasi_gereken_odeme", "yapilan_odeme", "muhasebe_notu"},
}
_PARA_ALANLAR = {"yapilmasi_gereken_odeme", "yapilan_odeme"}
_KOLEKSIYON = {"ogrenci": "students", "ogretmen": "teachers"}


async def _log(user: dict, hedef_tip: str, hedef_id: str, alan: str, eski, yeni):
    """Hafif audit: finansal/kişi alanı değişikliğini db.muhasebe_log'a yazar."""
    try:
        await db.muhasebe_log.insert_one({
            "id": str(uuid.uuid4()),
            "kullanici_id": user.get("id"),
            "kullanici_rol": user.get("role"),
            "tarih": datetime.utcnow().isoformat(),
            "hedef_tip": hedef_tip,
            "hedef_id": hedef_id,
            "alan": alan,
            "eski": eski,
            "yeni": yeni,
        })
    except Exception as ex:
        logging.warning(f"[muhasebe_log] yazılamadı: {ex}")


def _num(v) -> float:
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


@router.get("/muhasebe/kisiler")
async def muhasebe_kisiler(current_user=Depends(_ERISIM)):
    """Ödeme kaydı/tablosu için kişi listesi — CRM detayı OLMADAN, sadece ad-soyad
    ve ödeme alanları döner."""
    ogrenciler = []
    try:
        async for s in db.students.find({}, {
            "_id": 0, "id": 1, "ad": 1, "soyad": 1,
            "veli_ad": 1, "veli_soyad": 1, "veli_telefon": 1, "muhasebe_notu": 1,
            "yapilmasi_gereken_odeme": 1, "yapilan_odeme": 1, "ogretmene_yapilacak_odeme": 1,
        }):
            gereken = _num(s.get("yapilmasi_gereken_odeme"))
            yapilan = _num(s.get("yapilan_odeme"))
            ogrenciler.append({
                "id": s.get("id"),
                "ad": s.get("ad", ""),
                "soyad": s.get("soyad", ""),
                "veli_ad": s.get("veli_ad", ""),
                "veli_soyad": s.get("veli_soyad", ""),
                "veli_telefon": s.get("veli_telefon", ""),
                "muhasebe_notu": s.get("muhasebe_notu", ""),
                "yapilmasi_gereken_odeme": gereken,
                "yapilan_odeme": yapilan,
                "kalan": max(0.0, gereken - yapilan),
                "ogretmene_yapilacak_odeme": _num(s.get("ogretmene_yapilacak_odeme")),
            })
    except Exception as ex:
        logging.warning(f"[muhasebe] öğrenci listesi hatası: {ex}")

    ogretmenler = []
    try:
        async for t in db.teachers.find({}, {
            "_id": 0, "id": 1, "ad": 1, "soyad": 1, "muhasebe_notu": 1,
            "yapilmasi_gereken_odeme": 1, "yapilan_odeme": 1,
        }):
            gereken = _num(t.get("yapilmasi_gereken_odeme"))
            yapilan = _num(t.get("yapilan_odeme"))
            ogretmenler.append({
                "id": t.get("id"),
                "ad": t.get("ad", ""),
                "soyad": t.get("soyad", ""),
                "muhasebe_notu": t.get("muhasebe_notu", ""),
                "yapilmasi_gereken_odeme": gereken,
                "yapilan_odeme": yapilan,
                "kalan": max(0.0, gereken - yapilan),
            })
    except Exception as ex:
        logging.warning(f"[muhasebe] öğretmen listesi hatası: {ex}")

    return {"ogrenciler": ogrenciler, "ogretmenler": ogretmenler}


@router.get("/muhasebe/ozet")
async def muhasebe_ozet(current_user=Depends(_ERISIM)):
    """KPI özeti — kişi bakiyelerinden hesaplanır.
    Öğrenci: beklenen tahsilat / tahsil edilen / bekleyen.
    Öğretmen: ödenecek / ödenen / kalan."""
    ogr_beklenen = ogr_tahsil = 0.0
    try:
        async for s in db.students.find({}, {"_id": 0, "yapilmasi_gereken_odeme": 1, "yapilan_odeme": 1}):
            ogr_beklenen += _num(s.get("yapilmasi_gereken_odeme"))
            ogr_tahsil += _num(s.get("yapilan_odeme"))
    except Exception as ex:
        logging.warning(f"[muhasebe] öğrenci özet hatası: {ex}")

    ogt_odenecek = ogt_odenen = 0.0
    try:
        async for t in db.teachers.find({}, {"_id": 0, "yapilmasi_gereken_odeme": 1, "yapilan_odeme": 1}):
            ogt_odenecek += _num(t.get("yapilmasi_gereken_odeme"))
            ogt_odenen += _num(t.get("yapilan_odeme"))
    except Exception as ex:
        logging.warning(f"[muhasebe] öğretmen özet hatası: {ex}")

    return {
        "ogrenci": {
            "beklenen": round(ogr_beklenen, 2),
            "tahsil_edilen": round(ogr_tahsil, 2),
            "bekleyen": round(max(0.0, ogr_beklenen - ogr_tahsil), 2),
        },
        "ogretmen": {
            "odenecek": round(ogt_odenecek, 2),
            "odenen": round(ogt_odenen, 2),
            "kalan": round(max(0.0, ogt_odenecek - ogt_odenen), 2),
        },
    }


@router.patch("/muhasebe/kisi/{tip}/{kisi_id}")
async def muhasebe_kisi_duzenle(tip: str, kisi_id: str, data: dict, current_user=Depends(_ERISIM)):
    """Satır içi (hücre bazlı) düzenleme — yalnız değişen alan(lar) gönderilir.
    İzinli alanlar tip'e göre whitelist'lenir; para alanları negatif olamaz.
    Her değişiklik db.muhasebe_log'a yazılır (kim/ne zaman/eski→yeni)."""
    if tip not in _KOLEKSIYON:
        raise HTTPException(status_code=400, detail="Geçersiz tip")
    izinli = _DUZENLENEBILIR[tip]
    koleksiyon = getattr(db, _KOLEKSIYON[tip])
    kayit = await koleksiyon.find_one({"id": kisi_id})
    if not kayit:
        raise HTTPException(status_code=404, detail="Kişi bulunamadı")

    guncelle = {}
    for alan, deger in (data or {}).items():
        if alan not in izinli:
            continue
        if alan in _PARA_ALANLAR:
            try:
                deger = round(float(deger), 2)
            except (TypeError, ValueError):
                raise HTTPException(status_code=422, detail=f"{alan} sayısal olmalı")
            if deger < 0:
                raise HTTPException(status_code=422, detail=f"{alan} negatif olamaz")
        else:
            deger = str(deger).strip()
        guncelle[alan] = deger

    if not guncelle:
        raise HTTPException(status_code=400, detail="Düzenlenebilir alan yok")

    await koleksiyon.update_one({"id": kisi_id}, {"$set": guncelle})
    for alan, yeni in guncelle.items():
        await _log(current_user, tip, kisi_id, alan, kayit.get(alan), yeni)

    guncel = await koleksiyon.find_one({"id": kisi_id}, {"_id": 0})
    gereken = _num(guncel.get("yapilmasi_gereken_odeme"))
    yapilan = _num(guncel.get("yapilan_odeme"))
    return {"ok": True, "kalan": max(0.0, gereken - yapilan),
            "guncellenen": list(guncelle.keys())}


@router.post("/muhasebe/ogrenci/{ogrenci_id}/kur-ucreti")
async def kur_ucreti_ekle(ogrenci_id: str, data: dict, current_user=Depends(_ERISIM)):
    """Yeni kur/dönem ücreti ekler: db.kur_ucretleri'ne detay kaydı + öğrencinin
    beklenen toplamını (yapilmasi_gereken_odeme) `$inc` ile artırır. Beklenenin tek
    kaynağı hâlâ yapilmasi_gereken_odeme'dir (dashboard/hesap mantığı korunur)."""
    ogr = await db.students.find_one({"id": ogrenci_id})
    if not ogr:
        raise HTTPException(status_code=404, detail="Öğrenci bulunamadı")
    kur_adi = str(data.get("kur_adi", "")).strip()
    try:
        tutar = round(float(data.get("tutar")), 2)
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail="Tutar sayısal olmalı")
    if not kur_adi or tutar <= 0:
        raise HTTPException(status_code=422, detail="Kur adı ve pozitif tutar gerekli")
    kayit = {
        "id": str(uuid.uuid4()),
        "ogrenci_id": ogrenci_id,
        "kur_adi": kur_adi,
        "tutar": tutar,
        "baslangic_tarihi": str(data.get("baslangic_tarihi", "")).strip() or None,
        "tarih": datetime.utcnow().isoformat(),
        "ekleyen_id": current_user.get("id"),
    }
    await db.kur_ucretleri.insert_one(kayit)
    eski = _num(ogr.get("yapilmasi_gereken_odeme"))
    await db.students.update_one({"id": ogrenci_id}, {"$inc": {"yapilmasi_gereken_odeme": tutar}})
    await _log(current_user, "ogrenci", ogrenci_id, "kur_ucreti_ekle", eski, round(eski + tutar, 2))
    return {"ok": True, "yeni_beklenen": round(eski + tutar, 2), "kur_ucreti_id": kayit["id"]}


@router.get("/muhasebe/ogrenci/{ogrenci_id}/kur-ucretleri")
async def kur_ucretleri_listesi(ogrenci_id: str, current_user=Depends(_ERISIM)):
    """Öğrencinin eklenmiş kur/dönem ücretleri (kırılım/geçmiş)."""
    docs = await db.kur_ucretleri.find({"ogrenci_id": ogrenci_id}, {"_id": 0}) \
        .sort("tarih", -1).to_list(length=500)
    return {"ogeler": docs}


@router.get("/muhasebe/log")
async def muhasebe_log_listesi(hedef_id: str | None = None, limit: int = 100,
                               current_user=Depends(require_role(UserRole.ADMIN))):
    """Değişiklik izi (yalnız admin). hedef_id verilirse o kişiye filtrelenir."""
    sorgu = {"hedef_id": hedef_id} if hedef_id else {}
    docs = await db.muhasebe_log.find(sorgu, {"_id": 0}).sort("tarih", -1) \
        .to_list(length=min(limit, 500))
    return {"kayitlar": docs}
