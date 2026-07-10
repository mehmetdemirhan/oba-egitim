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
