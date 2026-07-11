"""Dinamik eğitim türleri — öğrencinin aldığı eğitim seçenekleri yöneticiden yönetilir.

Önceden `aldigi_egitim` serbest string + frontend'de 2 yerde hardcoded 8'li listeydi.
Artık `db.egitim_turleri` koleksiyonundan gelir; yönetici ekler/düzenler/pasife alır.
Kategori: "genel" (okuma becerileri) veya "brans" (branş dersleri, ör. Matematik).

Öğrenci kaydındaki `Student.aldigi_egitim` HÂLÂ string'tir (isimle eşleşir) — böylece
mevcut atamalar bozulmaz. Migration: koleksiyon boşsa varsayılan 8 tür + mevcut
öğrencilerdeki tüm farklı `aldigi_egitim` değerleri otomatik eklenir (idempotent).

Yollar (prefix=/api):
  GET    /egitim-turleri            (herkes — dropdownlar; aktif; ?dahil_pasif=true admin)
  POST   /egitim-turleri            (admin/koord — ekle)
  PUT    /egitim-turleri/{id}       (admin/koord — ad/kategori/sira/durum)
  DELETE /egitim-turleri/{id}       (admin/koord — pasife al = soft)
"""
import uuid
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException

from core.db import db
from core.auth import get_current_user, require_role, UserRole

router = APIRouter()

_YAZMA = require_role(UserRole.ADMIN, UserRole.COORDINATOR)

# Varsayılan türler (eski hardcoded liste) — ilk kurulumda seed edilir.
_VARSAYILAN = [
    "Okuma Becerileri Temel", "Okuma Becerileri İleri", "Hızlı Okuma", "Anlama Becerileri",
    "Yazım Kuralları", "Dikkat Geliştirme", "Kelime Dağarcığı", "Metin Analizi",
]

_kuruldu = False


async def _ilk_kurulum():
    """İdempotent migration: koleksiyon boşsa varsayılanlar + mevcut öğrenci eğitim
    türlerini seed eder. Hiçbir öğrenci ataması değişmez (yalnız tür listesi dolar)."""
    global _kuruldu
    if _kuruldu:
        return
    try:
        if await db.egitim_turleri.count_documents({}) == 0:
            adlar = list(_VARSAYILAN)
            # Mevcut öğrencilerdeki farklı aldigi_egitim değerlerini de ekle (kaybolmasın).
            try:
                mevcut = await db.students.distinct("aldigi_egitim")
                for m in mevcut:
                    if m and str(m).strip() and str(m).strip() not in adlar:
                        adlar.append(str(m).strip())
            except Exception:
                pass
            now = datetime.utcnow().isoformat()
            await db.egitim_turleri.insert_many([
                {"id": str(uuid.uuid4()), "ad": ad, "kategori": "genel", "sira": i,
                 "durum": "aktif", "tarih": now}
                for i, ad in enumerate(adlar)
            ])
            logging.info(f"[egitim_turleri] ilk kurulum: {len(adlar)} tür seed edildi")
        _kuruldu = True
    except Exception as ex:
        logging.warning(f"[egitim_turleri] ilk kurulum hatası: {ex}")


@router.get("/egitim-turleri")
async def egitim_turleri_listesi(dahil_pasif: bool = False, current_user=Depends(get_current_user)):
    """Eğitim türleri. Varsayılan yalnız aktif (dropdownlar için); dahil_pasif=true ise
    pasifler de (yönetim ekranı için). sira'ya göre sıralı."""
    await _ilk_kurulum()
    sorgu = {} if dahil_pasif else {"durum": "aktif"}
    docs = await db.egitim_turleri.find(sorgu, {"_id": 0}).sort("sira", 1).to_list(length=500)
    return {"turler": docs}


@router.post("/egitim-turleri")
async def egitim_turu_ekle(data: dict, current_user=Depends(_YAZMA)):
    await _ilk_kurulum()
    ad = str(data.get("ad", "")).strip()
    if len(ad) < 2:
        raise HTTPException(status_code=422, detail="Eğitim türü adı çok kısa")
    kategori = data.get("kategori", "genel")
    if kategori not in ("genel", "brans"):
        kategori = "genel"
    if await db.egitim_turleri.find_one({"ad": ad}):
        raise HTTPException(status_code=400, detail="Bu eğitim türü zaten var")
    son = await db.egitim_turleri.find_one(sort=[("sira", -1)])
    kayit = {"id": str(uuid.uuid4()), "ad": ad, "kategori": kategori,
             "sira": (son.get("sira", 0) + 1) if son else 0, "durum": "aktif",
             "tarih": datetime.utcnow().isoformat()}
    await db.egitim_turleri.insert_one(kayit)
    kayit.pop("_id", None)
    return {"ok": True, "tur": kayit}


@router.put("/egitim-turleri/{tur_id}")
async def egitim_turu_guncelle(tur_id: str, data: dict, current_user=Depends(_YAZMA)):
    guncelle = {}
    if "ad" in data and str(data["ad"]).strip():
        guncelle["ad"] = str(data["ad"]).strip()
    if data.get("kategori") in ("genel", "brans"):
        guncelle["kategori"] = data["kategori"]
    if data.get("durum") in ("aktif", "pasif"):
        guncelle["durum"] = data["durum"]
    if "sira" in data:
        try:
            guncelle["sira"] = int(data["sira"])
        except (TypeError, ValueError):
            pass
    if not guncelle:
        raise HTTPException(status_code=400, detail="Güncellenecek alan yok")
    r = await db.egitim_turleri.update_one({"id": tur_id}, {"$set": guncelle})
    if r.matched_count == 0:
        raise HTTPException(status_code=404, detail="Eğitim türü bulunamadı")
    return {"ok": True}


@router.delete("/egitim-turleri/{tur_id}")
async def egitim_turu_sil(tur_id: str, current_user=Depends(_YAZMA)):
    """Pasife al (soft) — eski öğrenci kayıtlarında görünür kalır, yeni seçimde çıkmaz."""
    r = await db.egitim_turleri.update_one({"id": tur_id}, {"$set": {"durum": "pasif"}})
    if r.matched_count == 0:
        raise HTTPException(status_code=404, detail="Eğitim türü bulunamadı")
    return {"ok": True}
