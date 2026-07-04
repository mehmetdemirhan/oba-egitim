"""Rozet yönetimi modülü (/rozet/*) — veri-odaklı rozet CRUD + istatistik.

FAZ 3. db.rozetler koleksiyonunu yönetir (tanım ekle/güncelle/sil/manuel ver).
Değerlendirme motoru core.rozet_motor'dadır; bu modül SADECE yönetim API'sidir.

Rozet kimliği (rol, kod) çiftidir — 'kod' tek başına benzersiz DEĞİL (gorev_ilk,
egz_ilk gibi kodlar hem öğretmen hem öğrenci rozetinde bulunur). Bu yüzden tekil
işlemler /rozet/{rol}/{kod} yolunu kullanır.

Eski /rozetler/* endpoint'leri (ilerleme.py) GERİYE DÖNÜK UYUMLU olarak kalır.
"""
import logging
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Body
from pymongo.errors import DuplicateKeyError

from core.db import db
from core.auth import get_current_user, require_role, UserRole
from core.rozet_helpers import rozet_odul_puan, rozet_bildirim_gonder
from core.rozet_motor import _kod_fallback_tanimlar

router = APIRouter(prefix="/rozet", tags=["rozet"])

GECERLI_ROLLER = {"teacher", "student"}
GECERLI_SEVIYELER = {"bronz", "gumus", "altin", "platin", "elmas"}
DUZENLENEBILIR_ALANLAR = {
    "ad", "aciklama", "ikon", "renk", "kategori", "seviye",
    "odul_puan", "kosul", "aktif", "sira",
}


def _temizle(doc: dict) -> dict:
    doc.pop("_id", None)
    return doc


async def _tanim_listesi(rol: Optional[str] = None) -> list:
    """db.rozetler'den tanımları döner; koleksiyon boşsa kod-fallback."""
    q = {}
    if rol:
        q["rol"] = rol
    docs = await db.rozetler.find(q).sort([("rol", 1), ("sira", 1)]).to_list(length=None)
    if docs:
        return [_temizle(d) for d in docs]
    # Fallback — migration henüz çalışmadıysa boş dönmesin
    roller = [rol] if rol in GECERLI_ROLLER else ["teacher", "student"]
    out = []
    for r in roller:
        out += await _kod_fallback_tanimlar(r)
    return out


async def _rol_user_idleri(rol: str) -> list:
    users = await db.users.find({"role": rol}, {"id": 1}).to_list(length=None)
    return [u["id"] for u in users]


# ─────────────────────────────────────────────
# OKUMA (public / auth)
# ─────────────────────────────────────────────
@router.get("/tanim")
async def rozet_tanim_listesi(rol: Optional[str] = None):
    """Tüm rozet tanımları (opsiyonel rol filtresi). Herkese açık."""
    return await _tanim_listesi(rol)


# ── Admin-only statik yollar (/{rol}/{kod}'dan ÖNCE) ──
@router.get("/istatistik")
async def rozet_istatistik(current_user=Depends(require_role(UserRole.ADMIN, UserRole.COORDINATOR))):
    """Her rozet için kazanan sayısı + en nadir/en yaygın özet."""
    tanimlar = await _tanim_listesi()
    # rol bazlı kullanıcı id kümeleri (kazanımlar rol'e göre ayrıştırılır)
    rol_userlar = {r: set(await _rol_user_idleri(r)) for r in GECERLI_ROLLER}
    # tüm kazanımları tek seferde çek
    kazanimlar = await db.kazanilan_rozetler.find({}, {"kullanici_id": 1, "rozet_kodu": 1}).to_list(length=None)

    sonuc = []
    for t in tanimlar:
        rol = t.get("rol")
        uset = rol_userlar.get(rol, set())
        sayi = sum(1 for k in kazanimlar
                   if k.get("rozet_kodu") == t.get("kod") and k.get("kullanici_id") in uset)
        sonuc.append({
            "kod": t.get("kod"), "ad": t.get("ad"), "rol": rol,
            "ikon": t.get("ikon"), "seviye": t.get("seviye"),
            "aktif": t.get("aktif", True), "kazanan_sayisi": sayi,
        })
    kazanilanlar = [s for s in sonuc if s["kazanan_sayisi"] > 0]
    en_yaygin = max(kazanilanlar, key=lambda s: s["kazanan_sayisi"], default=None)
    en_nadir = min(kazanilanlar, key=lambda s: s["kazanan_sayisi"], default=None)
    return {
        "toplam_tanim": len(tanimlar),
        "aktif_tanim": sum(1 for t in tanimlar if t.get("aktif", True)),
        "toplam_kazanim": len(kazanimlar),
        "en_yaygin": en_yaygin,
        "en_nadir": en_nadir,
        "rozetler": sorted(sonuc, key=lambda s: s["kazanan_sayisi"], reverse=True),
    }


@router.get("/export")
async def rozet_export(current_user=Depends(require_role(UserRole.ADMIN, UserRole.COORDINATOR))):
    """Tüm rozet tanımlarını JSON olarak döner (yedek/aktarım)."""
    return {"rozetler": await _tanim_listesi(), "tarih": datetime.utcnow().isoformat()}


@router.post("/import")
async def rozet_import(payload: dict = Body(...), current_user=Depends(require_role(UserRole.ADMIN, UserRole.COORDINATOR))):
    """JSON toplu içe aktarma — (rol, kod) üzerinde upsert."""
    kayitlar = payload.get("rozetler", payload if isinstance(payload, list) else [])
    if not isinstance(kayitlar, list):
        raise HTTPException(status_code=400, detail="'rozetler' listesi bekleniyor")
    now = datetime.utcnow().isoformat()
    eklenen, guncellenen, hatali = 0, 0, 0
    for r in kayitlar:
        if not isinstance(r, dict) or not r.get("kod") or r.get("rol") not in GECERLI_ROLLER:
            hatali += 1
            continue
        temiz = {k: v for k, v in r.items() if k in DUZENLENEBILIR_ALANLAR}
        temiz["guncelleme_tarihi"] = now
        res = await db.rozetler.update_one(
            {"rol": r["rol"], "kod": r["kod"]},
            {"$set": temiz, "$setOnInsert": {"rol": r["rol"], "kod": r["kod"], "olusturma_tarihi": now}},
            upsert=True,
        )
        if res.upserted_id:
            eklenen += 1
        else:
            guncellenen += 1
    return {"ok": True, "eklenen": eklenen, "guncellenen": guncellenen, "hatali": hatali}


@router.post("/tanim")
async def rozet_olustur(payload: dict = Body(...), current_user=Depends(require_role(UserRole.ADMIN, UserRole.COORDINATOR))):
    """Yeni rozet tanımı ekler."""
    kod = (payload.get("kod") or "").strip()
    rol = payload.get("rol")
    if not kod:
        raise HTTPException(status_code=400, detail="kod zorunlu")
    if rol not in GECERLI_ROLLER:
        raise HTTPException(status_code=400, detail=f"rol {GECERLI_ROLLER} olmalı")
    if payload.get("seviye") and payload["seviye"] not in GECERLI_SEVIYELER:
        raise HTTPException(status_code=400, detail=f"seviye {GECERLI_SEVIYELER} olmalı")
    now = datetime.utcnow().isoformat()
    doc = {
        "kod": kod, "rol": rol,
        "ad": payload.get("ad", kod),
        "aciklama": payload.get("aciklama", ""),
        "ikon": payload.get("ikon", "🏅"),
        "renk": payload.get("renk"),
        "kategori": payload.get("kategori", ""),
        "seviye": payload.get("seviye", "bronz"),
        "odul_puan": int(payload.get("odul_puan", 0) or 0),
        "kosul": payload.get("kosul", {"metrik": "manuel", "operator": None, "esik": None}),
        "aktif": bool(payload.get("aktif", True)),
        "sira": int(payload.get("sira", 999)),
        "olusturma_tarihi": now, "guncelleme_tarihi": now,
    }
    try:
        await db.rozetler.insert_one(doc)
    except DuplicateKeyError:
        raise HTTPException(status_code=409, detail=f"'{rol}/{kod}' zaten mevcut")
    return _temizle(doc)


@router.get("/ogrenci/{ogrenci_id}")
async def ogrenci_rozetleri(ogrenci_id: str, current_user=Depends(get_current_user)):
    """Bir öğrencinin rozet vitrini (tanımlar + kazanılanlar) — veli/öğretmen için.

    ogrenci_id = students koleksiyonundaki kayıt id'si. Kazanımlar öğrencinin
    USER hesabı üzerinden tutulduğu için önce ilgili user çözülür.
    NOT: /{rol}/{kod}'dan ÖNCE tanımlı olmalı ('ogrenci' rol sanılmasın)."""
    su = await db.users.find_one({"role": "student", "linked_id": ogrenci_id})
    kullanici_id = su["id"] if su else ogrenci_id
    kazanilanlar = await db.kazanilan_rozetler.find(
        {"kullanici_id": kullanici_id}, {"_id": 0}).to_list(length=None)
    tanimlar = await _tanim_listesi("student")
    return {"tanimlar": tanimlar, "kazanilanlar": kazanilanlar,
            "kazanilan_sayisi": len(kazanilanlar), "toplam": len(tanimlar)}


# ── Tekil rozet işlemleri (/{rol}/{kod}) ──
@router.get("/{rol}/{kod}")
async def rozet_getir(rol: str, kod: str):
    doc = await db.rozetler.find_one({"rol": rol, "kod": kod})
    if not doc:
        raise HTTPException(status_code=404, detail="Rozet bulunamadı")
    return _temizle(doc)


@router.put("/{rol}/{kod}")
async def rozet_guncelle(rol: str, kod: str, payload: dict = Body(...),
                         current_user=Depends(require_role(UserRole.ADMIN, UserRole.COORDINATOR))):
    mevcut = await db.rozetler.find_one({"rol": rol, "kod": kod})
    if not mevcut:
        raise HTTPException(status_code=404, detail="Rozet bulunamadı")
    if payload.get("seviye") and payload["seviye"] not in GECERLI_SEVIYELER:
        raise HTTPException(status_code=400, detail=f"seviye {GECERLI_SEVIYELER} olmalı")
    guncel = {k: v for k, v in payload.items() if k in DUZENLENEBILIR_ALANLAR}
    if "odul_puan" in guncel:
        guncel["odul_puan"] = int(guncel["odul_puan"] or 0)
    guncel["guncelleme_tarihi"] = datetime.utcnow().isoformat()
    await db.rozetler.update_one({"rol": rol, "kod": kod}, {"$set": guncel})
    return _temizle(await db.rozetler.find_one({"rol": rol, "kod": kod}))


@router.delete("/{rol}/{kod}")
async def rozet_sil(rol: str, kod: str, payload: dict = Body(default={}),
                    current_user=Depends(require_role(UserRole.ADMIN, UserRole.COORDINATOR))):
    """Rozet tanımını siler. kazananlari_koru=False ise bu roldeki kullanıcıların
    kazanımlarını da temizler (diğer roldeki aynı kod ETKİLENMEZ)."""
    res = await db.rozetler.delete_one({"rol": rol, "kod": kod})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Rozet bulunamadı")
    silinen_kazanim = 0
    if not payload.get("kazananlari_koru", True):
        uidler = await _rol_user_idleri(rol)
        r2 = await db.kazanilan_rozetler.delete_many(
            {"rozet_kodu": kod, "kullanici_id": {"$in": uidler}})
        silinen_kazanim = r2.deleted_count
    return {"ok": True, "silinen_kazanim": silinen_kazanim}


@router.get("/{rol}/{kod}/kazananlar")
async def rozet_kazananlar(rol: str, kod: str, current_user=Depends(require_role(UserRole.ADMIN, UserRole.COORDINATOR))):
    uidler = set(await _rol_user_idleri(rol))
    kazanimlar = await db.kazanilan_rozetler.find({"rozet_kodu": kod}).to_list(length=None)
    kazanimlar = [k for k in kazanimlar if k.get("kullanici_id") in uidler]
    users = {u["id"]: u for u in await db.users.find({"id": {"$in": [k["kullanici_id"] for k in kazanimlar]}}).to_list(length=None)}
    liste = []
    for k in kazanimlar:
        u = users.get(k["kullanici_id"], {})
        liste.append({
            "kullanici_id": k["kullanici_id"],
            "ad_soyad": f"{u.get('ad', '')} {u.get('soyad', '')}".strip(),
            "kazanma_tarihi": k.get("kazanma_tarihi"),
        })
    liste.sort(key=lambda x: x.get("kazanma_tarihi") or "", reverse=True)
    return {"rol": rol, "kod": kod, "toplam": len(liste), "kazananlar": liste}


@router.post("/{rol}/{kod}/ver")
async def rozet_manuel_ver(rol: str, kod: str, payload: dict = Body(...),
                           current_user=Depends(require_role(UserRole.ADMIN, UserRole.COORDINATOR))):
    """Bir kullanıcıya rozeti manuel verir + bildirim gönderir."""
    user_id = payload.get("user_id")
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id zorunlu")
    tanim = await db.rozetler.find_one({"rol": rol, "kod": kod})
    if not tanim:
        raise HTTPException(status_code=404, detail="Rozet bulunamadı")
    doc = {"id": _yeni_id(), "kullanici_id": user_id, "rozet_kodu": kod,
           "kazanma_tarihi": datetime.utcnow().isoformat(), "manuel": True}
    try:
        await db.kazanilan_rozetler.insert_one(doc)
    except DuplicateKeyError:
        return {"ok": True, "zaten_vardi": True}
    await rozet_bildirim_gonder(user_id, _temizle(tanim))
    return {"ok": True, "zaten_vardi": False}


@router.post("/{rol}/{kod}/geri-al")
async def rozet_geri_al(rol: str, kod: str, payload: dict = Body(...),
                        current_user=Depends(require_role(UserRole.ADMIN, UserRole.COORDINATOR))):
    """Bir kullanıcının kazandığı rozeti geri alır."""
    user_id = payload.get("user_id")
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id zorunlu")
    res = await db.kazanilan_rozetler.delete_one({"kullanici_id": user_id, "rozet_kodu": kod})
    return {"ok": True, "silindi": res.deleted_count > 0}


def _yeni_id():
    import uuid
    return str(uuid.uuid4())
