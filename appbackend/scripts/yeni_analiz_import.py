"""Bloom taksonomili açık uçlu metinleri ortak metin havuzuna (analiz_metinler) aktarır.

Kaynak: appbackend/data/yeni_analiz_metinleri.json (9 metin).
ÖNCEKİ 150 metinle AYNI koleksiyon ve AYNI şema kullanılır — fark yalnız soru
tipidir: bu metinlerde MCQ yoktur (sorular=[]); sorular açık uçludur ve
`acik_sorular` NESNE listesinde saklanır (bkz. core.acik_soru).

Alan eşleştirmesi:
  title        → baslik
  word_count   → seviye (+ kelime_sayisi senkron)   [SINIF eşleştirmesi yok]
  body         → icerik
  questions[]  → acik_sorular[]  (no, category→kategori(+ham), question→soru,
                                  answer→model_cevap/subjektif)
    · answer "(Öğrenci cevabı ...)" ise subjektif=True (otomatik puanlanamaz);
      içinde "örnek:" varsa örnek yönlendirme model_cevap olur.
    · aksi halde answer gerçek model cevaptır (subjektif=False).

İdempotent: id = uuid5(NS, "akici_okuma:"+baslik+":"+wc+":"+body). Var olan kayıt
$setOnInsert ile KORUNUR. VARSAYILAN MOD = DRY-RUN. Uygulamak için: --apply

Aynı formattaki HERHANGİ bir dosya için tekrar kullanılabilir — dosya adı/yolu
opsiyonel argüman olarak verilir (data/ altındaki ad veya mutlak yol).
Varsayılan: data/yeni_analiz_metinleri.json

Çalıştırma (appbackend dizininden):
  Önizleme:  .venv/Scripts/python.exe scripts/yeni_analiz_import.py yeni_analiz_metinleri2.json
  Uygula:    .venv/Scripts/python.exe scripts/yeni_analiz_import.py yeni_analiz_metinleri2.json --apply
Türkçe çıktı için Windows'ta: set PYTHONIOENCODING=utf-8
"""
import sys
import json
import uuid
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

APPLY = "--apply" in sys.argv
# İlk bayrak-olmayan argüman = dosya adı/yolu (opsiyonel)
_DOSYA_ARG = next((a for a in sys.argv[1:] if not a.startswith("--")), None)

KAYNAK = "akici_okuma"          # önceki 150 ile AYNI havuz
EKLEYEN_AD = "OBA Akıcı Okuma Havuzu"
SABIT_TARIH = "2026-07-07T00:00:00+00:00"
# 150 import'la AYNI isim uzayı — id şeması birebir aynı (uyum/idempotentlik).
NS = uuid.UUID("a51c0000-0000-4000-8000-000000000001")

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
if _DOSYA_ARG:
    _p = Path(_DOSYA_ARG)
    VERI_YOLU = _p if _p.is_absolute() else (_DATA_DIR / _DOSYA_ARG)
else:
    VERI_YOLU = _DATA_DIR / "yeni_analiz_metinleri.json"


def _metin_id(baslik: str, word_count: int, body: str) -> str:
    return str(uuid.uuid5(NS, f"{KAYNAK}:{baslik}:{word_count}:{body}"))


def _acik_id(metin_id: str, i: int) -> str:
    return str(uuid.uuid5(NS, f"{metin_id}:acik:{i}"))


def _doc_olustur(kayit: dict) -> dict:
    from core.metin_zorluk import zorluk_hesapla
    from core.acik_soru import acik_soru_nesnesi

    baslik = (kayit.get("title") or "").strip()
    body = kayit.get("body") or ""
    word_count = int(kayit.get("word_count") or 0)
    mid = _metin_id(baslik, word_count, body)

    acik_sorular = []
    for i, q in enumerate(kayit.get("questions") or []):
        acik_sorular.append(acik_soru_nesnesi(
            _acik_id(mid, i),
            q.get("no"),
            q.get("category"),
            q.get("question", ""),
            q.get("answer", ""),
        ))

    return {
        "id": mid,
        "baslik": baslik,
        "icerik": body,
        "kelime_sayisi": word_count,
        "seviye": word_count,
        "sinif_seviyesi": None,
        "tur": "akici_okuma",
        "zorluk": zorluk_hesapla(body),
        "durum": "havuzda",
        "kaynak": KAYNAK,
        "ekleyen_id": "sistem",
        "ekleyen_ad": EKLEYEN_AD,
        "oylar": {},
        "sorular": [],                 # bu metinlerde MCQ yok
        "acik_sorular": acik_sorular,  # NESNE listesi (Bloom + model cevap)
        "gorsel_prompt": None,
        "gorsel": None,
        "gorsel_ilk_ekleyen_id": None,
        "olusturma_tarihi": SABIT_TARIH,
        "yayin_tarihi": SABIT_TARIH,
    }


async def main():
    from core.db import db

    mod = "UYGULA (--apply)" if APPLY else "DRY-RUN (önizleme — hiçbir şey yazılmaz)"
    print("═══ YENİ ANALİZ METİNLERİ (Bloom / açık uçlu) İÇE AKTARIM ═══")
    print(f"  Mod: {mod}")
    print(f"  Kaynak: {VERI_YOLU}")

    if not VERI_YOLU.exists():
        print(f"  ✗ HATA: veri dosyası bulunamadı: {VERI_YOLU}")
        sys.exit(1)

    with open(VERI_YOLU, encoding="utf-8") as f:
        kayitlar = json.load(f)
    print(f"  Toplam kayıt: {len(kayitlar)}\n")

    sayac = {"eklendi": 0, "mevcut_korundu": 0, "bos_baslik": 0}
    toplam_acik = toplam_subjektif = 0
    from collections import Counter
    kat = Counter()
    for kayit in kayitlar:
        baslik = (kayit.get("title") or "").strip()
        if not baslik:
            sayac["bos_baslik"] += 1
            continue
        doc = _doc_olustur(kayit)
        toplam_acik += len(doc["acik_sorular"])
        toplam_subjektif += sum(1 for s in doc["acik_sorular"] if s["subjektif"])
        for s in doc["acik_sorular"]:
            kat[s["kategori"]] += 1

        if APPLY:
            r = await db.analiz_metinler.update_one(
                {"id": doc["id"]}, {"$setOnInsert": doc}, upsert=True)
            if r.upserted_id is not None:
                sayac["eklendi"] += 1
            else:
                sayac["mevcut_korundu"] += 1
        else:
            mevcut = await db.analiz_metinler.find_one({"id": doc["id"]}, {"_id": 1})
            sayac["mevcut_korundu" if mevcut else "eklendi"] += 1

    print("─── ÖZET ───")
    print(f"  {'Eklenecek' if not APPLY else 'Eklenen'} yeni metin : {sayac['eklendi']}")
    print(f"  Zaten var (korunur)       : {sayac['mevcut_korundu']}")
    print(f"  Boş başlık (atlandı)      : {sayac['bos_baslik']}")
    print(f"  Toplam açık uçlu soru     : {toplam_acik}  (subjektif/öğrenci cevabı: {toplam_subjektif})")
    print(f"  Bloom dağılımı            : {dict(kat)}")
    if not APPLY:
        print("\n  ⚠  DRY-RUN: hiçbir şey yazılmadı. Uygulamak için: --apply")
    print("═══ TAMAMLANDI ═══")


if __name__ == "__main__":
    asyncio.run(main())
