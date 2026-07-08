"""Migration — mevcut diagnostic_oturumlar kayıtlarına oturum_tipi ekler.

Her öğrenci için en ESKİ tamamlanmış oturum → "ilk_analiz", diğer tamamlanmışlar
ve devam edenler (oturum_tipi'si olmayanlar) → "ara_analiz". oturum_tipi zaten
olan kayıtlara dokunmaz (idempotent).

VARSAYILAN MOD = DRY-RUN. Uygulamak için: --apply
Çalıştırma (appbackend dizininden; MONGO_URL/DB_NAME ortamdan):
  .venv/Scripts/python.exe scripts/migrate_oturum_tipi.py            # önizleme
  .venv/Scripts/python.exe scripts/migrate_oturum_tipi.py --apply
"""
import sys
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
APPLY = "--apply" in sys.argv


async def main():
    from core.db import db

    print("═══ diagnostic_oturumlar → oturum_tipi MIGRATION ═══")
    print(f"  Mod: {'UYGULA (--apply)' if APPLY else 'DRY-RUN'}\n")

    oturumlar = await db.diagnostic_oturumlar.find().to_list(length=None)
    print(f"  Toplam oturum: {len(oturumlar)}")

    # Öğrenciye göre grupla
    ogr = {}
    for o in oturumlar:
        ogr.setdefault(o.get("ogrenci_id"), []).append(o)

    sayac = {"ilk_analiz": 0, "ara_analiz": 0, "atlandi": 0}
    for ogrenci_id, grup in ogr.items():
        # Tamamlanmışları olusturma_tarihi'ne göre sırala (en eski ilk)
        tamamlanan = sorted(
            [o for o in grup if o.get("durum") == "tamamlandi"],
            key=lambda o: o.get("olusturma_tarihi", ""))
        en_eski_id = tamamlanan[0]["id"] if tamamlanan else None
        for o in grup:
            if o.get("oturum_tipi"):
                sayac["atlandi"] += 1
                continue
            tip = "ilk_analiz" if o["id"] == en_eski_id else "ara_analiz"
            sayac[tip] += 1
            if APPLY:
                await db.diagnostic_oturumlar.update_one(
                    {"id": o["id"]}, {"$set": {"oturum_tipi": tip}})

    print("\n─── ÖZET ───")
    for k, v in sayac.items():
        print(f"  {k:12s}: {v}")
    if not APPLY:
        print("\n  ⚠  DRY-RUN: yazılmadı. Uygulamak için: --apply")
    print("═══ TAMAMLANDI ═══")


if __name__ == "__main__":
    asyncio.run(main())
