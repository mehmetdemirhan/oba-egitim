"""Egzersiz içerik cache ön-doldurma (pre-warm) scripti.

Tüm aktif egzersiz tiplerini, destekledikleri sınıf aralığında AI ile üretip
`egzersiz_icerikler` koleksiyonuna kaydeder. Böylece öğrenci bir egzersizi ilk
açtığında AI beklemesi olmaz; içerik cache'ten anında gelir.

Çalıştırma (appbackend dizininde):
    .venv\\Scripts\\python.exe scripts\\egzersiz_cache_doldur.py
    .venv\\Scripts\\python.exe scripts\\egzersiz_cache_doldur.py --adet 3 --tip anagram

Özellikler:
  - Yeniden çalıştırılabilir: yeterli (gerçek, mock OLMAYAN) içeriği olan
    (tip, sınıf) ikilileri atlanır → kaldığı yerden devam.
  - Gemini kotası dolup AI mock döndürmeye başlarsa script güvenli durur;
    kota yenilenince tekrar çalıştırılır (zaten üretilmiş içerikler atlanır).
  - Her AI çağrısı arasında bekleme (varsayılan 1.5 sn) → kota koruması.
  - AI anahtarı hiç yoksa mock içerik üretip kaydeder (sistem yine de çalışır).

Türkçe çıktı için Windows'ta: set PYTHONIOENCODING=utf-8
"""
import argparse
import asyncio
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Not: core.db, import anında bir Motor/GridFS istemcisi kurar ve çalışan bir
# event loop ister. Bu yüzden db'ye dokunan importlar event loop başladıktan
# SONRA, async gövde içinde yapılır (smoke testlerdeki desenin aynısı).
from core.config import (  # noqa: E402
    DB_NAME, GEMINI_API_KEY, GEMINI_API_KEY_2, GEMINI_API_KEY_3,
)

HEDEF_ADET = 2            # (tip, sınıf) başına hedef GERÇEK içerik sayısı
BEKLEME_SN = 1.5         # her AI çağrısı arası bekleme (kota koruması)
ARDISIK_HATA_SINIRI = 6  # bu kadar ardışık mock/hata → kota bitti say, dur

# Önyükleme ile üretilen içeriklerin "üreten" kimliği (kütüphanede görünür).
PREWARM_OLUSTURAN = {"id": "system_prewarm", "ad": "Sistem (Önyükleme)", "rol": "system"}

AI_VAR = bool(GEMINI_API_KEY or GEMINI_API_KEY_2 or GEMINI_API_KEY_3)


async def _mevcut_gercek_sayi(db, tip: str, sinif: int) -> int:
    """(tip, sınıf) için kayıtlı, mock OLMAYAN içerik sayısı."""
    return await db.egzersiz_icerikler.count_documents(
        {"tip": tip, "sinif": sinif, "mock": {"$ne": True}}
    )


async def calistir(hedef_adet: int, sadece_tip: str | None):
    # Event loop artık çalışıyor → db'ye dokunan modülleri burada import et.
    from core.db import db, client
    from core.egzersiz_tipleri import EGZERSIZ_TIPLERI
    from modules.egzersiz_motoru import _icerik_uret, _icerik_kaydet

    print("=== Egzersiz Cache Ön-Doldurma ===")
    print(f"DB: {DB_NAME} | AI anahtarı: {'VAR' if AI_VAR else 'YOK (mock üretilecek)'}")
    print(f"Hedef: (tip, sınıf) başına {hedef_adet} içerik | çağrı arası bekleme {BEKLEME_SN}s\n")

    if sadece_tip and sadece_tip not in EGZERSIZ_TIPLERI:
        print(f"[HATA] Bilinmeyen tip: {sadece_tip}")
        return 0

    basla = time.time()
    uretilen = 0          # kaydedilen içerik sayısı
    atlanan_dolu = 0      # zaten yeterli içeriği olan (tip,sınıf) sayısı
    hata = 0              # mock/exception ile atlanan çağrı
    ardisik_hata = 0
    durduruldu = False

    for tip, meta in EGZERSIZ_TIPLERI.items():
        if sadece_tip and tip != sadece_tip:
            continue
        smin = int(meta.get("sinif_min", 1))
        smax = int(meta.get("sinif_max", 8))
        for sinif in range(smin, smax + 1):
            mevcut = await _mevcut_gercek_sayi(db, tip, sinif)
            if mevcut >= hedef_adet:
                atlanan_dolu += 1
                continue

            # Bu (tip,sınıf) için mevcut bir varyant grubu varsa onu kullan;
            # yoksa ilk üretilen orijinal olur ve grubu kendi id'si olur.
            mevcut_doc = await db.egzersiz_icerikler.find_one({"tip": tip, "sinif": sinif})
            grup = (mevcut_doc.get("varyant_grubu") or mevcut_doc.get("id")) if mevcut_doc else None

            for _ in range(hedef_adet - mevcut):
                try:
                    icerik, mock = await _icerik_uret(tip, sinif, None, None)
                except Exception as ex:  # beklenmeyen hata → atla
                    hata += 1
                    ardisik_hata += 1
                    print(f"  [HATA] {tip} s{sinif}: {str(ex)[:80]}")
                    if ardisik_hata >= ARDISIK_HATA_SINIRI:
                        durduruldu = True
                        break
                    continue

                if mock and AI_VAR:
                    # AI anahtarı var ama mock döndü → büyük olasılıkla kota/limit.
                    # Mock'u KAYDETME (cache'i kirletmesin); say ve eşiğe gelince dur.
                    hata += 1
                    ardisik_hata += 1
                    print(f"  [MOCK] {tip} s{sinif}: AI mock döndü (kota?) — kaydedilmedi.")
                    if ardisik_hata >= ARDISIK_HATA_SINIRI:
                        durduruldu = True
                        break
                    await asyncio.sleep(BEKLEME_SN)
                    continue

                yeni = await _icerik_kaydet(
                    tip, sinif, None, None, icerik, "cache_prewarm", mock,
                    kaynak="prewarm", olusturan=PREWARM_OLUSTURAN, varyant_grubu=grup,
                )
                if grup is None:  # ilk üretilen orijinal → sonrakiler bu gruba girer
                    grup = yeni["id"]
                uretilen += 1
                ardisik_hata = 0
                etiket = "mock" if mock else "AI"
                print(f"  [OK]  {tip} s{sinif} ({etiket}) — üretilen toplam: {uretilen}")
                await asyncio.sleep(BEKLEME_SN)

            if durduruldu:
                break
        if durduruldu:
            break

    sure = round(time.time() - basla, 1)
    print("\n=== ÖZET ===")
    print(f"Üretilen içerik       : {uretilen}")
    print(f"Atlanan (zaten dolu)  : {atlanan_dolu} (tip,sınıf) ikilisi")
    print(f"Hata/mock atlanan     : {hata} çağrı")
    print(f"Süre                  : {sure} sn (~{round(sure / 60, 1)} dk)")
    if durduruldu:
        print("\n[UYARI] Ardışık hata/kota nedeniyle DURDURULDU.")
        print("        Kota yenilenince scripti tekrar çalıştırın; tamamlanmış")
        print("        (tip,sınıf) ikilileri atlanacaktır.")
    else:
        print("\n[OK] Tamamlandı.")

    client.close()
    return uretilen


def main():
    ap = argparse.ArgumentParser(description="Egzersiz cache ön-doldurma")
    ap.add_argument("--adet", type=int, default=HEDEF_ADET,
                    help="(tip,sınıf) başına hedef içerik sayısı (varsayılan 2)")
    ap.add_argument("--tip", type=str, default=None,
                    help="yalnızca bu egzersiz tipini doldur (örn. anagram)")
    args = ap.parse_args()
    asyncio.run(calistir(args.adet, args.tip))


if __name__ == "__main__":
    main()
