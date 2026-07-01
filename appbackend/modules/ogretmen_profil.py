"""Öğretmen profil modülü.

Öğretmenin kendi profilini görüntüleyip düzenlemesi, profil fotoğrafı yüklemesi;
yöneticinin alan bazlı görünürlük ayarlarını yönetmesi ve veli/öğrenci için
görünürlük filtresiyle "public" profil.

Veri:
  - Profil alanları `teachers` koleksiyonunda (schemaless olarak genişletilir).
  - E-posta login kimliği `users` koleksiyonunda (teacher düzenleyemez).
  - Görünürlük ayarları `profil_gorunurluk_ayarlari` koleksiyonu (_id="global").

Yollar (api_router prefix=/api):
  GET  /ogretmen/profil                     (teacher — kendi tam profili)
  PUT  /ogretmen/profil                     (teacher — kısmi güncelleme, korumalı alanlar hariç)
  POST /ogretmen/profil/foto                (teacher — foto yükle, 400x400)
  GET  /ogretmen/{ogretmen_id}/profil-public(herkes — görünürlüğe göre filtreli)
  GET  /admin/profil-gorunurluk             (admin/coordinator)
  PUT  /admin/profil-gorunurluk             (admin/coordinator)
"""
import io
import os
import logging
from pathlib import Path
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File

from core.db import db
from core.auth import get_current_user, require_role, UserRole

router = APIRouter()

# ── Profil fotoğrafı yükleme klasörü (appbackend/uploads/profil_fotolari) ──
UPLOAD_KOK = Path(__file__).resolve().parent.parent / "uploads"
FOTO_DIR = UPLOAD_KOK / "profil_fotolari"
FOTO_DIR.mkdir(parents=True, exist_ok=True)
MAX_FOTO_BYTE = 2 * 1024 * 1024  # 2MB
IZINLI_TIPLER = {"image/jpeg", "image/jpg", "image/png"}

# ── Görünürlük ──
GORUNURLUK_ID = "global"
VARSAYILAN_GORUNURLUK = {
    "profil_fotografi": "herkes",
    "dogum_tarihi": "admin",
    "adres": "admin",
    "sehir": "veli",
    "kisa_biyografi": "herkes",
    "egitim_gecmisi": "veli",
    "deneyim_yili": "herkes",
    "sertifikalar": "veli",
    "katilim_tarihi": "veli",
    "bildirim_tercihleri": "sadece_kendisi",
}

# Teacher'ın düzenleyebileceği alanlar (email/seviye/ödeme/katılım HARİÇ)
DUZENLENEBILIR = {
    "ad", "soyad", "brans", "telefon", "dogum_tarihi", "adres", "sehir",
    "kisa_biyografi", "egitim_gecmisi", "deneyim_yili", "sertifikalar",
    "bildirim_tercihleri", "profil_fotografi",
}
# users koleksiyonuna da yansıtılacak kimlik alanları
USERS_SENKRON = {"ad", "soyad", "telefon"}

VARSAYILAN_BILDIRIM = {
    "email": True, "push": True, "veli_mesaji": True,
    "ogrenci_mesaji": True, "admin_duyuru": True,
}


def _ogretmen_id(current_user: dict) -> str:
    return current_user.get("linked_id") or current_user.get("id")


def _profil_birlestir(teacher: dict, email: str) -> dict:
    """Teacher kaydını + varsayılanlarla tam profil sözlüğü üretir."""
    t = teacher or {}
    return {
        "id": t.get("id"),
        "ad": t.get("ad", ""),
        "soyad": t.get("soyad", ""),
        "brans": t.get("brans", ""),
        "telefon": t.get("telefon", ""),
        "seviye": t.get("seviye", ""),
        "email": email or "",
        "profil_fotografi": t.get("profil_fotografi") or "",
        "dogum_tarihi": t.get("dogum_tarihi"),
        "adres": t.get("adres", ""),
        "sehir": t.get("sehir", ""),
        "kisa_biyografi": t.get("kisa_biyografi", ""),
        "egitim_gecmisi": t.get("egitim_gecmisi") or [],
        "deneyim_yili": t.get("deneyim_yili", 0),
        "sertifikalar": t.get("sertifikalar") or [],
        "katilim_tarihi": t.get("katilim_tarihi") or t.get("olusturma_tarihi"),
        "bildirim_tercihleri": {**VARSAYILAN_BILDIRIM, **(t.get("bildirim_tercihleri") or {})},
    }


async def _gorunurluk_getir() -> dict:
    doc = await db.profil_gorunurluk_ayarlari.find_one({"_id": GORUNURLUK_ID})
    ayarlar = (doc or {}).get("ayarlar") or {}
    # Eksik alanları varsayılanla tamamla
    return {**VARSAYILAN_GORUNURLUK, **ayarlar}


# ─────────────────────────────────────────────────────────────
# Teacher — kendi profili
# ─────────────────────────────────────────────────────────────
@router.get("/ogretmen/profil")
async def get_kendi_profil(current_user=Depends(get_current_user)):
    if current_user.get("role") != "teacher":
        raise HTTPException(status_code=403, detail="Bu sayfa yalnızca öğretmenler içindir.")
    oid = _ogretmen_id(current_user)
    teacher = await db.teachers.find_one({"id": oid})
    profil = _profil_birlestir(teacher, current_user.get("email", ""))
    return profil


@router.put("/ogretmen/profil")
async def guncelle_kendi_profil(data: dict, current_user=Depends(get_current_user)):
    if current_user.get("role") != "teacher":
        raise HTTPException(status_code=403, detail="Bu sayfa yalnızca öğretmenler içindir.")
    oid = _ogretmen_id(current_user)

    # Yalnızca izinli alanları al (email/seviye/ödeme/katılım korunur)
    guncel = {k: v for k, v in (data or {}).items() if k in DUZENLENEBILIR}

    # Basit doğrulamalar
    if "kisa_biyografi" in guncel and isinstance(guncel["kisa_biyografi"], str):
        guncel["kisa_biyografi"] = guncel["kisa_biyografi"][:500]
    if "deneyim_yili" in guncel:
        try:
            guncel["deneyim_yili"] = max(0, int(guncel["deneyim_yili"]))
        except (TypeError, ValueError):
            guncel.pop("deneyim_yili", None)
    if "bildirim_tercihleri" in guncel and isinstance(guncel["bildirim_tercihleri"], dict):
        guncel["bildirim_tercihleri"] = {
            k: bool(guncel["bildirim_tercihleri"].get(k, VARSAYILAN_BILDIRIM[k]))
            for k in VARSAYILAN_BILDIRIM
        }

    if not guncel:
        teacher = await db.teachers.find_one({"id": oid})
        return _profil_birlestir(teacher, current_user.get("email", ""))

    guncel["profil_guncelleme_tarihi"] = datetime.now(timezone.utc).isoformat()
    await db.teachers.update_one({"id": oid}, {"$set": guncel}, upsert=True)

    # Kimlik alanlarını users'a da yansıt (header/görünüm tutarlı olsun)
    users_guncel = {k: guncel[k] for k in USERS_SENKRON if k in guncel}
    if users_guncel:
        await db.users.update_one({"id": current_user["id"]}, {"$set": users_guncel})

    teacher = await db.teachers.find_one({"id": oid})
    return _profil_birlestir(teacher, current_user.get("email", ""))


@router.post("/ogretmen/profil/foto")
async def profil_foto_yukle(dosya: UploadFile = File(...), current_user=Depends(get_current_user)):
    if current_user.get("role") != "teacher":
        raise HTTPException(status_code=403, detail="Bu işlem yalnızca öğretmenler içindir.")
    if dosya.content_type not in IZINLI_TIPLER:
        raise HTTPException(status_code=400, detail="Yalnızca JPEG/PNG yükleyebilirsiniz.")

    icerik = await dosya.read()
    if len(icerik) > MAX_FOTO_BYTE:
        raise HTTPException(status_code=400, detail="Dosya en fazla 2MB olabilir.")

    oid = _ogretmen_id(current_user)
    hedef = FOTO_DIR / f"{oid}.jpg"
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(icerik)).convert("RGB")
        img.thumbnail((400, 400))
        img.save(hedef, format="JPEG", quality=85)
    except Exception as ex:
        logging.warning(f"[profil_foto] PIL işleyemedi, ham kaydediliyor: {ex}")
        try:
            with open(hedef, "wb") as f:
                f.write(icerik)
        except Exception as ex2:
            raise HTTPException(status_code=500, detail=f"Dosya kaydedilemedi: {ex2}")

    url = f"/uploads/profil_fotolari/{oid}.jpg"
    await db.teachers.update_one({"id": oid}, {"$set": {"profil_fotografi": url}}, upsert=True)
    return {"profil_fotografi_url": url}


# ─────────────────────────────────────────────────────────────
# Public profil (görünürlük filtresiyle)
# ─────────────────────────────────────────────────────────────
def _izinli_seviyeler(viewer_role: str) -> set:
    if viewer_role in ("admin", "coordinator"):
        return {"herkes", "veli", "admin"}
    if viewer_role == "parent":
        return {"herkes", "veli"}
    # student, teacher, diğer → yalnızca herkes
    return {"herkes"}


@router.get("/ogretmen/{ogretmen_id}/profil-public")
async def get_public_profil(ogretmen_id: str, current_user=Depends(get_current_user)):
    teacher = await db.teachers.find_one({"id": ogretmen_id})
    if not teacher:
        raise HTTPException(status_code=404, detail="Öğretmen bulunamadı")

    # E-posta public'te dönmez
    tam = _profil_birlestir(teacher, "")
    ayarlar = await _gorunurluk_getir()
    izinli = _izinli_seviyeler(current_user.get("role", ""))

    # Her zaman görünen kimlik alanları
    sonuc = {
        "id": tam["id"],
        "ad": tam["ad"],
        "soyad": tam["soyad"],
        "brans": tam["brans"],
    }
    # Görünürlüğe tabi alanlar
    for alan in VARSAYILAN_GORUNURLUK:
        seviye = ayarlar.get(alan, "admin")
        if seviye == "sadece_kendisi":
            continue  # public'te asla
        if seviye in izinli and alan in tam:
            sonuc[alan] = tam[alan]
    return sonuc


# ─────────────────────────────────────────────────────────────
# Admin — görünürlük ayarları
# ─────────────────────────────────────────────────────────────
_ADMIN = require_role(UserRole.ADMIN, UserRole.COORDINATOR)


@router.get("/admin/profil-gorunurluk")
async def get_gorunurluk(current_user=Depends(_ADMIN)):
    return {"ayarlar": await _gorunurluk_getir()}


@router.put("/admin/profil-gorunurluk")
async def guncelle_gorunurluk(data: dict, current_user=Depends(_ADMIN)):
    gelen = (data or {}).get("ayarlar") or {}
    gecerli_seviye = {"herkes", "veli", "admin", "sadece_kendisi"}
    temiz = {}
    for alan, seviye in gelen.items():
        if alan in VARSAYILAN_GORUNURLUK and seviye in gecerli_seviye:
            temiz[alan] = seviye
    # bildirim_tercihleri her zaman sadece_kendisi kalır (özel alan)
    temiz["bildirim_tercihleri"] = "sadece_kendisi"

    mevcut = await _gorunurluk_getir()
    yeni = {**mevcut, **temiz}
    await db.profil_gorunurluk_ayarlari.update_one(
        {"_id": GORUNURLUK_ID},
        {"$set": {
            "ayarlar": yeni,
            "guncelleme_tarihi": datetime.now(timezone.utc).isoformat(),
            "guncelleyen_id": current_user.get("id"),
        }},
        upsert=True,
    )
    return {"ayarlar": yeni}
