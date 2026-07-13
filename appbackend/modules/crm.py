"""CRM çekirdeği: öğretmen, öğrenci, kurs, ders, ödeme ve dışa aktarım.

server.py'dan birebir taşındı. Modeller, yollar, yanıt modelleri ve davranış
değişmedi. TeacherLevel core/auth'tan gelir.
"""
import asyncio
import logging
import re
import uuid
from datetime import datetime, timezone, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core.db import db, prepare_for_mongo, parse_from_mongo
from core.auth import get_current_user, require_role, UserRole, TeacherLevel, hash_password
from core.audit import islem_kaydet, islem_listele
from core.hesap import gecici_sifre_uret, OGRETMEN_ROLLERI
from core.sistem import get_vergi_orani, get_kur_ucreti, get_ogretmen_payi

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
    il: Optional[str] = None
    ilce: Optional[str] = None
    arsivli: bool = False
    # Eğitimi Tamamladı (mezuniyet) akışı
    mezun: bool = False
    tamamlama_tarihi: Optional[datetime] = None
    tamamlayan_id: Optional[str] = None
    tamamlayan_rol: Optional[str] = None
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
    il: Optional[str] = None
    ilce: Optional[str] = None

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
    il: Optional[str] = None
    ilce: Optional[str] = None
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
    # Vergi: yalnız öğrenci tahsilatlarında dolar; oran tahsilat anındaki ayardan
    # SABİTLENİR (sonradan oran değişse eski kayıt kendi oranıyla kalır).
    brut: Optional[float] = None
    vergi_orani: Optional[float] = None
    vergi: Optional[float] = None
    net: Optional[float] = None
    kur_ucreti_id: Optional[str] = None  # İŞ 3 — bu tahsilat hangi kur kaydına ait

class PaymentCreate(BaseModel):
    tip: str
    kisi_id: str
    miktar: float
    aciklama: Optional[str] = None
    tarih: Optional[datetime] = None  # verilmezse sunucu "şimdi" kullanır
    kur_ucreti_id: Optional[str] = None  # verilmezse öğrencinin aktif kuruna atfedilir

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
    students = await db.students.find({"ogretmen_id": teacher_id, "arsivli": {"$ne": True}}).to_list(length=None)
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

def _kur_no(kur):
    """'Kur 3' / '3' / 3 → 3; boş/çözülemez → None."""
    try:
        s = re.sub(r"\D", "", str(kur if kur is not None else ""))
        return int(s) if s else None
    except Exception:
        return None


async def kur_atlama_xp_kaydet(student: dict, yeni_kur, eski_kur="", kaynak="ust_kur", tarih=None):
    """Kur>1 girişi/atlaması için öğretmen XP kaydı (db.kur_atlamalari).

    Sınıflandırma KUR NUMARASINA göre: kur<=1 → yeni kayıt (kayıt yazılmaz),
    kur>1 → üst kur/kur atlama (öğretmene XP).

    - İdempotent: aynı öğrenci + aynı kur no için XP'ye sayılan (kaynak!=manuel)
      kayıt zaten varsa yeniden yazmaz → öğrenci+kur başına TEK XP.
    - ogretmen_id = students.ogretmen_id (teachers.id); XP tablosu (_ogr_id=linked_id)
      ve rozet motoru (_ogretmen_metrikleri linked_id çözer) bununla eşler.
    - kaynak != 'manuel' → +kur_basi XP (varsayılan 7) TÜRETİLİR (özel yol yok).
    - Öğretmenin users.id'siyle rozet_tetikle (seviye/rozet otomatik).
    Döner: yeni kayıt oluşturulduysa True.
    """
    ogretmen_tid = student.get("ogretmen_id")
    kur_no = _kur_no(yeni_kur)
    if not ogretmen_tid or kur_no is None or kur_no <= 1:
        return False  # öğretmensiz veya kur<=1 (yeni kayıt) → kur atlama değil
    # İdempotent: bu öğrenci+kur için XP'ye sayılan kayıt var mı?
    async for k in db.kur_atlamalari.find(
            {"ogrenci_id": student["id"], "kaynak": {"$ne": "manuel"}},
            {"_id": 0, "yeni_kur": 1, "yeni_kur_no": 1}):
        n = k.get("yeni_kur_no")
        if n is None:
            n = _kur_no(k.get("yeni_kur"))
        if n == kur_no:
            return False  # zaten işlenmiş — mükerrer XP yok
    await db.kur_atlamalari.insert_one({
        "id": str(uuid.uuid4()),
        "ogrenci_id": student["id"],
        "ogretmen_id": ogretmen_tid,
        "eski_kur": str(eski_kur or ""),
        "yeni_kur": str(yeni_kur),
        "yeni_kur_no": kur_no,
        "kaynak": kaynak,  # != "manuel" → XP'ye sayılır
        "tarih": tarih or datetime.now(timezone.utc).isoformat(),
    })
    # Rozet motoru: öğretmenin users.id'siyle tetikle (fire-and-forget; yükleme
    # sırası bağımsız olsun diye fonksiyon-içi import).
    try:
        from core.rozet_motor import rozet_tetikle
        tuser = await db.users.find_one({"linked_id": ogretmen_tid}, {"_id": 0, "id": 1})
        if tuser and tuser.get("id"):
            asyncio.create_task(rozet_tetikle(tuser["id"], "kur_atlama"))
    except Exception as ex:
        logging.warning(f"[kur_atlama_xp] rozet tetikleme hatası: {ex}")
    return True


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
    # ★ Kur>1 ile DOĞRUDAN kayıt = üst kur girişi → öğretmene kur-atlama XP'si
    #   (idempotent; kur<=1 ise no-op). "Yeni Kura Geçir" ile aynı XP kuralı.
    await kur_atlama_xp_kaydet(student.dict(), student.kur, eski_kur="", kaynak="ust_kur_kayit")
    return student

@router.get("/students")
async def get_students(dahil_arsiv: bool = False, durum: Optional[str] = None,
                       current_user=Depends(get_current_user)):
    # durum="mezun" → Eğitimi Tamamlayanlar listesi. Varsayılan aktif liste mezunları
    # da hariç tutar (mezun öğrenci aktiften düşer; muhasebe takibi ayrı sorgular kullanır).
    if durum == "mezun":
        sorgu = {"mezun": True}
    elif dahil_arsiv:
        sorgu = {}
    else:
        sorgu = {"arsivli": {"$ne": True}, "mezun": {"$ne": True}}
    students = await db.students.find(sorgu).to_list(length=None)
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

def _ogretmen_id(current_user: dict) -> str:
    return current_user.get("linked_id") or current_user.get("id")


def _ogrenci_sahiplik_kontrol(current_user: dict, student: dict):
    """Öğretmen yalnız KENDİ öğrencisine dokunabilir; admin/koordinatör herkese.
    Başka öğretmenin öğrencisine erişim → 403."""
    rol = current_user.get("role")
    if rol in ("admin", "coordinator"):
        return
    if rol == "teacher" and student.get("ogretmen_id") == _ogretmen_id(current_user):
        return
    raise HTTPException(status_code=403, detail="Bu öğrenci üzerinde yetkiniz yok")


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
    _ogrenci_sahiplik_kontrol(current_user, old_student)
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
    # Audit: değişen her alanı işlem kaydına yaz (öğrenci düzenleme izi).
    for alan, yeni_deger in update_data.items():
        eski_deger = old_student.get(alan)
        if eski_deger != yeni_deger:
            await islem_kaydet(current_user, "ogrenci", "duzenle", "ogrenci", student_id, alan, eski_deger, yeni_deger)
    student = await db.students.find_one({"id": student_id})
    return Student(**parse_from_mongo(student))


async def _ogrenci_veri_var_mi(student_id: str) -> bool:
    """Öğrencinin geçmiş/mali verisi (ödeme, kur ücreti, okuma/egzersiz) var mı?
    Varsa gerçek silme yerine pasife alınır (muhasebe/geçmiş kopmasın)."""
    for koleksiyon, alan in [(db.payments, "kisi_id"), (db.kur_ucretleri, "ogrenci_id"),
                             (db.reading_logs, "ogrenci_id"), (db.egzersiz_oturumlari, "ogrenci_id"),
                             (db.kur_atlamalari, "ogrenci_id")]:
        try:
            if await koleksiyon.find_one({alan: student_id}, {"_id": 1}):
                return True
        except Exception:
            continue
    return False


@router.delete("/students/{student_id}")
async def delete_student(student_id: str, kalici: bool = False, current_user=Depends(get_current_user)):
    """Öğrenci kaldırma. Varsayılan: SOFT-DELETE (arsivli=true) — muhasebe alacakları ve
    geçmiş veriler korunur. `kalici=true` VE öğrencinin hiç verisi yoksa (yanlış ekleme)
    gerçek silme yapılır. Öğretmen yalnız kendi öğrencisini kaldırabilir."""
    student = await db.students.find_one({"id": student_id})
    if not student:
        raise HTTPException(status_code=404, detail="Öğrenci bulunamadı")
    _ogrenci_sahiplik_kontrol(current_user, student)
    veri_var = await _ogrenci_veri_var_mi(student_id)

    if kalici and not veri_var:
        # Gerçek silme (yalnız verisi olmayan yanlış eklemede). Öğretmen bakiye/sayaç geri al.
        if student.get('ogretmen_id'):
            await db.teachers.update_one(
                {"id": student['ogretmen_id']},
                {"$inc": {"ogrenci_sayisi": -1, "yapilmasi_gereken_odeme": -student.get('ogretmene_yapilacak_odeme', 0)},
                 "$pull": {"atanan_ogrenciler": student_id}})
        await db.students.delete_one({"id": student_id})
        await islem_kaydet(current_user, "ogrenci", "sil_kalici", "ogrenci", student_id,
                           "kayit", f"{student.get('ad','')} {student.get('soyad','')}".strip(), None)
        return {"message": "Öğrenci kalıcı olarak silindi", "mod": "kalici"}

    # Soft-delete: pasife al. Mali kayıtlar/bakiye KORUNUR; aktif rosterden çıkar.
    await db.students.update_one({"id": student_id}, {"$set": {"arsivli": True}})
    if student.get('ogretmen_id'):
        await db.teachers.update_one({"id": student['ogretmen_id']},
                                     {"$inc": {"ogrenci_sayisi": -1}, "$pull": {"atanan_ogrenciler": student_id}})
    await islem_kaydet(current_user, "ogrenci", "kaldir", "ogrenci", student_id, "arsivli", False, True)
    return {"message": "Öğrenci pasife alındı (geçmiş korundu)", "mod": "pasif", "veri_var": veri_var}


class KurGecisRequest(BaseModel):
    kur_no: Optional[int] = None            # verilmezse mevcut kur +1
    baslangic_tarihi: Optional[str] = None  # yeni kurun başlangıcı (ISO/serbest)


@router.post("/students/{student_id}/kur-gecis")
async def kur_gecis(student_id: str, req: KurGecisRequest, current_user=Depends(get_current_user)):
    """Öğretmen (veya admin/koordinatör) öğrenciyi bir üst kura geçirir — PEDAGOJİK
    işlem. Finansal kayıt OTOMATİK oluşur; öğretmen tutar görmez/girmez:

    - Sahiplik: öğretmen yalnız kendi öğrencisini geçirebilir (aksi 403).
    - Mükerrer koruma: aynı öğrenci + aynı kur no ile ikinci kayıt açılamaz (409).
    - Önceki açık kur kaydı "tamamlandi" işaretlenir (kalan borç satırı tabloda
      açık/tarihçe kalır — borç yeni kura TAŞINMAZ, kaybolmaz da).
    - Yeni kur için beklenen tutar = Ayarlar'daki kur ücreti (eğitim türü bazlı,
      yoksa genel varsayılan). Vergi oranı kayda snapshot'lanır (tahsilatta uygulanır).
    - Muhasebeye yeni alacak satırı (db.kur_ucretleri + öğrenci beklenen $inc).
    - admin + accountant'a bildirim; işlem audit'e düşer.
    Öğretmene dönen yanıtta TUTAR YOKTUR (muhasebe/admin panelinde görünür)."""
    rol = current_user.get("role")
    if rol not in ("admin", "coordinator", "teacher"):
        raise HTTPException(status_code=403, detail="Bu işlem için yetkiniz yok")
    student = await db.students.find_one({"id": student_id})
    if not student:
        raise HTTPException(status_code=404, detail="Öğrenci bulunamadı")
    _ogrenci_sahiplik_kontrol(current_user, student)

    # Yeni kur numarası: verilmezse mevcut +1
    mevcut_kur = student.get("kur")
    try:
        mevcut_no = int(str(mevcut_kur).strip() or 0)
    except (TypeError, ValueError):
        mevcut_no = 0
    yeni_no = req.kur_no if req.kur_no else mevcut_no + 1
    if not yeni_no or yeni_no <= 0:
        raise HTTPException(status_code=422, detail="Geçerli bir kur numarası gerekli")
    yeni_kur_adi = str(yeni_no)

    # Mükerrer koruma: aynı öğrenci + aynı kur no (iptal edilmemiş) zaten varsa engelle
    var = await db.kur_ucretleri.find_one(
        {"ogrenci_id": student_id, "kur_adi": yeni_kur_adi, "durum": {"$ne": "iptal"}})
    if var:
        raise HTTPException(status_code=409, detail=f"Bu öğrenci için {yeni_no}. kur zaten açılmış")

    # Tutar Ayarlar'dan (eğitim türü bazlı) — öğretmen görmez/girmez
    egitim_turu = student.get("aldigi_egitim")
    tutar = await get_kur_ucreti(egitim_turu)
    vergi_orani = await get_vergi_orani()

    # Önceki açık kur(lar)ı tamamlandı işaretle + tamamlanma tarihi (dönem hesabı için).
    # Satır tabloda kalır; tamamlanma_tarihi öğretmen dönem ödemesinde kullanılır.
    tamamlanma = datetime.now(timezone.utc).isoformat()
    await db.kur_ucretleri.update_many(
        {"ogrenci_id": student_id, "durum": {"$in": [None, "acik"]}},
        {"$set": {"durum": "tamamlandi", "tamamlanma_tarihi": tamamlanma}})

    # Yeni alacak satırı
    kayit = {
        "id": str(uuid.uuid4()),
        "ogrenci_id": student_id,
        "kur_adi": yeni_kur_adi,
        "tutar": tutar,
        "baslangic_tarihi": (req.baslangic_tarihi or "").strip() or None,
        "tarih": datetime.now(timezone.utc).isoformat(),
        "ekleyen_id": current_user.get("id"),
        "ekleyen_rol": rol,
        "egitim_turu": egitim_turu,
        "vergi_orani": vergi_orani,
        "ogretmen_pay": await get_ogretmen_payi(egitim_turu),  # SPEC B snapshot
        "durum": "acik",
    }
    await db.kur_ucretleri.insert_one(kayit)
    await db.students.update_one(
        {"id": student_id},
        {"$set": {"kur": yeni_kur_adi}, "$inc": {"yapilmasi_gereken_odeme": tutar}})

    # ★ Kur atlama = öğretmene kur-atlama XP'si + rozet (idempotent). ogretmen_id
    #   öğrencinin kendi öğretmeni (teachers.id); işlemi kim tetiklerse XP ona gider.
    await kur_atlama_xp_kaydet(student, yeni_kur_adi, eski_kur=mevcut_kur, kaynak="kur_gecis")

    # Audit
    await islem_kaydet(current_user, "ogrenci", "kur_gecis", "ogrenci", student_id,
                       "kur", mevcut_kur, yeni_kur_adi)

    # Bildirim: admin + accountant (fonksiyon-içi import — yükleme sırası bağımsız)
    try:
        from modules.bildirim import bildirim_olustur
        ad = f"{student.get('ad', '')} {student.get('soyad', '')}".strip()
        icerik = f"{ad} {yeni_no}. kura geçirildi, ₺{tutar:.0f} alacak oluştu."
        async for u in db.users.find({"role": {"$in": ["admin", "accountant"]}}, {"_id": 0, "id": 1}):
            if u.get("id"):
                await bildirim_olustur(u["id"], "kur_gecisi", icerik, student_id)
    except Exception as ex:
        logging.warning(f"[kur_gecis] bildirim hatası: {ex}")

    # Öğretmene TUTAR dönmez
    return {"ok": True, "yeni_kur": yeni_no, "mesaj": f"{yeni_no}. kura geçirildi"}


def _ogrenci_borc(student: dict) -> float:
    """Öğrencinin toplam kalan borcu (beklenen - yapılan). Negatifse 0."""
    try:
        beklenen = float(student.get("yapilmasi_gereken_odeme") or 0)
        yapilan = float(student.get("yapilan_odeme") or 0)
        return max(0.0, round(beklenen - yapilan, 2))
    except (TypeError, ValueError):
        return 0.0


@router.post("/students/{student_id}/egitim-tamamla")
async def egitim_tamamla(student_id: str, current_user=Depends(get_current_user)):
    """Öğrencinin eğitimini tamamlandı olarak işaretler (mezuniyet).

    - Sahiplik: öğretmen yalnız kendi öğrencisi (aksi 403); admin/koordinatör serbest.
    - Açık kur(lar) 'tamamlandi' işaretlenir (tamamlanma_tarihi).
    - Borç yoksa (tüm kalan=0) → aktiften düşer, arşive kalkar (arsivli=True).
    - Borç varsa → aktiften düşer ama arşive KALKMAZ; muhasebede 'eğitimi bitti,
      borcu var' rozetiyle görünür (borç kapanınca otomatik arşivlenir — bkz.
      muhasebe ödeme akışı).
    - admin + accountant'a bildirim (borç dahil); işlem audit'e düşer.
    Öğretmene dönen yanıtta TUTAR yoktur."""
    rol = current_user.get("role")
    if rol not in ("admin", "coordinator", "teacher"):
        raise HTTPException(status_code=403, detail="Bu işlem için yetkiniz yok")
    student = await db.students.find_one({"id": student_id})
    if not student:
        raise HTTPException(status_code=404, detail="Öğrenci bulunamadı")
    _ogrenci_sahiplik_kontrol(current_user, student)
    if student.get("mezun"):
        raise HTTPException(status_code=409, detail="Öğrenci zaten eğitimini tamamlamış")

    now = datetime.now(timezone.utc).isoformat()
    # Açık kur(lar)ı tamamlandı işaretle (dönem hesabı için tamamlanma_tarihi)
    await db.kur_ucretleri.update_many(
        {"ogrenci_id": student_id, "durum": {"$in": [None, "acik"]}},
        {"$set": {"durum": "tamamlandi", "tamamlanma_tarihi": now}})

    borc = _ogrenci_borc(student)
    borcsuz = borc <= 0.01
    guncelle = {
        "mezun": True, "tamamlama_tarihi": now,
        "tamamlayan_id": current_user.get("id"), "tamamlayan_rol": rol,
    }
    # Borçsuzsa doğrudan arşive; borçluysa aktiften düşer ama arşive kalkmaz
    if borcsuz:
        guncelle["arsivli"] = True
    await db.students.update_one({"id": student_id}, {"$set": guncelle})

    await islem_kaydet(current_user, "ogrenci", "egitim_tamamla", "ogrenci", student_id,
                       "mezun", False, True,
                       ekstra={"borc": borc, "arsivlendi": borcsuz})

    # Bildirim: admin + accountant (borç bilgisiyle)
    try:
        from modules.bildirim import bildirim_olustur
        ad = f"{student.get('ad', '')} {student.get('soyad', '')}".strip()
        borc_str = "yok" if borcsuz else f"₺{borc:.0f}"
        icerik = f"{ad} eğitimini tamamladı (borç: {borc_str})."
        async for u in db.users.find({"role": {"$in": ["admin", "accountant"]}}, {"_id": 0, "id": 1}):
            if u.get("id"):
                await bildirim_olustur(u["id"], "egitim_tamamla", icerik, student_id)
    except Exception as ex:
        logging.warning(f"[egitim_tamamla] bildirim hatası: {ex}")

    return {"ok": True, "mezun": True, "arsivlendi": borcsuz,
            "mesaj": "Eğitim tamamlandı olarak işaretlendi"}


@router.post("/students/{student_id}/egitim-tamamla-geri-al")
async def egitim_tamamla_geri_al(student_id: str, current_user=Depends(get_current_user)):
    """Eğitimi tamamladı işaretini geri alır. Admin/koordinatör her zaman; öğrenciyi
    tamamlayan öğretmen yalnız 7 gün içinde. Öğrenci aktife döner; işlem loglanır.
    (Kur 'tamamlandi' işareti geri ALINMAZ — dönem/hakediş hesabı bozulmasın.)"""
    rol = current_user.get("role")
    student = await db.students.find_one({"id": student_id})
    if not student:
        raise HTTPException(status_code=404, detail="Öğrenci bulunamadı")
    if not student.get("mezun"):
        raise HTTPException(status_code=400, detail="Öğrenci zaten aktif")

    if rol in ("admin", "coordinator"):
        pass  # her zaman
    elif rol == "teacher":
        _ogrenci_sahiplik_kontrol(current_user, student)
        tam = student.get("tamamlama_tarihi")
        gecikti = True
        try:
            if tam:
                t = datetime.fromisoformat(tam)
                if t.tzinfo is None:
                    t = t.replace(tzinfo=timezone.utc)
                gecikti = (datetime.now(timezone.utc) - t) > timedelta(days=7)
        except ValueError:
            gecikti = True
        if gecikti:
            raise HTTPException(status_code=403,
                                detail="Geri alma süresi doldu (öğretmen için 7 gün). Yönetici geri alabilir.")
    else:
        raise HTTPException(status_code=403, detail="Bu işlem için yetkiniz yok")

    await db.students.update_one({"id": student_id}, {"$set": {
        "mezun": False, "arsivli": False, "tamamlama_tarihi": None,
        "tamamlayan_id": None, "tamamlayan_rol": None}})
    await islem_kaydet(current_user, "ogrenci", "egitim_tamamla_geri_al", "ogrenci",
                       student_id, "mezun", True, False)
    return {"ok": True, "mezun": False, "mesaj": "Eğitim tamamlama geri alındı, öğrenci aktife döndü"}


@router.get("/islem-log")
async def islem_log_listesi(modul: str | None = None, hedef_id: str | None = None,
                            kullanici_id: str | None = None, hedef_tip: str | None = None,
                            limit: int = 200,
                            current_user=Depends(require_role(UserRole.ADMIN, UserRole.COORDINATOR))):
    """Yönetici salt-okunur İşlem Kayıtları (audit izi). modul/hedef_id/kullanici_id/
    hedef_tip ile filtrelenir; yeni→eski sırada döner."""
    kayitlar = await islem_listele(modul=modul, hedef_id=hedef_id, kullanici_id=kullanici_id,
                                   hedef_tip=hedef_tip, limit=limit)
    return {"kayitlar": kayitlar}

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
    doc = payment.dict()
    if payment.tip == "ogrenci":
        # İŞ 1 — Vergi: oranı tahsilat anındaki ayardan SABİTLE (sonradan değişse eski kayıt korunur)
        orani = await get_vergi_orani()
        m = round(float(payment.miktar), 2)
        doc["brut"] = m
        doc["vergi_orani"] = orani
        doc["vergi"] = round(m * orani / 100.0, 2)
        doc["net"] = round(m - doc["vergi"], 2)
    await db.payments.insert_one(prepare_for_mongo({**doc}))
    if payment.tip == "ogrenci":
        await db.students.update_one({"id": payment.kisi_id}, {"$inc": {"yapilan_odeme": payment.miktar}})
    elif payment.tip == "ogretmen":
        await db.teachers.update_one({"id": payment.kisi_id}, {"$inc": {"yapilan_odeme": payment.miktar}})
    return Payment(**doc)

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
    if eski.get("tip") == "ogrenci":
        # Vergiyi kaydın KENDİ oranıyla yeniden hesapla (oran yoksa güncel oranı sabitle)
        orani = float(eski.get("vergi_orani") if eski.get("vergi_orani") is not None else await get_vergi_orani())
        guncelle["brut"] = round(float(yeni_miktar), 2)
        guncelle["vergi_orani"] = orani
        guncelle["vergi"] = round(float(yeni_miktar) * orani / 100.0, 2)
        guncelle["net"] = round(float(yeni_miktar) - guncelle["vergi"], 2)
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
        _ogr = p.get('tip') == 'ogrenci'
        payment_export.append({"Tarih": p.get('tarih',''), "Tip": 'Öğrenci' if _ogr else 'Öğretmen', "Kişi": f"{person.get('ad','')} {person.get('soyad','')}" if person else 'Bilinmiyor', "Miktar": p.get('miktar',0), "Brüt": p.get('brut', p.get('miktar',0)) if _ogr else '', "Vergi Oranı (%)": p.get('vergi_orani','') if _ogr else '', "Vergi": p.get('vergi','') if _ogr else '', "Net": p.get('net','') if _ogr else '', "Açıklama": p.get('aciklama','')})
    return ExportData(ogretmenler=teacher_export, ogrenciler=student_export, kurslar=course_export, odemeler=payment_export)
