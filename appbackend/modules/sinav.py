"""Sınav Modülü — LGS/Bursluluk soru bankası + içe aktarım + admin onay + AI taktik.

Mimari kardeşleri: `meb_kelime.py` (içe aktarım/taslak-onay deseni),
`diagnostic.py` (base64-in-DB görsel serve deseni), `timi.py` (görsel-ağırlıklı
modül iskeleti). DB/kimlik/AI erişimi daima `core.*` üzerinden.

Akış (yarı-otomatik — TAM OTOMATİK YAYINLAMA YOK):
  yukle (PDF→pipeline, her soru "taslak" kaydedilir) → admin taslaklar ekranında
  görsel/metin karşılaştırıp düzeltir, gosterimTuru/konu/zorluk/cozumTaktigi
  doldurur → yayinla. `cozumTaktigi` PDF'te yok; admin (opsiyonel AI önerisiyle)
  doldurur. AI çıktısı asla otomatik yayınlanmaz.

Koleksiyonlar:
  db.sinav_sorulari   — soru bankası (taslak/yayinda/arsivli)
  db.sinav_cevaplari  — öğrenci cevapları (öğrenci çözüm arayüzü; task 5)
Ödev ataması ayrı collection açmaz; mevcut Görevler modülüne tur="sinav_odevi"
+ icerik_id ile bağlanır (task 4).
"""
import base64
import random
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from fastapi.responses import Response

from core.db import db
from core.auth import get_current_user, require_role, UserRole
from core.ai import _gemini_call_multimodal
from modules.sinav_parser import (
    parse_sinav_pdf, DERS_ETIKET, DERS_SIRASI, ATLANAN_DERSLER,
)

router = APIRouter()

# ── Yetki bağımlılıkları ──
_YAZMA = require_role(UserRole.ADMIN, UserRole.COORDINATOR)               # yükle/yayınla/sil
_OKUMA = require_role(UserRole.ADMIN, UserRole.COORDINATOR, UserRole.TEACHER)  # liste/düzenle

# ── Sabitler ──
MAX_PDF_BYTE = 25 * 1024 * 1024
SINAV_TURLERI = ["LGS", "bursluluk"]
ZORLUKLAR = ["kolay", "orta", "zor"]
GOSTERIM_TURLERI = ["metin", "gorsel"]
# Aktif dersler (İngilizce parser tarafında atlanır; enum genişletilebilir)
AKTIF_DERSLER = [d for d in DERS_SIRASI if d not in ATLANAN_DERSLER]

# PUT ile güncellenebilir alanlar (soruNo/kaynak izlenebilirlik dışı tutulur)
_DUZENLENEBILIR = {
    "ders", "soruMetni", "secenekler", "dogruCevap", "konu", "zorluk",
    "gosterimTuru", "cozumTaktigi", "sinifSeviyesi", "ekGorseller",
}
# Liste yanıtından çıkarılan ağır alanlar
_HAFIF_PROJ = {"soruBolgeGorseli_b64": 0, "_id": 0}


def _temizle(doc: dict) -> dict:
    """Mongo _id + ağır görseli dışarı vermeden döndürülecek kopya."""
    if not doc:
        return doc
    d = dict(doc)
    d.pop("_id", None)
    d.pop("soruBolgeGorseli_b64", None)
    d["gorselVar"] = bool(doc.get("soruBolgeGorseli_b64"))
    return d


def _ad(u: dict) -> str:
    return f"{u.get('ad', '')} {u.get('soyad', '')}".strip() or "Yönetici"


# ── 1) İÇE AKTARIM ────────────────────────────────────────────────────────
@router.post("/sinav/yukle")
async def sinav_yukle(
    dosya: UploadFile = File(...),
    sinavTuru: str = Form("LGS"),
    yil: int = Form(...),
    sinifSeviyesi: int = Form(8),
    current_user=Depends(_YAZMA),
):
    """PDF'i ayrıştırır ve her soruyu 'taslak' olarak kaydeder (yarı-otomatik).

    Dönüş: {grup_id, olusturulan, istatistik, uyarilar, kitapcikTuru}
    """
    if sinavTuru not in SINAV_TURLERI:
        raise HTTPException(status_code=400, detail="Geçersiz sınav türü.")
    ad = (dosya.filename or "").lower()
    if not ad.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Şimdilik yalnızca PDF desteklenir.")
    icerik = await dosya.read()
    if len(icerik) > MAX_PDF_BYTE:
        raise HTTPException(status_code=400, detail="PDF en fazla 25MB olabilir.")

    try:
        sonuc = parse_sinav_pdf(icerik)
    except Exception as ex:
        raise HTTPException(status_code=400, detail=f"PDF ayrıştırılamadı: {ex}")

    sorular = sonuc.get("sorular") or []
    if not sorular:
        raise HTTPException(status_code=400, detail="PDF'te soru bulunamadı.")

    grup_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    kaynak = dosya.filename or ""
    yazan_ad = _ad(current_user)
    kayitlar = []
    for s in sorular:
        kayitlar.append({
            "id": str(uuid.uuid4()),
            "grup_id": grup_id,
            "ders": s["ders"],
            "sinavTuru": sinavTuru,
            "yil": int(yil),
            "kitapcikTuru": sonuc.get("kitapcikTuru", "A"),
            "soruNo": s["soruNo"],
            "sinifSeviyesi": int(sinifSeviyesi),
            "konu": "",
            "zorluk": None,
            "soruMetni": s.get("soruMetni", ""),
            "secenekler": s.get("secenekler", {}),
            "dogruCevap": s.get("dogruCevap"),
            "gosterimTuru": s.get("gosterimTuru", "gorsel"),
            "ekGorseller": [],
            "cozumTaktigi": "",
            "soruBolgeGorseli_b64": s.get("soruBolgeGorseli_b64", ""),
            "gorsel_mime": "image/png",
            "kaynakDosya": kaynak,
            "durum": "taslak",
            "olusturan_id": current_user.get("id"),
            "olusturan_ad": yazan_ad,
            "olusturma_tarihi": now,
            "guncelleme_tarihi": now,
            "kullanim_sayisi": 0,
        })
    if kayitlar:
        await db.sinav_sorulari.insert_many(kayitlar)

    return {
        "grup_id": grup_id,
        "olusturulan": len(kayitlar),
        "kitapcikTuru": sonuc.get("kitapcikTuru", "A"),
        "istatistik": sonuc.get("istatistik", {}),
        "uyarilar": sonuc.get("uyarilar", []),
    }


# ── 2) TASLAK / LİSTE ─────────────────────────────────────────────────────
@router.get("/sinav/taslaklar")
async def sinav_taslaklar(
    grup_id: Optional[str] = Query(None),
    ders: Optional[str] = Query(None),
    durum: Optional[str] = Query(None),
    sayfa: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    current_user=Depends(_OKUMA),
):
    """Soruları (görsel hariç, hafif) filtreli+sayfalı listeler."""
    q = {}
    if grup_id:
        q["grup_id"] = grup_id
    if ders:
        q["ders"] = ders
    q["durum"] = durum if durum else {"$ne": "arsivli"}

    toplam = await db.sinav_sorulari.count_documents(q)
    docs = await (
        db.sinav_sorulari.find(q, _HAFIF_PROJ)
        .sort([("ders", 1), ("soruNo", 1)])
        .skip((sayfa - 1) * limit)
        .limit(limit)
        .to_list(length=limit)
    )
    for d in docs:
        d["gorselVar"] = True  # projeksiyon görseli çıkardı; tüm sorularda mevcut
    return {
        "sorular": docs,
        "toplam": toplam,
        "sayfa": sayfa,
        "limit": limit,
        "sayfa_sayisi": -(-toplam // limit),
    }


@router.get("/sinav/gruplar")
async def sinav_gruplar(current_user=Depends(_OKUMA)):
    """Yüklenmiş PDF gruplarını (parti) özetler."""
    pipeline = [
        {"$match": {"durum": {"$ne": "arsivli"}}},
        {"$group": {
            "_id": "$grup_id",
            "kaynakDosya": {"$first": "$kaynakDosya"},
            "sinavTuru": {"$first": "$sinavTuru"},
            "yil": {"$first": "$yil"},
            "kitapcikTuru": {"$first": "$kitapcikTuru"},
            "olusturma_tarihi": {"$first": "$olusturma_tarihi"},
            "toplam": {"$sum": 1},
            "taslak": {"$sum": {"$cond": [{"$eq": ["$durum", "taslak"]}, 1, 0]}},
            "yayinda": {"$sum": {"$cond": [{"$eq": ["$durum", "yayinda"]}, 1, 0]}},
        }},
        {"$sort": {"olusturma_tarihi": -1}},
    ]
    gruplar = await db.sinav_sorulari.aggregate(pipeline).to_list(length=None)
    for g in gruplar:
        g["grup_id"] = g.pop("_id")
    return {"gruplar": gruplar}


@router.get("/sinav/soru/{soru_id}")
async def sinav_soru_getir(soru_id: str, current_user=Depends(_OKUMA)):
    """Tek sorunun tüm alanları (görsel hariç; görsel ayrı endpoint'ten)."""
    doc = await db.sinav_sorulari.find_one({"id": soru_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Soru bulunamadı.")
    return _temizle(doc)


@router.get("/sinav/soru/{soru_id}/gorsel")
async def sinav_soru_gorsel(soru_id: str, current_user=Depends(get_current_user)):
    """Kırpılmış orijinal soru PNG'sini binary döner (<img src> için)."""
    doc = await db.sinav_sorulari.find_one({"id": soru_id}, {"soruBolgeGorseli_b64": 1, "gorsel_mime": 1})
    b64 = (doc or {}).get("soruBolgeGorseli_b64")
    if not b64:
        raise HTTPException(status_code=404, detail="Görsel yok.")
    try:
        ham = base64.b64decode(b64)
    except Exception:
        raise HTTPException(status_code=500, detail="Görsel çözülemedi.")
    return Response(content=ham, media_type=(doc or {}).get("gorsel_mime", "image/png"))


# ── 3) DÜZENLEME / YAYIN / SİLME ──────────────────────────────────────────
@router.put("/sinav/soru/{soru_id}")
async def sinav_soru_guncelle(soru_id: str, data: dict, current_user=Depends(_OKUMA)):
    """Admin taslağı düzeltir (metin/seçenek/cevap/konu/zorluk/gosterim/taktik)."""
    doc = await db.sinav_sorulari.find_one({"id": soru_id}, {"_id": 0, "durum": 1})
    if not doc:
        raise HTTPException(status_code=404, detail="Soru bulunamadı.")
    guncelle = {k: v for k, v in data.items() if k in _DUZENLENEBILIR}
    if not guncelle:
        raise HTTPException(status_code=400, detail="Güncellenecek geçerli alan yok.")
    # doğrulamalar
    if "dogruCevap" in guncelle and guncelle["dogruCevap"] not in ("A", "B", "C", "D", None):
        raise HTTPException(status_code=400, detail="dogruCevap A/B/C/D olmalı.")
    if "zorluk" in guncelle and guncelle["zorluk"] not in (ZORLUKLAR + [None]):
        raise HTTPException(status_code=400, detail="Geçersiz zorluk.")
    if "gosterimTuru" in guncelle and guncelle["gosterimTuru"] not in GOSTERIM_TURLERI:
        raise HTTPException(status_code=400, detail="Geçersiz gösterim türü.")
    if "ders" in guncelle and guncelle["ders"] not in AKTIF_DERSLER:
        raise HTTPException(status_code=400, detail="Geçersiz ders.")
    guncelle["guncelleme_tarihi"] = datetime.now(timezone.utc).isoformat()
    await db.sinav_sorulari.update_one({"id": soru_id}, {"$set": guncelle})
    yeni = await db.sinav_sorulari.find_one({"id": soru_id})
    return _temizle(yeni)


@router.post("/sinav/soru/{soru_id}/yayinla")
async def sinav_soru_yayinla(soru_id: str, current_user=Depends(_YAZMA)):
    """Taslağı yayına alır — doğru cevap zorunlu (öğrenciye gösterim için)."""
    doc = await db.sinav_sorulari.find_one({"id": soru_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Soru bulunamadı.")
    if not doc.get("dogruCevap"):
        raise HTTPException(status_code=400, detail="Doğru cevap boş — yayınlanamaz.")
    if doc.get("gosterimTuru") == "metin" and not doc.get("soruMetni"):
        raise HTTPException(status_code=400, detail="Metin gösterimi için soru metni gerekli.")
    await db.sinav_sorulari.update_one(
        {"id": soru_id},
        {"$set": {"durum": "yayinda", "guncelleme_tarihi": datetime.now(timezone.utc).isoformat()}},
    )
    return {"ok": True, "durum": "yayinda"}


@router.post("/sinav/grup/{grup_id}/yayinla")
async def sinav_grup_yayinla(grup_id: str, current_user=Depends(_YAZMA)):
    """Bir gruptaki, doğru cevabı olan tüm taslakları toplu yayınlar."""
    q = {"grup_id": grup_id, "durum": "taslak", "dogruCevap": {"$nin": [None, ""]}}
    res = await db.sinav_sorulari.update_many(
        q, {"$set": {"durum": "yayinda", "guncelleme_tarihi": datetime.now(timezone.utc).isoformat()}},
    )
    return {"ok": True, "yayinlanan": res.modified_count}


@router.delete("/sinav/soru/{soru_id}")
async def sinav_soru_sil(soru_id: str, current_user=Depends(_YAZMA)):
    """Soft-delete → durum='arsivli'."""
    res = await db.sinav_sorulari.update_one(
        {"id": soru_id}, {"$set": {"durum": "arsivli"}}
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Soru bulunamadı.")
    return {"ok": True}


# ── 4) AI ÇÖZÜM TAKTİĞİ ÖNERİSİ (multimodal) ──────────────────────────────
@router.post("/sinav/soru/{soru_id}/ai-taktik")
async def sinav_ai_taktik(soru_id: str, current_user=Depends(_OKUMA)):
    """Soru görüntüsü + doğru cevap → taslak çözüm taktiği üretir (kaydetmez).

    Admin dönen metni düzenleyip PUT ile kaydeder; AI çıktısı otomatik
    yayınlanmaz.
    """
    doc = await db.sinav_sorulari.find_one({"id": soru_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Soru bulunamadı.")
    b64 = doc.get("soruBolgeGorseli_b64")
    if not b64:
        raise HTTPException(status_code=400, detail="Soru görseli yok.")

    ders_ad = DERS_ETIKET.get(doc.get("ders", ""), doc.get("ders", ""))
    konu = doc.get("konu") or "belirtilmemiş"
    dogru = doc.get("dogruCevap") or "?"
    system = (
        "Sen deneyimli bir LGS/bursluluk sınavı hazırlık öğretmenisin. Görseldeki "
        "çoktan seçmeli soruyu incele ve öğrenciye 'çözüm taktiği' yaz. Amaç 'doğru "
        "cevap X' demek DEĞİL; bu tür soruların NASIL çözüleceğini, önce neye "
        "bakılacağını, hangi tuzaklardan kaçınılacağını öğretmek. Kısa (3-5 cümle), "
        "sade, öğrenci diliyle yaz. Sadece taktiği yaz; başlık/again ekleme."
    )
    prompt = (
        f"Ders: {ders_ad}\nKonu: {konu}\nDoğru cevap: {dogru}\n\n"
        f"Bu sorunun çözüm taktiğini yaz."
    )
    try:
        metin = await _gemini_call_multimodal(prompt, [("image/png", b64)], system=system, max_tokens=800)
    except Exception as ex:
        raise HTTPException(status_code=502, detail=f"AI önerisi üretilemedi: {ex}")
    return {"cozumTaktigi_oneri": (metin or "").strip()}


# ── 5) YARDIMCI / META ────────────────────────────────────────────────────
@router.get("/sinav/dersler")
async def sinav_dersler(current_user=Depends(get_current_user)):
    """Enum verisi — ders/sınavTürü/zorluk/gösterim (frontend dropdown)."""
    return {
        "dersler": [{"key": d, "ad": DERS_ETIKET.get(d, d)} for d in AKTIF_DERSLER],
        "sinavTurleri": SINAV_TURLERI,
        "zorluklar": ZORLUKLAR,
        "gosterimTurleri": GOSTERIM_TURLERI,
    }


@router.get("/sinav/istatistik")
async def sinav_istatistik(current_user=Depends(_OKUMA)):
    """Durum/ders bazlı sayımlar."""
    pipeline = [
        {"$match": {"durum": {"$ne": "arsivli"}}},
        {"$group": {"_id": {"ders": "$ders", "durum": "$durum"}, "n": {"$sum": 1}}},
    ]
    rows = await db.sinav_sorulari.aggregate(pipeline).to_list(length=None)
    ozet = {}
    for r in rows:
        ders = r["_id"]["ders"]
        ozet.setdefault(ders, {"taslak": 0, "yayinda": 0})
        ozet[ders][r["_id"]["durum"]] = r["n"]
    toplam_taslak = sum(v.get("taslak", 0) for v in ozet.values())
    toplam_yayinda = sum(v.get("yayinda", 0) for v in ozet.values())
    return {"ders_bazli": ozet, "toplam_taslak": toplam_taslak, "toplam_yayinda": toplam_yayinda}


# ── 6) ÖĞRETMEN: YAYINDAKİ SORULAR + OTOMATİK SEÇİM + ÖDEV TANIMI ──────────
@router.get("/sinav/yayinda")
async def sinav_yayinda(
    ders: Optional[str] = Query(None),
    konu: Optional[str] = Query(None),
    zorluk: Optional[str] = Query(None),
    sinavTuru: Optional[str] = Query(None),
    sayfa: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    current_user=Depends(_OKUMA),
):
    """Öğretmen: yayındaki soruları filtreli listeler (elle ödev seçimi için)."""
    q = {"durum": "yayinda"}
    if ders:
        q["ders"] = ders
    if konu:
        q["konu"] = konu
    if zorluk:
        q["zorluk"] = zorluk
    if sinavTuru:
        q["sinavTuru"] = sinavTuru
    toplam = await db.sinav_sorulari.count_documents(q)
    docs = await (
        db.sinav_sorulari.find(q, _HAFIF_PROJ)
        .sort([("ders", 1), ("soruNo", 1)])
        .skip((sayfa - 1) * limit)
        .limit(limit)
        .to_list(length=limit)
    )
    for d in docs:
        d["gorselVar"] = True
    return {"sorular": docs, "toplam": toplam, "sayfa": sayfa, "limit": limit,
            "sayfa_sayisi": -(-toplam // limit)}


async def _otomatik_soru_sec(ders: str, soruSayisi: int, konu: Optional[str] = None,
                             zorluk: Optional[str] = None) -> list:
    """Kritere uyan yayındaki sorulardan rastgele soruSayisi kadar id seçer."""
    q = {"durum": "yayinda", "ders": ders}
    if konu:
        q["konu"] = konu
    if zorluk:
        q["zorluk"] = zorluk
    havuz = await db.sinav_sorulari.find(q, {"id": 1, "_id": 0}).to_list(length=None)
    idler = [d["id"] for d in havuz]
    random.shuffle(idler)
    return idler[:max(0, soruSayisi)]


@router.post("/sinav/otomatik-sec")
async def sinav_otomatik_sec(data: dict, current_user=Depends(_OKUMA)):
    """Kriter → dengeli/rastgele soru id listesi (önizleme; ödev oluşturmaz)."""
    ders = data.get("ders")
    if ders not in AKTIF_DERSLER:
        raise HTTPException(status_code=400, detail="Geçerli bir ders seçin.")
    sayi = int(data.get("soruSayisi", 10))
    idler = await _otomatik_soru_sec(ders, sayi, data.get("konu"), data.get("zorluk"))
    return {"soruIds": idler, "bulunan": len(idler), "istenen": sayi}


@router.post("/sinav/odev")
async def sinav_odev_olustur(data: dict, current_user=Depends(_OKUMA)):
    """Sınav ödevi tanımı oluşturur (soru seti). Görevler'e icerik_id ile bağlanır.

    Body: {ad?, soruIds?[], otomatikKriter?{ders,konu?,zorluk?,soruSayisi}}
    Dönüş: {odev_id, ad, soruSayisi}
    """
    soru_ids = data.get("soruIds") or []
    kriter = data.get("otomatikKriter") or None

    if not soru_ids and kriter:
        ders = kriter.get("ders")
        if ders not in AKTIF_DERSLER:
            raise HTTPException(status_code=400, detail="Otomatik kriterde geçerli ders yok.")
        soru_ids = await _otomatik_soru_sec(
            ders, int(kriter.get("soruSayisi", 10)), kriter.get("konu"), kriter.get("zorluk")
        )

    if not soru_ids:
        raise HTTPException(status_code=400, detail="Soru seçilmedi.")
    # yalnızca yayındaki soruları kabul et (sıra korunur)
    gecerli = await db.sinav_sorulari.find(
        {"id": {"$in": soru_ids}, "durum": "yayinda"}, {"id": 1, "_id": 0}
    ).to_list(length=None)
    gecerli_set = {d["id"] for d in gecerli}
    temiz = [sid for sid in soru_ids if sid in gecerli_set]
    if not temiz:
        raise HTTPException(status_code=400, detail="Seçilen sorular yayında değil.")

    odev_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    await db.sinav_odevleri.insert_one({
        "id": odev_id,
        "ad": (data.get("ad") or "Sınav Ödevi").strip(),
        "soruIds": temiz,
        "otomatikKriter": kriter,
        "soruSayisi": len(temiz),
        "olusturan_id": current_user.get("id"),
        "olusturan_ad": _ad(current_user),
        "olusturma_tarihi": now,
    })
    return {"odev_id": odev_id, "ad": data.get("ad") or "Sınav Ödevi", "soruSayisi": len(temiz)}


@router.get("/sinav/odev/{odev_id}/ozet")
async def sinav_odev_ozet(odev_id: str, current_user=Depends(get_current_user)):
    """Ödev meta bilgisi (görev kartında gösterim için)."""
    o = await db.sinav_odevleri.find_one({"id": odev_id}, {"_id": 0})
    if not o:
        raise HTTPException(status_code=404, detail="Sınav ödevi bulunamadı.")
    return o


# ── 7) ÖĞRENCİ: ÇÖZÜM ARAYÜZÜ ─────────────────────────────────────────────
def _ogrenci_id(u: dict) -> str:
    """Öğrenci user hesabı → students kaydı (linked_id) veya kendi id'si."""
    return u.get("linked_id") or u.get("id")


@router.get("/sinav/odev/{odev_id}/sorular")
async def sinav_odev_sorular(odev_id: str, current_user=Depends(get_current_user)):
    """Öğrenci çözümü için ödev sorularını döner — DOĞRU CEVAP/TAKTİK SIZDIRMAZ.

    Cevap ve çözüm taktiği yalnızca /sinav/cevap yanıtında (cevaplandıktan sonra)
    verilir; böylece önceden 'gözetleme' engellenir.
    """
    o = await db.sinav_odevleri.find_one({"id": odev_id}, {"_id": 0})
    if not o:
        raise HTTPException(status_code=404, detail="Sınav ödevi bulunamadı.")
    idler = o.get("soruIds") or []
    proj = {"_id": 0, "soruBolgeGorseli_b64": 0, "dogruCevap": 0, "cozumTaktigi": 0}
    docs = await db.sinav_sorulari.find({"id": {"$in": idler}}, proj).to_list(length=None)
    sirali = {d["id"]: d for d in docs}
    sorular = []
    for sid in idler:  # ödevdeki sırayı koru
        d = sirali.get(sid)
        if d:
            d["gorselVar"] = True
            sorular.append(d)
    # öğrencinin daha önce verdiği cevaplar (kaldığı yerden devam / tekrar)
    ogr = _ogrenci_id(current_user)
    onceki = await db.sinav_cevaplari.find(
        {"odevId": odev_id, "ogrenciId": ogr}, {"_id": 0, "soruId": 1, "verilenCevap": 1, "dogruMu": 1}
    ).to_list(length=None)
    return {"odev": {"id": o["id"], "ad": o.get("ad"), "soruSayisi": len(sorular)},
            "sorular": sorular, "verilenler": onceki}


@router.post("/sinav/cevap")
async def sinav_cevap_ver(data: dict, current_user=Depends(get_current_user)):
    """Öğrenci cevabı kaydeder ve ANINDA doğru cevap + çözüm taktiği döner.

    Body: {odevId, soruId, verilenCevap: A-D, harcananSure?}
    """
    odev_id = data.get("odevId")
    soru_id = data.get("soruId")
    verilen = data.get("verilenCevap")
    if verilen not in ("A", "B", "C", "D"):
        raise HTTPException(status_code=400, detail="verilenCevap A/B/C/D olmalı.")
    odev = await db.sinav_odevleri.find_one({"id": odev_id}, {"_id": 0, "soruIds": 1})
    if not odev or soru_id not in (odev.get("soruIds") or []):
        raise HTTPException(status_code=404, detail="Soru bu ödevde bulunamadı.")
    soru = await db.sinav_sorulari.find_one({"id": soru_id}, {"_id": 0, "dogruCevap": 1, "cozumTaktigi": 1})
    if not soru:
        raise HTTPException(status_code=404, detail="Soru bulunamadı.")

    dogru = soru.get("dogruCevap")
    dogru_mu = (verilen == dogru)
    ogr = _ogrenci_id(current_user)
    now = datetime.now(timezone.utc).isoformat()
    # (odev, öğrenci, soru) tekil — tekrar cevaplama günceller
    await db.sinav_cevaplari.update_one(
        {"odevId": odev_id, "ogrenciId": ogr, "soruId": soru_id},
        {"$set": {
            "verilenCevap": verilen, "dogruMu": dogru_mu,
            "harcananSure": data.get("harcananSure"), "cevaplanmaTarihi": now,
        }, "$setOnInsert": {"id": str(uuid.uuid4())}},
        upsert=True,
    )
    await db.sinav_sorulari.update_one({"id": soru_id}, {"$inc": {"kullanim_sayisi": 1}})
    return {"dogruMu": dogru_mu, "dogruCevap": dogru, "cozumTaktigi": soru.get("cozumTaktigi") or ""}


# ── 8) ÖĞRETMEN: SONUÇ + KONU BAZLI KIRILIM ───────────────────────────────
@router.get("/sinav/odev/{odev_id}/sonuc")
async def sinav_odev_sonuc(odev_id: str, current_user=Depends(_OKUMA)):
    """Ödev sonucu: öğrenci bazlı skor + konu bazlı kırılım (zayıf-alan tespiti)."""
    odev = await db.sinav_odevleri.find_one({"id": odev_id}, {"_id": 0, "soruIds": 1, "ad": 1})
    if not odev:
        raise HTTPException(status_code=404, detail="Sınav ödevi bulunamadı.")
    soru_ids = odev.get("soruIds") or []
    sorular = await db.sinav_sorulari.find(
        {"id": {"$in": soru_ids}}, {"_id": 0, "id": 1, "konu": 1, "ders": 1}
    ).to_list(length=None)
    konu_map = {s["id"]: (s.get("konu") or "Genel") for s in sorular}

    cevaplar = await db.sinav_cevaplari.find({"odevId": odev_id}, {"_id": 0}).to_list(length=None)
    ogr, konu = {}, {}
    genel_d = genel_t = 0
    for c in cevaplar:
        oid = c.get("ogrenciId")
        d = 1 if c.get("dogruMu") else 0
        ogr.setdefault(oid, {"dogru": 0, "toplam": 0})
        ogr[oid]["dogru"] += d
        ogr[oid]["toplam"] += 1
        k = konu_map.get(c.get("soruId"), "Genel")
        konu.setdefault(k, {"dogru": 0, "toplam": 0})
        konu[k]["dogru"] += d
        konu[k]["toplam"] += 1
        genel_d += d
        genel_t += 1

    oids = list(ogr.keys())
    students = await db.students.find(
        {"id": {"$in": oids}}, {"_id": 0, "id": 1, "ad": 1, "soyad": 1}
    ).to_list(length=None)
    ad_map = {s["id"]: f"{s.get('ad', '')} {s.get('soyad', '')}".strip() or "Öğrenci" for s in students}

    ogrenciler = [
        {"ogrenciId": oid, "ad": ad_map.get(oid, "Öğrenci"), "dogru": v["dogru"], "toplam": v["toplam"]}
        for oid, v in sorted(ogr.items(), key=lambda kv: -kv[1]["dogru"])
    ]
    konu_bazli = [
        {"konu": k, "dogru": v["dogru"], "toplam": v["toplam"]}
        for k, v in sorted(konu.items(), key=lambda kv: (kv[1]["dogru"] / kv[1]["toplam"]) if kv[1]["toplam"] else 0)
    ]
    return {
        "ad": odev.get("ad"),
        "soruSayisi": len(soru_ids),
        "cozenSayisi": len(oids),
        "genel": {"dogru": genel_d, "toplam": genel_t},
        "ogrenciler": ogrenciler,
        "konuBazli": konu_bazli,
    }
