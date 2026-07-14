"""Duyuru / "Yeni Ne Var" modülü — db.duyurular.

Sisteme eklenen özellik/düzenlemelerin kısa maddeleri (tarih + 1-2 cümle). Admin
Ayarlar'dan ekler/düzenler/arşivler; rol hedefleme (herkes/öğretmen/admin). Dashboard'da
son 5 madde; "tümü" ile geçmiş açılır.
"""
import uuid
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException

from core.db import db
from core.auth import get_current_user, require_role, UserRole

router = APIRouter()

_ADMIN = require_role(UserRole.ADMIN)
GECERLI_ROLLER = {"herkes", "ogretmen", "admin"}


def _rol_gorunur(kullanici_rol: str, roller: list) -> bool:
    if not roller or "herkes" in roller:
        return True
    if kullanici_rol in ("admin", "coordinator") and ("admin" in roller):
        return True
    if kullanici_rol == "teacher" and ("ogretmen" in roller):
        return True
    return kullanici_rol in roller


@router.get("/duyurular")
async def duyurular_listele(hepsi: bool = False, current_user=Depends(get_current_user)):
    """Kullanıcının rolüne açık aktif duyurular. Varsayılan son 5; hepsi=true tümü."""
    rol = current_user.get("role")
    cur = db.duyurular.find({"aktif": True}, {"_id": 0}).sort([("sira", -1), ("tarih", -1)])
    tumu = await cur.to_list(length=500)
    gorunur = [d for d in tumu if _rol_gorunur(rol, d.get("roller", []))]
    return {"duyurular": gorunur if hepsi else gorunur[:5], "toplam": len(gorunur)}


@router.get("/duyurular/yonetim")
async def duyurular_yonetim(current_user=Depends(_ADMIN)):
    """Admin — tüm duyurular (arşivliler dahil)."""
    cur = db.duyurular.find({}, {"_id": 0}).sort([("sira", -1), ("tarih", -1)])
    return {"duyurular": await cur.to_list(length=1000)}


@router.post("/duyurular")
async def duyuru_ekle(payload: dict, current_user=Depends(_ADMIN)):
    baslik = (payload or {}).get("baslik", "").strip()
    icerik = (payload or {}).get("icerik", "").strip()
    if not baslik and not icerik:
        raise HTTPException(status_code=400, detail="Başlık veya içerik gerekli")
    roller = [r for r in ((payload or {}).get("roller") or ["herkes"]) if r in GECERLI_ROLLER] or ["herkes"]
    now = datetime.utcnow()
    son = await db.duyurular.find_one({}, sort=[("sira", -1)])
    doc = {
        "id": str(uuid.uuid4()), "baslik": baslik, "icerik": icerik, "roller": roller,
        "aktif": True, "sira": (int((son or {}).get("sira", 0)) + 1) if son else 1,
        "tarih": (payload or {}).get("tarih") or now.strftime("%Y-%m-%d"),
        "olusturma": now.isoformat(),
    }
    await db.duyurular.insert_one(doc)
    doc.pop("_id", None)
    return {"ok": True, "duyuru": doc}


@router.put("/duyurular/{duyuru_id}")
async def duyuru_guncelle(duyuru_id: str, payload: dict, current_user=Depends(_ADMIN)):
    mevcut = await db.duyurular.find_one({"id": duyuru_id})
    if not mevcut:
        raise HTTPException(status_code=404, detail="Duyuru bulunamadı")
    g = {}
    p = payload or {}
    for alan in ("baslik", "icerik", "tarih"):
        if alan in p:
            g[alan] = (p[alan] or "").strip()
    if "roller" in p:
        g["roller"] = [r for r in (p["roller"] or []) if r in GECERLI_ROLLER] or ["herkes"]
    if "aktif" in p:
        g["aktif"] = bool(p["aktif"])
    if "sira" in p:
        try:
            g["sira"] = int(p["sira"])
        except (TypeError, ValueError):
            pass
    await db.duyurular.update_one({"id": duyuru_id}, {"$set": g})
    return {"ok": True}


@router.delete("/duyurular/{duyuru_id}")
async def duyuru_sil(duyuru_id: str, current_user=Depends(_ADMIN)):
    r = await db.duyurular.delete_one({"id": duyuru_id})
    if r.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Duyuru bulunamadı")
    return {"ok": True}


# Başlangıç içeriği (son dönem eklenen özellikler) — bir kez seed edilir.
_SEED = [
    ("2026-07-14", "Hızlı Okuma Egzersizleri", "Egzersizlere Blok Okuma, Gölgeleme, Gruplama ve Takistoskop eklendi (yakında).", ["herkes"]),
    ("2026-07-14", "Analiz: Yarım Bırak & Devam Et", "Analizi taslak olarak kaydedip kaldığınız yerden devam edebilirsiniz.", ["ogretmen", "admin"]),
    ("2026-07-14", "TIMI Raporu PDF", "TIMI sonuç raporunu PDF olarak indirebilirsiniz.", ["ogretmen", "admin"]),
    ("2026-07-13", "Yeni Akıcı Okuma Metin Havuzu", "Analiz bölümü 150 yeni akıcı okuma metniyle güncellendi.", ["ogretmen", "admin"]),
    ("2026-07-13", "18 Kategorili Hata Takibi", "Analiz hata takibine ayrıntılı hata çeşitleri (atlama, ekleme, ters çevirme…) eklendi.", ["ogretmen", "admin"]),
    ("2026-07-12", "SSS / Yardım Bölümü", "Öğretmen, veli ve öğrenci ekranlarına SSS / Yardım bölümü eklendi.", ["herkes"]),
    ("2026-07-12", "Yönetici Log Ekranı", "Girişler, güvenlik uyarıları ve işlem kayıtları için Loglar ekranı eklendi.", ["admin"]),
    ("2026-07-10", "Muhasebe Yenilikleri", "Öğretmene göre gruplu görünüm ve ödeme-bazlı öğretmen hakedişi eklendi.", ["admin"]),
    ("2026-07-08", "Eğitimi Tamamladı Akışı", "Öğrenci detayından 'Eğitimi Tamamladı' ile mezuniyet ve otomatik arşiv.", ["ogretmen", "admin"]),
    ("2026-07-05", "Sınav Modülü", "Sınav oluşturma, atama ve otomatik değerlendirme modülü eklendi.", ["ogretmen", "admin"]),
    ("2026-07-03", "Kur Geçişi & Üst Kur", "Kur geçişi, üst kur/kur atlama sınıflandırması ve öğretmen XP entegrasyonu.", ["ogretmen", "admin"]),
]


async def duyurulari_seed():
    """Başlangıç duyurularını bir kez ekler (boşsa)."""
    try:
        if await db.duyurular.count_documents({}) > 0:
            return
        now = datetime.utcnow().isoformat()
        for i, (tarih, baslik, icerik, roller) in enumerate(reversed(_SEED)):
            await db.duyurular.insert_one({
                "id": str(uuid.uuid4()), "baslik": baslik, "icerik": icerik, "roller": roller,
                "aktif": True, "sira": i + 1, "tarih": tarih, "olusturma": now,
            })
        logging.info(f"[duyuru] {len(_SEED)} başlangıç duyurusu eklendi")
    except Exception as ex:
        logging.warning(f"[duyuru] seed hatası: {ex}")


@router.post("/duyurular/seed")
async def duyuru_seed_endpoint(current_user=Depends(_ADMIN)):
    """Admin — başlangıç duyurularını elle tetikle (boşsa ekler)."""
    await duyurulari_seed()
    return {"ok": True}
