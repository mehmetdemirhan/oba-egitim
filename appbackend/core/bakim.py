"""Bakım modu durumu — db.sistem_ayarlari (tip=bakim_modu), kısa cache'li.

Env değil DB tabanlı: deploy'suz aç/kapa. Durum kısa süreli (30 sn) cache'lenir;
her istekte DB'ye gidilmez (middleware her istekte çağırır). Aç/kapa ve mesaj
`modules/sistem.py`'den yönetilir; oradan `bakim_cache_temizle()` çağrılır.
"""
import time
import logging

from core.db import db

_KEY = {"tip": "bakim_modu"}
_TTL = 30.0  # saniye
_cache = {"deger": None, "ts": 0.0}

VARSAYILAN_MESAJ = (
    "Sistemimiz kısa bir bakımdan geçiyor. En kısa sürede tekrar hizmetinizdeyiz. "
    "Anlayışınız için teşekkür ederiz."
)


async def bakim_ayar_getir() -> dict:
    """Ham ayarı DB'den okur (cache'siz)."""
    doc = await db.sistem_ayarlari.find_one(_KEY)
    d = (doc or {}).get("degerler") or {}
    return {
        "aktif": bool(d.get("aktif", False)),
        "mesaj": (d.get("mesaj") or "").strip() or VARSAYILAN_MESAJ,
        "tahmini_bitis": d.get("tahmini_bitis"),
    }


async def bakim_durumu(force: bool = False) -> dict:
    """Cache'li bakım durumu. TTL içinde DB'ye gitmez."""
    now = time.time()
    if not force and _cache["deger"] is not None and (now - _cache["ts"]) < _TTL:
        return _cache["deger"]
    try:
        d = await bakim_ayar_getir()
    except Exception as ex:
        logging.warning(f"[bakim] durum okunamadı: {ex}")
        d = _cache["deger"] or {"aktif": False, "mesaj": VARSAYILAN_MESAJ, "tahmini_bitis": None}
    _cache["deger"] = d
    _cache["ts"] = now
    return d


def bakim_cache_temizle() -> None:
    """Ayar değişince çağrılır — sonraki istek DB'den taze okur."""
    _cache["deger"] = None
    _cache["ts"] = 0.0
