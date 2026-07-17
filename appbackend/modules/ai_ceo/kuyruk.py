"""AI CEO — Karar Kuyruğu ("Karar Bekleyenler").

Tüm AÇIK öneriler tek listede: öncelik sıralı, kategori filtreli, hızlı aksiyonlu.
Karar verilince kuyruktan DÜŞER (silinmez — durum takibi + karne sürer). Ertelenen öğe
belirlenen tarihte geri gelir. 7 günden eski karara bağlanmamış öğeler "gözden kaçıyor
olabilir" olarak işaretlenir.
"""
from fastapi import APIRouter, Depends

from core.db import db
from core.auth import require_role, UserRole
from core.zaman import simdi, aware as _aware

router = APIRouter()
_ADMIN = require_role(UserRole.ADMIN, UserRole.COORDINATOR)

_ONCELIK_SIRA = {"yuksek": 0, "orta": 1, "dusuk": 2}
GOZDEN_KACMA_GUN = 7


def _acik_mi(o: dict, simdiki) -> bool:
    d = o.get("durum")
    if d == "yeni":
        return True
    if d == "ertelendi":
        et = _aware(o.get("ertele_tarih"))
        return bool(et and et <= simdiki)  # süresi gelen ertelemeler geri kuyruğa
    return False


@router.get("/ai/ceo/kuyruk")
async def kuyruk(kategori: str = "", current_user=Depends(_ADMIN)):
    simdiki = simdi()
    q = {"durum": {"$in": ["yeni", "ertelendi"]}}
    if kategori:
        q["kategori"] = kategori
    oneriler = await db.ai_ceo_oneriler.find(q, {"_id": 0}).to_list(length=1000)
    acik = [o for o in oneriler if _acik_mi(o, simdiki)]
    # 7 günden eski + karara bağlanmamış → gözden kaçıyor olabilir
    for o in acik:
        d = _aware(o.get("tarih"))
        o["gozden_kaciyor"] = bool(d and (simdiki - d).days >= GOZDEN_KACMA_GUN)
    acik.sort(key=lambda o: (_ONCELIK_SIRA.get(o.get("oncelik"), 3), o.get("tarih", "")))
    return {
        "kuyruk": acik,
        "bekleyen_sayi": len(acik),
        "gozden_kacan_sayi": sum(1 for o in acik if o.get("gozden_kaciyor")),
    }


@router.get("/ai/ceo/kuyruk/bekleyen-sayi")
async def bekleyen_sayi(current_user=Depends(_ADMIN)):
    """Admin bildirim zili rozeti için hafif sayaç."""
    simdiki = simdi()
    oneriler = await db.ai_ceo_oneriler.find(
        {"durum": {"$in": ["yeni", "ertelendi"]}}, {"_id": 0, "durum": 1, "ertele_tarih": 1}).to_list(length=2000)
    n = sum(1 for o in oneriler if _acik_mi(o, simdiki))
    return {"bekleyen": n}
