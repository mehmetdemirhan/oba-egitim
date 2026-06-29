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

class SoruModel(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    soru: str
    secenekler: List[str]
    dogru_cevap: int

class IcerikCreate(BaseModel):
    baslik: str
    tur: str  # hizmetici, film, kitap, makale, okuma_parcasi
    aciklama: str = ""
    hedef_kitle: str  # ogretmen, ogrenci, hepsi
    sorular: List[SoruModel] = []
    # Makale alanları
    makale_link: Optional[str] = None
    makale_dosya_turu: Optional[str] = None  # pdf, word, link
    # Kitap ek alanlar
    kitap_yazar: Optional[str] = None
    kitap_isbn: Optional[str] = None
    kitap_yayinevi: Optional[str] = None
    kitap_sayfa: Optional[str] = None
    kitap_yas_grubu: Optional[str] = None
    kitap_link: Optional[str] = None
    kitap_kapak: Optional[str] = None
    kitap_bolum_sayisi: Optional[int] = None
    # Kitap/makale dosya (base64)
    dosya_b64: Optional[str] = None
    dosya_adi: Optional[str] = None
    dosya_turu: Optional[str] = None  # pdf, docx
    # Okuma parçası
    okuma_metni: Optional[str] = None
    okuma_seviye: Optional[str] = None  # kolay, orta, zor
    okuma_sure: Optional[int] = None  # dakika

class IcerikModel(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    baslik: str
    tur: str
    aciklama: str = ""
    hedef_kitle: str
    sorular: List[SoruModel] = []
    makale_link: Optional[str] = None
    makale_dosya_turu: Optional[str] = None
    kitap_yazar: Optional[str] = None
    kitap_isbn: Optional[str] = None
    kitap_yayinevi: Optional[str] = None
    kitap_sayfa: Optional[str] = None
    kitap_yas_grubu: Optional[str] = None
    kitap_link: Optional[str] = None
    kitap_kapak: Optional[str] = None
    kitap_bolum_sayisi: Optional[int] = None
    dosya_b64: Optional[str] = None
    dosya_adi: Optional[str] = None
    dosya_turu: Optional[str] = None
    okuma_metni: Optional[str] = None
    okuma_seviye: Optional[str] = None
    okuma_sure: Optional[int] = None
    ekleyen_id: str = ""
    ekleyen_ad: str = ""
    durum: str = "beklemede"  # beklemede, oylama, yayinda, reddedildi
    oylar: dict = Field(default_factory=dict)
    olusturma_tarihi: datetime = Field(default_factory=datetime.utcnow)
    yayin_tarihi: Optional[datetime] = None

class OyCreate(BaseModel):
    icerik_id: str
    onay: bool
    sebep: str = ""  # Red durumunda zorunlu

class TamamlamaCreate(BaseModel):
    icerik_id: str
    kullanici_id: str
    test_cevaplari: Optional[List[int]] = None

class TamamlamaModel(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    kullanici_id: str
    icerik_id: str
    test_yapildi: bool = False
    dogru_sayisi: int = 0
    toplam_soru: int = 0
    kazanilan_puan: int = 0
    tarih: datetime = Field(default_factory=datetime.utcnow)

# Dosya yükleme endpoint — kitap PDF/Word gelişim içeriğine eklenir
@api_router.post("/gelisim/dosya-yukle")
async def gelisim_dosya_yukle(
    dosya: UploadFile = File(...),
    current_user=Depends(get_current_user)
):
    role = current_user.get("role", "")
    if role not in ["admin", "coordinator", "teacher"]:
        raise HTTPException(status_code=403, detail="Yetkisiz")
    import os, base64
    ext = os.path.splitext(dosya.filename)[1].lower()
    if ext not in [".pdf", ".docx", ".doc", ".txt"]:
        raise HTTPException(status_code=400, detail=f"Desteklenmeyen format: {ext}. Desteklenen: .pdf, .docx, .doc, .txt")
    icerik = await dosya.read()
    if len(icerik) > 20 * 1024 * 1024:  # 20MB
        raise HTTPException(status_code=400, detail="Dosya 20MB'dan büyük olamaz")
    dosya_b64 = base64.b64encode(icerik).decode("utf-8")
    dosya_turu = "pdf" if ext == ".pdf" else "docx"
    return {
        "dosya_b64": dosya_b64,
        "dosya_adi": dosya.filename,
        "dosya_turu": dosya_turu,
        "boyut_kb": len(icerik) // 1024
    }

# İçerik ekleme (admin veya öğretmen)
@api_router.post("/gelisim/icerik")
async def create_icerik(icerik: IcerikCreate, current_user=Depends(get_current_user)):
    role = current_user.get("role", "")
    if role not in ["admin", "coordinator", "teacher"]:
        raise HTTPException(status_code=403, detail="Yetkisiz")
    
    # Admin/Koordinatör eklerse direkt yayında, öğretmen eklerse oylama
    durum = "yayinda" if role in ["admin", "coordinator"] else "oylama"
    
    model = IcerikModel(
        **icerik.dict(),
        ekleyen_id=current_user["id"],
        ekleyen_ad=f"{current_user.get('ad','')} {current_user.get('soyad','')}",
        durum=durum
    )
    data = model.dict()
    data["olusturma_tarihi"] = data["olusturma_tarihi"].isoformat()
    if data.get("yayin_tarihi"):
        data["yayin_tarihi"] = data["yayin_tarihi"].isoformat()

    # "Neden bu kitap?" alanı → +3 puan bonusu
    neden = data.get("neden_bu_icerik", "")
    if neden and len(neden.strip()) >= 20:
        data["neden_bonus"] = True
        try:
            await db.users.update_one({"id": current_user["id"]}, {"$inc": {"toplam_puan": 3}})
        except: pass

    # Test soruları bonusu → her soru +2 puan, max +20
    sorular = data.get("sorular", [])
    soru_bonus = min(len(sorular) * 2, 20)
    if soru_bonus > 0:
        data["soru_bonus"] = soru_bonus
        try:
            await db.users.update_one({"id": current_user["id"]}, {"$inc": {"toplam_puan": soru_bonus}})
        except: pass

    await db.gelisim_icerik.insert_one(data)

    # Kitap türünde içerik eklendiyse kitap havuzuna da kaydet (bölüm bazlı soru için)
    if data.get("tur") == "kitap":
        mevcut = await db.kitap_havuzu.find_one({"baslik": data.get("baslik", ""), "yazar": data.get("kitap_yazar", "")})
        if not mevcut:
            await db.kitap_havuzu.insert_one({
                "id": str(uuid.uuid4()),
                "baslik": data.get("baslik", ""),
                "yazar": data.get("kitap_yazar", ""),
                "yas_grubu": data.get("kitap_yas_grubu", ""),
                "zorluk": "orta",
                "bolum_sayisi": data.get("kitap_bolum_sayisi", 10),
                "kapak_url": data.get("kitap_kapak", ""),
                "ekleyen_id": current_user["id"],
                "ekleyen_ad": f"{current_user.get('ad','')} {current_user.get('soyad','')}",
                "durum": durum,
                "oylar": {},
                "gelisim_icerik_id": data.get("id"),
                "olusturma_tarihi": datetime.utcnow().isoformat(),
            })

    return data

# İçerikleri listele
@api_router.get("/gelisim/icerik")
async def get_icerik_list(current_user=Depends(get_current_user)):
    role = current_user.get("role", "")
    user_id = current_user.get("id", "")
    
    items = await db.gelisim_icerik.find().sort("olusturma_tarihi", -1).to_list(length=None)
    result = []
    for item in items:
        item.pop("_id", None)
        durum = item.get("durum", "")
        hedef = item.get("hedef_kitle", "hepsi")
        
        # Kitap türü ise bölüm bazlı soru sayısını ekle
        if item.get("tur") == "kitap":
            item["_soru_sayisi"] = await db.kitap_sorulari.count_documents({"kitap_id": item["id"]})
        
        # Admin her şeyi görür
        if role in ["admin", "coordinator"]:
            result.append(item)
        elif role == "teacher":
            if item.get("ekleyen_id") == user_id:
                result.append(item)
            elif durum == "oylama":
                result.append(item)
            elif durum == "yayinda" and hedef in ["hepsi", "ogretmen"]:
                result.append(item)
        elif role == "student":
            if durum == "yayinda" and hedef in ["hepsi", "ogrenci"]:
                result.append(item)
    
    return result

# Admin onay/red (beklemede → oylama veya reddedildi)
@api_router.post("/gelisim/icerik/{icerik_id}/admin-karar")
async def admin_karar(icerik_id: str, karar: dict, current_user=Depends(require_role(UserRole.ADMIN, UserRole.COORDINATOR))):
    # direkt=True → oylama atla, direkt yayına al
    onay = karar.get("onay", False)
    direkt = karar.get("direkt", False)
    if not onay:
        yeni_durum = "reddedildi"
    elif direkt:
        yeni_durum = "yayinda"
        icerik = await db.gelisim_icerik.find_one({"id": icerik_id})
        puanlar = await get_puan_ayarlari()
        if icerik and icerik.get("ekleyen_id"):
            await db.users.update_one({"id": icerik["ekleyen_id"]}, {"$inc": {"puan": puanlar.get("icerik_ekleme", 5)}})
    else:
        yeni_durum = "oylama"
    await db.gelisim_icerik.update_one(
        {"id": icerik_id},
        {"$set": {"durum": yeni_durum, **({"yayin_tarihi": datetime.utcnow().isoformat()} if yeni_durum == "yayinda" else {})}}
    )
    return {"durum": yeni_durum}

# Öğretmen oylama
@api_router.post("/gelisim/oy")
async def oy_ver(oy: OyCreate, current_user=Depends(get_current_user)):
    role = current_user.get("role", "")
    if role not in ["admin", "coordinator", "teacher"]:
        raise HTTPException(status_code=403, detail="Sadece öğretmenler oy verebilir")
    
    if not oy.onay and not oy.sebep:
        raise HTTPException(status_code=400, detail="Red için sebep belirtmelisiniz")
    
    icerik = await db.gelisim_icerik.find_one({"id": oy.icerik_id})
    if not icerik:
        raise HTTPException(status_code=404, detail="İçerik bulunamadı")
    if icerik.get("durum") != "oylama":
        raise HTTPException(status_code=400, detail="Bu içerik oylamada değil")
    
    user_id = current_user["id"]
    oylar = icerik.get("oylar", {})
    
    if user_id in oylar:
        raise HTTPException(status_code=400, detail="Zaten oy kullandınız")
    
    # Oyu kaydet
    oylar[user_id] = {"onay": oy.onay, "sebep": oy.sebep}
    await db.gelisim_icerik.update_one({"id": oy.icerik_id}, {"$set": {"oylar": oylar}})
    
    # Oy veren öğretmene puan (dinamik)
    puanlar = await get_puan_ayarlari()
    await db.users.update_one({"id": user_id}, {"$inc": {"puan": puanlar.get("icerik_oylama", 2)}})
    
    # %60 kontrolü
    ogretmenler = await db.users.find({"role": {"$in": ["teacher", "coordinator", "admin"]}}).to_list(length=None)
    toplam_ogretmen = len(ogretmenler)
    onay_sayisi = sum(1 for v in oylar.values() if v.get("onay"))
    oy_sayisi = len(oylar)
    
    yeni_durum = icerik.get("durum")
    
    if toplam_ogretmen > 0:
        onay_orani = onay_sayisi / toplam_ogretmen
        # Herkes oy kullandı veya onay oranı %60 geçti
        if onay_orani >= 0.6:
            yeni_durum = "yayinda"
            await db.gelisim_icerik.update_one(
                {"id": oy.icerik_id},
                {"$set": {"durum": "yayinda", "yayin_tarihi": datetime.utcnow().isoformat()}}
            )
            # İçerik ekleyene bonus puan (dinamik)
            ekleyen_id = icerik.get("ekleyen_id")
            if ekleyen_id:
                await db.users.update_one({"id": ekleyen_id}, {"$inc": {"puan": puanlar.get("icerik_ekleme", 5)}})
        elif oy_sayisi == toplam_ogretmen and onay_orani < 0.6:
            yeni_durum = "reddedildi"
            await db.gelisim_icerik.update_one({"id": oy.icerik_id}, {"$set": {"durum": "reddedildi"}})
    
    return {
        "mesaj": "Oyunuz kaydedildi (+2 puan)",
        "durum": yeni_durum,
        "onay_orani": round(onay_sayisi / max(toplam_ogretmen, 1) * 100),
        "oy_sayisi": oy_sayisi,
        "toplam": toplam_ogretmen
    }

# Tamamlama
@api_router.post("/gelisim/tamamla")
async def tamamla_icerik(data: TamamlamaCreate, current_user=Depends(get_current_user)):
    existing = await db.gelisim_tamamlama.find_one({"kullanici_id": data.kullanici_id, "icerik_id": data.icerik_id})
    if existing:
        raise HTTPException(status_code=400, detail="Bu içerik zaten tamamlandı")
    
    icerik = await db.gelisim_icerik.find_one({"id": data.icerik_id})
    if not icerik:
        raise HTTPException(status_code=404, detail="İçerik bulunamadı")
    
    sorular = icerik.get("sorular", [])
    toplam = len(sorular)
    dogru = 0
    test_yapildi = False
    puan = 1
    
    if data.test_cevaplari and toplam > 0:
        test_yapildi = True
        for i, cevap in enumerate(data.test_cevaplari):
            if i < toplam and cevap == sorular[i].get("dogru_cevap"):
                dogru += 1
        puan = max(1, round((dogru / toplam) * 10))
    
    tamamlama = TamamlamaModel(
        kullanici_id=data.kullanici_id,
        icerik_id=data.icerik_id,
        test_yapildi=test_yapildi,
        dogru_sayisi=dogru,
        toplam_soru=toplam,
        kazanilan_puan=puan
    )
    t_data = tamamlama.dict()
    t_data["tarih"] = t_data["tarih"].isoformat()
    await db.gelisim_tamamlama.insert_one(t_data)
    await db.users.update_one({"id": data.kullanici_id}, {"$inc": {"puan": puan}})
    
    return {"puan": puan, "dogru": dogru, "toplam": toplam, "test_yapildi": test_yapildi}

# Kullanıcının tamamlamaları
@api_router.get("/gelisim/tamamlama/{kullanici_id}")
async def get_tamamlamalar(kullanici_id: str, current_user=Depends(get_current_user)):
    items = await db.gelisim_tamamlama.find({"kullanici_id": kullanici_id}).to_list(length=None)
    for item in items:
        item.pop("_id", None)
    return items

# Puan tablosu
@api_router.get("/gelisim/puan-tablosu")
async def get_puan_tablosu(current_user=Depends(get_current_user)):
    users = await db.users.find().to_list(length=None)
    tablo = []
    for u in users:
        tablo.append({
            "ad": u.get("ad", ""), "soyad": u.get("soyad", ""),
            "role": u.get("role", ""), "puan": u.get("puan", 0)
        })
    tablo.sort(key=lambda x: x["puan"], reverse=True)
    return tablo

# İçerik sil
@api_router.delete("/gelisim/icerik/{icerik_id}")
async def delete_icerik(icerik_id: str, current_user=Depends(require_role(UserRole.ADMIN, UserRole.COORDINATOR))):
    await db.gelisim_icerik.delete_one({"id": icerik_id})
    return {"message": "Silindi"}


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

@api_router.get("/kitap-dersleri/siniflar")
async def kitap_dersleri_siniflar(current_user=Depends(get_current_user)):
    """Parça bulunan sınıf listesini döner."""
    siniflar = await db.ai_okuma_parcalari.distinct("sinif")
    return sorted([s for s in siniflar if s])


@api_router.get("/kitap-dersleri/kitaplar/{sinif}")
async def kitap_dersleri_kitaplar(sinif: int, current_user=Depends(get_current_user)):
    """Belirtilen sınıfa ait kitap listesini döner."""
    kitaplar = await db.ai_okuma_parcalari.distinct("kitap_adi", {"sinif": sinif})
    sonuc = []
    for k in kitaplar:
        parca_sayisi = await db.ai_okuma_parcalari.count_documents({"sinif": sinif, "kitap_adi": k})
        soru_sayisi = await db.ai_uretilen_sorular.count_documents({"sinif": sinif, "kitap_adi": k})
        sonuc.append({"kitap_adi": k, "parca_sayisi": parca_sayisi, "soru_sayisi": soru_sayisi})
    return sonuc


@api_router.get("/kitap-dersleri/parcalar/{sinif}/{kitap_adi}")
async def kitap_dersleri_parcalar(sinif: int, kitap_adi: str, current_user=Depends(get_current_user)):
    """Belirtilen kitabın okuma parçalarını ve sorularını döner."""
    from urllib.parse import unquote
    kitap_adi = unquote(kitap_adi)
    parcalar = await db.ai_okuma_parcalari.find(
        {"sinif": sinif, "kitap_adi": kitap_adi}
    ).sort("bolum", 1).to_list(length=None)
    for p in parcalar:
        p.pop("_id", None)
        # Her parçanın sorularını ekle
        sorular = await db.ai_uretilen_sorular.find(
            {"sinif": sinif, "kitap_adi": kitap_adi, "bolum": p.get("bolum", 0)}
        ).to_list(length=None)
        for s in sorular:
            s.pop("_id", None)
        p["sorular"] = sorular
    return parcalar


@api_router.post("/kitap-dersleri/cevapla")
async def kitap_dersleri_cevapla(payload: dict = Body(...), current_user=Depends(get_current_user)):
    """Öğrencinin soru cevabını kaydet ve XP ver."""
    soru_id = payload.get("soru_id")
    cevap = payload.get("cevap")
    kitap_adi = payload.get("kitap_adi", "")
    sinif = payload.get("sinif", 0)

    soru = await db.ai_uretilen_sorular.find_one({"id": soru_id})
    if not soru:
        raise HTTPException(status_code=404, detail="Soru bulunamadı")

    dogru = soru.get("dogru_cevap") == cevap
    xp = 5 if dogru else 1

    # Cevabı kaydet
    await db.ai_soru_cevaplari.insert_one({
        "id": str(uuid.uuid4()),
        "ogrenci_id": current_user.get("linked_id") or current_user["id"],
        "soru_id": soru_id,
        "kitap_adi": kitap_adi,
        "sinif": sinif,
        "cevap": cevap,
        "dogru": dogru,
        "xp": xp,
        "tarih": datetime.utcnow().isoformat(),
    })

    # XP ver
    if dogru:
        ogrenci_id = current_user.get("linked_id") or current_user["id"]
        await db.students.update_one({"id": ogrenci_id}, {"$inc": {"xp": xp}})
        await db.xp_logs.insert_one({
            "id": str(uuid.uuid4()),
            "ogrenci_id": ogrenci_id,
            "eylem": "kitap_sorusu",
            "xp": xp,
            "aciklama": f"📚 {kitap_adi} — doğru cevap",
            "tarih": datetime.utcnow().isoformat(),
        })

    return {"dogru": dogru, "xp_kazanildi": xp, "dogru_cevap": soru.get("dogru_cevap")}


# ── KİTAP İÇERİK EDİTÖRÜ (Admin) ──

@api_router.put("/kitap-dersleri/parca/{parca_id}")
async def kitap_parca_guncelle(
    parca_id: str,
    payload: dict = Body(...),
    current_user=Depends(require_role(UserRole.ADMIN))
):
    """Okuma parçasını güncelle."""
    guncelle = {}
    for alan in ["baslik", "ozet", "metin_kesit", "tema", "kelime_sayisi"]:
        if alan in payload:
            guncelle[alan] = payload[alan]
    if not guncelle:
        raise HTTPException(status_code=400, detail="Güncellenecek alan yok")
    await db.ai_okuma_parcalari.update_one({"id": parca_id}, {"$set": guncelle})
    return {"ok": True}


@api_router.delete("/kitap-dersleri/parca/{parca_id}")
async def kitap_parca_sil(parca_id: str, current_user=Depends(require_role(UserRole.ADMIN))):
    """Okuma parçasını sil."""
    await db.ai_okuma_parcalari.delete_one({"id": parca_id})
    return {"ok": True}


@api_router.put("/kitap-dersleri/soru/{soru_id}")
async def kitap_soru_guncelle(
    soru_id: str,
    payload: dict = Body(...),
    current_user=Depends(require_role(UserRole.ADMIN))
):
    """Soruyu güncelle."""
    guncelle = {}
    for alan in ["soru", "secenekler", "dogru_cevap", "taksonomi"]:
        if alan in payload:
            guncelle[alan] = payload[alan]
    if not guncelle:
        raise HTTPException(status_code=400, detail="Güncellenecek alan yok")
    await db.ai_uretilen_sorular.update_one({"id": soru_id}, {"$set": guncelle})
    return {"ok": True}


@api_router.delete("/kitap-dersleri/soru/{soru_id}")
async def kitap_soru_sil(soru_id: str, current_user=Depends(require_role(UserRole.ADMIN))):
    """Soruyu sil."""
    await db.ai_uretilen_sorular.delete_one({"id": soru_id})
    return {"ok": True}


@api_router.post("/kitap-dersleri/soru-ekle")
async def kitap_soru_ekle(
    payload: dict = Body(...),
    current_user=Depends(require_role(UserRole.ADMIN))
):
    """Parçaya yeni soru ekle."""
    yeni_soru = {
        "id": str(uuid.uuid4()),
        "yukleme_id": payload.get("yukleme_id", ""),
        "kitap_adi": payload.get("kitap_adi", ""),
        "sinif": payload.get("sinif", 0),
        "bolum": payload.get("bolum", 0),
        "soru": payload.get("soru", ""),
        "secenekler": payload.get("secenekler", []),
        "dogru_cevap": payload.get("dogru_cevap", 0),
        "taksonomi": payload.get("taksonomi", "bilgi"),
        "tarih": datetime.utcnow().isoformat(),
    }
    await db.ai_uretilen_sorular.insert_one(yeni_soru)
    yeni_soru.pop("_id", None)
    return yeni_soru


@api_router.post("/kitap-dersleri/parca-ekle")
async def kitap_parca_ekle(
    payload: dict = Body(...),
    current_user=Depends(require_role(UserRole.ADMIN))
):
    """Kitaba yeni okuma parçası ekle."""
    yeni_parca = {
        "id": str(uuid.uuid4()),
        "yukleme_id": payload.get("yukleme_id", "manuel"),
        "kitap_adi": payload.get("kitap_adi", ""),
        "sinif": payload.get("sinif", 0),
        "bolum": payload.get("bolum", 0),
        "baslik": payload.get("baslik", ""),
        "ozet": payload.get("ozet", ""),
        "metin_kesit": payload.get("metin_kesit", ""),
        "tema": payload.get("tema", ""),
        "kelime_sayisi": payload.get("kelime_sayisi", 0),
        "tarih": datetime.utcnow().isoformat(),
    }
    await db.ai_okuma_parcalari.insert_one(yeni_parca)
    yeni_parca.pop("_id", None)
    return yeni_parca


# ── AI bilgi tabanı modülü (/ai/bilgi-tabani/*, /ai/sorular, /ai/maliyet-ozet, /ai/demo-yukle). → modules/ai_bilgi_tabani.py
from modules.ai_bilgi_tabani import router as ai_bilgi_tabani_router
api_router.include_router(ai_bilgi_tabani_router)






@api_router.post("/kitap-dersleri/havuza-ekle/{parca_id}")
async def kitap_parca_havuza_ekle(parca_id: str, current_user=Depends(get_current_user)):
    """Okuma parçasını gelişim içerik havuzuna ekle."""
    parca = await db.ai_okuma_parcalari.find_one({"id": parca_id})
    if not parca:
        raise HTTPException(status_code=404, detail="Parça bulunamadı")
    mevcut = await db.gelisim_icerikleri.find_one({"kaynak_parca_id": parca_id})
    if mevcut:
        raise HTTPException(status_code=409, detail="Bu parça zaten içerik havuzunda")
    sorular = await db.ai_uretilen_sorular.find(
        {"yukleme_id": parca.get("yukleme_id"), "bolum": parca.get("bolum", 0)}
    ).to_list(length=None)
    soru_listesi = [{"id": str(uuid.uuid4()), "soru": s.get("soru",""), "secenekler": s.get("secenekler",[]), "dogru_cevap": s.get("dogru_cevap",0), "taksonomi": s.get("taksonomi","bilgi")} for s in sorular]
    icerik = {
        "id": str(uuid.uuid4()),
        "baslik": f"{parca.get('kitap_adi','')} — {parca.get('baslik','')}",
        "tur": "okuma_parcasi",
        "aciklama": parca.get("ozet",""),
        "hedef_kitle": "ogrenci",
        "okuma_metni": parca.get("metin_kesit",""),
        "okuma_seviye": "orta",
        "okuma_sure": max(1, len((parca.get("metin_kesit") or "").split()) // 200),
        "sorular": soru_listesi,
        "kaynak": "ai_bilgi_tabani",
        "kaynak_parca_id": parca_id,
        "kaynak_kitap": parca.get("kitap_adi",""),
        "sinif": parca.get("sinif"),
        "tema": parca.get("tema",""),
        "yukleyen_id": current_user["id"],
        "yukleyen_ad": f"{current_user.get('ad','')} {current_user.get('soyad','')}".strip(),
        "durum": "yayinda",
        "onayli": True,
        "oylama_sayisi": 0,
        "olumlu_oy": 0,
        "tarih": datetime.utcnow().isoformat(),
    }
    await db.gelisim_icerikleri.insert_one(icerik)
    icerik.pop("_id", None)
    return {"ok": True, "icerik_id": icerik["id"], "mesaj": "✅ İçerik havuzuna eklendi!"}




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

SPEECH_OKUMA_METİNLERİ = {
    1: [
        {"id": "s1_1", "baslik": "Küçük Kedi", "metin": "Küçük kedi bahçede oynadı. Güneş parlıyordu. Kedi mutluydu.", "kelime_sayisi": 10, "sinif": 1},
        {"id": "s1_2", "baslik": "Renkli Balonlar", "metin": "Ali kırmızı balon aldı. Ayşe sarı balon aldı. İkisi de çok sevindi.", "kelime_sayisi": 12, "sinif": 1},
    ],
    2: [
        {"id": "s2_1", "baslik": "Yağmur", "metin": "Sabah kalktığımda pencereden baktım. Dışarıda yağmur yağıyordu. Annem şemsiyemi hazırladı ve okula gittim.", "kelime_sayisi": 20, "sinif": 2},
        {"id": "s2_2", "baslik": "Kitap Kurdu", "metin": "Her gün en az bir kitap okuyorum. Kitaplar bana yeni dünyalar açıyor. En sevdiğim yer kütüphane.", "kelime_sayisi": 18, "sinif": 2},
    ],
    3: [
        {"id": "s3_1", "baslik": "Ormanda Bir Gün", "metin": "Ormanın içinde yürürken ağaçların arasından süzülen güneş ışığını seyrettim. Kuşlar şakıyor, yapraklar hışırdıyordu. Bu sessizlik içinde kendimi huzurlu hissettim.", "kelime_sayisi": 30, "sinif": 3},
        {"id": "s3_2", "baslik": "Dürüstlük", "metin": "Pazarda yürürken yerde bir cüzdan buldum. İçinde para ve kimlik vardı. Hemen karakola götürdüm. Görevli bana teşekkür etti ve sahibini bulacaklarını söyledi.", "kelime_sayisi": 32, "sinif": 3},
    ],
    4: [
        {"id": "s4_1", "baslik": "Göç Eden Kuşlar", "metin": "Her sonbahar leylekler uzun bir yolculuğa çıkar. Binlerce kilometre uçarak sıcak ülkelere göç ederler. Pusula gibi çalışan içgüdüleri sayesinde yollarını şaşırmazlar. Bu muhteşem yolculuk nesiller boyunca sürmektedir.", "kelime_sayisi": 38, "sinif": 4},
    ],
    5: [
        {"id": "s5_1", "baslik": "Anadolu Medeniyetleri", "metin": "Anadolu, tarihin en eski medeniyetlerine ev sahipliği yapmıştır. Hitit, Frigya, Lidya ve daha pek çok uygarlık bu topraklarda yaşamış, eserler bırakmıştır. Bu zengin miras günümüze kadar ulaşmıştır.", "kelime_sayisi": 35, "sinif": 5},
    ],
}

def _speech_mock_analiz(transkript: str, beklenen_metin: str, sure_sn: float, sinif: int) -> dict:
    """Web Speech API transkriptini beklenen metinle karşılaştırarak analiz üret."""
    import difflib
    import re

    def normalize(s):
        """Noktalama ve büyük/küçük harf normalize et."""
        s = s.lower()
        s = re.sub(r'[.,!?;:"\'-]', '', s)
        return s.split()

    b_kelimeler = normalize(beklenen_metin)
    gercek_transkript = transkript.strip() if transkript else ""

    # Transkript yoksa (kullanıcı hiç okumadı) — düşük skor
    if not gercek_transkript:
        return {
            "transkript": "",
            "telaffuz_skoru": 0,
            "akicilik_skoru": 0,
            "wpm": 0,
            "norm_wpm": {1:50,2:75,3:95,4:115,5:130}.get(sinif,95),
            "duraklama_sayisi": 0,
            "tonlama_skoru": 0,
            "vurgu_skoru": 0,
            "genel_skor": 0,
            "seviye": "geliştirilmeli",
            "guclu_yonler": [],
            "gelisim_alanlari": ["Okumaya başla — mikrofon sesi almadı"],
            "telaffuz_hatalar": [],
            "mock": True,
        }

    t_kelimeler = normalize(gercek_transkript)

    # ── Kelime bazlı diff ile yanlış/atlanmış kelimeleri bul ──
    matcher = difflib.SequenceMatcher(None, b_kelimeler, t_kelimeler, autojunk=False)
    dogru = 0
    yanlis_kelimeler = []
    atlanan_kelimeler = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            dogru += (i2 - i1)
        elif tag == "replace":
            # Beklenen kelimeler yanlış okunmuş
            for k in b_kelimeler[i1:i2]:
                yanlis_kelimeler.append(k)
        elif tag == "delete":
            # Beklenen kelimeler hiç okunmamış
            for k in b_kelimeler[i1:i2]:
                atlanan_kelimeler.append(k)

    toplam = len(b_kelimeler)
    telaffuz_skoru = round((dogru / toplam) * 100) if toplam > 0 else 0

    # Yanlış okunan kelimelerin orijinal (normalize edilmemiş) hallerini bul
    b_orijinal = beklenen_metin.split()
    telaffuz_hata_listesi = []
    for yanlis in set(yanlis_kelimeler + atlanan_kelimeler):
        # Orijinal metinde bu kelimeye yakın olanı bul
        for kel in b_orijinal:
            if normalize(kel) and normalize(kel)[0] == yanlis:
                telaffuz_hata_listesi.append(kel.strip('.,!?;:"\'-'))
                break
        else:
            telaffuz_hata_listesi.append(yanlis)

    # ── WPM hesapla ──
    sure_dk = max(sure_sn / 60, 0.1)
    # Transkriptteki kelime sayısından WPM
    wpm = round(len(t_kelimeler) / sure_dk)
    norm = {1: 50, 2: 75, 3: 95, 4: 115, 5: 130, 6: 145, 7: 155, 8: 165}.get(sinif, 95)
    akicilik_skoru = min(100, round(wpm / norm * 100))

    # ── Duraksama tahmini — WPM'e göre ──
    duraklama_sayisi = max(0, int((norm - wpm) / 15)) if wpm < norm else 0

    # ── Tonlama: noktalama işaretlerinde durup durmadığına bakılamaz,
    #    ancak cümle sonlarındaki kelime oranına bak ──
    noktalama_kelimeler = [w for w in beklenen_metin.split() if w[-1] in '.!?,;' if len(w) > 1]
    tonlama_skoru = min(100, telaffuz_skoru + 3)
    vurgu_skoru = min(100, akicilik_skoru + 2)

    seviye = "çok iyi" if telaffuz_skoru >= 85 else "iyi" if telaffuz_skoru >= 70 else "orta" if telaffuz_skoru >= 55 else "geliştirilmeli"

    guclu = []
    gelisim = []
    if telaffuz_skoru >= 80: guclu.append("Kelime telaffuzu başarılı")
    if akicilik_skoru >= 80: guclu.append("Okuma hızı sınıf normuna uygun")
    if len(telaffuz_hata_listesi) == 0 and telaffuz_skoru >= 70: guclu.append("Tüm kelimeleri doğru okudun")
    if akicilik_skoru < 70: gelisim.append(f"Okuma hızını artır (hedef: {norm} kelime/dk)")
    if len(telaffuz_hata_listesi) > 3: gelisim.append("Yanlış okunan kelimeleri tekrar çalış")
    if len(atlanan_kelimeler) > 2: gelisim.append("Bazı kelimeleri atladın, dikkatli oku")

    return {
        "transkript": gercek_transkript,
        "telaffuz_skoru": telaffuz_skoru,
        "akicilik_skoru": akicilik_skoru,
        "wpm": wpm,
        "norm_wpm": norm,
        "duraklama_sayisi": duraklama_sayisi,
        "tonlama_skoru": tonlama_skoru,
        "vurgu_skoru": vurgu_skoru,
        "genel_skor": round((telaffuz_skoru * 0.6 + akicilik_skoru * 0.4)),
        "seviye": seviye,
        "guclu_yonler": guclu,
        "gelisim_alanlari": gelisim,
        "telaffuz_hatalar": telaffuz_hata_listesi[:8],  # max 8 kelime göster
        "atlanan_kelimeler": atlanan_kelimeler[:5],
        "mock": False,  # Artık gerçek transkript analizi
    }


@api_router.get("/ai/speech/metinler")
async def speech_okuma_metinleri(sinif: int = 3, current_user=Depends(get_current_user)):
    """Sınıfa göre sesli okuma metinleri getir."""
    metinler = SPEECH_OKUMA_METİNLERİ.get(sinif, SPEECH_OKUMA_METİNLERİ.get(3, []))
    if not metinler:
        # En yakın sınıfı bul
        for s in range(sinif, 0, -1):
            if s in SPEECH_OKUMA_METİNLERİ:
                metinler = SPEECH_OKUMA_METİNLERİ[s]
                break
    return {"metinler": metinler, "sinif": sinif}


@api_router.post("/ai/speech/analiz")
async def speech_analiz(
    ses_dosyasi: UploadFile = File(None),
    metin_id: str = Form(""),
    ogrenci_id: str = Form(""),
    sure_sn: float = Form(30.0),
    sinif: int = Form(3),
    transkript_input: str = Form(""),  # Web Speech API'den gelen transkript
    current_user=Depends(get_current_user)
):
    """Sesli okuma kaydını analiz et: WPM + telaffuz + tonlama + duraklama."""
    # Hedef metni bul
    beklenen_metin = ""
    metin_baslik = ""
    for s_list in SPEECH_OKUMA_METİNLERİ.values():
        for m in s_list:
            if m["id"] == metin_id:
                beklened_metin = m["metin"]
                beklenen_metin = m["metin"]
                metin_baslik = m["baslik"]
                sinif = m.get("sinif", sinif)
                break

    transkript = transkript_input.strip()  # Web Speech API'den gelen
    whisper_kullanildi = False

    # Whisper API — varsa kullan
    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
    if ses_dosyasi and OPENAI_API_KEY:
        try:
            ses_bytes = await ses_dosyasi.read()
            # Dosya uzantısını ve mime type'ı belirle
            filename = ses_dosyasi.filename or "ses.webm"
            content_type = ses_dosyasi.content_type or "audio/webm"
            # Whisper desteklenen formatlar: mp4, webm, mp3, wav, m4a, ogg
            if "mp4" in content_type or filename.endswith(".mp4"):
                mime = "audio/mp4"
                ext = "mp4"
            else:
                mime = "audio/webm"
                ext = "webm"
            async with httpx.AsyncClient(timeout=90.0) as c:
                resp = await c.post(
                    "https://api.openai.com/v1/audio/transcriptions",
                    headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
                    files={"file": (f"ses.{ext}", ses_bytes, mime)},
                    data={"model": "whisper-1", "language": "tr"},
                )
                if resp.status_code == 200:
                    transkript = resp.json().get("text", "")
                    whisper_kullanildi = True
                else:
                    logging.warning(f"Whisper API yanıt: {resp.status_code} — {resp.text[:200]}")
        except Exception as e:
            logging.warning(f"Whisper API hatası: {e}")

    # Analiz
    analiz = _speech_mock_analiz(transkript, beklenen_metin, sure_sn, sinif)
    analiz["whisper_kullanildi"] = whisper_kullanildi

    # Claude ile derin analiz (API key varsa)
    if GEMINI_API_KEY and beklenen_metin and transkript:
        ai_prompt = f"""Öğrenci okuma analizi (Sınıf: {sinif}):

Beklenen metin: {beklenen_metin}
Öğrenci okuması (transkript): {transkript}
Süre: {sure_sn:.0f} saniye
WPM: {analiz['wpm']}

Analiz et ve şu JSON'u döndür:
{{
  "guclu_yonler": ["...", "..."],
  "gelisim_alanlari": ["...", "..."],
  "ogretmen_notu": "Öğretmene 1-2 cümle öneri",
  "ogrenci_mesaj": "Öğrenciye motive edici 1 cümle (sen diliyle)",
  "telaffuz_hatalar": ["yanlış okunan kelime varsa listele"],
  "tonlama_degerlendirme": "iyi/orta/geliştirilmeli"
}}

SADECE JSON döndür."""
        ai_result = await call_claude(
            "Sen ilkokul Türkçe okuma uzmanısın. Çocukların okuma becerilerini değerlendirirsin.",
            ai_prompt, model="haiku", max_tokens=500
        )
        if ai_result.get("parsed"):
            p = ai_result["parsed"]
            analiz["guclu_yonler"] = p.get("guclu_yonler", analiz["guclu_yonler"])
            analiz["gelisim_alanlari"] = p.get("gelisim_alanlari", analiz["gelisim_alanlari"])
            analiz["ogretmen_notu"] = p.get("ogretmen_notu", "")
            analiz["ogrenci_mesaj"] = p.get("ogrenci_mesaj", "")
            analiz["telaffuz_hatalar"] = p.get("telaffuz_hatalar", [])
            analiz["tonlama_degerlendirme"] = p.get("tonlama_degerlendirme", "")
            analiz["mock"] = False

    # Varsayılan mesajlar (AI yoksa)
    if "ogretmen_notu" not in analiz:
        analiz["ogretmen_notu"] = f"Öğrenci {analiz['wpm']} kelime/dk hızında okudu. " + (
            "Akıcılığını artırmak için tekrarlı okuma egzersizleri önerilebilir." if analiz["akicilik_skoru"] < 70
            else "Okuma hızı sınıf normuna uygun."
        )
    if "ogrenci_mesaj" not in analiz:
        mesajlar = {
            "çok iyi": "Harika okudun! Sen gerçek bir okuma şampiyonusun! 🏆",
            "iyi": "Çok güzel okudun! Her gün biraz daha iyileşiyorsun! ⭐",
            "orta": "İyi bir başlangıç! Pratik yaptıkça daha da güzelleşecek! 💪",
            "geliştirilmeli": "Okumaya devam et, her gün daha iyisi olacaksın! 🌱",
        }
        analiz["ogrenci_mesaj"] = mesajlar.get(analiz["seviye"], "Harika iş çıkardın!")

    # Veritabanına kaydet
    gercek_ogrenci_id = ogrenci_id or current_user.get("linked_id") or current_user.get("id")
    kayit_id = str(uuid.uuid4())
    await db.speech_logs.insert_one({
        "id": kayit_id,
        "ogrenci_id": gercek_ogrenci_id,
        "metin_id": metin_id,
        "metin_baslik": metin_baslik,
        "metin": beklenen_metin,
        "sinif": sinif,
        "sure_sn": sure_sn,
        "analiz": analiz,
        "tarih": datetime.utcnow().isoformat(),
    })

    # XP ver
    xp = 15 if analiz["genel_skor"] >= 80 else 10 if analiz["genel_skor"] >= 60 else 5
    ogrenci = await db.students.find_one({"id": gercek_ogrenci_id})
    if not ogrenci:
        ogrenci = await db.users.find_one({"id": gercek_ogrenci_id})
    if ogrenci:
        await db.students.update_one({"id": gercek_ogrenci_id}, {"$inc": {"toplam_xp": xp}})
        await db.xp_logs.insert_one({
            "id": str(uuid.uuid4()), "ogrenci_id": gercek_ogrenci_id,
            "eylem": "sesli_okuma", "xp": xp,
            "aciklama": f"Sesli okuma: {metin_baslik} — {analiz['genel_skor']}/100",
            "tarih": datetime.utcnow().isoformat(),
        })

    return {**analiz, "id": kayit_id, "xp_kazanildi": xp}


@api_router.get("/ai/speech/gecmis/{ogrenci_id}")
async def speech_gecmis(ogrenci_id: str, current_user=Depends(get_current_user)):
    """Öğrencinin sesli okuma geçmişi."""
    kayitlar = await db.speech_logs.find(
        {"ogrenci_id": ogrenci_id}
    ).sort("tarih", -1).to_list(length=50)
    for k in kayitlar:
        k.pop("_id", None)
    return kayitlar


@api_router.get("/ai/speech/istatistik/{ogrenci_id}")
async def speech_istatistik(ogrenci_id: str, current_user=Depends(get_current_user)):
    """Öğrencinin sesli okuma gelişim istatistikleri."""
    kayitlar = await db.speech_logs.find(
        {"ogrenci_id": ogrenci_id}
    ).sort("tarih", 1).to_list(length=None)
    for k in kayitlar:
        k.pop("_id", None)

    if not kayitlar:
        return {"toplam": 0, "ort_wpm": 0, "ort_skor": 0, "gelisim": [], "en_iyi": None}

    wpm_list = [k["analiz"].get("wpm", 0) for k in kayitlar]
    skor_list = [k["analiz"].get("genel_skor", 0) for k in kayitlar]

    # Son 10 kayıt grafik için
    gelisim = [
        {
            "tarih": k["tarih"][:10],
            "wpm": k["analiz"].get("wpm", 0),
            "skor": k["analiz"].get("genel_skor", 0),
            "metin": k.get("metin_baslik", ""),
        }
        for k in kayitlar[-10:]
    ]

    en_iyi = max(kayitlar, key=lambda k: k["analiz"].get("genel_skor", 0))

    return {
        "toplam": len(kayitlar),
        "ort_wpm": round(sum(wpm_list) / len(wpm_list)),
        "ort_skor": round(sum(skor_list) / len(skor_list)),
        "son_wpm": wpm_list[-1] if wpm_list else 0,
        "son_skor": skor_list[-1] if skor_list else 0,
        "gelisim": gelisim,
        "en_iyi": {
            "metin": en_iyi.get("metin_baslik", ""),
            "skor": en_iyi["analiz"].get("genel_skor", 0),
            "wpm": en_iyi["analiz"].get("wpm", 0),
            "tarih": en_iyi["tarih"][:10],
        },
    }


# ─────────────────────────────────────────────
# DALGA 4: KİTAP ZEKÂ HARİTASI
# ─────────────────────────────────────────────

ZEKA_BOYUTLARI = ["soyutluk", "kelime_zorlugu", "hayal_gucu", "felsefi_derinlik", "aksiyon", "duygusal_yogunluk", "hedef_kelime_yogunlugu"]
ZEKA_ETIKETLER = {
    "soyutluk": "Soyutluk",
    "kelime_zorlugu": "Kelime Zorluğu",
    "hayal_gucu": "Hayal Gücü",
    "felsefi_derinlik": "Felsefi Derinlik",
    "aksiyon": "Aksiyon",
    "duygusal_yogunluk": "Duygusal Yoğunluk",
    "hedef_kelime_yogunlugu": "Kelime Yoğunluğu",
}


def _dna_ile_kitap_eslesme(dna: dict, profil: dict) -> float:
    """Öğrencinin DNA'sı ile kitap profilinin uyum skoru (0-100)."""
    if not dna or not profil:
        return 50.0
    # DNA boyutları → kitap boyutu eşleştirmesi
    eslesmeler = [
        (dna.get("kelime_gucu", 50), profil.get("kelime_zorlugu", 5), False),      # kelime gücü yüksekse zor kitap iyi
        (dna.get("anlama_derinligi", 50), profil.get("soyutluk", 5), False),         # anlama derinliği yüksekse soyut kitap iyi
        (dna.get("anlama_derinligi", 50), profil.get("felsefi_derinlik", 5), False), # aynı
        (dna.get("akicilik", 50), profil.get("aksiyon", 5), True),                   # akıcı okuyucu aksiyon kitabı sever
    ]
    toplam = 0.0
    for dna_val, kitap_val, dogrusal in eslesmeler:
        kitap_norm = kitap_val * 10  # 1-10 → 0-100
        if dogrusal:
            fark = abs(dna_val - kitap_norm)
            toplam += max(0, 100 - fark)
        else:
            # DNA yüksekse yüksek kitap değeri iyi
            uyum = min(dna_val, kitap_norm) / max(dna_val, kitap_norm, 1) * 100
            toplam += uyum
    return round(toplam / len(eslesmeler), 1)


@api_router.post("/ai/kitap-zeka/analiz")
async def kitap_zeka_analiz(request: Request, current_user=Depends(get_current_user)):
    """
    Kitap adı ve yazardan 7 boyutlu Zekâ Haritası üret.
    Varsa cache'den döner, yoksa Claude ile üretir.
    """
    body = await request.json()
    kitap_adi = body.get("kitap_adi", "").strip()
    yazar = body.get("yazar", "").strip()
    kitap_id = body.get("kitap_id", "")
    sinif = int(body.get("sinif", 3))

    if not kitap_adi:
        raise HTTPException(status_code=400, detail="Kitap adı gerekli")

    # Cache kontrolü
    cache_key = f"{kitap_adi.lower()}_{yazar.lower()}"
    mevcut = await db.kitap_zeka_profilleri.find_one({"cache_key": cache_key})
    if mevcut:
        mevcut.pop("_id", None)
        return mevcut

    # Claude ile 7 boyut analizi
    boyutlar = {}
    ai_aciklama = ""

    if GEMINI_API_KEY:
        try:
            prompt = f"""Kitap: "{kitap_adi}" — Yazar: {yazar or 'bilinmiyor'} — Hedef sınıf: {sinif}

Bu kitabı 7 boyutta 1-10 arası puan ver (1=çok düşük, 10=çok yüksek):
1. soyutluk — Soyut kavramlar, metafor kullanımı
2. kelime_zorlugu — Kelime hazinesi güçlüğü
3. hayal_gucu — Hayal gücü ve yaratıcılık gerektirme
4. felsefi_derinlik — Felsefi ve ahlaki sorular
5. aksiyon — Aksiyon, macera, hız
6. duygusal_yogunluk — Duygusal etki, empati
7. hedef_kelime_yogunlugu — MEB hedef kelime yoğunluğu

Ayrıca 1 cümle Türkçe açıklama yaz.

SADECE JSON döndür:
{{"soyutluk":5,"kelime_zorlugu":4,"hayal_gucu":8,"felsefi_derinlik":3,"aksiyon":7,"duygusal_yogunluk":6,"hedef_kelime_yogunlugu":5,"aciklama":"..."}}"""

            result = await call_claude("Sen bir kitap analisti ve eğitim uzmanısın.", prompt, model="haiku", max_tokens=300)
            if result.get("parsed"):
                p = result["parsed"]
                boyutlar = {k: int(p.get(k, 5)) for k in ZEKA_BOYUTLARI}
                ai_aciklama = p.get("aciklama", "")
        except Exception as e:
            logging.warning(f"Kitap zeka analiz hatası: {e}")

    # Fallback — kural bazlı tahmin
    if not boyutlar:
        import random
        random.seed(hash(kitap_adi))
        boyutlar = {k: random.randint(3, 8) for k in ZEKA_BOYUTLARI}
        ai_aciklama = f"'{kitap_adi}' için otomatik profil oluşturuldu."

    # Genel zorluk skoru (1-10)
    genel_zorluk = round(sum([boyutlar["soyutluk"], boyutlar["kelime_zorlugu"], boyutlar["felsefi_derinlik"]]) / 3, 1)

    kayit = {
        "id": str(uuid.uuid4()),
        "cache_key": cache_key,
        "kitap_adi": kitap_adi,
        "yazar": yazar,
        "kitap_id": kitap_id,
        "sinif": sinif,
        "boyutlar": boyutlar,
        "genel_zorluk": genel_zorluk,
        "aciklama": ai_aciklama,
        "olusturma_tarihi": datetime.utcnow().isoformat(),
    }
    await db.kitap_zeka_profilleri.insert_one(kayit)
    kayit.pop("_id", None)
    return kayit


@api_router.get("/ai/kitap-zeka/tavsiye")
async def kitap_zeka_tavsiye(current_user=Depends(get_current_user)):
    """
    Öğrencinin DNA profiline göre en uygun kitapları öner.
    kitap_zeka_profilleri + okuma_kayitlari + dna karşılaştırması.
    """
    ogrenci_id = current_user.get("linked_id") or current_user.get("id")

    # DNA profili
    dna = await db.okuma_dna.find_one({"ogrenci_id": ogrenci_id})
    dna_boyutlar = dna or {}

    # Daha önce okunanlar
    okunanlar = await db.okuma_kayitlari.distinct("kitap_adi", {"ogrenci_id": ogrenci_id})
    okunanlar_set = {k.lower() for k in okunanlar if k}

    # Tüm profilli kitaplar
    tum_profiller = await db.kitap_zeka_profilleri.find({}).to_list(length=100)

    # Her kitap için uyum skoru hesapla
    skorlu = []
    for p in tum_profiller:
        p.pop("_id", None)
        if p["kitap_adi"].lower() in okunanlar_set:
            continue  # zaten okunan
        uyum = _dna_ile_kitap_eslesme(dna_boyutlar, p.get("boyutlar", {}))
        skorlu.append({**p, "uyum_skoru": uyum})

    # Uyum skoruna göre sırala, top 5
    skorlu.sort(key=lambda x: x["uyum_skoru"], reverse=True)
    return {"tavsiyeler": skorlu[:5], "dna_var": bool(dna)}


@api_router.get("/ai/kitap-zeka/profil/{kitap_id}")
async def kitap_zeka_profil(kitap_id: str, current_user=Depends(get_current_user)):
    """Kaydedilmiş kitap zekâ profilini getir."""
    profil = await db.kitap_zeka_profilleri.find_one({"kitap_id": kitap_id})
    if not profil:
        profil = await db.kitap_zeka_profilleri.find_one({"id": kitap_id})
    if not profil:
        raise HTTPException(status_code=404, detail="Profil bulunamadı")
    profil.pop("_id", None)
    return profil


@api_router.get("/ai/kitap-zeka/liste")
async def kitap_zeka_liste(current_user=Depends(get_current_user)):
    """Tüm profilli kitapları listele (admin/öğretmen)."""
    profiller = await db.kitap_zeka_profilleri.find({}).sort("olusturma_tarihi", -1).to_list(length=200)
    for p in profiller:
        p.pop("_id", None)
    return {"profiller": profiller}


# ─────────────────────────────────────────────
# DALGA 3: AI MOTİVASYON MOTORU
# ─────────────────────────────────────────────





# ─────────────────────────────────────────────
# DALGA 3: OKUMA EVRENİ (5 BÖLGE)
# ─────────────────────────────────────────────

EVREN_BOLGELER = [
    {"id":"orman","sira":1,"ad":"Orman Kitaplığı","emoji":"🌲","renk":"green","aciklama":"Okuma serüvenin burada başlıyor!","kosul":"Başlangıç — herkese açık","kilitAc":None},
    {"id":"daglar","sira":2,"ad":"Kelime Dağları","emoji":"⛰️","renk":"blue","aciklama":"50 kelime öğrenince dağlara tırmanırsın!","kosul":"50 kelime öğren","kilitAc":{"tip":"kelime","deger":50}},
    {"id":"liman","sira":3,"ad":"Hikâye Limanı","emoji":"⚓","renk":"cyan","aciklama":"5 kitap okuyunca limana yanaşırsın!","kosul":"5 kitap oku","kilitAc":{"tip":"kitap","deger":5}},
    {"id":"kutuphane","sira":4,"ad":"Bilgelik Kütüphanesi","emoji":"🏰","renk":"purple","aciklama":"Bloom testlerinde %60 başarı sağla!","kosul":"Bloom skoru %60+","kilitAc":{"tip":"bloom","deger":60}},
    {"id":"galaksi","sira":5,"ad":"Hayal Galaksisi","emoji":"🚀","renk":"orange","aciklama":"Her şeyi tamamlayınca galaksiye uçarsın!","kosul":"Hepsini tamamla","kilitAc":{"tip":"hepsi","deger":0}},
]


async def _evren_hesapla(ogrenci_id: str) -> dict:
    kelime_sayisi = await db.kelime_tekrar.count_documents({"ogrenci_id": ogrenci_id, "seviye": {"$gte": 3}})
    if kelime_sayisi == 0:
        kelime_sayisi = await db.kelime_tekrar.count_documents({"ogrenci_id": ogrenci_id})
    kitaplar = await db.okuma_kayitlari.distinct("kitap_adi", {"ogrenci_id": ogrenci_id, "kitap_adi": {"$exists": True, "$ne": ""}})
    kitap_sayisi = len([k for k in kitaplar if k and k.strip()])
    bloom_kayitlar = await db.ai_uretilen_sorular.find({"ogrenci_id": ogrenci_id, "cevaplandi": True}).sort("tarih", -1).to_list(length=30)
    bloom_skoru = 0
    if bloom_kayitlar:
        dogru = sum(1 for k in bloom_kayitlar if k.get("dogru_mu"))
        bloom_skoru = round(dogru / len(bloom_kayitlar) * 100)

    bolgeler_durum = []
    aktif_bolge = "orman"
    for b in EVREN_BOLGELER:
        acik = True; ilerleme = 100; kac_kaldi = ""
        kil = b["kilitAc"]
        if kil:
            if kil["tip"] == "kelime":
                acik = kelime_sayisi >= kil["deger"]; ilerleme = min(100, round(kelime_sayisi/kil["deger"]*100))
                kac_kaldi = f"{max(0,kil['deger']-kelime_sayisi)} kelime daha" if not acik else ""
            elif kil["tip"] == "kitap":
                acik = kitap_sayisi >= kil["deger"]; ilerleme = min(100, round(kitap_sayisi/kil["deger"]*100))
                kac_kaldi = f"{max(0,kil['deger']-kitap_sayisi)} kitap daha" if not acik else ""
            elif kil["tip"] == "bloom":
                acik = bloom_skoru >= kil["deger"]; ilerleme = min(100, bloom_skoru)
                kac_kaldi = f"%{max(0,kil['deger']-bloom_skoru)} daha" if not acik else ""
            elif kil["tip"] == "hepsi":
                acik = kelime_sayisi >= 50 and kitap_sayisi >= 5 and bloom_skoru >= 60
                ilerleme = round((min(100,kelime_sayisi/50*100)+min(100,kitap_sayisi/5*100)+min(100,bloom_skoru/60*100))/3)
                kac_kaldi = "" if acik else "Önceki bölgeleri tamamla"
        bolgeler_durum.append({**{k: v for k,v in b.items() if k != "kilitAc"}, "acik": acik, "ilerleme": ilerleme, "kac_kaldi": kac_kaldi})
        if acik:
            aktif_bolge = b["id"]

    return {
        "aktif_bolge": aktif_bolge,
        "bolgeler": bolgeler_durum,
        "istatistikler": {"kelime_sayisi": kelime_sayisi, "kitap_sayisi": kitap_sayisi, "bloom_skoru": bloom_skoru},
    }


@api_router.get("/ai/evren/durum/{ogrenci_id}")
async def evren_durum(ogrenci_id: str, current_user=Depends(get_current_user)):
    return await _evren_hesapla(ogrenci_id)


@api_router.get("/ai/evren/durum-me")
async def evren_durum_me(current_user=Depends(get_current_user)):
    ogrenci_id = current_user.get("linked_id") or current_user.get("id")
    return await _evren_hesapla(ogrenci_id)


# ─────────────────────────────────────────────
# DALGA 3: OKUMA DİKKAT ANALİZİ
# ─────────────────────────────────────────────

def _dikkat_skoru_hesapla(metrikler: dict) -> dict:
    """Davranış metriklerinden dikkat skoru üret."""
    sure_sn = metrikler.get("sure_sn", 0)
    kelime_sayisi = metrikler.get("kelime_sayisi", 100)
    geri_scroll_sayisi = metrikler.get("geri_scroll_sayisi", 0)
    zorluk_kelimeler = metrikler.get("zorluk_kelimeler", [])
    duraklamalar = metrikler.get("duraklamalar", 0)  # anormal duraklamalar

    # Beklenen okuma süresi (sinif normuna göre WPM)
    sinif = metrikler.get("sinif", 3)
    norm_wpm = {1:50, 2:75, 3:95, 4:115, 5:130}.get(sinif, 95)
    beklenen_sure = (kelime_sayisi / norm_wpm) * 60  # saniye

    # 1. Süre skoru — çok hızlı veya çok yavaş ise düşük
    if beklenen_sure > 0:
        oran = sure_sn / beklenen_sure
        if 0.7 <= oran <= 1.5:
            sure_skoru = 100
        elif 0.5 <= oran < 0.7 or 1.5 < oran <= 2.0:
            sure_skoru = 70
        elif oran < 0.5:
            sure_skoru = 40  # çok hızlı — atlıyor olabilir
        else:
            sure_skoru = 50  # çok yavaş — zorlanıyor
    else:
        sure_skoru = 60

    # 2. Geri scroll — dikkatin dağıldığı veya anlamadığı bölümler
    max_scroll = max(1, kelime_sayisi // 50)
    scroll_skoru = max(0, 100 - (geri_scroll_sayisi / max_scroll) * 30)

    # 3. Zorluk kelimeleri — tıklamak pozitif (merak) ama çok fazlası zorlandığını gösterir
    if len(zorluk_kelimeler) == 0:
        zorluk_skoru = 80  # hiç tıklamadı — anlıyor olabilir veya ilgisiz
    elif len(zorluk_kelimeler) <= 3:
        zorluk_skoru = 95  # meraklı — sağlıklı
    elif len(zorluk_kelimeler) <= 6:
        zorluk_skoru = 75  # biraz zorlanıyor
    else:
        zorluk_skoru = 55  # çok zorlanıyor

    # 4. Duraklamalar
    duraklama_skoru = max(40, 100 - duraklamalar * 10)

    # Genel dikkat skoru (ağırlıklı ortalama)
    dikkat = round(
        sure_skoru * 0.35 +
        scroll_skoru * 0.30 +
        zorluk_skoru * 0.20 +
        duraklama_skoru * 0.15
    )

    # Yorum
    if dikkat >= 80:
        yorum = "Harika konsantrasyon! Metni akıcı okudun."
        oneri = None
    elif dikkat >= 65:
        yorum = "İyi odaklanma. Birkaç bölümde zorlandın."
        oneri = "Zorlandığın kelimeleri not et ve tekrar bak." if zorluk_kelimeler else "Biraz daha yavaş okumayı dene."
    elif dikkat >= 50:
        yorum = "Dikkat dağınıklığı var. Bazı bölümleri tekrar okumalısın."
        oneri = "Sessiz bir ortamda okumayı dene. Kısa molalar ver."
    else:
        yorum = "Bu bölümü anlamakta zorlandın. Tekrar okumalısın."
        oneri = "Bu metni bir daha yavaşça oku. Zor kelimelerin anlamına bak."

    return {
        "dikkat_skoru": dikkat,
        "alt_skorlar": {
            "sure": round(sure_skoru),
            "scroll": round(scroll_skoru),
            "zorluk": round(zorluk_skoru),
            "duraklama": round(duraklama_skoru),
        },
        "yorum": yorum,
        "oneri": oneri,
        "zorluk_kelimeler": zorluk_kelimeler[:10],
        "geri_oku_onerisi": dikkat < 60,
    }


@api_router.post("/ai/dikkat/kaydet")
async def dikkat_kaydet(request: Request, current_user=Depends(get_current_user)):
    """Okuma oturumunun dikkat metriklerini kaydet ve analiz et."""
    body = await request.json()
    ogrenci_id = current_user.get("linked_id") or current_user.get("id")

    metrikler = {
        "sure_sn": body.get("sure_sn", 0),
        "kelime_sayisi": body.get("kelime_sayisi", 100),
        "geri_scroll_sayisi": body.get("geri_scroll_sayisi", 0),
        "zorluk_kelimeler": body.get("zorluk_kelimeler", []),
        "duraklamalar": body.get("duraklamalar", 0),
        "sinif": body.get("sinif", 3),
    }

    analiz = _dikkat_skoru_hesapla(metrikler)

    # Veritabanına kaydet
    kayit_id = str(uuid.uuid4())
    await db.dikkat_log.insert_one({
        "id": kayit_id,
        "ogrenci_id": ogrenci_id,
        "kitap_adi": body.get("kitap_adi", ""),
        "bolum": body.get("bolum", ""),
        "metrikler": metrikler,
        "analiz": analiz,
        "tarih": datetime.utcnow().isoformat(),
    })

    # DNA dikkat boyutunu güncelle — son 5 oturumun ortalaması
    son_kayitlar = await db.dikkat_log.find(
        {"ogrenci_id": ogrenci_id}
    ).sort("tarih", -1).to_list(length=5)
    son_kayitlar_pop = [k for k in son_kayitlar if k.get("_id")]
    for k in son_kayitlar:
        k.pop("_id", None)

    if son_kayitlar:
        ort_dikkat = round(sum(k["analiz"]["dikkat_skoru"] for k in son_kayitlar) / len(son_kayitlar))
        await db.okuma_dna.update_one(
            {"ogrenci_id": ogrenci_id},
            {"$set": {"boyutlar.dikkat_suresi": ort_dikkat, "son_guncelleme": datetime.utcnow().isoformat()}},
        )

    return {**analiz, "id": kayit_id}


@api_router.get("/ai/dikkat/gecmis/{ogrenci_id}")
async def dikkat_gecmis(ogrenci_id: str, current_user=Depends(get_current_user)):
    """Öğrencinin dikkat analizi geçmişi."""
    kayitlar = await db.dikkat_log.find(
        {"ogrenci_id": ogrenci_id}
    ).sort("tarih", -1).to_list(length=20)
    for k in kayitlar:
        k.pop("_id", None)
    return kayitlar


# ─────────────────────────────────────────────
# DALGA 3: OKUMA DİKKAT ANALİZİ
# ─────────────────────────────────────────────

@api_router.post("/ai/dikkat/kaydet")
async def dikkat_kaydet(request: Request, current_user=Depends(get_current_user)):
    """
    Okuma oturumu dikkat metriklerini kaydet, DNA dikkat boyutunu güncelle.
    Girdi: sure_sn, geri_scroll, zorluk_kelimeler, duraklamalar, scroll_hizi, okuma_id
    """
    body = await request.json()
    ogrenci_id = current_user.get("linked_id") or current_user.get("id")

    sure_sn      = int(body.get("sure_sn", 0))
    geri_scroll  = int(body.get("geri_scroll", 0))
    zorluk_kels  = body.get("zorluk_kelimeler", [])
    duraklamalar = int(body.get("duraklamalar", 0))
    scroll_hizi  = float(body.get("scroll_hizi_ort", 0))   # px/sn
    okuma_id     = body.get("okuma_id", "")
    sinif        = int(body.get("sinif", 3))

    # Dikkat skoru hesapla (0-100)
    # Düşük geri scroll → iyi dikkat
    # Az duraklatma → iyi akış
    # Normal scroll hızı (50-200 px/sn) → iyi okuma
    sure_dk = max(1, sure_sn / 60)

    geri_penalti   = min(40, geri_scroll * 3)
    durak_penalti  = min(20, duraklamalar * 5)
    hiz_bonus      = 10 if 30 <= scroll_hizi <= 250 else 0
    zorluk_bonus   = min(15, len(zorluk_kels) * 3)  # kelime tıklama dikkat göstergesi

    dikkat_skoru = max(10, 100 - geri_penalti - durak_penalti + hiz_bonus + zorluk_bonus)
    dikkat_skoru = round(min(100, dikkat_skoru))

    # Seviye ve tavsiye
    if dikkat_skoru >= 80:
        seviye = "odakli"
        mesaj  = "Harika! Okurken çok iyi odaklandın. 🎯"
    elif dikkat_skoru >= 60:
        seviye = "iyi"
        mesaj  = "Güzel bir okuma! Birkaç bölümde geri döndün, bu normaldir."
    elif dikkat_skoru >= 40:
        seviye = "orta"
        mesaj  = "Bazı bölümler zor geldi gibi görünüyor. Yavaş okumayı dene."
    else:
        seviye = "dagitik"
        mesaj  = "Bugün dikkatini toplamak zor olmuş olabilir. Kısa mola ver ve tekrar dene."

    # AI ile daha derin yorum (varsa)
    ai_yorum = None
    if GEMINI_API_KEY and len(zorluk_kels) > 0:
        try:
            prompt = f"""Öğrenci okuma dikkat analizi (Sınıf: {sinif}):
- Okuma süresi: {sure_dk:.1f} dakika
- Geri scroll sayısı: {geri_scroll}
- Duraklatma sayısı: {duraklamalar}
- Zorluk çekilen kelimeler: {', '.join(zorluk_kels[:5]) if zorluk_kels else 'yok'}
- Dikkat skoru: {dikkat_skoru}/100

Öğrenciye 2 cümle kısa ve motive edici Türkçe geri bildirim yaz. Çocuksu ama akıllıca."""
            r = await call_claude("Kısa ve motive edici geri bildirim ver.", prompt, model="haiku", max_tokens=150)
            ai_yorum = r.get("text", "")
        except Exception:
            pass

    # MongoDB'ye kaydet
    kayit = {
        "id": str(uuid.uuid4()),
        "ogrenci_id": ogrenci_id,
        "okuma_id": okuma_id,
        "sure_sn": sure_sn,
        "geri_scroll": geri_scroll,
        "zorluk_kelimeler": zorluk_kels,
        "duraklamalar": duraklamalar,
        "scroll_hizi_ort": scroll_hizi,
        "dikkat_skoru": dikkat_skoru,
        "seviye": seviye,
        "tarih": datetime.utcnow().isoformat(),
    }
    await db.dikkat_log.insert_one(kayit)

    # DNA dikkat boyutunu güncelle
    try:
        mevcut = await db.okuma_dna.find_one({"ogrenci_id": ogrenci_id})
        if mevcut:
            eski = mevcut.get("dikkat_suresi", 50)
            yeni = round(eski * 0.7 + dikkat_skoru * 0.3)  # ağırlıklı ortalama
            await db.okuma_dna.update_one(
                {"ogrenci_id": ogrenci_id},
                {"$set": {"dikkat_suresi": yeni, "son_guncelleme": datetime.utcnow().isoformat()}}
            )
    except Exception as e:
        logging.warning(f"DNA güncelleme hatası: {e}")

    return {
        "dikkat_skoru": dikkat_skoru,
        "seviye": seviye,
        "mesaj": mesaj,
        "ai_yorum": ai_yorum,
        "geri_bildirim": {
            "geri_scroll": geri_scroll,
            "zorluk_kels": zorluk_kels,
            "duraklamalar": duraklamalar,
        },
    }


@api_router.get("/ai/dikkat/gecmis/{ogrenci_id}")
async def dikkat_gecmis(ogrenci_id: str, current_user=Depends(get_current_user)):
    """Son 20 dikkat kaydı — trend grafik için."""
    kayitlar = await db.dikkat_log.find({"ogrenci_id": ogrenci_id}).sort("tarih", -1).to_list(length=20)
    for k in kayitlar:
        k.pop("_id", None)
    return kayitlar


# ─────────────────────────────────────────────
# DALGA 3: AI OKUMA ARKADAŞI (4 KARAKTER)
# ─────────────────────────────────────────────

AI_ARKADAS_KARAKTERLER = {
    "baykus": {
        "id": "baykus",
        "ad": "Bilge Baykuş",
        "emoji": "🦉",
        "renk": "purple",
        "tanim": "Derin sorular soran, düşündüren",
        "sistem_prompt": """Sen Bilge Baykuş'sun. İlkokul öğrencilerine okuma konusunda yardım eden bilge ve meraklı bir baykussun.
Özelliğin: Derin, düşündürücü sorular sorarsın. Bloom taksonomisinin analiz ve değerlendirme basamaklarını kullanırsın.
Kurallar:
- Her yanıtta 1-2 cümle konuş, sonra 1 soru sor
- Türkçe konuş, sade ve anlaşılır
- Asla kişisel bilgi sorma
- Sadece kitap, okuma, öğrenme hakkında konuş
- Yanıt max 3 cümle olsun
- Sen bir baykussun, bazen "Huu huu!" diyebilirsin""",
    },
    "robot": {
        "id": "robot",
        "ad": "Robot Kaptan",
        "emoji": "🤖",
        "renk": "blue",
        "tanim": "Heyecanlı, eğlenceli, macera dolu",
        "sistem_prompt": """Sen Robot Kaptan'sın! İlkokul öğrencileriyle konuşan süper heyecanlı bir robotsun!
Özelliğin: Her şeyi macera ve keşif olarak görürsün. Okumayı bir uzay yolculuğuna benzetirsin.
Kurallar:
- Heyecanlı konuş! Bazen "SÜPER!" veya "İNANILMAZ!" diyebilirsin
- Her yanıt max 3 cümle
- Türkçe konuş
- Sadece kitap ve okuma hakkında konuş
- Asla kişisel bilgi sorma
- Bazen robotça sesler çıkarabilirsin: bip bop!""",
    },
    "dede": {
        "id": "dede",
        "ad": "Kütüphane Dedesi",
        "emoji": "📖",
        "renk": "amber",
        "tanim": "Hikâye anlatan, sıcak, bilge",
        "sistem_prompt": """Sen Kütüphane Dedesi'sin. Yıllarca kütüphanede çalışmış, binlerce kitap okumuş, çok sevilen bir dedesin.
Özelliğin: Her konuya bağlantılı bir hikâye veya kitap hatırlarsın. Sıcak ve sevecensin.
Kurallar:
- "Ah, bir keresinde bir kitapta..." diye başlayabilirsin
- Her yanıt max 3 cümle
- Türkçe konuş, samimi ve sıcak ol
- Sadece kitap, okuma, hikâye hakkında konuş
- Asla kişisel bilgi sorma
- Bazen "Güzel kitaplar güzel rüyalar getirir" gibi atasözü söyleyebilirsin""",
    },
    "kedi": {
        "id": "kedi",
        "ad": "Gezgin Kedi",
        "emoji": "🐱",
        "renk": "green",
        "tanim": "Hayal gücü yüksek, yaratıcı, eğlenceli",
        "sistem_prompt": """Sen Gezgin Kedi'sin! Dünyanın her yerine seyahat etmiş, her kitabın içine girmiş bir kedisin.
Özelliğin: Hayal gücünü kullanırsın. Kitapların içindeki dünyaları canlandırırsın.
Kurallar:
- "Miyav! Bir keresinde o kitabın içine girmiştim ve..." diyebilirsin
- Her yanıt max 3 cümle
- Türkçe konuş, eğlenceli ve yaratıcı ol
- Sadece kitap, okuma, hayal gücü hakkında konuş
- Asla kişisel bilgi sorma
- Bazen "Miyav!" diyebilirsin""",
    },
}

# Günlük sohbet limiti
AI_ARKADAS_GUNLUK_LIMIT = 20
AI_ARKADAS_MODERASYON_ESIK = 50  # Her 50 mesajda moderasyon


def _arkadas_icerik_kontrol(mesaj: str) -> bool:
    """Çocuk güvenliği: uygunsuz içerik filtresi."""
    yasak_kelimeler = ["şifre", "adres", "telefon", "ev", "okul adresi", "nerede oturuyorsun"]
    mesaj_lower = mesaj.lower()
    return not any(k in mesaj_lower for k in yasak_kelimeler)


@api_router.get("/ai/arkadas/karakterler")
async def arkadas_karakterler(current_user=Depends(get_current_user)):
    """4 AI arkadaş karakterini getir."""
    return {
        "karakterler": [
            {k: v for k, v in kar.items() if k != "sistem_prompt"}
            for kar in AI_ARKADAS_KARAKTERLER.values()
        ]
    }


@api_router.post("/ai/arkadas/sohbet")
async def arkadas_sohbet(request: Request, current_user=Depends(get_current_user)):
    """Seçili karakterle sohbet et."""
    body = await request.json()
    karakter_id = body.get("karakter_id", "baykus")
    mesaj = body.get("mesaj", "").strip()
    gecmis = body.get("gecmis", [])  # [{rol: "user"|"assistant", icerik: "..."}]
    kitap_baglami = body.get("kitap_baglami", "")  # isteğe bağlı kitap adı

    if not mesaj:
        raise HTTPException(status_code=400, detail="Mesaj boş olamaz")
    if len(mesaj) > 500:
        raise HTTPException(status_code=400, detail="Mesaj çok uzun")
    if not _arkadas_icerik_kontrol(mesaj):
        raise HTTPException(status_code=400, detail="Bu tür bilgileri paylaşma — güvenliğin önemli!")

    karakter = AI_ARKADAS_KARAKTERLER.get(karakter_id, AI_ARKADAS_KARAKTERLER["baykus"])
    ogrenci_id = current_user.get("linked_id") or current_user.get("id")

    # Günlük limit kontrolü
    bugun = datetime.utcnow().strftime("%Y-%m-%d")
    gunluk_sayac = await db.ai_arkadas_log.count_documents({
        "ogrenci_id": ogrenci_id,
        "tarih": {"$gte": bugun}
    })
    if gunluk_sayac >= AI_ARKADAS_GUNLUK_LIMIT:
        return {
            "yanit": f"Bugün çok yoruldum! {karakter['emoji']} Yarın tekrar konuşalım. Bugün {AI_ARKADAS_GUNLUK_LIMIT} mesaj hakkın bitti.",
            "limit_doldu": True,
        }

    # Claude API ile yanıt
    sistem = karakter["sistem_prompt"]
    if kitap_baglami:
        sistem += f"\n\nÖğrenci şu an '{kitap_baglami}' kitabı hakkında konuşmak istiyor."

    # Sohbet geçmişini mesaj formatına çevir
    claude_mesajlar = []
    for h in gecmis[-6:]:  # son 6 mesaj (3 tur)
        claude_mesajlar.append({
            "role": "user" if h["rol"] == "user" else "assistant",
            "content": h["icerik"]
        })
    claude_mesajlar.append({"role": "user", "content": mesaj})

    yanit_metni = ""
    if GEMINI_API_KEY:
        try:
            result = await call_claude(sistem, mesaj, model="haiku", max_tokens=200)
            # call_claude single-turn, multi-turn için direkt API çağrısı
            if len(claude_mesajlar) > 1:
                # Multi-turn: tüm geçmişi tek prompt olarak gönder
                gecmis = "\n".join([f"{m['role'].upper()}: {m['content'] if isinstance(m['content'], str) else m['content'][0].get('text','')}" for m in claude_mesajlar])
                multi_prompt = f"{sistem}\n\nKONUŞMA GEÇMİŞİ:\n{gecmis}\n\nASISTAN:"
                yanit_metni = await _gemini_call(multi_prompt, max_tokens=200)
            else:
                yanit_metni = result.get("text", "")
        except Exception as e:
            logging.warning(f"AI Arkadaş API hatası: {e}")

    # API yoksa veya hata varsa — karakter bazlı mock yanıt
    if not yanit_metni:
        mock_yanitlar = {
            "baykus": [
                f"Huu huu! '{mesaj[:20]}...' çok ilginç bir düşünce! Peki, bu sana ne hissettiriyor?",
                "Harika bir soru! Kitaplar bize çok şey öğretir. Sen ne düşünüyorsun?",
                "Huu huu! Okumak zihnimizi açar. Bu kitapta en çok hangi bölümü sevdin?",
            ],
            "robot": [
                "BİP BOP! SÜPER düşünce! Bu kitap gerçekten bir uzay macerası gibi! Devam et!",
                "İNANILMAZ! Okumak bir zaman makinesi gibi, her sayfada yeni bir dünyaya gidiyorsun!",
                "SÜPER! Bip bop! Seninle okuma macerası yapmak çok eğlenceli!",
            ],
            "dede": [
                "Ah, güzel bir düşünce. Bir keresinde benzer bir kitap okumuştum, çok etkileyiciydi.",
                "Güzel kitaplar güzel rüyalar getirir. Okumaya devam et, çok işine yarayacak.",
                "Ah, biliyor musun, bu bana eski bir hikâyeyi hatırlattı. Kitaplar hayatımızı zenginleştirir.",
            ],
            "kedi": [
                f"Miyav! Ben de o kitabın içine girmiştim! Çok heyecanlıydı! Sen de hayal et!",
                "Miyav miyav! Kitaplar beni yeni dünyalara götürüyor. Sen hangi dünyaya gitmek istersin?",
                "Miyav! Hayal gücün çok güçlü! Her kitap yeni bir macera kapısı açar!",
            ],
        }
        import random
        yanit_metni = random.choice(mock_yanitlar.get(karakter_id, mock_yanitlar["baykus"]))

    # Veritabanına kaydet
    await db.ai_arkadas_log.insert_one({
        "id": str(uuid.uuid4()),
        "ogrenci_id": ogrenci_id,
        "karakter_id": karakter_id,
        "mesaj": mesaj,
        "yanit": yanit_metni,
        "kitap_baglami": kitap_baglami,
        "tarih": datetime.utcnow().strftime("%Y-%m-%d"),
        "tarih_tam": datetime.utcnow().isoformat(),
    })

    return {
        "yanit": yanit_metni,
        "karakter": {k: v for k, v in karakter.items() if k != "sistem_prompt"},
        "gunluk_kalan": max(0, AI_ARKADAS_GUNLUK_LIMIT - gunluk_sayac - 1),
        "limit_doldu": False,
    }


@api_router.get("/ai/arkadas/gecmis/{ogrenci_id}")
async def arkadas_gecmis(ogrenci_id: str, karakter_id: str = "", current_user=Depends(get_current_user)):
    """Öğrencinin belirli karakterle veya tüm sohbet geçmişi."""
    filtre = {"ogrenci_id": ogrenci_id}
    if karakter_id:
        filtre["karakter_id"] = karakter_id
    kayitlar = await db.ai_arkadas_log.find(filtre).sort("tarih_tam", -1).to_list(length=100)
    for k in kayitlar:
        k.pop("_id", None)
    return kayitlar


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

@api_router.post("/ai/kitap-zeka-haritasi")
async def kitap_zeka_haritasi(req: Request, current_user=Depends(get_current_user)):
    """Her kitap için 7 boyutlu AI profil üretir."""
    data = await req.json()
    kitap_adi = data.get("kitap_adi", "")
    yazar = data.get("yazar", "")
    sinif = data.get("sinif", 3)
    icerik_id = data.get("icerik_id", "")

    # Cache (kalıcı — kitap değişmez)
    cache = await db.kitap_zeka_haritasi.find_one({"icerik_id": icerik_id})
    if cache:
        cache.pop("_id", None)
        return cache

    # Metin varsa ekle
    metin_ek = ""
    icerik = await db.gelisim_icerik.find_one({"id": icerik_id})
    if icerik and icerik.get("okuma_metni"):
        metin_ek = f"\n\nMetin özeti (ilk 1000 kelime):\n{icerik['okuma_metni'][:2000]}"

    prompt = f"""Sen bir çocuk edebiyatı analistisin. "{kitap_adi}"{f" - {yazar}" if yazar else ""} için 7 boyutlu profil oluştur.{metin_ek}

Her boyutu 1-10 arasında puan ver. SADECE JSON döndür:
{{
  "kitap_adi": "{kitap_adi}",
  "boyutlar": {{
    "soyutluk": {{"puan": 5, "aciklama": "..."}},
    "kelime_zorlugu": {{"puan": 5, "aciklama": "..."}},
    "hayal_gucu": {{"puan": 5, "aciklama": "..."}},
    "felsefi_derinlik": {{"puan": 5, "aciklama": "..."}},
    "aksiyon": {{"puan": 5, "aciklama": "..."}},
    "duygusal_yogunluk": {{"puan": 5, "aciklama": "..."}},
    "hedef_kelime_yogunlugu": {{"puan": 5, "aciklama": "..."}}
  }},
  "sinif_uyumu": {sinif},
  "tavsiye_profil": "Bu kitap hangi öğrenciye uygundur? (2-3 cümle)",
  "tur_etiketleri": ["macera", "arkadaşlık"],
  "okuma_suresi_dk": 30
}}"""

    try:
        raw = await _gemini_call(prompt, max_tokens=1000)
        import json as _json, re as _re
        raw = raw.strip()
        if "```" in raw:
            m = _re.search(r"```(?:json)?\s*([\s\S]*?)```", raw)
            raw = m.group(1).strip() if m else _re.sub(r"```(?:json)?", "", raw).replace("```", "").strip()
        bs = raw.find("{"); be = raw.rfind("}")
        if bs != -1 and be != -1: raw = raw[bs:be+1]
        raw = _re.sub(r",\s*([}\]])", r"\1", raw)
        result = _json.loads(raw)
    except Exception as e:
        logging.error(f"[ZEKA-HARITA] Hata: {e}")
        result = {
            "kitap_adi": kitap_adi,
            "boyutlar": {
                "soyutluk": {"puan": 5, "aciklama": "Orta düzey soyut kavramlar içeriyor"},
                "kelime_zorlugu": {"puan": 5, "aciklama": "Yaş grubuna uygun kelime zenginliği"},
                "hayal_gucu": {"puan": 6, "aciklama": "Hayal gücünü geliştiren sahneler mevcut"},
                "felsefi_derinlik": {"puan": 4, "aciklama": "Temel değer sorgulamaları var"},
                "aksiyon": {"puan": 6, "aciklama": "Tempolu ve heyecanlı sahneler"},
                "duygusal_yogunluk": {"puan": 7, "aciklama": "Güçlü duygusal bağ kurduruyor"},
                "hedef_kelime_yogunlugu": {"puan": 5, "aciklama": "MEB müfredatına uygun kelimeler"}
            },
            "sinif_uyumu": sinif,
            "tavsiye_profil": "Okuma alışkanlığı kazanmaya başlayan, macera seven öğrencilere uygundur.",
            "tur_etiketleri": ["macera", "gelişim", "arkadaşlık"],
            "okuma_suresi_dk": sinif * 8
        }

    result["icerik_id"] = icerik_id
    result["olusturma_tarihi"] = datetime.utcnow().isoformat()
    await db.kitap_zeka_haritasi.update_one(
        {"icerik_id": icerik_id}, {"$set": result}, upsert=True
    )
    return result


# ─────────────────────────────────────────────
# KİTABA ÖZGÜ MİNİ OYUN — Kitap içeriğinden üret
# ─────────────────────────────────────────────

@api_router.post("/ai/kitap-oyun")
async def kitap_oyun_uret(req: Request, current_user=Depends(get_current_user)):
    """Kitap/metin içeriğinden oyun soruları üretir."""
    data = await req.json()
    kitap_adi = data.get("kitap_adi", "")
    icerik_id = data.get("icerik_id", "")
    oyun_turu = data.get("tur", "karakter_tahmini")  # karakter_tahmini, hikaye_devam, bosluk, eslestirme
    sinif = data.get("sinif", 3)

    # Metni al
    metin = ""
    icerik = await db.gelisim_icerik.find_one({"id": icerik_id})
    if icerik:
        metin = icerik.get("okuma_metni", "") or icerik.get("aciklama", "")
    if not metin:
        return {"oyun": None, "mesaj": "İçerik metni bulunamadı"}

    metin_kisalt = metin[:2500]

    if oyun_turu == "karakter_tahmini":
        prompt = f""""{kitap_adi}" metninden karakter tahmini oyunu oluştur.

Metin: {metin_kisalt}

SADECE JSON döndür. Metindeki gerçek karakterleri kullan:
{{
  "tur": "karakter_tahmini",
  "baslik": "🎭 Kim O?",
  "aciklama": "İpuçlarından karakteri bul!",
  "sorular": [
    {{
      "ipuclari": ["İpucu 1", "İpucu 2", "İpucu 3"],
      "dogru_karakter": "...",
      "secenekler": ["...", "...", "...", "..."]
    }}
  ],
  "xp": 8
}}"""

    elif oyun_turu == "hikaye_devam":
        prompt = f""""{kitap_adi}" metninden hikâye devam ettirme oyunu oluştur.

Metin: {metin_kisalt}

SADECE JSON döndür:
{{
  "tur": "hikaye_devam",
  "baslik": "📖 Hikâye Devam Ediyor",
  "aciklama": "Doğru devamı seç!",
  "sorular": [
    {{
      "metin_parcasi": "Metinden alınan bir paragraf...",
      "soru": "Bundan sonra ne oldu?",
      "secenekler": ["A seçeneği", "B seçeneği", "C seçeneği", "D seçeneği"],
      "dogru_idx": 0,
      "aciklama": "Neden bu doğru?"
    }}
  ],
  "xp": 10
}}"""

    elif oyun_turu == "eslestirme":
        prompt = f""""{kitap_adi}" metninden karakter-özellik eşleştirme oyunu oluştur.

Metin: {metin_kisalt}

SADECE JSON döndür:
{{
  "tur": "eslestirme",
  "baslik": "🎲 Kim Nasıl?",
  "aciklama": "Karakterleri özellikleriyle eşleştir!",
  "ciftler": [
    {{"sol": "Karakter adı", "sag": "Özelliği/yaptığı şey"}},
    {{"sol": "...", "sag": "..."}},
    {{"sol": "...", "sag": "..."}},
    {{"sol": "...", "sag": "..."}}
  ],
  "xp": 6
}}"""

    else:  # bosluk
        prompt = f""""{kitap_adi}" metninden boşluk doldurma oyunu oluştur. Metinden gerçek cümleler kullan.

Metin: {metin_kisalt}

SADECE JSON döndür:
{{
  "tur": "bosluk_doldurma",
  "baslik": "⬜ Boşluğu Doldur",
  "aciklama": "Metindeki eksik kelimeyi bul!",
  "sorular": [
    {{
      "cumle_bos": "Metinden alınan cümle ___ kelime yerine boş",
      "dogru": "doğru kelime",
      "secenekler": ["doğru kelime", "yanlış1", "yanlış2", "yanlış3"]
    }}
  ],
  "xp": 7
}}"""

    try:
        raw = await _gemini_call(prompt, max_tokens=1200)
        import json as _json, re as _re
        raw = raw.strip()
        if "```" in raw:
            m = _re.search(r"```(?:json)?\s*([\s\S]*?)```", raw)
            raw = m.group(1).strip() if m else _re.sub(r"```(?:json)?", "", raw).replace("```", "").strip()
        bs = raw.find("{"); be = raw.rfind("}")
        if bs != -1 and be != -1: raw = raw[bs:be+1]
        raw = _re.sub(r",\s*([}\]])", r"\1", raw)
        result = _json.loads(raw)
        return {"oyun": result}
    except Exception as e:
        logging.error(f"[KITAP-OYUN] Hata: {e}")
        return {"oyun": None, "mesaj": f"Oyun üretilemedi: {str(e)}"}



# ─────────────────────────────────────────────
# OKUMA EVRENİ — 5 Bölge Gamification
# ─────────────────────────────────────────────

OKUMA_EVRENI_BOLGELER = [
    {
        "id": "orman",
        "ad": "Orman Kitaplığı",
        "emoji": "🌲",
        "renk": "#22c55e",
        "aciklama": "Okuma yolculuğuna başladın!",
        "kriter": "baslangic",  # Herkes başlar
        "min_kitap": 0, "min_kelime": 0, "min_streak": 0, "min_bloom": 0,
    },
    {
        "id": "kelime_dag",
        "ad": "Kelime Dağları",
        "emoji": "⛰️",
        "renk": "#f59e0b",
        "aciklama": "50 kelime öğrendin!",
        "kriter": "kelime",
        "min_kitap": 0, "min_kelime": 50, "min_streak": 0, "min_bloom": 0,
    },
    {
        "id": "hikaye_limani",
        "ad": "Hikâye Limanı",
        "emoji": "⚓",
        "renk": "#3b82f6",
        "aciklama": "5 kitap/içerik tamamladın!",
        "kriter": "kitap",
        "min_kitap": 5, "min_kelime": 0, "min_streak": 0, "min_bloom": 0,
    },
    {
        "id": "bilgelik_kutuphane",
        "ad": "Bilgelik Kütüphanesi",
        "emoji": "🏰",
        "renk": "#8b5cf6",
        "aciklama": "Bloom %60 anlama seviyesine ulaştın!",
        "kriter": "bloom",
        "min_kitap": 5, "min_kelime": 100, "min_streak": 7, "min_bloom": 60,
    },
    {
        "id": "hayal_galaksisi",
        "ad": "Hayal Galaksisi",
        "emoji": "🚀",
        "renk": "#ec4899",
        "aciklama": "Tüm evrenin fethettdin! En yüksek seviye.",
        "kriter": "tumu",
        "min_kitap": 20, "min_kelime": 300, "min_streak": 30, "min_bloom": 80,
    },
]

@api_router.get("/ai/okuma-evreni/{ogrenci_id}")
async def okuma_evreni(ogrenci_id: str, current_user=Depends(get_current_user)):
    """Öğrencinin Okuma Evreni bölgesini ve ilerleme durumunu hesapla."""
    # İstatistikler
    logs = await db.reading_logs.find({"ogrenci_id": ogrenci_id}).to_list(length=None)
    tamamlananlar = await db.gelisim_tamamlananlar.find({"kullanici_id": ogrenci_id}).to_list(length=None)
    kelime_ogrenilen = await db.kelime_tekrar.count_documents({"ogrenci_id": ogrenci_id, "kutu": {"$gte": 3}})
    test_sonuclari = await db.kitap_test_sonuclari.find({"ogrenci_id": ogrenci_id}).to_list(length=None)

    # Streak hesapla
    from datetime import timedelta
    simdi = datetime.utcnow()
    tarihler = sorted(set(l.get("tarih", "")[:10] for l in logs), reverse=True)
    streak = 0
    for i in range(90):
        gun = (simdi - timedelta(days=i)).strftime("%Y-%m-%d")
        if gun in tarihler:
            streak += 1
        elif i > 0:
            break

    # Bloom ortalaması
    bloom_ortalama = 0
    if test_sonuclari:
        bloom_ortalama = sum(t.get("basari_yuzdesi", 0) for t in test_sonuclari) / len(test_sonuclari)

    # Tamamlanan içerik sayısı
    tamamlanan_sayi = len(tamamlananlar)

    # Mevcut bölgeyi hesapla
    aktif_bolge = OKUMA_EVRENI_BOLGELER[0]
    for bolge in reversed(OKUMA_EVRENI_BOLGELER):
        if (tamamlanan_sayi >= bolge["min_kitap"] and
            kelime_ogrenilen >= bolge["min_kelime"] and
            streak >= bolge["min_streak"] and
            bloom_ortalama >= bolge["min_bloom"]):
            aktif_bolge = bolge
            break

    # Sıradaki bölge
    aktif_idx = next((i for i, b in enumerate(OKUMA_EVRENI_BOLGELER) if b["id"] == aktif_bolge["id"]), 0)
    sonraki_bolge = OKUMA_EVRENI_BOLGELER[aktif_idx + 1] if aktif_idx < len(OKUMA_EVRENI_BOLGELER) - 1 else None

    # Sonraki bölgeye ilerleme yüzdesi
    ilerleme = {}
    if sonraki_bolge:
        hedefler = [
            ("kitap", tamamlanan_sayi, sonraki_bolge["min_kitap"]),
            ("kelime", kelime_ogrenilen, sonraki_bolge["min_kelime"]),
            ("streak", streak, sonraki_bolge["min_streak"]),
            ("bloom", round(bloom_ortalama), sonraki_bolge["min_bloom"]),
        ]
        for ad, mevcut, hedef in hedefler:
            if hedef > 0:
                ilerleme[ad] = {"mevcut": mevcut, "hedef": hedef, "yuzde": min(100, round(mevcut / hedef * 100))}

    return {
        "ogrenci_id": ogrenci_id,
        "aktif_bolge": aktif_bolge,
        "aktif_bolge_idx": aktif_idx,
        "sonraki_bolge": sonraki_bolge,
        "ilerleme": ilerleme,
        "tum_bolgeler": OKUMA_EVRENI_BOLGELER,
        "istatistikler": {
            "tamamlanan": tamamlanan_sayi,
            "kelime": kelime_ogrenilen,
            "streak": streak,
            "bloom": round(bloom_ortalama),
        }
    }


# ─────────────────────────────────────────────
# AI MOTİVASYON MOTORU — Mikro Hedef + Streak Koruma
# ─────────────────────────────────────────────



# ─────────────────────────────────────────────

# ─────────────────────────────────────────────
# AI GELİŞİM SİMÜLASYONU
# ─────────────────────────────────────────────

@api_router.get("/ai/gelisim-simulasyon/{ogrenci_id}")
async def gelisim_simulasyon(ogrenci_id: str, current_user=Depends(get_current_user)):
    """Mevcut verilerden 6 aylık gelişim projeksiyonu üretir."""
    v = await get_ogrenci_ai_verileri(ogrenci_id)
    if not v:
        return {"hata": "Öğrenci verisi bulunamadı"}

    streak = v["streak"].get("mevcut", 0)
    avg_dk = v["okuma_ozet"].get("ort_gunluk_dk", 0)
    kelime_sayisi = await db.kelime_tekrar.count_documents({"ogrenci_id": ogrenci_id})
    test_kayitlar = await db.kitap_test_sonuclari.find({"ogrenci_id": ogrenci_id}).sort("tarih", -1).to_list(length=20)
    bloom_ort = 0
    if test_kayitlar:
        bloom_ort = round(sum(k.get("basari_yuzdesi", 0) for k in test_kayitlar) / len(test_kayitlar))

    # Hedef okuma süreleri → projeksiyon
    senaryolar = []
    for hedef_dk in [5, 10, 15, 20]:
        gunluk = hedef_dk
        aylik_dk = gunluk * 22  # Haftada 5 gün
        alti_ay_dk = aylik_dk * 6
        mevcut = avg_dk or 1
        artis_oran = min(80, round((hedef_dk / max(mevcut, 1) - 1) * 30 + 15))
        kelime_kazanim = round(hedef_dk * 0.8 * 180)  # dk * kelime_hizi * gun
        bloom_artis = min(95, bloom_ort + round(artis_oran * 0.4))
        kitap_sayisi = round(alti_ay_dk / 90)  # Ortalama 90dk / kitap
        senaryolar.append({
            "hedef_dk": hedef_dk,
            "artis_yuzdesi": artis_oran,
            "kelime_kazanim": kelime_kazanim,
            "tahmini_kitap": kitap_sayisi,
            "bloom_tahmini": bloom_artis,
            "alti_ay_toplam_dk": alti_ay_dk,
        })

    # 6 aylık aylık projeksiyon (seçili hedef = 10 dk)
    aylik_projeksiyon = []
    baz_bloom = bloom_ort
    baz_kelime = kelime_sayisi
    for ay in range(1, 7):
        baz_bloom = min(95, baz_bloom + round((95 - baz_bloom) * 0.12))
        baz_kelime = baz_kelime + round(10 * 0.8 * 22 * ay * 0.15)
        aylik_projeksiyon.append({
            "ay": ay,
            "bloom_tahmini": baz_bloom,
            "kelime_tahmini": baz_kelime,
            "okunan_dk": 10 * 22 * ay,
        })

    return {
        "mevcut": {
            "streak": streak,
            "avg_dk": avg_dk,
            "kelime": kelime_sayisi,
            "bloom_ort": bloom_ort,
        },
        "senaryolar": senaryolar,
        "aylik_projeksiyon": aylik_projeksiyon,
        "ozet_mesaj": f"Şu an günde ortalama {avg_dk} dk okuyorsun. 10 dk/gün hedefiyle 6 ayda yaklaşık %{senaryolar[1]['artis_yuzdesi']} gelişim sağlarsın!",
    }


# ─────────────────────────────────────────────
# AI OKUMA TERAPİSİ — Erken Tespit
# ─────────────────────────────────────────────

@api_router.get("/ai/okuma-terapisi/{ogrenci_id}")
async def okuma_terapisi(ogrenci_id: str, current_user=Depends(get_current_user)):
    """Öğrenci verilerinden okuma güçlüğü sinyallerini tespit eder. TANI KOYMAZ, yönlendirir."""
    v = await get_ogrenci_ai_verileri(ogrenci_id)
    if not v:
        return {"sinyaller": [], "risk_seviyesi": "belirsiz", "oneri": "Veri yetersiz"}

    sinyaller = []
    risk_puan = 0

    # Streak düşüklüğü
    streak = v["streak"].get("mevcut", 0)
    if streak == 0:
        sinyaller.append({"tip": "motivasyon", "mesaj": "Son günlerde okuma aktivitesi yok", "agirlik": 2})
        risk_puan += 2

    # Okuma hızı analizi
    avg_dk = v["okuma_ozet"].get("ort_gunluk_dk", 0)
    if 0 < avg_dk < 5:
        sinyaller.append({"tip": "dikkat", "mesaj": "Çok kısa okuma süreleri (5 dk altı)", "agirlik": 3})
        risk_puan += 3

    # Test başarısı düşüklüğü
    test_kayitlar = await db.kitap_test_sonuclari.find({"ogrenci_id": ogrenci_id}).sort("tarih", -1).to_list(length=10)
    if test_kayitlar:
        bloom_ort = sum(k.get("basari_yuzdesi", 0) for k in test_kayitlar) / len(test_kayitlar)
        if bloom_ort < 40:
            sinyaller.append({"tip": "anlama", "mesaj": f"Anlama testlerinde düşük başarı (ort. %{round(bloom_ort)})", "agirlik": 4})
            risk_puan += 4
        # Bilgi ve kavrama basamaklarında bile düşüklük → potansiyel kelime zorluğu
        bilgi_sorulari = [k for k in test_kayitlar if k.get("taksonomi") in ["bilgi", "kavrama"]]
        if bilgi_sorulari:
            bilgi_ort = sum(k.get("dogru_mu", False) for k in bilgi_sorulari) / len(bilgi_sorulari) * 100
            if bilgi_ort < 50:
                sinyaller.append({"tip": "kelime_kacinma", "mesaj": "Temel anlama sorularında zorluk — kelime dağarcığı desteği gerekebilir", "agirlik": 3})
                risk_puan += 3

    # Kelime tekrar analizi
    kelime_sayisi = await db.kelime_tekrar.count_documents({"ogrenci_id": ogrenci_id})
    tekrar_yuksek = await db.kelime_tekrar.count_documents({"ogrenci_id": ogrenci_id, "tekrar_sayisi": {"$gte": 5}})
    if kelime_sayisi > 0 and tekrar_yuksek / max(kelime_sayisi, 1) > 0.4:
        sinyaller.append({"tip": "kelime_hafiza", "mesaj": "Kelimeleri hatırlamada tekrar eden güçlük", "agirlik": 2})
        risk_puan += 2

    # Okuma kayıtlarında geri dönüş / kısa oturum patikası
    okuma_log = await db.reading_logs.find({"ogrenci_id": ogrenci_id}).sort("tarih", -1).to_list(length=20)
    if len(okuma_log) >= 5:
        kisa_oturumlar = [l for l in okuma_log if (l.get("sure_dakika", 10)) < 3]
        if len(kisa_oturumlar) > len(okuma_log) * 0.5:
            sinyaller.append({"tip": "dikkat_suresi", "mesaj": "Okuma oturumları çok kısa kesiyor (dikkat dağılması belirtisi)", "agirlik": 3})
            risk_puan += 3

    # Risk seviyesi hesapla
    if risk_puan >= 8:
        risk_seviyesi = "yuksek"
        oneri = "Bu öğrenci için uzman yönlendirmesi düşünülebilir. Okuma güçlüğü belirtileri gözlemleniyor — lütfen bir okuma uzmanı veya rehber öğretmenle görüşün."
    elif risk_puan >= 4:
        risk_seviyesi = "orta"
        oneri = "Öğrencinin okuma alışkanlıkları dikkat gerektiriyor. Birebir destek ve farklı materyaller deneyin."
    elif risk_puan >= 1:
        risk_seviyesi = "dusuk"
        oneri = "Küçük sinyaller var. Düzenli takip ve teşvik yeterli olabilir."
    else:
        risk_seviyesi = "normal"
        oneri = "Belirgin bir okuma güçlüğü sinyali tespit edilmedi."

    return {
        "ogrenci_id": ogrenci_id,
        "risk_seviyesi": risk_seviyesi,
        "risk_puan": risk_puan,
        "sinyaller": sinyaller,
        "oneri": oneri,
        "uyari": "⚠️ Bu sistem TANI KOYMAZ. Sadece gözlem ve yönlendirme aracıdır.",
        "tarih": datetime.utcnow().isoformat(),
    }


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

@api_router.get("/gelisim/icerik/{icerik_id}/etki")
async def icerik_etki_istatistikleri(icerik_id: str, current_user=Depends(get_current_user)):
    """Bir içeriğin etkisini göster: kaç öğrenci tamamladı, materyal, oyun, post-reading."""
    tamamlayan = await db.gelisim_tamamlama.count_documents({"icerik_id": icerik_id})
    materyal_sayisi = await db.ai_materyal_log.count_documents({"icerik_id": icerik_id})
    oyun_sayisi = await db.ai_oyun_log.count_documents({"icerik_id": icerik_id})
    post_reading = await db.post_reading_cache.count_documents({"icerik_id": icerik_id})
    zeka_harita = await db.kitap_zeka_haritasi.count_documents({"icerik_id": icerik_id})

    # Bloom ortalaması
    testler = await db.kitap_test_sonuclari.find({"icerik_id": icerik_id}).to_list(length=100)
    bloom_ort = 0
    if testler:
        dogru_list = [t.get("dogru", 0) for t in testler if t.get("toplam", 0) > 0]
        if dogru_list:
            toplam_list = [t.get("toplam", 1) for t in testler if t.get("toplam", 0) > 0]
            bloom_ort = round(sum(d/t for d,t in zip(dogru_list, toplam_list)) / len(dogru_list) * 100)

    return {
        "icerik_id": icerik_id,
        "tamamlayan_ogrenci": tamamlayan,
        "uretilen_materyal": materyal_sayisi,
        "oynanan_oyun": oyun_sayisi,
        "post_reading_analiz": post_reading,
        "zeka_harita": 1 if zeka_harita > 0 else 0,
        "bloom_ort": bloom_ort,
    }


@api_router.get("/gelisim/etki-ozet")
async def etki_ozet(current_user=Depends(get_current_user)):
    """Öğretmenin eklediği tüm içeriklerin toplam etkisi."""
    user_id = current_user.get("id", "")
    icerikler = await db.gelisim_icerik.find({"ekleyen_id": user_id}).to_list(length=None)
    icerik_idler = [i["id"] for i in icerikler if i.get("id")]

    toplam_tamamlayan = 0
    toplam_materyal = 0
    en_cok = None
    en_cok_sayi = 0

    for ic in icerikler:
        iid = ic.get("id", "")
        sayi = await db.gelisim_tamamlama.count_documents({"icerik_id": iid})
        toplam_tamamlayan += sayi
        mat = await db.ai_materyal_log.count_documents({"icerik_id": iid})
        toplam_materyal += mat
        if sayi > en_cok_sayi:
            en_cok_sayi = sayi
            en_cok = ic.get("baslik", "")

    return {
        "toplam_icerik": len(icerikler),
        "toplam_tamamlayan": toplam_tamamlayan,
        "toplam_materyal": toplam_materyal,
        "en_populer_icerik": en_cok,
        "en_populer_tamamlayan": en_cok_sayi,
    }


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
