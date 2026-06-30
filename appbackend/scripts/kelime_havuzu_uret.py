"""Türkçe sınıf bazlı kelime havuzu — tek seferlik üretim / denetim scripti.

core/turkce_kelime_havuzu.py içindeki MASTER_KELIMELER listesini büyütmek için
yardımcıdır. İki modu vardır:

  1. --denetle (varsayılan): mevcut havuzun istatistiklerini gösterir, tekrarları
     ve şüpheli (çok uzun/boş) kelimeleri listeler. AI/ağ gerekmez.

  2. --ai "5. sınıf 30 yaygın kelime": Gemini'den (varsa) sınıf seviyesine uygun
     yeni kelime önerileri ister ve EKRANA basar. Otomatik dosyaya YAZMAZ —
     öğretmen/geliştirici çıktıyı gözden geçirip MASTER_KELIMELER'e elle ekler
     (TDK uyumu ve çocuk dostu kontrolü için kasıtlı manuel adım).

Çalıştırma (appbackend dizininde):
    set PYTHONIOENCODING=utf-8
    .venv\\Scripts\\python.exe scripts\\kelime_havuzu_uret.py --denetle
    .venv\\Scripts\\python.exe scripts\\kelime_havuzu_uret.py --ai "3. sinif 25 yaygin somut kelime"

NOT: Üretim çalışma zamanında ASLA çağrılmaz; oyun içeriği tamamen yereldir.
"""
import argparse
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.turkce_kelime_havuzu import (  # noqa: E402
    MASTER_KELIMELER, tum_kelimeler, sinif_kelimeleri, SINIF_MAX_UZUNLUK, tr_kucuk,
)


def denetle():
    print("=" * 56)
    print("KELIME HAVUZU DENETİMİ")
    print("=" * 56)
    ham = [tr_kucuk(k.strip()) for k in MASTER_KELIMELER if k.strip()]
    benzersiz = tum_kelimeler()
    print(f"Ham giriş     : {len(ham)}")
    print(f"Benzersiz     : {len(benzersiz)}")

    tekrar = [k for k, n in Counter(ham).items() if n > 1]
    if tekrar:
        print(f"\n⚠ Tekrarlanan {len(tekrar)} kelime: {', '.join(sorted(tekrar))}")
    else:
        print("\n✓ Tekrar yok.")

    suspheli = [k for k in benzersiz if len(k) < 2 or len(k) > 8]
    if suspheli:
        print(f"⚠ Şüpheli uzunluk ({len(suspheli)}): {', '.join(suspheli)}")

    print("\nUzunluk dağılımı:")
    dag = Counter(len(k) for k in benzersiz)
    for u in sorted(dag):
        print(f"  {u} harf: {dag[u]}")

    print("\nSınıf havuzu boyutları:")
    for s in range(1, 9):
        print(f"  sınıf {s} (≤{SINIF_MAX_UZUNLUK[s]} harf): {len(sinif_kelimeleri(s))} kelime")


def ai_oner(istek: str):
    """Gemini ile yeni kelime önerileri al (varsa). Sadece ekrana basar."""
    try:
        import asyncio
        from core.ai import call_claude
    except Exception as ex:
        print(f"AI modülü yüklenemedi: {ex}")
        return

    system = (
        "Sen Türkçe ilkokul/ortaokul öğretmeni asistanısın. Yalnızca TDK uyumlu, "
        "çocuk dostu, somut ve yaygın Türkçe kelimeler öner. Argo/teknik terim yok."
    )
    user = (
        f"{istek}. Sadece kelimeleri küçük harfle, virgülle ayırarak tek satırda ver. "
        "Açıklama, numara veya başka metin EKLEME."
    )

    async def _calistir():
        res = await call_claude(system, user, max_tokens=800)
        metin = (res.get("text") or "").strip()
        if not metin:
            print("AI boş yanıt döndürdü (kota/anahtar?).")
            return
        kelimeler = [tr_kucuk(k.strip()) for k in metin.replace("\n", ",").split(",")]
        kelimeler = [k for k in kelimeler if k and k.isalpha() or "ğ" in k or "ı" in k]
        mevcut = set(tum_kelimeler())
        yeni = sorted({k for k in kelimeler if k and k not in mevcut and 2 <= len(k) <= 8})
        print("\nÖNERİLEN YENİ KELİMELER (elle MASTER_KELIMELER'e ekleyin):")
        print(", ".join(f'"{k}"' for k in yeni))
        print(f"\n({len(yeni)} yeni / {len(kelimeler)} öneri)")

    asyncio.run(_calistir())


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Türkçe kelime havuzu üretim/denetim")
    ap.add_argument("--ai", metavar="ISTEK", help="Gemini'den kelime öner (örn. '3. sinif 25 kelime')")
    ap.add_argument("--denetle", action="store_true", help="Havuz istatistiklerini göster")
    args = ap.parse_args()

    if args.ai:
        ai_oner(args.ai)
    else:
        denetle()
