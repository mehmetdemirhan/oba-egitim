"""Migrasyon — analiz_metinler.acik_sorular alanını NESNE listesine normalize eder.

Önceki 150 metin import'unda acik_sorular DÜZ STRING listesiydi; yeni Bloom
metinleriyle tek tip şema olsun diye string'leri core.acik_soru şema nesnesine
çevirir (bkz. stringten_acik_soru). Zaten nesne olanlara dokunmaz.

İdempotent: tümü nesne olan dokümanlar atlanır. VARSAYILAN MOD = DRY-RUN.
    Önizleme:  .venv/Scripts/python.exe scripts/migrate_acik_sorular.py
    Uygula:    .venv/Scripts/python.exe scripts/migrate_acik_sorular.py --apply
Türkçe çıktı için Windows'ta: set PYTHONIOENCODING=utf-8
"""
import sys
import uuid
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

APPLY = "--apply" in sys.argv
NS = uuid.UUID("a51c0000-0000-4000-8000-000000000001")


async def main():
    from core.db import db
    from core.acik_soru import acik_soru_normalize_liste, subjektif_isaret

    print("═══ acik_sorular NESNE MİGRASYONU + subjektif yeniden sınıflama ═══")
    print(f"  Mod: {'UYGULA (--apply)' if APPLY else 'DRY-RUN (önizleme)'}\n")

    metinler = await db.analiz_metinler.find(
        {"acik_sorular": {"$exists": True, "$ne": []}}
    ).to_list(length=None)

    guncellenen = atlanan = 0
    subjektif_duzeltilen = 0  # "kabul edil" notu içerdiği halde subjektif=False olanlar
    for m in metinler:
        acik = m.get("acik_sorular") or []
        mid = m["id"]
        # 1) Şekil normalizasyonu (string → nesne)
        nesne_haline = all(isinstance(s, dict) for s in acik)
        yeni = acik if nesne_haline else acik_soru_normalize_liste(
            acik, lambda i, mid=mid: str(uuid.uuid5(NS, f"{mid}:acik:{i}")))

        # 2) Subjektif yeniden sınıflama: model_cevap "kabul edil" notu taşıyorsa
        #    ama subjektif=False işaretlenmişse düzelt (eski tespit bu notu kaçırıyordu).
        degisti = not nesne_haline
        for s in yeni:
            if isinstance(s, dict) and not s.get("subjektif") and subjektif_isaret(s.get("model_cevap") or ""):
                s["subjektif"] = True
                subjektif_duzeltilen += 1
                degisti = True

        if not degisti:
            atlanan += 1
            continue
        if APPLY:
            await db.analiz_metinler.update_one({"id": mid}, {"$set": {"acik_sorular": yeni}})
        guncellenen += 1

    print("─── ÖZET ───")
    print(f"  {'Güncellenecek' if not APPLY else 'Güncellenen'} metin : {guncellenen}")
    print(f"  Değişmeyen (atlandı)       : {atlanan}")
    print(f"  Subjektif'e çevrilen soru  : {subjektif_duzeltilen}")
    if not APPLY:
        print("\n  ⚠  DRY-RUN: hiçbir şey yazılmadı. Uygulamak için: --apply")
    print("═══ TAMAMLANDI ═══")


if __name__ == "__main__":
    asyncio.run(main())
