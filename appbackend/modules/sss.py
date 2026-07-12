"""SSS / Yardım modülü — sık sorulan sorular + kullanıcı soru kuyruğu.

İki koleksiyon:
  db.sss         : yayındaki soru-cevap kayıtları (rol bazlı görünür, anonim).
  db.sss_sorular : kullanıcıların gönderdiği, cevap bekleyen sorular kuyruğu.

Kullanıcı tarafı (öğretmen/veli/öğrenci): kendi rolüne açık yayın kayıtlarını
listeler; "sorum burada yok" akışıyla soru gönderir (günlük limit). Gönderilen
soru yayında GÖRÜNMEZ, kuyruğa düşer.

Yönetim tarafı (admin + koordinatör): kuyruğu cevaplar (yayınla / kişiye yanıtla
/ reddet), yayın kayıtlarını yönetir, doğrudan SSS ekler. Yayında soranın adı
ASLA görünmez (anonim).
"""
import uuid
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException

from core.db import db
from core.auth import get_current_user, require_role, UserRole

router = APIRouter()

_YONETICI = require_role(UserRole.ADMIN, UserRole.COORDINATOR)

# Sabit kategori seti (plan kararı)
SSS_KATEGORILER = ["Ödemeler", "Dersler/Kurlar", "Teknik", "Genel"]
# Kullanıcı tarafından seçilebilen görünürlük rolleri + "herkes"
GECERLI_ROLLER = {"teacher", "parent", "student", "herkes"}
# Kullanıcı başına günlük soru limiti (spam koruması)
GUNLUK_LIMIT = 5

# Soranın rolüne göre bildirim kategorisi (bildirim tercih eşlemesi)
_ROL_KATEGORI = {"student": "ogrenci", "teacher": "ogretmen", "parent": "veli"}


def _temizle(doc: dict) -> dict:
    doc.pop("_id", None)
    return doc


async def _yanit_bildirimi(soran_id: str, soran_rol: str | None, ilgili_id: str) -> None:
    """Sorusu yanıtlanan kullanıcıya bildirim (doğrudan; transactional, garanti teslim)."""
    try:
        doc = {
            "id": str(uuid.uuid4()),
            "alici_id": soran_id,
            "tur": "sss_yanit",
            "baslik": "✅ Sorunuz Yanıtlandı",
            "icerik": "Gönderdiğiniz soru yanıtlandı. Yardım bölümünden görebilirsiniz.",
            "oncelik": "normal",
            "kategori": _ROL_KATEGORI.get(soran_rol or "", "ogrenci"),
            "onem_seviyesi": "bilgi",
            "ilgili_id": ilgili_id,
            "okundu": False,
            "tarih": datetime.utcnow().isoformat(),
        }
        await db.bildirimler.insert_one(doc)
    except Exception as ex:
        logging.warning(f"[sss] yanıt bildirimi hatası: {ex}")


# ── KULLANICI TARAFI ──

@router.get("/sss/kategoriler")
async def sss_kategoriler(current_user=Depends(get_current_user)):
    """Sabit kategori listesi (form için)."""
    return {"kategoriler": SSS_KATEGORILER}


@router.get("/sss")
async def sss_listele(current_user=Depends(get_current_user)):
    """Kullanıcının rolüne açık, yayındaki (aktif) SSS kayıtları — kategori+sıra."""
    rol = current_user.get("role")
    sorgu = {"aktif": True, "roller": {"$in": [rol, "herkes"]}}
    cur = db.sss.find(sorgu, {"_id": 0}).sort([("kategori", 1), ("sira", 1)])
    kayitlar = await cur.to_list(length=1000)
    return {"kayitlar": kayitlar, "kategoriler": SSS_KATEGORILER}


@router.post("/sss/soru")
async def sss_soru_gonder(payload: dict, current_user=Depends(get_current_user)):
    """Kullanıcı sorusu gönderir → cevap bekleyenler kuyruğuna düşer (yayında görünmez)."""
    soru = (payload or {}).get("soru", "").strip()
    kategori = (payload or {}).get("kategori", "").strip() or "Genel"
    if not soru:
        raise HTTPException(status_code=400, detail="Soru boş olamaz")
    if len(soru) > 1000:
        raise HTTPException(status_code=400, detail="Soru çok uzun (en fazla 1000 karakter)")
    if kategori not in SSS_KATEGORILER:
        kategori = "Genel"

    # Günlük limit (bugünkü gönderim sayısı)
    bugun_bas = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    bugun_sayi = await db.sss_sorular.count_documents(
        {"soran_id": current_user.get("id"), "olusturma": {"$gte": bugun_bas}})
    if bugun_sayi >= GUNLUK_LIMIT:
        raise HTTPException(status_code=429,
                            detail=f"Günlük soru limitine ulaştınız (en fazla {GUNLUK_LIMIT}).")

    ad = f"{current_user.get('ad', '')} {current_user.get('soyad', '')}".strip()
    doc = {
        "id": str(uuid.uuid4()),
        "soru": soru,
        "kategori": kategori,
        "soran_id": current_user.get("id"),
        "soran_ad": ad or None,
        "soran_rol": current_user.get("role"),
        "durum": "bekliyor",
        "cevap": None,
        "olusturma": datetime.utcnow(),
        "cevap_tarihi": None,
    }
    await db.sss_sorular.insert_one(doc)
    return {"ok": True, "mesaj": "Sorunuz iletildi. Yanıtlandığında bildirim alacaksınız."}


# ── YÖNETİM TARAFI (admin + koordinatör) ──

@router.get("/sss/bekleyen-sayisi")
async def sss_bekleyen_sayisi(current_user=Depends(_YONETICI)):
    """Cevap bekleyen soru sayısı (bildirim zili rozeti — sadece sayı, spam yok)."""
    sayi = await db.sss_sorular.count_documents({"durum": "bekliyor"})
    return {"sayi": sayi}


@router.get("/sss/bekleyen")
async def sss_bekleyen_liste(current_user=Depends(_YONETICI)):
    """Cevap bekleyen sorular kuyruğu (kim/rol/kategori/tarih)."""
    cur = db.sss_sorular.find({"durum": "bekliyor"}, {"_id": 0}).sort("olusturma", 1)
    kayitlar = await cur.to_list(length=500)
    return {"kayitlar": kayitlar}


@router.post("/sss/bekleyen/{soru_id}/yanitla")
async def sss_yanitla(soru_id: str, payload: dict, current_user=Depends(_YONETICI)):
    """Bekleyen soruyu cevapla: aksiyon = yayinla | kisisel | reddet."""
    kuyruk = await db.sss_sorular.find_one({"id": soru_id})
    if not kuyruk:
        raise HTTPException(status_code=404, detail="Soru bulunamadı")
    if kuyruk.get("durum") != "bekliyor":
        raise HTTPException(status_code=400, detail="Bu soru zaten işlenmiş")

    aksiyon = (payload or {}).get("aksiyon")
    cevap = (payload or {}).get("cevap", "").strip()
    simdi = datetime.utcnow()

    if aksiyon == "reddet":
        await db.sss_sorular.update_one(
            {"id": soru_id},
            {"$set": {"durum": "reddedildi", "cevap_tarihi": simdi}})
        return {"ok": True, "durum": "reddedildi"}

    if not cevap:
        raise HTTPException(status_code=400, detail="Cevap boş olamaz")

    if aksiyon == "kisisel":
        # Genel değeri yok → yayına GİRMEZ, yalnız sorana bildirim
        await db.sss_sorular.update_one(
            {"id": soru_id},
            {"$set": {"durum": "kisisel", "cevap": cevap, "cevap_tarihi": simdi}})
        await _yanit_bildirimi(kuyruk.get("soran_id"), kuyruk.get("soran_rol"), soru_id)
        return {"ok": True, "durum": "kisisel"}

    if aksiyon == "yayinla":
        # Soru metni yayına girerken düzenlenebilir/anonimleştirilir (soran adı YOK)
        soru_yayin = ((payload or {}).get("soru_duzenli") or kuyruk.get("soru", "")).strip()
        kategori = (payload or {}).get("kategori") or kuyruk.get("kategori") or "Genel"
        if kategori not in SSS_KATEGORILER:
            kategori = "Genel"
        roller = [r for r in ((payload or {}).get("roller") or ["herkes"]) if r in GECERLI_ROLLER]
        if not roller:
            roller = ["herkes"]
        # Sıra: kategori sonuna ekle
        son = await db.sss.find_one({"kategori": kategori}, sort=[("sira", -1)])
        sira = (int((son or {}).get("sira", 0)) + 1) if son else 0
        yayin = {
            "id": str(uuid.uuid4()),
            "soru": soru_yayin,
            "cevap": cevap,
            "kategori": kategori,
            "roller": roller,
            "sira": sira,
            "aktif": True,
            "olusturma": simdi,
            "guncelleme": simdi,
        }
        await db.sss.insert_one(yayin)
        await db.sss_sorular.update_one(
            {"id": soru_id},
            {"$set": {"durum": "yayinlandi", "cevap": cevap, "cevap_tarihi": simdi}})
        await _yanit_bildirimi(kuyruk.get("soran_id"), kuyruk.get("soran_rol"), soru_id)
        return {"ok": True, "durum": "yayinlandi", "sss_id": yayin["id"]}

    raise HTTPException(status_code=400, detail="Geçersiz aksiyon")


@router.get("/sss/yonetim")
async def sss_yonetim_liste(current_user=Depends(_YONETICI)):
    """Tüm yayın kayıtları (yönetim görünümü — pasifler dahil)."""
    cur = db.sss.find({}, {"_id": 0}).sort([("kategori", 1), ("sira", 1)])
    kayitlar = await cur.to_list(length=2000)
    return {"kayitlar": kayitlar, "kategoriler": SSS_KATEGORILER}


@router.post("/sss")
async def sss_dogrudan_ekle(payload: dict, current_user=Depends(_YONETICI)):
    """Soru beklemeden doğrudan soru-cevap ekle ve yayınla."""
    soru = (payload or {}).get("soru", "").strip()
    cevap = (payload or {}).get("cevap", "").strip()
    if not soru or not cevap:
        raise HTTPException(status_code=400, detail="Soru ve cevap gerekli")
    kategori = (payload or {}).get("kategori") or "Genel"
    if kategori not in SSS_KATEGORILER:
        kategori = "Genel"
    roller = [r for r in ((payload or {}).get("roller") or ["herkes"]) if r in GECERLI_ROLLER]
    if not roller:
        roller = ["herkes"]
    son = await db.sss.find_one({"kategori": kategori}, sort=[("sira", -1)])
    sira = (int((son or {}).get("sira", 0)) + 1) if son else 0
    simdi = datetime.utcnow()
    yayin = {
        "id": str(uuid.uuid4()), "soru": soru, "cevap": cevap, "kategori": kategori,
        "roller": roller, "sira": sira, "aktif": True, "olusturma": simdi, "guncelleme": simdi,
    }
    await db.sss.insert_one(yayin)
    return {"ok": True, "sss": _temizle(dict(yayin))}


@router.put("/sss/{sss_id}")
async def sss_guncelle(sss_id: str, payload: dict, current_user=Depends(_YONETICI)):
    """Yayın kaydını düzenle (soru/cevap/kategori/roller/sira/aktif)."""
    mevcut = await db.sss.find_one({"id": sss_id})
    if not mevcut:
        raise HTTPException(status_code=404, detail="Kayıt bulunamadı")
    guncelle: dict = {"guncelleme": datetime.utcnow()}
    p = payload or {}
    if "soru" in p:
        guncelle["soru"] = (p["soru"] or "").strip()
    if "cevap" in p:
        guncelle["cevap"] = (p["cevap"] or "").strip()
    if "kategori" in p and p["kategori"] in SSS_KATEGORILER:
        guncelle["kategori"] = p["kategori"]
    if "roller" in p:
        roller = [r for r in (p["roller"] or []) if r in GECERLI_ROLLER]
        guncelle["roller"] = roller or ["herkes"]
    if "sira" in p:
        try:
            guncelle["sira"] = int(p["sira"])
        except (TypeError, ValueError):
            pass
    if "aktif" in p:
        guncelle["aktif"] = bool(p["aktif"])
    await db.sss.update_one({"id": sss_id}, {"$set": guncelle})
    return {"ok": True}


@router.delete("/sss/{sss_id}")
async def sss_sil(sss_id: str, current_user=Depends(_YONETICI)):
    """Yayın kaydını sil."""
    r = await db.sss.delete_one({"id": sss_id})
    if r.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Kayıt bulunamadı")
    return {"ok": True}
