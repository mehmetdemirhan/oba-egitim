"""FAZ 1 migrasyonu — rozet temizliği + alan adı normalizasyonu.

Yaptıkları (hepsi idempotent, tekrar çalıştırılabilir):
  1. Ölü AI rozetlerini (ai_ilk/ai_5/ai_20/ai_50) kazanilan_rozetler'den siler.
     NOT: Rozet ödül puanları HİÇBİR yerde kalıcı saklanmaz (toplam puan
     birlesik/puan-tablosu endpoint'lerinde anlık hesaplanır). Bu yüzden bu
     kazanımları silmek users.puan / students.toplam_xp alanlarını BOZMAZ;
     ayrıca bir geri-düşme (rollback) gerekmez.
  2. sistem_ayarlari'nda kayıtlı rozet tanımlarındaki "puan"/"xp" alanlarını
     tek "odul_puan" alanına taşır (öğretmen + öğrenci).
  3. kazanilan_rozetler üzerinde {kullanici_id, rozet_kodu} unique index'i kurar
     (önce duplikeleri temizler).

Çalıştırma (appbackend dizininden):
  .venv/Scripts/python.exe scripts/migrate_rozet_faz1.py
"""
import asyncio
import sys
from pathlib import Path

# appbackend kökünü path'e ekle (core.* importları için)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# NOT: core.db import'u event loop gerektirir (Motor GridFS). Bu yüzden modül
# seviyesinde DEĞİL, asyncio.run başladıktan sonra fonksiyon içinde import edilir.

OLU_AI_ROZETLER = ["ai_ilk", "ai_5", "ai_20", "ai_50"]


async def olu_ai_rozetleri_sil():
    from core.db import db
    n = await db.kazanilan_rozetler.count_documents({"rozet_kodu": {"$in": OLU_AI_ROZETLER}})
    if n == 0:
        print(f"  ✓ Ölü AI rozeti kazanımı yok (silinecek bir şey yok)")
        return 0
    res = await db.kazanilan_rozetler.delete_many({"rozet_kodu": {"$in": OLU_AI_ROZETLER}})
    print(f"  ✓ {res.deleted_count} ölü AI rozeti kazanımı silindi")
    return res.deleted_count


async def alan_adi_normalize(tip: str):
    from core.db import db
    doc = await db.sistem_ayarlari.find_one({"tip": tip})
    if not doc or not isinstance(doc.get("degerler"), list):
        print(f"  ✓ {tip}: DB'de kayıtlı tanım yok (koddaki DEFAULT geçerli), atlandı")
        return 0
    degisen = 0
    yeni = []
    for r in doc["degerler"]:
        if not isinstance(r, dict):
            yeni.append(r)
            continue
        if "odul_puan" not in r and ("puan" in r or "xp" in r):
            r = dict(r)
            r["odul_puan"] = int(r.pop("puan", r.pop("xp", 0)) or 0)
            r.pop("puan", None)
            r.pop("xp", None)
            degisen += 1
        else:
            r.pop("puan", None)
            r.pop("xp", None)
        # ölü AI rozet tanımını da temizle
        if r.get("kod") in OLU_AI_ROZETLER:
            continue
        yeni.append(r)
    await db.sistem_ayarlari.update_one({"tip": tip}, {"$set": {"degerler": yeni}})
    print(f"  ✓ {tip}: {degisen} tanımda alan adı odul_puan'a taşındı, {len(yeni)} tanım yazıldı")
    return degisen


async def main():
    from core.db import db, ensure_indexes
    print("═══ FAZ 1 ROZET MİGRASYONU ═══")
    print("1) Ölü AI rozetleri temizleniyor...")
    await olu_ai_rozetleri_sil()
    print("2) Alan adı normalizasyonu (sistem_ayarlari)...")
    await alan_adi_normalize("ogretmen_rozetleri")
    await alan_adi_normalize("ogrenci_rozetleri")
    print("3) Unique index kuruluyor (dedup + create_index)...")
    await ensure_indexes()
    # Doğrulama
    kalan_ai = await db.kazanilan_rozetler.count_documents({"rozet_kodu": {"$in": OLU_AI_ROZETLER}})
    toplam = await db.kazanilan_rozetler.count_documents({})
    print("─── SONUÇ ───")
    print(f"  kazanilan_rozetler toplam: {toplam}")
    print(f"  kalan ölü AI rozeti: {kalan_ai} (0 olmalı)")
    print("═══ TAMAMLANDI ═══")


if __name__ == "__main__":
    asyncio.run(main())
