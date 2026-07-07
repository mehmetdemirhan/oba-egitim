"""Backfill — analiz_metinler koleksiyonundaki metinlere `zorluk` etiketi yazar.

Kutulu Okuma egzersizi, öğrencinin sınıfı + kur→zorluk eşlemesine göre metin
seçer. Mevcut seed metinlerinde `zorluk` alanı yoktur; bu script onları
etiketler. Sınıf İÇİNDE göreli sıralama (tercile) kullanır → her sınıfta
kolay/orta/zor dağılımı olur, kur bazlı seçim anlamlı çalışır.

İdempotent: `zorluk` zaten olan metinleri atlar (--force ile yeniden hesaplar).
VARSAYILAN MOD = DRY-RUN. Uygulamak için: --apply

Çalıştırma (appbackend dizininden; MONGO_URL/DB_NAME ortamdan okunur):
  Önizleme:  .venv/Scripts/python.exe scripts/etiketle_metin_zorluk.py
  Uygula:    .venv/Scripts/python.exe scripts/etiketle_metin_zorluk.py --apply
Türkçe çıktı için Windows'ta: set PYTHONIOENCODING=utf-8
"""
import sys
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

APPLY = "--apply" in sys.argv
FORCE = "--force" in sys.argv


async def main():
    from core.db import db
    from core.metin_zorluk import okunabilirlik_skoru, zorluk_dagit_gorece

    mod = "UYGULA (--apply)" if APPLY else "DRY-RUN (önizleme — hiçbir şey yazılmaz)"
    print("═══ analiz_metinler ZORLUK ETİKETLEME ═══")
    print(f"  Mod: {mod}{'  [FORCE: mevcut etiketler de yeniden hesaplanır]' if FORCE else ''}\n")

    metinler = await db.analiz_metinler.find().to_list(length=None)
    print(f"  Toplam metin: {len(metinler)}")

    # Sınıfa göre grupla
    siniflar = {}
    for m in metinler:
        sinif = str(m.get("sinif_seviyesi", "?"))
        siniflar.setdefault(sinif, []).append(m)

    sayac = {"yazildi": 0, "atlandi_mevcut": 0, "bos_icerik": 0}
    for sinif in sorted(siniflar):
        grup = siniflar[sinif]
        # Etiketlenecekler: zorluk yoksa (veya FORCE)
        hedef = [m for m in grup if FORCE or not m.get("zorluk")]
        atlanan = len(grup) - len(hedef)
        sayac["atlandi_mevcut"] += atlanan
        if not hedef:
            print(f"  Sınıf {sinif}: {len(grup)} metin — hepsi zaten etiketli, atlandı")
            continue
        skorlar = [okunabilirlik_skoru(m.get("icerik", "")) for m in hedef]
        etiketler = zorluk_dagit_gorece(skorlar)
        dagilim = {"kolay": 0, "orta": 0, "zor": 0}
        print(f"  Sınıf {sinif}: {len(hedef)} metin etiketlenecek (atlanan: {atlanan})")
        for m, skor, z in zip(hedef, skorlar, etiketler):
            dagilim[z] += 1
            if not m.get("icerik", "").strip():
                sayac["bos_icerik"] += 1
            print(f"     · {m.get('baslik','(başlıksız)')[:40]:40s} skor={skor:5.1f} → {z}")
            if APPLY:
                await db.analiz_metinler.update_one({"id": m["id"]}, {"$set": {"zorluk": z}})
            sayac["yazildi"] += 1
        print(f"     dağılım → kolay:{dagilim['kolay']} orta:{dagilim['orta']} zor:{dagilim['zor']}")

    print("\n─── ÖZET ───")
    print(f"  Etiketlenen : {sayac['yazildi']}")
    print(f"  Atlanan (zaten etiketli): {sayac['atlandi_mevcut']}")
    if sayac["bos_icerik"]:
        print(f"  ⚠ Boş içerikli metin: {sayac['bos_icerik']} (skor=0, kolay olabilir)")
    if not APPLY:
        print("\n  ⚠  DRY-RUN: hiçbir şey yazılmadı. Uygulamak için: --apply")
    print("═══ TAMAMLANDI ═══")


if __name__ == "__main__":
    asyncio.run(main())
