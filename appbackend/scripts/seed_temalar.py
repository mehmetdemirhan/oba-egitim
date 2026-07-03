"""Tema seed — hazır temaları theme_configs koleksiyonuna yazar (idempotent).

core.tema_varsayilan.TEMALAR'ı kod üzerinde upsert eder. Mevcut (elle düzenlenmiş)
temaların 'modlar' ve 'ad' alanlarını EZMEZ; yalnız yoksa ekler.

Çalıştırma (appbackend dizininden):
  .venv/Scripts/python.exe scripts/seed_temalar.py
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
# core.db event loop gerektirir → import fonksiyon içinde.


async def main():
    from core.db import db, ensure_indexes
    from core.tema_varsayilan import TEMALAR
    from datetime import datetime

    print("═══ TEMA SEED ═══")
    await ensure_indexes()  # uq_tema_kod garanti
    now = datetime.utcnow().isoformat()
    eklenen, korunan = 0, 0
    for t in TEMALAR:
        mevcut = await db.theme_configs.find_one({"kod": t["kod"]})
        if mevcut:
            korunan += 1
            continue
        doc = {**t, "olusturma_tarihi": now, "guncelleme_tarihi": now}
        await db.theme_configs.insert_one(doc)
        eklenen += 1
        print(f"  + {t['kod']} ({t['ad']})")
    toplam = await db.theme_configs.count_documents({})
    print("─── SONUÇ ───")
    print(f"  eklenen: {eklenen} | korunan (mevcut): {korunan} | toplam: {toplam}")
    print("═══ TAMAMLANDI ═══")


if __name__ == "__main__":
    asyncio.run(main())
