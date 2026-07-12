"""Merkezi yapılandırma — tüm ortam değişkenleri ve sabitler.

server.py ve modüller bu dosyadan import eder. Davranış server.py'daki
orijinal tanımlarla BİREBİR aynıdır (sadece konum değişti).
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# .env appbackend/ kökünde; bu dosya core/ altında olduğu için iki üst dizin.
ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / '.env')

# ── MongoDB ──
MONGO_URL = os.environ['MONGO_URL']
DB_NAME = os.environ['DB_NAME']

# ── E-posta (SMTP) — şifre sıfırlama akışı ──
# SMTP tanımlı DEĞİLSE e-posta ile şifre sıfırlama KAPALIDIR (admin kurtarma yolu kalır).
# Geçici şifre/reset bilgisi ASLA HTTP yanıtında dönmez (güvenlik).
SMTP_HOST = os.environ.get("SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
SMTP_FROM = os.environ.get("SMTP_FROM", "") or SMTP_USER or "noreply@oba.com"
SMTP_TLS = os.environ.get("SMTP_TLS", "true").lower() in ("1", "true", "yes", "on")
SMTP_ENABLED = bool(SMTP_HOST and SMTP_USER and SMTP_PASSWORD)
# Reset linkinin işaret edeceği frontend kökü (e-postadaki bağlantı)
FRONTEND_URL = os.environ.get("FRONTEND_URL", "https://oba-egitim.vercel.app").rstrip("/")
# Reset token geçerlilik süresi (dakika)
SIFRE_RESET_TOKEN_DK = int(os.environ.get("SIFRE_RESET_TOKEN_DK", "30"))

# ── Web Push (VAPID) — ders hatırlatma bildirimleri ──
VAPID_PUBLIC_KEY = os.environ.get("VAPID_PUBLIC_KEY", "")
# PEM tek satırda saklanır (\n kaçışlı) → gerçek satır başlarına çevrilir
VAPID_PRIVATE_KEY = os.environ.get("VAPID_PRIVATE_KEY", "").replace("\\n", "\n")
VAPID_SUBJECT = os.environ.get("VAPID_SUBJECT", "mailto:admin@oba.com")
# Ders saatleri yerel (TR) saklanır; "15 dk önce" hesabı için UTC ofseti
PUSH_TZ_OFFSET_SAAT = int(os.environ.get("PUSH_TZ_OFFSET_SAAT", "3"))
# Ders öncesi kaç dakika bildirilsin
PUSH_HATIRLATMA_DK = int(os.environ.get("PUSH_HATIRLATMA_DK", "15"))
# /push/kontrol için gizli anahtar (cron çağrısında ?anahtar=). Boşsa açık (dev).
PUSH_CRON_TOKEN = os.environ.get("PUSH_CRON_TOKEN", "")

# ── Backup (GridFS) & update-check config ──
APP_VERSION = os.environ.get("APP_VERSION", "1.0.0")
GITHUB_REPO_OWNER = os.environ.get("GITHUB_REPO_OWNER", "")
GITHUB_REPO_NAME = os.environ.get("GITHUB_REPO_NAME", "")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
UPDATE_CHECK_MIN_INTERVAL_SECONDS = 300
MAX_MANUAL_BACKUPS_TO_RETAIN = 10
MAX_AUTO_PRE_RESTORE_BACKUPS_TO_RETAIN = 3
BACKUP_COLLECTION_DENYLIST = {
    "backup_history",
    "backups.files",
    "backups.chunks",
    "fs.files",
    "fs.chunks",
}

# ── JWT Config ──
SECRET_KEY = os.environ.get('SECRET_KEY', 'okuma-becerileri-secret-key-change-in-production')
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get('ACCESS_TOKEN_EXPIRE_MINUTES', '60'))
# Kalıcı oturum: refresh token 45 gün (access kısa ömürlü, arka planda yenilenir)
REFRESH_TOKEN_EXPIRE_DAYS = int(os.environ.get('REFRESH_TOKEN_EXPIRE_DAYS', '45'))

# ── AI / Gemini ──
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")  # geriye dönük uyumluluk
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", os.environ.get("ANTHROPIC_API_KEY", ""))
GEMINI_API_KEY_2 = os.environ.get("GEMINI_API_KEY_2", "")  # Yedek key
GEMINI_API_KEY_3 = os.environ.get("GEMINI_API_KEY_3", "")  # 3. key
YANDEX_DISK_TOKEN = os.environ.get("YANDEX_DISK_TOKEN", "")  # Yandex Disk OAuth token

# Model rotasyon listesi — kota dolunca bir sonrakini dene
GEMINI_MODELS = [
    "gemini-2.0-flash",           # ana model
    "gemini-2.0-flash-lite",      # hafif, az kota
    "gemini-flash-latest",        # alias - farklı kota havuzu
    "gemini-flash-lite-latest",   # en hafif
    "gemini-2.5-flash",           # en güçlü flash
]
AI_MODEL = os.environ.get("AI_DEFAULT_MODEL", GEMINI_MODELS[0])
AI_DEFAULT_MODEL = AI_MODEL
AI_HAIKU_MODEL = AI_MODEL
AI_CACHE_HOURS = int(os.environ.get("AI_CACHE_HOURS", "24"))
AI_MAX_DAILY_REQUESTS = int(os.environ.get("AI_MAX_DAILY_REQUESTS", "500"))

# ── Veli Mesaj Funnel'ı: kanallar ──
# Kanal kimlik bilgisi TANIMLI değilse UI'da "kurulmadı" görünür; gönderim yapılmaz.
# FAZ 1 — SMS (Netgsm; TR'de yaygın REST API). Değerler yoksa kanal pasif.
NETGSM_USERNAME = os.environ.get("NETGSM_USERNAME", "")
NETGSM_PASSWORD = os.environ.get("NETGSM_PASSWORD", "")
NETGSM_HEADER = os.environ.get("NETGSM_HEADER", "")          # onaylı gönderici başlığı
NETGSM_BASE_URL = os.environ.get("NETGSM_BASE_URL", "https://api.netgsm.com.tr").rstrip("/")
SMS_BIRIM_UCRET = float(os.environ.get("SMS_BIRIM_UCRET", "0.15"))  # maliyet tahmini (TL/parça)
# İYS (opsiyonel — hesaba özel). Pazarlama mesajlarında Netgsm İYS filtresi (2. katman).
NETGSM_IYS_FILTER = os.environ.get("NETGSM_IYS_FILTER", "")
NETGSM_PARTNER_CODE = os.environ.get("NETGSM_PARTNER_CODE", "")
NETGSM_ENABLED = bool(NETGSM_USERNAME and NETGSM_PASSWORD and NETGSM_HEADER)

# FAZ 2 — WhatsApp Cloud API (şablon gönderimi + durum webhook'u).
# Kimlik bilgileri (WHATSAPP_TOKEN + WHATSAPP_PHONE_ID) env'de DOLU olunca kanal
# otomatik AÇILIR (WHATSAPP_ENABLED); boşken UI'da "kurulmadı" görünür.
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN", "")
WHATSAPP_PHONE_ID = os.environ.get("WHATSAPP_PHONE_ID", "")
WHATSAPP_BASE_URL = os.environ.get("WHATSAPP_BASE_URL", "https://graph.facebook.com/v20.0").rstrip("/")
WHATSAPP_BIRIM_UCRET = float(os.environ.get("WHATSAPP_BIRIM_UCRET", "0.35"))
# Şablon varsayılanları: şablon kaydı wa_sablon_adi/wa_dil vermezse bunlar kullanılır.
WHATSAPP_DEFAULT_TEMPLATE = os.environ.get("WHATSAPP_DEFAULT_TEMPLATE", "bilgilendirme")
WHATSAPP_DEFAULT_LANG = os.environ.get("WHATSAPP_DEFAULT_LANG", "tr")
# Webhook doğrulama token'ı (Meta panelinde girilen "Verify Token" ile aynı olmalı).
WHATSAPP_WEBHOOK_VERIFY_TOKEN = os.environ.get("WHATSAPP_WEBHOOK_VERIFY_TOKEN", "")
WHATSAPP_ENABLED = bool(WHATSAPP_TOKEN and WHATSAPP_PHONE_ID)
