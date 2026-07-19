# -*- coding: utf-8 -*-
"""ÖLÇÜM METİNLERİ → analiz_metinler koleksiyonu (bolum="olcum") toplu içe aktarım.

Kaynak (iki dosyayı birleştirir):
  - data/olcum_ham.json           : gövde/başlık/kelime_sayısı/sınıf (PyMuPDF, birebir)
  - data/olcum_parts/*.json       : 10 açık uçlu soru + cevap (alt-ajan yapılandırması)

Şema: 150'lik Akıcı Okuma (yeni_analiz_import) ile AYNI koleksiyon+alanlar; farklar:
  - bolum = "olcum"               (yeni birincil kategori — "Ölçüm Metinleri")
  - kaynak = "olcum"
  - sinif_seviyesi = "1".."8" | "lise"  (GERÇEK sınıf etiketi; okuma havuzu null'dır)
  - tur = "olcum"
  - durum = "havuzda"             (ADMIN toplu içe aktarım = onaydan MUAF; bundan
                                    sonra ELLE eklenen metinler onay akışına girer)
  - acik_sorular = 10 × {no, kategori(+ham), soru, model_cevap, subjektif}

Gövde: govde_temiz doluysa onu (A.4 İNSAN gibi başlıksız dosyalar), yoksa ham govde.

İdempotent: id = uuid5(NS, "olcum:"+baslik+":"+wc+":"+body). Var olan kayıt
$setOnInsert ile KORUNUR. VARSAYILAN MOD = DRY-RUN. Uygulamak için: --apply

Çalıştırma (appbackend dizininden):
  Önizleme:  .venv/Scripts/python.exe scripts/olcum_import.py
  Uygula:    .venv/Scripts/python.exe scripts/olcum_import.py --apply
Türkçe çıktı için Windows'ta: set PYTHONIOENCODING=utf-8
"""
import sys
import json
import uuid
import glob
import asyncio
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

APPLY = "--apply" in sys.argv

KAYNAK = "olcum"
BOLUM = "olcum"
TUR = "olcum"
EKLEYEN_AD = "OBA Ölçüm Metinleri (admin toplu içe aktarım)"
SABIT_TARIH = "2026-07-19T00:00:00+00:00"
NS = uuid.UUID("b51c0000-0000-4000-8000-000000000002")  # olcum ad uzayı

_DATA = Path(__file__).resolve().parent.parent / "data"
HAM = _DATA / "olcum_ham.json"
PARTS = _DATA / "olcum_parts"
BIRLESIK = _DATA / "olcum_metinleri.json"   # doğrulama için birleşik çıktı


def _metin_id(baslik: str, wc, body: str) -> str:
    return str(uuid.uuid5(NS, f"{KAYNAK}:{baslik}:{wc}:{body}"))


def _acik_id(mid: str, i: int) -> str:
    return str(uuid.uuid5(NS, f"{mid}:acik:{i}"))


def _birlestir():
    """olcum_ham.json (gövde) + olcum_parts/*.json (soru) → metin listesi (dosya bazlı)."""
    ham = {x["dosya"]: x for x in json.load(open(HAM, encoding="utf-8"))}
    parcalar = {}
    for pf in sorted(glob.glob(str(PARTS / "*.json"))):
        for kayit in json.load(open(pf, encoding="utf-8")):
            parcalar[kayit["dosya"]] = kayit
    # Elle-doğrulanmış düzeltmeler (çapraz doğrulama ile bulunan ajan hataları)
    override_yolu = _DATA / "olcum_override.json"
    if override_yolu.exists():
        for kayit in json.load(open(override_yolu, encoding="utf-8")):
            parcalar[kayit["dosya"]] = kayit

    eksik = set(ham) - set(parcalar)
    if eksik:
        print(f"  ⚠ Parça bulunamayan dosyalar: {sorted(eksik)}")

    metinler = []
    for dosya, h in ham.items():
        p = parcalar.get(dosya)
        if not p:
            continue
        govde = (p.get("govde_temiz") or h.get("govde") or "").strip()
        baslik = (p.get("baslik") or h.get("baslik") or "").strip()
        sinif = p.get("sinif_seviyesi", h.get("sinif_seviyesi"))
        sinif_str = "lise" if str(sinif).lower() == "lise" else str(sinif)
        wc = p.get("kelime_sayisi") or h.get("kelime_sayisi") or len(govde.split())
        metinler.append({
            "dosya": dosya,
            "baslik": baslik,
            "sinif_seviyesi": sinif_str,
            "kelime_sayisi": int(wc) if wc else len(govde.split()),
            "govde": govde,
            "sorular": p.get("sorular") or [],
            "notlar": p.get("notlar") or "",
        })
    return metinler


def _doc_olustur(m: dict) -> dict:
    # TEK KAYNAK: core.olcum.doc_olustur (endpoint ile birebir aynı şema/ID).
    from core.olcum import doc_olustur
    return doc_olustur(m)


async def main():
    from core.db import db

    mod = "UYGULA (--apply)" if APPLY else "DRY-RUN (önizleme — hiçbir şey yazılmaz)"
    print("═══ ÖLÇÜM METİNLERİ İÇE AKTARIM (bolum=olcum) ═══")
    print(f"  Mod: {mod}\n")

    metinler = _birlestir()
    # Doğrulama için birleşik dosyayı da yaz
    json.dump(metinler, open(BIRLESIK, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    sayac = {"eklendi": 0, "korundu": 0}
    kat = Counter()
    toplam_soru = toplam_subj = 0
    uyarilar = []

    for m in metinler:
        doc = _doc_olustur(m)
        ns = len(doc["acik_sorular"])
        toplam_soru += ns
        toplam_subj += sum(1 for s in doc["acik_sorular"] if s["subjektif"])
        for s in doc["acik_sorular"]:
            kat[s["kategori"]] += 1
        if ns != 10:
            uyarilar.append(f"{m['baslik']}: {ns} soru (10 bekleniyordu)")
        bos_cevap = [s["no"] for s in doc["acik_sorular"] if not s["subjektif"] and not s["model_cevap"]]
        if bos_cevap:
            uyarilar.append(f"{m['baslik']}: boş cevap soru# {bos_cevap}")
        if m.get("notlar"):
            uyarilar.append(f"{m['baslik']}: not → {m['notlar'][:120]}")

        if APPLY:
            r = await db.analiz_metinler.update_one(
                {"id": doc["id"]}, {"$setOnInsert": doc}, upsert=True)
            sayac["eklendi" if r.upserted_id is not None else "korundu"] += 1
        else:
            mevcut = await db.analiz_metinler.find_one({"id": doc["id"]}, {"_id": 1})
            sayac["korundu" if mevcut else "eklendi"] += 1

    print("─── ÖZET ───")
    print(f"  Metin           : {len(metinler)}")
    print(f"  {'Eklenecek' if not APPLY else 'Eklenen'} yeni    : {sayac['eklendi']}")
    print(f"  Zaten var       : {sayac['korundu']}")
    print(f"  Toplam soru     : {toplam_soru}  (subjektif: {toplam_subj})")
    print(f"  Bloom dağılımı  : {dict(kat)}")
    print(f"  Sınıf dağılımı  : {dict(Counter(m['sinif_seviyesi'] for m in metinler))}")
    print(f"  Birleşik çıktı  : {BIRLESIK}")
    if uyarilar:
        print("\n─── DOĞRULAMA UYARILARI (örneklem kontrolü için) ───")
        for u in uyarilar:
            print(f"  • {u}")
    if not APPLY:
        print("\n  ⚠  DRY-RUN: hiçbir şey yazılmadı. Uygulamak için: --apply")
    print("═══ TAMAMLANDI ═══")


if __name__ == "__main__":
    asyncio.run(main())
