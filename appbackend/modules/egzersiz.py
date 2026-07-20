"""Egzersiz puan sistemi endpoint'leri (/egzersiz/*).

server.py'dan birebir taşındı. Yollar ve davranış değişmedi.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException

from core.db import db
from core.auth import get_current_user
from core.zaman import iso, simdi

router = APIRouter()


def _ogr_id(user):
    """Göz egzersizini oynayan öğrencinin kimliği (öğrenci hesabı user.linked_id taşır)."""
    return user.get("linked_id") or user.get("id")


def _goz_skor(dogru, yanlis, sure_sn, zorluk):
    """Göz egzersizi skoru — DOĞRULUK + SÜRE + ZORLUK (açıklanabilir, sihirli sayı yok).

      accuracy = dogru / (dogru + yanlis)         → yanlışlar puanı düşürür
      hiz      = dogru / sure_sn  (doğru/saniye)  → hızlı bitiren bonus alır
      temel    = dogru * 10                        (her doğru 10 puan)
      skor = round( temel
                    * (0.5 + 0.5*accuracy)         # 0.5..1.0  (doğruluk çarpanı)
                    * (1   + min(1.0, hiz))        # 1.0..2.0  (hız çarpanı)
                    * (0.8 + 0.1*zorluk) )         # zorluk 1..5 → 0.9..1.3

    Yani: hızlı VE doğru → yüksek; yavaş veya hatalı → düşük. Zor egzersiz daha çok puan.
    """
    dogru = max(0, int(dogru or 0))
    yanlis = max(0, int(yanlis or 0))
    toplam = dogru + yanlis
    accuracy = (dogru / toplam) if toplam else 1.0
    sure_sn = max(1, int(sure_sn or 1))
    hiz = dogru / sure_sn
    zorluk = min(5, max(1, int(zorluk or 1)))
    return round(dogru * 10 * (0.5 + 0.5 * accuracy) * (1 + min(1.0, hiz)) * (0.8 + 0.1 * zorluk))


# ── Egzersiz Puan Sistemi ──
@router.get("/egzersiz/puanlar")
async def get_egzersiz_puanlari():
    doc = await db.ayarlar.find_one({"tip": "egzersiz_puanlari"})
    if doc:
        doc.pop("_id", None)
        doc.pop("tip", None)
        return doc.get("puanlar", {})
    return {}

@router.post("/egzersiz/puan-ayarla")
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

@router.post("/egzersiz/tamamla")
async def egzersiz_tamamla(data: dict, current_user=Depends(get_current_user)):
    kullanici_id = data.get("kullanici_id", current_user.get("id"))
    egzersiz_id = data.get("egzersiz_id", "")
    if not egzersiz_id:
        raise HTTPException(status_code=400, detail="Egzersiz ID gerekli")
    # Bugün zaten yaptı mı?
    bugun = simdi().strftime("%Y-%m-%d")
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
    kazanilan = puanlar.get(egzersiz_id, 2)  # varsayılan 2 puan (egzersiz XP tarifesi)
    # Kaydet
    await db.egzersiz_kayitlari.insert_one({
        "id": str(uuid.uuid4()),
        "kullanici_id": kullanici_id,
        "egzersiz_id": egzersiz_id,
        "tarih": bugun,
        "kazanilan_puan": kazanilan,
        "zaman": iso()
    })
    # Kullanıcı puanını güncelle
    await db.users.update_one({"id": kullanici_id}, {"$inc": {"puan": kazanilan}})
    return {"kazanilan_puan": kazanilan, "egzersiz_id": egzersiz_id}


# ═══════════════════════════════════════════════════════════════════
# GÖZ EGZERSİZİ SKORU — doğruluk + süre bazlı skor + kişisel rekor
# (Benzer Kelimeler, Kolonlar, Metin Arama, Kelime Arama vb. istemci taraflı oyunlar)
# ═══════════════════════════════════════════════════════════════════

@router.post("/egzersiz/goz/skor")
async def goz_skor_kaydet(data: dict, current_user=Depends(get_current_user)):
    """Bir göz egzersizi turunun skorunu kaydeder ve kişisel rekoru döner.
    Body: {tip, dogru, yanlis, sure_sn, zorluk}."""
    tip = (data.get("tip") or "").strip()
    if not tip:
        raise HTTPException(status_code=400, detail="Egzersiz tipi gerekli")
    oid = _ogr_id(current_user)
    dogru = int(data.get("dogru") or 0)
    yanlis = int(data.get("yanlis") or 0)
    sure_sn = int(data.get("sure_sn") or 0)
    zorluk = int(data.get("zorluk") or 1)
    skor = _goz_skor(dogru, yanlis, sure_sn, zorluk)

    # Rekoru INSERT'ten ÖNCE oku (bu kayıt hariç önceki en yüksek).
    onceki = await db.egzersiz_goz_skorlari.find({"ogrenci_id": oid, "tip": tip}) \
        .sort("skor", -1).limit(1).to_list(1)
    onceki_rekor = onceki[0]["skor"] if onceki else 0

    await db.egzersiz_goz_skorlari.insert_one({
        "id": str(uuid.uuid4()), "ogrenci_id": oid, "tip": tip,
        "dogru": dogru, "yanlis": yanlis, "sure_sn": sure_sn, "zorluk": zorluk,
        "skor": skor, "tarih": iso(),
    })
    return {"skor": skor, "rekor": max(skor, onceki_rekor), "yeni_rekor": skor > onceki_rekor}


@router.get("/egzersiz/goz/rekorlar")
async def goz_rekorlar(ogrenci_id: str = None, current_user=Depends(get_current_user)):
    """Öğrencinin tip bazlı kişisel rekorları {tip: {rekor, oynanma}}.
    ogrenci_id verilmezse aktif kullanıcının (öğrenci) kendi rekorları."""
    oid = ogrenci_id or _ogr_id(current_user)
    cur = db.egzersiz_goz_skorlari.aggregate([
        {"$match": {"ogrenci_id": oid}},
        {"$group": {"_id": "$tip", "rekor": {"$max": "$skor"}, "oynanma": {"$sum": 1}}},
    ])
    out = {}
    async for r in cur:
        out[r["_id"]] = {"rekor": r["rekor"], "oynanma": r["oynanma"]}
    return out
