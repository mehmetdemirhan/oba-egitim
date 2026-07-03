from fastapi import FastAPI, APIRouter, HTTPException, Depends, status, Body, UploadFile, File, Form
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorGridFSBucket
from bson import json_util, ObjectId
import os
import io
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional
import uuid
import random
import re
from datetime import datetime, timezone, timedelta
from enum import Enum
from passlib.context import CryptContext
from jose import JWTError, jwt
import httpx

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# ÇEKİRDEK KATMAN (core/) — yapılandırma, DB bağlantısı, kimlik doğrulama
# Aşağıdaki semboller core/ altına taşındı; davranış birebir aynıdır.
from core.config import (
    APP_VERSION, GITHUB_REPO_OWNER, GITHUB_REPO_NAME, GITHUB_TOKEN,
    UPDATE_CHECK_MIN_INTERVAL_SECONDS, MAX_MANUAL_BACKUPS_TO_RETAIN,
    MAX_AUTO_PRE_RESTORE_BACKUPS_TO_RETAIN, BACKUP_COLLECTION_DENYLIST,
    SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES,
    ANTHROPIC_API_KEY, GEMINI_API_KEY, GEMINI_API_KEY_2, GEMINI_API_KEY_3,
    YANDEX_DISK_TOKEN, GEMINI_MODELS, AI_MODEL, AI_DEFAULT_MODEL,
    AI_HAIKU_MODEL, AI_CACHE_HOURS, AI_MAX_DAILY_REQUESTS,
)
from core.db import client, db, backup_fs, prepare_for_mongo, parse_from_mongo
from core.auth import (
    TeacherLevel, UserRole, pwd_context, security,
    hash_password, verify_password, create_access_token, decode_token,
    get_current_user, require_role,
)

from core.ai import _gemini_call, call_claude, _mock_bilgi_tabani_response, get_ogrenci_ai_verileri

# Create the main app without a prefix
app = FastAPI(title="Okuma Becerileri Akademisi API")

# ★ CORS — En güvenilir yapılandırma
# NOT: allow_origins=["*"] ve allow_credentials=True birlikte kullanılamaz.
# Bu yüzden ya credentials kapatılır ya da origin spesifik yazılır.
# Render'da en güvenilir yol: origin'i dinamik olarak echo etmek.

ALLOWED_ORIGINS = {
    "https://oba-egitim-frontend.onrender.com",
    "https://oba-egitim.vercel.app",
    "https://oba-egitim-git-main-mehmetdemirhans-projects.vercel.app",
    "http://localhost:3000",
    "http://localhost:3001",
}

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

class CustomCORSMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        origin = request.headers.get("origin", "")
        is_allowed = origin in ALLOWED_ORIGINS or origin.endswith(".onrender.com") or origin.endswith(".vercel.app")

        # OPTIONS preflight — hemen yanıtla
        if request.method == "OPTIONS":
            response = Response(status_code=200)
            if is_allowed:
                response.headers["Access-Control-Allow-Origin"] = origin
                response.headers["Access-Control-Allow-Credentials"] = "true"
                response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS, PATCH"
                response.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type, Accept, Origin, X-Requested-With"
                response.headers["Access-Control-Max-Age"] = "86400"
            return response

        # Normal istek — try/except ile 500 hatalarında da CORS header ekle
        try:
            response = await call_next(request)
        except Exception as e:
            logging.error(f"Unhandled error: {e}")
            response = Response(content=str(e), status_code=500)
        if is_allowed:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS, PATCH"
            response.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type, Accept, Origin, X-Requested-With"
        return response

app.add_middleware(CustomCORSMiddleware)

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# ENUMS / HELPERS / AUTH
# (TeacherLevel, UserRole, prepare_for_mongo, parse_from_mongo,
#  hash_password, verify_password, create_access_token, decode_token,
# yukarıda import ediliyorlar. Davranış birebir aynıdır.

# UserCreate/UserLogin/UserResponse/TokenResponse/ChangePassword ve 7 endpoint
# aynı yollarla kayıtlı kalır.

# STARTUP: Admin kullanıcı oluştur

from modules.seed import create_default_admin
app.add_event_handler("startup", create_default_admin)

# Kritik DB index'lerini oluştur (kazanilan_rozetler unique vb.) — FAZ 1
from core.db import ensure_indexes
app.add_event_handler("startup", ensure_indexes)

# MEVCUT MODELLER (değişmeden korunuyor)

# CRM modelleri (Teacher/Student/Course/Ders/Payment + Create/Update + ExportData)

# MEVCUT ROUTE'LAR (değişmeden korunuyor)

# Dashboard & istatistik endpoint'leri (/dashboard, /dashboard/bekleyenler,

# CRM endpoint'leri (/teachers, /students, /courses, /dersler, /payments, /export)

# YEDEKLEME (BACKUP) + GÜNCELLEME (UPDATE CHECK) — ADMIN
#   /admin/backups/{id}/download, /admin/backups/{id}/restore, DELETE,
#   /admin/version, /admin/updates/check) aynı yollarla kayıtlı kalır.

# GİRİŞ ANALİZİ (FAZ 1A)


# ── Puan Ayarları ──
from core.sistem import VARSAYILAN_PUANLAR, get_puan_ayarlari






# MODÜL YÖNETİCİSİ (yama sistemi) — ADMIN

# GELİŞİM ALANI - Tam İş Akışı


# OKUMA KAYITLARI (reading_logs) + ÖĞRENCİ PANELİ
# aynı yollarla kayıtlı.

# /risk-skor/{ogrenci_id} ve /risk-skor/toplu aynı yollar+sırayla kayıtlı.

# XP + LİG + KUR SİSTEMİ (Faz 3)

from core.sistem import (
    XP_TABLOSU_DEFAULT, LIG_ESIKLERI_DEFAULT, LIG_SIRA,
    OGRETMEN_ROZETLERI_DEFAULT, OGRENCI_ROZETLERI_DEFAULT, ANKET_SORULARI_DEFAULT,
    get_xp_tablosu, get_lig_esikleri, get_ogretmen_rozetleri,
    get_ogrenci_rozetleri, get_anket_sorulari,
)


# SİSTEM AYARLARI YÖNETİMİ (Admin CRUD)

# ROZET SİSTEMİ (Öğretmen + Öğrenci)

# VELİ DEĞERLENDİRME ANKETİ


# KUR ATLAMA KAYDI (rozet için güncelleme)

# kur/atla endpoint'ini güncelle — kur_atlamalari collection'ına da kaydet
_original_kur_atla = None  # placeholder

# AI KOÇLUK + DNA + SORU ÜRETİMİ + HİKAYE



# ── KİTAP DERSLERİ — Öğrenci için sınıf/kitap bazlı okuma ──


# ── KİTAP İÇERİK EDİTÖRÜ (Admin) ──



# DALGA 2: SOCRATİC READİNG + KELİME EVRİMİ + MİNİ OYUN

# ── KELİME EVRİMİ (SPACED REPETITION) ──


# ── MİNİ OYUN ÜRETİCİ ──

# AI BİLGİ TABANI — PDF/DOCX Yükleme + AI Öğrenme + Puan Sistemi

# ── YANDEX DISK YARDIMCI FONKSİYONLAR ──────────────────────

# /hedefler/sablonlar, /hedefler (POST/GET), /hedefler/{id} (DELETE) aynı yollarla.

# Endpoint'ler (/bildirimler, /bildirimler/okunmamis, .../okundu,
# /bildirimler/tumunu-oku, DELETE, /bildirimler/kontrol) aynı yollarla kayıtlı.
# Paylaşılan semboller server.py'nin başka yerlerinde (startup demo seed,
# diagnostic rapor, görev, mesaj) kullanıldığı için import ediliyor.

# /mesajlar, /mesajlar/{id}/okundu, /mesajlar/okunmamis-sayisi aynı yollarla.
# (create_mesaj, bildirim_olustur'u modules.bildirim'den kullanır.)

# /gorevler, /gorevler/toplu, /gorevler/{id}/durum, DELETE, /gorevler/istatistik
# aynı yollarla. (create_gorev, bildirim_gorev_atandi'yı modules.bildirim'den kullanır.)

# DALGA 3: SPEECH AI — SESLİ OKUMA ANALİZİ


# DALGA 4: KİTAP ZEKÂ HARİTASI

ZEKA_ETIKETLER = {
    "soyutluk": "Soyutluk",
    "kelime_zorlugu": "Kelime Zorluğu",
    "hayal_gucu": "Hayal Gücü",
    "felsefi_derinlik": "Felsefi Derinlik",
    "aksiyon": "Aksiyon",
    "duygusal_yogunluk": "Duygusal Yoğunluk",
    "hedef_kelime_yogunlugu": "Kelime Yoğunluğu",
}


# DALGA 3: AI MOTİVASYON MOTORU

# DALGA 3: OKUMA EVRENİ (5 BÖLGE)


# DALGA 3: OKUMA DİKKAT ANALİZİ


# DALGA 3: OKUMA DİKKAT ANALİZİ

# DALGA 3: AI OKUMA ARKADAŞI (4 KARAKTER)

# ═══════════════════════════════════════════════════════════
# DALGA 4 — SCAFFOLD READING
# ═══════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════
# DALGA 4 — AI MATERYAl ÜRETİCİ
# ═══════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════
# DALGA 4 — ADAPTIVE STORY ENGINE
# ═══════════════════════════════════════════════════════════

# POST-READING AI — Kitap Bitirme Sonrası Analiz

# KİTAP ZEKÂ HARİTASI — 7 Boyutlu AI Profil

# KİTABA ÖZGÜ MİNİ OYUN — Kitap içeriğinden üret

# OKUMA EVRENİ — 5 Bölge Gamification

# AI MOTİVASYON MOTORU — Mikro Hedef + Streak Koruma

# AI GELİŞİM SİMÜLASYONU

# AI OKUMA TERAPİSİ — Erken Tespit

# HİBRİT İÇERİK ONAY — AI Skor Sistemi

# TÜRKİYE OKUMA HARİTASI (Anonim, KVKK uyumlu)


# ETKİ İSTATİSTİKLERİ

# ÖZELLİK YÖNETİMİ — Admin Panel Feature Flags

# APP SETUP

# ★ CORS middleware yukarıda (app oluşturulduktan hemen sonra) eklendi
# Router'ı burada dahil ediyoruz
from core.registry import register_routers
register_routers(api_router)
app.include_router(api_router)

# ── Statik dosyalar (öğretmen profil fotoğrafları vb.) ──
# /uploads/... altındaki dosyalar doğrudan servis edilir (API prefix'i olmadan).
try:
    from fastapi.staticfiles import StaticFiles
    _uploads_dir = Path(__file__).resolve().parent / "uploads"
    _uploads_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/uploads", StaticFiles(directory=str(_uploads_dir)), name="uploads")
except Exception as _ex:
    logging.warning(f"[server] uploads statik mount başarısız: {_ex}")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()

# PEER REVIEW ROZET SİSTEMİ

# GLOBAL KELİME HARİTASI

# KVKK / VERİ YÖNETİMİ

# SEZONLUK RESET
