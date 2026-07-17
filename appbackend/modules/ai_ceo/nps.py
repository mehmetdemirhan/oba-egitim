"""AI CEO — Müşterinin Sesi (S6d): mikro-NPS + çıkış nedeni.

Kur bitince veliye mikro-NPS (0-10 + serbest metin). NPS sağlık skoru bileşenidir; düşüş
anomali üretir; serbest metinler anonim tema özetine girer. İptal/yarıda bırakmada çıkış
nedeni. KVKK: öğrenci takma-ID; serbest metin anonim; kişisel iletişim verisi TUTULMAZ.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException

from core.db import db
from core.auth import require_role, UserRole, get_current_user
from core.zaman import iso

from .fotograf import takma_id

router = APIRouter()
_ADMIN = require_role(UserRole.ADMIN, UserRole.COORDINATOR)

CIKIS_NEDENLERI = ["fiyat", "memnuniyetsizlik", "tasinma", "tamamladi", "diger"]


def _nps_hesapla(puanlar: list) -> dict:
    n = len(puanlar)
    if n == 0:
        return {"nps": None, "sayi": 0, "promoter": 0, "pasif": 0, "detractor": 0}
    promoter = sum(1 for p in puanlar if p >= 9)
    detractor = sum(1 for p in puanlar if p <= 6)
    pasif = n - promoter - detractor
    return {"nps": round((promoter - detractor) * 100 / n, 1), "sayi": n,
            "promoter": promoter, "pasif": pasif, "detractor": detractor}


async def nps_ozet() -> dict:
    kayitlar = await db.ai_ceo_nps.find({}, {"_id": 0, "puan": 1}).to_list(length=50000)
    puanlar = [int(k["puan"]) for k in kayitlar if isinstance(k.get("puan"), (int, float))]
    return _nps_hesapla(puanlar)


@router.post("/ai/ceo/nps")
async def nps_gonder(govde: dict, current_user=Depends(get_current_user)):
    """Veli/öğrenci mikro-NPS gönderir. Öğrenci takma-ID ile saklanır (KVKK)."""
    try:
        puan = int(govde.get("puan"))
        assert 0 <= puan <= 10
    except (TypeError, ValueError, AssertionError):
        raise HTTPException(status_code=400, detail="puan 0-10 olmalı")
    oid = govde.get("ogrenci_id") or current_user.get("linked_id") or current_user.get("id")
    await db.ai_ceo_nps.insert_one({
        "id": str(uuid.uuid4()), "ogrenci_takma": takma_id(oid), "kur": str(govde.get("kur", ""))[:20],
        "puan": puan, "yorum": str(govde.get("yorum", ""))[:1000],  # anonim tema özetinde kullanılır
        "tarih": iso()})
    return {"ok": True}


@router.get("/ai/ceo/nps/ozet")
async def nps_ozet_endpoint(current_user=Depends(_ADMIN)):
    ozet = await nps_ozet()
    # Anonim yorum örneklemi (isim/iletişim yok — yalnız metin)
    yorumlar = await db.ai_ceo_nps.find({"yorum": {"$nin": [None, ""]}}, {"_id": 0, "puan": 1, "yorum": 1}).sort("tarih", -1).to_list(length=50)
    # Çıkış nedeni dağılımı
    cikislar = await db.ai_ceo_cikis_nedeni.find({}, {"_id": 0, "neden": 1}).to_list(length=20000)
    dagilim = {}
    for c in cikislar:
        dagilim[c.get("neden", "diger")] = dagilim.get(c.get("neden", "diger"), 0) + 1
    return {"nps": ozet, "yorumlar": yorumlar, "cikis_dagilimi": dagilim}


@router.post("/ai/ceo/cikis-nedeni")
async def cikis_nedeni(govde: dict, current_user=Depends(_ADMIN)):
    neden = govde.get("neden")
    if neden not in CIKIS_NEDENLERI:
        raise HTTPException(status_code=400, detail=f"Geçersiz neden. Seçenekler: {CIKIS_NEDENLERI}")
    oid = govde.get("ogrenci_id") or ""
    await db.ai_ceo_cikis_nedeni.insert_one({
        "id": str(uuid.uuid4()), "ogrenci_takma": takma_id(oid) if oid else "", "neden": neden,
        "not": str(govde.get("not", ""))[:500], "tarih": iso()})
    return {"ok": True}
