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
import logging

from fastapi import APIRouter, Depends

from core.db import db
from core.auth import require_role, UserRole

router = APIRouter()

_ERISIM = require_role(UserRole.ADMIN, UserRole.ACCOUNTANT)


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
            "yapilmasi_gereken_odeme": 1, "yapilan_odeme": 1, "ogretmene_yapilacak_odeme": 1,
        }):
            gereken = _num(s.get("yapilmasi_gereken_odeme"))
            yapilan = _num(s.get("yapilan_odeme"))
            ogrenciler.append({
                "id": s.get("id"),
                "ad": s.get("ad", ""),
                "soyad": s.get("soyad", ""),
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
            "_id": 0, "id": 1, "ad": 1, "soyad": 1,
            "yapilmasi_gereken_odeme": 1, "yapilan_odeme": 1,
        }):
            gereken = _num(t.get("yapilmasi_gereken_odeme"))
            yapilan = _num(t.get("yapilan_odeme"))
            ogretmenler.append({
                "id": t.get("id"),
                "ad": t.get("ad", ""),
                "soyad": t.get("soyad", ""),
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
