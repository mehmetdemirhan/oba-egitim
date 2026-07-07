"""TIMI — Teele Çoklu Zeka Envanteri modülü (/timi/*).

Sue Teele (1992), Gardner Çoklu Zeka Kuramı'na dayalı 28 kart / 56 görselden oluşan
zorlamalı-seçim (forced-choice) envanteri. Öğretmen öğrenciyle karşılıklı oturup her
kartta iki görselden birini (A/B) işaretler; sistem 7 zeka kategorisine puanlar.

Giriş Analizi (modules/diagnostic.py) oturum akışının kardeşi: aynı roller
(admin/coordinator/teacher) uygular, aynı desenle oturum başlat → yanıt → tamamla.

Puanlama anahtarı `data/timi_scoring_key.json`'dan okunur (kendisi doğrulanmıştır;
yeniden türetilmez). Her kategori tam 8 kez görsel olarak görünür → alt-ölçek 0-8.
"""
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core.db import db
from core.auth import get_current_user

router = APIRouter()

KATKI_ROLLERI = ("admin", "coordinator", "teacher")

# ── Puanlama anahtarı (sabit) ──
_ANAHTAR_YOLU = Path(__file__).resolve().parent.parent / "data" / "timi_scoring_key.json"
with open(_ANAHTAR_YOLU, encoding="utf-8") as _f:
    SCORING_KEY = json.load(_f)

TOPLAM_KART = SCORING_KEY.get("total_cards", 28)
# {1: {"key": "dilsel", "tr": "..."}, ...}
KATEGORILER = SCORING_KEY["categories"]
# kategori no (int) → anahtar (dilsel, ...)
KATEGORI_NO_KEY = {int(no): c["key"] for no, c in KATEGORILER.items()}
# anahtarların sabit sırası (rapor/grafik ekseninde tutarlı)
KATEGORI_SIRA = [KATEGORI_NO_KEY[i] for i in sorted(KATEGORI_NO_KEY)]
# kart no → {"A": kategori_no, "B": kategori_no}
KART_MAP = {c["card"]: {"A": c["A_category"], "B": c["B_category"]} for c in SCORING_KEY["cards"]}


def timi_puanla(yanitlar: List[dict]) -> dict:
    """yanitlar [{kart_no, secim}] → {anahtar: puan} (7 kategori, 0-8)."""
    puan = {k: 0 for k in KATEGORI_SIRA}
    for y in yanitlar:
        kart = KART_MAP.get(y.get("kart_no"))
        if not kart:
            continue
        secim = (y.get("secim") or "").upper()
        if secim not in ("A", "B"):
            continue
        kat_no = kart[secim]
        anahtar = KATEGORI_NO_KEY.get(kat_no)
        if anahtar:
            puan[anahtar] += 1
    return puan


def baskin_alanlar(kategori_puanlari: dict) -> list:
    """En yüksek puanlı kategori(ler); eşitlik durumunda hepsi listelenir."""
    if not kategori_puanlari:
        return []
    en_yuksek = max(kategori_puanlari.values())
    if en_yuksek <= 0:
        return []
    return [k for k in KATEGORI_SIRA if kategori_puanlari.get(k, 0) == en_yuksek]


def _serialize(doc: dict) -> dict:
    doc = dict(doc)
    doc.pop("_id", None)
    return doc


# ── Meta (kategori adları + kart sayısı) — sonuç ekranı etiketleri için ──
@router.get("/timi/meta")
async def timi_meta(current_user=Depends(get_current_user)):
    return {
        "toplam_kart": TOPLAM_KART,
        "kategori_sira": KATEGORI_SIRA,
        "kategoriler": [
            {"no": int(no), "key": c["key"], "tr": c["tr"], "en": c.get("en", "")}
            for no, c in sorted(KATEGORILER.items(), key=lambda kv: int(kv[0]))
        ],
    }


# ── Oturum başlat ──
class TimiBaslat(BaseModel):
    ogrenci_id: str


@router.post("/timi/baslat")
async def timi_baslat(data: TimiBaslat, current_user=Depends(get_current_user)):
    if current_user.get("role") not in KATKI_ROLLERI:
        raise HTTPException(status_code=403, detail="Yetkisiz")
    ogrenci = await db.students.find_one({"id": data.ogrenci_id})
    if not ogrenci:
        raise HTTPException(status_code=404, detail="Öğrenci bulunamadı")
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "id": str(uuid.uuid4()),
        "ogrenci_id": data.ogrenci_id,
        "ogretmen_id": current_user["id"],
        "sinif_seviyesi": str(ogrenci.get("sinif", "") or ""),
        "yanitlar": [],
        "kategori_puanlari": {},
        "baskin_zeka_alanlari": [],
        "notlar": "",
        "durum": "devam",
        "uygulama_tarihi": None,
        "olusturma_tarihi": now,
        "guncelleme_tarihi": now,
    }
    await db.timi_sonuclar.insert_one(doc)
    return _serialize(doc)


# ── Yanıt işaretle (tek kart) ──
class TimiYanit(BaseModel):
    kart_no: int
    secim: str  # "A" | "B"


@router.patch("/timi/{sonuc_id}/yanit")
async def timi_yanit(sonuc_id: str, data: TimiYanit, current_user=Depends(get_current_user)):
    if current_user.get("role") not in KATKI_ROLLERI:
        raise HTTPException(status_code=403, detail="Yetkisiz")
    secim = (data.secim or "").upper()
    if not (1 <= data.kart_no <= TOPLAM_KART):
        raise HTTPException(status_code=400, detail=f"Geçersiz kart no (1-{TOPLAM_KART})")
    if secim not in ("A", "B"):
        raise HTTPException(status_code=400, detail="Seçim A veya B olmalı")

    doc = await db.timi_sonuclar.find_one({"id": sonuc_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Oturum bulunamadı")

    yanitlar = [y for y in (doc.get("yanitlar") or []) if y.get("kart_no") != data.kart_no]
    yanitlar.append({"kart_no": data.kart_no, "secim": secim})
    yanitlar.sort(key=lambda y: y["kart_no"])
    await db.timi_sonuclar.update_one(
        {"id": sonuc_id},
        {"$set": {"yanitlar": yanitlar, "guncelleme_tarihi": datetime.now(timezone.utc).isoformat()}},
    )
    return {"kart_no": data.kart_no, "secim": secim, "yanit_sayisi": len(yanitlar)}


# ── Tamamla (puanla) ──
class TimiTamamla(BaseModel):
    notlar: str = ""
    yanitlar: Optional[List[dict]] = None  # opsiyonel: tümünü tek seferde de gönderebilir


@router.post("/timi/{sonuc_id}/tamamla")
async def timi_tamamla(sonuc_id: str, data: TimiTamamla, current_user=Depends(get_current_user)):
    if current_user.get("role") not in KATKI_ROLLERI:
        raise HTTPException(status_code=403, detail="Yetkisiz")
    doc = await db.timi_sonuclar.find_one({"id": sonuc_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Oturum bulunamadı")

    # Yanıtlar: gövdede geldiyse onları kullan (normalize), yoksa kayıtlıları
    if data.yanitlar is not None:
        temiz = []
        for y in data.yanitlar:
            kn = y.get("kart_no")
            sc = (y.get("secim") or "").upper()
            if isinstance(kn, int) and 1 <= kn <= TOPLAM_KART and sc in ("A", "B"):
                temiz.append({"kart_no": kn, "secim": sc})
        # kart_no'ya göre tekilleştir
        by_no = {y["kart_no"]: y for y in temiz}
        yanitlar = [by_no[k] for k in sorted(by_no)]
    else:
        yanitlar = doc.get("yanitlar") or []

    if len(yanitlar) < TOPLAM_KART:
        raise HTTPException(
            status_code=400,
            detail=f"Tüm kartlar yanıtlanmalı ({len(yanitlar)}/{TOPLAM_KART})",
        )

    kategori_puanlari = timi_puanla(yanitlar)
    baskin = baskin_alanlar(kategori_puanlari)
    # Detay cevap tablosu için her yanıta seçilen kategoriyi ekle
    yanitlar_zengin = []
    for y in yanitlar:
        kart = KART_MAP.get(y["kart_no"], {})
        kat_no = kart.get(y["secim"])
        yanitlar_zengin.append({
            "kart_no": y["kart_no"],
            "secim": y["secim"],
            "kategori": KATEGORI_NO_KEY.get(kat_no) if kat_no else None,
        })
    now = datetime.now(timezone.utc).isoformat()
    guncelle = {
        "yanitlar": yanitlar_zengin,
        "kategori_puanlari": kategori_puanlari,
        "baskin_zeka_alanlari": baskin,
        "notlar": data.notlar,
        "durum": "tamamlandi",
        "uygulama_tarihi": now,
        "guncelleme_tarihi": now,
    }
    await db.timi_sonuclar.update_one({"id": sonuc_id}, {"$set": guncelle})
    yeni = await db.timi_sonuclar.find_one({"id": sonuc_id})
    return _serialize(yeni)


# ── Öğrencinin TIMI geçmişi ──
@router.get("/timi/ogrenci/{ogrenci_id}")
async def timi_ogrenci(ogrenci_id: str, current_user=Depends(get_current_user)):
    items = await db.timi_sonuclar.find({"ogrenci_id": ogrenci_id}).sort("olusturma_tarihi", -1).to_list(length=None)
    return [_serialize(i) for i in items]


# ── Tek oturum ──
@router.get("/timi/{sonuc_id}")
async def timi_getir(sonuc_id: str, current_user=Depends(get_current_user)):
    doc = await db.timi_sonuclar.find_one({"id": sonuc_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Oturum bulunamadı")
    return _serialize(doc)
