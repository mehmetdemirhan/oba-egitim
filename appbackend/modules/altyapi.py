"""Altyapı Kullanımı — Vercel / Render hesap & servis bilgisi (best-effort).

KRİTİK İLKE: Yalnızca API'nin GERÇEKTEN döndürdüğü veri gösterilir. Token yoksa
'yapilandirilmadi'; API erişimi/şekli beklenenden farklıysa 'hata' + ne bulunduğu
(HTTP kodu/mesaj) döner — ASLA tahmini/uydurma değer üretilmez.

Ortam değişkenleri:
  VERCEL_TOKEN         — Vercel API token (yoksa kart 'yapılandırılmadı').
  VERCEL_TEAM_ID       — (opsiyonel) takım hesabı için.
  RENDER_API_KEY       — Render API anahtarı (yoksa 'yapılandırılmadı').
"""
import os
import logging

import httpx
from fastapi import APIRouter, Depends

from core.auth import require_role, UserRole

router = APIRouter()
_ADMIN = require_role(UserRole.ADMIN)
_ZAMAN_ASIMI = 12.0


async def _vercel():
    token = os.environ.get("VERCEL_TOKEN", "").strip()
    if not token:
        return {"durum": "yapilandirilmadi", "aciklama": "VERCEL_TOKEN ortam değişkeni tanımlı değil."}
    team = os.environ.get("VERCEL_TEAM_ID", "").strip()
    q = {"teamId": team} if team else {}
    basliklar = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=_ZAMAN_ASIMI) as c:
            ru = await c.get("https://api.vercel.com/v2/user", headers=basliklar, params=q)
            if ru.status_code == 401 or ru.status_code == 403:
                return {"durum": "hata", "aciklama": f"Yetkilendirme reddedildi (HTTP {ru.status_code}). Token geçersiz veya yetkisiz olabilir."}
            if ru.status_code != 200:
                return {"durum": "hata", "aciklama": f"Vercel /v2/user beklenmeyen yanıt: HTTP {ru.status_code}.", "govde": ru.text[:300]}
            user = (ru.json() or {}).get("user", {}) or ru.json() or {}
            rp = await c.get("https://api.vercel.com/v9/projects", headers=basliklar, params={**q, "limit": 100})
            projeler = []
            proje_uyari = None
            if rp.status_code == 200:
                for p in (rp.json() or {}).get("projects", []):
                    son = None
                    lt = p.get("latestDeployments") or []
                    if lt:
                        son = lt[0].get("createdAt")
                    projeler.append({"ad": p.get("name"), "cerceve": p.get("framework"), "son_deploy_ms": son})
            else:
                proje_uyari = f"Proje listesi alınamadı (HTTP {rp.status_code})."
            return {
                "durum": "ok",
                "hesap": user.get("username") or user.get("name") or user.get("email"),
                "plan": user.get("billing", {}).get("plan") if isinstance(user.get("billing"), dict) else None,
                "proje_sayisi": len(projeler),
                "projeler": projeler[:12],
                "kota_notu": "Vercel API'si plan kotası/kalan bant genişliğini genel uçlarda sunmaz; yalnızca hesap ve proje bilgisi gösterilir.",
                "uyari": proje_uyari,
            }
    except httpx.TimeoutException:
        return {"durum": "hata", "aciklama": f"Vercel API zaman aşımı ({int(_ZAMAN_ASIMI)}s)."}
    except Exception as ex:
        logging.warning(f"[altyapi] vercel hata: {ex}")
        return {"durum": "hata", "aciklama": f"Vercel API'ye erişilemedi: {type(ex).__name__}."}


async def _render():
    key = os.environ.get("RENDER_API_KEY", "").strip()
    if not key:
        return {"durum": "yapilandirilmadi", "aciklama": "RENDER_API_KEY ortam değişkeni tanımlı değil."}
    basliklar = {"Authorization": f"Bearer {key}", "Accept": "application/json"}
    try:
        async with httpx.AsyncClient(timeout=_ZAMAN_ASIMI) as c:
            r = await c.get("https://api.render.com/v1/services", headers=basliklar, params={"limit": 50})
            if r.status_code in (401, 403):
                return {"durum": "hata", "aciklama": f"Yetkilendirme reddedildi (HTTP {r.status_code}). API anahtarı geçersiz veya yetkisiz olabilir."}
            if r.status_code != 200:
                return {"durum": "hata", "aciklama": f"Render /v1/services beklenmeyen yanıt: HTTP {r.status_code}.", "govde": r.text[:300]}
            veri = r.json()
            if not isinstance(veri, list):
                return {"durum": "hata", "aciklama": "Render yanıt şekli beklenenden farklı (liste bekleniyordu).", "govde": str(veri)[:300]}
            servisler = []
            for item in veri:
                s = item.get("service", item) if isinstance(item, dict) else {}
                servisler.append({
                    "ad": s.get("name"), "tip": s.get("type"),
                    "durum": s.get("suspended") or "aktif",
                    "bolge": s.get("region"), "son_guncelleme": s.get("updatedAt"),
                })
            return {
                "durum": "ok",
                "servis_sayisi": len(servisler),
                "servisler": servisler[:12],
                "kota_notu": "Render API'si plan kotası/kalan kredi değerlerini servis uçlarında sunmaz; servis listesi ve durumu gösterilir.",
            }
    except httpx.TimeoutException:
        return {"durum": "hata", "aciklama": f"Render API zaman aşımı ({int(_ZAMAN_ASIMI)}s)."}
    except Exception as ex:
        logging.warning(f"[altyapi] render hata: {ex}")
        return {"durum": "hata", "aciklama": f"Render API'ye erişilemedi: {type(ex).__name__}."}


@router.get("/altyapi/kullanim")
async def altyapi_kullanim(current_user=Depends(_ADMIN)):
    """Vercel + Render altyapı bilgisi. Token yoksa 'yapilandirilmadi'; API farklıysa
    'hata' + bulgular. Tahmini/uydurma veri YOK."""
    return {"vercel": await _vercel(), "render": await _render()}
