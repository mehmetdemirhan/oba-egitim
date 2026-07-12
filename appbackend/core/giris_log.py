"""Giriş/çıkış (oturum) audit kaydı — db.giris_log.

Login (başarılı/başarısız), logout ve token yenileme olaylarını ayrı bir
koleksiyona yazar. Kim, hangi rol, ne zaman, hangi IP ve hangi cihaz/tarayıcı
(kısaltılmış user-agent). Başarısız girişte denenen e-posta + IP tutulur.

GÜVENLİK: Şifre veya token içeriği ASLA yazılmaz. `islem_log` (core.audit)
finansal/kayıt değişiklikleri içindir; bu koleksiyon yalnız oturum olaylarıdır.

`olusturma` alanı BİLİNÇLİ olarak native `datetime` (BSON Date) tutulur; TTL
index'i (core.db.ensure_indexes) bu alan üzerinden çalışır — ISO string TTL'de
çalışmaz. `core.audit` deseninin oturum-olayları karşılığıdır; asla exception
fırlatmaz (log yazımı esas isteği bozmamalı).
"""
import uuid
import logging
from datetime import datetime

from core.db import db

# Geçerli olay türleri
TIPLER = {"login_basarili", "login_basarisiz", "logout", "token_yenile"}

_UA_MAX = 180  # kısaltılmış user-agent üst sınırı


def client_ip(request) -> str:
    """İstemci IP'si (Render/proxy arkasında x-forwarded-for önceliklidir)."""
    try:
        xff = request.headers.get("x-forwarded-for", "") if request else ""
        if xff:
            return xff.split(",")[0].strip()
        return request.client.host if (request and request.client) else "bilinmiyor"
    except Exception:
        return "bilinmiyor"


def _kisa_ua(request) -> str:
    try:
        ua = (request.headers.get("user-agent", "") if request else "") or ""
        return ua[:_UA_MAX]
    except Exception:
        return ""


async def giris_kaydet(tip: str, user: dict | None = None, request=None,
                       denenen_email: str | None = None) -> None:
    """Bir oturum olayını db.giris_log'a yazar. Asla exception fırlatmaz.

    tip           : "login_basarili" | "login_basarisiz" | "logout" | "token_yenile"
    user          : başarılı olaylarda kullanıcı dokümanı (None olabilir)
    request       : IP + user-agent için FastAPI Request (opsiyonel)
    denenen_email : yalnız başarısız girişte denenen e-posta/telefon
    """
    try:
        ad = f"{(user or {}).get('ad', '')} {(user or {}).get('soyad', '')}".strip()
        doc = {
            "id": str(uuid.uuid4()),
            "tip": tip if tip in TIPLER else "bilinmiyor",
            "user_id": (user or {}).get("id"),
            "kullanici_ad": ad or None,
            "rol": (user or {}).get("role"),
            "ip": client_ip(request),
            "ua": _kisa_ua(request),
            # native datetime — TTL index bu alanda çalışır (ISO string DEĞİL)
            "olusturma": datetime.utcnow(),
        }
        if denenen_email:
            doc["denenen_email"] = denenen_email
        await db.giris_log.insert_one(doc)
    except Exception as ex:
        logging.warning(f"[giris_log] yazılamadı: {ex}")
