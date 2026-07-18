"""Bildirim sistemi: tür tanımları, üretici, endpoint'ler ve otomatik tetikleyiciler.

server.py'dan birebir taşındı. Yollar ve davranış değişmedi.

Paylaşılan semboller (BILDIRIM_TURLERI, bildirim_olustur, bildirim_gorev_atandi,
bildirim_rapor_tamamlandi) server.py ve diğer modüller tarafından import edilebilir;
böylece mesaj/görev/hedef gibi modüller bildirim'e bağımlı kalabilir.
"""
import uuid
import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Body

from core.db import db
from core.auth import get_current_user

router = APIRouter()


# Her tür için: baslik, oncelik(eski uyum), kategori(ogrenci|ogretmen|veli),
# onem(kritik|orta|bilgi|dusuk), cooldown_saat(spam engeli; 0 = kısıtsız)
BILDIRIM_TURLERI = {
    "rapor_tamamlandi": {"baslik": "📋 Rapor Hazır", "oncelik": "yuksek", "kategori": "veli", "onem": "bilgi", "cooldown_saat": 0},
    "gorev_atandi":     {"baslik": "📌 Yeni Görev", "oncelik": "normal", "kategori": "ogrenci", "onem": "orta", "cooldown_saat": 0},
    "gorev_tamamlandi": {"baslik": "✅ Görev Tamamlandı", "oncelik": "normal", "kategori": "ogretmen", "onem": "bilgi", "cooldown_saat": 0},
    "gorev_hatirlatma": {"baslik": "⏰ Görev Hatırlatma", "oncelik": "normal", "kategori": "ogrenci", "onem": "orta", "cooldown_saat": 24},
    "streak_kirildi":   {"baslik": "🔥 Streak Uyarısı", "oncelik": "yuksek", "kategori": "ogrenci", "onem": "orta", "cooldown_saat": 24},
    "streak_tebrik":    {"baslik": "🎉 Streak Tebrik", "oncelik": "normal", "kategori": "ogrenci", "onem": "bilgi", "cooldown_saat": 24},
    "kur_atladi":       {"baslik": "🎓 Kur Atlama", "oncelik": "yuksek", "kategori": "ogrenci", "onem": "bilgi", "cooldown_saat": 0},
    "mesaj_geldi":      {"baslik": "✉️ Yeni Mesaj", "oncelik": "normal", "kategori": "veli", "onem": "bilgi", "cooldown_saat": 0},
    "rozet_kazandi":    {"baslik": "🏅 Yeni Rozet", "oncelik": "normal", "kategori": "ogrenci", "onem": "bilgi", "cooldown_saat": 0},
    "risk_yuksek":      {"baslik": "🚨 Yüksek Risk", "oncelik": "yuksek", "kategori": "ogrenci", "onem": "kritik", "cooldown_saat": 24},
    "anket_hatirlatma": {"baslik": "⭐ Değerlendirme", "oncelik": "normal", "kategori": "veli", "onem": "bilgi", "cooldown_saat": 24},
    "lig_yukseldi":     {"baslik": "🏆 Lig Yükselme", "oncelik": "normal", "kategori": "ogrenci", "onem": "bilgi", "cooldown_saat": 0},
    "haftalik_ozet":    {"baslik": "📊 Haftalık Özet", "oncelik": "normal", "kategori": "ogretmen", "onem": "dusuk", "cooldown_saat": 24},
    "ders_degisiklik":  {"baslik": "📅 Ders Değişikliği", "oncelik": "yuksek", "kategori": "veli", "onem": "orta", "cooldown_saat": 0},
    "kur_gecisi":       {"baslik": "🎓 Kur Geçişi — Yeni Alacak", "oncelik": "yuksek", "kategori": "ogretmen", "onem": "orta", "cooldown_saat": 0},
    "kur_gecikme":      {"baslik": "⏰ Kur Süresi Aşıldı", "oncelik": "yuksek", "kategori": "ogretmen", "onem": "orta", "cooldown_saat": 0},
    "sss_yanit":        {"baslik": "✅ Sorunuz Yanıtlandı", "oncelik": "normal", "kategori": "ogrenci", "onem": "bilgi", "cooldown_saat": 0},
    "egitim_tamamla":   {"baslik": "🎓 Eğitim Tamamlandı", "oncelik": "normal", "kategori": "ogrenci", "onem": "bilgi", "cooldown_saat": 0},
    "ai_ceo_haftalik":  {"baslik": "📊 AI CEO Haftalık Brifing", "oncelik": "normal", "kategori": "ogretmen", "onem": "bilgi", "cooldown_saat": 24},
    "ai_ceo_anomali":   {"baslik": "⚠️ AI CEO Anomali", "oncelik": "yuksek", "kategori": "ogretmen", "onem": "kritik", "cooldown_saat": 12},
    "ai_ceo_mektup":    {"baslik": "📩 Performans Mektubu", "oncelik": "yuksek", "kategori": "ogretmen", "onem": "orta", "cooldown_saat": 0},
    "ai_ceo_miran":     {"baslik": "🧭 Sistem Danışmanı Miran", "oncelik": "normal", "kategori": "ogretmen", "onem": "bilgi", "cooldown_saat": 24},
    "timi_taslak_uyari": {"baslik": "🗑️ TIMI Taslağı Silinecek", "oncelik": "normal", "kategori": "ogretmen", "onem": "orta", "cooldown_saat": 24},
    "analiz_taslak_uyari": {"baslik": "🗑️ Yarım Analiz Silinecek", "oncelik": "normal", "kategori": "ogretmen", "onem": "orta", "cooldown_saat": 24},
}

VARSAYILAN_TERCIH = {"ogrenci": True, "ogretmen": True, "veli": True}


async def bildirim_olustur(alici_id, tur, icerik, ilgili_id=None):
    """Bildirim oluştur ve kaydet.

    - Kullanıcı tercihi: kapalı kategorinin bildirimi HİÇ oluşturulmaz.
    - Cooldown: tür için cooldown_saat>0 ve aynı (alıcı, tür, ilgili_id) o süre
      içinde varsa yeni bildirim üretilmez (spam engeli).
    """
    tur_bilgi = BILDIRIM_TURLERI.get(tur, {"baslik": "Bildirim", "oncelik": "normal",
                                           "kategori": "ogrenci", "onem": "bilgi", "cooldown_saat": 0})
    kategori = tur_bilgi.get("kategori", "ogrenci")
    onem = tur_bilgi.get("onem", "bilgi")

    # Kategori tercihi (varsayılan açık) — kapalıysa üretme
    alici = await db.users.find_one({"id": alici_id}, {"bildirim_tercihleri": 1})
    tercih = (alici or {}).get("bildirim_tercihleri") or {}
    if tercih.get(kategori, True) is False:
        return None

    # Cooldown / tekilleştirme
    cd = tur_bilgi.get("cooldown_saat", 0)
    if cd and cd > 0:
        esik = (datetime.utcnow() - timedelta(hours=cd)).isoformat()
        mevcut = await db.bildirimler.find_one(
            {"alici_id": alici_id, "tur": tur, "ilgili_id": ilgili_id, "tarih": {"$gte": esik}})
        if mevcut:
            return None

    doc = {
        "id": str(uuid.uuid4()),
        "alici_id": alici_id,
        "tur": tur,
        "baslik": tur_bilgi["baslik"],
        "icerik": icerik,
        "oncelik": tur_bilgi.get("oncelik", "normal"),
        "kategori": kategori,
        "onem_seviyesi": onem,
        "ilgili_id": ilgili_id,
        "okundu": False,
        "tarih": datetime.utcnow().isoformat(),
    }
    await db.bildirimler.insert_one(doc)
    return doc


# Bildirimleri getir
@router.get("/bildirimler")
async def get_bildirimler(current_user=Depends(get_current_user)):
    user_id = current_user["id"]
    bildirimler = await db.bildirimler.find({"alici_id": user_id}).sort("tarih", -1).to_list(length=50)
    for b in bildirimler:
        b.pop("_id", None)
    return bildirimler


# Okunmamış bildirim sayısı
@router.get("/bildirimler/okunmamis")
async def get_okunmamis_bildirim(current_user=Depends(get_current_user)):
    sayi = await db.bildirimler.count_documents({"alici_id": current_user["id"], "okundu": False})
    return {"sayi": sayi}


# Bildirim tercihleri (kategori bazlı aç/kapa)
@router.get("/bildirimler/tercihler")
async def get_bildirim_tercihleri(current_user=Depends(get_current_user)):
    t = current_user.get("bildirim_tercihleri") or {}
    return {**VARSAYILAN_TERCIH, **t}


@router.put("/bildirimler/tercihler")
async def put_bildirim_tercihleri(payload: dict = Body(...), current_user=Depends(get_current_user)):
    yeni = {k: bool(payload.get(k, True)) for k in ("ogrenci", "ogretmen", "veli")}
    await db.users.update_one({"id": current_user["id"]}, {"$set": {"bildirim_tercihleri": yeni}})
    return {"ok": True, "bildirim_tercihleri": yeni}


# Bildirim okundu işaretle
@router.put("/bildirimler/{bildirim_id}/okundu")
async def bildirim_okundu(bildirim_id: str, current_user=Depends(get_current_user)):
    await db.bildirimler.update_one({"id": bildirim_id}, {"$set": {"okundu": True}})
    return {"ok": True}


# Tüm bildirimleri okundu yap
@router.put("/bildirimler/tumunu-oku")
async def tumunu_oku(current_user=Depends(get_current_user)):
    await db.bildirimler.update_many({"alici_id": current_user["id"], "okundu": False}, {"$set": {"okundu": True}})
    return {"ok": True}


# Bildirim sil
@router.delete("/bildirimler/{bildirim_id}")
async def bildirim_sil(bildirim_id: str, current_user=Depends(get_current_user)):
    await db.bildirimler.delete_one({"id": bildirim_id, "alici_id": current_user["id"]})
    return {"ok": True}


# ── OTOMATİK BİLDİRİM TETİKLEYİCİLERİ ──

# Görev atandığında bildirim (gorevler endpoint'ine hook)
async def bildirim_gorev_atandi(hedef_id, baslik, atayan_ad):
    # Hedef kullanıcının user id'sini bul
    user = await db.users.find_one({"$or": [{"id": hedef_id}, {"linked_id": hedef_id}]})
    if user:
        await bildirim_olustur(user["id"], "gorev_atandi", f"{atayan_ad} size yeni görev atadı: {baslik}", hedef_id)


# Rapor tamamlandığında veliye bildirim
async def bildirim_rapor_tamamlandi(ogrenci_id, rapor_baslik):
    student = await db.students.find_one({"id": ogrenci_id})
    if student:
        # Velinin user'ını bul
        veli = await db.users.find_one({"role": "parent", "$or": [
            {"linked_id": ogrenci_id},
            {"telefon": student.get("veli_telefon", "")}
        ]})
        if veli:
            await bildirim_olustur(veli["id"], "rapor_tamamlandi",
                f"{student.get('ad', '')} {student.get('soyad', '')} için yeni rapor hazır: {rapor_baslik}", ogrenci_id)


# Streak uyarısı (günlük kontrol)
async def bildirim_streak_kontrol():
    """Tüm öğrencilerin streak'ini kontrol et, gerekirse bildirim gönder"""
    from datetime import timedelta
    simdi = datetime.utcnow()
    dun = (simdi - timedelta(days=1)).strftime("%Y-%m-%d")
    evvelsi = (simdi - timedelta(days=2)).strftime("%Y-%m-%d")

    students = await db.students.find({"arsivli": {"$ne": True}}).to_list(length=None)
    for s in students:
        logs = await db.reading_logs.find({"ogrenci_id": s["id"]}).to_list(length=None)
        tarihler = set(l.get("tarih", "")[:10] for l in logs)

        # Dün okumadı ama önceki gün okumuştu → streak kırılma riski
        if evvelsi in tarihler and dun not in tarihler:
            user = await db.users.find_one({"linked_id": s["id"], "role": "student"})
            if user:
                # Bugün zaten bildirim gönderildi mi?
                mevcut = await db.bildirimler.find_one({
                    "alici_id": user["id"], "tur": "streak_kirildi",
                    "tarih": {"$gte": simdi.strftime("%Y-%m-%d")}
                })
                if not mevcut:
                    await bildirim_olustur(user["id"], "streak_kirildi",
                        "Dün okuma yapmadın! Streak'ini korumak için bugün oku 📖")

            # Veliye de bildir
            veli = await db.users.find_one({"role": "parent", "$or": [
                {"linked_id": s["id"]}, {"telefon": s.get("veli_telefon", "")}
            ]})
            if veli:
                mevcut_v = await db.bildirimler.find_one({
                    "alici_id": veli["id"], "tur": "streak_kirildi",
                    "tarih": {"$gte": simdi.strftime("%Y-%m-%d")}
                })
                if not mevcut_v:
                    await bildirim_olustur(veli["id"], "streak_kirildi",
                        f"{s.get('ad', '')} dün okuma yapmadı. Streak kırılma riski!")

        # 7 gün streak → tebrik
        streak = 0
        for i in range(30):
            gun = (simdi - timedelta(days=i)).strftime("%Y-%m-%d")
            if gun in tarihler:
                streak += 1
            elif i > 0:
                break
        if streak == 7:
            user = await db.users.find_one({"linked_id": s["id"], "role": "student"})
            if user:
                mevcut = await db.bildirimler.find_one({
                    "alici_id": user["id"], "tur": "streak_tebrik",
                    "icerik": {"$regex": "7 gün"}
                })
                if not mevcut:
                    await bildirim_olustur(user["id"], "streak_tebrik",
                        "🎉 7 gün üst üste okudun! Harika gidiyorsun!")


# Görev hatırlatma (son 1 gün kala)
async def bildirim_gorev_hatirlatma():
    from datetime import timedelta
    simdi = datetime.utcnow()
    yarin = (simdi + timedelta(days=1)).strftime("%Y-%m-%d")

    gorevler = await db.gorevler.find({"durum": "bekliyor", "son_tarih": yarin}).to_list(length=None)
    for g in gorevler:
        user = await db.users.find_one({"$or": [{"id": g["hedef_id"]}, {"linked_id": g["hedef_id"]}]})
        if user:
            mevcut = await db.bildirimler.find_one({
                "alici_id": user["id"], "tur": "gorev_hatirlatma", "ilgili_id": g["id"]
            })
            if not mevcut:
                await bildirim_olustur(user["id"], "gorev_hatirlatma",
                    f"Yarın son gün: {g['baslik']}", g["id"])


# Risk yüksekse öğretmene bildir
async def bildirim_risk_kontrol():
    students = await db.students.find({"arsivli": {"$ne": True}}).to_list(length=None)
    from datetime import timedelta
    simdi = datetime.utcnow()

    for s in students:
        logs = await db.reading_logs.find({"ogrenci_id": s["id"]}).to_list(length=None)
        yedi_gun = simdi - timedelta(days=7)
        son_7 = [l for l in logs if l.get("tarih", "") >= yedi_gun.isoformat()]
        aktif_7 = len(set(l.get("tarih", "")[:10] for l in son_7))

        if aktif_7 == 0 and len(logs) > 0:  # Daha önce aktifti ama son 7 gün hiç okumadı
            ogretmen_user = await db.users.find_one({"linked_id": s.get("ogretmen_id"), "role": "teacher"})
            if ogretmen_user:
                mevcut = await db.bildirimler.find_one({
                    "alici_id": ogretmen_user["id"], "tur": "risk_yuksek",
                    "ilgili_id": s["id"],
                    "tarih": {"$gte": (simdi - timedelta(days=7)).isoformat()}
                })
                if not mevcut:
                    await bildirim_olustur(ogretmen_user["id"], "risk_yuksek",
                        f"🚨 {s.get('ad', '')} {s.get('soyad', '')} son 7 gündür hiç okuma yapmadı!", s["id"])


# Manuel bildirim kontrol endpoint'i (admin veya cron job çağırabilir)
@router.post("/bildirimler/kontrol")
async def bildirim_kontrol_endpoint(current_user=Depends(get_current_user)):
    if current_user.get("role") not in ["admin", "coordinator"]:
        raise HTTPException(status_code=403, detail="Yetkisiz")
    await bildirim_streak_kontrol()
    await bildirim_gorev_hatirlatma()
    await bildirim_risk_kontrol()
    return {"ok": True, "mesaj": "Bildirim kontrolü tamamlandı"}
