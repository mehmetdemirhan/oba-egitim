"""Dashboard & istatistik endpoint'leri (/dashboard, /stats/*) ve modelleri.

server.py'dan birebir taşındı. Yollar, yanıt modelleri ve davranış değişmedi.
"""
from datetime import datetime, timezone, timedelta
from typing import List

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from core.db import db
from core.auth import require_role, UserRole

router = APIRouter()


class DashboardStats(BaseModel):
    toplam_ogretmen: int
    toplam_ogrenci: int
    toplam_kurs: int
    toplam_ogrenci_alacak: float
    toplam_ogretmen_borc: float
    bu_ay_odenen_toplam: float
    # Koordinatör dashboard'u için öğrenci-bazlı metrikler (additive; admin
    # görünümü bunları kullanmaz). "kur atlayan" hem öğretmen akışını hem elle
    # düzenlemeyi kapsar (tüm kur_atlamalari).
    bu_ay_yeni_kayit: int = 0
    bu_ay_kur_atlayan: int = 0

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
    kur_atlayan: int = 0  # o ay kur atlayan öğrenci sayısı (koordinatör grafiği)


@router.get("/dashboard", response_model=DashboardStats)
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
    # Bu ayki TAHSİLAT = yalnız öğrenci (veliden alınan) ödemeleri, brüt (öğretmene
    # yapılan ödemeler tahsilat değildir). Kart etiketi "Bu Ay Tahsilat" ile uyumlu.
    monthly_payments = await db.payments.find({"tarih": {"$gte": current_month_start.isoformat()}, "tip": "ogrenci"}).to_list(length=None)
    monthly_total = sum(p.get('miktar', 0) for p in monthly_payments)
    # Öğrenci-bazlı aylık metrikler (koordinatör dashboard'u)
    bu_ay_yeni_kayit = await db.students.count_documents({"olusturma_tarihi": {"$gte": current_month_start.isoformat()}})
    bu_ay_kur_atlayan = await db.kur_atlamalari.count_documents({"tarih": {"$gte": current_month_start.isoformat()}})
    return DashboardStats(
        toplam_ogretmen=teacher_count,
        toplam_ogrenci=student_count,
        toplam_kurs=course_count,
        toplam_ogrenci_alacak=total_student_receivable,
        toplam_ogretmen_borc=total_teacher_debt,
        bu_ay_odenen_toplam=monthly_total,
        bu_ay_yeni_kayit=bu_ay_yeni_kayit,
        bu_ay_kur_atlayan=bu_ay_kur_atlayan,
    )


@router.get("/dashboard/bekleyenler")
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

@router.get("/stats/weekly", response_model=List[WeeklyStats])
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

@router.get("/stats/monthly", response_model=List[MonthlyStats])
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
        kur_atlayan = await db.kur_atlamalari.count_documents({"tarih": {"$gte": month_start.isoformat(), "$lt": month_end.isoformat()}})
        stats.append(MonthlyStats(
            ay=month_start.strftime('%B %Y'),
            yeni_ogrenciler=len(students_this_month),
            odemeler=sum(p.get('miktar', 0) for p in payments_this_month),
            gelir=sum(s.get('yapilmasi_gereken_odeme', 0) for s in students_this_month),
            toplam_borc=sum(max(0, s.get('yapilmasi_gereken_odeme', 0) - s.get('yapilan_odeme', 0)) for s in students_total),
            kur_atlayan=kur_atlayan,
        ))
    return list(reversed(stats))
