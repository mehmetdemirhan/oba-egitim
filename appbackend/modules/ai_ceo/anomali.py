"""AI CEO — Kural bazlı anomali uyarıları (AI YOK, deterministik).

Tahsilat düşüşü, giriş azalması, geciken kur birikimi → kırmızı "dikkat" kartı + admin
bildirimi. Eşikler tek yerde; yeni kural eklemek kolay.
"""
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from core.db import db
from core.auth import require_role, UserRole

from .fotograf import son_fotograf
from .ortak import metrik_al

router = APIRouter()
_ADMIN = require_role(UserRole.ADMIN, UserRole.COORDINATOR)

# Eşikler
ESIK_TAHSILAT_DUSUS = 20.0     # % — son ay bir önceki aya göre bu kadar düşerse
ESIK_GIRIS_DUSUS = 30.0        # % — son 7 gün bir önceki 7 güne göre
ESIK_GECIKEN_KUR = 10          # adet — geciken kur bu sayıyı aşarsa


def _yuzde_dusus(onceki, simdi) -> float | None:
    try:
        onceki = float(onceki); simdi = float(simdi)
        if onceki <= 0:
            return None
        return round((onceki - simdi) * 100 / onceki, 1)
    except (TypeError, ValueError):
        return None


def anomalileri_hesapla(fotograf: dict) -> list:
    """Fotoğraftan kural bazlı anomalileri üretir."""
    if not fotograf:
        return []
    uyarilar = []

    # 1) Tahsilat düşüşü (son 3 ay trendinden son iki ay)
    trend = metrik_al(fotograf, "muhasebe.tahsilat_trendi_son3ay", {}) or {}
    aylar = sorted(trend.items())
    if len(aylar) >= 2:
        dusus = _yuzde_dusus(aylar[-2][1], aylar[-1][1])
        if dusus is not None and dusus >= ESIK_TAHSILAT_DUSUS:
            uyarilar.append({
                "tip": "tahsilat_dususu", "seviye": "kritik",
                "mesaj": f"Tahsilat son ay %{dusus} düştü ({aylar[-2][0]}→{aylar[-1][0]}).",
                "deger": dusus,
            })

    # 2) Geciken kur birikimi
    geciken = metrik_al(fotograf, "ogretmen.geciken_kur_sayisi", 0) or 0
    if geciken >= ESIK_GECIKEN_KUR:
        uyarilar.append({
            "tip": "geciken_kur_birikimi", "seviye": "orta",
            "mesaj": f"{geciken} kur 35 günlük hedefi aştı — tahsilat/tamamlama riski.",
            "deger": geciken,
        })

    # 3) Giriş azalması (envanter: aktivite/log koleksiyonlarının son 7 gün toplamı)
    env = metrik_al(fotograf, "envanter.koleksiyonlar", {}) or {}
    son7 = sum((o.get("son_7gun") or 0) for o in env.values() if isinstance(o, dict))
    son30 = sum((o.get("son_30gun") or 0) for o in env.values() if isinstance(o, dict))
    if son30 > 0:
        beklenen_haftalik = son30 / 4.0
        dusus = _yuzde_dusus(beklenen_haftalik, son7)
        if dusus is not None and dusus >= ESIK_GIRIS_DUSUS:
            uyarilar.append({
                "tip": "giris_azalmasi", "seviye": "orta",
                "mesaj": f"Son 7 gün sistem hareketi beklenene göre %{dusus} düşük.",
                "deger": dusus,
            })
    return uyarilar


async def anomali_bildirim_gonder(uyarilar: list):
    """Kritik anomaliler için admin'e bildirim (cooldown bildirim.py'de)."""
    if not uyarilar:
        return
    try:
        from modules.bildirim import bildirim_olustur
        adminler = await db.users.find({"role": {"$in": ["admin", "coordinator"]}}, {"_id": 0, "id": 1}).to_list(length=50)
        for u in uyarilar:
            if u.get("seviye") != "kritik":
                continue
            for a in adminler:
                await bildirim_olustur(a["id"], "ai_ceo_anomali", f"⚠️ {u['mesaj']}", None)
    except Exception as e:
        logging.warning(f"[ai_ceo] anomali bildirim hatası: {e}")


@router.get("/ai/ceo/anomali")
async def anomali_listesi(current_user=Depends(_ADMIN)):
    foto = await son_fotograf()
    uyarilar = anomalileri_hesapla(foto) if foto else []
    return {"anomaliler": uyarilar, "fotograf_tarih": foto.get("tarih") if foto else None}
