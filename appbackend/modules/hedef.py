"""Öğretmen hedef sistemi endpoint'leri (/hedefler/*) ve şablonları.

server.py'dan birebir taşındı. Yollar ve davranış değişmedi.
"""
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends

from core.db import db
from core.auth import get_current_user

router = APIRouter()


HEDEF_SABLONLARI = [
    {"kod": "ogrenci_sayisi", "baslik": "Öğrenci Sayısı", "ikon": "👥", "birim": "öğrenci", "aciklama": "Toplam aktif öğrenci sayısı"},
    {"kod": "kur_atlama", "baslik": "Kur Atlama", "ikon": "🎓", "birim": "kur atlama", "aciklama": "Toplam kur atlama sayısı"},
    {"kod": "icerik_uretme", "baslik": "İçerik Üretme", "ikon": "📚", "birim": "içerik", "aciklama": "Yayına alınan gelişim içeriği sayısı"},
    {"kod": "gorev_atama", "baslik": "Görev Atama", "ikon": "📌", "birim": "görev", "aciklama": "Atanan ve tamamlanan görev sayısı"},
    {"kod": "streak_ortalama", "baslik": "Öğrenci Streak Ortalaması", "ikon": "🔥", "birim": "gün", "aciklama": "Öğrencilerinizin ortalama okuma streak'i"},
    {"kod": "veli_puan", "baslik": "Veli Değerlendirme Puanı", "ikon": "⭐", "birim": "puan", "aciklama": "Veli anket ortalaması (1-5)"},
    {"kod": "rozet_sayisi", "baslik": "Rozet Kazanma", "ikon": "🏅", "birim": "rozet", "aciklama": "Kazanılan toplam rozet sayısı"},
    {"kod": "risk_azaltma", "baslik": "Riskli Öğrenci Azaltma", "ikon": "🛡️", "birim": "öğrenci", "aciklama": "Düşük riskli öğrenci sayısı"},
]


@router.get("/hedefler/sablonlar")
async def get_hedef_sablonlari():
    return HEDEF_SABLONLARI


@router.post("/hedefler")
async def create_hedef(payload: dict, current_user=Depends(get_current_user)):
    hedef = {
        "id": str(uuid.uuid4()),
        "kullanici_id": current_user["id"],
        "kod": payload.get("kod", ""),
        "baslik": payload.get("baslik", ""),
        "ikon": payload.get("ikon", "🎯"),
        "hedef_deger": payload.get("hedef_deger", 0),
        "baslangic_deger": payload.get("baslangic_deger", 0),
        "birim": payload.get("birim", ""),
        "son_tarih": payload.get("son_tarih", ""),
        "durum": "aktif",
        "olusturma_tarihi": datetime.utcnow().isoformat(),
    }
    await db.ogretmen_hedefler.insert_one(hedef)
    hedef.pop("_id", None)
    return hedef


@router.get("/hedefler")
async def get_hedefler(current_user=Depends(get_current_user)):
    hedefler = await db.ogretmen_hedefler.find({"kullanici_id": current_user["id"]}).sort("olusturma_tarihi", -1).to_list(length=None)
    ogretmen_id = current_user.get("linked_id") or current_user["id"]

    for h in hedefler:
        h.pop("_id", None)
        kod = h.get("kod", "")
        mevcut = 0
        if kod == "ogrenci_sayisi":
            mevcut = await db.students.count_documents({"ogretmen_id": ogretmen_id, "arsivli": {"$ne": True}})
        elif kod == "kur_atlama":
            # Elle (kaynak="manuel") kur düzenlemeleri hedefe sayılmaz.
            mevcut = await db.kur_atlamalari.count_documents({"ogretmen_id": ogretmen_id, "kaynak": {"$ne": "manuel"}})
        elif kod == "icerik_uretme":
            mevcut = await db.gelisim_icerik.count_documents({"ekleyen_id": current_user["id"], "durum": "yayinda"})
        elif kod == "gorev_atama":
            mevcut = await db.gorevler.count_documents({"atayan_id": current_user["id"], "durum": "tamamlandi"})
        elif kod == "streak_ortalama":
            ogrenciler = await db.students.find({"ogretmen_id": ogretmen_id, "arsivli": {"$ne": True}}).to_list(length=None)
            from datetime import timedelta
            simdi_h = datetime.utcnow()
            toplam_streak = 0
            for s in ogrenciler:
                logs = await db.reading_logs.find({"ogrenci_id": s["id"]}).to_list(length=None)
                tarihler = set(l.get("tarih", "")[:10] for l in logs)
                st = 0
                for i in range(60):
                    gun = (simdi_h - timedelta(days=i)).strftime("%Y-%m-%d")
                    if gun in tarihler: st += 1
                    elif i > 0: break
                toplam_streak += st
            mevcut = round(toplam_streak / max(len(ogrenciler), 1), 1)
        elif kod == "veli_puan":
            anketler = await db.veli_anketleri.find({"ogretmen_id": ogretmen_id}).to_list(length=None)
            if anketler:
                puanlar = []
                for a in anketler:
                    p = [y.get("puan", 0) for y in a.get("yanitlar", []) if y.get("puan")]
                    if p: puanlar.append(sum(p) / len(p))
                mevcut = round(sum(puanlar) / max(len(puanlar), 1), 1) if puanlar else 0
            else:
                mevcut = 0
        elif kod == "rozet_sayisi":
            mevcut = await db.kazanilan_rozetler.count_documents({"kullanici_id": current_user["id"]})
        elif kod == "risk_azaltma":
            ogrenciler = await db.students.find({"ogretmen_id": ogretmen_id, "arsivli": {"$ne": True}}).to_list(length=None)
            from datetime import timedelta
            simdi_h = datetime.utcnow()
            dusuk_risk = 0
            for s in ogrenciler:
                logs = await db.reading_logs.find({"ogrenci_id": s["id"]}).to_list(length=None)
                son7 = [l for l in logs if l.get("tarih", "") >= (simdi_h - timedelta(days=7)).isoformat()]
                if len(set(l.get("tarih", "")[:10] for l in son7)) >= 3:
                    dusuk_risk += 1
            mevcut = dusuk_risk

        h["mevcut_deger"] = mevcut
        h["ilerleme"] = min(100, round((mevcut / max(h.get("hedef_deger", 1), 0.1)) * 100))
        h["tamamlandi"] = mevcut >= h.get("hedef_deger", 0)
    return hedefler


@router.delete("/hedefler/{hedef_id}")
async def delete_hedef(hedef_id: str, current_user=Depends(get_current_user)):
    await db.ogretmen_hedefler.delete_one({"id": hedef_id, "kullanici_id": current_user["id"]})
    return {"ok": True}
