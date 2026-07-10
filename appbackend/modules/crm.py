"""CRM çekirdeği: öğretmen, öğrenci, kurs, ders, ödeme ve dışa aktarım.

server.py'dan birebir taşındı. Modeller, yollar, yanıt modelleri ve davranış
değişmedi. TeacherLevel core/auth'tan gelir.
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core.db import db, prepare_for_mongo, parse_from_mongo
from core.auth import get_current_user, require_role, UserRole, TeacherLevel, hash_password
from core.hesap import gecici_sifre_uret, OGRETMEN_ROLLERI

router = APIRouter()


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
    # ── Opsiyonel hesap oluşturma (tek adımda user + teacher) ──
    hesap_olustur: bool = False
    email: Optional[str] = None
    hesap_rol: str = "teacher"   # teacher | coordinator | admin

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
    tarih: Optional[datetime] = None  # verilmezse sunucu "şimdi" kullanır

class PaymentUpdate(BaseModel):
    miktar: Optional[float] = None
    aciklama: Optional[str] = None
    tarih: Optional[datetime] = None

class ExportData(BaseModel):
    ogretmenler: List[dict]
    ogrenciler: List[dict]
    kurslar: List[dict]
    odemeler: List[dict]


@router.post("/teachers")
async def create_teacher(
    teacher_data: TeacherCreate,
    current_user=Depends(require_role(UserRole.ADMIN, UserRole.COORDINATOR)),
):
    teacher = Teacher(
        ad=teacher_data.ad, soyad=teacher_data.soyad, brans=teacher_data.brans,
        telefon=teacher_data.telefon, seviye=teacher_data.seviye,
        yapilmasi_gereken_odeme=teacher_data.yapilmasi_gereken_odeme,
    )
    await db.teachers.insert_one(prepare_for_mongo(teacher.dict()))
    sonuc = teacher.dict()

    # Opsiyonel: aynı adımda kullanıcı hesabı oluştur (user ↔ teacher köprüsü)
    if teacher_data.hesap_olustur and teacher_data.email:
        email = teacher_data.email.lower().strip()
        rol = teacher_data.hesap_rol if teacher_data.hesap_rol in OGRETMEN_ROLLERI else "teacher"
        if await db.users.find_one({"email": email}):
            raise HTTPException(status_code=400, detail="Bu e-posta zaten kayıtlı")
        gecici_sifre = gecici_sifre_uret()
        user_doc = {
            "id": str(uuid.uuid4()),
            "ad": teacher_data.ad, "soyad": teacher_data.soyad, "email": email,
            "telefon": teacher_data.telefon or None,
            "password_hash": hash_password(gecici_sifre),
            "role": rol, "linked_id": teacher.id,
            "sifre_degistirme_zorunlu": True,
            "olusturma_tarihi": datetime.now(timezone.utc).isoformat(),
        }
        await db.users.insert_one(user_doc)
        await db.teachers.update_one({"id": teacher.id}, {"$set": {"user_id": user_doc["id"]}})
        sonuc["user_id"] = user_doc["id"]
        sonuc["hesap"] = {"email": email, "rol": rol,
                          "gecici_sifre": gecici_sifre, "gecici_sifre_uretildi": True}
    return sonuc

@router.get("/teachers", response_model=List[Teacher])
async def get_teachers():
    teachers = await db.teachers.find().to_list(length=None)
    result = []
    for teacher in teachers:
        real_count = await db.students.count_documents({"ogretmen_id": teacher['id']})
        teacher['ogrenci_sayisi'] = real_count
        if teacher.get('ogrenci_sayisi', 0) != real_count:
            await db.teachers.update_one({"id": teacher['id']}, {"$set": {"ogrenci_sayisi": real_count}})
        # Tek bozuk kayıt (ör. eksik 'seviye') TÜM listeyi 500'e düşürmesin:
        # geçersiz kaydı atla + logla, geçerli kayıtları döndürmeye devam et.
        try:
            result.append(Teacher(**parse_from_mongo(teacher)))
        except Exception as ex:
            logging.warning(
                f"[crm] Teacher kaydı parse edilemedi, atlandı: id={teacher.get('id')} "
                f"ad={teacher.get('ad','')} {teacher.get('soyad','')} hata={type(ex).__name__}: {ex}"
            )
    return result

@router.get("/teachers/{teacher_id}", response_model=Teacher)
async def get_teacher(teacher_id: str):
    teacher = await db.teachers.find_one({"id": teacher_id})
    if not teacher:
        raise HTTPException(status_code=404, detail="Öğretmen bulunamadı")
    return Teacher(**parse_from_mongo(teacher))

@router.get("/teachers/{teacher_id}/students", response_model=List[Student])
async def get_teacher_students(teacher_id: str):
    teacher = await db.teachers.find_one({"id": teacher_id})
    if not teacher:
        raise HTTPException(status_code=404, detail="Öğretmen bulunamadı")
    students = await db.students.find({"ogretmen_id": teacher_id}).to_list(length=None)
    return [Student(**parse_from_mongo(s)) for s in students]

@router.put("/teachers/{teacher_id}", response_model=Teacher)
async def update_teacher(teacher_id: str, teacher_update: TeacherUpdate):
    update_data = teacher_update.dict(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="Güncellenecek veri bulunamadı")
    result = await db.teachers.update_one({"id": teacher_id}, {"$set": update_data})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Öğretmen bulunamadı")
    teacher = await db.teachers.find_one({"id": teacher_id})
    return Teacher(**parse_from_mongo(teacher))

@router.delete("/teachers/{teacher_id}")
async def delete_teacher(teacher_id: str):
    result = await db.teachers.delete_one({"id": teacher_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Öğretmen bulunamadı")
    return {"message": "Öğretmen başarıyla silindi"}

@router.post("/students", response_model=Student)
async def create_student(student_data: StudentCreate, current_user=Depends(get_current_user)):
    rol = current_user.get("role")
    if rol not in ("admin", "coordinator", "teacher"):
        raise HTTPException(status_code=403, detail="Bu işlem için yetkiniz yok")
    data = student_data.dict()
    if rol == "teacher":
        # Öğretmen kendi öğrencisini ekler: öğretmen ataması kendine sabitlenir,
        # mali alanlar body'den gelse bile yok sayılır.
        data["ogretmen_id"] = current_user.get("linked_id") or current_user.get("id")
        data["yapilmasi_gereken_odeme"] = 0.0
        data["ogretmene_yapilacak_odeme"] = 0.0
    elif rol == "coordinator":
        # Koordinatör admin ile AYNI formu kullanır (öğretmen atamasını seçebilir);
        # TEK fark: mali alanlar body'den gelse bile yok sayılır (muhasebe admin'e ait).
        data["yapilmasi_gereken_odeme"] = 0.0
        data["ogretmene_yapilacak_odeme"] = 0.0
    student = Student(**data)
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

@router.get("/students")
async def get_students(current_user=Depends(get_current_user)):
    students = await db.students.find().to_list(length=None)
    sonuc = [Student(**parse_from_mongo(s)).dict() for s in students]
    # Öğretmen + Koordinatör mali alanları görmemeli (muhasebe yalnızca admin'e ait).
    if current_user.get("role") in ("teacher", "coordinator"):
        for s in sonuc:
            for alan in ("yapilmasi_gereken_odeme", "yapilan_odeme", "ogretmene_yapilacak_odeme"):
                s.pop(alan, None)
    return sonuc

@router.get("/students/{student_id}", response_model=Student)
async def get_student(student_id: str):
    student = await db.students.find_one({"id": student_id})
    if not student:
        raise HTTPException(status_code=404, detail="Öğrenci bulunamadı")
    return Student(**parse_from_mongo(student))

@router.put("/students/{student_id}", response_model=Student)
async def update_student(student_id: str, student_update: StudentUpdate, current_user=Depends(get_current_user)):
    update_data = student_update.dict(exclude_unset=True)
    # Mali alanları yalnızca admin güncelleyebilir; öğretmen/koordinatör gönderse
    # bile yok sayılır (muhasebe yetkisi yalnız admin'e ait).
    if current_user.get("role") in ("teacher", "coordinator"):
        for alan in ("yapilmasi_gereken_odeme", "yapilan_odeme", "ogretmene_yapilacak_odeme"):
            update_data.pop(alan, None)
    if not update_data:
        raise HTTPException(status_code=400, detail="Güncellenecek veri bulunamadı")
    old_student = await db.students.find_one({"id": student_id})
    if not old_student:
        raise HTTPException(status_code=404, detail="Öğrenci bulunamadı")
    old_teacher_id = old_student.get('ogretmen_id')
    # ogretmen_id kısmi güncellemede gönderilmemişse mevcut atama korunur;
    # aksi halde None değeri "öğretmeni kaldır" olarak yanlış yorumlanırdı.
    new_teacher_id = update_data['ogretmen_id'] if 'ogretmen_id' in update_data else old_teacher_id
    old_payment = old_student.get('ogretmene_yapilacak_odeme', 0)
    new_payment = update_data.get('ogretmene_yapilacak_odeme', old_payment)
    await db.students.update_one({"id": student_id}, {"$set": update_data})
    # Elle kur değişimi de kur atlama olarak loglanır (dashboard "kur atlayan"
    # metriği için). kaynak="manuel" ile ayrışır; öğretmen rozet/hedef/başarı
    # sayaçları bu manuel kayıtları saymaz (kaynak != "manuel" filtresi).
    eski_kur = old_student.get('kur', '')
    if 'kur' in update_data and update_data['kur'] != eski_kur:
        await db.kur_atlamalari.insert_one({
            "id": str(uuid.uuid4()),
            "ogrenci_id": student_id,
            "ogretmen_id": new_teacher_id,
            "eski_kur": eski_kur,
            "yeni_kur": update_data['kur'],
            "tarih": datetime.now(timezone.utc).isoformat(),
            "kaynak": "manuel",
        })
    if old_teacher_id != new_teacher_id:
        if old_teacher_id:
            await db.teachers.update_one({"id": old_teacher_id}, {"$inc": {"ogrenci_sayisi": -1, "yapilmasi_gereken_odeme": -old_payment}, "$pull": {"atanan_ogrenciler": student_id}})
        if new_teacher_id:
            await db.teachers.update_one({"id": new_teacher_id}, {"$inc": {"ogrenci_sayisi": 1, "yapilmasi_gereken_odeme": new_payment}, "$addToSet": {"atanan_ogrenciler": student_id}})
    elif old_teacher_id and old_payment != new_payment:
        await db.teachers.update_one({"id": old_teacher_id}, {"$inc": {"yapilmasi_gereken_odeme": new_payment - old_payment}})
    student = await db.students.find_one({"id": student_id})
    return Student(**parse_from_mongo(student))

@router.delete("/students/{student_id}")
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

@router.post("/courses", response_model=Course)
async def create_course(course_data: CourseCreate):
    course = Course(**course_data.dict())
    await db.courses.insert_one(prepare_for_mongo(course.dict()))
    return course

@router.get("/courses", response_model=List[Course])
async def get_courses():
    courses = await db.courses.find().to_list(length=None)
    return [Course(**parse_from_mongo(c)) for c in courses]

@router.get("/courses/{course_id}", response_model=Course)
async def get_course(course_id: str):
    course = await db.courses.find_one({"id": course_id})
    if not course:
        raise HTTPException(status_code=404, detail="Kurs bulunamadı")
    return Course(**parse_from_mongo(course))

@router.put("/courses/{course_id}", response_model=Course)
async def update_course(course_id: str, course_update: CourseUpdate):
    update_data = course_update.dict(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="Güncellenecek veri bulunamadı")
    result = await db.courses.update_one({"id": course_id}, {"$set": update_data})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Kurs bulunamadı")
    course = await db.courses.find_one({"id": course_id})
    return Course(**parse_from_mongo(course))

@router.delete("/courses/{course_id}")
async def delete_course(course_id: str):
    result = await db.courses.delete_one({"id": course_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Kurs bulunamadı")
    return {"message": "Kurs başarıyla silindi"}

# ── Ders Endpoints ──
@router.get("/courses/{kurs_id}/dersler")
async def get_dersler(kurs_id: str):
    dersler = await db.dersler.find({"kurs_id": kurs_id}).sort("sira", 1).to_list(length=None)
    for d in dersler:
        d.pop("_id", None)
    return dersler

@router.post("/courses/{kurs_id}/dersler")
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

@router.put("/dersler/{ders_id}")
async def update_ders(ders_id: str, data: DersUpdate, current_user=Depends(get_current_user)):
    update = data.dict(exclude_unset=True)
    if update:
        await db.dersler.update_one({"id": ders_id}, {"$set": update})
    ders = await db.dersler.find_one({"id": ders_id})
    if ders:
        ders.pop("_id", None)
    return ders

@router.delete("/dersler/{ders_id}")
async def delete_ders(ders_id: str, current_user=Depends(get_current_user)):
    await db.dersler.delete_one({"id": ders_id})
    return {"message": "Ders silindi"}

@router.post("/dersler/{ders_id}/icerik")
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

@router.delete("/dersler/{ders_id}/icerik/{icerik_id}")
async def delete_ders_icerik(ders_id: str, icerik_id: str, current_user=Depends(get_current_user)):
    await db.dersler.update_one({"id": ders_id}, {"$pull": {"icerikler": {"id": icerik_id}}})
    return {"message": "İçerik silindi"}

@router.post("/payments", response_model=Payment)
async def create_payment(payment_data: PaymentCreate,
                         current_user=Depends(require_role(UserRole.ADMIN, UserRole.ACCOUNTANT))):
    # None alanları düş: tarih verilmezse Payment modelinin varsayılanı (şimdi) kullanılır.
    payment = Payment(**{k: v for k, v in payment_data.dict().items() if v is not None})
    await db.payments.insert_one(prepare_for_mongo(payment.dict()))
    if payment.tip == "ogrenci":
        await db.students.update_one({"id": payment.kisi_id}, {"$inc": {"yapilan_odeme": payment.miktar}})
    elif payment.tip == "ogretmen":
        await db.teachers.update_one({"id": payment.kisi_id}, {"$inc": {"yapilan_odeme": payment.miktar}})
    return payment

@router.get("/payments", response_model=List[Payment])
async def get_payments(current_user=Depends(require_role(UserRole.ADMIN, UserRole.ACCOUNTANT))):
    payments = await db.payments.find().sort("tarih", -1).to_list(length=None)
    return [Payment(**parse_from_mongo(p)) for p in payments]

@router.delete("/payments/{payment_id}")
async def delete_payment(payment_id: str,
                         current_user=Depends(require_role(UserRole.ADMIN, UserRole.ACCOUNTANT))):
    payment = await db.payments.find_one({"id": payment_id})
    if not payment:
        raise HTTPException(status_code=404, detail="Ödeme bulunamadı")
    if payment['tip'] == "ogrenci":
        await db.students.update_one({"id": payment['kisi_id']}, {"$inc": {"yapilan_odeme": -payment['miktar']}})
    elif payment['tip'] == "ogretmen":
        await db.teachers.update_one({"id": payment['kisi_id']}, {"$inc": {"yapilan_odeme": -payment['miktar']}})
    await db.payments.delete_one({"id": payment_id})
    return {"message": "Ödeme başarıyla silindi"}

@router.put("/payments/{payment_id}", response_model=Payment)
async def update_payment(payment_id: str, data: PaymentUpdate,
                         current_user=Depends(require_role(UserRole.ADMIN, UserRole.ACCOUNTANT))):
    """Ödeme düzeltme: miktar/açıklama/tarih güncellenir. Miktar değişirse kişi
    bakiyesi (yapilan_odeme) fark kadar ayarlanır. tip/kisi_id değişmez."""
    eski = await db.payments.find_one({"id": payment_id})
    if not eski:
        raise HTTPException(status_code=404, detail="Ödeme bulunamadı")
    yeni_miktar = data.miktar if data.miktar is not None else eski.get("miktar", 0)
    delta = float(yeni_miktar) - float(eski.get("miktar", 0))
    if delta and eski.get("tip") == "ogrenci":
        await db.students.update_one({"id": eski["kisi_id"]}, {"$inc": {"yapilan_odeme": delta}})
    elif delta and eski.get("tip") == "ogretmen":
        await db.teachers.update_one({"id": eski["kisi_id"]}, {"$inc": {"yapilan_odeme": delta}})
    guncelle = {"miktar": float(yeni_miktar)}
    if data.aciklama is not None:
        guncelle["aciklama"] = data.aciklama
    if data.tarih is not None:
        guncelle["tarih"] = data.tarih.isoformat()
    await db.payments.update_one({"id": payment_id}, {"$set": guncelle})
    guncel = await db.payments.find_one({"id": payment_id})
    return Payment(**parse_from_mongo(guncel))

@router.get("/export", response_model=ExportData)
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
