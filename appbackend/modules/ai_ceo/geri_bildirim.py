"""AI CEO — geri bildirim toplama (FAZ 4, madde 12).

Her öneri/karar/denetim/sohbet cevabının altına 👍/👎 + opsiyonel "neden yanlıştı/eksikti" metni.
Koleksiyon: ai_geri_bildirim
  {id, ajan, kaynak_id, kaynak_tur, kullanici_id, puan(olumlu|olumsuz), duzeltme_metni, kategori, tarih}

Tarih DAİMA core.zaman.simdi()/iso() üzerinden (aware UTC). Bu ham veri, öğrenme enjeksiyonu
(ogrenme.py) ve öğrenme metrikleri için tek kaynaktır.

Uçlar: POST /ai/ceo/geri-bildirim, GET /ai/ceo/geri-bildirim.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException

from core.db import db
from core.auth import require_role, UserRole, get_current_user
from core.zaman import iso

router = APIRouter()
_KOORD = require_role(UserRole.ADMIN, UserRole.COORDINATOR)

_PUANLAR = ("olumlu", "olumsuz")
# Serbest ama tutarlı kategori önerisi (kayıt yine de serbest metin kabul eder)
GECERLI_AJANLAR = ("ayda", "deniz", "miran", "atlas", "lina", "nova", "ayaz", "karar")


@router.post("/ai/ceo/geri-bildirim")
async def geri_bildirim_gonder(govde: dict, current_user=Depends(get_current_user)):
    """AI çıktısına 👍/👎 + opsiyonel düzeltme. Çıktıyı gören her yetkili kullanıcı verebilir."""
    puan = str(govde.get("puan", "")).strip().lower()
    if puan not in _PUANLAR:
        raise HTTPException(status_code=400, detail=f"puan {_PUANLAR} olmalı")
    ajan = str(govde.get("ajan", "")).strip().lower() or "genel"
    kayit = {
        "id": str(uuid.uuid4()),
        "ajan": ajan,
        "kaynak_id": str(govde.get("kaynak_id", ""))[:80] or None,
        "kaynak_tur": str(govde.get("kaynak_tur", ""))[:40] or None,  # oneri|karar|denetim|sohbet
        "kullanici_id": current_user.get("id"),
        "puan": puan,
        "duzeltme_metni": str(govde.get("duzeltme_metni", "")).strip()[:2000],
        "kategori": str(govde.get("kategori", "")).strip()[:60] or ajan,
        "tarih": iso(),
    }
    await db.ai_geri_bildirim.insert_one({**kayit})
    kayit.pop("_id", None)
    return {"ok": True, "kayit": kayit}


@router.get("/ai/ceo/geri-bildirim")
async def geri_bildirim_listele(ajan: str = "", kaynak_id: str = "", current_user=Depends(_KOORD)):
    """Geri bildirim kayıtları (filtre: ajan / kaynak_id)."""
    q = {}
    if ajan:
        q["ajan"] = ajan.strip().lower()
    if kaynak_id:
        q["kaynak_id"] = kaynak_id.strip()
    kayitlar = await db.ai_geri_bildirim.find(q, {"_id": 0}).sort("tarih", -1).to_list(length=500)
    return {"kayitlar": kayitlar, "sayi": len(kayitlar)}
