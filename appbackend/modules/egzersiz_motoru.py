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
import asyncio
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query

from core.db import db
from core.auth import get_current_user, require_role, UserRole
from core.ai import call_claude
from core.sistem import get_xp_tablosu
from core.egzersiz_tipleri import tip_var_mi, tip_meta, tip_listesi
from core.egzersiz_prompts import prompt_uret, mock_uret
from core.bulmaca_olusturucu import bulmaca_uret, kelime_dogrula

router = APIRouter()

# Bir içerik bu kadar kez kullanılınca (havuzdaki en az kullanılan bile) arka
# planda taze içerik üretilir — kullanıcı beklemeden çeşitlilik korunur.
YENILEME_ESIGI = 20

# Aynı (tip, sınıf) için aynı anda birden fazla arka plan üretimi tetiklenmesin.
_yenileme_aktif: set = set()

# Kelime-odaklı egzersiz tipleri: AI içeriğinde MEB müfredat kelimelerine öncelik ver.
_MEB_KELIME_TIPLERI = {
    "kelime_anlam_eslestirme", "es_karsit_anlamli", "anagram", "bulmaca",
    "kelime_yagmuru", "kelime_merdiveni", "baglam_ipucu", "frayer",
    "anlam_haritasi", "sight_words", "hafiza_karti",
}


# ─────────────────────────────────────────────
# Yardımcılar
# ─────────────────────────────────────────────
def _temizle(doc: dict) -> dict:
    if doc:
        doc.pop("_id", None)
    return doc


async def _meb_kelimeler(sinif: int, sadece_anlamli: bool = False, limit: int = 500) -> list[str]:
    """MEB müfredat kelimelerini güvenli biçimde getirir (hata → boş liste)."""
    try:
        from core.kelime_secici import meb_kelime_stringleri
        return await meb_kelime_stringleri(sinif, sadece_anlamli=sadece_anlamli, limit=limit)
    except Exception as ex:
        logging.warning(f"[egzersiz_motoru] MEB kelime getirme hatası: {ex}")
        return []


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

    # Kelime Gezmece (ve "bulmaca" üreticili tipler): içerik AI ile değil,
    # core/bulmaca_olusturucu.py ile yerel üretilir. Mock değildir.
    # MEB müfredat kelimeleri varsa bulmaca onların önceliğiyle kurulur.
    if meta.get("icerik_uretici") == "bulmaca":
        meb = await _meb_kelimeler(sinif)
        return bulmaca_uret(sinif, meb_kelimeler=meb or None), False

    system, user_msg = prompt_uret(tip, sinif, konu, soru_sayisi, zorluk)
    if not user_msg:
        return mock_uret(tip, sinif, konu, soru_sayisi), True

    # MEB/kitap önceliği: kelime-odaklı tiplerde AI'a bu kelimelerden üretmesini söyle.
    # (Liste, köprü sayesinde müfredat + AI Eğit ile yüklenen kitap kelimelerini içerir.)
    if tip in _MEB_KELIME_TIPLERI:
        meb = await _meb_kelimeler(sinif, sadece_anlamli=True, limit=60)
        if meb:
            user_msg += ("\n\nZORUNLU KAYNAK: Bu egzersizi ÖNCELİKLE aşağıdaki kelimelerden üret "
                         "(öğrencinin okulda/kitaplarında öğrendiği kelimeler). Mümkün olduğunca "
                         f"YALNIZCA bu listeden seç:\n{', '.join(meb[:40])}.")

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
                         icerik: dict, ekleyen_id: str, mock: bool,
                         kaynak: str = "ai_uretim", olusturan: dict | None = None,
                         varyant_grubu: str | None = None) -> dict:
    """İçeriği kalıcı kütüphaneye kaydeder.

    Kütüphane şeması (eski kayıtlar bu alanlar olmadan da çalışır; sorgular
    eksik `durum`'u "aktif" kabul eder):
      - durum: "aktif" | "arsivli"
      - varyant_grubu: orijinal içeriğin id'si (orijinal ise kendi id'si)
      - kaynak: "ai_uretim" | "manuel" | "prewarm"
      - olusturan_id / olusturan_ad / olusturan_rol
      - son_kullanim_tarihi
    """
    yeni_id = str(uuid.uuid4())
    olusturan = olusturan or {}
    doc = {
        "id": yeni_id,
        "tip": tip,
        "sinif": sinif,
        "konu": konu or "",
        "zorluk": zorluk or "orta",
        "icerik": icerik,
        "mock": bool(mock),
        "durum": "aktif",
        # Orijinal içerik kendi id'sini grup yapar; varyantlar orijinalin grubunu paylaşır.
        "varyant_grubu": varyant_grubu or yeni_id,
        "kaynak": kaynak,
        "olusturan_id": olusturan.get("id") or ekleyen_id,
        "olusturan_ad": olusturan.get("ad", ""),
        "olusturan_rol": olusturan.get("rol", ""),
        "olusturma_tarihi": datetime.utcnow().isoformat(),
        "ekleyen_id": ekleyen_id,
        "kullanim_sayisi": 0,
        "son_kullanim_tarihi": None,
    }
    await db.egzersiz_icerikler.insert_one(dict(doc))
    return doc


async def _arka_plan_uret(tip: str, sinif: int, ekleyen_id: str):
    """Sıcak (çok kullanılan) bir tip için arka planda yeni içerik üretip cache'ler.

    Yalnızca GERÇEK (mock olmayan) içerik eklenir; kullanıcı akışını bloklamaz.
    Aynı (tip, sınıf) için eşzamanlı tekrar tetiklenmeyi `_yenileme_aktif` engeller.
    """
    anahtar = (tip, sinif)
    if anahtar in _yenileme_aktif:
        return
    _yenileme_aktif.add(anahtar)
    try:
        icerik, mock = await _icerik_uret(tip, sinif, None, None)
        if not mock:
            await _icerik_kaydet(tip, sinif, None, None, icerik, ekleyen_id, mock)
            logging.info(f"[egzersiz_motoru] arka plan içerik üretildi: {tip} s{sinif}")
    except Exception as ex:
        logging.warning(f"[egzersiz_motoru] arka plan üretim hatası ({tip} s{sinif}): {ex}")
    finally:
        _yenileme_aktif.discard(anahtar)


# Eski kayıtlarda `durum` alanı yoksa "aktif" kabul edilir (migration gerekmez).
_AKTIF = {"$or": [{"durum": "aktif"}, {"durum": {"$exists": False}}]}


def _aktif_sorgu(tip: str, sinif: int) -> dict:
    return {"tip": tip, "sinif": sinif, **_AKTIF}


async def _icerik_sec_veya_uret(tip: str, sinif: int, ekleyen_id: str) -> dict:
    """Oturum için kalıcı kütüphaneden içerik seçer.

    1. (tip, sınıf) için durum="aktif" içerikleri kullanım sayısı artan, eşitlikte
       son kullanımı en eski olacak şekilde getirir (round-robin etkisi); en az
       kullanılanların oluşturduğu küçük banttan RASTGELE seçer (çeşitlilik).
    2. Hiç aktif içerik yoksa SADECE O ZAMAN AI ile üretir ve kütüphaneye ekler.
    3. Havuzdaki en az kullanılan içerik bile YENILEME_ESIGI'ye ulaştıysa
       (tüm havuz "sıcak"), arka planda taze içerik üretmeyi sıraya koyar.
    """
    adaylar = await db.egzersiz_icerikler.find(_aktif_sorgu(tip, sinif)).sort(
        [("kullanim_sayisi", 1), ("son_kullanim_tarihi", 1)]
    ).to_list(length=30)

    if adaylar:
        en_az = adaylar[0].get("kullanim_sayisi", 0)
        havuz = [a for a in adaylar if a.get("kullanim_sayisi", 0) <= en_az + 2]
        secilen = random.choice(havuz)
        if en_az >= YENILEME_ESIGI:
            # Bloklamadan arka planda yeni içerik üret (kullanıcı bunu beklemez).
            asyncio.create_task(_arka_plan_uret(tip, sinif, ekleyen_id))
        return secilen

    icerik, mock = await _icerik_uret(tip, sinif, None, None)
    return await _icerik_kaydet(tip, sinif, None, None, icerik, ekleyen_id, mock,
                                kaynak="ai_uretim")


# ─────────────────────────────────────────────
# Kütüphane yardımcıları
# ─────────────────────────────────────────────
def _kullanici_ad(user: dict) -> str:
    ad = f"{user.get('ad', '')} {user.get('soyad', '')}".strip()
    return ad or user.get("ad") or "Kullanıcı"


def _icerik_ozet(icerik: dict, uzunluk: int = 100) -> str:
    """İçeriğin insan-okur kısa özetini (ilk ~100 karakter) üretir."""
    if not isinstance(icerik, dict):
        return ""
    parca = ""
    if icerik.get("metin"):
        parca = str(icerik["metin"])
    elif icerik.get("sorular"):
        ilk = icerik["sorular"][0] if icerik["sorular"] else {}
        parca = str(ilk.get("soru", ""))
    elif icerik.get("ciftler"):
        parca = ", ".join(f"{c.get('sol', '')}={c.get('sag', '')}" for c in icerik["ciftler"][:4])
    elif icerik.get("kelimeler"):
        parca = ", ".join(str(k.get("cevap", k)) for k in icerik["kelimeler"][:6])
    elif icerik.get("kelime"):
        parca = str(icerik["kelime"])
    elif icerik.get("parcalar"):
        parca = " ".join(map(str, icerik["parcalar"]))
    elif icerik.get("olaylar"):
        parca = " / ".join(map(str, icerik["olaylar"][:3]))
    elif icerik.get("hedef"):
        parca = str(icerik["hedef"])
    parca = " ".join(parca.split())
    return parca[:uzunluk] + ("…" if len(parca) > uzunluk else "")


def _ozet_kayit(d: dict) -> dict:
    """Kütüphane listesi için tek içeriğin özet kaydı."""
    meta = tip_meta(d.get("tip", "")) or {}
    return {
        "id": d.get("id"),
        "tip": d.get("tip"),
        "tip_ad": meta.get("ad", d.get("tip")),
        "ikon": meta.get("ikon", "📝"),
        "sinif": d.get("sinif"),
        "ozet": _icerik_ozet(d.get("icerik", {})),
        "olusturan_ad": d.get("olusturan_ad") or "—",
        "olusturan_rol": d.get("olusturan_rol") or "",
        "kaynak": d.get("kaynak", "ai_uretim"),
        "durum": d.get("durum", "aktif"),
        "kullanim_sayisi": d.get("kullanim_sayisi", 0),
        "varyant_grubu": d.get("varyant_grubu") or d.get("id"),
        "son_kullanim_tarihi": d.get("son_kullanim_tarihi"),
        "olusturma_tarihi": d.get("olusturma_tarihi"),
        "mock": d.get("mock", False),
    }


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

    await db.egzersiz_icerikler.update_one(
        {"id": icerik_doc["id"]},
        {"$inc": {"kullanim_sayisi": 1},
         "$set": {"son_kullanim_tarihi": datetime.utcnow().isoformat()}},
    )

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


@router.post("/egzersiz/kelime-gezmece/dogrula")
async def kelime_gezmece_dogrula(data: dict, current_user=Depends(get_current_user)):
    """Kelime Gezmece — oyuncunun oluşturduğu kelimeyi doğrular.

    Body: { icerik_id, harf_sirasi: ["e","l","m","a"] }
    Yanıt: { kelime, durum: "grid"|"bonus"|"gecersiz", puan_kazanildi }

    Puanlama (KELIME_GEZMECE özel kuralı): grid kelimesi +10, bonus kelime +15.
    Kelime havuzunun tamamı istemciye verilmez; doğrulama burada yapılır.
    Yetki: giriş yapmış herhangi bir kullanıcı (öğrenci/öğretmen/admin).
    """
    icerik_id = data.get("icerik_id")
    harf_sirasi = data.get("harf_sirasi") or []
    if not icerik_id:
        raise HTTPException(status_code=400, detail="icerik_id gerekli")
    if not isinstance(harf_sirasi, list) or not harf_sirasi:
        raise HTTPException(status_code=400, detail="harf_sirasi (liste) gerekli")

    icerik_doc = await db.egzersiz_icerikler.find_one({"id": icerik_id})
    if not icerik_doc:
        raise HTTPException(status_code=404, detail="İçerik bulunamadı")
    if icerik_doc.get("tip") != "kelime_gezmece":
        raise HTTPException(status_code=400, detail="İçerik Kelime Gezmece türünde değil")

    icerik = icerik_doc.get("icerik", {})
    sinif = int(icerik_doc.get("sinif", 3))
    kelime = "".join(str(h) for h in harf_sirasi)
    durum, puan = kelime_dogrula(icerik, kelime, sinif)
    return {"kelime": kelime, "durum": durum, "puan_kazanildi": puan}


@router.post("/egzersiz/kelime-gezmece/seviye")
async def kelime_gezmece_seviye(data: dict, current_user=Depends(get_current_user)):
    """Kelime Gezmece — belirli sınıf/seviye için bulmaca getirir veya üretir.

    Body: { sinif, seviye_no }
    Yanıt: { icerik_id, icerik, seviye_no }

    Cache: (sinif, seviye_no) kombinasyonu daha önce üretildiyse aynı içerik
    kullanılır (kullanim_sayisi += 1); yoksa bulmaca_olusturucu ile üretilip
    egzersiz_icerikler koleksiyonuna kaydedilir (kaynak="otomatik_uretim").
    """
    sinif = max(1, min(8, int(data.get("sinif", 3))))
    seviye_no = max(1, int(data.get("seviye_no", 1)))

    mevcut = await db.egzersiz_icerikler.find_one({
        "tip": "kelime_gezmece", "sinif": sinif,
        "icerik.seviye_no": seviye_no, **_AKTIF,
    })
    if mevcut:
        await db.egzersiz_icerikler.update_one(
            {"id": mevcut["id"]},
            {"$inc": {"kullanim_sayisi": 1},
             "$set": {"son_kullanim_tarihi": datetime.utcnow().isoformat()}},
        )
        return {"icerik_id": mevcut["id"], "icerik": mevcut.get("icerik", {}),
                "seviye_no": seviye_no}

    meb = await _meb_kelimeler(sinif)
    icerik = bulmaca_uret(sinif, seviye_no, meb_kelimeler=meb or None)
    olusturan = {
        "id": current_user.get("id"),
        "ad": _kullanici_ad(current_user),
        "rol": current_user.get("role", ""),
    }
    doc = await _icerik_kaydet("kelime_gezmece", sinif, None, None, icerik,
                              current_user.get("id"), False,
                              kaynak="otomatik_uretim", olusturan=olusturan)
    return {"icerik_id": doc["id"], "icerik": icerik, "seviye_no": seviye_no}


@router.post("/egzersiz/kelime-gezmece/tamamla")
async def kelime_gezmece_tamamla(data: dict, current_user=Depends(get_current_user)):
    """Kelime Gezmece — çok seviyeli oturumu bitirir, XP + puanı sıralamaya işler.

    Body: { sinif, seviye_sayisi, bonus_sayisi, toplam_puan, en_yuksek_seviye?, sure_sn? }
    XP kuralı: tamamlanan her seviye +50 XP, her bonus kelime +15 XP.
    (Yarım kalan seviye sayılmaz — frontend yalnızca tamamlanan seviyeleri iletir.)
    """
    sinif = max(1, min(8, int(data.get("sinif", 3))))
    seviye_sayisi = max(0, int(data.get("seviye_sayisi", 0)))
    bonus_sayisi = max(0, int(data.get("bonus_sayisi", 0)))
    toplam_puan = max(0, int(data.get("toplam_puan", 0)))
    en_yuksek_seviye = max(seviye_sayisi, int(data.get("en_yuksek_seviye", seviye_sayisi)))
    sure_sn = int(data.get("sure_sn", 0))

    xp = seviye_sayisi * 50 + bonus_sayisi * 15
    ogrenci_id = _ogrenci_id(current_user)
    now = datetime.utcnow().isoformat()

    oturum = {
        "id": str(uuid.uuid4()),
        "ogrenci_id": ogrenci_id,
        "tip": "kelime_gezmece",
        "icerik_id": None,
        "cevaplar": [],
        "dogru_sayisi": seviye_sayisi,
        "toplam_soru": max(1, seviye_sayisi),
        "seviye_sayisi": seviye_sayisi,
        "bonus_sayisi": bonus_sayisi,
        "en_yuksek_seviye": en_yuksek_seviye,
        "sure_sn": sure_sn,
        "puan": toplam_puan,
        "xp": xp,
        "durum": "tamamlandi",
        "baslama_t": now,
        "bitis_t": now,
    }
    await db.egzersiz_oturumlari.insert_one(dict(oturum))

    if xp > 0 and ogrenci_id:
        await db.students.update_one({"id": ogrenci_id}, {"$inc": {"toplam_xp": xp}})
        await db.xp_logs.insert_one({
            "id": str(uuid.uuid4()),
            "ogrenci_id": ogrenci_id,
            "eylem": "egzersiz_kelime_gezmece",
            "xp": xp,
            "tarih": now,
        })

    return {
        "xp": xp,
        "seviye_sayisi": seviye_sayisi,
        "bonus_sayisi": bonus_sayisi,
        "toplam_puan": toplam_puan,
        "en_yuksek_seviye": en_yuksek_seviye,
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


# ─────────────────────────────────────────────
# Kütüphane endpoint'leri (öğretmen/koordinatör/admin)
# ─────────────────────────────────────────────
_KUTUPHANE_YETKI = require_role(UserRole.ADMIN, UserRole.COORDINATOR, UserRole.TEACHER)


@router.get("/egzersiz/icerikler")
async def egzersiz_icerikler(
    tip: str | None = Query(None),
    sinif: int | None = Query(None),
    durum: str = Query("aktif"),
    sayfa: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user=Depends(_KUTUPHANE_YETKI),
):
    """Kalıcı içerik kütüphanesi — sayfalı liste (öğretmen/koordinatör/admin).

    durum: "aktif" (varsayılan) | "arsivli" | "hepsi".
    """
    sorgu: dict = {}
    if tip:
        sorgu["tip"] = tip
    if sinif is not None:
        sorgu["sinif"] = sinif
    if durum == "aktif":
        sorgu.update(_AKTIF)
    elif durum and durum != "hepsi":
        sorgu["durum"] = durum

    toplam = await db.egzersiz_icerikler.count_documents(sorgu)
    atla = (sayfa - 1) * limit
    docs = await db.egzersiz_icerikler.find(sorgu).sort(
        "olusturma_tarihi", -1
    ).skip(atla).limit(limit).to_list(length=limit)

    return {
        "icerikler": [_ozet_kayit(d) for d in docs],
        "toplam": toplam,
        "sayfa": sayfa,
        "limit": limit,
        "sayfa_sayisi": max(1, -(-toplam // limit)),  # ceil
    }


@router.get("/egzersiz/icerik/{icerik_id}")
async def egzersiz_icerik_detay(icerik_id: str, current_user=Depends(_KUTUPHANE_YETKI)):
    """Tek içeriğin tam detayı + aynı varyant grubundaki kardeşleri (önizleme)."""
    doc = await db.egzersiz_icerikler.find_one({"id": icerik_id})
    if not doc:
        raise HTTPException(status_code=404, detail="İçerik bulunamadı")

    grup = doc.get("varyant_grubu") or doc["id"]
    kardesler = await db.egzersiz_icerikler.find(
        {"$or": [{"varyant_grubu": grup}, {"id": icerik_id}]}
    ).sort("olusturma_tarihi", -1).to_list(length=50)

    kardes_ozet = [{
        "id": k.get("id"),
        "ozet": _icerik_ozet(k.get("icerik", {})),
        "durum": k.get("durum", "aktif"),
        "kullanim_sayisi": k.get("kullanim_sayisi", 0),
        "olusturma_tarihi": k.get("olusturma_tarihi"),
        "kendisi": k.get("id") == icerik_id,
    } for k in kardesler]

    meta = tip_meta(doc.get("tip", "")) or {}
    return {
        **_temizle(doc),
        "tip_ad": meta.get("ad", doc.get("tip")),
        "ikon": meta.get("ikon", "📝"),
        "puanlama": meta.get("puanlama", "secmeli"),
        "varyant_sayisi": len(kardes_ozet),
        "kardesler": kardes_ozet,
    }


@router.post("/egzersiz/icerik/{icerik_id}/varyant-uret")
async def egzersiz_varyant_uret(icerik_id: str, current_user=Depends(_KUTUPHANE_YETKI)):
    """Mevcut içeriğin YENİ bir varyantını AI ile üretir.

    Eski içerik ARŞİVLENMEZ — "aktif" kalır. Yeni içerik aynı varyant grubuna
    eklenir; böylece kütüphanede gruplanır.
    """
    eski = await db.egzersiz_icerikler.find_one({"id": icerik_id})
    if not eski:
        raise HTTPException(status_code=404, detail="İçerik bulunamadı")

    tip = eski["tip"]
    sinif = int(eski.get("sinif", 3))
    konu = eski.get("konu") or None
    zorluk = eski.get("zorluk") or None
    grup = eski.get("varyant_grubu") or eski["id"]

    icerik, mock = await _icerik_uret(tip, sinif, konu, zorluk)
    olusturan = {
        "id": current_user.get("id"),
        "ad": _kullanici_ad(current_user),
        "rol": current_user.get("role", ""),
    }
    yeni = await _icerik_kaydet(tip, sinif, konu, zorluk, icerik, current_user.get("id"),
                                mock, kaynak="ai_uretim", olusturan=olusturan,
                                varyant_grubu=grup)
    return {**_temizle(yeni), "varyant_uretildi": True}


@router.patch("/egzersiz/icerik/{icerik_id}/arsivle")
async def egzersiz_arsivle(icerik_id: str, current_user=Depends(require_role(UserRole.ADMIN))):
    """İçeriği arşivler (durum="arsivli"). Yalnızca admin. Kayıt DB'de kalır;
    oturum çekiminde artık gelmez."""
    res = await db.egzersiz_icerikler.update_one(
        {"id": icerik_id}, {"$set": {"durum": "arsivli"}}
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="İçerik bulunamadı")
    return {"id": icerik_id, "durum": "arsivli"}


@router.delete("/egzersiz/icerik/{icerik_id}")
async def egzersiz_icerik_sil(icerik_id: str, current_user=Depends(require_role(UserRole.ADMIN))):
    """İçeriği kalıcı siler (hard delete). Yalnızca admin; nadir kullanılır.
    Genelde arşivleme tercih edilmelidir."""
    res = await db.egzersiz_icerikler.delete_one({"id": icerik_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="İçerik bulunamadı")
    return {"id": icerik_id, "silindi": True}
