"""MEB kelime 'ders' alanı migration'ı — idempotent, tek seferlik.

Yapar:
  1. `ders` alanı olmayan/boş tüm meb_kelimeleri kayıtlarına ders="turkce" yazar.
  2. Varsa eski (kelime, sinif) unique index'ini kaldırır; yeni (kelime, sinif, ders)
     unique index'i oluşturur.

Çalıştırma (appbackend dizininde):
    set PYTHONIOENCODING=utf-8
    .venv/Scripts/python.exe scripts/meb_kelime_ders_migration.py

İki kez çalıştırmak güvenlidir (ikinci sefer 0 kayıt güncellenir).
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def run():
    from core.db import db  # core.config .env'i otomatik yükler

    # 1) ders alanını doldur
    res = await db.meb_kelimeleri.update_many(
        {"$or": [{"ders": {"$exists": False}}, {"ders": None}, {"ders": ""}]},
        {"$set": {"ders": "turkce"}},
    )
    print(f"{res.modified_count} kayıt güncellendi (ders=turkce set edildi)")

    # 2) Index geçişi
    try:
        idx = await db.meb_kelimeleri.index_information()
        for ad, spec in idx.items():
            keys = {k for k, _ in spec.get("key", [])}
            if keys == {"kelime", "sinif"} and spec.get("unique"):
                await db.meb_kelimeleri.drop_index(ad)
                print(f"Eski unique index '{ad}' (kelime,sinif) silindi")
        await db.meb_kelimeleri.create_index(
            [("kelime", 1), ("sinif", 1), ("ders", 1)],
            unique=True, name="kelime_sinif_ders_uniq",
        )
        print("Yeni unique index (kelime, sinif, ders) oluşturuldu / mevcut")
    except Exception as ex:
        print(f"Index uyarısı (veri migration'ı tamamlandı): {ex}")


if __name__ == "__main__":
    asyncio.run(run())
    print("Migration tamamlandı.")
