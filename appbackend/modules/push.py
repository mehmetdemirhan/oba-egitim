"""Web Push modülü (/push/*) — ders hatırlatma bildirimleri (VAPID).

Akış:
  - Veli tarayıcıda izin verir → PushSubscription → POST /push/abone (kaydedilir)
  - Dışarıdan cron (cron-job.org) her dakika POST /push/kontrol'ü çağırır
    (aktif saatlerde). Motor, ~15 dk sonra dersi olan öğrencilerin velilerine
    web push gönderir. Idempotent (aynı ders için tekrar göndermez).

Render Free uykusu: cron hem servisi uyandırır hem kontrolü tetikler.
Zaman: ders saatleri yerel (TR) saklandığı için UTC+PUSH_TZ_OFFSET_SAAT kullanılır.
"""
import json
import logging
from datetime import datetime, timedelta, date

from fastapi import APIRouter, Depends, HTTPException, Body, Query

from core.db import db
from core.auth import get_current_user
from core.config import (
    VAPID_PUBLIC_KEY, VAPID_PRIVATE_KEY, VAPID_SUBJECT,
    PUSH_TZ_OFFSET_SAAT, PUSH_HATIRLATMA_DK, PUSH_CRON_TOKEN,
)

router = APIRouter(prefix="/push", tags=["push"])


# ─────────────────────────────────────────────
# ABONELİK
# ─────────────────────────────────────────────
@router.get("/vapid-public")
async def vapid_public():
    """Frontend abone olurken kullanacağı applicationServerKey (public)."""
    return {"public_key": VAPID_PUBLIC_KEY, "aktif": bool(VAPID_PRIVATE_KEY)}


@router.post("/abone")
async def abone_ol(payload: dict = Body(...), current_user=Depends(get_current_user)):
    """PushSubscription'ı kaydeder (cihaz başına endpoint ile upsert)."""
    sub = payload.get("subscription") or payload
    endpoint = sub.get("endpoint")
    if not endpoint:
        raise HTTPException(status_code=400, detail="Geçersiz abonelik")
    await db.push_abonelikleri.update_one(
        {"endpoint": endpoint},
        {"$set": {"user_id": current_user["id"], "endpoint": endpoint,
                  "subscription": sub, "tarih": datetime.utcnow().isoformat()}},
        upsert=True,
    )
    return {"ok": True}


@router.delete("/abone")
async def abone_sil(payload: dict = Body(default={}), current_user=Depends(get_current_user)):
    endpoint = payload.get("endpoint")
    q = {"user_id": current_user["id"]}
    if endpoint:
        q["endpoint"] = endpoint
    res = await db.push_abonelikleri.delete_many(q)
    return {"ok": True, "silindi": res.deleted_count}


@router.get("/durum")
async def durum(current_user=Depends(get_current_user)):
    """Kullanıcının kaç cihazda abone olduğu."""
    n = await db.push_abonelikleri.count_documents({"user_id": current_user["id"]})
    return {"abone_cihaz": n, "aktif": bool(VAPID_PRIVATE_KEY)}


# ─────────────────────────────────────────────
# GÖNDERİM
# ─────────────────────────────────────────────
async def _web_push_gonder(sub: dict, payload: dict) -> bool:
    """Tek bir aboneliğe push gönderir. 404/410 (ölü abonelik) ise siler."""
    from pywebpush import webpush, WebPushException
    try:
        webpush(
            subscription_info=sub,
            data=json.dumps(payload),
            vapid_private_key=VAPID_PRIVATE_KEY,
            vapid_claims={"sub": VAPID_SUBJECT},
            timeout=10,
        )
        return True
    except WebPushException as ex:
        kod = getattr(ex.response, "status_code", None)
        if kod in (404, 410):  # abonelik ölmüş → temizle
            await db.push_abonelikleri.delete_one({"endpoint": sub.get("endpoint")})
        else:
            logging.warning(f"[push] gönderim hatası ({kod}): {ex}")
        return False
    except Exception as ex:
        logging.warning(f"[push] beklenmeyen hata: {ex}")
        return False


async def _kullaniciya_gonder(user_id: str, payload: dict) -> int:
    """Kullanıcının tüm cihazlarına gönderir; başarılı gönderim sayısını döner."""
    gonderilen = 0
    async for a in db.push_abonelikleri.find({"user_id": user_id}):
        if await _web_push_gonder(a["subscription"], payload):
            gonderilen += 1
    return gonderilen


# ─────────────────────────────────────────────
# DERS HATIRLATMA MOTORU
# ─────────────────────────────────────────────
async def _gunun_dersleri(gun_date: date) -> list:
    """Verilen gün için tüm dersler (somut oturumlar + seri-planlı, çakışma tekilleştirilmiş)."""
    from modules.ders_programi import _seri_planli_uret
    today_iso = gun_date.isoformat()
    bloke, dersler = set(), []
    IPTAL = {"iptal", "iptal_edildi", "gelmedi_iptal"}
    async for o in db.ders_oturumlari.find({"tarih": {"$regex": f"^{today_iso}"}}):
        if o.get("seri_id"):
            bloke.add((o["seri_id"], today_iso))
        if (o.get("yoklama") or "planli") in IPTAL:
            continue
        dersler.append(o)
    async for s in db.ders_serileri.find({"durum": "aktif", "gun": gun_date.weekday()}):
        dersler += _seri_planli_uret(s, gun_date, gun_date, bloke)
    return dersler


async def _ogrenci_veli_userlari(ogrenci_id: str) -> set:
    """Öğrencinin velisi olan USER id'lerini çözer (students.veli_id + linked_id)."""
    ids = set()
    st = await db.students.find_one({"id": ogrenci_id})
    if st and st.get("veli_id"):
        ids.add(st["veli_id"])
    async for u in db.users.find({"role": "parent", "linked_id": ogrenci_id}, {"id": 1}):
        ids.add(u["id"])
    return ids


@router.post("/kontrol")
async def push_kontrol(anahtar: str = Query(default=""), gonder: bool = Query(default=True)):
    """Cron ucu: ~PUSH_HATIRLATMA_DK dk sonra dersi olan öğrencilerin velilerine push.

    Güvenlik: PUSH_CRON_TOKEN tanımlıysa ?anahtar= eşleşmeli. Idempotent."""
    if PUSH_CRON_TOKEN and anahtar != PUSH_CRON_TOKEN:
        raise HTTPException(status_code=403, detail="Geçersiz anahtar")

    simdi_tr = datetime.utcnow() + timedelta(hours=PUSH_TZ_OFFSET_SAAT)
    hedef = simdi_tr + timedelta(minutes=PUSH_HATIRLATMA_DK)
    hedef_saat = hedef.strftime("%H:%M")
    gun_date = hedef.date()

    dersler = [d for d in await _gunun_dersleri(gun_date)
               if d.get("baslangic_saati") == hedef_saat]

    gonderilen, veli_sayisi = 0, 0
    for d in dersler:
        anahtar_key = f"{d['ogrenci_id']}_{gun_date.isoformat()}_{d['baslangic_saati']}"
        if await db.push_gonderimler.find_one({"anahtar": anahtar_key}):
            continue  # zaten bildirildi
        veliler = await _ogrenci_veli_userlari(d["ogrenci_id"])
        ogr_ad = d.get("ogrenci_ad", "Öğrenci")
        payload = {
            "baslik": "📚 Ders Hatırlatma",
            "govde": f"{ogr_ad}'nin dersi {d['baslangic_saati']}'te başlıyor ({PUSH_HATIRLATMA_DK} dk kaldı).",
            "url": "/",
        }
        if gonder:
            for uid in veliler:
                gonderilen += await _kullaniciya_gonder(uid, payload)
        veli_sayisi += len(veliler)
        await db.push_gonderimler.insert_one({
            "anahtar": anahtar_key, "ogrenci_id": d["ogrenci_id"],
            "saat": d["baslangic_saati"], "veli_sayisi": len(veliler),
            "tarih": datetime.utcnow().isoformat(),
        })

    return {
        "ok": True, "hedef_saat": hedef_saat, "gun": gun_date.isoformat(),
        "ders_sayisi": len(dersler), "veli_sayisi": veli_sayisi, "gonderilen": gonderilen,
    }
