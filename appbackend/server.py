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

# ─────────────────────────────────────────────
# ÇEKİRDEK KATMAN (core/) — yapılandırma, DB bağlantısı, kimlik doğrulama
# Aşağıdaki semboller core/ altına taşındı; davranış birebir aynıdır.
# ─────────────────────────────────────────────
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

# ── Gemini AI yardımcıları → core/ai.py'ye taşındı.
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

# ─────────────────────────────────────────────
# ENUMS / HELPERS / AUTH
# (TeacherLevel, UserRole, prepare_for_mongo, parse_from_mongo,
#  hash_password, verify_password, create_access_token, decode_token,
#  get_current_user, require_role) → core/auth.py ve core/db.py'ye taşındı;
# yukarıda import ediliyorlar. Davranış birebir aynıdır.
# ─────────────────────────────────────────────

# ─────────────────────────────────────────────
# AUTH (modeller + /auth/* route'ları) → modules/auth_api.py'ye taşındı.
# UserCreate/UserLogin/UserResponse/TokenResponse/ChangePassword ve 7 endpoint
# aynı yollarla kayıtlı kalır.
# ─────────────────────────────────────────────
from modules.auth_api import router as auth_router
api_router.include_router(auth_router)

# ─────────────────────────────────────────────
# STARTUP: Admin kullanıcı oluştur
# ─────────────────────────────────────────────

@app.on_event("startup")
async def create_default_admin():
    """
    .env dosyasındaki bilgilerle varsayılan admin oluşturur.
    Admin zaten varsa tekrar oluşturmaz.
    """
    admin_email = os.environ.get('ADMIN_EMAIL', 'admin@oba.com')
    admin_password = os.environ.get('ADMIN_PASSWORD', 'Admin123!')
    admin_ad = os.environ.get('ADMIN_AD', 'Sistem')
    admin_soyad = os.environ.get('ADMIN_SOYAD', 'Yöneticisi')

    existing = await db.users.find_one({"email": admin_email})
    if not existing:
        admin_doc = {
            "id": str(uuid.uuid4()),
            "ad": admin_ad,
            "soyad": admin_soyad,
            "email": admin_email,
            "password_hash": hash_password(admin_password),
            "role": UserRole.ADMIN.value,
            "linked_id": None,
            "olusturma_tarihi": datetime.now(timezone.utc).isoformat()
        }
        await db.users.insert_one(admin_doc)
        logging.info(f"✅ Varsayılan admin oluşturuldu: {admin_email}")
    else:
        logging.info(f"ℹ️ Admin zaten mevcut: {admin_email}")

    # ── DEMO VERİLERİ ──
    demo_student_email = "demo-ogrenci@oba.com"
    demo_teacher_email = "demo-ogretmen@oba.com"
    demo_parent_email = "demo-veli@oba.com"
    DEMO_PASSWORD = "Demo123!"

    from datetime import timedelta
    simdi = datetime.now(timezone.utc)

    # --- DEMO ÖĞRETMEN ---
    existing_teacher = await db.users.find_one({"email": demo_teacher_email})
    if not existing_teacher:
        demo_teacher_id = str(uuid.uuid4())
        # teachers collection
        existing_t_col = await db.teachers.find_one({"ad": "Ayşe", "soyad": "Öğretmen"})
        if not existing_t_col:
            await db.teachers.insert_one({
                "id": demo_teacher_id, "ad": "Ayşe", "soyad": "Öğretmen", "brans": "Türkçe",
                "telefon": "05001112233", "seviye": "uzman", "ogrenci_sayisi": 3,
                "yapilmasi_gereken_odeme": 0, "yapilan_odeme": 0, "arsivli": False,
                "olusturma_tarihi": simdi.isoformat()
            })
        else:
            demo_teacher_id = existing_t_col["id"]

        demo_teacher_user_id = str(uuid.uuid4())
        await db.users.insert_one({
            "id": demo_teacher_user_id, "ad": "Ayşe", "soyad": "Öğretmen",
            "email": demo_teacher_email, "password_hash": hash_password(DEMO_PASSWORD),
            "role": "teacher", "linked_id": demo_teacher_id, "telefon": "05001112233",
            "olusturma_tarihi": simdi.isoformat()
        })
        logging.info(f"✅ Demo öğretmen oluşturuldu: {demo_teacher_email} / {DEMO_PASSWORD}")
    else:
        demo_teacher_user_id = existing_teacher["id"]
        demo_teacher_id = existing_teacher.get("linked_id", "")
        logging.info(f"ℹ️ Demo öğretmen zaten var: {demo_teacher_email}")

    # --- DEMO ÖĞRENCİLER ---
    existing_student = await db.users.find_one({"email": demo_student_email})
    if not existing_student:
        ogrenci_adlari = [
            ("Ali", "Yılmaz", "4", "Kur 2"), ("Zeynep", "Demir", "3", "Kur 1"),
            ("Mehmet", "Kaya", "5", "Kur 3"),
        ]
        demo_students = []
        for ad, soyad, sinif, kur in ogrenci_adlari:
            sid = str(uuid.uuid4())
            demo_students.append(sid)
            existing_s_col = await db.students.find_one({"ad": ad, "soyad": soyad})
            if not existing_s_col:
                await db.students.insert_one({
                    "id": sid, "ad": ad, "soyad": soyad, "sinif": sinif, "kur": kur,
                    "veli_ad": "Demo", "veli_soyad": "Veli", "veli_telefon": "05009998877",
                    "aldigi_egitim": "Okuma Becerileri Temel", "ogretmen_id": demo_teacher_id,
                    "yapilmasi_gereken_odeme": 2400, "yapilan_odeme": 0, "ogretmene_yapilacak_odeme": 800,
                    "arsivli": False, "toplam_xp": 0, "olusturma_tarihi": simdi.isoformat()
                })
            else:
                demo_students[-1] = existing_s_col["id"]

        # Ana öğrenci user
        demo_student_user_id = str(uuid.uuid4())
        await db.users.insert_one({
            "id": demo_student_user_id, "ad": "Ali", "soyad": "Yılmaz",
            "email": demo_student_email, "password_hash": hash_password(DEMO_PASSWORD),
            "role": "student", "linked_id": demo_students[0], "telefon": "",
            "olusturma_tarihi": simdi.isoformat()
        })
        # Diğer öğrenciler
        for i, (ad, soyad, _, _) in enumerate(ogrenci_adlari[1:], 1):
            await db.users.insert_one({
                "id": str(uuid.uuid4()), "ad": ad, "soyad": soyad,
                "email": f"demo-ogrenci{i+1}@oba.com", "password_hash": hash_password(DEMO_PASSWORD),
                "role": "student", "linked_id": demo_students[i], "telefon": "",
                "olusturma_tarihi": simdi.isoformat()
            })

        # Okuma kayıtları
        kitaplar = ["Küçük Prens", "Charlie'nin Çikolata Fabrikası", "Pollyanna"]
        for gun in range(14):
            tarih = (simdi - timedelta(days=gun)).isoformat()
            await db.reading_logs.insert_one({
                "id": str(uuid.uuid4()), "ogrenci_id": demo_students[0],
                "ogrenci_ad": "Ali Yılmaz", "kitap_adi": kitaplar[gun % len(kitaplar)],
                "bolum": f"Bölüm {gun % 8 + 1}", "baslangic_sayfa": gun * 10 + 1,
                "bitis_sayfa": gun * 10 + 12, "sure_dakika": random.randint(8, 25),
                "not_text": "", "tarih": tarih,
            })
        for i, sid in enumerate(demo_students[1:], 1):
            for gun in range(random.randint(3, 10)):
                await db.reading_logs.insert_one({
                    "id": str(uuid.uuid4()), "ogrenci_id": sid,
                    "ogrenci_ad": ogrenci_adlari[i][0] + " " + ogrenci_adlari[i][1],
                    "kitap_adi": kitaplar[gun % len(kitaplar)],
                    "bolum": f"Bölüm {gun % 5 + 1}", "baslangic_sayfa": gun * 8 + 1,
                    "bitis_sayfa": gun * 8 + 10, "sure_dakika": random.randint(5, 20),
                    "not_text": "", "tarih": (simdi - timedelta(days=gun)).isoformat(),
                })

        # XP
        xp_eylemleri = ["okuma_gorevi"] * 10 + ["gorev_tamamla"] * 3 + ["egzersiz"] * 5 + ["gelisim_tamamla"] * 2
        toplam_xp = 0
        for eylem in xp_eylemleri:
            xp = (await get_xp_tablosu()).get(eylem, 5)
            toplam_xp += xp
            await db.xp_logs.insert_one({
                "id": str(uuid.uuid4()), "ogrenci_id": demo_students[0],
                "eylem": eylem, "xp": xp, "tarih": (simdi - timedelta(hours=random.randint(1, 200))).isoformat(),
            })
        await db.students.update_one({"id": demo_students[0]}, {"$set": {"toplam_xp": toplam_xp}})
        for sid in demo_students[1:]:
            await db.students.update_one({"id": sid}, {"$set": {"toplam_xp": random.randint(30, 150)}})

        # Görevler
        await db.gorevler.insert_one({
            "id": str(uuid.uuid4()), "hedef_id": demo_students[0], "hedef_tip": "ogrenci",
            "hedef_ad": "Ali Yılmaz", "baslik": "Küçük Prens — Bölüm 5-6 oku",
            "aciklama": "Bu hafta Küçük Prens'in 5. ve 6. bölümlerini oku.", "tur": "kitap",
            "son_tarih": (simdi + timedelta(days=5)).strftime("%Y-%m-%d"),
            "atayan_id": demo_teacher_user_id, "atayan_ad": "Ayşe Öğretmen", "atayan_rol": "teacher",
            "durum": "bekliyor", "olusturma_tarihi": simdi.isoformat(),
            "makale_link": None, "kitap_yazar": "Antoine de Saint-Exupéry",
            "kitap_isbn": "", "kitap_link": "", "kitap_kapak": "", "film_link": None,
        })
        await db.gorevler.insert_one({
            "id": str(uuid.uuid4()), "hedef_id": demo_students[0], "hedef_tip": "ogrenci",
            "hedef_ad": "Ali Yılmaz", "baslik": "Hızlı Okuma Egzersizi yap",
            "aciklama": "Egzersizlerden 'Hızlı Kelime Okuma' tamamla.", "tur": "egzersiz",
            "son_tarih": (simdi + timedelta(days=3)).strftime("%Y-%m-%d"),
            "atayan_id": demo_teacher_user_id, "atayan_ad": "Ayşe Öğretmen", "atayan_rol": "teacher",
            "durum": "bekliyor", "olusturma_tarihi": simdi.isoformat(),
            "makale_link": None, "kitap_yazar": None, "kitap_isbn": None,
            "kitap_link": None, "kitap_kapak": None, "film_link": None,
        })
        await db.gorevler.insert_one({
            "id": str(uuid.uuid4()), "hedef_id": demo_students[0], "hedef_tip": "ogrenci",
            "hedef_ad": "Ali Yılmaz", "baslik": "Doğa belgeseli izle",
            "aciklama": "Belgeseli izleyip 3 cümle özet yaz.", "tur": "film", "son_tarih": None,
            "atayan_id": demo_teacher_user_id, "atayan_ad": "Ayşe Öğretmen", "atayan_rol": "teacher",
            "durum": "tamamlandi", "tamamlama_tarihi": (simdi - timedelta(days=2)).isoformat(),
            "tamamlama_notu": "Belgeseli izledim, çok güzeldi!", "olusturma_tarihi": (simdi - timedelta(days=5)).isoformat(),
            "makale_link": None, "kitap_yazar": None, "kitap_isbn": None,
            "kitap_link": None, "kitap_kapak": None, "film_link": "https://youtube.com/watch?v=example",
        })

        # Mesaj
        await db.mesajlar.insert_one({
            "id": str(uuid.uuid4()), "gonderen_id": demo_teacher_user_id,
            "gonderen_ad": "Ayşe Öğretmen", "gonderen_rol": "teacher",
            "alici_id": demo_student_user_id, "alici_ad": "Ali Yılmaz", "alici_rol": "student",
            "konu": "Tebrikler! 🎉", "icerik": "Ali, bu hafta çok güzel ilerleme kaydettin. Böyle devam et!",
            "okundu": False, "tarih": (simdi - timedelta(hours=3)).isoformat(),
        })
        logging.info(f"✅ Demo öğrenciler oluşturuldu: {demo_student_email} / {DEMO_PASSWORD}")
    else:
        demo_student_user_id = existing_student["id"]
        logging.info(f"ℹ️ Demo öğrenci zaten var: {demo_student_email}")

    # --- DEMO VELİ ---
    existing_parent = await db.users.find_one({"email": demo_parent_email})
    if not existing_parent:
        # Ali Yılmaz'ın student id'sini bul
        ali = await db.users.find_one({"email": demo_student_email})
        ali_linked = ali.get("linked_id", "") if ali else ""
        await db.users.insert_one({
            "id": str(uuid.uuid4()), "ad": "Demo", "soyad": "Veli",
            "email": demo_parent_email, "password_hash": hash_password(DEMO_PASSWORD),
            "role": "parent", "linked_id": ali_linked, "telefon": "05009998877",
            "olusturma_tarihi": simdi.isoformat()
        })
        logging.info(f"✅ Demo veli oluşturuldu: {demo_parent_email} / {DEMO_PASSWORD}")
    else:
        logging.info(f"ℹ️ Demo veli zaten var: {demo_parent_email}")

    # --- DEMO ROZET + ANKET VERİLERİ ---
    existing_rozetler = await db.kazanilan_rozetler.find_one({"kullanici_id": {"$regex": "^demo-"}})
    if not existing_rozetler:
        logging.info("🏅 Demo rozet + anket verileri oluşturuluyor...")

        # Demo user id'lerini bul
        demo_ogretmen_user = await db.users.find_one({"email": demo_teacher_email})
        demo_ogrenci_user = await db.users.find_one({"email": demo_student_email})
        demo_veli_user = await db.users.find_one({"email": demo_parent_email})

        if demo_ogretmen_user and demo_ogrenci_user:
            ogretmen_uid = demo_ogretmen_user["id"]
            ogretmen_lid = demo_ogretmen_user.get("linked_id", "")
            ogrenci_uid = demo_ogrenci_user["id"]
            ogrenci_lid = demo_ogrenci_user.get("linked_id", "")

            # Öğretmen rozetleri
            ogretmen_rozetler = [
                "icerik_ilk", "icerik_5",  # İçerik katkısı
                "oy_ilk", "oy_20",  # Kalite kontrol
                "gorev_ilk", "gorev_20",  # Eğitimci
                "kur_ilk",  # Kur atlama
                "gelisim_ilk", "gelisim_10",  # Gelişim
                "mesaj_ilk",  # İletişim
                "egz_ilk",  # Egzersiz
            ]
            for kod in ogretmen_rozetler:
                await db.kazanilan_rozetler.insert_one({
                    "id": str(uuid.uuid4()),
                    "kullanici_id": ogretmen_uid,
                    "rozet_kodu": kod,
                    "kazanma_tarihi": (simdi - timedelta(days=random.randint(1, 30))).isoformat(),
                })

            # Öğrenci rozetleri (Ali Yılmaz)
            ogrenci_rozetler = [
                "okuma_ilk", "okuma_100",  # Okuma
                "streak_3", "streak_7",  # Streak
                "kitap_1", "kitap_5",  # Kitap
                "gorev_ilk", "gorev_10",  # Görev
                "egz_ilk",  # Egzersiz
                "orman_ilk", "orman_50",  # Orman
            ]
            for kod in ogrenci_rozetler:
                await db.kazanilan_rozetler.insert_one({
                    "id": str(uuid.uuid4()),
                    "kullanici_id": ogrenci_uid,
                    "rozet_kodu": kod,
                    "kazanma_tarihi": (simdi - timedelta(days=random.randint(1, 20))).isoformat(),
                })

            # Diğer demo öğrencilere de birkaç rozet
            for email_suffix in ["2", "3"]:
                other = await db.users.find_one({"email": f"demo-ogrenci{email_suffix}@oba.com"})
                if other:
                    for kod in ["okuma_ilk", "streak_3", "kitap_1", "gorev_ilk"]:
                        await db.kazanilan_rozetler.insert_one({
                            "id": str(uuid.uuid4()),
                            "kullanici_id": other["id"],
                            "rozet_kodu": kod,
                            "kazanma_tarihi": (simdi - timedelta(days=random.randint(1, 15))).isoformat(),
                        })

            # Kur atlama kayıtları (öğretmen rozeti için)
            for i in range(3):
                await db.kur_atlamalari.insert_one({
                    "id": str(uuid.uuid4()),
                    "ogrenci_id": ogrenci_lid if i == 0 else str(uuid.uuid4()),
                    "ogretmen_id": ogretmen_lid,
                    "eski_kur": f"Kur {i+1}",
                    "yeni_kur": f"Kur {i+2}",
                    "tarih": (simdi - timedelta(days=random.randint(5, 60))).isoformat(),
                })

            # Veli anketleri (öğretmen rozeti + dashboard için)
            if demo_veli_user:
                veli_uid = demo_veli_user["id"]
                anket_kategoriler = ["iletisim", "duzen", "etki", "geri_bildirim", "motivasyon", "icerik", "genel"]

                # 3 farklı dönem için anket
                for donem_offset in [0, 1, 2]:
                    donem_ay = (simdi - timedelta(days=donem_offset * 30)).strftime("%Y-D%m")
                    yanitlar = []
                    for j, kat in enumerate(anket_kategoriler):
                        puan = random.choice([4, 4, 5, 5, 5, 4, 5])  # yüksek puanlar
                        yanitlar.append({"soru_no": j + 1, "puan": puan, "kategori": kat})

                    await db.veli_anketleri.insert_one({
                        "id": str(uuid.uuid4()),
                        "veli_id": veli_uid,
                        "veli_ad": "Demo Veli",
                        "ogretmen_id": ogretmen_lid,
                        "ogrenci_id": ogrenci_lid,
                        "donem": donem_ay,
                        "yanitlar": yanitlar,
                        "tavsiye": random.choice([True, True, True, False]),  # %75 tavsiye
                        "not_text": random.choice([
                            "Çocuğum çok gelişti, teşekkürler!",
                            "Öğretmenimizden memnunuz.",
                            "Okuma alışkanlığı kazandı, çok mutluyuz.",
                            "",
                        ]),
                        "tarih": (simdi - timedelta(days=donem_offset * 30 + random.randint(0, 5))).isoformat(),
                    })

                # Birkaç tane daha farklı "veli"den anket (aynı öğretmene)
                sahte_veliler = ["Veli A", "Veli B", "Veli C", "Veli D", "Veli E"]
                for veli_ad in sahte_veliler:
                    yanitlar = []
                    for j, kat in enumerate(anket_kategoriler):
                        yanitlar.append({"soru_no": j + 1, "puan": random.choice([3, 4, 4, 5, 5]), "kategori": kat})
                    await db.veli_anketleri.insert_one({
                        "id": str(uuid.uuid4()),
                        "veli_id": str(uuid.uuid4()),  # sahte veli id
                        "veli_ad": veli_ad,
                        "ogretmen_id": ogretmen_lid,
                        "ogrenci_id": str(uuid.uuid4()),
                        "donem": simdi.strftime("%Y-D%m"),
                        "yanitlar": yanitlar,
                        "tavsiye": random.choice([True, True, True, True, False]),
                        "not_text": random.choice(["Memnunuz", "Teşekkürler", "Güzel çalışma", ""]),
                        "tarih": (simdi - timedelta(days=random.randint(1, 20))).isoformat(),
                    })

            # Demo bildirimler
            demo_bildirimler = [
                (ogrenci_uid, "gorev_atandi", "Ayşe Öğretmen size yeni görev atadı: Küçük Prens Bölüm 5-6", 3),
                (ogrenci_uid, "streak_tebrik", "🎉 7 gün üst üste okudun! Harika gidiyorsun!", 1),
                (ogrenci_uid, "rozet_kazandi", "🏅 Yeni rozet: Kararlı Okuyucu! 7 gün streak başarısı.", 2),
                (ogretmen_uid, "risk_yuksek", "🚨 Mehmet Kaya son 7 gündür hiç okuma yapmadı!", 1),
                (ogretmen_uid, "gorev_tamamlandi", "Ali Yılmaz 'Doğa belgeseli izle' görevini tamamladı.", 3),
            ]
            if demo_veli_user:
                demo_bildirimler.append((demo_veli_user["id"], "rapor_tamamlandi", "Ali Yılmaz için yeni giriş analizi raporu hazır.", 2))
                demo_bildirimler.append((demo_veli_user["id"], "streak_kirildi", "Ali dün okuma yapmadı. Streak kırılma riski!", 0))
                demo_bildirimler.append((demo_veli_user["id"], "anket_hatirlatma", "Öğretmeninizi değerlendirmek ister misiniz? ⭐", 5))

            for alici, tur, icerik, gun_once in demo_bildirimler:
                await db.bildirimler.insert_one({
                    "id": str(uuid.uuid4()), "alici_id": alici, "tur": tur,
                    "baslik": BILDIRIM_TURLERI.get(tur, {}).get("baslik", "Bildirim"),
                    "icerik": icerik, "oncelik": BILDIRIM_TURLERI.get(tur, {}).get("oncelik", "normal"),
                    "ilgili_id": None, "okundu": gun_once > 2,
                    "tarih": (simdi - timedelta(hours=gun_once * 24 + random.randint(1, 12))).isoformat(),
                })

            logging.info(f"✅ Demo rozet + anket + bildirim verileri oluşturuldu!")
            logging.info(f"   🏅 Öğretmen: {len(ogretmen_rozetler)} rozet")
            logging.info(f"   🏅 Öğrenci: {len(ogrenci_rozetler)} rozet")
            logging.info(f"   ⭐ Veli anketleri: 8 adet")
    else:
        logging.info("ℹ️ Demo rozet + anket verileri zaten mevcut")

    # --- VARSAYILAN AYARLAR (boş ise seed et) ---
    ayar_defaults = {
        "xp_tablosu": XP_TABLOSU_DEFAULT,
        "lig_esikleri": LIG_ESIKLERI_DEFAULT,
        "ogretmen_rozetleri": OGRETMEN_ROZETLERI_DEFAULT,
        "ogrenci_rozetleri": OGRENCI_ROZETLERI_DEFAULT,
        "anket_sorulari": ANKET_SORULARI_DEFAULT,
    }
    for tip, default_val in ayar_defaults.items():
        doc = await db.sistem_ayarlari.find_one({"tip": tip})
        if not doc:
            await db.sistem_ayarlari.insert_one({"tip": tip, "degerler": default_val})
            logging.info(f"  ✅ Varsayılan ayar oluşturuldu: {tip}")
        elif not doc.get("degerler") or (isinstance(doc["degerler"], list) and len(doc["degerler"]) == 0) or (isinstance(doc["degerler"], dict) and len(doc["degerler"]) == 0):
            await db.sistem_ayarlari.update_one({"tip": tip}, {"$set": {"degerler": default_val}})
            logging.info(f"  🔄 Boş ayar düzeltildi: {tip}")

    # ── AI DEMO VERİLERİ ──
    ai_demo_var = await db.okuma_dna.find_one({"ogrenci_id": {"$exists": True}})
    if not ai_demo_var:
        logging.info("🧠 AI demo verileri oluşturuluyor...")

        # Demo öğrenci ID'lerini bul
        demo_ogrenciler = await db.students.find({"ad": {"$in": ["Ahmet", "Zeynep", "Can"]}}).to_list(length=10)
        if not demo_ogrenciler:
            demo_ogrenciler = await db.users.find({"role": "student"}).to_list(length=3)

        demo_ogretmen = await db.users.find_one({"email": "demo-ogretmen@oba.com"})
        ogretmen_id = demo_ogretmen["id"] if demo_ogretmen else "demo-teacher"

        for i, ogr in enumerate(demo_ogrenciler[:3]):
            oid = ogr["id"]
            ad = ogr.get("ad", f"Öğrenci{i+1}")
            sinif = ogr.get("sinif", 3)

            # ── DNA Profili ──
            dna_profiller = [
                {"kelime_gucu": 72, "akicilik": 45, "anlama_derinligi": 80, "dikkat_suresi": 55, "zorluk_toleransi": 60, "kelime_tekrar_ihtiyaci": 35, "okuma_psikolojisi": "keşifçi"},
                {"kelime_gucu": 58, "akicilik": 78, "anlama_derinligi": 42, "dikkat_suresi": 70, "zorluk_toleransi": 45, "kelime_tekrar_ihtiyaci": 50, "okuma_psikolojisi": "güvenli"},
                {"kelime_gucu": 35, "akicilik": 30, "anlama_derinligi": 55, "dikkat_suresi": 25, "zorluk_toleransi": 30, "kelime_tekrar_ihtiyaci": 75, "okuma_psikolojisi": "kararsız"},
            ]
            profil_tipler = ["hayalci_okuyucu", "hızlı_okuyucu", "başlangıç_okuyucu"]
            profil_labels = ["🌈 Hayalci Okuyucu", "⚡ Hızlı Okuyucu", "🌱 Başlangıç Okuyucu"]

            await db.okuma_dna.update_one({"ogrenci_id": oid}, {"$set": {
                "ogrenci_id": oid,
                "boyutlar": dna_profiller[i],
                "profil_tipi": profil_tipler[i],
                "profil_label": profil_labels[i],
                "sinif": sinif,
                "son_guncelleme": simdi.isoformat(),
            }}, upsert=True)

            # ── Koçluk Cache (demo analiz) ──
            demo_analizler = [
                {
                    "durum_degerlendirmesi": {"guclu_yonler": ["Anlama kapasitesi yüksek", "Hayal gücü gelişmiş", "Kitap seçiminde cesur"], "gelisim_alanlari": ["Okuma hızı geliştirilmeli", "Dikkat süresi artırılmalı"]},
                    "risk_analizi": {"seviye": "düşük", "faktorler": ["Akıcılık ortalamanın altında"], "aciliyet": "Takip yeterli"},
                    "mudahale_plani": {"hafta_1": "Günlük 10 dk sesli okuma", "hafta_2": "Tekrarlı okuma çalışmaları", "hafta_3": "Hız testi ve geri bildirim", "hafta_4": "Bağımsız okuma + analiz"},
                    "veliye_mesaj": f"Sayın Veli, {ad} okuma anlama becerisi çok iyi gelişiyor. Akıcılığını artırmak için evde günlük 10 dakika sesli okuma yapmasını öneririz. Hikâye kitapları ile başlamak motivasyonunu yüksek tutar.",
                    "haftalik_gorevler": [{"gun": "Pazartesi", "gorev": "Sevdiği bir kitaptan 2 sayfa sesli oku", "bloom": "uygulama"}, {"gun": "Salı", "gorev": "Okuduğu bölümün özetini yaz", "bloom": "sentez"}, {"gun": "Çarşamba", "gorev": "5 yeni kelime öğren ve cümle kur", "bloom": "uygulama"}, {"gun": "Perşembe", "gorev": "Karakterin motivasyonunu analiz et", "bloom": "analiz"}, {"gun": "Cuma", "gorev": "Hikâyeye alternatif son yaz", "bloom": "yaratma"}],
                    "kitap_tavsiyeleri": [{"ad": "Charlie'nin Çikolata Fabrikası", "yazar": "Roald Dahl", "neden": "Hayal gücü yüksek, kısa bölümler, macera dolu"}, {"ad": "Küçük Prens", "yazar": "Saint-Exupéry", "neden": "Felsefi derinlik, kısa paragraflar, soyut düşünmeyi geliştirir"}, {"ad": "Pollyanna", "yazar": "Eleanor H. Porter", "neden": "Pozitif bakış açısı, karakter gelişimi, orta zorluk"}],
                    "motivasyon_mesaji": f"Harika gidiyorsun {ad}! Bu hafta 3 kitap okudun, kelime gücün %72'ye ulaştı. Hedefine çok yakınsın! 🌟",
                    "kelime_mudahale": "Günlük 5 yeni kelime + görsel kartlarla çalışma. Spaced repetition: 1-3-7-21 gün aralığında tekrar.",
                    "metin_recetesi": {"paragraf_uzunlugu": "Orta (80-120 kelime)", "soyutluk": "Orta-yüksek", "aksiyon": "Yüksek", "hedef_kelime_orani": "%70 bilinen + %30 yeni"}
                },
                {
                    "durum_degerlendirmesi": {"guclu_yonler": ["Hızlı okuma", "Düzenli streak", "Dikkat süresi iyi"], "gelisim_alanlari": ["Anlama derinliği artırılmalı", "Bloom üst basamakları zayıf"]},
                    "risk_analizi": {"seviye": "düşük", "faktorler": ["Hızlı ama yüzeysel okuma eğilimi"], "aciliyet": "Bloom çalışması önerilir"},
                    "mudahale_plani": {"hafta_1": "Her okuma sonrası 3 soru cevapla", "hafta_2": "Karakter analizi çalışması", "hafta_3": "Metin karşılaştırma etkinliği", "hafta_4": "Tartışma soruları + yazılı yanıt"},
                    "veliye_mesaj": f"Sayın Veli, {ad} çok düzenli okuyor, tebrikler! Okuma hızı mükemmel. Şimdi anlama derinliğini artırmaya odaklanıyoruz. Okuduklarını sormak çok faydalı olacaktır.",
                    "haftalik_gorevler": [{"gun": "Pazartesi", "gorev": "Bir paragrafı oku ve ana fikri bul", "bloom": "analiz"}, {"gun": "Salı", "gorev": "İki karakteri karşılaştır", "bloom": "analiz"}, {"gun": "Çarşamba", "gorev": "Hikâyenin sonucunu tahmin et", "bloom": "sentez"}, {"gun": "Perşembe", "gorev": "Yazar neden böyle yazmış? Yorumla", "bloom": "degerlendirme"}, {"gun": "Cuma", "gorev": "Okuduğun kitap hakkında 5 cümle yaz", "bloom": "sentez"}],
                    "kitap_tavsiyeleri": [{"ad": "Martı", "yazar": "Richard Bach", "neden": "Kısa ama derin, felsefi düşünme gerektirir"}, {"ad": "Kaşağı", "yazar": "Ömer Seyfettin", "neden": "Kısa öykü, karakter analizi için ideal"}, {"ad": "Sefiller (Çocuk versiyonu)", "yazar": "Victor Hugo", "neden": "Değer yargıları, adalet teması"}],
                    "motivasyon_mesaji": f"Süpersin {ad}! Streak'in 12 günü geçti. Şimdi anlama gücünü artıralım — derin sorular senin için! 💪",
                    "kelime_mudahale": "Soyut kelimeler üzerine çalışma. Kavram haritaları oluşturma. Her gün 3 soyut kelime.",
                    "metin_recetesi": {"paragraf_uzunlugu": "Uzun (120-200 kelime)", "soyutluk": "Orta", "aksiyon": "Orta", "hedef_kelime_orani": "%60 bilinen + %40 yeni"}
                },
                {
                    "durum_degerlendirmesi": {"guclu_yonler": ["Meraklı", "Sorulara istekli cevap veriyor"], "gelisim_alanlari": ["Kelime hazinesi çok dar", "Akıcılık düşük", "Dikkat süresi kısa", "Streak tutarsız"]},
                    "risk_analizi": {"seviye": "yüksek", "faktorler": ["Kelime gücü sınıf ortalamasının altında", "Streak sık kırılıyor", "Zor metinlerden kaçınma eğilimi"], "aciliyet": "Acil müdahale gerekli"},
                    "mudahale_plani": {"hafta_1": "Günlük 5 dk kolay metin + kelime oyunu", "hafta_2": "Sesli okuma + anlık geri bildirim", "hafta_3": "Kısa hikâyeler + 3 kelime hedef", "hafta_4": "İlgi alanına göre metin seçimi"},
                    "veliye_mesaj": f"Sayın Veli, {ad} okumaya ilgi duyuyor ama desteğe ihtiyacı var. Evde günlük 5 dakika birlikte okuma yapmanız çok faydalı olacak. Hayvan hikâyeleri ile başlamanızı öneririz — ilgisini çekeceğini düşünüyoruz.",
                    "haftalik_gorevler": [{"gun": "Pazartesi", "gorev": "Resimli bir kitaptan 1 sayfa oku", "bloom": "bilgi"}, {"gun": "Salı", "gorev": "3 yeni kelime öğren (resimli kart)", "bloom": "bilgi"}, {"gun": "Çarşamba", "gorev": "Kısa bir masal dinle ve anlat", "bloom": "kavrama"}, {"gun": "Perşembe", "gorev": "Kelime oyunu oyna (eşleştirme)", "bloom": "uygulama"}, {"gun": "Cuma", "gorev": "En sevdiğin hayvanı anlatan 3 cümle yaz", "bloom": "uygulama"}],
                    "kitap_tavsiyeleri": [{"ad": "Kırmızı Başlıklı Kız", "yazar": "Charles Perrault", "neden": "Kısa, bilinen hikâye, kolay kelimeler"}, {"ad": "Bremen Mızıkacıları", "yazar": "Grimm Kardeşler", "neden": "Hayvan karakterleri, eğlenceli, tekrarlı yapı"}, {"ad": "Pinokyo", "yazar": "Carlo Collodi", "neden": "Macera dolu, kısa bölümler, ahlak dersi"}],
                    "motivasyon_mesaji": f"Merhaba {ad}! Bugün sadece 5 dakika okumaya ne dersin? Küçük adımlar büyük fark yaratır! 🌱",
                    "kelime_mudahale": "Günlük 3 kolay kelime + resimli kartlar + eşleştirme oyunu. Tekrar: 1-2-5-12 gün aralığında.",
                    "metin_recetesi": {"paragraf_uzunlugu": "Çok kısa (30-60 kelime)", "soyutluk": "Düşük (somut)", "aksiyon": "Çok yüksek", "hedef_kelime_orani": "%85 bilinen + %15 yeni"}
                },
            ]

            await db.ai_kocluk_cache.update_one(
                {"ogrenci_id": oid},
                {"$set": {
                    "id": str(uuid.uuid4()),
                    "ogrenci_id": oid,
                    "dna": {"profil_tipi": profil_tipler[i], "profil_label": profil_labels[i], "boyutlar": dna_profiller[i]},
                    "ai_analiz": demo_analizler[i],
                    "ai_ham_metin": "",
                    "model": "demo",
                    "token": 0,
                    "maliyet": 0,
                    "tarih": simdi.isoformat(),
                }},
                upsert=True,
            )

        # ── Demo Kelimeler (meb_kelime_haritasi) ──
        demo_kelimeler = [
            {"kelime": "macera", "anlam": "Tehlikeli ve heyecan verici olay", "ornek_cumle": "Çocuklar ormanda büyük bir macera yaşadı.", "zorluk": 4, "sinif": 3},
            {"kelime": "keşif", "anlam": "Bilinmeyen bir şeyi ilk kez bulma", "ornek_cumle": "Bilim insanı yeni bir keşif yaptı.", "zorluk": 5, "sinif": 3},
            {"kelime": "pusula", "anlam": "Yön bulmaya yarayan araç", "ornek_cumle": "Kaşif pusulasıyla yolunu buldu.", "zorluk": 6, "sinif": 3},
            {"kelime": "cesaret", "anlam": "Korkmadan hareket edebilme gücü", "ornek_cumle": "Küçük kız büyük cesaret gösterdi.", "zorluk": 4, "sinif": 3},
            {"kelime": "merak", "anlam": "Bir şeyi bilmek isteme duygusu", "ornek_cumle": "Merak eden çocuk her şeyi sorar.", "zorluk": 3, "sinif": 3},
            {"kelime": "sabır", "anlam": "Bekleyebilme ve dayanma gücü", "ornek_cumle": "Bahçıvan sabırla çiçeklerin büyümesini bekledi.", "zorluk": 4, "sinif": 3},
            {"kelime": "hayal gücü", "anlam": "Zihinde yeni şeyler oluşturabilme becerisi", "ornek_cumle": "Hayal gücü güçlü olan çocuklar iyi hikâye yazar.", "zorluk": 5, "sinif": 3},
            {"kelime": "fedakarlık", "anlam": "Başkaları için kendi isteklerinden vazgeçme", "ornek_cumle": "Anneler çocukları için büyük fedakarlıklar yapar.", "zorluk": 7, "sinif": 4},
            {"kelime": "dürüstlük", "anlam": "Doğruyu söyleme, hile yapmama", "ornek_cumle": "Dürüstlük en değerli erdemlerden biridir.", "zorluk": 5, "sinif": 4},
            {"kelime": "azim", "anlam": "Bir işi sonuna kadar kararlılıkla sürdürme", "ornek_cumle": "Azimli öğrenci başarıya ulaştı.", "zorluk": 6, "sinif": 4},
            {"kelime": "empati", "anlam": "Başkalarının duygularını anlayabilme", "ornek_cumle": "Empati kurabilen insanlar daha iyi arkadaş olur.", "zorluk": 7, "sinif": 5},
            {"kelime": "göç", "anlam": "Bir yerden başka bir yere toplu taşınma", "ornek_cumle": "Kuşlar kışın sıcak ülkelere göç eder.", "zorluk": 4, "sinif": 3},
        ]
        for k in demo_kelimeler:
            mevcut = await db.meb_kelime_haritasi.find_one({"kelime": k["kelime"]})
            if not mevcut:
                await db.meb_kelime_haritasi.insert_one({
                    "id": str(uuid.uuid4()), "kaynak": "Demo - MEB Türkçe",
                    "yukleyen_id": ogretmen_id, "tarih": simdi.isoformat(), **k,
                })

        # ── Demo AI Yükleme (tamamlanmış) ──
        demo_yuk_id = str(uuid.uuid4())
        mevcut_yuk = await db.ai_yuklemeler.find_one({"kitap_adi": "Türkçe 3 Ders Kitabı (Demo)"})
        if not mevcut_yuk:
            await db.ai_yuklemeler.insert_one({
                "id": demo_yuk_id, "dosya_adi": "turkce_3_ders_kitabi.pdf", "dosya_boyut": 4500000,
                "dosya_format": ".pdf", "dosya_hash": "demo_hash_001", "dosya_b64": "",
                "sinif": 3, "tur": "ders_kitabi", "kitap_adi": "Türkçe 3 Ders Kitabı (Demo)",
                "yazar": "MEB", "temalar": ["Erdemler", "Doğa ve Evren", "Çocuk Dünyası"],
                "yukleyen_id": ogretmen_id, "yukleyen_ad": "Ayşe Öğretmen", "yukleyen_rol": "teacher",
                "durum": "tamamlandi", "onayli": True, "ilerleme": 100,
                "sonuc": {"sayfa_sayisi": 180, "kelime_sayisi": 45000, "chunk_sayisi": 8,
                          "cikarilan_kelime": 12, "eklenen_kelime": 12, "okuma_parcasi": 4, "uretilen_soru": 15, "bonus_puan": 10},
                "guven_skoru": {"toplam": 92, "seviye": "yuksek", "detay": {"icindekiler": 90, "dil_uygunlugu": 95, "bloom_dagilimi": 88}}, "okuma_seviyesi": "3. Sınıf", "versiyon": 1, "tarih": (simdi - timedelta(days=3)).isoformat(),
            })

            # Demo okuma parçaları
            demo_parcalar = [
                {"baslik": "Ormanın Sırrı", "ozet": "Küçük bir çocuk ormanda kaybolur ve konuşan hayvanlarla arkadaş olur. Birlikte evin yolunu bulurlar.", "tema": "Doğa ve Evren", "metin_kesit": "Ağaçların arasından süzülen güneş ışığı, ormanın derinliklerini aydınlatıyordu. Küçük Ali ilk kez bu kadar içerilere gelmişti. Bir sincap daldan dala atlayarak ona yol gösteriyordu sanki..."},
                {"baslik": "Dürüst Çocuk", "ozet": "Pazarda para bulan bir çocuğun dürüstlük hikâyesi. Parayı sahibine teslim etmesi ve ödüllendirilmesi.", "tema": "Erdemler", "metin_kesit": "Elif pazarda yerde parlayan bir şey gördü. Eğilip baktığında bunun bir cüzdan olduğunu anladı. İçinde epey para vardı. 'Bunu sahibine vermem lazım' diye düşündü..."},
                {"baslik": "Göçmen Kuşlar", "ozet": "Leyleklerin göç yolculuğunu anlatan bilgilendirici metin. Göçün nedenleri ve kuşların yol bulma yetenekleri.", "tema": "Doğa ve Evren", "metin_kesit": "Her sonbaharda leylekler uzun bir yolculuğa çıkar. Binlerce kilometre uçarak sıcak ülkelere göç ederler. Pusula gibi bir iç duyguları sayesinde yollarını hiç şaşırmazlar..."},
                {"baslik": "Takım Çalışması", "ozet": "Sınıftaki öğrencilerin birlikte proje hazırlama hikâyesi. İşbirliği ve paylaşma temaları.", "tema": "Çocuk Dünyası", "metin_kesit": "Öğretmen sınıfa bir proje verdi: 'Hayalinizdeki şehri tasarlayın.' Herkes tek başına yapmak istedi ama çok zordu. Sonunda birlikte çalışmaya karar verdiler..."},
            ]
            for j, p in enumerate(demo_parcalar):
                await db.ai_okuma_parcalari.insert_one({
                    "id": str(uuid.uuid4()), "yukleme_id": demo_yuk_id, "kitap_adi": "Türkçe 3 Ders Kitabı (Demo)",
                    "sinif": 3, "bolum": j+1, **p, "kelime_sayisi": len(p["metin_kesit"].split()), "tarih": simdi.isoformat(),
                })

            # Demo sorular
            demo_sorular = [
                {"soru": "Ali ormanda kime rastladı?", "secenekler": ["Bir sincap", "Bir ayı", "Bir balık", "Bir kuş"], "dogru_cevap": 0, "taksonomi": "bilgi", "bolum": 1},
                {"soru": "Ormandaki hayvanlar Ali'ye nasıl yardım etti?", "secenekler": ["Yemek verdiler", "Yol gösterdiler", "Şarkı söylediler", "Uyuttular"], "dogru_cevap": 1, "taksonomi": "kavrama", "bolum": 1},
                {"soru": "Elif cüzdanı neden sahibine verdi?", "secenekler": ["Korktuğu için", "Dürüst olduğu için", "Paraya ihtiyacı olmadığı için", "Annesi gördüğü için"], "dogru_cevap": 1, "taksonomi": "analiz", "bolum": 2},
                {"soru": "Sen Elif'in yerinde olsaydın ne yapardın?", "secenekler": ["Sahibine verirdim", "Saklar bir şey alırdım", "Polise götürürdüm", "Bilmiyorum"], "dogru_cevap": 0, "taksonomi": "degerlendirme", "bolum": 2},
                {"soru": "Leylekler neden göç eder?", "secenekler": ["Sıcak ülkelere gitmek için", "Arkadaş bulmak için", "Yeni yuva yapmak için", "Uçmayı öğrenmek için"], "dogru_cevap": 0, "taksonomi": "bilgi", "bolum": 3},
                {"soru": "Kuşların yol bulma yeteneğine ne ad verilir?", "secenekler": ["GPS", "İç pusula / içgüdü", "Harita okuma", "Rüzgar takibi"], "dogru_cevap": 1, "taksonomi": "kavrama", "bolum": 3},
                {"soru": "Göç eden kuşlar ile göç etmeyen kuşları karşılaştırınız.", "secenekler": ["Göçmenler daha büyük", "Göçmenler soğuğa dayanamaz", "Göçmenler daha hızlı", "Fark yok"], "dogru_cevap": 1, "taksonomi": "analiz", "bolum": 3},
                {"soru": "Öğrenciler neden birlikte çalışmaya karar verdi?", "secenekler": ["Öğretmen zorladı", "Tek başlarına yapamadılar", "Canları sıkıldı", "Ödül kazanmak için"], "dogru_cevap": 1, "taksonomi": "kavrama", "bolum": 4},
                {"soru": "Takım çalışması neden önemlidir? Kendi hayatından örnek ver.", "secenekler": ["Daha hızlı biter", "Herkes bir şey öğrenir", "Daha eğlenceli olur", "Hepsi doğru"], "dogru_cevap": 3, "taksonomi": "sentez", "bolum": 4},
                {"soru": "Hikâyedeki şehir tasarımı projesinde sen olsan ne eklerdin?", "secenekler": ["Park", "Kütüphane", "Hayvanat bahçesi", "Hepsi"], "dogru_cevap": 3, "taksonomi": "yaratma", "bolum": 4},
            ]
            for s in demo_sorular:
                await db.ai_uretilen_sorular.insert_one({
                    "id": str(uuid.uuid4()), "yukleme_id": demo_yuk_id, "kitap_adi": "Türkçe 3 Ders Kitabı (Demo)",
                    "sinif": 3, **s, "tarih": simdi.isoformat(),
                })

            # Öğretmene AI puan ver
            await db.ai_egitim_puanlari.insert_one({
                "id": str(uuid.uuid4()), "kullanici_id": ogretmen_id,
                "eylem": "dosya_yukle", "dosya_adi": "turkce_3_ders_kitabi.pdf", "sinif": 3, "puan": 30, "tarih": simdi.isoformat(),
            })

        # ── Dalga 2 Demo: Kelime Evrimi (Spaced Repetition) ──
        kelime_tekrar_var = await db.kelime_tekrar.find_one({})
        if not kelime_tekrar_var:
            for ogr in demo_ogrenciler[:3]:
                oid = ogr["id"]
                sinif = ogr.get("sinif", 3)
                demo_tekrar_kelimeler = [
                    {"kelime": "macera", "anlam": "Tehlikeli ve heyecan verici olay", "ornek_cumle": "Çocuklar ormanda büyük bir macera yaşadı.", "kutu": 3, "dogru": 4, "tekrar": 5, "gun_sonra": 7},
                    {"kelime": "keşif", "anlam": "Bilinmeyen bir şeyi ilk kez bulma", "ornek_cumle": "Bilim insanı yeni bir keşif yaptı.", "kutu": 2, "dogru": 2, "tekrar": 3, "gun_sonra": 3},
                    {"kelime": "pusula", "anlam": "Yön bulmaya yarayan araç", "ornek_cumle": "Kaşif pusulasıyla yolunu buldu.", "kutu": 1, "dogru": 0, "tekrar": 1, "gun_sonra": 0},
                    {"kelime": "cesaret", "anlam": "Korkmadan hareket edebilme gücü", "ornek_cumle": "Küçük kız büyük cesaret gösterdi.", "kutu": 4, "dogru": 6, "tekrar": 7, "gun_sonra": 21},
                    {"kelime": "merak", "anlam": "Bir şeyi bilmek isteme duygusu", "ornek_cumle": "Merak eden çocuk her şeyi sorar.", "kutu": 5, "dogru": 8, "tekrar": 8, "gun_sonra": 45},
                    {"kelime": "sabır", "anlam": "Bekleyebilme ve dayanma gücü", "ornek_cumle": "Bahçıvan sabırla çiçeklerin büyümesini bekledi.", "kutu": 1, "dogru": 1, "tekrar": 3, "gun_sonra": 0},
                    {"kelime": "göç", "anlam": "Bir yerden başka bir yere toplu taşınma", "ornek_cumle": "Kuşlar kışın sıcak ülkelere göç eder.", "kutu": 2, "dogru": 3, "tekrar": 4, "gun_sonra": 1},
                    {"kelime": "dürüstlük", "anlam": "Doğruyu söyleme, hile yapmama", "ornek_cumle": "Dürüstlük en değerli erdemlerden biridir.", "kutu": 3, "dogru": 5, "tekrar": 6, "gun_sonra": 5},
                ]
                for kt in demo_tekrar_kelimeler:
                    await db.kelime_tekrar.insert_one({
                        "id": str(uuid.uuid4()),
                        "ogrenci_id": oid,
                        "kelime": kt["kelime"],
                        "anlam": kt["anlam"],
                        "ornek_cumle": kt["ornek_cumle"],
                        "sinif": sinif,
                        "kutu": kt["kutu"],
                        "tekrar_sayisi": kt["tekrar"],
                        "dogru_sayisi": kt["dogru"],
                        "son_gosterim": (simdi - timedelta(days=max(1, kt["gun_sonra"]))).isoformat(),
                        "sonraki_gosterim": (simdi + timedelta(days=kt["gun_sonra"])).isoformat() if kt["gun_sonra"] > 0 else simdi.isoformat(),
                        "tarih": (simdi - timedelta(days=14)).isoformat(),
                    })
            logging.info("  ✅ Kelime Evrimi demo verileri oluşturuldu (8 kelime × 3 öğrenci)")

        # ── Dalga 2 Demo: Socratic Reading logları ──
        socratic_var = await db.ai_socratic_log.find_one({})
        if not socratic_var:
            demo_socratic = [
                {"kitap": "Ormanın Sırrı", "soru": "Ali ormanda kaybolduğunda ne hissetti sence?", "bloom": "analiz", "gun_once": 2},
                {"kitap": "Ormanın Sırrı", "soru": "Sen Ali'nin yerinde olsaydın ne yapardın?", "bloom": "degerlendirme", "gun_once": 2},
                {"kitap": "Dürüst Çocuk", "soru": "Elif cüzdanı sahibine verdi. Bu doğru bir karar mıydı?", "bloom": "degerlendirme", "gun_once": 1},
                {"kitap": "Göçmen Kuşlar", "soru": "Kuşlar nasıl yol buluyor olabilir?", "bloom": "analiz", "gun_once": 1},
                {"kitap": "Takım Çalışması", "soru": "Tek başına mı yoksa takımla mı çalışmak daha iyi? Neden?", "bloom": "sentez", "gun_once": 0},
            ]
            for ogr in demo_ogrenciler[:2]:
                for s in demo_socratic:
                    await db.ai_socratic_log.insert_one({
                        "id": str(uuid.uuid4()),
                        "ogrenci_id": ogr["id"],
                        "kitap_adi": s["kitap"],
                        "bolum": "Bölüm 1",
                        "soru": s["soru"],
                        "bloom": s["bloom"],
                        "cevap": "Demo cevap — öğrenci düşüncesini yazdı.",
                        "puan": random.randint(3, 5),
                        "tarih": (simdi - timedelta(days=s["gun_once"])).isoformat(),
                    })
            logging.info("  ✅ Socratic Reading demo logları oluşturuldu")

        # ── Dalga 3 Demo: Speech AI logları ──
        speech_var = await db.speech_logs.find_one({})
        if not speech_var:
            demo_speech = [
                {"metin_id": "s3_1", "baslik": "Ormanda Bir Gün", "metin": SPEECH_OKUMA_METİNLERİ[3][0]["metin"], "gun_once": 6, "sure": 38, "wpm": 52, "skor": 72, "telaffuz": 75, "akicilik": 68},
                {"metin_id": "s3_2", "baslik": "Dürüstlük", "metin": SPEECH_OKUMA_METİNLERİ[3][1]["metin"], "gun_once": 5, "sure": 35, "wpm": 58, "skor": 76, "telaffuz": 78, "akicilik": 73},
                {"metin_id": "s3_1", "baslik": "Ormanda Bir Gün", "metin": SPEECH_OKUMA_METİNLERİ[3][0]["metin"], "gun_once": 4, "sure": 33, "wpm": 63, "skor": 80, "telaffuz": 82, "akicilik": 78},
                {"metin_id": "s3_2", "baslik": "Dürüstlük", "metin": SPEECH_OKUMA_METİNLERİ[3][1]["metin"], "gun_once": 3, "sure": 30, "wpm": 68, "skor": 84, "telaffuz": 85, "akicilik": 83},
                {"metin_id": "s3_1", "baslik": "Ormanda Bir Gün", "metin": SPEECH_OKUMA_METİNLERİ[3][0]["metin"], "gun_once": 1, "sure": 28, "wpm": 74, "skor": 88, "telaffuz": 89, "akicilik": 87},
            ]
            for ogr in demo_ogrenciler[:2]:
                sinif_int = 3
                try:
                    sinif_int = int(ogr.get("sinif", 3))
                except:
                    pass
                for s in demo_speech:
                    genel = s["skor"]
                    seviye = "çok iyi" if genel >= 85 else "iyi" if genel >= 70 else "orta"
                    await db.speech_logs.insert_one({
                        "id": str(uuid.uuid4()),
                        "ogrenci_id": ogr["id"],
                        "metin_id": s["metin_id"],
                        "metin_baslik": s["baslik"],
                        "metin": s["metin"],
                        "sinif": sinif_int,
                        "sure_sn": s["sure"],
                        "analiz": {
                            "transkript": s["metin"],
                            "telaffuz_skoru": s["telaffuz"],
                            "akicilik_skoru": s["akicilik"],
                            "wpm": s["wpm"],
                            "norm_wpm": 95,
                            "duraklama_sayisi": random.randint(1, 4),
                            "tonlama_skoru": s["telaffuz"] + 2,
                            "vurgu_skoru": s["akicilik"] + 3,
                            "genel_skor": genel,
                            "seviye": seviye,
                            "guclu_yonler": ["Telaffuz başarılı", "Ritim tutarlı"] if genel >= 75 else ["Kelime tanıma gelişiyor"],
                            "gelisim_alanlari": ["Hız artırılabilir"] if s["wpm"] < 80 else [],
                            "ogretmen_notu": f"Öğrenci {s['wpm']} kelime/dk okuyor. {'Sınıf normuna yaklaşıyor.' if s['wpm'] > 60 else 'Tekrarlı okuma önerilir.'}",
                            "ogrenci_mesaj": "Harika ilerliyorsun! 🌟" if genel >= 80 else "Her gün biraz daha iyileşiyorsun! 💪",
                            "telaffuz_hatalar": [],
                            "mock": True,
                            "whisper_kullanildi": False,
                        },
                        "tarih": (simdi - timedelta(days=s["gun_once"])).isoformat(),
                    })
            logging.info("  ✅ Speech AI demo logları oluşturuldu")

        logging.info("✅ AI demo verileri oluşturuldu: DNA, koçluk, kelimeler, parçalar, sorular, tekrar, socratic, speech")
    else:
        logging.info("ℹ️ AI demo verileri zaten mevcut")

    logging.info("📋 Demo Hesapları:")
    logging.info(f"   🎓 Öğrenci: {demo_student_email} / {DEMO_PASSWORD}")
    logging.info(f"   👩‍🏫 Öğretmen: {demo_teacher_email} / {DEMO_PASSWORD}")
    logging.info(f"   👪 Veli: {demo_parent_email} / {DEMO_PASSWORD}")
    logging.info(f"   🔑 Admin: {admin_email} / {admin_password}")

# ─────────────────────────────────────────────
# MEVCUT MODELLER (değişmeden korunuyor)
# ─────────────────────────────────────────────

# CRM modelleri (Teacher/Student/Course/Ders/Payment + Create/Update + ExportData)
# → modules/crm.py'ye taşındı.
# DashboardStats / WeeklyStats / MonthlyStats → modules/dashboard.py'ye taşındı.

# ─────────────────────────────────────────────
# MEVCUT ROUTE'LAR (değişmeden korunuyor)
# ─────────────────────────────────────────────

# Dashboard & istatistik endpoint'leri (/dashboard, /dashboard/bekleyenler,
# /stats/weekly, /stats/monthly) → modules/dashboard.py'ye taşındı.
from modules.dashboard import router as dashboard_router
api_router.include_router(dashboard_router)

# CRM endpoint'leri (/teachers, /students, /courses, /dersler, /payments, /export)
# → modules/crm.py'ye taşındı (modeller dahil). Aynı yollarla kayıtlı.
from modules.crm import router as crm_router
api_router.include_router(crm_router)

# ─────────────────────────────────────────────
# YEDEKLEME (BACKUP) + GÜNCELLEME (UPDATE CHECK) — ADMIN
# → modules/yedekleme.py'ye taşındı. Endpoint'ler (/admin/backup, /admin/backups,
#   /admin/backups/{id}/download, /admin/backups/{id}/restore, DELETE,
#   /admin/version, /admin/updates/check) aynı yollarla kayıtlı kalır.
# ─────────────────────────────────────────────
from modules.yedekleme import router as yedekleme_router
api_router.include_router(yedekleme_router)


# ─────────────────────────────────────────────
# GİRİŞ ANALİZİ (FAZ 1A)
# ─────────────────────────────────────────────

# Norm tablosu + hız/kur helper'ları → modules/diagnostic.py'ye taşındı.

# ── Tanılama (diagnostic) + PDF rapor → modules/diagnostic.py'ye taşındı.
from modules.diagnostic import router as diagnostic_router
api_router.include_router(diagnostic_router)

# ── Puan Ayarları ──
from core.sistem import VARSAYILAN_PUANLAR, get_puan_ayarlari

# ── Sistem ayarları modülü (/ayarlar/*, /ayarlar/puanlar, /ayarlar/ozellikler, /ayarlar/{tip}). → modules/ayarlar.py
from modules.ayarlar import router as ayarlar_router
api_router.include_router(ayarlar_router)



# Egzersiz puan sistemi (/egzersiz/*) → modules/egzersiz.py'ye taşındı.
from modules.egzersiz import router as egzersiz_router
api_router.include_router(egzersiz_router)

# ── Kitap + Soru Havuzu + Bölüm Bazlı Test → modules/kitap.py'ye taşındı.
from modules.kitap import router as kitap_router
api_router.include_router(kitap_router)

# ── Soru CRUD → modules/sorular.py'ye taşındı.
from modules.sorular import router as sorular_router
api_router.include_router(sorular_router)
# (kitap-bilgi-cek → modules/kitap.py)

# ── Admin bakım/debug modülü (/admin/fix-ids, /admin/gemini-*, /admin/debug-*). → modules/admin_debug.py
from modules.admin_debug import router as admin_debug_router
api_router.include_router(admin_debug_router)





# ─────────────────────────────────────────────
# GELİŞİM ALANI - Tam İş Akışı
# ─────────────────────────────────────────────

# SoruModel → modules/gelisim.py

# Gelişim modelleri (IcerikCreate/IcerikModel/OyCreate/Tamamlama*) → modules/gelisim.py

# ── Öğretmen gelişim içerikleri modülü (/gelisim/*). → modules/gelisim.py
from modules.gelisim import router as gelisim_router
api_router.include_router(gelisim_router)










# ─────────────────────────────────────────────
# OKUMA KAYITLARI (reading_logs) + ÖĞRENCİ PANELİ
# → modules/ogrenci_panel.py'ye taşındı. /reading-logs*, /ogrenci-panel/*
# aynı yollarla kayıtlı.
# ─────────────────────────────────────────────
from modules.ogrenci_panel import router as ogrenci_panel_router
api_router.include_router(ogrenci_panel_router)


# ─────────────────────────────────────────────
# RİSK SKORU HESAPLAMA (Faz 4) → modules/risk.py'ye taşındı.
# /risk-skor/{ogrenci_id} ve /risk-skor/toplu aynı yollar+sırayla kayıtlı.
# ─────────────────────────────────────────────
from modules.risk import router as risk_router
api_router.include_router(risk_router)


# ─────────────────────────────────────────────
# XP + LİG + KUR SİSTEMİ (Faz 3)
# ─────────────────────────────────────────────

# XP/lig/rozet/anket varsayılanları + getter'lar → core/sistem.py'ye taşındı.
from core.sistem import (
    XP_TABLOSU_DEFAULT, LIG_ESIKLERI_DEFAULT, LIG_SIRA,
    OGRETMEN_ROZETLERI_DEFAULT, OGRENCI_ROZETLERI_DEFAULT, ANKET_SORULARI_DEFAULT,
    get_xp_tablosu, get_lig_esikleri, get_ogretmen_rozetleri,
    get_ogrenci_rozetleri, get_anket_sorulari,
)


# ── İlerleme/oyunlaştırma modülü (/xp/*, /kur/*, /rozetler/*, /sezon/*, /puan-tablosu/birlesik). → modules/ilerleme.py
from modules.ilerleme import router as ilerleme_router
api_router.include_router(ilerleme_router)


# _get_toplam_xp → modules/ilerleme.py










# ─────────────────────────────────────────────
# SİSTEM AYARLARI YÖNETİMİ (Admin CRUD)
# ─────────────────────────────────────────────










# ─────────────────────────────────────────────
# ROZET SİSTEMİ (Öğretmen + Öğrenci)
# ─────────────────────────────────────────────










# ─────────────────────────────────────────────
# VELİ DEĞERLENDİRME ANKETİ
# ─────────────────────────────────────────────



# ── Veli anketleri modülü (/anketler/*). → modules/anketler.py
from modules.anketler import router as anketler_router
api_router.include_router(anketler_router)








# ─────────────────────────────────────────────
# KUR ATLAMA KAYDI (rozet için güncelleme)
# ─────────────────────────────────────────────

# kur/atla endpoint'ini güncelle — kur_atlamalari collection'ına da kaydet
_original_kur_atla = None  # placeholder


# ─────────────────────────────────────────────
# AI KOÇLUK + DNA + SORU ÜRETİMİ + HİKAYE
# ─────────────────────────────────────────────

# AI_KOCLUK_SYSTEM_PROMPT → modules/ai_kocluk.py

# AI_SORU/HIKAYE_SYSTEM_PROMPT → modules/ai_uretim.py


# ── AI koçluk, DNA & motivasyon modülü (/ai/dna, /ai/kocluk/*, /ai/motivasyon/*). → modules/ai_kocluk.py
from modules.ai_kocluk import router as ai_kocluk_router
api_router.include_router(ai_kocluk_router)






# ── AI içerik üretimi modülü (/ai/soru-uret, /ai/hikaye*, /ai/materyal/*, /ai/mini-oyun*, /ai/scaffold/*, /ai/post-reading, /ai/icerik-kalite-skoru, /ai/kelime-listesi, /ai/okuma-parcalari). → modules/ai_uretim.py
from modules.ai_uretim import router as ai_uretim_router
api_router.include_router(ai_uretim_router)








# ── KİTAP DERSLERİ — Öğrenci için sınıf/kitap bazlı okuma ──

# ── Kitap dersleri (sınıf bazlı parça/soru havuzu) modülü (/kitap-dersleri/*). → modules/kitap_dersleri.py
from modules.kitap_dersleri import router as kitap_dersleri_router
api_router.include_router(kitap_dersleri_router)








# ── KİTAP İÇERİK EDİTÖRÜ (Admin) ──













# ── AI bilgi tabanı modülü (/ai/bilgi-tabani/*, /ai/sorular, /ai/maliyet-ozet, /ai/demo-yukle). → modules/ai_bilgi_tabani.py
from modules.ai_bilgi_tabani import router as ai_bilgi_tabani_router
api_router.include_router(ai_bilgi_tabani_router)










# ── AI sokratik diyalog modülü (/ai/socratic-soru, /ai/socratic-cevap, /ai/socratic-log). → modules/ai_socratic.py
from modules.ai_socratic import router as ai_socratic_router
api_router.include_router(ai_socratic_router)






# ─────────────────────────────────────────────
# DALGA 2: SOCRATİC READİNG + KELİME EVRİMİ + MİNİ OYUN
# ─────────────────────────────────────────────





# ── KELİME EVRİMİ (SPACED REPETITION) ──

# ── AI kelime evrimi modülü (/ai/kelime-evrimi/*). → modules/ai_kelime.py
from modules.ai_kelime import router as ai_kelime_router
api_router.include_router(ai_kelime_router)






# ── MİNİ OYUN ÜRETİCİ ──





# ─────────────────────────────────────────────
# AI BİLGİ TABANI — PDF/DOCX Yükleme + AI Öğrenme + Puan Sistemi
# ─────────────────────────────────────────────

# AI_EGITIM_PUANLARI + DESTEKLENEN_FORMATLAR → modules/ai_bilgi_tabani.py






# ── YANDEX DISK YARDIMCI FONKSİYONLAR ──────────────────────

































# ─────────────────────────────────────────────
# ÖĞRETMEN HEDEF SİSTEMİ → modules/hedef.py'ye taşındı.
# /hedefler/sablonlar, /hedefler (POST/GET), /hedefler/{id} (DELETE) aynı yollarla.
# ─────────────────────────────────────────────
from modules.hedef import router as hedef_router
api_router.include_router(hedef_router)


# ─────────────────────────────────────────────
# BİLDİRİM SİSTEMİ → modules/bildirim.py'ye taşındı.
# Endpoint'ler (/bildirimler, /bildirimler/okunmamis, .../okundu,
# /bildirimler/tumunu-oku, DELETE, /bildirimler/kontrol) aynı yollarla kayıtlı.
# Paylaşılan semboller server.py'nin başka yerlerinde (startup demo seed,
# diagnostic rapor, görev, mesaj) kullanıldığı için import ediliyor.
# ─────────────────────────────────────────────
from modules.bildirim import (
    router as bildirim_router,
    BILDIRIM_TURLERI,
    bildirim_olustur,
    bildirim_gorev_atandi,
    bildirim_rapor_tamamlandi,
)
api_router.include_router(bildirim_router)

# (kitap havuzu blok B → modules/kitap.py)


# ─────────────────────────────────────────────
# MESAJLAŞMA SİSTEMİ → modules/mesaj.py'ye taşındı.
# /mesajlar, /mesajlar/{id}/okundu, /mesajlar/okunmamis-sayisi aynı yollarla.
# (create_mesaj, bildirim_olustur'u modules.bildirim'den kullanır.)
# ─────────────────────────────────────────────
from modules.mesaj import router as mesaj_router
api_router.include_router(mesaj_router)


# ─────────────────────────────────────────────
# GÖREV ATAMA SİSTEMİ → modules/gorev.py'ye taşındı.
# /gorevler, /gorevler/toplu, /gorevler/{id}/durum, DELETE, /gorevler/istatistik
# aynı yollarla. (create_gorev, bildirim_gorev_atandi'yı modules.bildirim'den kullanır.)
# ─────────────────────────────────────────────
from modules.gorev import router as gorev_router
api_router.include_router(gorev_router)


# ─────────────────────────────────────────────
# DALGA 3: SPEECH AI — SESLİ OKUMA ANALİZİ
# ─────────────────────────────────────────────

# SPEECH_OKUMA_METİNLERİ → modules/ai_speech.py (server import ediyor)

# ── AI konuşma/okuma analizi modülü (/ai/speech/*). → modules/ai_speech.py
from modules.ai_speech import router as ai_speech_router, SPEECH_OKUMA_METİNLERİ
api_router.include_router(ai_speech_router)










# ─────────────────────────────────────────────
# DALGA 4: KİTAP ZEKÂ HARİTASI
# ─────────────────────────────────────────────

# ZEKA_BOYUTLARI → modules/ai_kitap_zeka.py
ZEKA_ETIKETLER = {
    "soyutluk": "Soyutluk",
    "kelime_zorlugu": "Kelime Zorluğu",
    "hayal_gucu": "Hayal Gücü",
    "felsefi_derinlik": "Felsefi Derinlik",
    "aksiyon": "Aksiyon",
    "duygusal_yogunluk": "Duygusal Yoğunluk",
    "hedef_kelime_yogunlugu": "Kelime Yoğunluğu",
}


# ── AI kitap zekası modülü (/ai/kitap-zeka/*, /ai/kitap-zeka-haritasi, /ai/kitap-oyun). → modules/ai_kitap_zeka.py
from modules.ai_kitap_zeka import router as ai_kitap_zeka_router
api_router.include_router(ai_kitap_zeka_router)










# ─────────────────────────────────────────────
# DALGA 3: AI MOTİVASYON MOTORU
# ─────────────────────────────────────────────





# ─────────────────────────────────────────────
# DALGA 3: OKUMA EVRENİ (5 BÖLGE)
# ─────────────────────────────────────────────

# EVREN_BOLGELER → modules/ai_oyunlastirma.py


# ── AI oyunlaştırma & gelişim modülü (/ai/evren/*, /ai/okuma-evreni, /ai/gelisim-simulasyon, /ai/okuma-terapisi). → modules/ai_oyunlastirma.py
from modules.ai_oyunlastirma import router as ai_oyunlastirma_router
api_router.include_router(ai_oyunlastirma_router)






# ─────────────────────────────────────────────
# DALGA 3: OKUMA DİKKAT ANALİZİ
# ─────────────────────────────────────────────

# ── AI dikkat takibi + arkadaş sohbeti modülü (/ai/dikkat/*, /ai/arkadas/*). → modules/ai_dikkat_arkadas.py
from modules.ai_dikkat_arkadas import router as ai_dikkat_arkadas_router
api_router.include_router(ai_dikkat_arkadas_router)






# ─────────────────────────────────────────────
# DALGA 3: OKUMA DİKKAT ANALİZİ
# ─────────────────────────────────────────────





# ─────────────────────────────────────────────
# DALGA 3: AI OKUMA ARKADAŞI (4 KARAKTER)
# ─────────────────────────────────────────────

# AI_ARKADAS_* sabitleri → modules/ai_dikkat_arkadas.py










# ═══════════════════════════════════════════════════════════
# DALGA 4 — SCAFFOLD READING
# ═══════════════════════════════════════════════════════════





# ═══════════════════════════════════════════════════════════
# DALGA 4 — AI MATERYAl ÜRETİCİ
# ═══════════════════════════════════════════════════════════





# ═══════════════════════════════════════════════════════════
# DALGA 4 — ADAPTIVE STORY ENGINE
# ═══════════════════════════════════════════════════════════






# ─────────────────────────────────────────────
# POST-READING AI — Kitap Bitirme Sonrası Analiz
# ─────────────────────────────────────────────



# ─────────────────────────────────────────────
# KİTAP ZEKÂ HARİTASI — 7 Boyutlu AI Profil
# ─────────────────────────────────────────────



# ─────────────────────────────────────────────
# KİTABA ÖZGÜ MİNİ OYUN — Kitap içeriğinden üret
# ─────────────────────────────────────────────




# ─────────────────────────────────────────────
# OKUMA EVRENİ — 5 Bölge Gamification
# ─────────────────────────────────────────────

# OKUMA_EVRENI_BOLGELER → modules/ai_oyunlastirma.py



# ─────────────────────────────────────────────
# AI MOTİVASYON MOTORU — Mikro Hedef + Streak Koruma
# ─────────────────────────────────────────────



# ─────────────────────────────────────────────

# ─────────────────────────────────────────────
# AI GELİŞİM SİMÜLASYONU
# ─────────────────────────────────────────────



# ─────────────────────────────────────────────
# AI OKUMA TERAPİSİ — Erken Tespit
# ─────────────────────────────────────────────



# ─────────────────────────────────────────────
# HİBRİT İÇERİK ONAY — AI Skor Sistemi
# ─────────────────────────────────────────────



# ─────────────────────────────────────────────
# TÜRKİYE OKUMA HARİTASI (Anonim, KVKK uyumlu)
# ─────────────────────────────────────────────

# ── Kullanıcı + il/harita istatistik modülü (/kullanici/il-guncelle, /istatistik/turkiye-harita). → modules/kullanici.py
from modules.kullanici import router as kullanici_router
api_router.include_router(kullanici_router)





# ─────────────────────────────────────────────
# ETKİ İSTATİSTİKLERİ
# ─────────────────────────────────────────────





# ─────────────────────────────────────────────
# ÖZELLİK YÖNETİMİ — Admin Panel Feature Flags
# ─────────────────────────────────────────────

# Özellik (feature-flag) altyapısı → core/sistem.py


# APP SETUP
# ─────────────────────────────────────────────

# ★ CORS middleware yukarıda (app oluşturulduktan hemen sonra) eklendi
# Router'ı burada dahil ediyoruz
app.include_router(api_router)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()


# ─────────────────────────────────────────────
# PEER REVIEW ROZET SİSTEMİ
# ─────────────────────────────────────────────



# ─────────────────────────────────────────────
# GLOBAL KELİME HARİTASI
# ─────────────────────────────────────────────

@api_router.get("/istatistik/global-kelime-haritasi")
async def global_kelime_haritasi(current_user=Depends(get_current_user)):
    """Türkiye genelinde kelime öğrenme analizi."""
    try:
        # En zor kelimeler - en yüksek yanlış oranına sahip
        pipeline_zor = [
            {"$group": {
                "_id": "$kelime",
                "toplam": {"$sum": 1},
                "yanlis": {"$sum": {"$cond": [{"$eq": ["$dogru", False]}, 1, 0]}},
                "sinif": {"$first": "$sinif"}
            }},
            {"$match": {"toplam": {"$gte": 10}}},
            {"$project": {
                "kelime": "$_id",
                "yanlis_oran": {"$round": [{"$multiply": [{"$divide": ["$yanlis", "$toplam"]}, 100]}, 0]},
                "adet": "$toplam",
                "sinif": 1
            }},
            {"$sort": {"yanlis_oran": -1}},
            {"$limit": 10}
        ]

        # En hızlı öğrenilen - en düşük ortalama öğrenme süresi
        pipeline_hizli = [
            {"$match": {"sure_gun": {"$exists": True, "$gt": 0}}},
            {"$group": {
                "_id": "$kelime",
                "sure_gun": {"$avg": "$sure_gun"},
                "adet": {"$sum": 1},
                "sinif": {"$first": "$sinif"}
            }},
            {"$match": {"adet": {"$gte": 20}}},
            {"$project": {
                "kelime": "$_id",
                "sure_gun": {"$round": ["$sure_gun", 1]},
                "adet": 1, "sinif": 1
            }},
            {"$sort": {"sure_gun": 1}},
            {"$limit": 8}
        ]

        en_zor = await db.kelime_ogrenme.aggregate(pipeline_zor).to_list(10)
        en_hizli = await db.kelime_ogrenme.aggregate(pipeline_hizli).to_list(8)

        # Yazım hataları
        pipeline_yanlis = [
            {"$match": {"yanlis_yazi": {"$exists": True}}},
            {"$group": {
                "_id": {"dogru": "$kelime", "yanlis": "$yanlis_yazi"},
                "adet": {"$sum": 1},
                "sinif": {"$first": "$sinif"}
            }},
            {"$sort": {"adet": -1}},
            {"$limit": 5}
        ]
        yanlislar_raw = await db.kelime_ogrenme.aggregate(pipeline_yanlis).to_list(5)
        yanlislar = [{"yanlis": f"{y['_id']['yanlis']}→{y['_id']['dogru']}", "adet": y["adet"], "sinif": y.get("sinif","?")} for y in yanlislar_raw]

        # Özet
        toplam_kelime = await db.kelime_ogrenme.distinct("kelime")
        toplam_ogrenme = await db.kelime_ogrenme.count_documents({"dogru": True})

        return {
            "en_zor": en_zor if en_zor else [],
            "en_hizli": en_hizli if en_hizli else [],
            "yanlislar": yanlislar if yanlislar else [],
            "ozet": {
                "toplam_kelime": len(toplam_kelime),
                "toplam_ogrenme": toplam_ogrenme,
                "ortalama_sure": 3.4,
                "aktif_il": 52
            }
        }
    except Exception as e:
        logging.error(f"[GLOBAL-KELIME] {e}")
        return {"en_zor": [], "en_hizli": [], "yanlislar": [], "ozet": {}}


# ─────────────────────────────────────────────
# KVKK / VERİ YÖNETİMİ
# ─────────────────────────────────────────────

@api_router.get("/kullanici/veri-indir")
async def veri_indir(current_user=Depends(get_current_user)):
    """KVKK madde 11: Kullanıcının tüm verilerini JSON olarak indir."""
    try:
        user_id = current_user["id"]

        # Okuma kayıtları
        okuma = await db.reading_logs.find({"student_id": user_id}, {"_id": 0}).to_list(1000)
        # XP kayıtları
        xp = await db.xp_logs.find({"kullanici_id": user_id}, {"_id": 0}).to_list(1000)
        # Rozetler
        rozetler = await db.kullanici_rozetler.find({"kullanici_id": user_id}, {"_id": 0}).to_list(100)
        # Mesajlar
        mesajlar = await db.messages.find({"$or": [{"sender_id": user_id}, {"receiver_id": user_id}]}, {"_id": 0}).to_list(500)
        # Kelime bankası
        kelimeler = await db.kelime_ogrenme.find({"kullanici_id": user_id}, {"_id": 0}).to_list(5000)

        veri = {
            "meta": {
                "export_tarihi": datetime.utcnow().isoformat(),
                "kullanici_id": user_id,
                "kvkk_not": "Bu dosya KVKK madde 11 kapsamında üretilmiştir.",
                "platform": "OBA - Okuma Becerileri Akademisi"
            },
            "profil": {
                "ad": current_user.get("name", ""),
                "email": current_user.get("email", ""),
                "rol": current_user.get("role", ""),
                "okul": current_user.get("school", ""),
            },
            "okuma_kayitlari": okuma,
            "xp_gecmisi": xp,
            "rozetler": rozetler,
            "mesajlar_ozet": {"toplam": len(mesajlar)},
            "kelime_bankasi": kelimeler,
        }

        import json
        from fastapi.responses import Response
        json_str = json.dumps(veri, ensure_ascii=False, indent=2, default=str)
        return Response(
            content=json_str,
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename=oba_verilerim.json"}
        )
    except Exception as e:
        logging.error(f"[VERİ-İNDİR] {e}")
        raise HTTPException(status_code=500, detail="Veri hazırlanamadı")


@api_router.delete("/kullanici/hesap-sil")
async def hesap_sil(current_user=Depends(get_current_user)):
    """KVKK madde 11: Kullanıcının tüm verilerini ve hesabını sil."""
    try:
        user_id = current_user["id"]
        # Tüm collection'lardan kullanıcı verilerini sil
        await db.users.delete_one({"id": user_id})
        await db.reading_logs.delete_many({"student_id": user_id})
        await db.xp_logs.delete_many({"kullanici_id": user_id})
        await db.kullanici_rozetler.delete_many({"kullanici_id": user_id})
        await db.messages.delete_many({"$or": [{"sender_id": user_id}, {"receiver_id": user_id}]})
        await db.kelime_ogrenme.delete_many({"kullanici_id": user_id})
        await db.gelisim_tamamlama.delete_many({"kullanici_id": user_id})
        return {"ok": True, "mesaj": "Tüm verileriniz silindi"}
    except Exception as e:
        logging.error(f"[HESAP-SİL] {e}")
        raise HTTPException(status_code=500, detail="Hesap silinemedi")


# ─────────────────────────────────────────────
# SEZONLUK RESET
# ─────────────────────────────────────────────








# ── Ölü route'lar: app.include_router'dan SONRA tanımlı (baseline'da kayıtsız).
#    Davranış birebir korunsun diye taşınmadı; orijinaldeki gibi kayıt-dışıdır.
@api_router.get("/gelisim/peer-rozet")
async def get_peer_rozet(current_user=Depends(get_current_user)):
    """Kullanıcının haftalık oy sayısı ve toplam peer review rozeti."""
    try:
        from datetime import datetime, timedelta
        haftanin_basi = datetime.utcnow() - timedelta(days=datetime.utcnow().weekday())
        haftanin_basi = haftanin_basi.replace(hour=0, minute=0, second=0, microsecond=0)

        # Haftalık oy sayısı - gelisim_oylar collection'ından
        haftalik = await db.gelisim_oylar.count_documents({
            "kullanici_id": current_user["id"],
            "tarih": {"$gte": haftanin_basi}
        })

        # Toplam oy sayısı (tüm zamanlar)
        toplam = await db.gelisim_oylar.count_documents({
            "kullanici_id": current_user["id"]
        })

        # Rozet hesapla
        rozet = "Bronz Onaycı"
        if toplam >= 50: rozet = "Platin Uzman"
        elif toplam >= 20: rozet = "Altın Moderatör"
        elif toplam >= 5:  rozet = "Gümüş Değerlendirici"

        return {
            "haftalik_oy": haftalik,
            "haftalik_limit": 5,
            "toplam_oy": toplam,
            "rozet": rozet,
            "kalan": max(0, 5 - haftalik),
        }
    except Exception as e:
        logging.error(f"[PEER-ROZET] {e}")
        return {"haftalik_oy": 0, "haftalik_limit": 5, "toplam_oy": 0, "rozet": "Bronz Onaycı", "kalan": 5}

@api_router.get("/gelisim/peer-review-ozet")
async def peer_review_ozet(current_user=Depends(get_current_user)):
    """Admin: Peer review genel özeti ve lider tablosu."""
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403)
    try:
        from datetime import timedelta
        haftanin_basi = datetime.utcnow() - timedelta(days=datetime.utcnow().weekday())
        haftanin_basi = haftanin_basi.replace(hour=0, minute=0, second=0, microsecond=0)

        toplam = await db.gelisim_oylar.count_documents({})
        bu_hafta = await db.gelisim_oylar.count_documents({"tarih": {"$gte": haftanin_basi}})

        # Onay oranı
        onay_count = await db.gelisim_oylar.count_documents({"onay": True})
        onay_orani = round(onay_count / toplam * 100) if toplam > 0 else 0

        # Kullanıcı başına oy sayısı
        pipeline = [
            {"$group": {"_id": "$kullanici_id", "toplam_oy": {"$sum": 1}}},
            {"$sort": {"toplam_oy": -1}},
            {"$limit": 5}
        ]
        lider_ids = await db.gelisim_oylar.aggregate(pipeline).to_list(5)

        liderler = []
        for l in lider_ids:
            u = await db.users.find_one({"id": l["_id"]})
            if u:
                t = l["toplam_oy"]
                rozet = "🥉 Bronz Onaycı"
                if t >= 50: rozet = "💎 Platin Uzman"
                elif t >= 20: rozet = "🥇 Altın Moderatör"
                elif t >= 5:  rozet = "🥈 Gümüş Değerlendirici"
                liderler.append({"ad": u.get("name",""), "toplam_oy": t, "rozet": rozet, "okul": u.get("school","")})

        aktif = await db.gelisim_oylar.distinct("kullanici_id", {"tarih": {"$gte": haftanin_basi}})

        return {
            "ozet": {"toplam_oy": toplam, "bu_hafta": bu_hafta, "aktif_moderator": len(aktif), "onay_orani": onay_orani},
            "liderler": liderler,
            "rozet_dagilim": [
                {"rozet": "💎 Platin Uzman", "min": 50, "sayi": 0, "renk": "from-blue-400 to-cyan-300"},
                {"rozet": "🥇 Altın Moderatör", "min": 20, "sayi": 0, "renk": "from-yellow-500 to-amber-400"},
                {"rozet": "🥈 Gümüş Değerlendirici", "min": 5, "sayi": 0, "renk": "from-gray-400 to-gray-300"},
                {"rozet": "🥉 Bronz Onaycı", "min": 0, "sayi": 0, "renk": "from-amber-700 to-amber-500"},
            ],
            "haftalik_trend": [0]*7
        }
    except Exception as e:
        logging.error(f"[PEER-REVIEW-OZET] {e}")
        return {"ozet": {}, "liderler": [], "rozet_dagilim": [], "haftalik_trend": [0]*7}


# ── Ölü route'lar (orijinalde mount sonrası): /sezon/* — kayıt-dışı korundu.
@api_router.get("/sezon/bilgi")
async def sezon_bilgi(current_user=Depends(get_current_user)):
    """Mevcut sezon bilgisi."""
    try:
        sezon = await db.sezon_meta.find_one({}, {"_id": 0})
        if not sezon:
            katilimci = await db.users.count_documents({})
            sezon = {"sezon_no": 1, "baslangic": datetime.utcnow().isoformat(), "katilimci": katilimci}
        return sezon
    except Exception as e:
        return {"sezon_no": "—", "katilimci": 0}

@api_router.post("/sezon/reset")
async def sezon_reset(current_user=Depends(get_current_user)):
    """Admin: Sezon sıfırlama - XP sıfırla, rozetleri koru."""
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Sadece admin yapabilir")
    try:
        # Tüm kullanıcıların XP ve lig puanını sıfırla
        await db.users.update_many({}, {"$set": {"xp": 0, "lig": "bronz"}})
        # XP loglarını arşivle
        sezon_no = (await db.sezon_meta.find_one({}) or {}).get("sezon_no", 1)
        await db.xp_logs_arsiv.insert_many(
            [{"sezon": sezon_no, **log} async for log in db.xp_logs.find({})]
        )
        await db.xp_logs.delete_many({})
        # Sezon numarasını artır
        await db.sezon_meta.update_one(
            {}, {"$inc": {"sezon_no": 1}, "$set": {"baslangic": datetime.utcnow().isoformat()}},
            upsert=True
        )
        return {"ok": True, "mesaj": f"Sezon {sezon_no} tamamlandı, yeni sezon başladı"}
    except Exception as e:
        logging.error(f"[SEZON-RESET] {e}")
        raise HTTPException(status_code=500, detail="Sezon sıfırlanamadı")
