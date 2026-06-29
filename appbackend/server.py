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
from modules.auth_api import router as auth_router
api_router.include_router(auth_router)

# STARTUP: Admin kullanıcı oluştur

from modules.seed import create_default_admin
app.add_event_handler("startup", create_default_admin)

# MEVCUT MODELLER (değişmeden korunuyor)

# CRM modelleri (Teacher/Student/Course/Ders/Payment + Create/Update + ExportData)

# MEVCUT ROUTE'LAR (değişmeden korunuyor)

# Dashboard & istatistik endpoint'leri (/dashboard, /dashboard/bekleyenler,
from modules.dashboard import router as dashboard_router
api_router.include_router(dashboard_router)

# CRM endpoint'leri (/teachers, /students, /courses, /dersler, /payments, /export)
from modules.crm import router as crm_router
api_router.include_router(crm_router)

# YEDEKLEME (BACKUP) + GÜNCELLEME (UPDATE CHECK) — ADMIN
#   /admin/backups/{id}/download, /admin/backups/{id}/restore, DELETE,
#   /admin/version, /admin/updates/check) aynı yollarla kayıtlı kalır.
from modules.yedekleme import router as yedekleme_router
api_router.include_router(yedekleme_router)

# GİRİŞ ANALİZİ (FAZ 1A)

from modules.diagnostic import router as diagnostic_router
api_router.include_router(diagnostic_router)

# ── Puan Ayarları ──
from core.sistem import VARSAYILAN_PUANLAR, get_puan_ayarlari

from modules.ayarlar import router as ayarlar_router
api_router.include_router(ayarlar_router)

from modules.egzersiz import router as egzersiz_router
api_router.include_router(egzersiz_router)

from modules.kitap import router as kitap_router
api_router.include_router(kitap_router)

from modules.sorular import router as sorular_router
api_router.include_router(sorular_router)

from modules.admin_debug import router as admin_debug_router
api_router.include_router(admin_debug_router)

# MODÜL YÖNETİCİSİ (yama sistemi) — ADMIN
from modules.admin_patch import router as admin_patch_router
api_router.include_router(admin_patch_router)

# GELİŞİM ALANI - Tam İş Akışı

from modules.gelisim import router as gelisim_router
api_router.include_router(gelisim_router)

# OKUMA KAYITLARI (reading_logs) + ÖĞRENCİ PANELİ
# aynı yollarla kayıtlı.
from modules.ogrenci_panel import router as ogrenci_panel_router
api_router.include_router(ogrenci_panel_router)

# /risk-skor/{ogrenci_id} ve /risk-skor/toplu aynı yollar+sırayla kayıtlı.
from modules.risk import router as risk_router
api_router.include_router(risk_router)

# XP + LİG + KUR SİSTEMİ (Faz 3)

from core.sistem import (
    XP_TABLOSU_DEFAULT, LIG_ESIKLERI_DEFAULT, LIG_SIRA,
    OGRETMEN_ROZETLERI_DEFAULT, OGRENCI_ROZETLERI_DEFAULT, ANKET_SORULARI_DEFAULT,
    get_xp_tablosu, get_lig_esikleri, get_ogretmen_rozetleri,
    get_ogrenci_rozetleri, get_anket_sorulari,
)

from modules.ilerleme import router as ilerleme_router
api_router.include_router(ilerleme_router)

# SİSTEM AYARLARI YÖNETİMİ (Admin CRUD)

# ROZET SİSTEMİ (Öğretmen + Öğrenci)

# VELİ DEĞERLENDİRME ANKETİ

from modules.anketler import router as anketler_router
api_router.include_router(anketler_router)

# KUR ATLAMA KAYDI (rozet için güncelleme)

# kur/atla endpoint'ini güncelle — kur_atlamalari collection'ına da kaydet
_original_kur_atla = None  # placeholder

# AI KOÇLUK + DNA + SORU ÜRETİMİ + HİKAYE

from modules.ai_kocluk import router as ai_kocluk_router
api_router.include_router(ai_kocluk_router)

from modules.ai_uretim import router as ai_uretim_router
api_router.include_router(ai_uretim_router)

# ── KİTAP DERSLERİ — Öğrenci için sınıf/kitap bazlı okuma ──

from modules.kitap_dersleri import router as kitap_dersleri_router
api_router.include_router(kitap_dersleri_router)

# ── KİTAP İÇERİK EDİTÖRÜ (Admin) ──

from modules.ai_bilgi_tabani import router as ai_bilgi_tabani_router
api_router.include_router(ai_bilgi_tabani_router)

from modules.ai_socratic import router as ai_socratic_router
api_router.include_router(ai_socratic_router)

# DALGA 2: SOCRATİC READİNG + KELİME EVRİMİ + MİNİ OYUN

# ── KELİME EVRİMİ (SPACED REPETITION) ──

from modules.ai_kelime import router as ai_kelime_router
api_router.include_router(ai_kelime_router)

# ── MİNİ OYUN ÜRETİCİ ──

# AI BİLGİ TABANI — PDF/DOCX Yükleme + AI Öğrenme + Puan Sistemi

# ── YANDEX DISK YARDIMCI FONKSİYONLAR ──────────────────────

# /hedefler/sablonlar, /hedefler (POST/GET), /hedefler/{id} (DELETE) aynı yollarla.
from modules.hedef import router as hedef_router
api_router.include_router(hedef_router)

# Endpoint'ler (/bildirimler, /bildirimler/okunmamis, .../okundu,
# /bildirimler/tumunu-oku, DELETE, /bildirimler/kontrol) aynı yollarla kayıtlı.
# Paylaşılan semboller server.py'nin başka yerlerinde (startup demo seed,
# diagnostic rapor, görev, mesaj) kullanıldığı için import ediliyor.
from modules.bildirim import (
    router as bildirim_router,
    BILDIRIM_TURLERI,
    bildirim_olustur,
    bildirim_gorev_atandi,
    bildirim_rapor_tamamlandi,
)
api_router.include_router(bildirim_router)

# /mesajlar, /mesajlar/{id}/okundu, /mesajlar/okunmamis-sayisi aynı yollarla.
# (create_mesaj, bildirim_olustur'u modules.bildirim'den kullanır.)
from modules.mesaj import router as mesaj_router
api_router.include_router(mesaj_router)

# /gorevler, /gorevler/toplu, /gorevler/{id}/durum, DELETE, /gorevler/istatistik
# aynı yollarla. (create_gorev, bildirim_gorev_atandi'yı modules.bildirim'den kullanır.)
from modules.gorev import router as gorev_router
api_router.include_router(gorev_router)

# DALGA 3: SPEECH AI — SESLİ OKUMA ANALİZİ

from modules.ai_speech import router as ai_speech_router, SPEECH_OKUMA_METİNLERİ
api_router.include_router(ai_speech_router)

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

from modules.ai_kitap_zeka import router as ai_kitap_zeka_router
api_router.include_router(ai_kitap_zeka_router)

# DALGA 3: AI MOTİVASYON MOTORU

# DALGA 3: OKUMA EVRENİ (5 BÖLGE)

from modules.ai_oyunlastirma import router as ai_oyunlastirma_router
api_router.include_router(ai_oyunlastirma_router)

# DALGA 3: OKUMA DİKKAT ANALİZİ

from modules.ai_dikkat_arkadas import router as ai_dikkat_arkadas_router
api_router.include_router(ai_dikkat_arkadas_router)

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

from modules.kullanici import router as kullanici_router
api_router.include_router(kullanici_router)

# ETKİ İSTATİSTİKLERİ

# ÖZELLİK YÖNETİMİ — Admin Panel Feature Flags

# APP SETUP

# ★ CORS middleware yukarıda (app oluşturulduktan hemen sonra) eklendi
# Router'ı burada dahil ediyoruz
app.include_router(api_router)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()

# PEER REVIEW ROZET SİSTEMİ

# GLOBAL KELİME HARİTASI

# KVKK / VERİ YÖNETİMİ

# SEZONLUK RESET
