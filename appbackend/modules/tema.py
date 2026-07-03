"""Tema modülü (/tema/*) — tema tanımları + kullanıcı tercihi + (FAZ 3) yönetim.

FAZ 2 kapsamı: OKUMA + ÇÖZÜMLEME (ThemeProvider bunları kullanır)
  - GET  /tema/hazir            hazır temalar (public)
  - GET  /tema/aktif            giriş yapan kullanıcının çözümlenmiş aktif teması
  - GET  /tema/kullanici/tercih kullanıcı tema tercihi
  - POST /tema/kullanici/tercih kullanıcı tema tercihini kaydet
  - GET  /tema/{kod}            tekil tema (public)

FAZ 3'te admin CRUD + logo yükleme aynı router'a eklenir.

Tema çözümleme önceliği: kullanıcı tercihi → rol varsayılanı → sistem varsayılanı
→ "deniz" fallback.
"""
import os
import uuid
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Body, UploadFile, File
from pymongo.errors import DuplicateKeyError

from core.db import db
from core.auth import get_current_user, require_role, UserRole
from core.tema_varsayilan import (
    TEMALAR, TOKEN_ALANLARI, SISTEM_VARSAYILAN_TEMA, ROL_VARSAYILAN_TEMA, tema_getir,
)

DUZENLENEBILIR_ALANLAR = {"ad", "aciklama", "kategori", "hedef_rol", "modlar"}
SILINEMEZ_KATEGORILER = {"hazir", "rol_default"}

router = APIRouter(prefix="/tema", tags=["tema"])

GECERLI_MODLAR = {"light", "dark", "auto"}


def _temizle(doc: dict) -> dict:
    if doc:
        doc.pop("_id", None)
    return doc


async def _tema_listesi(kategori: Optional[str] = None) -> list:
    """theme_configs'ten temalar; koleksiyon boşsa koddan fallback."""
    q = {}
    if kategori:
        q["kategori"] = kategori
    docs = await db.theme_configs.find(q).to_list(length=None)
    if docs:
        return [_temizle(d) for d in docs]
    # Fallback (seed çalışmadıysa)
    return [t for t in TEMALAR if not kategori or t.get("kategori") == kategori]


async def _sistem_varsayilan_kod() -> str:
    doc = await db.sistem_ayarlari.find_one({"tip": "tema_ayarlari"})
    if doc:
        kod = (doc.get("degerler") or {}).get("aktif_tema")
        if kod:
            return kod
    return SISTEM_VARSAYILAN_TEMA


async def _tema_dokuman(kod: str) -> Optional[dict]:
    doc = await db.theme_configs.find_one({"kod": kod})
    if doc:
        return _temizle(doc)
    return tema_getir(kod)


async def resolve_tema(user: Optional[dict]) -> dict:
    """Kullanıcı için aktif temayı + modu çözer.

    Döner: {tema: <tam tema dokümanı>, mod: "light"|"dark"|"auto", kaynak: <str>}
    """
    pref = ((user or {}).get("tema_tercihi") or {})
    kod = pref.get("tema_kodu")
    kaynak = "kullanici"
    if not kod:
        rol = (user or {}).get("role")
        kod = ROL_VARSAYILAN_TEMA.get(rol)
        kaynak = "rol_varsayilan"
    if not kod:
        kod = await _sistem_varsayilan_kod()
        kaynak = "sistem_varsayilan"
    tema = await _tema_dokuman(kod)
    if not tema:
        tema = await _tema_dokuman(SISTEM_VARSAYILAN_TEMA) or tema_getir(SISTEM_VARSAYILAN_TEMA)
        kaynak = "fallback"
    mod = pref.get("mod", "light")
    if mod not in GECERLI_MODLAR:
        mod = "light"
    return {"tema": tema, "mod": mod, "kaynak": kaynak}


# ── Statik/özel yollar ({kod}'dan ÖNCE) ──
@router.get("/hazir")
async def hazir_temalar():
    """Hazır + rol-default temalar (public — login öncesi de erişilebilir)."""
    return await _tema_listesi()


@router.get("/aktif")
async def aktif_tema(current_user=Depends(get_current_user)):
    """Giriş yapan kullanıcının çözümlenmiş aktif teması (ThemeProvider için)."""
    return await resolve_tema(current_user)


@router.get("/kullanici/tercih")
async def kullanici_tercih_getir(current_user=Depends(get_current_user)):
    return (current_user or {}).get("tema_tercihi") or {"tema_kodu": None, "mod": "light"}


@router.post("/kullanici/tercih")
async def kullanici_tercih_kaydet(payload: dict = Body(...), current_user=Depends(get_current_user)):
    """Kullanıcının tema tercihini kaydeder (users.tema_tercihi)."""
    tercih = {
        "tema_kodu": payload.get("tema_kodu"),
        "mod": payload.get("mod", "light"),
        "otomatik_gecis_saati": payload.get("otomatik_gecis_saati"),
    }
    if tercih["mod"] not in GECERLI_MODLAR:
        tercih["mod"] = "light"
    # tema_kodu verildiyse geçerli olmalı
    if tercih["tema_kodu"] and not await _tema_dokuman(tercih["tema_kodu"]):
        raise HTTPException(status_code=400, detail="Geçersiz tema kodu")
    await db.users.update_one({"id": current_user["id"]}, {"$set": {"tema_tercihi": tercih}})
    return {"ok": True, "tema_tercihi": tercih, "cozumlenen": await resolve_tema({**current_user, "tema_tercihi": tercih})}


# ─────────────────────────────────────────────
# ADMIN YÖNETİMİ (FAZ 3) — /{kod}'dan ÖNCE tanımlı statik yollar
# ─────────────────────────────────────────────
@router.get("/tumu")
async def tum_temalar(current_user=Depends(require_role(UserRole.ADMIN))):
    """Tüm temalar (hazır + özel) — admin."""
    temalar = await _tema_listesi()
    aktif = await _sistem_varsayilan_kod()
    return {"temalar": temalar, "sistem_aktif": aktif}


@router.get("/export")
async def tema_export(current_user=Depends(require_role(UserRole.ADMIN))):
    return {"temalar": await _tema_listesi(), "tarih": datetime.utcnow().isoformat()}


@router.post("/import")
async def tema_import(payload: dict = Body(...), current_user=Depends(require_role(UserRole.ADMIN))):
    kayitlar = payload.get("temalar", payload if isinstance(payload, list) else [])
    if not isinstance(kayitlar, list):
        raise HTTPException(status_code=400, detail="'temalar' listesi bekleniyor")
    now = datetime.utcnow().isoformat()
    eklenen, guncellenen, hatali = 0, 0, 0
    for t in kayitlar:
        if not isinstance(t, dict) or not t.get("kod") or not isinstance(t.get("modlar"), dict):
            hatali += 1
            continue
        temiz = {k: v for k, v in t.items() if k in DUZENLENEBILIR_ALANLAR}
        temiz["guncelleme_tarihi"] = now
        res = await db.theme_configs.update_one(
            {"kod": t["kod"]},
            {"$set": temiz, "$setOnInsert": {"kod": t["kod"], "olusturma_tarihi": now}},
            upsert=True,
        )
        if res.upserted_id:
            eklenen += 1
        else:
            guncellenen += 1
    return {"ok": True, "eklenen": eklenen, "guncellenen": guncellenen, "hatali": hatali}


@router.post("")
async def tema_olustur(payload: dict = Body(...), current_user=Depends(require_role(UserRole.ADMIN))):
    """Yeni özel tema ekler."""
    kod = (payload.get("kod") or "").strip()
    if not kod:
        raise HTTPException(status_code=400, detail="kod zorunlu")
    if not isinstance(payload.get("modlar"), dict) or "light" not in payload["modlar"]:
        raise HTTPException(status_code=400, detail="modlar.light zorunlu")
    now = datetime.utcnow().isoformat()
    doc = {
        "kod": kod,
        "ad": payload.get("ad", kod),
        "aciklama": payload.get("aciklama", ""),
        "kategori": payload.get("kategori", "ozel"),
        "hedef_rol": payload.get("hedef_rol"),
        "modlar": payload["modlar"],
        "olusturma_tarihi": now, "guncelleme_tarihi": now,
    }
    try:
        await db.theme_configs.insert_one(doc)
    except DuplicateKeyError:
        raise HTTPException(status_code=409, detail=f"'{kod}' zaten mevcut")
    return _temizle(doc)


@router.post("/aktif-yap/{kod}")
async def tema_aktif_yap(kod: str, current_user=Depends(require_role(UserRole.ADMIN))):
    """Sistem geneli varsayılan temayı ayarlar (sistem_ayarlari.tema_ayarlari)."""
    if not await _tema_dokuman(kod):
        raise HTTPException(status_code=404, detail="Tema bulunamadı")
    await db.sistem_ayarlari.update_one(
        {"tip": "tema_ayarlari"},
        {"$set": {"tip": "tema_ayarlari", "degerler": {"aktif_tema": kod},
                  "guncelleme_tarihi": datetime.utcnow().isoformat()}},
        upsert=True,
    )
    return {"ok": True, "sistem_aktif": kod}


@router.post("/logo")
async def tema_logo_yukle(dosya: UploadFile = File(...), current_user=Depends(require_role(UserRole.ADMIN))):
    """Logo yükler (/uploads/logo/), URL'i tema_ayarlari'na yazar."""
    uzanti = (os.path.splitext(dosya.filename or "")[1] or ".png").lower()
    if uzanti not in (".png", ".jpg", ".jpeg", ".svg", ".webp"):
        raise HTTPException(status_code=400, detail="Desteklenmeyen format")
    klasor = Path(__file__).resolve().parent.parent / "uploads" / "logo"
    klasor.mkdir(parents=True, exist_ok=True)
    ad = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}{uzanti}"
    (klasor / ad).write_bytes(await dosya.read())
    url = f"/uploads/logo/{ad}"
    await db.sistem_ayarlari.update_one(
        {"tip": "tema_ayarlari"},
        {"$set": {"tip": "tema_ayarlari", "logo_url": url,
                  "guncelleme_tarihi": datetime.utcnow().isoformat()}},
        upsert=True,
    )
    return {"ok": True, "logo_url": url}


@router.put("/{kod}")
async def tema_guncelle(kod: str, payload: dict = Body(...), current_user=Depends(require_role(UserRole.ADMIN))):
    mevcut = await db.theme_configs.find_one({"kod": kod})
    if not mevcut:
        raise HTTPException(status_code=404, detail="Tema bulunamadı")
    guncel = {k: v for k, v in payload.items() if k in DUZENLENEBILIR_ALANLAR}
    guncel["guncelleme_tarihi"] = datetime.utcnow().isoformat()
    await db.theme_configs.update_one({"kod": kod}, {"$set": guncel})
    return _temizle(await db.theme_configs.find_one({"kod": kod}))


@router.delete("/{kod}")
async def tema_sil(kod: str, current_user=Depends(require_role(UserRole.ADMIN))):
    mevcut = await db.theme_configs.find_one({"kod": kod})
    if not mevcut:
        raise HTTPException(status_code=404, detail="Tema bulunamadı")
    if mevcut.get("kategori") in SILINEMEZ_KATEGORILER:
        raise HTTPException(status_code=400, detail="Hazır/rol-varsayılan temalar silinemez")
    await db.theme_configs.delete_one({"kod": kod})
    return {"ok": True}


@router.get("/{kod}")
async def tema_getir_tekil(kod: str):
    tema = await _tema_dokuman(kod)
    if not tema:
        raise HTTPException(status_code=404, detail="Tema bulunamadı")
    return tema
