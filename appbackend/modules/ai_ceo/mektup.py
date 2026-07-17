"""AI CEO — Öğretmen performans mektupları (Ayda → admin aracı) + ONAY akışı.

Ayda taslak üretir: güçlü yönler (veriyle) → gelişim alanları (nazik, somut) →
teşekkür/motivasyon. ASLA kırıcı/suçlayıcı değil.

ONAY ZORUNLU (API seviyesinde de): taslak admin'e gelir, düzenler/onaylar; onaysız
HİÇBİR mektup öğretmene gitmez. Öğretmen ucu YALNIZ onaylı mektupları döndürür.
"""
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from core.db import db
from core.auth import require_role, UserRole, get_current_user
from core.ai import call_claude
from core.config import GEMINI_API_KEY

from .personalar import sistem_promptu

router = APIRouter()
_ADMIN = require_role(UserRole.ADMIN, UserRole.COORDINATOR)


async def _ogretmen_performans(ogretmen_id: str) -> dict:
    """Mektup için tek öğretmenin KENDİ agregat performansı (KVKK: iletişim verisi yok)."""
    t = await db.teachers.find_one({"id": ogretmen_id}, {"_id": 0, "telefon": 0, "email": 0, "kargo_adresi": 0})
    if not t:
        return {}
    kurlar = await db.kur_ucretleri.find({"ogrenci_id": {"$in": t.get("atanan_ogrenciler") or []}}, {"_id": 0}).to_list(length=5000)
    aktif_ogr = len(t.get("atanan_ogrenciler") or [])
    geciken = 0
    for k in kurlar:
        if k.get("durum") in (None, "acik", "aktif") and not (k.get("tamamlanma_tarihi") or k.get("odeme_tamamlanma_tarihi")):
            geciken += 1
    return {
        "ad": f"{t.get('ad','')} {t.get('soyad','')}".strip(),
        "aktif_ogrenci": aktif_ogr,
        "acik_kur": geciken,
        "seviye": t.get("seviye"),
    }


def _mektup_prompt(perf: dict) -> tuple:
    system = sistem_promptu(
        "ayda",
        "Şimdi bir ÖĞRETMEN PERFORMANS MEKTUBU taslağı yazıyorsun. Ton motive edici ve "
        "geliştirici; ASLA kırıcı/suçlayıcı değil. Yapı zorunlu: (1) güçlü yönler (veriyle), "
        "(2) gelişim alanları (nazik, somut öneriyle), (3) teşekkür/motivasyon kapanışı.")
    user = (
        f"Öğretmen performans verisi (agregat): {perf}\n\n"
        "Bu öğretmene özel, sıcak ve yapıcı bir mektup yaz. SADECE şu JSON:\n"
        '{"selamlama":"...","guclu_yonler":"...","gelisim_alanlari":"...","kapanis":"..."}'
    )
    return system, user


def _deterministik_mektup(perf: dict) -> dict:
    ad = perf.get("ad", "Değerli Öğretmenimiz")
    return {
        "selamlama": f"Sayın {ad},",
        "guclu_yonler": f"Bu dönem {perf.get('aktif_ogrenci', 0)} öğrenciyle emek verdiniz; "
                        "öğrencilerinizin gelişimine katkınız değerli.",
        "gelisim_alanlari": (f"Açık {perf.get('acik_kur', 0)} kur var; birkaçını planlı ek "
                             "çalışmayla zamanında tamamlamak yenilemeyi güçlendirir." if perf.get("acik_kur") else
                             "Mevcut temponuzu koruyarak öğrenci takibini sürdürmeniz yeterli."),
        "kapanis": "Emeğiniz için teşekkür ederiz; birlikte daha da güçleneceğiz.",
    }


async def _mektup_uret(ogretmen_id: str) -> dict:
    perf = await _ogretmen_performans(ogretmen_id)
    if not perf:
        raise HTTPException(status_code=404, detail="Öğretmen bulunamadı")
    icerik = None
    if GEMINI_API_KEY:
        try:
            system, user = _mektup_prompt(perf)
            res = await call_claude(system, user, max_tokens=1500, ozellik="ceo_brifing")
            p = res.get("parsed")
            if isinstance(p, dict) and p.get("kapanis"):
                icerik = p
        except Exception as e:
            logging.warning(f"[ai_ceo] mektup AI hatası: {e}")
    if not icerik:
        icerik = _deterministik_mektup(perf)
    kayit = {
        "id": str(uuid.uuid4()),
        "ogretmen_id": ogretmen_id,
        "ogretmen_ad": perf.get("ad"),
        "icerik": icerik,
        "durum": "taslak",     # taslak | onayli | reddedildi
        "onayli": False,       # API guard: True olmadan öğretmene GÖRÜNMEZ
        "tarih": datetime.now(timezone.utc).isoformat(),
        "ureten": "ayda",
    }
    await db.ai_ceo_mektuplar.insert_one({**kayit})
    kayit.pop("_id", None)
    return kayit


# ─────────────────────────── admin uçları ───────────────────────────
@router.post("/ai/ceo/mektup/uret")
async def mektup_uret(govde: dict, current_user=Depends(_ADMIN)):
    ogretmen_id = govde.get("ogretmen_id")
    if not ogretmen_id:
        raise HTTPException(status_code=400, detail="ogretmen_id gerekli")
    return {"ok": True, "mektup": await _mektup_uret(ogretmen_id)}


@router.post("/ai/ceo/mektup/toplu")
async def mektup_toplu(current_user=Depends(_ADMIN)):
    teachers = await db.teachers.find({"arsivli": {"$ne": True}}, {"_id": 0, "id": 1}).to_list(length=5000)
    uretilen = []
    for t in teachers:
        try:
            m = await _mektup_uret(t["id"])
            uretilen.append({"id": m["id"], "ogretmen_id": m["ogretmen_id"], "ogretmen_ad": m["ogretmen_ad"]})
        except Exception as e:
            logging.warning(f"[ai_ceo] toplu mektup {t['id']} hatası: {e}")
    return {"ok": True, "uretilen": len(uretilen), "mektuplar": uretilen}


@router.get("/ai/ceo/mektuplar")
async def mektup_listesi(current_user=Depends(_ADMIN)):
    docs = await db.ai_ceo_mektuplar.find({}, {"_id": 0}).sort("tarih", -1).to_list(length=1000)
    return {"mektuplar": docs}


@router.put("/ai/ceo/mektup/{mektup_id}")
async def mektup_duzenle(mektup_id: str, govde: dict, current_user=Depends(_ADMIN)):
    icerik = govde.get("icerik")
    if not isinstance(icerik, dict):
        raise HTTPException(status_code=400, detail="icerik (obje) gerekli")
    r = await db.ai_ceo_mektuplar.update_one(
        {"id": mektup_id, "onayli": False},  # onaylı mektup düzenlenemez
        {"$set": {"icerik": icerik, "duzenlendi": True}})
    if r.matched_count == 0:
        raise HTTPException(status_code=404, detail="Taslak mektup bulunamadı (onaylı olabilir)")
    return {"ok": True}


@router.post("/ai/ceo/mektup/{mektup_id}/onayla")
async def mektup_onayla(mektup_id: str, current_user=Depends(_ADMIN)):
    m = await db.ai_ceo_mektuplar.find_one({"id": mektup_id})
    if not m:
        raise HTTPException(status_code=404, detail="Mektup bulunamadı")
    if m.get("onayli"):
        return {"ok": True, "zaten_onayli": True}
    now = datetime.now(timezone.utc).isoformat()
    await db.ai_ceo_mektuplar.update_one({"id": mektup_id}, {"$set": {
        "onayli": True, "durum": "onayli", "onaylayan": current_user.get("id"), "onay_tarih": now}})
    # Onaylı mektup öğretmenin bildirimine düşer
    try:
        from modules.bildirim import bildirim_olustur
        await bildirim_olustur(m["ogretmen_id"], "ai_ceo_mektup",
                               "📩 Yönetimden size özel bir performans mektubu var.", mektup_id)
    except Exception as e:
        logging.warning(f"[ai_ceo] mektup bildirim hatası: {e}")
    return {"ok": True, "onaylandi": True}


@router.post("/ai/ceo/mektup/{mektup_id}/reddet")
async def mektup_reddet(mektup_id: str, govde: dict = None, current_user=Depends(_ADMIN)):
    r = await db.ai_ceo_mektuplar.update_one(
        {"id": mektup_id, "onayli": False},
        {"$set": {"durum": "reddedildi", "red_notu": str((govde or {}).get("not", ""))[:400]}})
    if r.matched_count == 0:
        raise HTTPException(status_code=404, detail="Taslak bulunamadı")
    return {"ok": True}


# ─────────────────────────── öğretmen ucu (YALNIZ ONAYLI) ───────────────────────────
@router.get("/ai/ceo/mektuplarim")
async def mektuplarim(current_user=Depends(get_current_user)):
    if current_user.get("role") != "teacher":
        raise HTTPException(status_code=403, detail="Bu sayfa öğretmenler içindir.")
    oid = current_user.get("linked_id") or current_user.get("id")
    # API GUARD: yalnız onaylı mektuplar döner — taslak ASLA sızmaz
    docs = await db.ai_ceo_mektuplar.find(
        {"ogretmen_id": oid, "onayli": True}, {"_id": 0, "onaylayan": 0}
    ).sort("onay_tarih", -1).to_list(length=200)
    return {"mektuplar": docs}
