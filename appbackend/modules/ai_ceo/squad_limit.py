"""AI Squad tetikleme limiti + tahmini maliyet (FAZ 2, madde 8).

Her pipeline tetiklemesi GERÇEK Atlas+Lina+Nova LLM çağrısı yapar → kotasız risk. Bu modül:
  - günlük/aylık tetik sayısını (ai_squad_pipeline_runs.olusturma_tarihi) sayar
  - yapılandırılabilir limit + tahmini maliyet döner (limit aşılırsa uyarı / opsiyonel sert blok)

Limitler RUNTIME ayarlanabilir: db.sistem_ayarlari (tip='squad_ayarlari', degerler={gunluk_limit,
aylik_limit, tetik_ucret, sert_blok}). Admin mevcut PUT /api/ayarlar/squad_ayarlari ile değiştirir.
Maliyet TAHMİNİDİR (birim ücret × tetik); tetik_ucret 0 ise dürüstçe "tanımsız" gösterilir.

Uç: /ai/squad/orkestrator/limit-durum. Ayrıca squad_orkestrator tetikte limit_kontrol() çağırır.
"""
from fastapi import APIRouter, Depends, HTTPException

from core.db import db
from core.auth import require_role, UserRole
from core.zaman import iso

router = APIRouter()
_KOORD = require_role(UserRole.ADMIN, UserRole.COORDINATOR)

# Güvenli varsayılanlar (sistem_ayarlari ile ezilir)
_VARSAYILAN = {"gunluk_limit": 50, "aylik_limit": 500, "tetik_ucret": 0.0, "sert_blok": False}


async def _ayarlar() -> dict:
    doc = await db.sistem_ayarlari.find_one({"tip": "squad_ayarlari"})
    d = dict(_VARSAYILAN)
    if doc and isinstance(doc.get("degerler"), dict):
        for k in _VARSAYILAN:
            if doc["degerler"].get(k) is not None:
                d[k] = doc["degerler"][k]
    return d


async def limit_durumu() -> dict:
    """Günlük/aylık kullanım + limit + tahmini maliyet. Tetik sayımı olusturma_tarihi öneki ile."""
    ayar = await _ayarlar()
    bugun = iso()[:10]      # YYYY-MM-DD
    bu_ay = iso()[:7]       # YYYY-MM
    gunluk = await db.ai_squad_pipeline_runs.count_documents({"olusturma_tarihi": {"$regex": f"^{bugun}"}})
    aylik = await db.ai_squad_pipeline_runs.count_documents({"olusturma_tarihi": {"$regex": f"^{bu_ay}"}})

    ucret = float(ayar["tetik_ucret"] or 0)
    tahmini_maliyet = round(aylik * ucret, 2) if ucret > 0 else None
    gunluk_asildi = gunluk >= int(ayar["gunluk_limit"])
    aylik_asildi = aylik >= int(ayar["aylik_limit"])
    return {
        "gunluk_kullanim": gunluk, "gunluk_limit": int(ayar["gunluk_limit"]),
        "aylik_kullanim": aylik, "aylik_limit": int(ayar["aylik_limit"]),
        "tetik_ucret": ucret, "tahmini_aylik_maliyet": tahmini_maliyet,
        "sert_blok": bool(ayar["sert_blok"]),
        "asildi": gunluk_asildi or aylik_asildi,
        "gunluk_asildi": gunluk_asildi, "aylik_asildi": aylik_asildi,
    }


async def limit_kontrol_veya_hata():
    """Tetik öncesi çağrılır. Sert blok + limit aşımı → 429. Değilse uyarı bilgisini döner."""
    durum = await limit_durumu()
    if durum["asildi"] and durum["sert_blok"]:
        hangi = "günlük" if durum["gunluk_asildi"] else "aylık"
        raise HTTPException(status_code=429,
                            detail=f"Squad {hangi} tetik limiti aşıldı ({durum['gunluk_kullanim']}/{durum['gunluk_limit']} günlük, "
                                   f"{durum['aylik_kullanim']}/{durum['aylik_limit']} aylık). Sert blok açık.")
    return durum


@router.get("/ai/squad/orkestrator/limit-durum")
async def squad_limit_durum(current_user=Depends(_KOORD)):
    return await limit_durumu()
