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
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Body

from core.db import db
from core.auth import get_current_user
from core.tema_varsayilan import (
    TEMALAR, TOKEN_ALANLARI, SISTEM_VARSAYILAN_TEMA, ROL_VARSAYILAN_TEMA, tema_getir,
)

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


@router.get("/{kod}")
async def tema_getir_tekil(kod: str):
    tema = await _tema_dokuman(kod)
    if not tema:
        raise HTTPException(status_code=404, detail="Tema bulunamadı")
    return tema
