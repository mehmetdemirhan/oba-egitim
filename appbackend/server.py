from fastapi import FastAPI, APIRouter, HTTPException, Depends, status, Body
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
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

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# JWT Config
SECRET_KEY = os.environ.get('SECRET_KEY', 'okuma-becerileri-secret-key-change-in-production')
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get('ACCESS_TOKEN_EXPIRE_MINUTES', '60'))

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

# Create the main app without a prefix
app = FastAPI(title="Okuma Becerileri Akademisi API")

# ★ CORS — En güvenilir yapılandırma
# NOT: allow_origins=["*"] ve allow_credentials=True birlikte kullanılamaz.
# Bu yüzden ya credentials kapatılır ya da origin spesifik yazılır.
# Render'da en güvenilir yol: origin'i dinamik olarak echo etmek.

ALLOWED_ORIGINS = {
    "https://oba-egitim-frontend.onrender.com",
    "http://localhost:3000",
    "http://localhost:3001",
}

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

class CustomCORSMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        origin = request.headers.get("origin", "")
        is_allowed = origin in ALLOWED_ORIGINS or origin.endswith(".onrender.com")

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
# ENUMS
# ─────────────────────────────────────────────

class TeacherLevel(str, Enum):
    YENI = "yeni"
    UZMAN = "uzman"

class UserRole(str, Enum):
    ADMIN = "admin"
    COORDINATOR = "coordinator"
    TEACHER = "teacher"
    STUDENT = "student"
    PARENT = "parent"

# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def prepare_for_mongo(data):
    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, datetime):
                data[key] = value.isoformat()
            elif isinstance(value, dict):
                data[key] = prepare_for_mongo(value)
            elif isinstance(value, list):
                data[key] = [prepare_for_mongo(item) if isinstance(item, dict) else item for item in value]
    return data

def parse_from_mongo(item):
    if isinstance(item, dict):
        for key, value in item.items():
            if key.endswith('_tarihi') or key in ('olusturma_tarihi', 'tarih'):
                if isinstance(value, str):
                    try:
                        item[key] = datetime.fromisoformat(value)
                    except:
                        pass
            elif isinstance(value, dict):
                item[key] = parse_from_mongo(value)
            elif isinstance(value, list):
                item[key] = [parse_from_mongo(s) if isinstance(s, dict) else s for s in value]
    return item

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Geçersiz veya süresi dolmuş token",
            headers={"WWW-Authenticate": "Bearer"},
        )

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    payload = decode_token(credentials.credentials)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Geçersiz token")
    user = await db.users.find_one({"id": user_id})
    if not user:
        raise HTTPException(status_code=401, detail="Kullanıcı bulunamadı")
    return user

def require_role(*roles: UserRole):
    async def checker(current_user=Depends(get_current_user)):
        if current_user.get("role") not in [r.value for r in roles]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bu işlem için yetkiniz yok"
            )
        return current_user
    return checker

# ─────────────────────────────────────────────
# AUTH MODELS
# ─────────────────────────────────────────────

class UserCreate(BaseModel):
    ad: str
    soyad: str
    email: str
    password: str
    role: UserRole
    telefon: Optional[str] = None
    linked_id: Optional[str] = None  # teacher_id, student_id or parent's student_id

class UserLogin(BaseModel):
    email_or_phone: Optional[str] = None
    email: Optional[str] = None  # eski frontend uyumluluğu
    password: str

class UserResponse(BaseModel):
    id: str
    ad: str
    soyad: str
    email: str
    role: UserRole
    telefon: Optional[str] = None
    linked_id: Optional[str] = None
    olusturma_tarihi: datetime
    puan: int = 0

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

class ChangePassword(BaseModel):
    old_password: str
    new_password: str

# ─────────────────────────────────────────────
# AUTH ROUTES
# ─────────────────────────────────────────────

@api_router.post("/auth/login", response_model=TokenResponse)
async def login(credentials: UserLogin):
    girdi = (credentials.email_or_phone or credentials.email or "").lower().strip()
    if not girdi:
        raise HTTPException(status_code=400, detail="E-posta veya telefon gerekli")
    # Email veya telefon ile kullanıcı bul
    user = await db.users.find_one({"email": girdi})
    if not user:
        user = await db.users.find_one({"telefon": girdi})
    if not user or not verify_password(credentials.password, user.get("password_hash", "")):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="E-posta/telefon veya şifre hatalı"
        )
    
    token = create_access_token({"sub": user["id"], "role": user["role"]})
    
    user_response = UserResponse(
        id=user["id"],
        ad=user["ad"],
        soyad=user["soyad"],
        email=user["email"],
        role=user["role"],
        telefon=user.get("telefon"),
        linked_id=user.get("linked_id"),
        olusturma_tarihi=datetime.fromisoformat(user["olusturma_tarihi"]) if isinstance(user.get("olusturma_tarihi"), str) else user.get("olusturma_tarihi", datetime.now(timezone.utc)),
        puan=user.get("puan", 0)
    )
    
    return TokenResponse(access_token=token, user=user_response)

@api_router.get("/auth/me", response_model=UserResponse)
async def get_me(current_user=Depends(get_current_user)):
    return UserResponse(
        id=current_user["id"],
        ad=current_user["ad"],
        soyad=current_user["soyad"],
        email=current_user["email"],
        role=current_user["role"],
        telefon=current_user.get("telefon"),
        linked_id=current_user.get("linked_id"),
        olusturma_tarihi=datetime.fromisoformat(current_user["olusturma_tarihi"]) if isinstance(current_user.get("olusturma_tarihi"), str) else current_user.get("olusturma_tarihi", datetime.now(timezone.utc)),
        puan=current_user.get("puan", 0)
    )

@api_router.post("/auth/forgot-password")
async def forgot_password(data: dict = Body(...)):
    email_or_phone = data.get("email_or_phone", "").lower().strip()
    if not email_or_phone:
        raise HTTPException(status_code=400, detail="E-posta veya telefon giriniz")
    user = await db.users.find_one({"email": email_or_phone})
    if not user:
        user = await db.users.find_one({"telefon": email_or_phone})
    if not user:
        raise HTTPException(status_code=404, detail="Bu bilgilerle kayıtlı kullanıcı bulunamadı")
    # 6 haneli geçici şifre oluştur
    gecici_sifre = str(random.randint(100000, 999999))
    new_hash = hash_password(gecici_sifre)
    await db.users.update_one({"id": user["id"]}, {"$set": {"password_hash": new_hash}})
    # NOT: Gerçek uygulamada burada e-posta veya SMS gönderilir
    # Şimdilik geçici şifreyi response'da döndürüyoruz (geliştirme aşaması)
    return {
        "message": f"Geçici şifre oluşturuldu",
        "gecici_sifre": gecici_sifre,
        "kullanici": f"{user['ad']} {user['soyad']}",
        "email": user.get("email", ""),
        "telefon": user.get("telefon", ""),
    }

@api_router.post("/auth/change-password")
async def change_password(data: ChangePassword, current_user=Depends(get_current_user)):
    if not verify_password(data.old_password, current_user.get("password_hash", "")):
        raise HTTPException(status_code=400, detail="Mevcut şifre hatalı")
    
    new_hash = hash_password(data.new_password)
    await db.users.update_one(
        {"id": current_user["id"]},
        {"$set": {"password_hash": new_hash}}
    )
    return {"message": "Şifre başarıyla güncellendi"}

# Admin: kullanıcı oluşturma (sadece admin)
@api_router.post("/auth/users", response_model=UserResponse)
async def create_user(
    user_data: UserCreate,
    current_user=Depends(require_role(UserRole.ADMIN))
):
    # Email kontrolü
    existing = await db.users.find_one({"email": user_data.email.lower().strip()})
    if existing:
        raise HTTPException(status_code=400, detail="Bu e-posta zaten kayıtlı")
    
    user_doc = {
        "id": str(uuid.uuid4()),
        "ad": user_data.ad,
        "soyad": user_data.soyad,
        "email": user_data.email.lower().strip(),
        "telefon": user_data.telefon.strip() if user_data.telefon else None,
        "password_hash": hash_password(user_data.password),
        "role": user_data.role.value,
        "linked_id": user_data.linked_id,
        "olusturma_tarihi": datetime.now(timezone.utc).isoformat()
    }
    await db.users.insert_one(user_doc)
    
    return UserResponse(
        id=user_doc["id"],
        ad=user_doc["ad"],
        soyad=user_doc["soyad"],
        email=user_doc["email"],
        role=user_doc["role"],
        linked_id=user_doc.get("linked_id"),
        olusturma_tarihi=datetime.now(timezone.utc)
    )

@api_router.get("/auth/users", response_model=List[UserResponse])
async def list_users(current_user=Depends(require_role(UserRole.ADMIN))):
    users = await db.users.find().to_list(length=None)
    result = []
    for u in users:
        result.append(UserResponse(
            id=u["id"],
            ad=u["ad"],
            soyad=u["soyad"],
            email=u["email"],
            role=u["role"],
            telefon=u.get("telefon"),
            linked_id=u.get("linked_id"),
            olusturma_tarihi=datetime.fromisoformat(u["olusturma_tarihi"]) if isinstance(u.get("olusturma_tarihi"), str) else datetime.now(timezone.utc),
            puan=u.get("puan", 0)
        ))
    return result

@api_router.delete("/auth/users/{user_id}")
async def delete_user(user_id: str, current_user=Depends(require_role(UserRole.ADMIN))):
    if user_id == current_user["id"]:
        raise HTTPException(status_code=400, detail="Kendi hesabınızı silemezsiniz")
    result = await db.users.delete_one({"id": user_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı")
    return {"message": "Kullanıcı silindi"}

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

# ─────────────────────────────────────────────
# MEVCUT MODELLER (değişmeden korunuyor)
# ─────────────────────────────────────────────

class Teacher(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    ad: str
    soyad: str
    brans: str
    telefon: str
    seviye: TeacherLevel
    ogrenci_sayisi: int = 0
    atanan_ogrenciler: List[str] = []
    yapilmasi_gereken_odeme: float = 0.0
    yapilan_odeme: float = 0.0
    arsivli: bool = False
    olusturma_tarihi: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def tam_ad(self):
        return f"{self.ad} {self.soyad}"

    @property
    def borc(self):
        has_students = self.ogrenci_sayisi > 0 or len(self.atanan_ogrenciler) > 0
        if not has_students:
            return 0.0
        return max(0, self.yapilmasi_gereken_odeme - self.yapilan_odeme)

class TeacherCreate(BaseModel):
    ad: str
    soyad: str
    brans: str
    telefon: str
    seviye: TeacherLevel
    yapilmasi_gereken_odeme: float = 0.0

class TeacherUpdate(BaseModel):
    ad: Optional[str] = None
    soyad: Optional[str] = None
    brans: Optional[str] = None
    telefon: Optional[str] = None
    seviye: Optional[TeacherLevel] = None
    yapilmasi_gereken_odeme: Optional[float] = None
    yapilan_odeme: Optional[float] = None
    arsivli: Optional[bool] = None

class Student(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    ad: str
    soyad: str
    sinif: str
    veli_ad: str
    veli_soyad: str
    veli_telefon: str
    aldigi_egitim: str
    kur: str
    yapilmasi_gereken_odeme: float = 0.0
    yapilan_odeme: float = 0.0
    ogretmene_yapilacak_odeme: float = 0.0
    ogretmen_id: Optional[str] = None
    arsivli: bool = False
    olusturma_tarihi: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class StudentCreate(BaseModel):
    ad: str
    soyad: str
    sinif: str
    veli_ad: str
    veli_soyad: str
    veli_telefon: str
    aldigi_egitim: str
    kur: str
    yapilmasi_gereken_odeme: float = 0.0
    ogretmene_yapilacak_odeme: float = 0.0
    ogretmen_id: Optional[str] = None

class StudentUpdate(BaseModel):
    ad: Optional[str] = None
    soyad: Optional[str] = None
    sinif: Optional[str] = None
    veli_ad: Optional[str] = None
    veli_soyad: Optional[str] = None
    veli_telefon: Optional[str] = None
    aldigi_egitim: Optional[str] = None
    kur: Optional[str] = None
    yapilmasi_gereken_odeme: Optional[float] = None
    yapilan_odeme: Optional[float] = None
    ogretmene_yapilacak_odeme: Optional[float] = None
    ogretmen_id: Optional[str] = None
    arsivli: Optional[bool] = None

class Course(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    ad: str
    fiyat: float
    sure: int
    olusturma_tarihi: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    ogrenci_sayisi: int = 0
    arsivli: bool = False

class CourseCreate(BaseModel):
    ad: str
    fiyat: float
    sure: int

class CourseUpdate(BaseModel):
    ad: Optional[str] = None
    fiyat: Optional[float] = None
    sure: Optional[int] = None
    arsivli: Optional[bool] = None

# ── Ders ve İçerik Modelleri ──
class DersIcerik(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tur: str  # video, pdf, docx
    baslik: str
    url: str = ""
    ozet: str = ""

class Ders(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    kurs_id: str
    baslik: str
    sira: int = 0
    ozet: str = ""
    icerikler: List[DersIcerik] = []
    olusturma_tarihi: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class DersCreate(BaseModel):
    baslik: str
    sira: int = 0
    ozet: str = ""

class DersUpdate(BaseModel):
    baslik: Optional[str] = None
    sira: Optional[int] = None
    ozet: Optional[str] = None

class DersIcerikCreate(BaseModel):
    tur: str
    baslik: str
    url: str = ""
    ozet: str = ""

class Payment(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tip: str
    kisi_id: str
    miktar: float
    aciklama: Optional[str] = None
    tarih: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class PaymentCreate(BaseModel):
    tip: str
    kisi_id: str
    miktar: float
    aciklama: Optional[str] = None

class DashboardStats(BaseModel):
    toplam_ogretmen: int
    toplam_ogrenci: int
    toplam_kurs: int
    toplam_ogrenci_alacak: float
    toplam_ogretmen_borc: float
    bu_ay_odenen_toplam: float

class WeeklyStats(BaseModel):
    hafta: str
    yeni_ogrenciler: int
    odemeler: float
    gelir: float

class MonthlyStats(BaseModel):
    ay: str
    yeni_ogrenciler: int
    odemeler: float
    gelir: float
    toplam_borc: float

class ExportData(BaseModel):
    ogretmenler: List[dict]
    ogrenciler: List[dict]
    kurslar: List[dict]
    odemeler: List[dict]

# ─────────────────────────────────────────────
# MEVCUT ROUTE'LAR (değişmeden korunuyor)
# ─────────────────────────────────────────────

@api_router.get("/dashboard", response_model=DashboardStats)
async def get_dashboard_stats():
    teacher_count = await db.teachers.count_documents({})
    student_count = await db.students.count_documents({})
    course_count = await db.courses.count_documents({})
    teachers = await db.teachers.find().to_list(length=None)
    students = await db.students.find().to_list(length=None)
    total_student_receivable = sum(max(0, s.get('yapilmasi_gereken_odeme', 0) - s.get('yapilan_odeme', 0)) for s in students)
    total_teacher_debt = 0
    for t in teachers:
        has_students = t.get('ogrenci_sayisi', 0) > 0 or len(t.get('atanan_ogrenciler', [])) > 0
        if has_students:
            total_teacher_debt += max(0, t.get('yapilmasi_gereken_odeme', 0) - t.get('yapilan_odeme', 0))
    current_month_start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    monthly_payments = await db.payments.find({"tarih": {"$gte": current_month_start.isoformat()}}).to_list(length=None)
    monthly_total = sum(p.get('miktar', 0) for p in monthly_payments)
    return DashboardStats(
        toplam_ogretmen=teacher_count,
        toplam_ogrenci=student_count,
        toplam_kurs=course_count,
        toplam_ogrenci_alacak=total_student_receivable,
        toplam_ogretmen_borc=total_teacher_debt,
        bu_ay_odenen_toplam=monthly_total
    )


@api_router.get("/dashboard/bekleyenler")
async def get_bekleyenler(current_user=Depends(require_role(UserRole.ADMIN, UserRole.COORDINATOR))):
    # Analiz metinleri - beklemede olanlar
    metin_bekleyen = await db.analiz_metinler.find({"durum": "beklemede"}).sort("olusturma_tarihi", -1).to_list(length=None)
    metin_oylama = await db.analiz_metinler.find({"durum": "oylama"}).sort("olusturma_tarihi", -1).to_list(length=None)
    # Gelişim araçları - beklemede olanlar
    gelisim_bekleyen = await db.gelisim_icerik.find({"durum": "beklemede"}).sort("olusturma_tarihi", -1).to_list(length=None)
    gelisim_oylama = await db.gelisim_icerik.find({"durum": "oylama"}).sort("olusturma_tarihi", -1).to_list(length=None)

    # Kitaplar - beklemede olanlar
    kitap_bekleyen = await db.kitaplar.find({"durum": "beklemede"}).sort("olusturma_tarihi", -1).to_list(length=None)
    kitap_oylama = await db.kitaplar.find({"durum": "oylama"}).sort("olusturma_tarihi", -1).to_list(length=None)

    for lst in [metin_bekleyen, metin_oylama, gelisim_bekleyen, gelisim_oylama, kitap_bekleyen, kitap_oylama]:
        for item in lst:
            item.pop("_id", None)
            item.pop("icerik", None)

    return {
        "metin_bekleyen": metin_bekleyen,
        "metin_oylama": metin_oylama,
        "gelisim_bekleyen": gelisim_bekleyen,
        "gelisim_oylama": gelisim_oylama,
        "kitap_bekleyen": kitap_bekleyen,
        "kitap_oylama": kitap_oylama,
        "toplam": len(metin_bekleyen) + len(metin_oylama) + len(gelisim_bekleyen) + len(gelisim_oylama) + len(kitap_bekleyen) + len(kitap_oylama)
    }

@api_router.get("/stats/weekly", response_model=List[WeeklyStats])
async def get_weekly_stats():
    from datetime import timedelta
    stats = []
    now = datetime.now(timezone.utc)
    for i in range(12):
        week_start = now - timedelta(weeks=i+1)
        week_end = now - timedelta(weeks=i)
        students_this_week = await db.students.find({"olusturma_tarihi": {"$gte": week_start.isoformat(), "$lt": week_end.isoformat()}}).to_list(length=None)
        payments_this_week = await db.payments.find({"tarih": {"$gte": week_start.isoformat(), "$lt": week_end.isoformat()}}).to_list(length=None)
        stats.append(WeeklyStats(
            hafta=f"{week_start.strftime('%d/%m')} - {week_end.strftime('%d/%m')}",
            yeni_ogrenciler=len(students_this_week),
            odemeler=sum(p.get('miktar', 0) for p in payments_this_week),
            gelir=sum(s.get('yapilmasi_gereken_odeme', 0) for s in students_this_week)
        ))
    return list(reversed(stats))

@api_router.get("/stats/monthly", response_model=List[MonthlyStats])
async def get_monthly_stats():
    from datetime import timedelta
    stats = []
    now = datetime.now(timezone.utc)
    for i in range(6):
        if i == 0:
            month_end = now
        else:
            month_end = now.replace(day=1) - timedelta(days=1)
            for j in range(i-1):
                month_end = month_end.replace(day=1) - timedelta(days=1)
                month_end = month_end.replace(day=28)
        month_start = month_end.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        students_this_month = await db.students.find({"olusturma_tarihi": {"$gte": month_start.isoformat(), "$lt": month_end.isoformat()}}).to_list(length=None)
        payments_this_month = await db.payments.find({"tarih": {"$gte": month_start.isoformat(), "$lt": month_end.isoformat()}}).to_list(length=None)
        students_total = await db.students.find({"olusturma_tarihi": {"$lt": month_end.isoformat()}}).to_list(length=None)
        stats.append(MonthlyStats(
            ay=month_start.strftime('%B %Y'),
            yeni_ogrenciler=len(students_this_month),
            odemeler=sum(p.get('miktar', 0) for p in payments_this_month),
            gelir=sum(s.get('yapilmasi_gereken_odeme', 0) for s in students_this_month),
            toplam_borc=sum(max(0, s.get('yapilmasi_gereken_odeme', 0) - s.get('yapilan_odeme', 0)) for s in students_total)
        ))
    return list(reversed(stats))

@api_router.post("/teachers", response_model=Teacher)
async def create_teacher(teacher_data: TeacherCreate):
    teacher = Teacher(**teacher_data.dict())
    await db.teachers.insert_one(prepare_for_mongo(teacher.dict()))
    return teacher

@api_router.get("/teachers", response_model=List[Teacher])
async def get_teachers():
    teachers = await db.teachers.find().to_list(length=None)
    result = []
    for teacher in teachers:
        real_count = await db.students.count_documents({"ogretmen_id": teacher['id']})
        teacher['ogrenci_sayisi'] = real_count
        if teacher.get('ogrenci_sayisi', 0) != real_count:
            await db.teachers.update_one({"id": teacher['id']}, {"$set": {"ogrenci_sayisi": real_count}})
        result.append(Teacher(**parse_from_mongo(teacher)))
    return result

@api_router.get("/teachers/{teacher_id}", response_model=Teacher)
async def get_teacher(teacher_id: str):
    teacher = await db.teachers.find_one({"id": teacher_id})
    if not teacher:
        raise HTTPException(status_code=404, detail="Öğretmen bulunamadı")
    return Teacher(**parse_from_mongo(teacher))

@api_router.get("/teachers/{teacher_id}/students", response_model=List[Student])
async def get_teacher_students(teacher_id: str):
    teacher = await db.teachers.find_one({"id": teacher_id})
    if not teacher:
        raise HTTPException(status_code=404, detail="Öğretmen bulunamadı")
    students = await db.students.find({"ogretmen_id": teacher_id}).to_list(length=None)
    return [Student(**parse_from_mongo(s)) for s in students]

@api_router.put("/teachers/{teacher_id}", response_model=Teacher)
async def update_teacher(teacher_id: str, teacher_update: TeacherUpdate):
    update_data = teacher_update.dict(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="Güncellenecek veri bulunamadı")
    result = await db.teachers.update_one({"id": teacher_id}, {"$set": update_data})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Öğretmen bulunamadı")
    teacher = await db.teachers.find_one({"id": teacher_id})
    return Teacher(**parse_from_mongo(teacher))

@api_router.delete("/teachers/{teacher_id}")
async def delete_teacher(teacher_id: str):
    result = await db.teachers.delete_one({"id": teacher_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Öğretmen bulunamadı")
    return {"message": "Öğretmen başarıyla silindi"}

@api_router.post("/students", response_model=Student)
async def create_student(student_data: StudentCreate):
    student = Student(**student_data.dict())
    await db.students.insert_one(prepare_for_mongo(student.dict()))
    if student.ogretmen_id:
        teacher = await db.teachers.find_one({"id": student.ogretmen_id})
        if teacher:
            await db.teachers.update_one(
                {"id": student.ogretmen_id},
                {"$inc": {"ogrenci_sayisi": 1, "yapilmasi_gereken_odeme": student.ogretmene_yapilacak_odeme},
                 "$addToSet": {"atanan_ogrenciler": student.id}}
            )
    # ★ Otomatik muhasebe kaydı: öğrenci alacak kaydı
    if student.yapilmasi_gereken_odeme and student.yapilmasi_gereken_odeme > 0:
        alacak_kaydi = {
            "id": str(uuid.uuid4()),
            "tip": "ogrenci",
            "kisi_id": student.id,
            "miktar": student.yapilmasi_gereken_odeme,
            "aciklama": f"Kayıt ücreti — {student.ad} {student.soyad}",
            "tarih": datetime.now(timezone.utc).isoformat(),
        }
        await db.payments.insert_one(alacak_kaydi)
    # ★ Otomatik muhasebe kaydı: öğretmene yapılacak ödeme
    if student.ogretmen_id and student.ogretmene_yapilacak_odeme and student.ogretmene_yapilacak_odeme > 0:
        ogretmen_kaydi = {
            "id": str(uuid.uuid4()),
            "tip": "ogretmen",
            "kisi_id": student.ogretmen_id,
            "miktar": student.ogretmene_yapilacak_odeme,
            "aciklama": f"Öğretmen ücreti — {student.ad} {student.soyad}",
            "tarih": datetime.now(timezone.utc).isoformat(),
        }
        await db.payments.insert_one(ogretmen_kaydi)
    return student

@api_router.get("/students", response_model=List[Student])
async def get_students():
    students = await db.students.find().to_list(length=None)
    return [Student(**parse_from_mongo(s)) for s in students]

@api_router.get("/students/{student_id}", response_model=Student)
async def get_student(student_id: str):
    student = await db.students.find_one({"id": student_id})
    if not student:
        raise HTTPException(status_code=404, detail="Öğrenci bulunamadı")
    return Student(**parse_from_mongo(student))

@api_router.put("/students/{student_id}", response_model=Student)
async def update_student(student_id: str, student_update: StudentUpdate):
    update_data = student_update.dict(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="Güncellenecek veri bulunamadı")
    old_student = await db.students.find_one({"id": student_id})
    if not old_student:
        raise HTTPException(status_code=404, detail="Öğrenci bulunamadı")
    old_teacher_id = old_student.get('ogretmen_id')
    new_teacher_id = update_data.get('ogretmen_id')
    old_payment = old_student.get('ogretmene_yapilacak_odeme', 0)
    new_payment = update_data.get('ogretmene_yapilacak_odeme', old_payment)
    await db.students.update_one({"id": student_id}, {"$set": update_data})
    if old_teacher_id != new_teacher_id:
        if old_teacher_id:
            await db.teachers.update_one({"id": old_teacher_id}, {"$inc": {"ogrenci_sayisi": -1, "yapilmasi_gereken_odeme": -old_payment}, "$pull": {"atanan_ogrenciler": student_id}})
        if new_teacher_id:
            await db.teachers.update_one({"id": new_teacher_id}, {"$inc": {"ogrenci_sayisi": 1, "yapilmasi_gereken_odeme": new_payment}, "$addToSet": {"atanan_ogrenciler": student_id}})
    elif old_teacher_id and old_payment != new_payment:
        await db.teachers.update_one({"id": old_teacher_id}, {"$inc": {"yapilmasi_gereken_odeme": new_payment - old_payment}})
    student = await db.students.find_one({"id": student_id})
    return Student(**parse_from_mongo(student))

@api_router.delete("/students/{student_id}")
async def delete_student(student_id: str):
    student = await db.students.find_one({"id": student_id})
    if not student:
        raise HTTPException(status_code=404, detail="Öğrenci bulunamadı")
    if student.get('ogretmen_id'):
        teacher = await db.teachers.find_one({"id": student['ogretmen_id']})
        if teacher:
            await db.teachers.update_one(
                {"id": student['ogretmen_id']},
                {"$inc": {"ogrenci_sayisi": -1, "yapilmasi_gereken_odeme": -student.get('ogretmene_yapilacak_odeme', 0)},
                 "$pull": {"atanan_ogrenciler": student_id}}
            )
    await db.students.delete_one({"id": student_id})
    return {"message": "Öğrenci başarıyla silindi"}

@api_router.post("/courses", response_model=Course)
async def create_course(course_data: CourseCreate):
    course = Course(**course_data.dict())
    await db.courses.insert_one(prepare_for_mongo(course.dict()))
    return course

@api_router.get("/courses", response_model=List[Course])
async def get_courses():
    courses = await db.courses.find().to_list(length=None)
    return [Course(**parse_from_mongo(c)) for c in courses]

@api_router.get("/courses/{course_id}", response_model=Course)
async def get_course(course_id: str):
    course = await db.courses.find_one({"id": course_id})
    if not course:
        raise HTTPException(status_code=404, detail="Kurs bulunamadı")
    return Course(**parse_from_mongo(course))

@api_router.put("/courses/{course_id}", response_model=Course)
async def update_course(course_id: str, course_update: CourseUpdate):
    update_data = course_update.dict(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="Güncellenecek veri bulunamadı")
    result = await db.courses.update_one({"id": course_id}, {"$set": update_data})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Kurs bulunamadı")
    course = await db.courses.find_one({"id": course_id})
    return Course(**parse_from_mongo(course))

@api_router.delete("/courses/{course_id}")
async def delete_course(course_id: str):
    result = await db.courses.delete_one({"id": course_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Kurs bulunamadı")
    return {"message": "Kurs başarıyla silindi"}

# ── Ders Endpoints ──
@api_router.get("/courses/{kurs_id}/dersler")
async def get_dersler(kurs_id: str):
    dersler = await db.dersler.find({"kurs_id": kurs_id}).sort("sira", 1).to_list(length=None)
    for d in dersler:
        d.pop("_id", None)
    return dersler

@api_router.post("/courses/{kurs_id}/dersler")
async def create_ders(kurs_id: str, data: DersCreate, current_user=Depends(get_current_user)):
    ders_doc = {
        "id": str(uuid.uuid4()),
        "kurs_id": kurs_id,
        "baslik": data.baslik,
        "sira": data.sira,
        "ozet": data.ozet,
        "icerikler": [],
        "olusturma_tarihi": datetime.utcnow().isoformat(),
    }
    await db.dersler.insert_one(ders_doc)
    ders_doc.pop("_id", None)
    return ders_doc

@api_router.put("/dersler/{ders_id}")
async def update_ders(ders_id: str, data: DersUpdate, current_user=Depends(get_current_user)):
    update = data.dict(exclude_unset=True)
    if update:
        await db.dersler.update_one({"id": ders_id}, {"$set": update})
    ders = await db.dersler.find_one({"id": ders_id})
    if ders:
        ders.pop("_id", None)
    return ders

@api_router.delete("/dersler/{ders_id}")
async def delete_ders(ders_id: str, current_user=Depends(get_current_user)):
    await db.dersler.delete_one({"id": ders_id})
    return {"message": "Ders silindi"}

@api_router.post("/dersler/{ders_id}/icerik")
async def add_ders_icerik(ders_id: str, data: DersIcerikCreate, current_user=Depends(get_current_user)):
    icerik = {
        "id": str(uuid.uuid4()),
        "tur": data.tur,
        "baslik": data.baslik,
        "url": data.url,
        "ozet": data.ozet,
    }
    await db.dersler.update_one({"id": ders_id}, {"$push": {"icerikler": icerik}})
    return icerik

@api_router.delete("/dersler/{ders_id}/icerik/{icerik_id}")
async def delete_ders_icerik(ders_id: str, icerik_id: str, current_user=Depends(get_current_user)):
    await db.dersler.update_one({"id": ders_id}, {"$pull": {"icerikler": {"id": icerik_id}}})
    return {"message": "İçerik silindi"}

@api_router.post("/payments", response_model=Payment)
async def create_payment(payment_data: PaymentCreate):
    payment = Payment(**payment_data.dict())
    await db.payments.insert_one(prepare_for_mongo(payment.dict()))
    if payment.tip == "ogrenci":
        await db.students.update_one({"id": payment.kisi_id}, {"$inc": {"yapilan_odeme": payment.miktar}})
    elif payment.tip == "ogretmen":
        await db.teachers.update_one({"id": payment.kisi_id}, {"$inc": {"yapilan_odeme": payment.miktar}})
    return payment

@api_router.get("/payments", response_model=List[Payment])
async def get_payments():
    payments = await db.payments.find().sort("tarih", -1).to_list(length=None)
    return [Payment(**parse_from_mongo(p)) for p in payments]

@api_router.delete("/payments/{payment_id}")
async def delete_payment(payment_id: str):
    payment = await db.payments.find_one({"id": payment_id})
    if not payment:
        raise HTTPException(status_code=404, detail="Ödeme bulunamadı")
    if payment['tip'] == "ogrenci":
        await db.students.update_one({"id": payment['kisi_id']}, {"$inc": {"yapilan_odeme": -payment['miktar']}})
    elif payment['tip'] == "ogretmen":
        await db.teachers.update_one({"id": payment['kisi_id']}, {"$inc": {"yapilan_odeme": -payment['miktar']}})
    await db.payments.delete_one({"id": payment_id})
    return {"message": "Ödeme başarıyla silindi"}

@api_router.get("/export", response_model=ExportData)
async def get_export_data():
    teachers = await db.teachers.find().to_list(length=None)
    teacher_export = [{"Ad": t.get('ad',''), "Soyad": t.get('soyad',''), "Branş": t.get('brans',''), "Telefon": t.get('telefon',''), "Seviye": t.get('seviye',''), "Öğrenci Sayısı": t.get('ogrenci_sayisi',0), "Yapılması Gereken Ödeme": t.get('yapilmasi_gereken_odeme',0), "Yapılan Ödeme": t.get('yapilan_odeme',0), "Borç": max(0, t.get('yapilmasi_gereken_odeme',0) - t.get('yapilan_odeme',0)) if (t.get('ogrenci_sayisi',0) > 0 or len(t.get('atanan_ogrenciler',[])) > 0) else 0} for t in teachers]
    students = await db.students.find().to_list(length=None)
    student_export = []
    for s in students:
        teacher = await db.teachers.find_one({"id": s.get('ogretmen_id')}) if s.get('ogretmen_id') else None
        student_export.append({"Ad": s.get('ad',''), "Soyad": s.get('soyad',''), "Sınıf": s.get('sinif',''), "Veli Adı": s.get('veli_ad',''), "Veli Soyadı": s.get('veli_soyad',''), "Veli Telefon": s.get('veli_telefon',''), "Aldığı Eğitim": s.get('aldigi_egitim',''), "Kur": s.get('kur',''), "Yapılması Gereken Ödeme": s.get('yapilmasi_gereken_odeme',0), "Yapılan Ödeme": s.get('yapilan_odeme',0), "Öğretmene Yapılacak Ödeme": s.get('ogretmene_yapilacak_odeme',0), "Öğretmen": f"{teacher.get('ad','')} {teacher.get('soyad','')}" if teacher else 'Atanmamış', "Alacak": max(0, s.get('yapilmasi_gereken_odeme',0) - s.get('yapilan_odeme',0))})
    courses = await db.courses.find().to_list(length=None)
    course_export = [{"Kurs Adı": c.get('ad',''), "Fiyat": c.get('fiyat',0), "Süre (Saat)": c.get('sure',0), "Öğrenci Sayısı": c.get('ogrenci_sayisi',0)} for c in courses]
    payments = await db.payments.find().sort("tarih", -1).to_list(length=None)
    payment_export = []
    for p in payments:
        if p.get('tip') == 'ogrenci':
            person = await db.students.find_one({"id": p.get('kisi_id')})
        else:
            person = await db.teachers.find_one({"id": p.get('kisi_id')})
        payment_export.append({"Tarih": p.get('tarih',''), "Tip": 'Öğrenci' if p.get('tip') == 'ogrenci' else 'Öğretmen', "Kişi": f"{person.get('ad','')} {person.get('soyad','')}" if person else 'Bilinmiyor', "Miktar": p.get('miktar',0), "Açıklama": p.get('aciklama','')})
    return ExportData(ogretmenler=teacher_export, ogrenciler=student_export, kurslar=course_export, odemeler=payment_export)

@api_router.post("/backup/google-drive")
async def backup_to_google_drive(backup_data: dict):
    return {"success": True, "message": "Data queued for Google Drive backup", "backup_id": str(uuid.uuid4())}


# ─────────────────────────────────────────────
# GİRİŞ ANALİZİ (FAZ 1A)
# ─────────────────────────────────────────────

# Varsayılan norm tablosu (admin değiştirebilir)
VARSAYILAN_NORMLAR = {
    "1": {"dusuk": 25, "orta": 40, "yeterli": 60},
    "2": {"dusuk": 55, "orta": 75, "yeterli": 95},
    "3": {"dusuk": 65, "orta": 90, "yeterli": 115},
    "4": {"dusuk": 80, "orta": 110, "yeterli": 140},
    "5": {"dusuk": 90, "orta": 120, "yeterli": 150},
    "6": {"dusuk": 100, "orta": 135, "yeterli": 170},
    "7": {"dusuk": 110, "orta": 150, "yeterli": 185},
    "8": {"dusuk": 120, "orta": 160, "yeterli": 200},
}

async def get_norm_tablosu():
    doc = await db.sistem_ayarlari.find_one({"tip": "okuma_hizi_normlari"})
    if doc:
        return doc.get("normlar", VARSAYILAN_NORMLAR)
    return VARSAYILAN_NORMLAR

async def hiz_degerlendirme(sinif: str, wpm: float) -> str:
    normlar = await get_norm_tablosu()
    sinif_no = sinif.replace("-", "").replace(".", "").strip()[:1]
    n = normlar.get(sinif_no, normlar.get("4", VARSAYILAN_NORMLAR["4"]))
    if wpm <= n["dusuk"]:
        return "dusuk"
    elif wpm <= n["orta"]:
        return "orta"
    elif wpm <= n["yeterli"]:
        return "yeterli"
    else:
        return "ileri"

async def kur_onerisi_hesapla(wpm: float, dogruluk: float, sinif: str) -> str:
    hiz = await hiz_degerlendirme(sinif, wpm)
    if dogruluk >= 97 and hiz in ("yeterli", "ileri"):
        return "Kur 3"
    elif dogruluk >= 93 and hiz in ("orta", "yeterli", "ileri"):
        return "Kur 2"
    else:
        return "Kur 1"

# ── Norm Tablosu Yönetimi ──
class NormGuncelle(BaseModel):
    normlar: dict  # {"1": {"dusuk": 25, "orta": 40, "yeterli": 60}, ...}

@api_router.get("/diagnostic/normlar")
async def get_normlar(current_user=Depends(get_current_user)):
    return await get_norm_tablosu()

@api_router.put("/diagnostic/normlar")
async def update_normlar(data: NormGuncelle, current_user=Depends(require_role(UserRole.ADMIN, UserRole.COORDINATOR))):
    await db.sistem_ayarlari.update_one(
        {"tip": "okuma_hizi_normlari"},
        {"$set": {"tip": "okuma_hizi_normlari", "normlar": data.normlar}},
        upsert=True
    )
    return {"message": "Norm tablosu güncellendi", "normlar": data.normlar}

# ── Puan Ayarları ──
VARSAYILAN_PUANLAR = {
    "metin_ekleme": 5,
    "oylama_katilim": 2,
    "metin_havuza_girme": 10,
    "icerik_ekleme": 5,
    "icerik_oylama": 2,
}

async def get_puan_ayarlari():
    doc = await db.sistem_ayarlari.find_one({"tip": "puan_ayarlari"})
    if doc:
        return doc.get("puanlar", VARSAYILAN_PUANLAR)
    return VARSAYILAN_PUANLAR

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


# ─────────────────────────────────────────────
# ★ EKSİK MODELLER VE ENDPOINT'LER (EKLENDİ)
# ─────────────────────────────────────────────

# Metin oluşturma modeli — frontend MetinYonetimi bileşeni kullanıyor
class MetinCreate(BaseModel):
    baslik: str
    icerik: str
    kelime_sayisi: int = 0
    sinif_seviyesi: str = "4"
    tur: str = "hikaye"  # hikaye, bilgilendirici, siir

# Metin oylama modeli — metin_oy_ver endpoint'i kullanıyor (NameError düzeltmesi)
class MetinOyCreate(BaseModel):
    metin_id: str
    onay: bool
    sebep: str = ""


# ★ Metin ekleme endpoint'i (frontend: axios.post(`${API}/diagnostic/texts`, ...))
@api_router.post("/diagnostic/texts")
async def create_metin(data: MetinCreate, current_user=Depends(get_current_user)):
    role = current_user.get("role", "")
    if role not in ["admin", "coordinator", "teacher"]:
        raise HTTPException(status_code=403, detail="Yetkisiz")

    # Kelime sayısı otomatik hesapla (0 geldiyse)
    kelime_sayisi = data.kelime_sayisi
    if kelime_sayisi == 0 and data.icerik:
        kelime_sayisi = len(data.icerik.strip().split())

    # Admin/Koordinatör eklerse direkt oylama, öğretmen eklerse beklemede
    durum = "oylama" if role in ["admin", "coordinator"] else "beklemede"

    metin_doc = {
        "id": str(uuid.uuid4()),
        "baslik": data.baslik,
        "icerik": data.icerik,
        "kelime_sayisi": kelime_sayisi,
        "sinif_seviyesi": data.sinif_seviyesi,
        "tur": data.tur,
        "durum": durum,
        "ekleyen_id": current_user["id"],
        "ekleyen_ad": f"{current_user.get('ad', '')} {current_user.get('soyad', '')}",
        "oylar": {},
        "olusturma_tarihi": datetime.now(timezone.utc).isoformat(),
        "yayin_tarihi": None,
    }
    await db.analiz_metinler.insert_one(metin_doc)

    # Ekleyene puan ver (dinamik)
    puanlar = await get_puan_ayarlari()
    await db.users.update_one({"id": current_user["id"]}, {"$inc": {"puan": puanlar.get("metin_ekleme", 5)}})

    metin_doc.pop("_id", None)
    return metin_doc


# ★ Metin listeleme endpoint'i (frontend: axios.get(`${API}/diagnostic/texts`))
@api_router.get("/diagnostic/texts")
async def get_metinler(current_user=Depends(get_current_user)):
    role = current_user.get("role", "")
    user_id = current_user.get("id", "")

    items = await db.analiz_metinler.find().sort("olusturma_tarihi", -1).to_list(length=None)
    result = []
    for item in items:
        item.pop("_id", None)
        durum = item.get("durum", "")

        # Admin her şeyi görür
        if role == "admin":
            result.append(item)
        # Öğretmen: kendi eklediği + oylama bekleyenler + havuzdakiler
        elif role == "teacher":
            if item.get("ekleyen_id") == user_id:
                result.append(item)
            elif durum in ("oylama", "havuzda"):
                result.append(item)
        # Öğrenci/diğer: sadece havuzdakiler
        else:
            if durum == "havuzda":
                result.append(item)

    return result


# ─────────────────────────────────────────────
# MEVCUT GİRİŞ ANALİZİ ROUTE'LARI
# ─────────────────────────────────────────────

@api_router.post("/diagnostic/texts/{metin_id}/admin-karar")
async def metin_admin_karar(metin_id: str, karar: dict, current_user=Depends(require_role(UserRole.ADMIN, UserRole.COORDINATOR))):
    # karar: {"onay": True/False, "direkt": True/False}
    # direkt=True → oylama atla, direkt havuza al
    onay = karar.get("onay", False)
    direkt = karar.get("direkt", False)
    if not onay:
        yeni_durum = "reddedildi"
    elif direkt:
        yeni_durum = "havuzda"
        # Ekleyene bonus puan (havuza direkt girince - dinamik)
        puanlar = await get_puan_ayarlari()
        metin = await db.analiz_metinler.find_one({"id": metin_id})
        if metin and metin.get("ekleyen_id"):
            await db.users.update_one({"id": metin["ekleyen_id"]}, {"$inc": {"puan": puanlar.get("metin_havuza_girme", 10)}})
    else:
        yeni_durum = "oylama"
    await db.analiz_metinler.update_one(
        {"id": metin_id},
        {"$set": {"durum": yeni_durum, **({"yayin_tarihi": datetime.utcnow().isoformat()} if yeni_durum == "havuzda" else {})}}
    )
    return {"durum": yeni_durum}

@api_router.post("/diagnostic/texts/oy")
async def metin_oy_ver(oy: MetinOyCreate, current_user=Depends(get_current_user)):
    role = current_user.get("role", "")
    if role not in ["admin", "coordinator", "teacher"]:
        raise HTTPException(status_code=403, detail="Sadece öğretmenler oy verebilir")
    if not oy.onay and not oy.sebep:
        raise HTTPException(status_code=400, detail="Red için sebep belirtmelisiniz")
    metin = await db.analiz_metinler.find_one({"id": oy.metin_id})
    if not metin:
        raise HTTPException(status_code=404, detail="Metin bulunamadı")
    if metin.get("durum") != "oylama":
        raise HTTPException(status_code=400, detail="Bu metin oylamada değil")
    user_id = current_user["id"]
    oylar = metin.get("oylar", {})
    if user_id in oylar:
        raise HTTPException(status_code=400, detail="Zaten oy kullandınız")
    oylar[user_id] = {"onay": oy.onay, "sebep": oy.sebep}
    await db.analiz_metinler.update_one({"id": oy.metin_id}, {"$set": {"oylar": oylar}})
    # Oy veren öğretmene puan (dinamik)
    puanlar = await get_puan_ayarlari()
    await db.users.update_one({"id": user_id}, {"$inc": {"puan": puanlar.get("oylama_katilim", 2)}})
    # %60 kontrolü
    ogretmenler = await db.users.find({"role": {"$in": ["teacher", "coordinator", "admin"]}}).to_list(length=None)
    toplam = len(ogretmenler)
    onay_sayisi = sum(1 for v in oylar.values() if v.get("onay"))
    oy_sayisi = len(oylar)
    yeni_durum = metin.get("durum")
    if toplam > 0:
        onay_orani = onay_sayisi / toplam
        if onay_orani >= 0.6:
            yeni_durum = "havuzda"
            await db.analiz_metinler.update_one(
                {"id": oy.metin_id},
                {"$set": {"durum": "havuzda", "yayin_tarihi": datetime.utcnow().isoformat()}}
            )
            # Metni ekleyene bonus puan (havuza girince - dinamik)
            ekleyen_id = metin.get("ekleyen_id")
            if ekleyen_id:
                await db.users.update_one({"id": ekleyen_id}, {"$inc": {"puan": puanlar.get("metin_havuza_girme", 10)}})
        elif oy_sayisi == toplam and onay_orani < 0.6:
            yeni_durum = "reddedildi"
            await db.analiz_metinler.update_one({"id": oy.metin_id}, {"$set": {"durum": "reddedildi"}})
    return {
        "mesaj": f"Oyunuz kaydedildi (+{puanlar.get('oylama_katilim', 2)} puan)",
        "durum": yeni_durum,
        "onay_orani": round(onay_sayisi / max(toplam, 1) * 100),
        "oy_sayisi": oy_sayisi,
        "toplam": toplam
    }

@api_router.delete("/diagnostic/texts/{metin_id}")
async def delete_metin(metin_id: str, current_user=Depends(require_role(UserRole.ADMIN, UserRole.COORDINATOR))):
    await db.analiz_metinler.delete_one({"id": metin_id})
    return {"message": "Silindi"}

# ── Analiz Oturumları ──
class HataKaydi(BaseModel):
    tip: str  # atlama, yanlis_okuma, takilma, tekrar
    kelime: str = ""

class AnalizOturumBaslat(BaseModel):
    ogrenci_id: str
    metin_id: str

class AnalizTamamla(BaseModel):
    sure_saniye: float
    hatalar: List[HataKaydi]
    gozlem_notu: str = ""
    ogretmen_kur: str = ""

class DiagnosticOturum(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    ogrenci_id: str
    metin_id: str
    ogretmen_id: str
    durum: str = "devam"
    sure_saniye: float = 0
    hatalar: List[dict] = []
    gozlem_notu: str = ""
    wpm: float = 0
    dogruluk_yuzde: float = 0
    hiz_deger: str = ""
    sistem_kur: str = ""
    ogretmen_kur: str = ""
    olusturma_tarihi: datetime = Field(default_factory=datetime.utcnow)
    tamamlama_tarihi: Optional[datetime] = None

@api_router.post("/diagnostic/sessions")
async def baslat_oturum(data: AnalizOturumBaslat, current_user=Depends(get_current_user)):
    if current_user.get("role") not in ["admin", "coordinator", "teacher"]:
        raise HTTPException(status_code=403, detail="Yetkisiz")
    # Metni bul (id veya _id ile)
    metin = await db.analiz_metinler.find_one({"id": data.metin_id})
    if not metin:
        raise HTTPException(status_code=404, detail=f"Metin bulunamadı: {data.metin_id}")
    # Öğrenciyi kontrol et
    ogrenci = await db.students.find_one({"id": data.ogrenci_id})
    if not ogrenci:
        raise HTTPException(status_code=404, detail=f"Öğrenci bulunamadı: {data.ogrenci_id}")
    oturum = DiagnosticOturum(
        ogrenci_id=data.ogrenci_id,
        metin_id=data.metin_id,
        ogretmen_id=current_user["id"]
    )
    d = oturum.dict()
    d["olusturma_tarihi"] = d["olusturma_tarihi"].isoformat()
    d["tamamlama_tarihi"] = None
    await db.diagnostic_oturumlar.insert_one(d)
    d.pop("_id", None)
    return d

@api_router.get("/diagnostic/sessions")
async def get_oturumlar(current_user=Depends(get_current_user)):
    q = {}
    if current_user.get("role") == "teacher":
        q["ogretmen_id"] = current_user["id"]
    items = await db.diagnostic_oturumlar.find(q).sort("olusturma_tarihi", -1).to_list(length=None)
    for i in items: i.pop("_id", None)
    return items

@api_router.get("/diagnostic/sessions/student/{ogrenci_id}")
async def get_ogrenci_oturumlari(ogrenci_id: str, current_user=Depends(get_current_user)):
    items = await db.diagnostic_oturumlar.find({"ogrenci_id": ogrenci_id}).sort("olusturma_tarihi", -1).to_list(length=None)
    for i in items: i.pop("_id", None)
    return items

@api_router.post("/diagnostic/sessions/{oturum_id}/complete")
async def tamamla_oturum(oturum_id: str, data: AnalizTamamla, current_user=Depends(get_current_user)):
    oturum = await db.diagnostic_oturumlar.find_one({"id": oturum_id})
    if not oturum:
        raise HTTPException(status_code=404, detail="Oturum bulunamadı")

    metin = await db.analiz_metinler.find_one({"id": oturum["metin_id"]})
    kelime_sayisi = metin.get("kelime_sayisi", 100) if metin else 100
    sinif_seviyesi = metin.get("sinif_seviyesi", "4") if metin else "4"

    # Hesaplamalar
    sure_dakika = data.sure_saniye / 60 if data.sure_saniye > 0 else 1
    wpm = round(kelime_sayisi / sure_dakika, 1)

    toplam_hata = len(data.hatalar)
    dogruluk = round(max(0, (kelime_sayisi - toplam_hata) / kelime_sayisi * 100), 1)

    hiz_deger = await hiz_degerlendirme(sinif_seviyesi, wpm)
    sistem_kur = await kur_onerisi_hesapla(wpm, dogruluk, sinif_seviyesi)
    atanan_kur = data.ogretmen_kur if data.ogretmen_kur else sistem_kur

    # Hata dağılımı
    hata_sayilari = {"atlama": 0, "yanlis_okuma": 0, "takilma": 0, "tekrar": 0}
    for h in data.hatalar:
        tip = h.tip if hasattr(h, "tip") else h.get("tip", "")
        if tip in hata_sayilari:
            hata_sayilari[tip] += 1

    now = datetime.utcnow().isoformat()
    guncelle = {
        "durum": "tamamlandi",
        "sure_saniye": data.sure_saniye,
        "hatalar": [h.dict() if hasattr(h, "dict") else h for h in data.hatalar],
        "gozlem_notu": data.gozlem_notu,
        "wpm": wpm,
        "dogruluk_yuzde": dogruluk,
        "hiz_deger": hiz_deger,
        "sistem_kur": sistem_kur,
        "ogretmen_kur": atanan_kur,
        "tamamlama_tarihi": now
    }
    await db.diagnostic_oturumlar.update_one({"id": oturum_id}, {"$set": guncelle})

    # Öğrencinin kurunu güncelle
    await db.students.update_one({"id": oturum["ogrenci_id"]}, {"$set": {"kur": atanan_kur}})

    return {
        "wpm": wpm,
        "dogruluk_yuzde": dogruluk,
        "hiz_deger": hiz_deger,
        "sistem_kur": sistem_kur,
        "atanan_kur": atanan_kur,
        "hata_sayilari": hata_sayilari,
        "sure_saniye": data.sure_saniye
    }



# ── Rapor Sistemi ──
class AnlamaVeri(BaseModel):
    # 4.1 Sözcük düzeyinde
    cumle_anlama: str = "orta"          # zayif / orta / iyi
    bilinmeyen_sozcuk: str = "orta"
    baglac_zamir: str = "orta"
    # 4.2 Ana yapı
    ana_fikir: str = "orta"
    yardimci_fikir: str = "orta"
    konu: str = "orta"
    baslik_onerme: str = "orta"
    # 4.3 Derin anlama
    neden_sonuc: str = "orta"
    cikarim: str = "orta"
    ipuclari: str = "orta"
    yorumlama: str = "orta"
    # 4.4 Eleştirel
    gorus_bildirme: str = "orta"
    yazar_amaci: str = "orta"
    alternatif_fikir: str = "orta"
    guncelle_hayat: str = "orta"
    # 4.5 Soru performansı
    bilgi: str = "iyi"
    kavrama: str = "iyi"
    uygulama: str = "iyi"
    analiz: str = "iyi"
    sentez: str = "iyi"
    degerlendirme: str = "iyi"
    genel_yuzde: int = 0

class ProzodikVeri(BaseModel):
    noktalama: int = 3    # 1-4 puan
    vurgu: int = 3
    tonlama: int = 3
    akicilik: int = 3
    anlamli_gruplama: int = 3

class RaporOlusturCreate(BaseModel):
    oturum_id: str
    anlama: AnlamaVeri
    prozodik: ProzodikVeri
    ogretmen_notu: str = ""

def anlama_yuzde(anlama: AnlamaVeri) -> int:
    alanlar = [
        anlama.cumle_anlama, anlama.bilinmeyen_sozcuk, anlama.baglac_zamir,
        anlama.ana_fikir, anlama.yardimci_fikir, anlama.konu, anlama.baslik_onerme,
        anlama.neden_sonuc, anlama.cikarim, anlama.ipuclari, anlama.yorumlama,
        anlama.gorus_bildirme, anlama.yazar_amaci, anlama.alternatif_fikir, anlama.guncelle_hayat,
        anlama.bilgi, anlama.kavrama, anlama.uygulama, anlama.analiz, anlama.sentez, anlama.degerlendirme
    ]
    puan_map = {"zayif": 0, "orta": 1, "iyi": 2}
    toplam = sum(puan_map.get(a, 1) for a in alanlar)
    return round(toplam / (len(alanlar) * 2) * 100)

def hiz_metni(hiz_deger: str) -> str:
    return {"dusuk": "düşük", "orta": "orta", "yeterli": "yeterli", "ileri": "ileri"}.get(hiz_deger, "orta")

def prozodik_seviye(toplam: int) -> str:
    if toplam >= 18: return "çok iyi"
    elif toplam >= 14: return "iyi"
    elif toplam >= 10: return "orta"
    else: return "geliştirilmeli"

def anlama_seviye(pct: int) -> str:
    if pct >= 85: return "iyi"
    elif pct >= 70: return "orta"
    else: return "zayıf"

def _hata_sayilari_hesapla(hatalar_raw):
    """Ham hata listesinden [{tur, sayi}] formatına çevir"""
    if not hatalar_raw:
        return []
    # Eğer zaten {tur, sayi} formatındaysa dokunma
    if hatalar_raw and isinstance(hatalar_raw[0], dict) and "sayi" in hatalar_raw[0]:
        return hatalar_raw
    # Ham liste: [{tip: "atlama", kelime: "x"}, ...] → sayılarla topla
    sayac = {}
    for h in hatalar_raw:
        tip = h.get("tip", "") if isinstance(h, dict) else ""
        if tip:
            sayac[tip] = sayac.get(tip, 0) + 1
    hata_labels = {"atlama": "Atlama", "yanlis_okuma": "Yanlış Okuma", "takilma": "Takılma", "tekrar": "Tekrar"}
    result = []
    for tip, sayi in sayac.items():
        result.append({"tur": tip, "sayi": sayi})
    # Eğer hiç hata yoksa standart 4 türü 0 olarak göster
    if not result:
        for tip in ["atlama", "yanlis_okuma", "takilma", "tekrar"]:
            result.append({"tur": tip, "sayi": 0})
    return result

@api_router.post("/diagnostic/rapor")
async def olustur_rapor(data: RaporOlusturCreate, current_user=Depends(get_current_user)):
    oturum = await db.diagnostic_oturumlar.find_one({"id": data.oturum_id})
    if not oturum:
        raise HTTPException(status_code=404, detail="Oturum bulunamadı")

    metin = await db.analiz_metinler.find_one({"id": oturum.get("metin_id")})
    ogrenci = await db.students.find_one({"id": oturum.get("ogrenci_id")})
    ogretmen = await db.users.find_one({"id": oturum.get("ogretmen_id")})

    prozodik_toplam = data.prozodik.noktalama + data.prozodik.vurgu + data.prozodik.tonlama + data.prozodik.akicilik + data.prozodik.anlamli_gruplama
    anlama_pct = data.anlama.genel_yuzde if data.anlama.genel_yuzde > 0 else anlama_yuzde(data.anlama)

    rapor_data = {
        "id": str(uuid.uuid4()),
        "oturum_id": data.oturum_id,
        "ogrenci_id": oturum.get("ogrenci_id"),
        "ogretmen_id": oturum.get("ogretmen_id"),
        "ogrenci_ad": f"{ogrenci.get('ad','')} {ogrenci.get('soyad','')}" if ogrenci else "",
        "ogrenci_sinif": ogrenci.get("sinif", "") if ogrenci else "",
        "ogretmen_ad": f"{ogretmen.get('ad','')} {ogretmen.get('soyad','')}" if ogretmen else "",
        "metin_adi": metin.get("baslik", "") if metin else "",
        "metin_turu": metin.get("tur", "") if metin else "",
        "kelime_sayisi": metin.get("kelime_sayisi", 0) if metin else 0,
        "sure_saniye": oturum.get("sure_saniye", 0),
        "wpm": oturum.get("wpm", 0),
        "dogruluk_yuzde": oturum.get("dogruluk_yuzde", 0),
        "hiz_deger": oturum.get("hiz_deger", ""),
        "atanan_kur": oturum.get("ogretmen_kur", ""),
        "hata_sayilari": _hata_sayilari_hesapla(oturum.get("hatalar", [])),
        "anlama": data.anlama.dict(),
        "anlama_yuzde": anlama_pct,
        "prozodik": data.prozodik.dict(),
        "prozodik_toplam": prozodik_toplam,
        "ogretmen_notu": data.ogretmen_notu,
        "olusturma_tarihi": datetime.utcnow().isoformat(),
    }
    await db.diagnostic_raporlar.insert_one(rapor_data)
    rapor_data.pop("_id", None)
    return rapor_data

@api_router.get("/diagnostic/rapor/ogrenci/{ogrenci_id}")
async def get_ogrenci_raporlari(ogrenci_id: str, current_user=Depends(get_current_user)):
    items = await db.diagnostic_raporlar.find({"ogrenci_id": ogrenci_id}).sort("olusturma_tarihi", -1).to_list(length=None)
    for i in items: i.pop("_id", None)
    return items

@api_router.get("/diagnostic/rapor/{rapor_id}")
async def get_rapor(rapor_id: str, current_user=Depends(get_current_user)):
    rapor = await db.diagnostic_raporlar.find_one({"id": rapor_id})
    if not rapor:
        raise HTTPException(status_code=404, detail="Rapor bulunamadı")
    rapor.pop("_id", None)
    return rapor

# ── Egzersiz Puan Sistemi ──
@api_router.get("/egzersiz/puanlar")
async def get_egzersiz_puanlari():
    doc = await db.ayarlar.find_one({"tip": "egzersiz_puanlari"})
    if doc:
        doc.pop("_id", None)
        doc.pop("tip", None)
        return doc.get("puanlar", {})
    return {}

@api_router.post("/egzersiz/puan-ayarla")
async def set_egzersiz_puanlari(data: dict, current_user=Depends(get_current_user)):
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Yetki yok")
    puanlar = data.get("puanlar", {})
    await db.ayarlar.update_one(
        {"tip": "egzersiz_puanlari"},
        {"$set": {"tip": "egzersiz_puanlari", "puanlar": puanlar}},
        upsert=True
    )
    return {"message": "Puanlar kaydedildi"}

@api_router.post("/egzersiz/tamamla")
async def egzersiz_tamamla(data: dict, current_user=Depends(get_current_user)):
    kullanici_id = data.get("kullanici_id", current_user.get("id"))
    egzersiz_id = data.get("egzersiz_id", "")
    if not egzersiz_id:
        raise HTTPException(status_code=400, detail="Egzersiz ID gerekli")
    # Bugün zaten yaptı mı?
    bugun = datetime.utcnow().strftime("%Y-%m-%d")
    mevcut = await db.egzersiz_kayitlari.find_one({
        "kullanici_id": kullanici_id,
        "egzersiz_id": egzersiz_id,
        "tarih": bugun
    })
    if mevcut:
        raise HTTPException(status_code=409, detail="Bu egzersiz bugün zaten tamamlandı")
    # Puan hesapla
    ayar = await db.ayarlar.find_one({"tip": "egzersiz_puanlari"})
    puanlar = ayar.get("puanlar", {}) if ayar else {}
    kazanilan = puanlar.get(egzersiz_id, 10)  # varsayılan 10 puan
    # Kaydet
    await db.egzersiz_kayitlari.insert_one({
        "id": str(uuid.uuid4()),
        "kullanici_id": kullanici_id,
        "egzersiz_id": egzersiz_id,
        "tarih": bugun,
        "kazanilan_puan": kazanilan,
        "zaman": datetime.utcnow().isoformat()
    })
    # Kullanıcı puanını güncelle
    await db.users.update_one({"id": kullanici_id}, {"$inc": {"puan": kazanilan}})
    return {"kazanilan_puan": kazanilan, "egzersiz_id": egzersiz_id}

# ── Kitap + Soru Havuzu ──
class KitapCreate(BaseModel):
    baslik: str
    yazar: str = ""
    yas_grubu: str = "8-10"
    zorluk: str = "orta"
    bolum_sayisi: int = 1

@api_router.post("/kitaplar")
async def kitap_ekle(data: KitapCreate, current_user=Depends(get_current_user)):
    role = current_user.get("role", "")
    if role not in ("admin", "coordinator", "teacher"):
        raise HTTPException(status_code=403, detail="Yetki yok")
    durum = "oylama" if role in ("admin", "coordinator") else "beklemede"
    kitap = {
        "id": str(uuid.uuid4()),
        "baslik": data.baslik,
        "yazar": data.yazar,
        "yas_grubu": data.yas_grubu,
        "zorluk": data.zorluk,
        "bolum_sayisi": data.bolum_sayisi,
        "ekleyen_id": current_user["id"],
        "ekleyen_ad": f"{current_user.get('ad','')} {current_user.get('soyad','')}".strip(),
        "durum": durum,
        "oylar": {},
        "olusturma_tarihi": datetime.utcnow().isoformat(),
    }
    await db.kitaplar.insert_one(kitap)
    kitap.pop("_id", None)
    return kitap

@api_router.get("/kitaplar")
async def kitap_listele(current_user=Depends(get_current_user)):
    role = current_user.get("role", "")
    kitaplar = await db.kitaplar.find().sort("olusturma_tarihi", -1).to_list(length=None)
    for k in kitaplar:
        k.pop("_id", None)
    if role in ("admin", "coordinator"):
        return kitaplar
    # Öğretmen: kendi eklediği + oylamada + havuzda
    return [k for k in kitaplar if k.get("durum") in ("oylama", "havuzda") or k.get("ekleyen_id") == current_user["id"]]

@api_router.put("/kitaplar/{kitap_id}")
async def kitap_guncelle(kitap_id: str, data: dict, current_user=Depends(get_current_user)):
    kitap = await db.kitaplar.find_one({"id": kitap_id})
    if not kitap:
        raise HTTPException(status_code=404, detail="Kitap bulunamadı")
    update = {k: v for k, v in data.items() if k in ("baslik", "yazar", "yas_grubu", "zorluk", "bolum_sayisi")}
    if update:
        await db.kitaplar.update_one({"id": kitap_id}, {"$set": update})
    return {"message": "Güncellendi"}

@api_router.delete("/kitaplar/{kitap_id}")
async def kitap_sil(kitap_id: str, current_user=Depends(get_current_user)):
    if current_user.get("role") not in ("admin", "coordinator"):
        raise HTTPException(status_code=403, detail="Yetki yok")
    await db.kitaplar.delete_one({"id": kitap_id})
    await db.sorular.delete_many({"kitap_id": kitap_id})
    return {"message": "Kitap ve soruları silindi"}

# Kitap admin karar (oylama başlat / direkt havuza al / reddet)
@api_router.post("/kitaplar/{kitap_id}/admin-karar")
async def kitap_admin_karar(kitap_id: str, data: dict, current_user=Depends(get_current_user)):
    if current_user.get("role") not in ("admin", "coordinator"):
        raise HTTPException(status_code=403, detail="Yetki yok")
    onay = data.get("onay", True)
    direkt = data.get("direkt", False)
    if not onay:
        await db.kitaplar.update_one({"id": kitap_id}, {"$set": {"durum": "reddedildi", "red_sebep": data.get("sebep", "")}})
        return {"message": "Reddedildi"}
    if direkt:
        await db.kitaplar.update_one({"id": kitap_id}, {"$set": {"durum": "havuzda"}})
        return {"message": "Direkt havuza alındı"}
    await db.kitaplar.update_one({"id": kitap_id}, {"$set": {"durum": "oylama"}})
    return {"message": "Oylama başlatıldı"}

# Kitap oylama
@api_router.post("/kitaplar/{kitap_id}/oy")
async def kitap_oy_ver(kitap_id: str, data: dict, current_user=Depends(get_current_user)):
    kitap = await db.kitaplar.find_one({"id": kitap_id})
    if not kitap or kitap.get("durum") != "oylama":
        raise HTTPException(status_code=400, detail="Bu kitap oylamada değil")
    user_id = current_user["id"]
    oylar = kitap.get("oylar", {})
    if user_id in oylar:
        raise HTTPException(status_code=400, detail="Zaten oy kullandınız")
    onay = data.get("onay", True)
    oylar[user_id] = {"onay": onay, "sebep": data.get("sebep", ""), "tarih": datetime.utcnow().isoformat()}
    update = {"oylar": oylar}
    # Oy eşiği kontrolü
    ayar = await db.ayarlar.find_one({"tip": "puan_ayarlari"})
    esik = ayar.get("oy_esik", 3) if ayar else 3
    onay_sayisi = sum(1 for o in oylar.values() if o.get("onay"))
    red_sayisi = sum(1 for o in oylar.values() if not o.get("onay"))
    if red_sayisi >= 1:
        update["durum"] = "reddedildi"
    elif onay_sayisi >= esik:
        update["durum"] = "havuzda"
    await db.kitaplar.update_one({"id": kitap_id}, {"$set": update})
    # Katkı puanı
    await db.users.update_one({"id": user_id}, {"$inc": {"puan": 3}})
    return {"message": "Oy kaydedildi"}

# ── Soru CRUD ──
class SoruCreate(BaseModel):
    kitap_id: str
    bolum: int = 1
    soru_metni: str
    secenekler: list = []
    dogru_cevap: int = 0

@api_router.post("/sorular")
async def soru_ekle(data: SoruCreate, current_user=Depends(get_current_user)):
    soru = {
        "id": str(uuid.uuid4()),
        "kitap_id": data.kitap_id,
        "bolum": data.bolum,
        "soru_metni": data.soru_metni,
        "secenekler": data.secenekler,
        "dogru_cevap": data.dogru_cevap,
        "ekleyen_id": current_user["id"],
        "ekleyen_ad": f"{current_user.get('ad','')} {current_user.get('soyad','')}".strip(),
        "kullanim_sayisi": 0,
        "olusturma_tarihi": datetime.utcnow().isoformat(),
    }
    await db.sorular.insert_one(soru)
    soru.pop("_id", None)
    return soru

@api_router.get("/sorular/{kitap_id}")
async def soru_listele(kitap_id: str, bolum: int = None, current_user=Depends(get_current_user)):
    filtre = {"kitap_id": kitap_id}
    if bolum is not None:
        filtre["bolum"] = bolum
    sorular = await db.sorular.find(filtre).sort("bolum", 1).to_list(length=None)
    for s in sorular:
        s.pop("_id", None)
    return sorular

@api_router.put("/sorular/{soru_id}")
async def soru_guncelle(soru_id: str, data: dict, current_user=Depends(get_current_user)):
    update = {k: v for k, v in data.items() if k in ("soru_metni", "secenekler", "dogru_cevap", "bolum")}
    if update:
        await db.sorular.update_one({"id": soru_id}, {"$set": update})
    return {"message": "Güncellendi"}

@api_router.delete("/sorular/{soru_id}")
async def soru_sil(soru_id: str, current_user=Depends(get_current_user)):
    await db.sorular.delete_one({"id": soru_id})
    return {"message": "Silindi"}

# ── Kitap Bilgi Çekme (ISBN / Link) ──
@api_router.post("/kitap-bilgi-cek")
async def kitap_bilgi_cek(data: dict, current_user=Depends(get_current_user)):
    import urllib.request, urllib.error, ssl, json, asyncio

    deger = data.get("deger", "").strip()
    tip = data.get("tip", "isbn")
    result = {"baslik": "", "yazar": "", "isbn": "", "yayinevi": "", "sayfa_sayisi": "", "aciklama": "", "kapak_url": "", "link": ""}

    def fetch_url(url):
        try:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
            with urllib.request.urlopen(req, timeout=12, context=ctx) as resp:
                raw = resp.read()
                try:
                    return raw.decode("utf-8")
                except Exception:
                    return raw.decode("latin-1")
        except Exception:
            return None

    if tip == "isbn":
        isbn_temiz = re.sub(r"[^0-9X]", "", deger.upper())
        # Google Books API
        raw = await asyncio.to_thread(fetch_url, f"https://www.googleapis.com/books/v1/volumes?q=isbn:{isbn_temiz}")
        if raw:
            try:
                j = json.loads(raw)
                if j.get("totalItems", 0) > 0:
                    vol = j["items"][0]["volumeInfo"]
                    result["baslik"] = vol.get("title", "")
                    result["yazar"] = ", ".join(vol.get("authors", []))
                    result["yayinevi"] = vol.get("publisher", "")
                    result["sayfa_sayisi"] = str(vol.get("pageCount", "") or "")
                    result["aciklama"] = (vol.get("description", "") or "")[:200]
                    result["isbn"] = isbn_temiz
                    imgs = vol.get("imageLinks", {})
                    result["kapak_url"] = imgs.get("thumbnail", imgs.get("smallThumbnail", ""))
                    result["link"] = vol.get("infoLink", "")
            except Exception:
                pass
        # Open Library fallback
        if not result["baslik"]:
            raw = await asyncio.to_thread(fetch_url, f"https://openlibrary.org/api/books?bibkeys=ISBN:{isbn_temiz}&format=json&jscmd=data")
            if raw:
                try:
                    j = json.loads(raw)
                    key = f"ISBN:{isbn_temiz}"
                    if key in j:
                        book = j[key]
                        result["baslik"] = book.get("title", "")
                        result["yazar"] = ", ".join([a.get("name", "") for a in book.get("authors", [])])
                        result["yayinevi"] = ", ".join([p.get("name", "") for p in book.get("publishers", [])])
                        result["sayfa_sayisi"] = str(book.get("number_of_pages", "") or "")
                        result["isbn"] = isbn_temiz
                        cover = book.get("cover", {})
                        result["kapak_url"] = cover.get("medium", cover.get("small", ""))
                        result["link"] = book.get("url", "")
                except Exception:
                    pass

    elif tip == "link":
        html = await asyncio.to_thread(fetch_url, deger)
        if html:
            QP = """[\"']"""
            m = re.search(r'property\s*=\s*' + QP + r'og:title' + QP + r'[^>]*content\s*=\s*' + QP + r'([^"\']+)', html, re.I)
            if m:
                result["baslik"] = m.group(1).strip()
            else:
                m = re.search(r"<title[^>]*>([^<]+)</title>", html, re.I)
                if m:
                    t = m.group(1).strip()
                    for sep in [" - ", " | ", " :: "]:
                        if sep in t:
                            t = t.split(sep)[0].strip()
                            break
                    result["baslik"] = t
            m = re.search(r'property\s*=\s*' + QP + r'og:description' + QP + r'[^>]*content\s*=\s*' + QP + r'([^"\']+)', html, re.I)
            if m:
                result["aciklama"] = m.group(1).strip()[:200]
            m = re.search(r'property\s*=\s*' + QP + r'og:image' + QP + r'[^>]*content\s*=\s*' + QP + r'([^"\']+)', html, re.I)
            if m:
                result["kapak_url"] = m.group(1).strip()
            m = re.search(r'itemprop\s*=\s*' + QP + r'author' + QP + r'[^>]*>([^<]+)', html, re.I)
            if not m:
                m = re.search(r'Yazar\s*:?\s*</\w+>\s*<[^>]+>([^<]+)', html, re.I)
            if m:
                result["yazar"] = m.group(1).strip()
            m = re.search(r'itemprop\s*=\s*' + QP + r'publisher' + QP + r'[^>]*>([^<]+)', html, re.I)
            if not m:
                m = re.search(r'Yay.nevi\s*:?\s*</\w+>\s*<[^>]+>([^<]+)', html, re.I)
            if m:
                result["yayinevi"] = m.group(1).strip()
            m = re.search(r'(?:Sayfa|sayfa)\s*(?:Say.s.)?\s*:?\s*(\d+)', html)
            if m:
                result["sayfa_sayisi"] = m.group(1)
            m = re.search(r'ISBN[^:]*:\s*([\d\-]{10,})', html, re.I)
            if m:
                result["isbn"] = re.sub(r"[^0-9]", "", m.group(1))
            result["link"] = deger

    if not result["baslik"]:
        raise HTTPException(status_code=404, detail="Kitap bilgisi bulunamadi")
    return result

# ── PDF Rapor Üretimi ──
def _tr_upper(text):
    """Türkçe büyük harf çevirimi (i→İ, ı→I)"""
    if not text:
        return text
    tr_map = str.maketrans("abcçdefgğhıijklmnoöprsştuüvyz", "ABCÇDEFGĞHIİJKLMNOÖPRSŞTUÜVYZ")
    return text.translate(tr_map)

@api_router.get("/diagnostic/rapor/{rapor_id}/pdf")
async def get_rapor_pdf(rapor_id: str, current_user=Depends(get_current_user)):
    rapor = await db.diagnostic_raporlar.find_one({"id": rapor_id})
    if not rapor:
        raise HTTPException(status_code=404, detail="Rapor bulunamadı")
    rapor.pop("_id", None)

    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import cm, mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph as RLPara, Spacer, Table as RLTable, TableStyle, HRFlowable
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    # ── Türkçe Font Kaydı ──
    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
    font_registered = False
    for fp in font_paths:
        if os.path.exists(fp):
            font_registered = True
            break

    if font_registered:
        pdfmetrics.registerFont(TTFont("TRFont", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"))
        pdfmetrics.registerFont(TTFont("TRFontBold", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"))
        FONT = "TRFont"
        FONTB = "TRFontBold"
    else:
        FONT = "Helvetica"
        FONTB = "Helvetica-Bold"

    buffer = io.BytesIO()
    doc_pdf = SimpleDocTemplate(buffer, pagesize=A4, topMargin=1.5*cm, bottomMargin=1.5*cm, leftMargin=2*cm, rightMargin=2*cm)

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='TitleOBA', fontSize=18, leading=22, alignment=TA_CENTER, spaceAfter=4, textColor=colors.HexColor('#1F4E79'), fontName=FONTB))
    styles.add(ParagraphStyle(name='SubOBA', fontSize=11, leading=14, alignment=TA_CENTER, spaceAfter=16, textColor=colors.HexColor('#666666'), fontName=FONT))
    styles.add(ParagraphStyle(name='SectOBA', fontSize=12, leading=16, spaceBefore=14, spaceAfter=8, textColor=colors.HexColor('#1F4E79'), fontName=FONTB))
    styles.add(ParagraphStyle(name='SubSectOBA', fontSize=10, leading=13, spaceBefore=10, spaceAfter=4, textColor=colors.HexColor('#333333'), fontName=FONTB))
    styles.add(ParagraphStyle(name='BodyOBA', fontSize=9, leading=13, spaceAfter=4, fontName=FONT))
    styles.add(ParagraphStyle(name='SmallOBA', fontSize=8, leading=11, textColor=colors.HexColor('#999999'), fontName=FONT))
    styles.add(ParagraphStyle(name='BigNum', fontSize=28, leading=32, textColor=colors.HexColor('#1F4E79'), fontName=FONTB))

    el = []  # elements

    hdr_bg = colors.HexColor('#1F4E79')
    alt_bg = colors.HexColor('#F2F7FB')
    bdr = colors.HexColor('#CCCCCC')
    ora = colors.HexColor('#E67E22')

    def tbl_style(rows, has_header=True):
        s = [
            ('FONTNAME', (0,0), (-1,-1), FONT),
            ('FONTSIZE', (0,0), (-1,-1), 9),
            ('GRID', (0,0), (-1,-1), 0.5, bdr),
            ('TOPPADDING', (0,0), (-1,-1), 5),
            ('BOTTOMPADDING', (0,0), (-1,-1), 5),
            ('LEFTPADDING', (0,0), (-1,-1), 6),
            ('RIGHTPADDING', (0,0), (-1,-1), 6),
        ]
        if has_header:
            s += [
                ('BACKGROUND', (0,0), (-1,0), hdr_bg),
                ('TEXTCOLOR', (0,0), (-1,0), colors.white),
                ('FONTNAME', (0,0), (-1,0), FONTB),
            ]
        for i in range(1 if has_header else 0, rows):
            if i % 2 == 0:
                s.append(('BACKGROUND', (0,i), (-1,i), alt_bg))
        return s

    # ── BAŞLIK ──
    el.append(RLPara("Okuma Becerileri Akademisi", styles['TitleOBA']))
    el.append(RLPara("Giriş Analizi Raporu", styles['SubOBA']))

    # ── 1. ÖĞRENCİ BİLGİLERİ ──
    el.append(RLPara("1. Öğrenci Bilgileri", styles['SectOBA']))
    w1, w2, w3, w4 = 3*cm, 5*cm, 3*cm, 5*cm
    info = [
        ["Adı Soyadı:", rapor.get("ogrenci_ad", "-"), "Sınıfı:", rapor.get("ogrenci_sinif", "-")],
        ["Eğitimci:", rapor.get("ogretmen_ad", "-"), "Tarih:", rapor.get("olusturma_tarihi", "")[:10]],
    ]
    t = RLTable(info, colWidths=[w1, w2, w3, w4])
    t.setStyle(TableStyle([
        ('FONTNAME', (0,0), (0,-1), FONTB), ('FONTNAME', (2,0), (2,-1), FONTB),
        ('FONTNAME', (1,0), (1,-1), FONT), ('FONTNAME', (3,0), (3,-1), FONT),
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('TEXTCOLOR', (0,0), (0,-1), hdr_bg), ('TEXTCOLOR', (2,0), (2,-1), hdr_bg),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5), ('TOPPADDING', (0,0), (-1,-1), 5),
    ]))
    el.append(t)

    # ── 2. METİN BİLGİLERİ ──
    el.append(RLPara("2. Metin Bilgileri", styles['SectOBA']))
    kelime_s = rapor.get("kelime_sayisi", 0)
    dogruluk = rapor.get("dogruluk_yuzde", 0)
    yanlis_k = round(kelime_s * (100 - dogruluk) / 100) if kelime_s else 0
    dogru_k = kelime_s - yanlis_k
    sure_sn_total = rapor.get("sure_saniye", 0)
    sure_dk = int(sure_sn_total) // 60
    sure_sn = int(sure_sn_total) % 60
    metin_info = [
        ["Metnin Adı:", _tr_upper(rapor.get("metin_adi", "-"))],
        ["Metnin Türü:", _tr_upper(rapor.get("metin_turu", "-"))],
        ["Toplam Kelime Sayısı:", str(kelime_s)],
        ["Doğru Okunan Kelime:", str(dogru_k)],
        ["Yanlış Okunan Kelime:", str(yanlis_k)],
        ["Tamamlama Süresi:", f"{sure_dk}:{str(sure_sn).zfill(2)} ({sure_sn_total} sn)"],
    ]
    t2 = RLTable(metin_info, colWidths=[5*cm, 11*cm])
    t2.setStyle(TableStyle([
        ('FONTNAME', (0,0), (0,-1), FONTB), ('FONTNAME', (1,0), (1,-1), FONT),
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('GRID', (0,0), (-1,-1), 0.5, bdr),
        ('BACKGROUND', (0,0), (0,-1), alt_bg),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5), ('TOPPADDING', (0,0), (-1,-1), 5),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
    ]))
    el.append(t2)

    # ── 3. OKUMA HIZI ──
    el.append(RLPara("3. Okuma Hızı", styles['SectOBA']))
    wpm = round(rapor.get("wpm", 0))
    hiz_map = {"dusuk": "Düşük", "orta": "Orta", "yeterli": "Yeterli", "ileri": "İleri"}
    hiz_label = hiz_map.get(rapor.get("hiz_deger", ""), "?")
    hiz_renk = {"dusuk": "#E74C3C", "orta": "#F39C12", "yeterli": "#27AE60", "ileri": "#2E86C1"}.get(rapor.get("hiz_deger", ""), "#333")
    el.append(RLPara(f'<font size="28" color="{hiz_renk}"><b>{wpm}</b></font>  <font size="10">kelime/dakika</font>', styles['BodyOBA']))
    el.append(RLPara(f'<font size="12" color="{hiz_renk}"><b>{hiz_label} Düzey</b></font>', styles['BodyOBA']))
    el.append(Spacer(1, 4))
    sinif = rapor.get("ogrenci_sinif", "")
    el.append(RLPara(f"Öğrencinin okuma hızı dakikada <b>{wpm} kelime</b>dir. Bu okuma hızı, öğrencinin bulunduğu sınıf düzeyi normlarına göre <b>{hiz_label.lower()} düzeydedir</b>.", styles['BodyOBA']))

    # ── 4. DOĞRU OKUMA ORANI ──
    el.append(RLPara("3.1. Doğru Okuma Oranı", styles['SubSectOBA']))
    el.append(RLPara(f"Doğruluk: <b>%{round(dogruluk)}</b>", styles['BodyOBA']))
    hatalar = rapor.get("hata_sayilari", [])
    # Dict formatındaysa listeye çevir: {"atlama": 2, ...} → [{"tur": "atlama", "sayi": 2}]
    if isinstance(hatalar, dict):
        hatalar = [{"tur": k, "sayi": v} for k, v in hatalar.items()]
    if hatalar:
        hata_labels = {"atlama": "Atlama", "yanlis_okuma": "Yanlış Okuma", "yanlis": "Yanlış Okuma", "takilma": "Takılma", "tekrar": "Tekrar"}
        hata_desc = {"atlama": "Kelime veya satır atlama", "yanlis_okuma": "Kelimeyi farklı okuma", "yanlis": "Kelimeyi farklı okuma", "takilma": "Kelimede duraksama", "tekrar": "Aynı kelimeyi tekrar okuma"}
        hata_rows = [["Hata Türü", "Açıklama", "Sayı"]]
        toplam_hata = 0
        for h in hatalar:
            tur = h.get("tur", "")
            sayi = h.get("sayi", 0)
            toplam_hata += sayi
            hata_rows.append([hata_labels.get(tur, tur), hata_desc.get(tur, ""), str(sayi)])
        hata_rows.append(["TOPLAM", "", str(toplam_hata)])
        t3 = RLTable(hata_rows, colWidths=[3.5*cm, 6.5*cm, 2*cm])
        t3.setStyle(TableStyle(tbl_style(len(hata_rows)) + [
            ('FONTNAME', (0,-1), (-1,-1), FONTB),
            ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor('#E8F0FE')),
            ('ALIGN', (2,0), (2,-1), 'CENTER'),
        ]))
        el.append(t3)

    # ── 5. OKUDUĞUNU ANLAMA ──
    anlama = rapor.get("anlama", {})
    anlama_pct = rapor.get("anlama_yuzde", 0)
    anlama_sev = "İyi" if anlama_pct >= 85 else "Orta" if anlama_pct >= 70 else "Zayıf"
    el.append(RLPara(f"4. Okuduğunu Anlama Becerileri — %{anlama_pct}", styles['SectOBA']))

    # Anlama alt grupları
    anlama_gruplari = [
        ("4.1 Sözcük Düzeyinde Anlama", [
            ("Cümle anlamını kavrama", "cumle_anlama"),
            ("Bilinmeyen sözcük tahmini", "bilinmeyen_sozcuk"),
            ("Bağlaç ve zamirleri anlama", "baglac_zamir"),
        ]),
        ("4.2 Metnin Ana Yapısını Anlama", [
            ("Ana fikir belirleme", "ana_fikir"),
            ("Yardımcı fikirleri ifade etme", "yardimci_fikir"),
            ("Metnin konusunu ifade etme", "konu"),
            ("Başlık önerme", "baslik_onerme"),
        ]),
        ("4.3 Metinler Arasılık ve Derin Anlama", [
            ("Neden-sonuç ilişkisini belirleme", "neden_sonuc"),
            ("Çıkarım yapma", "cikarim"),
            ("Metindeki ipuçlarını kullanma", "ipuclari"),
            ("Yorumlama", "yorumlama"),
        ]),
        ("4.4 Eleştirel ve Yaratıcı Okuma", [
            ("Metne yönelik görüş bildirme", "gorus_bildirme"),
            ("Yazarın amacını sezme", "yazar_amaci"),
            ("Alternatif son / fikir üretme", "alternatif_fikir"),
            ("Metni günlük hayatla ilişkilendirme", "guncelle_hayat"),
        ]),
        ("4.5 Soru Performans Analizi", [
            ("Bilgi", "bilgi"),
            ("Kavrama", "kavrama"),
            ("Uygulama", "uygulama"),
            ("Analiz", "analiz"),
            ("Sentez", "sentez"),
            ("Değerlendirme", "degerlendirme"),
        ]),
    ]

    seviye_map = {"zayif": "Zayıf", "orta": "Orta", "iyi": "İyi"}
    for grup_baslik, olcutler in anlama_gruplari:
        el.append(RLPara(grup_baslik, styles['SubSectOBA']))
        rows = [["Ölçüt", "Zayıf", "Orta", "İyi"]]
        for label, key in olcutler:
            val = anlama.get(key, "orta")
            row = [label]
            for s in ["zayif", "orta", "iyi"]:
                row.append("+" if val == s else "")
            rows.append(row)
        t_a = RLTable(rows, colWidths=[7*cm, 3*cm, 3*cm, 3*cm])
        st = tbl_style(len(rows))
        # Renklendir: + işaretlerini turuncu yap
        for ri in range(1, len(rows)):
            for ci in range(1, 4):
                if rows[ri][ci] == "+":
                    st.append(('TEXTCOLOR', (ci, ri), (ci, ri), ora))
                    st.append(('FONTNAME', (ci, ri), (ci, ri), FONTB))
        st.append(('ALIGN', (1,0), (-1,-1), 'CENTER'))
        t_a.setStyle(TableStyle(st))
        el.append(t_a)

    # ── 6. PROZODİK OKUMA ──
    proz = rapor.get("prozodik", {})
    proz_toplam = rapor.get("prozodik_toplam", 0)
    proz_sev = "Çok İyi" if proz_toplam >= 18 else "İyi" if proz_toplam >= 14 else "Orta" if proz_toplam >= 10 else "Geliştirilmeli"
    el.append(RLPara("5. Prozodik Okuma Ölçeği", styles['SectOBA']))

    proz_desc = {
        "noktalama": ["Uymuyor", "Kısmen", "Çoğunlukla", "Tam ve bilinçli"],
        "vurgu": ["Tek düze", "Yer yer", "Anlama uygun", "Etkili ve bilinçli"],
        "tonlama": ["Monoton", "Sınırlı", "Metne uygun", "Doğal ve etkileyici"],
        "akicilik": ["Sık duraklama", "Kısmi akış", "Genel akıcı", "Kesintisiz"],
        "anlamli_gruplama": ["Sözcük sözcük", "Kısmen", "Çoğunlukla", "Tam ve tutarlı"],
    }
    proz_labels = {"noktalama": "Noktalama ve Duraklama", "vurgu": "Vurgu", "tonlama": "Tonlama", "akicilik": "Akıcılık", "anlamli_gruplama": "Anlamlı Gruplama"}

    proz_rows = [["Ölçüt", "1 puan", "2 puan", "3 puan", "4 puan", "Puan"]]
    for key in ["noktalama", "vurgu", "tonlama", "akicilik", "anlamli_gruplama"]:
        puan = proz.get(key, 0)
        descs = proz_desc.get(key, ["", "", "", ""])
        row = [proz_labels.get(key, key)]
        for pi in range(4):
            row.append(descs[pi])
        row.append(str(puan))
        proz_rows.append(row)
    proz_rows.append(["", "", "", "", "Toplam", str(proz_toplam)])

    t_p = RLTable(proz_rows, colWidths=[2.8*cm, 2.5*cm, 2.5*cm, 2.5*cm, 2.8*cm, 1.5*cm])
    ps = tbl_style(len(proz_rows))
    # Seçili puanı turuncu yap
    for ri in range(1, len(proz_rows) - 1):
        key = list(proz_desc.keys())[ri - 1]
        puan = proz.get(key, 0)
        if 1 <= puan <= 4:
            ps.append(('TEXTCOLOR', (puan, ri), (puan, ri), ora))
            ps.append(('FONTNAME', (puan, ri), (puan, ri), FONTB))
    ps.append(('ALIGN', (5, 0), (5, -1), 'CENTER'))
    ps.append(('FONTNAME', (0, -1), (-1, -1), FONTB))
    ps.append(('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#E8F0FE')))
    t_p.setStyle(TableStyle(ps))
    el.append(t_p)
    el.append(RLPara(f"Prozodik okuma performansı: <b>{proz_sev}</b> (Toplam {proz_toplam}/20)", styles['BodyOBA']))

    # ── 7. SONUÇ VE GENEL YORUM ──
    el.append(RLPara("6. Sonuç ve Genel Yorum", styles['SectOBA']))
    if rapor.get("ogretmen_notu"):
        for line in rapor.get("ogretmen_notu", "").split("\n"):
            if line.strip():
                el.append(RLPara(line.strip(), styles['BodyOBA']))

    # AI Yorumları
    ai = rapor.get("ai_yorumlar", {})
    if ai:
        el.append(Spacer(1, 6))
        ai_labels = {"hiz": "Okuma Hızı", "dogruluk": "Doğru Okuma", "anlama": "Anlama", "prozodik": "Prozodik Okuma", "sonuc": "Sonuç", "oneriler": "Öneriler"}
        for key, label in ai_labels.items():
            if ai.get(key):
                el.append(RLPara(f"<b>{label}:</b> {ai[key]}", styles['BodyOBA']))

    # ── KUR ──
    el.append(Spacer(1, 8))
    el.append(RLPara(f"Atanan Kur: <b>{rapor.get('atanan_kur', '-')}</b>", styles['BodyOBA']))

    # ── ALT BİLGİ ──
    el.append(Spacer(1, 20))
    el.append(HRFlowable(width="100%", thickness=0.5, color=bdr))
    el.append(RLPara("Bu rapor Okuma Becerileri Akademisi sistemi tarafından oluşturulmuştur.", styles['SmallOBA']))

    doc_pdf.build(el)
    buffer.seek(0)

    ogrenci_ad = rapor.get("ogrenci_ad", "ogrenci").replace(" ", "_")
    tarih = rapor.get("olusturma_tarihi", "")[:10]
    filename = f"Rapor_{ogrenci_ad}_{tarih}.pdf"

    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


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
    tur: str  # hizmetici, film, kitap, makale
    aciklama: str = ""
    hedef_kitle: str  # ogretmen, ogrenci, hepsi
    sorular: List[SoruModel] = []
    # Makale alanları
    makale_link: Optional[str] = None
    makale_dosya_turu: Optional[str] = None  # pdf, word, link

class IcerikModel(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    baslik: str
    tur: str
    aciklama: str = ""
    hedef_kitle: str
    sorular: List[SoruModel] = []
    makale_link: Optional[str] = None
    makale_dosya_turu: Optional[str] = None
    ekleyen_id: str = ""
    ekleyen_ad: str = ""
    durum: str = "beklemede"  # beklemede, oylama, yayinda, reddedildi
    oylar: dict = Field(default_factory=dict)  # {user_id: {"oy": True/False, "sebep": ""}}
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

# İçerik ekleme (admin veya öğretmen)
@api_router.post("/gelisim/icerik")
async def create_icerik(icerik: IcerikCreate, current_user=Depends(get_current_user)):
    role = current_user.get("role", "")
    if role not in ["admin", "coordinator", "teacher"]:
        raise HTTPException(status_code=403, detail="Yetkisiz")
    
    # Admin/Koordinatör eklerse direkt oylama, öğretmen eklerse beklemede
    durum = "oylama" if role in ["admin", "coordinator"] else "beklemede"
    
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
    await db.gelisim_icerik.insert_one(data)
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
        
        # Admin her şeyi görür
        if role == "admin":
            result.append(item)
        # Öğretmen: kendi eklediği + oylama bekleyenler + yayındakiler
        elif role == "teacher":
            if item.get("ekleyen_id") == user_id:
                result.append(item)
            elif durum == "oylama":
                result.append(item)
            elif durum == "yayinda" and hedef in ["hepsi", "ogretmen"]:
                result.append(item)
        # Öğrenci: sadece yayındakiler
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
# ─────────────────────────────────────────────

class ReadingLogCreate(BaseModel):
    kitap_id: Optional[str] = None
    kitap_adi: str = ""
    bolum: str = ""
    baslangic_sayfa: Optional[int] = None
    bitis_sayfa: Optional[int] = None
    sure_dakika: int = 0
    not_text: str = ""

class ReadingLogModel(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    ogrenci_id: str
    ogrenci_ad: str = ""
    kitap_id: Optional[str] = None
    kitap_adi: str = ""
    bolum: str = ""
    baslangic_sayfa: Optional[int] = None
    bitis_sayfa: Optional[int] = None
    sure_dakika: int = 0
    not_text: str = ""
    tarih: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


# Okuma kaydı oluştur
@api_router.post("/reading-logs")
async def create_reading_log(log: ReadingLogCreate, current_user=Depends(get_current_user)):
    # Öğrenci kendi kaydını oluşturur
    # Öğrenci user ise, linked student'ı bul
    ogrenci_id = current_user.get("linked_id") or current_user.get("id")
    ogrenci_ad = f"{current_user.get('ad', '')} {current_user.get('soyad', '')}".strip()

    # Eğer linked_id varsa student collection'dan adı çek
    if current_user.get("linked_id"):
        st = await db.students.find_one({"id": current_user["linked_id"]})
        if st:
            ogrenci_ad = f"{st.get('ad', '')} {st.get('soyad', '')}".strip()
            ogrenci_id = st["id"]

    model = ReadingLogModel(
        ogrenci_id=ogrenci_id,
        ogrenci_ad=ogrenci_ad,
        **log.dict()
    )
    data = model.dict()
    await db.reading_logs.insert_one(data)
    return data


# Öğrencinin okuma kayıtları
@api_router.get("/reading-logs/{ogrenci_id}")
async def get_reading_logs(ogrenci_id: str, current_user=Depends(get_current_user)):
    logs = await db.reading_logs.find({"ogrenci_id": ogrenci_id}).sort("tarih", -1).to_list(length=None)
    for log in logs:
        log.pop("_id", None)
    return logs


# Öğrencinin okuma istatistikleri
@api_router.get("/reading-logs/{ogrenci_id}/istatistik")
async def get_reading_stats(ogrenci_id: str, current_user=Depends(get_current_user)):
    logs = await db.reading_logs.find({"ogrenci_id": ogrenci_id}).to_list(length=None)

    toplam_dakika = sum(l.get("sure_dakika", 0) for l in logs)
    toplam_kayit = len(logs)
    kitaplar = set(l.get("kitap_adi", "") for l in logs if l.get("kitap_adi"))

    # Son 7 günün kaydı
    from datetime import timedelta
    simdi = datetime.utcnow()
    yedi_gun = simdi - timedelta(days=7)
    son_7_gun = [l for l in logs if l.get("tarih", "") >= yedi_gun.isoformat()]
    aktif_gunler = len(set(l.get("tarih", "")[:10] for l in son_7_gun))

    # Bugünkü okuma
    bugun = simdi.strftime("%Y-%m-%d")
    bugunun_kayitlari = [l for l in logs if l.get("tarih", "").startswith(bugun)]
    bugun_dakika = sum(l.get("sure_dakika", 0) for l in bugunun_kayitlari)

    # Streak hesapla
    tarihler = sorted(set(l.get("tarih", "")[:10] for l in logs), reverse=True)
    streak = 0
    kontrol = simdi.strftime("%Y-%m-%d")
    for i in range(60):
        gun = (simdi - timedelta(days=i)).strftime("%Y-%m-%d")
        if gun in tarihler:
            streak += 1
        elif i > 0:  # bugün yoksa streak kırılmamış olabilir
            break

    return {
        "toplam_dakika": toplam_dakika,
        "toplam_kayit": toplam_kayit,
        "toplam_kitap": len(kitaplar),
        "aktif_gunler_7": aktif_gunler,
        "bugun_dakika": bugun_dakika,
        "streak": streak,
        "kitaplar": list(kitaplar),
    }


# Öğrenci paneli: kendine atanan görevler
@api_router.get("/ogrenci-panel/gorevler")
async def get_ogrenci_gorevler(current_user=Depends(get_current_user)):
    ogrenci_id = current_user.get("linked_id") or current_user.get("id")
    gorevler = await db.gorevler.find({"hedef_id": ogrenci_id, "hedef_tip": "ogrenci"}).sort("olusturma_tarihi", -1).to_list(length=None)
    for g in gorevler:
        g.pop("_id", None)
    return gorevler


# Öğrenci paneli: profil bilgisi (student collection'dan)
@api_router.get("/ogrenci-panel/profil")
async def get_ogrenci_profil(current_user=Depends(get_current_user)):
    linked_id = current_user.get("linked_id")
    if linked_id:
        student = await db.students.find_one({"id": linked_id})
        if student:
            student.pop("_id", None)
            # Öğretmen bilgisini ekle
            ogretmen_bilgi = None
            if student.get("ogretmen_id"):
                t = await db.teachers.find_one({"id": student["ogretmen_id"]})
                if t:
                    ogretmen_bilgi = {"ad": t.get("ad",""), "soyad": t.get("soyad",""), "brans": t.get("brans",""), "telefon": t.get("telefon","")}
            return {**student, "user_ad": current_user.get("ad"), "user_soyad": current_user.get("soyad"), "email": current_user.get("email"), "ogretmen_bilgi": ogretmen_bilgi}
    return {
        "id": current_user.get("id"),
        "ad": current_user.get("ad", ""),
        "soyad": current_user.get("soyad", ""),
        "email": current_user.get("email", ""),
        "sinif": "",
        "kur": "",
        "ogretmen_bilgi": None,
    }


# Öğrenci paneli: anonim puan tablosu (sadece sıra + kendi konumu)
@api_router.get("/ogrenci-panel/siralama")
async def get_ogrenci_siralama(current_user=Depends(get_current_user)):
    ogrenci_id = current_user.get("linked_id") or current_user.get("id")
    # Tüm öğrencilerin okuma istatistiklerini çek
    tum_loglar = await db.reading_logs.find().to_list(length=None)

    # Öğrenci bazlı toplam dakika
    ogrenci_dakika = {}
    for log in tum_loglar:
        oid = log.get("ogrenci_id", "")
        ogrenci_dakika[oid] = ogrenci_dakika.get(oid, 0) + log.get("sure_dakika", 0)

    # Sırala
    siralama = sorted(ogrenci_dakika.items(), key=lambda x: x[1], reverse=True)

    # Anonim tablo oluştur
    tablo = []
    benim_siram = None
    for i, (oid, dakika) in enumerate(siralama):
        sira = i + 1
        if oid == ogrenci_id:
            benim_siram = sira
            tablo.append({"sira": sira, "dakika": dakika, "ben": True, "ad": "Sen 🌟"})
        else:
            tablo.append({"sira": sira, "dakika": dakika, "ben": False, "ad": f"Öğrenci #{sira}"})

    # Eğer ben listede yoksa ekle
    if benim_siram is None:
        tablo.append({"sira": len(tablo) + 1, "dakika": 0, "ben": True, "ad": "Sen 🌟"})
        benim_siram = len(tablo)

    return {"siralama": tablo[:20], "benim_siram": benim_siram, "toplam_ogrenci": len(siralama) or 1}


# ─────────────────────────────────────────────
# XP + LİG + KUR SİSTEMİ (Faz 3)
# ─────────────────────────────────────────────

XP_TABLOSU = {
    "okuma_gorevi": 10, "anlama_testi": 15, "kelime_gorevi": 8,
    "gunluk_streak": 5, "kitap_bitirme": 30, "yazili_ozet": 20,
    "egzersiz": 5, "gelisim_tamamla": 5, "gorev_tamamla": 10,
}

LIG_ESIKLERI = {
    "bronz": 0, "gumus": 200, "altin": 500, "elmas": 1000,
}

LIG_SIRA = ["bronz", "gumus", "altin", "elmas"]


# XP kazan
@api_router.post("/xp/kazan")
async def xp_kazan(payload: dict, current_user=Depends(get_current_user)):
    ogrenci_id = current_user.get("linked_id") or current_user.get("id")
    eylem = payload.get("eylem", "")
    xp = XP_TABLOSU.get(eylem, 0)
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
        if toplam >= LIG_ESIKLERI[l]:
            lig = l
            break
    # Sonraki lig
    idx = LIG_SIRA.index(lig)
    sonraki_lig = LIG_SIRA[idx + 1] if idx < len(LIG_SIRA) - 1 else None
    sonraki_esik = LIG_ESIKLERI.get(sonraki_lig, 0) if sonraki_lig else 0
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
            if xp >= LIG_ESIKLERI[l]:
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
    await db.students.update_one({"id": ogrenci_id}, {"$set": {"kur": yeni_kur}})
    return {"ok": True, "yeni_kur": yeni_kur}


# ─────────────────────────────────────────────
# MESAJLAŞMA SİSTEMİ
# ─────────────────────────────────────────────

class MesajCreate(BaseModel):
    alici_id: str
    alici_tip: str = ""  # user id veya teacher/student ref
    icerik: str
    konu: str = ""

class MesajModel(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    gonderen_id: str
    gonderen_ad: str = ""
    gonderen_rol: str = ""
    alici_id: str
    alici_ad: str = ""
    alici_rol: str = ""
    konu: str = ""
    icerik: str
    okundu: bool = False
    tarih: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


@api_router.post("/mesajlar")
async def create_mesaj(mesaj: MesajCreate, current_user=Depends(get_current_user)):
    gonderen_ad = f"{current_user.get('ad', '')} {current_user.get('soyad', '')}".strip()
    gonderen_rol = current_user.get("role", "")

    # Alıcı bilgisini bul
    alici = await db.users.find_one({"id": mesaj.alici_id})
    alici_ad = ""
    alici_rol = ""
    if alici:
        alici_ad = f"{alici.get('ad', '')} {alici.get('soyad', '')}".strip()
        alici_rol = alici.get("role", "")

    model = MesajModel(
        gonderen_id=current_user["id"],
        gonderen_ad=gonderen_ad,
        gonderen_rol=gonderen_rol,
        alici_id=mesaj.alici_id,
        alici_ad=alici_ad,
        alici_rol=alici_rol,
        konu=mesaj.konu,
        icerik=mesaj.icerik,
    )
    data = model.dict()
    await db.mesajlar.insert_one(data)
    return data


@api_router.get("/mesajlar")
async def get_mesajlar(current_user=Depends(get_current_user)):
    user_id = current_user["id"]
    mesajlar = await db.mesajlar.find({
        "$or": [{"gonderen_id": user_id}, {"alici_id": user_id}]
    }).sort("tarih", -1).to_list(length=None)
    for m in mesajlar:
        m.pop("_id", None)
    return mesajlar


@api_router.put("/mesajlar/{mesaj_id}/okundu")
async def mesaj_okundu(mesaj_id: str, current_user=Depends(get_current_user)):
    await db.mesajlar.update_one({"id": mesaj_id, "alici_id": current_user["id"]}, {"$set": {"okundu": True}})
    return {"ok": True}


@api_router.get("/mesajlar/okunmamis-sayisi")
async def okunmamis_sayisi(current_user=Depends(get_current_user)):
    sayi = await db.mesajlar.count_documents({"alici_id": current_user["id"], "okundu": False})
    return {"sayi": sayi}


# ─────────────────────────────────────────────
# GÖREV ATAMA SİSTEMİ
# İki yönlü: Yönetici → Öğretmen, Öğretmen → Öğrenci
# ─────────────────────────────────────────────

class GorevCreate(BaseModel):
    hedef_id: str
    hedef_tip: str  # "ogretmen" veya "ogrenci"
    baslik: str
    aciklama: str = ""
    tur: str = "ozel"  # ozel, film, kitap, makale, hizmetici, egzersiz
    icerik_id: Optional[str] = None
    son_tarih: Optional[str] = None
    makale_link: Optional[str] = None
    kitap_yazar: Optional[str] = None
    kitap_isbn: Optional[str] = None
    kitap_link: Optional[str] = None
    kitap_kapak: Optional[str] = None
    film_link: Optional[str] = None

class GorevModel(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    hedef_id: str
    hedef_tip: str
    hedef_ad: str = ""
    baslik: str
    aciklama: str = ""
    tur: str = "ozel"
    icerik_id: Optional[str] = None
    son_tarih: Optional[str] = None
    atayan_id: str = ""
    atayan_ad: str = ""
    atayan_rol: str = ""
    durum: str = "bekliyor"
    tamamlama_tarihi: Optional[str] = None
    tamamlama_notu: Optional[str] = None
    makale_link: Optional[str] = None
    kitap_yazar: Optional[str] = None
    kitap_isbn: Optional[str] = None
    kitap_link: Optional[str] = None
    kitap_kapak: Optional[str] = None
    film_link: Optional[str] = None
    olusturma_tarihi: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


@api_router.post("/gorevler")
async def create_gorev(gorev: GorevCreate, current_user=Depends(get_current_user)):
    role = current_user.get("role", "")
    if gorev.hedef_tip == "ogretmen" and role not in ["admin", "coordinator"]:
        raise HTTPException(status_code=403, detail="Öğretmenlere görev yalnızca yönetici/koordinatör atayabilir")
    if gorev.hedef_tip == "ogrenci" and role not in ["admin", "coordinator", "teacher"]:
        raise HTTPException(status_code=403, detail="Öğrencilere görev yalnızca öğretmen/yönetici atayabilir")

    hedef_ad = ""
    if gorev.hedef_tip == "ogretmen":
        user = await db.users.find_one({"id": gorev.hedef_id})
        if user:
            hedef_ad = f"{user.get('ad', '')} {user.get('soyad', '')}".strip()
        else:
            raise HTTPException(status_code=404, detail="Hedef öğretmen bulunamadı")
    elif gorev.hedef_tip == "ogrenci":
        student = await db.students.find_one({"id": gorev.hedef_id})
        if student:
            hedef_ad = f"{student.get('ad', '')} {student.get('soyad', '')}".strip()
        else:
            raise HTTPException(status_code=404, detail="Hedef öğrenci bulunamadı")

    model = GorevModel(
        **gorev.dict(),
        hedef_ad=hedef_ad,
        atayan_id=current_user["id"],
        atayan_ad=f"{current_user.get('ad', '')} {current_user.get('soyad', '')}".strip(),
        atayan_rol=role,
    )
    data = model.dict()
    await db.gorevler.insert_one(data)
    return data


@api_router.post("/gorevler/toplu")
async def create_toplu_gorev(payload: dict, current_user=Depends(get_current_user)):
    hedef_idler = payload.get("hedef_idler", [])
    hedef_tip = payload.get("hedef_tip", "")
    gorev_bilgi = payload.get("gorev", {})
    role = current_user.get("role", "")

    if hedef_tip == "ogretmen" and role not in ["admin", "coordinator"]:
        raise HTTPException(status_code=403, detail="Yetkisiz")
    if hedef_tip == "ogrenci" and role not in ["admin", "coordinator", "teacher"]:
        raise HTTPException(status_code=403, detail="Yetkisiz")

    olusturulan = []
    for hid in hedef_idler:
        hedef_ad = ""
        if hedef_tip == "ogretmen":
            u = await db.users.find_one({"id": hid})
            hedef_ad = f"{u.get('ad', '')} {u.get('soyad', '')}".strip() if u else ""
        elif hedef_tip == "ogrenci":
            s = await db.students.find_one({"id": hid})
            hedef_ad = f"{s.get('ad', '')} {s.get('soyad', '')}".strip() if s else ""

        model = GorevModel(
            hedef_id=hid, hedef_tip=hedef_tip, hedef_ad=hedef_ad,
            baslik=gorev_bilgi.get("baslik", ""), aciklama=gorev_bilgi.get("aciklama", ""),
            tur=gorev_bilgi.get("tur", "ozel"), icerik_id=gorev_bilgi.get("icerik_id"),
            son_tarih=gorev_bilgi.get("son_tarih"),
            makale_link=gorev_bilgi.get("makale_link"), kitap_yazar=gorev_bilgi.get("kitap_yazar"),
            kitap_isbn=gorev_bilgi.get("kitap_isbn"), kitap_link=gorev_bilgi.get("kitap_link"),
            kitap_kapak=gorev_bilgi.get("kitap_kapak"), film_link=gorev_bilgi.get("film_link"),
            atayan_id=current_user["id"],
            atayan_ad=f"{current_user.get('ad', '')} {current_user.get('soyad', '')}".strip(),
            atayan_rol=role,
        )
        data = model.dict()
        await db.gorevler.insert_one(data)
        olusturulan.append(data)

    return {"olusturulan": len(olusturulan), "gorevler": olusturulan}


@api_router.get("/gorevler")
async def get_gorevler(
    hedef_tip: Optional[str] = None,
    hedef_id: Optional[str] = None,
    durum: Optional[str] = None,
    current_user=Depends(get_current_user)
):
    role = current_user.get("role", "")
    user_id = current_user.get("id", "")
    filtre = {}
    if hedef_tip:
        filtre["hedef_tip"] = hedef_tip
    if hedef_id:
        filtre["hedef_id"] = hedef_id
    if durum:
        filtre["durum"] = durum

    if role == "teacher":
        items_atanan = await db.gorevler.find({"hedef_id": user_id, **({k: v for k, v in filtre.items() if k != "hedef_id"})}).sort("olusturma_tarihi", -1).to_list(length=None)
        items_atadigi = await db.gorevler.find({"atayan_id": user_id, **({k: v for k, v in filtre.items() if k != "hedef_id"})}).sort("olusturma_tarihi", -1).to_list(length=None)
        seen = set()
        items = []
        for i in items_atanan + items_atadigi:
            if i["id"] not in seen:
                seen.add(i["id"])
                items.append(i)
    else:
        items = await db.gorevler.find(filtre).sort("olusturma_tarihi", -1).to_list(length=None)

    for item in items:
        item.pop("_id", None)
    return items


@api_router.put("/gorevler/{gorev_id}/durum")
async def update_gorev_durum(gorev_id: str, payload: dict, current_user=Depends(get_current_user)):
    gorev = await db.gorevler.find_one({"id": gorev_id})
    if not gorev:
        raise HTTPException(status_code=404, detail="Görev bulunamadı")

    yeni_durum = payload.get("durum", "")
    update = {"durum": yeni_durum}
    if yeni_durum == "tamamlandi":
        update["tamamlama_tarihi"] = datetime.utcnow().isoformat()
        if payload.get("not"):
            update["tamamlama_notu"] = payload["not"]

    await db.gorevler.update_one({"id": gorev_id}, {"$set": update})
    return {"durum": yeni_durum}


@api_router.delete("/gorevler/{gorev_id}")
async def delete_gorev(gorev_id: str, current_user=Depends(get_current_user)):
    role = current_user.get("role", "")
    gorev = await db.gorevler.find_one({"id": gorev_id})
    if not gorev:
        raise HTTPException(status_code=404, detail="Görev bulunamadı")
    if gorev.get("atayan_id") != current_user["id"] and role not in ["admin", "coordinator"]:
        raise HTTPException(status_code=403, detail="Yalnızca atayan veya yönetici silebilir")
    await db.gorevler.delete_one({"id": gorev_id})
    return {"message": "Görev silindi"}


@api_router.get("/gorevler/istatistik")
async def get_gorev_istatistik(current_user=Depends(get_current_user)):
    tum = await db.gorevler.find().to_list(length=None)
    og = [g for g in tum if g.get("hedef_tip") == "ogretmen"]
    os = [g for g in tum if g.get("hedef_tip") == "ogrenci"]
    def h(l):
        return {"toplam": len(l), "bekliyor": len([g for g in l if g.get("durum") == "bekliyor"]),
                "devam_ediyor": len([g for g in l if g.get("durum") == "devam_ediyor"]),
                "tamamlandi": len([g for g in l if g.get("durum") == "tamamlandi"]),
                "suresi_doldu": len([g for g in l if g.get("durum") == "suresi_doldu"])}
    return {"ogretmen": h(og), "ogrenci": h(os)}


# ─────────────────────────────────────────────
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
