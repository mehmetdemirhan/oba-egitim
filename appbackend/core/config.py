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

# ── Güvenlik / geliştirme bayrakları ──
# Şifre sıfırlamada geçici şifreyi HTTP yanıtında GÖSTER (yalnızca lokal geliştirme).
# Prod'da e-posta/SMS gönderimi olmadığından varsayılan KAPALI: şifre yanıtta dönmez.
SIFRE_SIFIRLAMA_DEBUG = os.environ.get("SIFRE_SIFIRLAMA_DEBUG", "").lower() in ("1", "true", "yes", "on")

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
