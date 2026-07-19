"""Metin kalite geri bildirimi — öğretmen 1-5 yıldız + kötü metinlerin admin denetimi.

Öğretmen bir okuma/ölçüm metnini KULLANDIKTAN sonra (oturum tamamlanınca) metne 1-5 yıldız
kalite puanı verir. FARKLI metin başına İLK geri bildirimde XP kazanır (anti-farm: aynı metne
2. kez puan XP vermez). Bir metin ortalama < 2.0 VE en az 2 oy aldığında 'kalite_riski' işaretlenir
ve koordinatör/admin denetim kuyruğuna düşer (havuzdan çıkar / düzelt / koru). Admin kararı
verildikten sonra metin tekrar kuyruğa DÜŞMEZ (incelendi=true).

Koleksiyon: metin_kalite_geribildirim {id, metin_id, bolum, ogretmen_id, yildiz, yorum, oturum_id,
ilk_tarih, guncelleme_tarihi}. Özet analiz_metinler.kalite alanına denormalize edilir.

Uçlar: /metin-kalite/*.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Body

from core.db import db
from core.auth import require_role, UserRole, get_current_user
from core.zaman import iso
from core.sistem import get_puan_ayarlari

router = APIRouter()
_ADMIN = require_role(UserRole.ADMIN, UserRole.COORDINATOR)

# Kalite riski eşiği (kullanıcı kararı): ortalama bu değerin ALTINDA + en az bu kadar oy → riskli
_RISK_ORT = 2.0
_RISK_MIN_OY = 2
_KATKI_ROLLERI = ("admin", "coordinator", "teacher")


def _tid(current_user: dict) -> str:
    """Öğretmen kimliği (keşif/anti-farm sayımıyla tutarlı)."""
    return current_user.get("linked_id") or current_user.get("id")


async def _kalite_yenile(metin_id: str) -> dict:
    """Metnin tüm geri bildirimlerinden özet + risk bayrağını yeniden hesaplar (deterministik).
    incelendi/admin_karar KORUNUR — kullanıcı 'karar verilmiş metin tekrar düşmesin' dedi."""
    kayitlar = await db.metin_kalite_geribildirim.find(
        {"metin_id": metin_id}, {"_id": 0, "yildiz": 1}).to_list(length=20000)
    sayi = len(kayitlar)
    ort = round(sum(k["yildiz"] for k in kayitlar) / sayi, 2) if sayi else None
    dagilim = {str(i): sum(1 for k in kayitlar if k["yildiz"] == i) for i in range(1, 6)}
    riskli = bool(sayi >= _RISK_MIN_OY and ort is not None and ort < _RISK_ORT)
    mevcut = ((await db.analiz_metinler.find_one({"id": metin_id}, {"_id": 0, "kalite": 1})) or {}).get("kalite") or {}
    kalite = {"ort": ort, "sayi": sayi, "dagilim": dagilim, "riskli": riskli,
              "incelendi": bool(mevcut.get("incelendi", False)), "admin_karar": mevcut.get("admin_karar"),
              "guncelleme": iso()}
    await db.analiz_metinler.update_one({"id": metin_id}, {"$set": {"kalite": kalite}})
    return kalite


@router.post("/metin-kalite/geri-bildirim")
async def geri_bildirim(govde: dict = Body(...), current_user=Depends(get_current_user)):
    """Öğretmen bir metne 1-5 yıldız kalite puanı verir. İlk kez o metne puan verdiyse XP kazanır."""
    if current_user.get("role") not in _KATKI_ROLLERI:
        raise HTTPException(status_code=403, detail="Bu işlem eğitmenler içindir.")
    metin_id = str(govde.get("metin_id", "")).strip()
    try:
        yildiz = int(govde.get("yildiz"))
        assert 1 <= yildiz <= 5
    except (TypeError, ValueError, AssertionError):
        raise HTTPException(status_code=400, detail="yildiz 1-5 arası olmalı")
    metin = await db.analiz_metinler.find_one({"id": metin_id}, {"_id": 0, "id": 1, "bolum": 1})
    if not metin:
        raise HTTPException(status_code=404, detail="Metin bulunamadı")

    tid = _tid(current_user)
    mevcut = await db.metin_kalite_geribildirim.find_one({"metin_id": metin_id, "ogretmen_id": tid}, {"_id": 1})
    ilk_mi = mevcut is None
    now = iso()
    await db.metin_kalite_geribildirim.update_one(
        {"metin_id": metin_id, "ogretmen_id": tid},
        {"$set": {"metin_id": metin_id, "bolum": metin.get("bolum"), "ogretmen_id": tid,
                  "yildiz": yildiz, "yorum": str(govde.get("yorum", "")).strip()[:1000],
                  "oturum_id": str(govde.get("oturum_id", ""))[:80] or None, "guncelleme_tarihi": now},
         "$setOnInsert": {"id": str(uuid.uuid4()), "ilk_tarih": now}}, upsert=True)

    # XP yalnız FARKLI metne İLK geri bildirimde (anti-farm)
    xp_kazanildi = 0
    if ilk_mi:
        xp_kazanildi = int((await get_puan_ayarlari()).get("metin_kalite_geri_bildirim", 3))
        await db.users.update_one({"id": current_user["id"]}, {"$inc": {"puan": xp_kazanildi}})

    kalite = await _kalite_yenile(metin_id)
    return {"ok": True, "ilk_mi": ilk_mi, "xp_kazanildi": xp_kazanildi, "kalite": kalite}


@router.get("/metin-kalite/durum/{metin_id}")
async def kalite_durum(metin_id: str, current_user=Depends(get_current_user)):
    """Öğretmenin kendi puanı + metnin genel kalite özeti (widget ön-doldurma)."""
    tid = _tid(current_user)
    benim = await db.metin_kalite_geribildirim.find_one(
        {"metin_id": metin_id, "ogretmen_id": tid}, {"_id": 0, "yildiz": 1, "yorum": 1})
    metin = await db.analiz_metinler.find_one({"id": metin_id}, {"_id": 0, "kalite": 1})
    return {"benim": benim, "kalite": (metin or {}).get("kalite")}


@router.get("/metin-kalite/riskli")
async def riskli_kuyruk(current_user=Depends(_ADMIN)):
    """Koordinatör/admin denetim kuyruğu: kalite riski taşıyan ve henüz İNCELENMEMİŞ metinler.
    İncelenmiş (karar verilmiş) metinler tekrar düşmez."""
    metinler = await db.analiz_metinler.find(
        {"kalite.riskli": True, "kalite.incelendi": {"$ne": True}},
        {"_id": 0, "id": 1, "baslik": 1, "bolum": 1, "sinif_seviyesi": 1, "durum": 1, "kalite": 1}
    ).sort("kalite.ort", 1).to_list(length=500)
    # Her metin için son birkaç yorumu ekle (kanıt)
    for m in metinler:
        yorumlar = await db.metin_kalite_geribildirim.find(
            {"metin_id": m["id"], "yorum": {"$nin": [None, ""]}},
            {"_id": 0, "yildiz": 1, "yorum": 1, "guncelleme_tarihi": 1}
        ).sort("guncelleme_tarihi", -1).to_list(length=10)
        m["yorumlar"] = yorumlar
    return {"metinler": metinler, "sayi": len(metinler)}


@router.post("/metin-kalite/{metin_id}/karar")
async def kalite_karar(metin_id: str, govde: dict = Body(...), current_user=Depends(_ADMIN)):
    """Admin/koordinatör kararı: korundu | duzeltildi | cikarildi. incelendi=true → kuyruktan çıkar,
    tekrar düşmez. 'cikarildi' metni havuzdan çıkarır (durum=reddedildi)."""
    karar = str(govde.get("karar", "")).strip().lower()
    if karar not in ("korundu", "duzeltildi", "cikarildi"):
        raise HTTPException(status_code=400, detail="karar: korundu | duzeltildi | cikarildi")
    metin = await db.analiz_metinler.find_one({"id": metin_id}, {"_id": 0, "kalite": 1})
    if not metin:
        raise HTTPException(status_code=404, detail="Metin bulunamadı")
    kalite = metin.get("kalite") or {}
    kalite.update({"incelendi": True, "admin_karar": karar, "karar_veren": current_user.get("id"),
                   "karar_tarihi": iso(), "karar_notu": str(govde.get("not", ""))[:500]})
    guncelle = {"kalite": kalite}
    if karar == "cikarildi":
        guncelle["durum"] = "reddedildi"  # havuzdan çıkar (mevcut havuz mantığıyla uyumlu)
    await db.analiz_metinler.update_one({"id": metin_id}, {"$set": guncelle})
    return {"ok": True, "karar": karar, "durum": guncelle.get("durum")}
