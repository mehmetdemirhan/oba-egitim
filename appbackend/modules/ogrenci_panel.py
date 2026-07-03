"""Okuma kayıtları (reading_logs) + öğrenci paneli endpoint'leri.

server.py'dan birebir taşındı. Yollar ve davranış değişmedi.
"""
import uuid
import asyncio
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from core.db import db
from core.auth import get_current_user
from core.rozet_motor import rozet_tetikle

router = APIRouter()


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
@router.post("/reading-logs")
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
    data.pop("_id", None)  # insert_one'ın eklediği ObjectId JSON serileştirmede patlamasın
    # Event: okuma kaydı okuma/kitap/streak/orman rozetlerini tetikler (fire-and-forget)
    asyncio.create_task(rozet_tetikle(current_user["id"], "okuma_kaydi"))
    return data


# Öğrencinin okuma kayıtları
@router.get("/reading-logs/{ogrenci_id}")
async def get_reading_logs(ogrenci_id: str, current_user=Depends(get_current_user)):
    logs = await db.reading_logs.find({"ogrenci_id": ogrenci_id}).sort("tarih", -1).to_list(length=None)
    for log in logs:
        log.pop("_id", None)
    return logs


# Öğrencinin okuma istatistikleri
@router.get("/reading-logs/{ogrenci_id}/istatistik")
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
@router.get("/ogrenci-panel/gorevler")
async def get_ogrenci_gorevler(current_user=Depends(get_current_user)):
    ogrenci_id = current_user.get("linked_id") or current_user.get("id")
    gorevler = await db.gorevler.find({"hedef_id": ogrenci_id, "hedef_tip": "ogrenci"}).sort("olusturma_tarihi", -1).to_list(length=None)
    for g in gorevler:
        g.pop("_id", None)
    return gorevler


# Öğrenci paneli: profil bilgisi (student collection'dan)
@router.get("/ogrenci-panel/profil")
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
@router.get("/ogrenci-panel/siralama")
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
