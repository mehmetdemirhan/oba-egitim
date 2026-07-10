"""E-posta gönderimi (SMTP) — yalnızca stdlib (smtplib + email).

SMTP ayarları core.config'ten env üzerinden okunur. SMTP tanımlı değilse
(SMTP_ENABLED False) gönderim yapılmaz ve False döner; çağıran akış buna göre
davranır (ör. şifre sıfırlama e-postası kapalıysa kullanıcıya admin'e başvur
mesajı gösterilir).
"""
import logging
import smtplib
import ssl
from email.message import EmailMessage

from core.config import (
    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM, SMTP_TLS, SMTP_ENABLED,
)


def send_email(to: str, subject: str, html: str, text: str = "") -> bool:
    """Tek bir HTML e-posta gönderir. Başarılıysa True, aksi halde False.

    SMTP kapalıysa veya hata olursa False döner (istisna fırlatmaz; çağıran akış
    güvenlik gereği yanıtını buna göre nötr tutar).
    """
    if not SMTP_ENABLED:
        return False
    if not to:
        return False
    try:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = SMTP_FROM
        msg["To"] = to
        msg.set_content(text or "Bu e-postayı görüntülemek için HTML destekli bir istemci kullanın.")
        msg.add_alternative(html, subtype="html")

        if SMTP_TLS:
            ctx = ssl.create_default_context()
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as s:
                s.starttls(context=ctx)
                s.login(SMTP_USER, SMTP_PASSWORD)
                s.send_message(msg)
        else:
            # Örn. 465 (SSL) veya TLS'siz sunucu
            if SMTP_PORT == 465:
                ctx = ssl.create_default_context()
                with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=20, context=ctx) as s:
                    s.login(SMTP_USER, SMTP_PASSWORD)
                    s.send_message(msg)
            else:
                with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as s:
                    s.login(SMTP_USER, SMTP_PASSWORD)
                    s.send_message(msg)
        return True
    except Exception as ex:  # ağ/kimlik hatası — sızdırma, sessiz logla
        logging.error(f"[MAIL] Gönderim başarısız ({to}): {ex}")
        return False
