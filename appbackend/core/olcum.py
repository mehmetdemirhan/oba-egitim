# -*- coding: utf-8 -*-
"""Ölçüm Metinleri (bolum="olcum") toplu içe aktarım çekirdeği.

TEK KAYNAK: `data/olcum_metinleri.json` (scripts/olcum_import.py birleştirmesiyle
üretilir — PDF gövdeleri + alt-ajan/elle-doğrulanmış Bloom soruları). Hem CLI
script hem admin endpoint (POST /diagnostic/olcum-import) BURAYI kullanır ki
şema/ID tek yerde tanımlı olsun.

İçe aktarım ADMIN toplu işlemidir → durum="havuzda" (onaydan MUAF). İdempotent:
id = uuid5(NS, "olcum:"+baslik+":"+wc+":"+body); var olan kayıt $setOnInsert ile
KORUNUR.
"""
import json
import uuid
from pathlib import Path

VERI_YOLU = Path(__file__).resolve().parent.parent / "data" / "olcum_metinleri.json"

KAYNAK = "olcum"
BOLUM = "olcum"
TUR = "olcum"
EKLEYEN_AD = "OBA Ölçüm Metinleri (admin toplu içe aktarım)"
SABIT_TARIH = "2026-07-19T00:00:00+00:00"
NS = uuid.UUID("b51c0000-0000-4000-8000-000000000002")


def metin_id(baslik: str, wc, body: str) -> str:
    return str(uuid.uuid5(NS, f"{KAYNAK}:{baslik}:{wc}:{body}"))


def _acik_id(mid: str, i: int) -> str:
    return str(uuid.uuid5(NS, f"{mid}:acik:{i}"))


def doc_olustur(m: dict) -> dict:
    """Birleşik kayıttan (dosya/baslik/sinif_seviyesi/govde/sorular) DB dokümanı."""
    from core.metin_zorluk import zorluk_hesapla
    from core.acik_soru import acik_soru_nesnesi

    baslik = (m.get("baslik") or "").strip()
    govde = (m.get("govde") or "").strip()
    wc = int(m.get("kelime_sayisi") or len(govde.split()))
    sinif = m.get("sinif_seviyesi")
    sinif_str = "lise" if str(sinif).lower() == "lise" else str(sinif)
    mid = metin_id(baslik, wc, govde)

    acik = []
    for i, q in enumerate(m.get("sorular") or []):
        nesne = acik_soru_nesnesi(
            _acik_id(mid, i),
            q.get("no", i + 1),
            q.get("kategori_ham") or q.get("kategori"),
            q.get("soru", ""),
            q.get("cevap", ""),
        )
        if q.get("subjektif"):
            nesne["subjektif"] = True
        acik.append(nesne)

    return {
        "id": mid,
        "baslik": baslik,
        "icerik": govde,
        "kelime_sayisi": wc,
        "seviye": wc,
        "sinif_seviyesi": sinif_str,   # GERÇEK sınıf etiketi (okuma havuzu null'dır)
        "tur": TUR,
        "bolum": BOLUM,
        "zorluk": zorluk_hesapla(govde),
        "durum": "havuzda",            # admin toplu = onaydan muaf
        "kaynak": KAYNAK,
        "ekleyen_id": "sistem",
        "ekleyen_ad": EKLEYEN_AD,
        "oylar": {},
        "sorular": [],                 # Ölçüm setinde ÇSS yok
        "acik_sorular": acik,
        "gorsel_prompt": None,
        "gorsel": None,
        "gorsel_ilk_ekleyen_id": None,
        "olusturma_tarihi": SABIT_TARIH,
        "yayin_tarihi": SABIT_TARIH,
    }


async def yukle(db, veri_yolu: Path = None) -> dict:
    """olcum_metinleri.json → analiz_metinler upsert. Özet döndürür."""
    yol = veri_yolu or VERI_YOLU
    if not yol.exists():
        return {"hata": f"veri dosyası yok: {yol.name}", "eklendi": 0, "korundu": 0, "metin": 0}

    metinler = json.load(open(yol, encoding="utf-8"))
    eklendi = korundu = toplam_soru = 0
    for m in metinler:
        doc = doc_olustur(m)
        toplam_soru += len(doc["acik_sorular"])
        r = await db.analiz_metinler.update_one(
            {"id": doc["id"]}, {"$setOnInsert": doc}, upsert=True)
        if r.upserted_id is not None:
            eklendi += 1
        else:
            korundu += 1
    return {"metin": len(metinler), "eklendi": eklendi, "korundu": korundu,
            "toplam_soru": toplam_soru, "hata": None}
