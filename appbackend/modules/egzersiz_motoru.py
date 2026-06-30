"""Egzersiz Motoru — jenerik egzersiz üretim, oturum ve puanlama motoru.

Tek bir motor, çok sayıda egzersiz tipini yönetir. Tip başına özel endpoint
YOKTUR; tip tanımları core/egzersiz_tipleri.py ve core/egzersiz_prompts.py
içinde config olarak durur.

Endpoint'ler (hepsi /api/egzersiz/ önekinde):
  GET  /egzersiz/tipler                  → tip listesi (opsiyonel ?sinif=)
  POST /egzersiz/uret                    → AI ile içerik üretir + cache'ler
  POST /egzersiz/oturum                  → yeni oturum başlatır
  POST /egzersiz/oturum/{id}/cevap       → tek soru doğruluğu
  POST /egzersiz/oturum/{id}/bitir       → puanlama + XP + kayıt
  GET  /egzersiz/gecmis/{ogrenci_id}     → oturum geçmişi
  GET  /egzersiz/icerikler               → cache'lenmiş içerikler (öğretmen)

NOT: Mevcut egzersiz/Leitner/Sokratik/Sesli modüllerine DOKUNULMAZ; bu motor
yalnızca yeni egzersiz tiplerini yönetir.
"""
import uuid
import random
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query

from core.db import db
from core.auth import get_current_user
from core.ai import call_claude
from core.sistem import get_xp_tablosu
from core.egzersiz_tipleri import tip_var_mi, tip_meta, tip_listesi
from core.egzersiz_prompts import prompt_uret, mock_uret

router = APIRouter()

# Bir içeriğin kaç oturumda tekrar gösterilebileceği (cache yeniden kullanım)
MAX_KULLANIM = 5


# ─────────────────────────────────────────────
# Yardımcılar
# ─────────────────────────────────────────────
def _temizle(doc: dict) -> dict:
    if doc:
        doc.pop("_id", None)
    return doc


def _toplam_soru(meta: dict, icerik: dict) -> int:
    p = meta.get("puanlama", "secmeli")
    if p == "secmeli":
        return len(icerik.get("sorular", []))
    if p == "eslesme":
        return len(icerik.get("ciftler", []))
    # sira / serbest → tek puanlama
    return 1


async def _icerik_uret(tip: str, sinif: int, konu: str | None, zorluk: str | None) -> tuple[dict, bool]:
    """AI ile içerik üretir. Başarısızsa 1 kez retry, yine olmazsa mock döner.

    Dönüş: (icerik_dict, mock_mu)
    """
    meta = tip_meta(tip)
    soru_sayisi = meta.get("soru_sayisi", 5)
    system, user_msg = prompt_uret(tip, sinif, konu, soru_sayisi, zorluk)
    if not user_msg:
        return mock_uret(tip, sinif, konu, soru_sayisi), True

    for deneme in range(2):
        try:
            res = await call_claude(system, user_msg, max_tokens=3000)
            parsed = res.get("parsed")
            if isinstance(parsed, dict) and parsed:
                return parsed, False
        except Exception as ex:
            logging.warning(f"[egzersiz_motoru] AI üretim hatası ({tip}, deneme {deneme}): {ex}")
    # Fallback
    logging.info(f"[egzersiz_motoru] '{tip}' için mock içerik kullanılıyor")
    return mock_uret(tip, sinif, konu, soru_sayisi), True


async def _icerik_kaydet(tip: str, sinif: int, konu: str | None, zorluk: str | None,
                         icerik: dict, ekleyen_id: str, mock: bool) -> dict:
    doc = {
        "id": str(uuid.uuid4()),
        "tip": tip,
        "sinif": sinif,
        "konu": konu or "",
        "zorluk": zorluk or "orta",
        "icerik": icerik,
        "mock": bool(mock),
        "olusturma_tarihi": datetime.utcnow().isoformat(),
        "ekleyen_id": ekleyen_id,
        "kullanim_sayisi": 0,
    }
    await db.egzersiz_icerikler.insert_one(dict(doc))
    return doc


async def _icerik_sec_veya_uret(tip: str, sinif: int, ekleyen_id: str) -> dict:
    """Oturum için içerik seçer: önce cache'ten az kullanılmış rastgele bir içerik,
    yoksa AI ile üretir."""
    adaylar = await db.egzersiz_icerikler.find({
        "tip": tip, "sinif": sinif, "kullanim_sayisi": {"$lt": MAX_KULLANIM}
    }).to_list(length=50)
    if adaylar:
        return random.choice(adaylar)
    icerik, mock = await _icerik_uret(tip, sinif, None, None)
    return await _icerik_kaydet(tip, sinif, None, None, icerik, ekleyen_id, mock)


def _kontrol(meta: dict, icerik: dict, soru_no: int, cevap) -> tuple[bool, object]:
    """Jenerik cevap kontrolü — puanlama stratejisine göre.

    Dönüş: (dogru_mu, dogru_cevap)
    """
    p = meta.get("puanlama", "secmeli")
    try:
        if p == "secmeli":
            sorular = icerik.get("sorular", [])
            if 0 <= soru_no < len(sorular):
                dogru = sorular[soru_no].get("dogru")
                return (cevap == dogru), dogru
            return False, None
        if p == "sira":
            dogru_sira = icerik.get("dogru_sira", [])
            return (list(cevap) == list(dogru_sira)), dogru_sira
        if p == "eslesme":
            ciftler = icerik.get("ciftler", [])
            # cevap: {"sol": index, "sag": eşleştirilen değer}
            if isinstance(cevap, dict):
                idx = cevap.get("sol")
                if isinstance(idx, int) and 0 <= idx < len(ciftler):
                    beklenen = list(ciftler[idx].values())
                    return (cevap.get("sag") in beklenen), ciftler[idx]
            return False, None
        # serbest → dış puanlama (ör. telaffuz); cevap doğru kabul edilir
        return bool(cevap), cevap
    except Exception as ex:
        logging.warning(f"[egzersiz_motoru] kontrol hatası: {ex}")
        return False, None


def _ogrenci_id(current_user: dict) -> str:
    return current_user.get("linked_id") or current_user.get("id")


# ─────────────────────────────────────────────
# Endpoint'ler
# ─────────────────────────────────────────────
@router.get("/egzersiz/tipler")
async def egzersiz_tipler(sinif: int | None = Query(None)):
    """Kayıtlı tüm egzersiz tiplerini (opsiyonel sınıf filtresiyle) döndürür."""
    return {"tipler": tip_listesi(sinif)}


@router.post("/egzersiz/uret")
async def egzersiz_uret(data: dict, current_user=Depends(get_current_user)):
    """AI ile yeni içerik üretir ve cache'ler."""
    tip = data.get("tip", "")
    sinif = int(data.get("sinif", 3))
    konu = data.get("konu")
    zorluk = data.get("zorluk")
    if not tip_var_mi(tip):
        raise HTTPException(status_code=400, detail=f"Bilinmeyen egzersiz tipi: {tip}")
    icerik, mock = await _icerik_uret(tip, sinif, konu, zorluk)
    doc = await _icerik_kaydet(tip, sinif, konu, zorluk, icerik, current_user.get("id"), mock)
    return _temizle(doc)


@router.post("/egzersiz/oturum")
async def egzersiz_oturum_baslat(data: dict, current_user=Depends(get_current_user)):
    """Yeni oturum başlatır. icerik_id verilmezse cache/AI'dan içerik seçilir."""
    tip = data.get("tip", "")
    sinif = int(data.get("sinif", 3))
    icerik_id = data.get("icerik_id")
    if not tip_var_mi(tip):
        raise HTTPException(status_code=400, detail=f"Bilinmeyen egzersiz tipi: {tip}")
    meta = tip_meta(tip)

    if icerik_id:
        icerik_doc = await db.egzersiz_icerikler.find_one({"id": icerik_id})
        if not icerik_doc:
            raise HTTPException(status_code=404, detail="İçerik bulunamadı")
    else:
        icerik_doc = await _icerik_sec_veya_uret(tip, sinif, current_user.get("id"))

    await db.egzersiz_icerikler.update_one({"id": icerik_doc["id"]}, {"$inc": {"kullanim_sayisi": 1}})

    oturum = {
        "id": str(uuid.uuid4()),
        "ogrenci_id": _ogrenci_id(current_user),
        "tip": tip,
        "icerik_id": icerik_doc["id"],
        "cevaplar": [],
        "dogru_sayisi": 0,
        "toplam_soru": _toplam_soru(meta, icerik_doc.get("icerik", {})),
        "sure_sn": 0,
        "puan": 0,
        "xp": 0,
        "durum": "devam",
        "baslama_t": datetime.utcnow().isoformat(),
        "bitis_t": None,
    }
    await db.egzersiz_oturumlari.insert_one(dict(oturum))
    return {
        "oturum_id": oturum["id"],
        "tip": tip,
        "toplam_soru": oturum["toplam_soru"],
        "icerik_id": icerik_doc["id"],
        "icerik": icerik_doc.get("icerik", {}),
        "mock": icerik_doc.get("mock", False),
    }


@router.post("/egzersiz/oturum/{oturum_id}/cevap")
async def egzersiz_cevap(oturum_id: str, data: dict, current_user=Depends(get_current_user)):
    """Tek bir sorunun cevabını değerlendirir."""
    oturum = await db.egzersiz_oturumlari.find_one({"id": oturum_id})
    if not oturum:
        raise HTTPException(status_code=404, detail="Oturum bulunamadı")
    meta = tip_meta(oturum["tip"])
    icerik_doc = await db.egzersiz_icerikler.find_one({"id": oturum["icerik_id"]})
    icerik = icerik_doc.get("icerik", {}) if icerik_doc else {}

    soru_no = int(data.get("soru_no", 0))
    cevap = data.get("cevap")
    dogru, dogru_cevap = _kontrol(meta, icerik, soru_no, cevap)

    await db.egzersiz_oturumlari.update_one(
        {"id": oturum_id},
        {
            "$push": {"cevaplar": {"soru_no": soru_no, "cevap": cevap, "dogru": dogru}},
            "$inc": {"dogru_sayisi": 1 if dogru else 0},
        },
    )
    return {"dogru": dogru, "dogru_cevap": dogru_cevap}


@router.post("/egzersiz/oturum/{oturum_id}/bitir")
async def egzersiz_bitir(oturum_id: str, data: dict = None, current_user=Depends(get_current_user)):
    """Oturumu kapatır, puan + XP hesaplar ve kaydeder."""
    data = data or {}
    oturum = await db.egzersiz_oturumlari.find_one({"id": oturum_id})
    if not oturum:
        raise HTTPException(status_code=404, detail="Oturum bulunamadı")
    if oturum.get("durum") == "tamamlandi":
        return _temizle(oturum)

    toplam = oturum.get("toplam_soru", 0) or 1
    dogru_sayisi = oturum.get("dogru_sayisi", 0)
    sure_sn = int(data.get("sure_sn", 0))
    oran = dogru_sayisi / toplam if toplam else 0

    baz_xp = (await get_xp_tablosu()).get("egzersiz_motoru", 10)
    xp = round(baz_xp * oran)
    puan = dogru_sayisi * 2

    await db.egzersiz_oturumlari.update_one(
        {"id": oturum_id},
        {"$set": {
            "durum": "tamamlandi",
            "sure_sn": sure_sn,
            "puan": puan,
            "xp": xp,
            "bitis_t": datetime.utcnow().isoformat(),
        }},
    )

    # XP'yi öğrenciye ekle (kanonik desen: db.students + xp_logs)
    ogrenci_id = oturum.get("ogrenci_id")
    if xp > 0 and ogrenci_id:
        await db.students.update_one({"id": ogrenci_id}, {"$inc": {"toplam_xp": xp}})
        await db.xp_logs.insert_one({
            "id": str(uuid.uuid4()),
            "ogrenci_id": ogrenci_id,
            "eylem": f"egzersiz_{oturum['tip']}",
            "xp": xp,
            "tarih": datetime.utcnow().isoformat(),
        })

    return {
        "oturum_id": oturum_id,
        "dogru_sayisi": dogru_sayisi,
        "toplam_soru": toplam,
        "puan": puan,
        "xp": xp,
        "oran": round(oran * 100),
    }


@router.get("/egzersiz/gecmis/{ogrenci_id}")
async def egzersiz_gecmis(ogrenci_id: str, current_user=Depends(get_current_user)):
    """Öğrencinin egzersiz oturum geçmişi (son 50)."""
    oturumlar = await db.egzersiz_oturumlari.find(
        {"ogrenci_id": ogrenci_id}
    ).sort("baslama_t", -1).to_list(length=50)
    for o in oturumlar:
        o.pop("_id", None)
    return {"oturumlar": oturumlar}


@router.get("/egzersiz/icerikler")
async def egzersiz_icerikler(tip: str = Query(...), sinif: int | None = Query(None),
                             current_user=Depends(get_current_user)):
    """Öğretmen için: cache'lenmiş içerikleri listeler."""
    sorgu = {"tip": tip}
    if sinif is not None:
        sorgu["sinif"] = sinif
    icerikler = await db.egzersiz_icerikler.find(sorgu).sort("olusturma_tarihi", -1).to_list(length=100)
    for i in icerikler:
        i.pop("_id", None)
    return {"icerikler": icerikler}
