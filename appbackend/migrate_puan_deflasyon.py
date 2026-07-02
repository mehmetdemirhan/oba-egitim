"""Puan/XP deflasyonu migrasyonu — DB'deki sistem_ayarlari puan tablolarını
KOD VARSAYILANLARINA senkronlar.

Neden gerekli: seed.py, XP/lig/rozet/puan varsayılanlarını bir kez DB'ye (sistem_ayarlari)
yazar; getter'lar önce DB'yi okuduğu için, koddaki varsayılanları değiştirmek DB'ye
zaten yazılmış eski değerleri GÜNCELLEMEZ. Bu script o kayıtları güncel kod
varsayılanlarıyla üzerine yazar (idempotent — tekrar çalıştırılabilir).

Çalıştırma (appbackend içinde, uygulamanın .env'i otomatik yüklenir):
    .venv/Scripts/python.exe migrate_puan_deflasyon.py

DİKKAT: rozet tablolarını da üzerine yazar; admin panelinden özel rozet eklediyseniz
önce yedek alın (yedekleme modülü) veya bu iki tipi listeden çıkarın.
"""
import asyncio
import os
import sys

os.environ.setdefault("SECRET_KEY", "migrate")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# core.db import'unda motor/GridFS aktif event loop ister; loop'u önce kur ve
# migrasyonu AYNI loop'ta çalıştır (aksi halde "attached to a different loop").
_LOOP = asyncio.new_event_loop()
asyncio.set_event_loop(_LOOP)

from core.db import db, client  # .env'den MONGO_URL/DB_NAME yükler
from core.sistem import (
    XP_TABLOSU_DEFAULT, LIG_ESIKLERI_DEFAULT,
    OGRETMEN_ROZETLERI_DEFAULT, OGRENCI_ROZETLERI_DEFAULT,
    VARSAYILAN_PUANLAR, OGRETMEN_PUAN_AGIRLIKLARI_DEFAULT,
)

# (tip, deger_anahtari, yeni_deger) — puan_ayarlari "puanlar", diğerleri "degerler" kullanır
HEDEFLER = [
    ("xp_tablosu", "degerler", XP_TABLOSU_DEFAULT),
    ("lig_esikleri", "degerler", LIG_ESIKLERI_DEFAULT),
    ("ogretmen_rozetleri", "degerler", OGRETMEN_ROZETLERI_DEFAULT),
    ("ogrenci_rozetleri", "degerler", OGRENCI_ROZETLERI_DEFAULT),
    ("ogretmen_puan_agirliklari", "degerler", OGRETMEN_PUAN_AGIRLIKLARI_DEFAULT),
    ("puan_ayarlari", "puanlar", VARSAYILAN_PUANLAR),
]


def _ozet(v):
    """Bir tablonun kısa özetini (birkaç örnek değer) döndürür."""
    if isinstance(v, dict):
        return {k: v[k] for k in list(v)[:4]}
    if isinstance(v, list):
        return [f"{r.get('kod')}={r.get('puan', r.get('xp'))}" for r in v[:4]]
    return v


async def run():
    print("=" * 60)
    print(f"DB: {db.name}")
    print("=" * 60)
    for tip, anahtar, yeni in HEDEFLER:
        eski_doc = await db.sistem_ayarlari.find_one({"tip": tip})
        eski = eski_doc.get(anahtar) if eski_doc else None
        await db.sistem_ayarlari.update_one(
            {"tip": tip},
            {"$set": {"tip": tip, anahtar: yeni}},
            upsert=True,
        )
        durum = "YOK→oluşturuldu" if eski is None else "güncellendi"
        print(f"[{tip}] {durum}")
        print(f"    önce : {_ozet(eski)}")
        print(f"    sonra: {_ozet(yeni)}")

    # ── db.ayarlar: egzersiz per-id ödülleri (admin ayarlı; varsayılan seed YOK) ──
    # Doküman varsa iki haneli değerleri tek haneye çeker (egzersiz tarifesi ~2 →
    # ~÷5). Yoksa atlanır (kod fallback'i zaten 2 kullanır).
    ez = await db.ayarlar.find_one({"tip": "egzersiz_puanlari"})
    if ez and ez.get("puanlar"):
        eski = ez["puanlar"]
        yeni = {
            k: (v if not isinstance(v, (int, float)) or v <= 9 else max(1, min(9, round(v / 5))))
            for k, v in eski.items()
        }
        if yeni != eski:
            await db.ayarlar.update_one({"tip": "egzersiz_puanlari"}, {"$set": {"puanlar": yeni}})
            print("[egzersiz_puanlari] güncellendi (db.ayarlar)")
            for k in eski:
                if eski[k] != yeni[k]:
                    print(f"    {k}: {eski[k]} → {yeni[k]}")
        else:
            print("[egzersiz_puanlari] zaten tek haneli, değişiklik yok")
    else:
        print("[egzersiz_puanlari] db.ayarlar'da yok → atlandı (kod fallback'i 2 kullanır)")

    print("=" * 60)
    print("Bitti. Backend'i yeniden başlatmaya gerek yok (getter'lar DB'yi her istekte okur).")
    client.close()


if __name__ == "__main__":
    _LOOP.run_until_complete(run())
