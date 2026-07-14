"""Loglar modülü — yönetici log ekranı için okuma uçları.

Üç bölüm:
  1) GET /loglar/ozet     : tüm grafikler için tek özet uç (Mongo aggregation).
  2) GET /loglar/giris     : giris_log canlı akış tablosu (filtreli + sayfalı).
  3) GET/PUT /loglar/saklama : giriş logu saklama süresi (TTL) ayarı.

Yetki: yalnız admin + koordinatör (accountant/teacher → 403). Log YAZIMI burada
yapılmaz (core.giris_log / core.audit); bu modül salt-okurdur. islem_log tablosu
UI'da bu ekrana taşınır ama ucu crm.py'deki /islem-log olarak kalır.
"""
import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException

from core.db import db
from core.auth import require_role, UserRole

router = APIRouter()

_YONETICI = require_role(UserRole.ADMIN, UserRole.COORDINATOR)

# Başarısız giriş eşiği: aynı IP/e-posta son EŞIK_DK dakikada EŞIK_SAYI+ deneme
ESIK_SAYI = 5
ESIK_DK = 15


def _gun_str(alan: str = "$olusturma"):
    return {"$dateToString": {"format": "%Y-%m-%d", "date": alan}}


@router.get("/loglar/ozet")
async def loglar_ozet(sure_periyot: str = "ay", current_user=Depends(_YONETICI)):
    """Log ekranındaki tüm grafiklerin verisini tek çağrıda döndürür.
    sure_periyot: 'gun' | 'hafta' | 'ay' → sadece 'Kullanıcıların Geçirdiği Süre'
    metriğinin zaman penceresini değiştirir (diğer grafikler 30 gün sabit)."""
    simdi = datetime.utcnow()
    otuz = simdi - timedelta(days=30)
    bugun_bas = datetime(simdi.year, simdi.month, simdi.day)
    esik_bas = simdi - timedelta(minutes=ESIK_DK)
    _sure_gun = {"gun": 1, "hafta": 7, "ay": 30}.get(sure_periyot, 30)
    sure_bas = simdi - timedelta(days=_sure_gun)

    sonuc = {
        "gunluk_aktif": [], "isi_haritasi": [], "bugun_rol": [],
        "basarisiz_gunluk": [], "islem_hacmi": [], "uyarilar": [],
        "esik": {"sayi": ESIK_SAYI, "dakika": ESIK_DK},
        "oturum_sure": {"ortalama_dk": 0, "toplam_oturum": 0, "rol_bazli": []},
    }

    try:
        # 1) Günlük aktif kullanıcı (30 gün, rol bazlı distinct kullanıcı)
        cur = db.giris_log.aggregate([
            {"$match": {"tip": "login_basarili", "olusturma": {"$gte": otuz}}},
            {"$group": {"_id": {"gun": _gun_str(), "rol": "$rol"},
                        "kullanicilar": {"$addToSet": "$user_id"}}},
            {"$project": {"_id": 0, "gun": "$_id.gun", "rol": "$_id.rol",
                          "sayi": {"$size": "$kullanicilar"}}},
            {"$sort": {"gun": 1}},
        ])
        sonuc["gunluk_aktif"] = await cur.to_list(length=2000)

        # 2) Saatlik yoğunluk ısı haritası (haftanın günü × saat)
        cur = db.giris_log.aggregate([
            {"$match": {"tip": "login_basarili", "olusturma": {"$gte": otuz}}},
            {"$group": {"_id": {"gun": {"$dayOfWeek": "$olusturma"},
                                "saat": {"$hour": "$olusturma"}},
                        "sayi": {"$sum": 1}}},
            {"$project": {"_id": 0, "gun": "$_id.gun", "saat": "$_id.saat", "sayi": 1}},
        ])
        sonuc["isi_haritasi"] = await cur.to_list(length=200)

        # 3) Bugünkü başarılı giriş rol dağılımı
        cur = db.giris_log.aggregate([
            {"$match": {"tip": "login_basarili", "olusturma": {"$gte": bugun_bas}}},
            {"$group": {"_id": "$rol", "sayi": {"$sum": 1}}},
            {"$project": {"_id": 0, "rol": "$_id", "sayi": 1}},
        ])
        sonuc["bugun_rol"] = await cur.to_list(length=50)

        # 4) Başarısız giriş çizgisi (30 gün, gün bazlı)
        cur = db.giris_log.aggregate([
            {"$match": {"tip": "login_basarisiz", "olusturma": {"$gte": otuz}}},
            {"$group": {"_id": _gun_str(), "sayi": {"$sum": 1}}},
            {"$project": {"_id": 0, "gun": "$_id", "sayi": 1}},
            {"$sort": {"gun": 1}},
        ])
        sonuc["basarisiz_gunluk"] = await cur.to_list(length=100)

        # 4b) Eşik uyarısı: kısa pencerede aynı IP/e-posta çok başarısız deneme
        cur = db.giris_log.aggregate([
            {"$match": {"tip": "login_basarisiz", "olusturma": {"$gte": esik_bas}}},
            {"$group": {"_id": {"ip": "$ip", "email": "$denenen_email"},
                        "sayi": {"$sum": 1}, "son": {"$max": "$olusturma"}}},
            {"$match": {"sayi": {"$gte": ESIK_SAYI}}},
            {"$project": {"_id": 0, "ip": "$_id.ip", "email": "$_id.email",
                          "sayi": 1, "son": 1}},
            {"$sort": {"sayi": -1}},
        ])
        sonuc["uyarilar"] = await cur.to_list(length=100)

        # 5) İşlem hacmi (islem_log, 30 gün, olay türüne göre) — tarih ISO string
        cur = db.islem_log.aggregate([
            {"$match": {"tarih": {"$gte": otuz.isoformat()}}},
            {"$group": {"_id": "$islem", "sayi": {"$sum": 1}}},
            {"$project": {"_id": 0, "islem": "$_id", "sayi": 1}},
            {"$sort": {"sayi": -1}},
        ])
        sonuc["islem_hacmi"] = await cur.to_list(length=100)

        # Oturum süresi: login→logout çiftlerinden (logout yoksa sonraki aktivite/
        # varsayılan tavan tahmini). Rol bazlı kırılım (son 30 gün).
        VARSAYILAN_TAVAN_DK = 20  # logout yoksa oturum en fazla bu kadar sayılır
        cur = db.giris_log.find(
            {"olusturma": {"$gte": sure_bas}, "tip": {"$in": ["login_basarili", "logout", "token_yenile"]}},
            {"_id": 0, "user_id": 1, "rol": 1, "tip": 1, "olusturma": 1}).sort("olusturma", 1)
        olaylar = await cur.to_list(length=50000)
        kul = {}
        for o in olaylar:
            uid = o.get("user_id")
            if uid:
                kul.setdefault(uid, []).append(o)
        rol_sure, rol_say = {}, {}
        toplam_sure, toplam_say = 0.0, 0
        for uid, lst in kul.items():
            i = 0
            while i < len(lst):
                if lst[i]["tip"] == "login_basarili":
                    bas = lst[i]["olusturma"]
                    rol = lst[i].get("rol") or "?"
                    # Bu login'den sonraki ilk logout'u bul (araya token_yenile girebilir)
                    j = i + 1
                    bitis = None
                    while j < len(lst):
                        if lst[j]["tip"] == "logout":
                            bitis = lst[j]["olusturma"]; break
                        if lst[j]["tip"] == "login_basarili":
                            break  # yeni oturum başlamış, öncekinde logout yok
                        j += 1
                    if bitis is not None:
                        dk = (bitis - bas).total_seconds() / 60.0
                    else:
                        # logout yok → son token_yenile'ye kadar tahmin; aktivite yoksa
                        # tavan varsay; aşırı uzun tahmini 8 saatle sınırla.
                        son_aktivite = bas
                        for k in range(i + 1, len(lst)):
                            if lst[k]["tip"] == "token_yenile":
                                son_aktivite = lst[k]["olusturma"]
                            elif lst[k]["tip"] == "login_basarili":
                                break
                        span = (son_aktivite - bas).total_seconds() / 60.0
                        dk = min(span if span > 1 else VARSAYILAN_TAVAN_DK, 8 * 60)
                    if 0 < dk <= 24 * 60:  # 0<dk≤1 gün makul
                        toplam_sure += dk; toplam_say += 1
                        rol_sure[rol] = rol_sure.get(rol, 0.0) + dk
                        rol_say[rol] = rol_say.get(rol, 0) + 1
                i += 1
        sonuc["oturum_sure"] = {
            "periyot": sure_periyot if sure_periyot in ("gun", "hafta", "ay") else "ay",
            "ortalama_dk": round(toplam_sure / toplam_say, 1) if toplam_say else 0,
            "toplam_oturum": toplam_say,
            "rol_bazli": sorted(
                [{"rol": r, "ortalama_dk": round(rol_sure[r] / rol_say[r], 1), "oturum_sayisi": rol_say[r]}
                 for r in rol_sure],
                key=lambda x: x["oturum_sayisi"], reverse=True),
        }
    except Exception as ex:
        logging.warning(f"[loglar] ozet aggregation hatası: {ex}")

    return sonuc


@router.get("/loglar/giris")
async def loglar_giris(tarih_bas: str | None = None, tarih_bit: str | None = None,
                       rol: str | None = None, tip: str | None = None,
                       kullanici_ara: str | None = None,
                       skip: int = 0, limit: int = 50,
                       current_user=Depends(_YONETICI)):
    """giris_log canlı akış tablosu — filtreli + sayfalı. {kayitlar, toplam} döner."""
    limit = min(max(1, limit), 200)
    skip = max(0, skip)
    sorgu: dict = {}
    if rol:
        sorgu["rol"] = rol
    if tip:
        sorgu["tip"] = tip
    # Tarih aralığı (native datetime)
    zaman: dict = {}
    for k, uc in (("$gte", tarih_bas), ("$lte", tarih_bit)):
        if uc:
            try:
                zaman[k] = datetime.fromisoformat(uc)
            except ValueError:
                pass
    if zaman:
        sorgu["olusturma"] = zaman
    if kullanici_ara:
        rx = {"$regex": kullanici_ara, "$options": "i"}
        sorgu["$or"] = [{"kullanici_ad": rx}, {"denenen_email": rx}, {"ip": rx}]

    try:
        toplam = await db.giris_log.count_documents(sorgu)
        cur = (db.giris_log.find(sorgu, {"_id": 0})
               .sort("olusturma", -1).skip(skip).limit(limit))
        kayitlar = await cur.to_list(length=limit)
    except Exception as ex:
        logging.warning(f"[loglar] giris listeleme hatası: {ex}")
        kayitlar, toplam = [], 0
    return {"kayitlar": kayitlar, "toplam": toplam, "skip": skip, "limit": limit}


@router.get("/loglar/saklama")
async def saklama_getir(current_user=Depends(_YONETICI)):
    """Giriş logu saklama süresini (gün) döndürür (varsayılan 90)."""
    doc = await db.sistem_ayarlari.find_one({"tip": "log_saklama"})
    gun = int(((doc or {}).get("degerler") or {}).get("gun") or 90)
    return {"gun": gun}


@router.put("/loglar/saklama")
async def saklama_ayarla(payload: dict, current_user=Depends(_YONETICI)):
    """Saklama süresini günceller ve giris_log TTL index'ini collMod ile uygular."""
    try:
        gun = int((payload or {}).get("gun"))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Geçersiz gün değeri")
    if gun < 1 or gun > 3650:
        raise HTTPException(status_code=400, detail="Gün 1–3650 aralığında olmalı")

    await db.sistem_ayarlari.update_one(
        {"tip": "log_saklama"},
        {"$set": {"degerler": {"gun": gun},
                  "guncelleme_tarihi": datetime.utcnow().isoformat(),
                  "guncelleyen": current_user.get("id")}},
        upsert=True,
    )
    # TTL index'i çalışma anında güncelle (collMod). Index yoksa oluştur.
    saniye = gun * 86400
    try:
        await db.command({"collMod": "giris_log",
                          "index": {"name": "ttl_giris_log", "expireAfterSeconds": saniye}})
    except Exception:
        try:
            await db.giris_log.create_index(
                "olusturma", expireAfterSeconds=saniye, name="ttl_giris_log")
        except Exception as ex:
            logging.warning(f"[loglar] TTL güncellenemedi: {ex}")
    return {"ok": True, "gun": gun}
