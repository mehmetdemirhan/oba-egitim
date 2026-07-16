"""Dashboard & istatistik endpoint'leri (/dashboard, /stats/*) ve modelleri.

server.py'dan birebir taşındı. Yollar, yanıt modelleri ve davranış değişmedi.
"""
import re
from datetime import datetime, timezone, timedelta, date
from typing import List

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from core.db import db
from core.auth import require_role, UserRole
from core.kayit_normalize import normalize_sinif

router = APIRouter()


def _kur_no(kur):
    """'Kur 3'/'3'/3 → 3; boş/çözülemez → None. Sınıflandırma kur NUMARASINA göre."""
    try:
        s = re.sub(r"\D", "", str(kur if kur is not None else ""))
        return int(s) if s else None
    except Exception:
        return None


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
    bu_ay_yeni_kayit: int = 0       # yalnız kur==1 (gerçek yeni kayıt)
    bu_ay_ust_kur: int = 0          # kur>1 ile doğrudan giren (üst kur girişi)
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
    # Yeni kayıt = KUR==1; kur>1 ile giren "üst kur girişi" sayılır (yeni öğrenci DEĞİL).
    bu_ay_kayitlar = await db.students.find(
        {"olusturma_tarihi": {"$gte": current_month_start.isoformat()}}, {"_id": 0, "kur": 1}).to_list(length=None)
    bu_ay_yeni_kayit = sum(1 for s in bu_ay_kayitlar if (_kur_no(s.get("kur")) or 1) == 1)
    bu_ay_ust_kur = sum(1 for s in bu_ay_kayitlar if (_kur_no(s.get("kur")) or 1) > 1)
    bu_ay_kur_atlayan = await db.kur_atlamalari.count_documents({"tarih": {"$gte": current_month_start.isoformat()}})
    return DashboardStats(
        toplam_ogretmen=teacher_count,
        toplam_ogrenci=student_count,
        toplam_kurs=course_count,
        toplam_ogrenci_alacak=total_student_receivable,
        toplam_ogretmen_borc=total_teacher_debt,
        bu_ay_odenen_toplam=monthly_total,
        bu_ay_yeni_kayit=bu_ay_yeni_kayit,
        bu_ay_ust_kur=bu_ay_ust_kur,
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
            yeni_ogrenciler=sum(1 for s in students_this_week if (_kur_no(s.get("kur")) or 1) == 1),  # kur==1
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
            yeni_ogrenciler=sum(1 for s in students_this_month if (_kur_no(s.get("kur")) or 1) == 1),  # kur==1
            odemeler=sum(p.get('miktar', 0) for p in payments_this_month),
            gelir=sum(s.get('yapilmasi_gereken_odeme', 0) for s in students_this_month),
            toplam_borc=sum(max(0, s.get('yapilmasi_gereken_odeme', 0) - s.get('yapilan_odeme', 0)) for s in students_total),
            kur_atlayan=kur_atlayan,
        ))
    return list(reversed(stats))


# ── Admin analitik: kur yenileme hunisi + nakit akışı/yaşlandırma + öğretmen perf ──
# TEK sorgu-partisi: tüm koleksiyonlar bir kez okunur, hesap bellekte (N+1 yok).
# Finansal içerik → yalnız admin. iptal kur kayıtları hesaba katılmaz.
def _gunf(s):
    try:
        return datetime.strptime(str(s)[:10], "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def _numf(v) -> float:
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


@router.get("/dashboard/analitik")
async def dashboard_analitik(current_user=Depends(require_role(UserRole.ADMIN))):
    """Kur yenileme hunisi + aylık nakit akışı + alacak yaşlandırma + öğretmen
    performansı. Mevcut verilerden; tek geçiş."""
    from modules.muhasebe import _kur_dagilimi, _kur_gizli  # FIFO tek kaynak (runtime import)

    bugun = datetime.now(timezone.utc).date()

    students = await db.students.find({}, {
        "_id": 0, "id": 1, "ogretmen_id": 1, "arsivli": 1, "aldigi_egitim": 1, "kur": 1,
        "yapilmasi_gereken_odeme": 1, "yapilan_odeme": 1, "olusturma_tarihi": 1}).to_list(length=None)
    teachers = await db.teachers.find({}, {"_id": 0, "id": 1, "ad": 1, "soyad": 1}).to_list(length=None)
    kurlar = await db.kur_ucretleri.find({"durum": {"$ne": "iptal"}}, {
        "_id": 0, "ogrenci_id": 1, "kur_adi": 1, "durum": 1, "tamamlanma_tarihi": 1,
        "baslangic_tarihi": 1, "tarih": 1, "tutar": 1, "odendi_donem": 1, "egitim_turu": 1}).to_list(length=None)
    payments = await db.payments.find({}, {"_id": 0, "tip": 1, "miktar": 1, "vergi": 1, "tarih": 1}).to_list(length=None)
    donem_odemeleri = await db.ogretmen_donem_odemeleri.find({}, {"_id": 0, "toplam": 1, "tarih": 1}).to_list(length=None)
    anketler = await db.veli_anketleri.find({}, {"_id": 0, "ogretmen_id": 1, "yanitlar": 1}).to_list(length=None)
    paylar_ayar = ((await db.sistem_ayarlari.find_one({"tip": "ogretmen_paylari"})) or {}).get("degerler", {}) or {}
    # Satış Başarısı için: kur geçişleri (yenileme) + genel kur ücreti (beklenen gelir)
    kur_atlamalari = await db.kur_atlamalari.find(
        {}, {"_id": 0, "tarih": 1, "kaynak": 1}).to_list(length=None)
    ucret_ayar = ((await db.sistem_ayarlari.find_one({"tip": "kur_ucretleri"})) or {}).get("degerler", {}) or {}
    genel_ucret = _numf(ucret_ayar.get("genel", 0)) or 14400

    def pay(et):
        turler = paylar_ayar.get("turler", {}) or {}
        if et and et in turler and turler[et] not in (None, ""):
            return _numf(turler[et])
        return _numf(paylar_ayar.get("genel", 0))

    # Son 12 ay anahtarları (eski→yeni)
    aylar = []
    yy, mm = bugun.year, bugun.month
    for _ in range(12):
        aylar.append(f"{yy:04d}-{mm:02d}")
        mm -= 1
        if mm < 1:
            mm = 12; yy -= 1
    aylar.reverse()

    # Öğrenci bazında kur kayıtları (tarih artan)
    kur_by_ogr = {}
    for k in kurlar:
        kur_by_ogr.setdefault(k.get("ogrenci_id"), []).append(k)
    for oid in kur_by_ogr:
        kur_by_ogr[oid].sort(key=lambda k: str(k.get("baslangic_tarihi") or k.get("tarih") or ""))

    # Seviye kümesi + tamamlanma tarihleri
    seviyeler, tamamlanan = {}, {}
    for oid, ks in kur_by_ogr.items():
        lv, comp = set(), {}
        for k in ks:
            n = _kur_no(k.get("kur_adi"))
            if n is None:
                continue
            lv.add(n)
            if k.get("durum") == "tamamlandi" and k.get("tamamlanma_tarihi"):
                d = _gunf(k["tamamlanma_tarihi"])
                if d:
                    comp[n] = d
        seviyeler[oid] = lv
        tamamlanan[oid] = comp

    # Üst kurdan kayıt = önceki kurlar TAMAMLANMIŞ sayılır (yalnız sayım/istatistik;
    # muhasebeye etki YOK — kur_ucretleri'ye kayıt açılmaz). Öğrenci mevcut kur K ise
    # 1..K-1 tamamlanmış + 1..K seviyesine ulaşılmış kabul edilir. Türetilen tamamlanma
    # tarihi SABİT ESKİ (trend penceresi dışında): huni sayımına girer, aylık trendi
    # kirletmez, 30 gün "beklemede" tetiklemez. Gerçek tamamlanma tarihi varsa KORUNUR.
    _TURETME_TARIHI = date(2000, 1, 1)
    for s in students:
        mk = _kur_no(s.get("kur"))
        if not mk or mk <= 1:
            continue
        oid = s.get("id")
        lv = seviyeler.setdefault(oid, set())
        comp = tamamlanan.setdefault(oid, {})
        for n in range(1, mk):
            lv.add(n)
            comp.setdefault(n, _TURETME_TARIHI)
        lv.add(mk)

    # 1a) Huni
    maxlv = max((max(lv) for lv in seviyeler.values() if lv), default=0)
    huni = []
    for N in range(1, maxlv + 1):
        tamamlayan = gecen = beklemede = 0
        for oid, comp in tamamlanan.items():
            if N in comp:
                tamamlayan += 1
                if (N + 1) in seviyeler[oid]:
                    gecen += 1
                elif (bugun - comp[N]).days < 30:
                    beklemede += 1
        if tamamlayan == 0:
            continue
        payda = tamamlayan - beklemede
        huni.append({"kur": N, "tamamlayan": tamamlayan, "gecen": gecen, "beklemede": beklemede,
                     "oran": round(gecen * 100 / payda, 1) if payda > 0 else None})

    # 1b) Aylık yenileme trendi
    yt = {a: {"tamamlanan": 0, "gecen": 0, "beklemede": 0} for a in aylar}
    for oid, comp in tamamlanan.items():
        for N, d in comp.items():
            key = f"{d.year:04d}-{d.month:02d}"
            if key not in yt:
                continue
            yt[key]["tamamlanan"] += 1
            if (N + 1) in seviyeler[oid]:
                yt[key]["gecen"] += 1
            elif (bugun - d).days < 30:
                yt[key]["beklemede"] += 1
    yenileme_trend = []
    for a in aylar:
        t = yt[a]
        payda = t["tamamlanan"] - t["beklemede"]
        yenileme_trend.append({"ay": a, **t, "oran": round(t["gecen"] * 100 / payda, 1) if payda > 0 else None})

    # 1c) Satış Başarısı — aylık SATILAN KUR = yeni kayıt kurları + yenileme kurları
    #     (mevcut öğrencinin sonraki kura geçişi). Yenileme oranı yenileme_trend ile
    #     tutarlı (30 gün beklemede penceresi). Beklenen gelir = satılan × genel ücret.
    oran_map = {r["ay"]: r["oran"] for r in yenileme_trend}
    sb_yeni = {a: 0 for a in aylar}
    sb_yenileme = {a: 0 for a in aylar}
    for s in students:
        d = _gunf(s.get("olusturma_tarihi"))
        if d:
            key = f"{d.year:04d}-{d.month:02d}"
            if key in sb_yeni:
                sb_yeni[key] += 1
    for ka in kur_atlamalari:
        # ust_kur_kayit = yeni kayıt (yukarıda sayıldı); yenileme = kur_gecis/manuel geçiş
        if (ka.get("kaynak") or "") not in ("kur_gecis", "manuel"):
            continue
        d = _gunf(ka.get("tarih"))
        if d:
            key = f"{d.year:04d}-{d.month:02d}"
            if key in sb_yenileme:
                sb_yenileme[key] += 1
    satis_basarisi = []
    for a in aylar:
        yeni, yenileme = sb_yeni[a], sb_yenileme[a]
        satilan = yeni + yenileme
        satis_basarisi.append({
            "ay": a, "yeni_kur": yeni, "yenileme_kur": yenileme, "satilan_kur": satilan,
            "yenileme_orani": oran_map.get(a), "beklenen_gelir": round(satilan * genel_ucret, 2),
        })

    # 2a) Aylık nakit akışı
    nk = {a: {"tahsilat": 0.0, "vergi": 0.0, "ogretmen_odeme": 0.0} for a in aylar}
    for p in payments:
        d = _gunf(p.get("tarih"))
        if not d:
            continue
        key = f"{d.year:04d}-{d.month:02d}"
        if key not in nk:
            continue
        if p.get("tip") == "ogrenci":
            nk[key]["tahsilat"] += _numf(p.get("miktar"))
            nk[key]["vergi"] += _numf(p.get("vergi"))
        elif p.get("tip") == "ogretmen":
            nk[key]["ogretmen_odeme"] += _numf(p.get("miktar"))
    for od in donem_odemeleri:
        d = _gunf(od.get("tarih"))
        if d and f"{d.year:04d}-{d.month:02d}" in nk:
            nk[f"{d.year:04d}-{d.month:02d}"]["ogretmen_odeme"] += _numf(od.get("toplam"))
    nakit_akisi = []
    for a in aylar:
        n = nk[a]
        nakit_akisi.append({"ay": a, "tahsilat": round(n["tahsilat"], 2), "vergi": round(n["vergi"], 2),
                            "ogretmen_odeme": round(n["ogretmen_odeme"], 2),
                            "net": round(n["tahsilat"] - n["vergi"] - n["ogretmen_odeme"], 2)})

    # 2b) Alacak yaşlandırma (yaş = kur başlangıç tarihinden bugüne)
    yas = {"0-30": {"sayi": 0, "toplam": 0.0}, "31-60": {"sayi": 0, "toplam": 0.0}, "60+": {"sayi": 0, "toplam": 0.0}}

    def _kova(gun):
        return "0-30" if gun <= 30 else "31-60" if gun <= 60 else "60+"

    for s in students:
        ks = kur_by_ogr.get(s["id"]) or []
        if ks:
            for drow in _kur_dagilimi(ks, _numf(s.get("yapilan_odeme"))):
                if _kur_gizli(drow) or drow["kalan"] <= 0.01:
                    continue
                bas = _gunf(drow.get("kayit_zamani"))
                k = _kova((bugun - bas).days if bas else 0)
                yas[k]["sayi"] += 1
                yas[k]["toplam"] += drow["kalan"]
        else:
            kalan = max(0.0, _numf(s.get("yapilmasi_gereken_odeme")) - _numf(s.get("yapilan_odeme")))
            if kalan > 0.01:
                bas = _gunf(s.get("olusturma_tarihi"))
                k = _kova((bugun - bas).days if bas else 0)
                yas[k]["sayi"] += 1
                yas[k]["toplam"] += kalan
    for k in yas:
        yas[k]["toplam"] = round(yas[k]["toplam"], 2)

    # Güncel dönem sınırları (öğretmen bu dönem hakedişi)
    if bugun.day <= 15:
        dy, dm = bugun.year, bugun.month
    else:
        dy, dm = (bugun.year + 1, 1) if bugun.month == 12 else (bugun.year, bugun.month + 1)
    donem_bitis = date(dy, dm, 15)
    oy, om = (dy - 1, 12) if dm == 1 else (dy, dm - 1)
    donem_bas = date(oy, om, 15)

    # 3) Öğretmen performansı
    anket_puan = {}
    for a in anketler:
        for y in (a.get("yanitlar") or []):
            if y.get("puan") is not None:
                anket_puan.setdefault(a.get("ogretmen_id"), []).append(_numf(y["puan"]))
    ogr_ogrenciler = {}
    for s in students:
        if s.get("ogretmen_id"):
            ogr_ogrenciler.setdefault(s["ogretmen_id"], []).append(s)

    performans = []
    for t in teachers:
        tid = t["id"]
        ogrs = ogr_ogrenciler.get(tid, [])
        aktif = sum(1 for s in ogrs if not s.get("arsivli"))
        sureler, geciken = [], 0
        tam_say = gec_say = bek_say = 0
        hakedis = 0.0
        for s in ogrs:
            slv = seviyeler.get(s["id"], set())
            for k in (kur_by_ogr.get(s["id"]) or []):
                n = _kur_no(k.get("kur_adi"))
                durum = k.get("durum")
                bas = _gunf(k.get("baslangic_tarihi") or k.get("tarih"))
                if durum == "tamamlandi" and k.get("tamamlanma_tarihi"):
                    tam = _gunf(k["tamamlanma_tarihi"])
                    if bas and tam:
                        sureler.append((tam - bas).days)
                    if n is not None:
                        tam_say += 1
                        if (n + 1) in slv:
                            gec_say += 1
                        elif tam and (bugun - tam).days < 30:
                            bek_say += 1
                elif durum in (None, "acik") and bas and (bugun - bas).days > 35:
                    geciken += 1
                # SPEC B: hakediş ödeme-bazlı — veli ödemesi tamamlanan (damgalı) kur
                # döneme giriyorsa; pay snapshot varsa ondan, yoksa güncel tanımdan.
                ott = _gunf(k.get("odeme_tamamlanma_tarihi")) if k.get("odeme_tamamlanma_tarihi") else None
                if ott and donem_bas < ott <= donem_bitis and not k.get("odendi_donem"):
                    pk = k.get("ogretmen_pay")
                    hakedis += _numf(pk) if pk is not None else pay(k.get("egitim_turu") or s.get("aldigi_egitim"))
        payda_yen = tam_say - bek_say
        puanlar = anket_puan.get(tid, [])
        performans.append({
            "ogretmen_id": tid, "ad": f"{t.get('ad', '')} {t.get('soyad', '')}".strip(),
            "aktif_ogrenci": aktif,
            "ort_tamamlama_gun": round(sum(sureler) / len(sureler), 1) if sureler else None,
            "geciken_kur": geciken,
            "tamamlanan_kur": tam_say,
            "yenileme_orani": (None if tam_say < 3 else (round(gec_say * 100 / payda_yen, 1) if payda_yen > 0 else None)),
            "yenileme_yetersiz": tam_say < 3,
            "memnuniyet": round(sum(puanlar) / len(puanlar), 2) if puanlar else None,
            "donem_hakedis": round(hakedis, 2),
        })
    performans.sort(key=lambda x: -x["aktif_ogrenci"])

    return {
        "huni": huni,
        "yenileme_trend": yenileme_trend,
        "satis_basarisi": satis_basarisi,
        "nakit_akisi": nakit_akisi,
        "yaslandirma": yas,
        "yaslandirma_tanim": "Yaş = kur başlangıç tarihinden bugüne (gün).",
        "ogretmen_performans": performans,
        "guncel_donem": f"{dy:04d}-{dm:02d}-15",
    }


@router.get("/dashboard/sinif-dagilimi")
async def sinif_dagilimi(current_user=Depends(require_role(UserRole.ADMIN, UserRole.COORDINATOR))):
    """Aktif öğrencilerin (arşivli + mezun HARİÇ) sınıf seviyesine göre dağılımı.
    1-8. sınıf ayrı kova; parse edilemeyen/boş/aralık dışı sınıf → '?' kovası.
    normalize_sinif ile ayrıştırılır (ilk rakam grubu, 1-12 aralığı). Anonim: yalnız sayı."""
    ogrenciler = await db.students.find(
        {"arsivli": {"$ne": True}, "mezun": {"$ne": True}},
        {"_id": 0, "sinif": 1},
    ).to_list(length=None)
    kovalar = {str(i): 0 for i in range(1, 9)}
    kovalar["?"] = 0
    for s in ogrenciler:
        n = normalize_sinif(s.get("sinif"))
        anahtar = str(n) if isinstance(n, int) and 1 <= n <= 8 else "?"
        kovalar[anahtar] += 1
    toplam = sum(kovalar.values())
    dagilim = [
        {"sinif": k, "etiket": (f"{k}. Sınıf" if k != "?" else "Belirsiz"),
         "sayi": v, "yuzde": round(v * 100 / toplam, 1) if toplam else 0.0}
        for k, v in kovalar.items()
    ]
    return {"dagilim": dagilim, "toplam": toplam}
