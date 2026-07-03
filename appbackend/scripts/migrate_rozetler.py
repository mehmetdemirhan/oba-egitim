"""FAZ 2 migrasyonu — kod-gömülü rozet tanımlarını 'rozetler' koleksiyonuna taşır.

core.sistem DEFAULT listelerini (ad/ikon/kategori/seviye/odul_puan) +
core.rozet_kosullari koşullarını (metrik/operator/esik) birleştirip veri-odaklı
'rozetler' koleksiyonuna yazar.

Şema (her doküman):
  {kod, ad, aciklama, ikon, renk, kategori, seviye, odul_puan, rol,
   kosul: {metrik, operator, esik, ve?}, aktif, sira,
   olusturma_tarihi, guncelleme_tarihi}

Idempotent: (rol, kod) üzerinde upsert. Tekrar çalıştırmak güvenlidir; mevcut
kayıtların 'aktif' ve elle düzenlenmiş alanları KORUNUR (yalnızca eksikler eklenir).

Çalıştırma (appbackend dizininden):
  .venv/Scripts/python.exe scripts/migrate_rozetler.py
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# core.db event loop gerektirir → importlar fonksiyon içinde.


async def _tanimlari_uret():
    from core.sistem import get_ogretmen_rozetleri, get_ogrenci_rozetleri
    from core.rozet_kosullari import (
        OGRETMEN_KOSULLARI, OGRENCI_KOSULLARI, METRIK_ACIKLAMALARI, kosul_getir,
    )
    from core.rozet_helpers import rozet_odul_puan

    kaynaklar = [
        ("teacher", await get_ogretmen_rozetleri(), OGRETMEN_KOSULLARI),
        ("student", await get_ogrenci_rozetleri(), OGRENCI_KOSULLARI),
    ]
    tanimlar = []
    for rol, temel, kosullar in kaynaklar:
        for sira, t in enumerate(temel):
            kod = t.get("kod")
            kosul = kosullar.get(kod) or kosul_getir(rol, kod)
            metrik = kosul.get("metrik", "manuel")
            aciklama = METRIK_ACIKLAMALARI.get(metrik, "")
            if kosul.get("esik") is not None:
                aciklama = f"{aciklama} (≥ {kosul['esik']})"
            tanimlar.append({
                "kod": kod,
                "ad": t.get("ad", kod),
                "aciklama": aciklama,
                "ikon": t.get("ikon", "🏅"),
                "renk": t.get("renk"),
                "kategori": t.get("kategori", ""),
                "seviye": t.get("seviye", "bronz"),
                "odul_puan": rozet_odul_puan(t),
                "rol": rol,
                "kosul": kosul,
                "aktif": True,
                "sira": sira,
            })
    return tanimlar


async def main():
    from core.db import db, ensure_indexes
    from datetime import datetime

    print("═══ FAZ 2 ROZET TANIM MİGRASYONU ═══")
    await ensure_indexes()  # (rol, kod) unique index garanti

    tanimlar = await _tanimlari_uret()
    now = datetime.utcnow().isoformat()
    eklenen, guncellenen = 0, 0
    for t in tanimlar:
        mevcut = await db.rozetler.find_one({"rol": t["rol"], "kod": t["kod"]})
        if mevcut:
            # Sadece eksik alanları tamamla; elle düzenlenenleri (aktif, odul_puan,
            # ad, kosul) EZME — koşul/puan admin panelden değişmiş olabilir.
            eksik = {k: v for k, v in t.items() if k not in mevcut}
            eksik["guncelleme_tarihi"] = now
            await db.rozetler.update_one({"_id": mevcut["_id"]}, {"$set": eksik})
            guncellenen += 1
        else:
            t["olusturma_tarihi"] = now
            t["guncelleme_tarihi"] = now
            await db.rozetler.insert_one(t)
            eklenen += 1

    toplam = await db.rozetler.count_documents({})
    ogr = await db.rozetler.count_documents({"rol": "teacher"})
    ogn = await db.rozetler.count_documents({"rol": "student"})
    print("─── SONUÇ ───")
    print(f"  eklenen: {eklenen} | güncellenen (korundu): {guncellenen}")
    print(f"  rozetler toplam: {toplam} (öğretmen {ogr}, öğrenci {ogn})")
    print("═══ TAMAMLANDI ═══")


if __name__ == "__main__":
    asyncio.run(main())
