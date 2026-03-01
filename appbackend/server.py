from fastapi import FastAPI, APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional
import uuid
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
    linked_id: Optional[str] = None  # teacher_id, student_id or parent's student_id

class UserLogin(BaseModel):
    email: str
    password: str

class UserResponse(BaseModel):
    id: str
    ad: str
    soyad: str
    email: str
    role: UserRole
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
    user = await db.users.find_one({"email": credentials.email.lower().strip()})
    if not user or not verify_password(credentials.password, user.get("password_hash", "")):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="E-posta veya şifre hatalı"
        )
    
    token = create_access_token({"sub": user["id"], "role": user["role"]})
    
    user_response = UserResponse(
        id=user["id"],
        ad=user["ad"],
        soyad=user["soyad"],
        email=user["email"],
        role=user["role"],
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
        linked_id=current_user.get("linked_id"),
        olusturma_tarihi=datetime.fromisoformat(current_user["olusturma_tarihi"]) if isinstance(current_user.get("olusturma_tarihi"), str) else current_user.get("olusturma_tarihi", datetime.now(timezone.utc)),
        puan=current_user.get("puan", 0)
    )

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

class Course(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    ad: str
    fiyat: float
    sure: int
    olusturma_tarihi: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    ogrenci_sayisi: int = 0

class CourseCreate(BaseModel):
    ad: str
    fiyat: float
    sure: int

class CourseUpdate(BaseModel):
    ad: Optional[str] = None
    fiyat: Optional[float] = None
    sure: Optional[int] = None

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
async def update_normlar(data: NormGuncelle, current_user=Depends(require_role(UserRole.ADMIN))):
    await db.sistem_ayarlari.update_one(
        {"tip": "okuma_hizi_normlari"},
        {"$set": {"tip": "okuma_hizi_normlari", "normlar": data.normlar}},
        upsert=True
    )
    return {"message": "Norm tablosu güncellendi", "normlar": data.normlar}

@api_router.post("/diagnostic/texts/{metin_id}/admin-karar")
async def metin_admin_karar(metin_id: str, karar: dict, current_user=Depends(require_role(UserRole.ADMIN))):
    # karar: {"onay": True/False, "direkt": True/False}
    # direkt=True → oylama atla, direkt havuza al
    onay = karar.get("onay", False)
    direkt = karar.get("direkt", False)
    if not onay:
        yeni_durum = "reddedildi"
    elif direkt:
        yeni_durum = "havuzda"
        # Ekleyene +10 bonus puan (havuza direkt girince)
        metin = await db.analiz_metinler.find_one({"id": metin_id})
        if metin and metin.get("ekleyen_id"):
            await db.users.update_one({"id": metin["ekleyen_id"]}, {"$inc": {"puan": 10}})
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
    if role not in ["admin", "teacher"]:
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
    # Oy veren öğretmene +2 puan
    await db.users.update_one({"id": user_id}, {"$inc": {"puan": 2}})
    # %60 kontrolü
    ogretmenler = await db.users.find({"role": {"$in": ["teacher", "admin"]}}).to_list(length=None)
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
            # Metni ekleyene +10 bonus puan (havuza girince)
            ekleyen_id = metin.get("ekleyen_id")
            if ekleyen_id:
                await db.users.update_one({"id": ekleyen_id}, {"$inc": {"puan": 10}})
        elif oy_sayisi == toplam and onay_orani < 0.6:
            yeni_durum = "reddedildi"
            await db.analiz_metinler.update_one({"id": oy.metin_id}, {"$set": {"durum": "reddedildi"}})
    return {
        "mesaj": "Oyunuz kaydedildi (+2 puan)",
        "durum": yeni_durum,
        "onay_orani": round(onay_sayisi / max(toplam, 1) * 100),
        "oy_sayisi": oy_sayisi,
        "toplam": toplam
    }

@api_router.delete("/diagnostic/texts/{metin_id}")
async def delete_metin(metin_id: str, current_user=Depends(require_role(UserRole.ADMIN))):
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
    if current_user.get("role") not in ["admin", "teacher"]:
        raise HTTPException(status_code=403, detail="Yetkisiz")
    metin = await db.analiz_metinler.find_one({"id": data.metin_id})
    if not metin:
        raise HTTPException(status_code=404, detail="Metin bulunamadı")
    oturum = DiagnosticOturum(
        ogrenci_id=data.ogrenci_id,
        metin_id=data.metin_id,
        ogretmen_id=current_user["id"]
    )
    d = oturum.dict()
    d["olusturma_tarihi"] = d["olusturma_tarihi"].isoformat()
    d["tamamlama_tarihi"] = None
    await db.diagnostic_oturumlar.insert_one(d)
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
        "hata_sayilari": oturum.get("hatalar", []),
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

# ─────────────────────────────────────────────
# GELİŞİM ALANI
# ─────────────────────────────────────────────

class SoruModel(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    soru: str
    secenekler: List[str]
    dogru_cevap: int

class IcerikCreate(BaseModel):
    baslik: str
    tur: str  # hizmetici, film, kitap
    aciklama: str = ""
    hedef_kitle: str  # ogretmen, ogrenci, hepsi
    sorular: List[SoruModel] = []

class IcerikModel(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    baslik: str
    tur: str
    aciklama: str = ""
    hedef_kitle: str
    sorular: List[SoruModel] = []
    olusturma_tarihi: datetime = Field(default_factory=datetime.utcnow)

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

@api_router.post("/gelisim/icerik")
async def create_icerik(icerik: IcerikCreate, current_user=Depends(require_role(UserRole.ADMIN))):
    model = IcerikModel(**icerik.dict())
    data = model.dict()
    data['olusturma_tarihi'] = data['olusturma_tarihi'].isoformat()
    await db.gelisim_icerik.insert_one(data)
    return model

@api_router.get("/gelisim/icerik")
async def get_icerik_list(current_user=Depends(get_current_user)):
    items = await db.gelisim_icerik.find().sort("olusturma_tarihi", -1).to_list(length=None)
    result = []
    for item in items:
        item.pop('_id', None)
        # Filtrele: hedef kitle
        hedef = item.get('hedef_kitle', 'hepsi')
        rol = current_user.get('role', '')
        if hedef == 'hepsi' or (hedef == 'ogretmen' and rol == 'teacher') or (hedef == 'ogrenci' and rol == 'student') or rol == 'admin':
            result.append(item)
    return result

@api_router.delete("/gelisim/icerik/{icerik_id}")
async def delete_icerik(icerik_id: str, current_user=Depends(require_role(UserRole.ADMIN))):
    await db.gelisim_icerik.delete_one({"id": icerik_id})
    return {"message": "Silindi"}

@api_router.post("/gelisim/tamamla")
async def tamamla_icerik(data: TamamlamaCreate, current_user=Depends(get_current_user)):
    # Daha önce tamamladı mı?
    existing = await db.gelisim_tamamlama.find_one({"kullanici_id": data.kullanici_id, "icerik_id": data.icerik_id})
    if existing:
        raise HTTPException(status_code=400, detail="Bu içerik zaten tamamlandı")
    
    icerik = await db.gelisim_icerik.find_one({"id": data.icerik_id})
    if not icerik:
        raise HTTPException(status_code=404, detail="İçerik bulunamadı")
    
    sorular = icerik.get('sorular', [])
    toplam = len(sorular)
    dogru = 0
    test_yapildi = False
    puan = 1  # Sadece tamamlandı puanı
    
    if data.test_cevaplari and toplam > 0:
        test_yapildi = True
        for i, cevap in enumerate(data.test_cevaplari):
            if i < toplam and cevap == sorular[i].get('dogru_cevap'):
                dogru += 1
        # Puan: doğru sayısı / toplam * 10 (min 1, max 10)
        puan = max(1, round((dogru / toplam) * 10)) if toplam > 0 else 1
    
    tamamlama = TamamlamaModel(
        kullanici_id=data.kullanici_id,
        icerik_id=data.icerik_id,
        test_yapildi=test_yapildi,
        dogru_sayisi=dogru,
        toplam_soru=toplam,
        kazanilan_puan=puan
    )
    tamamlama_data = tamamlama.dict()
    tamamlama_data['tarih'] = tamamlama_data['tarih'].isoformat()
    await db.gelisim_tamamlama.insert_one(tamamlama_data)
    
    # Kullanıcı puanını güncelle
    await db.users.update_one({"id": data.kullanici_id}, {"$inc": {"puan": puan}})
    
    return {"puan": puan, "dogru": dogru, "toplam": toplam, "test_yapildi": test_yapildi}

@api_router.get("/gelisim/tamamlama/{kullanici_id}")
async def get_tamamlamalar(kullanici_id: str, current_user=Depends(get_current_user)):
    items = await db.gelisim_tamamlama.find({"kullanici_id": kullanici_id}).to_list(length=None)
    for item in items:
        item.pop('_id', None)
    return items

@api_router.get("/gelisim/puan-tablosu")
async def get_puan_tablosu(current_user=Depends(get_current_user)):
    users = await db.users.find().to_list(length=None)
    tablo = []
    for u in users:
        u.pop('_id', None)
        u.pop('hashed_password', None)
        tablo.append({"ad": u.get('ad',''), "soyad": u.get('soyad',''), "role": u.get('role',''), "puan": u.get('puan', 0)})
    tablo.sort(key=lambda x: x['puan'], reverse=True)
    return tablo



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
async def update_normlar(data: NormGuncelle, current_user=Depends(require_role(UserRole.ADMIN))):
    await db.sistem_ayarlari.update_one(
        {"tip": "okuma_hizi_normlari"},
        {"$set": {"tip": "okuma_hizi_normlari", "normlar": data.normlar}},
        upsert=True
    )
    return {"message": "Norm tablosu güncellendi", "normlar": data.normlar}

# ── Analiz Metinleri (Moderasyon Akışlı) ──
class AnalizMetinCreate(BaseModel):
    baslik: str
    icerik: str
    kelime_sayisi: int
    sinif_seviyesi: str
    tur: str = "hikaye"  # hikaye, bilgilendirici, siir

class AnalizMetin(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    baslik: str
    icerik: str
    kelime_sayisi: int
    sinif_seviyesi: str
    tur: str = "hikaye"
    ekleyen_id: str = ""
    ekleyen_ad: str = ""
    durum: str = "beklemede"  # beklemede, oylama, havuzda, reddedildi
    oylar: dict = Field(default_factory=dict)  # {user_id: {"onay": True/False, "sebep": ""}}
    olusturma_tarihi: datetime = Field(default_factory=datetime.utcnow)
    yayin_tarihi: Optional[datetime] = None

class MetinOyCreate(BaseModel):
    metin_id: str
    onay: bool
    sebep: str = ""

@api_router.post("/diagnostic/texts")
async def create_metin(metin: AnalizMetinCreate, current_user=Depends(get_current_user)):
    role = current_user.get("role", "")
    if role not in ["admin", "teacher"]:
        raise HTTPException(status_code=403, detail="Yetkisiz")
    # Kelime sayısını otomatik hesapla
    ks = len(metin.icerik.strip().split()) if metin.icerik else metin.kelime_sayisi
    # Admin eklerse direkt oylama, öğretmen eklerse beklemede
    durum = "oylama" if role == "admin" else "beklemede"
    model = AnalizMetin(
        **{**metin.dict(), "kelime_sayisi": ks},
        ekleyen_id=current_user["id"],
        ekleyen_ad=f"{current_user.get('ad','')} {current_user.get('soyad','')}",
        durum=durum
    )
    data = model.dict()
    data["olusturma_tarihi"] = data["olusturma_tarihi"].isoformat()
    data["yayin_tarihi"] = None
    await db.analiz_metinler.insert_one(data)
    # Metin ekleme katkı puanı: +5
    await db.users.update_one({"id": current_user["id"]}, {"$inc": {"puan": 5}})
    return data

@api_router.get("/diagnostic/texts")
async def get_metinler(current_user=Depends(get_current_user)):
    role = current_user.get("role", "")
    user_id = current_user.get("id", "")
    items = await db.analiz_metinler.find().sort("olusturma_tarihi", -1).to_list(length=None)
    result = []
    for item in items:
        item.pop("_id", None)
        durum = item.get("durum", "")
        if role == "admin":
            result.append(item)
        elif role == "teacher":
            # Kendi eklediği + oylama bekleyenler + havuzdakiler
            if item.get("ekleyen_id") == user_id or durum in ("oylama", "havuzda"):
                result.append(item)
        else:
            if durum == "havuzda":
                result.append(item)
    return result

@api_router.post("/diagnostic/texts/{metin_id}/admin-karar")
async def metin_admin_karar(metin_id: str, karar: dict, current_user=Depends(require_role(UserRole.ADMIN))):
    # karar: {"onay": True/False, "direkt": True/False}
    # direkt=True → oylama atla, direkt havuza al
    onay = karar.get("onay", False)
    direkt = karar.get("direkt", False)
    if not onay:
        yeni_durum = "reddedildi"
    elif direkt:
        yeni_durum = "havuzda"
        # Ekleyene +10 bonus puan (havuza direkt girince)
        metin = await db.analiz_metinler.find_one({"id": metin_id})
        if metin and metin.get("ekleyen_id"):
            await db.users.update_one({"id": metin["ekleyen_id"]}, {"$inc": {"puan": 10}})
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
    if role not in ["admin", "teacher"]:
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
    # Oy veren öğretmene +2 puan
    await db.users.update_one({"id": user_id}, {"$inc": {"puan": 2}})
    # %60 kontrolü
    ogretmenler = await db.users.find({"role": {"$in": ["teacher", "admin"]}}).to_list(length=None)
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
            # Metni ekleyene +10 bonus puan (havuza girince)
            ekleyen_id = metin.get("ekleyen_id")
            if ekleyen_id:
                await db.users.update_one({"id": ekleyen_id}, {"$inc": {"puan": 10}})
        elif oy_sayisi == toplam and onay_orani < 0.6:
            yeni_durum = "reddedildi"
            await db.analiz_metinler.update_one({"id": oy.metin_id}, {"$set": {"durum": "reddedildi"}})
    return {
        "mesaj": "Oyunuz kaydedildi (+2 puan)",
        "durum": yeni_durum,
        "onay_orani": round(onay_sayisi / max(toplam, 1) * 100),
        "oy_sayisi": oy_sayisi,
        "toplam": toplam
    }

@api_router.delete("/diagnostic/texts/{metin_id}")
async def delete_metin(metin_id: str, current_user=Depends(require_role(UserRole.ADMIN))):
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
    if current_user.get("role") not in ["admin", "teacher"]:
        raise HTTPException(status_code=403, detail="Yetkisiz")
    metin = await db.analiz_metinler.find_one({"id": data.metin_id})
    if not metin:
        raise HTTPException(status_code=404, detail="Metin bulunamadı")
    oturum = DiagnosticOturum(
        ogrenci_id=data.ogrenci_id,
        metin_id=data.metin_id,
        ogretmen_id=current_user["id"]
    )
    d = oturum.dict()
    d["olusturma_tarihi"] = d["olusturma_tarihi"].isoformat()
    d["tamamlama_tarihi"] = None
    await db.diagnostic_oturumlar.insert_one(d)
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
        "hata_sayilari": oturum.get("hatalar", []),
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
    tur: str  # hizmetici, film, kitap
    aciklama: str = ""
    hedef_kitle: str  # ogretmen, ogrenci, hepsi
    sorular: List[SoruModel] = []

class IcerikModel(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    baslik: str
    tur: str
    aciklama: str = ""
    hedef_kitle: str
    sorular: List[SoruModel] = []
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
    if role not in ["admin", "teacher"]:
        raise HTTPException(status_code=403, detail="Yetkisiz")
    
    # Admin eklerse direkt oylama, öğretmen eklerse beklemede
    durum = "oylama" if role == "admin" else "beklemede"
    
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
async def admin_karar(icerik_id: str, karar: dict, current_user=Depends(require_role(UserRole.ADMIN))):
    # direkt=True → oylama atla, direkt yayına al
    onay = karar.get("onay", False)
    direkt = karar.get("direkt", False)
    if not onay:
        yeni_durum = "reddedildi"
    elif direkt:
        yeni_durum = "yayinda"
        icerik = await db.gelisim_icerik.find_one({"id": icerik_id})
        if icerik and icerik.get("ekleyen_id"):
            await db.users.update_one({"id": icerik["ekleyen_id"]}, {"$inc": {"puan": 5}})
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
    if role not in ["admin", "teacher"]:
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
    
    # Oy veren öğretmene +2 puan
    await db.users.update_one({"id": user_id}, {"$inc": {"puan": 2}})
    
    # %60 kontrolü
    ogretmenler = await db.users.find({"role": {"$in": ["teacher", "admin"]}}).to_list(length=None)
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
            # İçerik ekleyene +5 bonus puan
            ekleyen_id = icerik.get("ekleyen_id")
            if ekleyen_id:
                await db.users.update_one({"id": ekleyen_id}, {"$inc": {"puan": 5}})
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
async def delete_icerik(icerik_id: str, current_user=Depends(require_role(UserRole.ADMIN))):
    await db.gelisim_icerik.delete_one({"id": icerik_id})
    return {"message": "Silindi"}


# ─────────────────────────────────────────────
# APP SETUP
# ─────────────────────────────────────────────

app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
