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

@api_router.get("/ayarlar/puanlar")
async def get_puanlar(current_user=Depends(get_current_user)):
    return await get_puan_ayarlari()

@api_router.put("/ayarlar/puanlar")
async def update_puanlar(data: dict = Body(...), current_user=Depends(require_role(UserRole.ADMIN))):
    await db.sistem_ayarlari.update_one(
        {"tip": "puan_ayarlari"},
        {"$set": {"tip": "puan_ayarlari", "puanlar": data}},
        upsert=True
    )
    return {"message": "Puan ayarları güncellendi", "puanlar": data}


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

# ── Migration / Debug Endpoint ──
@api_router.post("/admin/fix-ids")
async def fix_missing_ids(current_user=Depends(require_role(UserRole.ADMIN))):
    """Eksik id alanlarını düzelt"""
    fixed = 0
    # analiz_metinler
    async for doc in db.analiz_metinler.find({"id": {"$exists": False}}):
        new_id = str(uuid.uuid4())
        await db.analiz_metinler.update_one({"_id": doc["_id"]}, {"$set": {"id": new_id}})
        fixed += 1
    # analiz_metinler - durum alanı yoksa ekle
    await db.analiz_metinler.update_many({"durum": {"$exists": False}}, {"$set": {"durum": "havuzda"}})
    # diagnostic_oturumlar
    async for doc in db.diagnostic_oturumlar.find({"id": {"$exists": False}}):
        await db.diagnostic_oturumlar.update_one({"_id": doc["_id"]}, {"$set": {"id": str(uuid.uuid4())}})
    return {"fixed": fixed, "message": "ID düzeltme tamamlandı"}

@api_router.get("/admin/gemini-test")
async def gemini_test(current_user=Depends(require_role(UserRole.ADMIN))):
    """Gemini API bağlantısını test et — sadece admin."""
    key = GEMINI_API_KEY
    if not key:
        return {"durum": "HATA", "sebep": "GEMINI_API_KEY environment variable tanımlı değil", "key_uzunluk": 0}
    try:
        yanit = await _gemini_call("Merhaba! Sadece 'Gemini çalışıyor' yaz.", max_tokens=50)
        return {"durum": "OK", "yanit": yanit, "key_uzunluk": len(key), "model": AI_MODEL}
    except Exception as e:
        return {"durum": "HATA", "sebep": str(e), "key_uzunluk": len(key), "model": AI_MODEL}

@api_router.get("/admin/gemini-modeller")
async def gemini_modeller():
    """Kullanılabilir Gemini modellerini listele — geçici public."""
    key = GEMINI_API_KEY
    if not key:
        return {"hata": "API key yok"}
    try:
        async with httpx.AsyncClient(timeout=15.0) as c:
            r = await c.get(f"https://generativelanguage.googleapis.com/v1beta/models?key={key}")
            data = r.json()
        modeller = []
        for m in data.get("models", []):
            if "generateContent" in m.get("supportedGenerationMethods", []):
                modeller.append(m.get("name", "").replace("models/", ""))
        return {"modeller": modeller, "toplam": len(modeller)}
    except Exception as e:
        return {"hata": str(e)}

@api_router.get("/admin/debug-metinler")
async def debug_metinler(current_user=Depends(require_role(UserRole.ADMIN))):
    """Tüm metinleri ham haliyle göster"""
    items = await db.analiz_metinler.find().to_list(length=None)
    result = []
    for item in items:
        item.pop("_id", None)
        result.append({"id": item.get("id","EKSİK"), "baslik": item.get("baslik","?"), "durum": item.get("durum","?")})
    return result

@api_router.get("/admin/debug-ogrenciler")
async def debug_ogrenciler(current_user=Depends(require_role(UserRole.ADMIN))):
    items = await db.students.find().to_list(length=None)
    result = []
    for item in items:
        item.pop("_id", None)
        result.append({"id": item.get("id","EKSİK"), "ad": item.get("ad","?"), "soyad": item.get("soyad","?")})
    return result

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


# XP kazan
@api_router.post("/xp/kazan")
async def xp_kazan(payload: dict, current_user=Depends(get_current_user)):
    ogrenci_id = current_user.get("linked_id") or current_user.get("id")
    eylem = payload.get("eylem", "")
    xp = (await get_xp_tablosu()).get(eylem, 0)
    if xp == 0:
        return {"xp": 0, "mesaj": "Bilinmeyen eylem"}

    log = {
        "id": str(uuid.uuid4()),
        "ogrenci_id": ogrenci_id,
        "eylem": eylem,
        "xp": xp,
        "tarih": datetime.utcnow().isoformat(),
    }
    await db.xp_logs.insert_one(log)

    # Toplam XP güncelle
    await db.students.update_one({"id": ogrenci_id}, {"$inc": {"toplam_xp": xp}})

    return {"xp": xp, "toplam": await _get_toplam_xp(ogrenci_id)}


async def _get_toplam_xp(ogrenci_id):
    student = await db.students.find_one({"id": ogrenci_id})
    return student.get("toplam_xp", 0) if student else 0


# XP durumu
@api_router.get("/xp/durum/{ogrenci_id}")
async def xp_durum(ogrenci_id: str, current_user=Depends(get_current_user)):
    toplam = await _get_toplam_xp(ogrenci_id)
    # Lig hesapla
    lig = "bronz"
    for l in reversed(LIG_SIRA):
        if toplam >= (await get_lig_esikleri()).get(l, 0):
            lig = l
            break
    # Sonraki lig
    idx = LIG_SIRA.index(lig)
    sonraki_lig = LIG_SIRA[idx + 1] if idx < len(LIG_SIRA) - 1 else None
    sonraki_esik = (await get_lig_esikleri()).get(sonraki_lig, 0) if sonraki_lig else 0
    kalan = max(0, sonraki_esik - toplam)

    # Son XP kayıtları
    son_xp = await db.xp_logs.find({"ogrenci_id": ogrenci_id}).sort("tarih", -1).to_list(length=10)
    for x in son_xp:
        x.pop("_id", None)

    return {
        "toplam_xp": toplam,
        "lig": lig,
        "lig_label": {"bronz": "🥉 Bronz", "gumus": "🥈 Gümüş", "altin": "🥇 Altın", "elmas": "💎 Elmas"}.get(lig, lig),
        "sonraki_lig": sonraki_lig,
        "sonraki_esik": sonraki_esik,
        "kalan_xp": kalan,
        "son_xp": son_xp,
    }


# Lig sıralaması (anonim)
@api_router.get("/xp/lig-siralama")
async def lig_siralama(current_user=Depends(get_current_user)):
    ogrenci_id = current_user.get("linked_id") or current_user.get("id")
    students = await db.students.find().to_list(length=None)
    siralama = sorted(students, key=lambda s: s.get("toplam_xp", 0), reverse=True)

    tablo = []
    benim_siram = None
    for i, s in enumerate(siralama):
        sira = i + 1
        xp = s.get("toplam_xp", 0)
        lig = "bronz"
        for l in reversed(LIG_SIRA):
            if xp >= (await get_lig_esikleri()).get(l, 0):
                lig = l
                break
        ben = s.get("id") == ogrenci_id
        if ben:
            benim_siram = sira
        tablo.append({
            "sira": sira,
            "xp": xp,
            "lig": lig,
            "lig_label": {"bronz": "🥉", "gumus": "🥈", "altin": "🥇", "elmas": "💎"}.get(lig, ""),
            "ben": ben,
            "ad": "Sen 🌟" if ben else f"Öğrenci #{sira}",
        })

    return {"siralama": tablo[:30], "benim_siram": benim_siram or len(tablo) + 1, "toplam": len(siralama)}


# Kur atlama kontrolü
@api_router.get("/kur/kontrol/{ogrenci_id}")
async def kur_kontrol(ogrenci_id: str, current_user=Depends(get_current_user)):
    # Kriterleri kontrol et
    gorevler = await db.gorevler.find({"hedef_id": ogrenci_id, "durum": "tamamlandi"}).to_list(length=None)
    reading_logs = await db.reading_logs.find({"ogrenci_id": ogrenci_id}).to_list(length=None)
    kitaplar = set(l.get("kitap_adi", "") for l in reading_logs if l.get("kitap_adi"))

    # Streak
    from datetime import timedelta
    simdi = datetime.utcnow()
    tarihler = sorted(set(l.get("tarih", "")[:10] for l in reading_logs), reverse=True)
    streak = 0
    for i in range(60):
        gun = (simdi - timedelta(days=i)).strftime("%Y-%m-%d")
        if gun in tarihler:
            streak += 1
        elif i > 0:
            break

    tamamlanan_gorev = len(gorevler)
    kitap_sayisi = len(kitaplar)

    # Anlama yüzdesi (gelişim tamamlamalardan)
    tamamlamalar = await db.gelisim_tamamlama.find({"kullanici_id": ogrenci_id}).to_list(length=None)
    if tamamlamalar:
        toplam_dogru = sum(t.get("dogru_sayisi", 0) for t in tamamlamalar if t.get("test_yapildi"))
        toplam_soru = sum(t.get("toplam_soru", 0) for t in tamamlamalar if t.get("test_yapildi"))
        anlama_yuzdesi = round((toplam_dogru / max(toplam_soru, 1)) * 100)
    else:
        anlama_yuzdesi = 0

    kriterler = {
        "gorev_12": {"gerekli": 12, "mevcut": tamamlanan_gorev, "tamam": tamamlanan_gorev >= 12},
        "anlama_75": {"gerekli": 75, "mevcut": anlama_yuzdesi, "tamam": anlama_yuzdesi >= 75},
        "kitap_4": {"gerekli": 4, "mevcut": kitap_sayisi, "tamam": kitap_sayisi >= 4},
        "streak_10": {"gerekli": 10, "mevcut": streak, "tamam": streak >= 10},
    }

    hepsi_tamam = all(k["tamam"] for k in kriterler.values())

    return {
        "kriterler": kriterler,
        "kur_atlayabilir": hepsi_tamam,
        "mevcut_kur": (await db.students.find_one({"id": ogrenci_id}) or {}).get("kur", ""),
    }


# Kur atla (öğretmen onayı ile)
@api_router.post("/kur/atla")
async def kur_atla(payload: dict, current_user=Depends(get_current_user)):
    role = current_user.get("role", "")
    if role not in ["admin", "coordinator", "teacher"]:
        raise HTTPException(status_code=403, detail="Sadece öğretmen/yönetici kur atlatabilir")

    ogrenci_id = payload.get("ogrenci_id")
    yeni_kur = payload.get("yeni_kur", "")

    # Mevcut kuru al
    student = await db.students.find_one({"id": ogrenci_id})
    eski_kur = student.get("kur", "") if student else ""

    # Kur güncelle
    await db.students.update_one({"id": ogrenci_id}, {"$set": {"kur": yeni_kur}})

    # Kur atlama kaydı (rozet sistemi için)
    ogretmen_id = current_user.get("linked_id") or current_user.get("id")
    await db.kur_atlamalari.insert_one({
        "id": str(uuid.uuid4()),
        "ogrenci_id": ogrenci_id,
        "ogretmen_id": ogretmen_id,
        "eski_kur": eski_kur,
        "yeni_kur": yeni_kur,
        "tarih": datetime.utcnow().isoformat(),
    })

    return {"ok": True, "yeni_kur": yeni_kur, "eski_kur": eski_kur}


# ─────────────────────────────────────────────
# SİSTEM AYARLARI YÖNETİMİ (Admin CRUD)
# ─────────────────────────────────────────────

# ÖNEMLİ: /ayarlar/ozellikler, /ayarlar/{tip}'den ÖNCE tanımlanmalı
@api_router.get("/ayarlar/ozellikler")
async def get_ozellik_ayarlari_public():
    doc = await db.sistem_ayarlari.find_one({"tip": "ozellik_ayarlari"})
    varsayilan = {f["id"]: {"aktif": True, "roller": {"ogretmen": True, "ogrenci": True, "veli": True}} for f in OZELLIK_TANIMLARI}
    ayarlar = doc.get("degerler", varsayilan) if doc else varsayilan
    for f in OZELLIK_TANIMLARI:
        if f["id"] not in ayarlar:
            ayarlar[f["id"]] = {"aktif": True, "roller": {"ogretmen": True, "ogrenci": True, "veli": True}}
    return {"tanimlar": OZELLIK_TANIMLARI, "ayarlar": ayarlar}

@api_router.get("/ayarlar/{tip}")
async def get_ayar(tip: str, current_user=Depends(get_current_user)):
    doc = await db.sistem_ayarlari.find_one({"tip": tip})
    if doc:
        doc.pop("_id", None)
        return doc
    # Varsayılan değerleri döndür
    defaults = {
        "xp_tablosu": XP_TABLOSU_DEFAULT,
        "lig_esikleri": LIG_ESIKLERI_DEFAULT,
        "ogretmen_rozetleri": OGRETMEN_ROZETLERI_DEFAULT,
        "ogrenci_rozetleri": OGRENCI_ROZETLERI_DEFAULT,
        "anket_sorulari": ANKET_SORULARI_DEFAULT,
    }
    return {"tip": tip, "degerler": defaults.get(tip, {})}


@api_router.put("/ayarlar/{tip}")
async def update_ayar(tip: str, payload: dict, current_user=Depends(get_current_user)):
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Sadece admin ayar değiştirebilir")
    degerler = payload.get("degerler", {})
    await db.sistem_ayarlari.update_one(
        {"tip": tip},
        {"$set": {"tip": tip, "degerler": degerler, "guncelleme_tarihi": datetime.utcnow().isoformat(), "guncelleyen": current_user.get("ad", "")}},
        upsert=True
    )
    return {"ok": True, "tip": tip}


@api_router.get("/ayarlar")
async def get_tum_ayarlar(current_user=Depends(get_current_user)):
    if current_user.get("role") not in ["admin", "coordinator"]:
        raise HTTPException(status_code=403, detail="Yetkisiz")
    ayarlar = await db.sistem_ayarlari.find().to_list(length=None)
    for a in ayarlar:
        a.pop("_id", None)
    return ayarlar


# Birleştirilmiş Puan Tablosu (gelişim + rozet puanları)
@api_router.get("/puan-tablosu/birlesik")
async def get_birlesik_puan_tablosu(current_user=Depends(get_current_user)):
    users = await db.users.find().to_list(length=None)
    tablo = []
    for u in users:
        uid = u["id"]
        gelisim_puan = u.get("puan", 0)

        # Rozet puanları
        rozetler = await db.kazanilan_rozetler.find({"kullanici_id": uid}).to_list(length=None)
        rozet_kodlar = [r["rozet_kodu"] for r in rozetler]

        ogretmen_rozet_list = await get_ogretmen_rozetleri()
        ogrenci_rozet_list = await get_ogrenci_rozetleri()
        tum_rozetler = ogretmen_rozet_list + ogrenci_rozet_list

        rozet_puan = 0
        for rk in rozet_kodlar:
            tanim = next((r for r in tum_rozetler if r["kod"] == rk), None)
            if tanim:
                rozet_puan += tanim.get("puan", tanim.get("xp", 0))

        toplam = gelisim_puan + rozet_puan

        tablo.append({
            "ad": u.get("ad", ""), "soyad": u.get("soyad", ""),
            "role": u.get("role", ""),
            "gelisim_puan": gelisim_puan,
            "rozet_puan": rozet_puan,
            "rozet_sayisi": len(rozet_kodlar),
            "toplam_puan": toplam,
        })
    tablo.sort(key=lambda x: x["toplam_puan"], reverse=True)
    return tablo


# ─────────────────────────────────────────────
# ROZET SİSTEMİ (Öğretmen + Öğrenci)
# ─────────────────────────────────────────────




@api_router.get("/rozetler/tanim")
async def rozet_tanimlari():
    return {"ogretmen": await get_ogretmen_rozetleri(), "ogrenci": await get_ogrenci_rozetleri()}


@api_router.get("/rozetler/{user_id}")
async def get_rozetler(user_id: str, current_user=Depends(get_current_user)):
    rozetler = await db.kazanilan_rozetler.find({"kullanici_id": user_id}).to_list(length=None)
    for r in rozetler:
        r.pop("_id", None)
    return rozetler


@api_router.post("/rozetler/kontrol")
async def rozet_kontrol(current_user=Depends(get_current_user)):
    user_id = current_user["id"]
    role = current_user.get("role", "")
    linked_id = current_user.get("linked_id", "")

    mevcut = await db.kazanilan_rozetler.find({"kullanici_id": user_id}).to_list(length=None)
    mevcut_kodlar = set(r["rozet_kodu"] for r in mevcut)
    yeni_rozetler = []

    if role == "teacher":
        ogretmen_id = linked_id or user_id
        # İçerik sayısı
        icerikler = await db.gelisim_icerik.count_documents({"ekleyen_id": user_id, "durum": "yayinda"})
        # Oylama sayısı
        tum_icerikler = await db.gelisim_icerik.find({"durum": {"$in": ["yayinda", "oylama"]}}).to_list(length=None)
        oy_sayisi = sum(1 for ic in tum_icerikler if user_id in (ic.get("oylar") or {}))
        # Görev atama
        gorevler = await db.gorevler.find({"atayan_id": user_id}).to_list(length=None)
        gorev_sayisi = len(gorevler)
        tamamlanan_gorev = len([g for g in gorevler if g.get("durum") == "tamamlandi"])
        # Öğrenci streak ortalaması
        ogrenciler = await db.students.find({"ogretmen_id": ogretmen_id, "arsivli": {"$ne": True}}).to_list(length=None)
        from datetime import timedelta
        simdi = datetime.utcnow()
        streakler = []
        for s in ogrenciler:
            logs = await db.reading_logs.find({"ogrenci_id": s["id"]}).to_list(length=None)
            tarihler = sorted(set(l.get("tarih", "")[:10] for l in logs), reverse=True)
            st = 0
            for i in range(60):
                gun = (simdi - timedelta(days=i)).strftime("%Y-%m-%d")
                if gun in tarihler: st += 1
                elif i > 0: break
            streakler.append(st)
        ort_streak = sum(streakler) / max(len(streakler), 1)
        # Kur atlama
        kur_sayisi = await db.kur_atlamalari.count_documents({"ogretmen_id": ogretmen_id})
        # Gelişim tamamlama
        gelisim_tam = await db.gelisim_tamamlama.count_documents({"kullanici_id": user_id})
        # Mesaj
        mesajlar = await db.mesajlar.find({"gonderen_id": user_id}).to_list(length=None)
        mesaj_sayisi = len(mesajlar)
        mesaj_roller = set(m.get("alici_rol", "") for m in mesajlar)
        # Egzersiz
        egz_tam = await db.egzersiz_tamamlama.find({"kullanici_id": user_id}).to_list(length=None)
        egz_turler = set(e.get("egzersiz_id", "") for e in egz_tam)
        # Veli anketi
        anketler = await db.veli_anketleri.find({"ogretmen_id": ogretmen_id}).to_list(length=None)
        anket_sayisi = len(anketler)
        anket_ort = 0
        tavsiye_oran = 0
        if anket_sayisi > 0:
            puanlar = []
            tavsiyeler = 0
            for a in anketler:
                yanitlar = a.get("yanitlar", [])
                puan_yanitlar = [y.get("puan", 0) for y in yanitlar if y.get("puan")]
                if puan_yanitlar:
                    puanlar.append(sum(puan_yanitlar) / len(puan_yanitlar))
                if a.get("tavsiye"):
                    tavsiyeler += 1
            anket_ort = sum(puanlar) / max(len(puanlar), 1)
            tavsiye_oran = (tavsiyeler / anket_sayisi) * 100

        # Kontrol
        checks = [
            ("icerik_ilk", icerikler >= 1), ("icerik_5", icerikler >= 5), ("icerik_20", icerikler >= 20), ("icerik_50", icerikler >= 50),
            ("oy_ilk", oy_sayisi >= 1), ("oy_20", oy_sayisi >= 20), ("oy_50", oy_sayisi >= 50),
            ("gorev_ilk", gorev_sayisi >= 1), ("gorev_20", gorev_sayisi >= 20 and tamamlanan_gorev >= 10),
            ("ilham_veren", ort_streak >= 7), ("yildiz_egitimci", ort_streak >= 10),
            ("kur_ilk", kur_sayisi >= 1), ("kur_20", kur_sayisi >= 20), ("kur_30", kur_sayisi >= 30), ("kur_50", kur_sayisi >= 50), ("kur_100", kur_sayisi >= 100),
            ("veli_ilk", anket_sayisi >= 1 and anket_ort >= 4), ("veli_20", anket_sayisi >= 20 and anket_ort >= 4.5),
            ("veli_30", anket_sayisi >= 30 and anket_ort >= 4.5 and tavsiye_oran >= 90),
            ("veli_100", anket_sayisi >= 100 and anket_ort >= 4.8 and tavsiye_oran >= 95),
            ("gelisim_ilk", gelisim_tam >= 1), ("gelisim_10", gelisim_tam >= 10), ("gelisim_uzman", gelisim_tam >= 30),
            ("mesaj_ilk", mesaj_sayisi >= 1), ("kopru_kurucu", "student" in mesaj_roller and "parent" in mesaj_roller),
            ("egz_ilk", len(egz_turler) >= 1), ("egz_tamset", len(egz_turler) >= 14),
        ]
        for kod, kosul in checks:
            if kosul and kod not in mevcut_kodlar:
                doc = {"id": str(uuid.uuid4()), "kullanici_id": user_id, "rozet_kodu": kod, "kazanma_tarihi": datetime.utcnow().isoformat()}
                await db.kazanilan_rozetler.insert_one(doc)
                rozet_bilgi = next((r for r in (await get_ogretmen_rozetleri()) if r["kod"] == kod), None)
                yeni_rozetler.append({**doc, "rozet": rozet_bilgi})

    elif role == "student":
        ogrenci_id = linked_id or user_id
        logs = await db.reading_logs.find({"ogrenci_id": ogrenci_id}).to_list(length=None)
        toplam_dk = sum(l.get("sure_dakika", 0) for l in logs)
        kitaplar = set(l.get("kitap_adi", "") for l in logs if l.get("kitap_adi"))
        from datetime import timedelta
        simdi = datetime.utcnow()
        tarihler = sorted(set(l.get("tarih", "")[:10] for l in logs), reverse=True)
        streak = 0
        for i in range(60):
            gun = (simdi - timedelta(days=i)).strftime("%Y-%m-%d")
            if gun in tarihler: streak += 1
            elif i > 0: break
        gorevler_tam = await db.gorevler.count_documents({"hedef_id": ogrenci_id, "durum": "tamamlandi"})
        egz_tam = await db.egzersiz_tamamlama.find({"kullanici_id": user_id}).to_list(length=None)
        egz_turler = set(e.get("egzersiz_id", "") for e in egz_tam)
        egz_toplam = len(egz_tam)
        agac_sayisi = toplam_dk  # 1 dk = 1 ağaç
        student = await db.students.find_one({"id": ogrenci_id})
        toplam_xp = student.get("toplam_xp", 0) if student else 0

        checks = [
            ("okuma_ilk", len(logs) >= 1), ("okuma_100", toplam_dk >= 100), ("okuma_500", toplam_dk >= 500), ("okuma_2000", toplam_dk >= 2000),
            ("streak_3", streak >= 3), ("streak_7", streak >= 7), ("streak_21", streak >= 21), ("streak_60", streak >= 60),
            ("kitap_1", len(kitaplar) >= 1), ("kitap_5", len(kitaplar) >= 5), ("kitap_15", len(kitaplar) >= 15), ("kitap_30", len(kitaplar) >= 30),
            ("gorev_ilk", gorevler_tam >= 1), ("gorev_10", gorevler_tam >= 10), ("gorev_30", gorevler_tam >= 30), ("gorev_100", gorevler_tam >= 100),
            ("egz_ilk", egz_toplam >= 1), ("egz_20", egz_toplam >= 20), ("egz_14", len(egz_turler) >= 14),
            ("orman_ilk", agac_sayisi >= 1), ("orman_50", agac_sayisi >= 50), ("orman_200", agac_sayisi >= 200),
            ("lig_gumus", toplam_xp >= 200), ("lig_altin", toplam_xp >= 500), ("lig_elmas", toplam_xp >= 1000),
        ]
        for kod, kosul in checks:
            if kosul and kod not in mevcut_kodlar:
                doc = {"id": str(uuid.uuid4()), "kullanici_id": user_id, "rozet_kodu": kod, "kazanma_tarihi": datetime.utcnow().isoformat()}
                await db.kazanilan_rozetler.insert_one(doc)
                rozet_bilgi = next((r for r in (await get_ogrenci_rozetleri()) if r["kod"] == kod), None)
                yeni_rozetler.append({**doc, "rozet": rozet_bilgi})

    return {"yeni_rozetler": yeni_rozetler, "toplam": len(mevcut_kodlar) + len(yeni_rozetler)}


# ─────────────────────────────────────────────
# VELİ DEĞERLENDİRME ANKETİ
# ─────────────────────────────────────────────



@api_router.get("/anketler/sorular")
async def get_anket_sorulari_endpoint():
    return await get_anket_sorulari()


@api_router.post("/anketler")
async def create_anket(payload: dict, current_user=Depends(get_current_user)):
    if current_user.get("role") != "parent":
        raise HTTPException(status_code=403, detail="Sadece veliler anket doldurabilir")

    ogretmen_id = payload.get("ogretmen_id", "")
    ogrenci_id = payload.get("ogrenci_id", "")
    yanitlar = payload.get("yanitlar", [])
    tavsiye = payload.get("tavsiye", None)
    not_text = payload.get("not_text", "")
    donem = payload.get("donem", datetime.utcnow().strftime("%Y-D%m"))

    # Aynı dönem + aynı öğretmen kontrolü
    mevcut = await db.veli_anketleri.find_one({
        "veli_id": current_user["id"], "ogretmen_id": ogretmen_id, "donem": donem
    })
    if mevcut:
        raise HTTPException(status_code=409, detail="Bu dönem için zaten anket doldurdunuz")

    doc = {
        "id": str(uuid.uuid4()),
        "veli_id": current_user["id"],
        "veli_ad": f"{current_user.get('ad', '')} {current_user.get('soyad', '')}".strip(),
        "ogretmen_id": ogretmen_id,
        "ogrenci_id": ogrenci_id,
        "donem": donem,
        "yanitlar": yanitlar,
        "tavsiye": tavsiye,
        "not_text": not_text,
        "tarih": datetime.utcnow().isoformat(),
    }
    await db.veli_anketleri.insert_one(doc)
    return doc


@api_router.get("/anketler/ogretmen/{ogretmen_id}/ozet")
async def anket_ozet(ogretmen_id: str, current_user=Depends(get_current_user)):
    anketler = await db.veli_anketleri.find({"ogretmen_id": ogretmen_id}).to_list(length=None)
    if not anketler:
        return {"anket_sayisi": 0, "ortalama": 0, "tavsiye_oran": 0, "kategoriler": {}, "son_anketler": []}

    puanlar = []
    tavsiyeler = 0
    kategori_toplam = {}
    kategori_sayac = {}

    for a in anketler:
        for y in a.get("yanitlar", []):
            if y.get("puan"):
                puanlar.append(y["puan"])
                kat = y.get("kategori", "genel")
                kategori_toplam[kat] = kategori_toplam.get(kat, 0) + y["puan"]
                kategori_sayac[kat] = kategori_sayac.get(kat, 0) + 1
        if a.get("tavsiye"):
            tavsiyeler += 1

    ortalama = round(sum(puanlar) / max(len(puanlar), 1), 1)
    tavsiye_oran = round((tavsiyeler / len(anketler)) * 100)
    kategoriler = {k: round(kategori_toplam[k] / kategori_sayac[k], 1) for k in kategori_toplam}

    # Öğretmen isimleri görmez
    role = current_user.get("role", "")
    son_anketler = []
    for a in sorted(anketler, key=lambda x: x.get("tarih", ""), reverse=True)[:10]:
        a.pop("_id", None)
        entry = {"donem": a.get("donem"), "tarih": a.get("tarih"), "tavsiye": a.get("tavsiye")}
        puan_yanitlar = [y.get("puan") for y in a.get("yanitlar", []) if y.get("puan")]
        entry["ortalama"] = round(sum(puan_yanitlar) / max(len(puan_yanitlar), 1), 1) if puan_yanitlar else 0
        if role in ["admin", "coordinator"]:
            entry["veli_ad"] = a.get("veli_ad", "")
            entry["not_text"] = a.get("not_text", "")
        son_anketler.append(entry)

    return {
        "anket_sayisi": len(anketler), "ortalama": ortalama, "tavsiye_oran": tavsiye_oran,
        "kategoriler": kategoriler, "son_anketler": son_anketler,
    }


@api_router.get("/anketler/veli/{veli_id}")
async def veli_anketleri(veli_id: str, current_user=Depends(get_current_user)):
    anketler = await db.veli_anketleri.find({"veli_id": veli_id}).to_list(length=None)
    for a in anketler:
        a.pop("_id", None)
    return anketler


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

@api_router.put("/kullanici/il-guncelle")
async def il_guncelle(req: Request, current_user=Depends(get_current_user)):
    """Kullanıcının il bilgisini güncelle (harita için anonim veri)."""
    data = await req.json()
    il = data.get("il", "").strip()
    if not il:
        raise HTTPException(status_code=400, detail="İl boş olamaz")
    await db.users.update_one({"id": current_user["id"]}, {"$set": {"il": il}})
    return {"ok": True, "il": il}



@api_router.get("/istatistik/turkiye-harita")
async def turkiye_okuma_haritasi():
    """İl bazında anonim okuma istatistikleri. Bireysel bilgi içermez."""
    try:
        # Kullanıcıların il bilgisi + okuma verileri — anonim aggregation
        pipeline = [
            {"$match": {"role": "student", "il": {"$exists": True, "$ne": ""}}},
            {"$group": {
                "_id": "$il",
                "okuyucu_sayisi": {"$sum": 1},
                "ogrenci_idler": {"$push": "$id"}
            }}
        ]
        il_gruplari = await db.users.aggregate(pipeline).to_list(length=None)

        iller = []
        toplam_okuyucu = 0
        toplam_kelime_genel = 0
        aktif_il_sayisi = 0

        for grup in il_gruplari:
            il_adi = grup["_id"]
            if not il_adi:
                continue
            ogrenci_idler = grup.get("ogrenci_idler", [])
            okuyucu = len(ogrenci_idler)
            toplam_okuyucu += okuyucu

            # Bu ildeki öğrencilerin toplam kitap tamamlama sayısı
            kitap_sayisi = await db.gelisim_tamamlama.count_documents(
                {"ogrenci_id": {"$in": ogrenci_idler}}
            )

            # Kelime öğrenme sayısı
            kelime_sayisi = await db.kelime_evrimi.count_documents(
                {"ogrenci_id": {"$in": ogrenci_idler}, "kutu": {"$gte": 3}}
            )
            toplam_kelime_genel += kelime_sayisi

            # Streak ortalaması
            streak_data = await db.users.find(
                {"id": {"$in": ogrenci_idler}},
                {"streak": 1}
            ).to_list(length=None)
            avg_streak = round(
                sum(u.get("streak", 0) for u in streak_data) / len(streak_data)
            ) if streak_data else 0

            if kitap_sayisi > 0 or kelime_sayisi > 0:
                aktif_il_sayisi += 1

            iller.append({
                "il": il_adi,
                "okuyucu_sayisi": okuyucu,
                "kitap_sayisi": kitap_sayisi,
                "kelime_sayisi": kelime_sayisi,
                "avg_streak": avg_streak,
            })

        # Sırala: kitap sayısına göre
        iller.sort(key=lambda x: x["kitap_sayisi"], reverse=True)

        return {
            "iller": iller,
            "toplam_okuyucu": toplam_okuyucu,
            "toplam_kelime": toplam_kelime_genel,
            "aktif_il": aktif_il_sayisi,
            "guncelleme": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logging.error(f"[TURKİYE-HARİTA] Hata: {e}")
        return {"iller": [], "toplam_okuyucu": 0, "toplam_kelime": 0, "aktif_il": 0}


# ─────────────────────────────────────────────
# ETKİ İSTATİSTİKLERİ
# ─────────────────────────────────────────────





# ─────────────────────────────────────────────
# ÖZELLİK YÖNETİMİ — Admin Panel Feature Flags
# ─────────────────────────────────────────────

OZELLIK_TANIMLARI = [
    # ── ÖĞRETMEN PANELİ ──
    {"id":"ogretmen_dashboard",     "label":"Öğretmen Dashboard",        "kategori":"ogretmen","ikon":"📊","aciklama":"Risk skorları, öğrenci özeti, genel istatistikler"},
    {"id":"ogretmen_giris_analizi", "label":"Giriş Analizi (Okuma)",      "kategori":"ogretmen","ikon":"🔬","aciklama":"Sesli okuma analizi, WPM, prozodik okuma ve rapor üretimi"},
    {"id":"ogretmen_gelisim",       "label":"Gelişim Alanı",              "kategori":"ogretmen","ikon":"🎓","aciklama":"İçerik ekleme, oylama, materyal yönetimi"},
    {"id":"ogretmen_gorevler",      "label":"Görev Atama",                "kategori":"ogretmen","ikon":"📌","aciklama":"Öğrencilere görev ve ödev atama sistemi"},
    {"id":"ogretmen_mesajlar",      "label":"Mesajlaşma",                 "kategori":"ogretmen","ikon":"✉️","aciklama":"Öğrenci ve velilerle mesajlaşma"},
    {"id":"ogretmen_ai_kocluk",     "label":"AI Koçluk Raporu",           "kategori":"ogretmen","ikon":"🧠","aciklama":"AI ile öğrenci analizi, DNA profili ve kişisel öneriler"},
    {"id":"ogretmen_ai_soru",       "label":"AI Soru Üretici",            "kategori":"ogretmen","ikon":"❓","aciklama":"Metin yükleyerek Bloom taksonomili soru üretme"},
    {"id":"ogretmen_ai_bilgi",      "label":"AI Bilgi Tabanı (PDF/Word)", "kategori":"ogretmen","ikon":"📚","aciklama":"Ders kitabı yükleme ve AI ile kelime/soru çıkarma"},
    {"id":"ogretmen_rozetler",      "label":"Rozet & Başarılar",          "kategori":"ogretmen","ikon":"🏅","aciklama":"Öğretmen rozet ve başarı sistemi"},
    {"id":"ogretmen_hedefler",      "label":"Hedef Sistemi",              "kategori":"ogretmen","ikon":"🎯","aciklama":"Öğretmenin kişisel hedef koyma ve takip sistemi"},
    {"id":"ogretmen_veli_anket",    "label":"Veli Anket Sonuçları",       "kategori":"ogretmen","ikon":"⭐","aciklama":"Velilerin öğretmeni değerlendirdiği anket sonuçları"},
    # ── ÖĞRENCİ PANELİ ──
    {"id":"ogrenci_okuma_kaydi",    "label":"Okuma Kaydı",                "kategori":"ogrenci","ikon":"📖","aciklama":"Ne okudum, okuma süresi ve sayfa takibi"},
    {"id":"ogrenci_gorevler",       "label":"Görevler",                   "kategori":"ogrenci","ikon":"✅","aciklama":"Öğretmenden gelen görevleri görme ve tamamlama"},
    {"id":"ogrenci_gelisim",        "label":"Gelişim Alanı",              "kategori":"ogrenci","ikon":"🎓","aciklama":"İçerik okuma, video izleme, egzersizler"},
    {"id":"ogrenci_egzersizler",    "label":"Göz ve Beyin Egzersizleri",  "kategori":"ogrenci","ikon":"👁️","aciklama":"Odak ve algı geliştirici egzersiz modülleri"},
    {"id":"ogrenci_xp_lig",         "label":"XP & Lig Sistemi",           "kategori":"ogrenci","ikon":"🏆","aciklama":"Puan kazanma, lig yükselme ve sıralama"},
    {"id":"ogrenci_rozetler",       "label":"Rozetler",                   "kategori":"ogrenci","ikon":"🎖️","aciklama":"Öğrenci başarı rozetleri"},
    {"id":"ogrenci_speech_ai",      "label":"Sesli Okuma Analizi (AI)",   "kategori":"ogrenci","ikon":"🎤","aciklama":"Mikrofona sesli okuma ve AI analizi"},
    {"id":"ogrenci_kelime_evrimi",  "label":"Kelime Evrimi (Kartlar)",    "kategori":"ogrenci","ikon":"🔤","aciklama":"Spaced repetition ile kelime öğrenme"},
    {"id":"ogrenci_mini_oyunlar",   "label":"Mini Oyunlar",               "kategori":"ogrenci","ikon":"🎮","aciklama":"Kelime avı, eşleştirme ve boşluk doldurma oyunları"},
    {"id":"ogrenci_scaffold",       "label":"Scaffold Okuma (Seviyeleme)","kategori":"ogrenci","ikon":"📐","aciklama":"DNA'ya göre kolay/orta/orijinal metin seviyeleme"},
    {"id":"ogrenci_materyal",       "label":"AI Materyal Üretici",        "kategori":"ogrenci","ikon":"🛠️","aciklama":"Kitaptan soru seti, kelime listesi, etkinlik üretme"},
    {"id":"ogrenci_hikaye",         "label":"Kişisel Hikaye (AI)",        "kategori":"ogrenci","ikon":"✨","aciklama":"İlgi alanına göre AI tarafından yazılan özel hikaye"},
    {"id":"ogrenci_ai_arkadas",     "label":"AI Okuma Arkadaşı",          "kategori":"ogrenci","ikon":"🤖","aciklama":"4 karakterli AI sohbet asistanı"},
    {"id":"ogrenci_orman",          "label":"Okuma Ormanı",               "kategori":"ogrenci","ikon":"🌲","aciklama":"Okuduğun dakika = Diktiğin ağaç gamification"},
    {"id":"ogrenci_mesajlar",       "label":"Mesajlaşma",                 "kategori":"ogrenci","ikon":"💬","aciklama":"Öğretmenle mesajlaşma"},
    {"id":"ogrenci_siralama",       "label":"Sıralama Tablosu",           "kategori":"ogrenci","ikon":"📈","aciklama":"Anonim okuma dakikası sıralaması"},
    # ── VELİ PANELİ ──
    {"id":"veli_dashboard",         "label":"Veli Dashboard",             "kategori":"veli","ikon":"🏠","aciklama":"Çocuğun okuma istatistikleri ve genel durumu"},
    {"id":"veli_gorev_takip",       "label":"Görev Takibi",               "kategori":"veli","ikon":"📋","aciklama":"Çocuğa atanan görevleri görme"},
    {"id":"veli_okuma_gecmisi",     "label":"Okuma Geçmişi",              "kategori":"veli","ikon":"📅","aciklama":"Haftalık/aylık okuma istatistikleri"},
    {"id":"veli_bildirimler",       "label":"Bildirimler",                "kategori":"veli","ikon":"🔔","aciklama":"Streak uyarısı, rapor bildirimleri"},
    {"id":"veli_anket",             "label":"Öğretmen Değerlendirme",     "kategori":"veli","ikon":"⭐","aciklama":"Öğretmeni değerlendirme anketi"},
    {"id":"veli_mesajlar",          "label":"Mesajlaşma",                 "kategori":"veli","ikon":"💬","aciklama":"Öğretmenle mesajlaşma"},
    {"id":"veli_rapor",             "label":"Giriş Analizi Raporları",    "kategori":"veli","ikon":"📄","aciklama":"Öğretmenin hazırladığı raporları görme"},
]

OZELLIK_VARSAYILAN = {
    f["id"]: {"aktif": True, "roller": {"ogretmen": True, "ogrenci": True, "veli": True}}
    for f in OZELLIK_TANIMLARI
}


async def get_ozellik_ayarlari() -> dict:
    doc = await db.sistem_ayarlari.find_one({"tip": "ozellik_ayarlari"})
    if doc and doc.get("degerler"):
        mevcut = doc["degerler"]
        for f in OZELLIK_TANIMLARI:
            if f["id"] not in mevcut:
                mevcut[f["id"]] = {"aktif": True, "roller": {"ogretmen": True, "ogrenci": True, "veli": True}}
        return mevcut
    return dict(OZELLIK_VARSAYILAN)


@api_router.get("/ayarlar/ozellikler")
async def get_ozellik_ayarlari_endpoint():
    ayarlar = await get_ozellik_ayarlari()
    return {"tanimlar": OZELLIK_TANIMLARI, "ayarlar": ayarlar}


@api_router.put("/ayarlar/ozellikler")
async def update_ozellik_ayarlari(
    payload: dict = Body(...),
    current_user=Depends(require_role(UserRole.ADMIN))
):
    ayarlar = payload.get("ayarlar", {})
    gecerli_idler = {f["id"] for f in OZELLIK_TANIMLARI}
    temiz = {k: v for k, v in ayarlar.items() if k in gecerli_idler}
    await db.sistem_ayarlari.update_one(
        {"tip": "ozellik_ayarlari"},
        {"$set": {
            "tip": "ozellik_ayarlari",
            "degerler": temiz,
            "guncelleme_tarihi": datetime.utcnow().isoformat(),
            "guncelleyen": f"{current_user.get('ad', '')} {current_user.get('soyad', '')}".strip()
        }},
        upsert=True
    )
    return {"ok": True, "guncellenen": len(temiz)}


async def ozellik_aktif_mi(ozellik_id: str, rol: str) -> bool:
    """Verilen özelliğin belirtilen rol için aktif olup olmadığını döner."""
    ayarlar = await get_ozellik_ayarlari()
    ozellik = ayarlar.get(ozellik_id, {"aktif": True, "roller": {}})
    if not ozellik.get("aktif", True):
        return False
    return ozellik.get("roller", {}).get(rol, True)


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