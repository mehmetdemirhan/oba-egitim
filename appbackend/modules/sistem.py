"""Sistem modülü — bakım modu yönetimi + public durum ucu.

- GET  /sistem/durum   : PUBLIC (auth yok). Login sayfası bunu okur. Yalnız
                          {bakim, mesaj, tahmini_bitis} döner (sızıntı yok).
- GET  /sistem/bakim   : admin — tam ayar.
- PUT  /sistem/bakim   : admin — aç/kapat + mesaj + tahmini bitiş. islem_log'a düşer.

Merkezi uygulama server.py'deki BakimMiddleware'de; bu modül yalnız ayar + durum.
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException

from core.db import db
from core.auth import require_role, UserRole, get_current_user
from core.audit import islem_kaydet
from core.bakim import bakim_durumu, bakim_ayar_getir, bakim_cache_temizle, VARSAYILAN_MESAJ

router = APIRouter()

_ADMIN = require_role(UserRole.ADMIN)


@router.get("/sistem/durum")
async def sistem_durum():
    """PUBLIC — bakım durumu (login ekranı için). Auth gerektirmez, minimum bilgi."""
    d = await bakim_durumu()
    return {"bakim": d["aktif"], "mesaj": d["mesaj"] if d["aktif"] else None,
            "tahmini_bitis": d["tahmini_bitis"] if d["aktif"] else None}


@router.get("/sistem/bakim")
async def bakim_getir(current_user=Depends(_ADMIN)):
    """Admin — bakım modu tam ayarı (düzenleme ekranı için)."""
    d = await bakim_ayar_getir()
    d["varsayilan_mesaj"] = VARSAYILAN_MESAJ
    return d


@router.put("/sistem/bakim")
async def bakim_ayarla(payload: dict, current_user=Depends(_ADMIN)):
    """Admin — bakım modunu aç/kapat + mesaj + tahmini bitiş. Değişiklik audit'e düşer."""
    onceki = await bakim_ayar_getir()
    aktif = bool((payload or {}).get("aktif"))
    mesaj = str((payload or {}).get("mesaj", "")).strip() or VARSAYILAN_MESAJ
    tahmini_bitis = (payload or {}).get("tahmini_bitis") or None
    await db.sistem_ayarlari.update_one(
        {"tip": "bakim_modu"},
        {"$set": {"degerler": {"aktif": aktif, "mesaj": mesaj, "tahmini_bitis": tahmini_bitis},
                  "guncelleme_tarihi": datetime.utcnow().isoformat(),
                  "guncelleyen": current_user.get("id")}},
        upsert=True,
    )
    bakim_cache_temizle()
    # Aç/kapa işlemi audit'e (kim ne zaman)
    if onceki.get("aktif") != aktif:
        await islem_kaydet(current_user, "sistem", "bakim_ac" if aktif else "bakim_kapat",
                           "sistem", "bakim_modu", "aktif", onceki.get("aktif"), aktif)
    return {"ok": True, "aktif": aktif, "mesaj": mesaj, "tahmini_bitis": tahmini_bitis}
