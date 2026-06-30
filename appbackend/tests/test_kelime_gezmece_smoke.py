"""Kelime Gezmece smoke testi (pytest DEĞİL — doğrudan python ile çalıştırılır).

Çalıştırma (Windows):
    cd appbackend
    set PYTHONIOENCODING=utf-8 && .venv/Scripts/python.exe tests/test_kelime_gezmece_smoke.py

Kapsam:
  - bulmaca_olusturucu içerik üretiyor mu (her sınıf için)
  - Doğru kelime → "grid"
  - Geçersiz kelime → "gecersiz"
  - Bonus durumu → "bonus"
  - Kelime havuzu sınıf filtreleri
"""
import os
import sys
import random

# appbackend kökünü path'e ekle (core importları için)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.bulmaca_olusturucu import bulmaca_uret, kelime_dogrula, _turetilebilir_mi
from core.turkce_kelime_havuzu import (
    sinif_kelimeleri, gecerli_mi, kelime_seti, tr_kucuk,
)
from collections import Counter

basari = 0
toplam = 0


def kontrol(ad, kosul):
    global basari, toplam
    toplam += 1
    if kosul:
        basari += 1
        print(f"  ✓ {ad}")
    else:
        print(f"  ✗ {ad}  <-- BAŞARISIZ")


def test_havuz():
    print("\n[1] Kelime havuzu")
    for s in range(1, 9):
        kelimeler = sinif_kelimeleri(s)
        kontrol(f"sınıf {s}: {len(kelimeler)} kelime (>0)", len(kelimeler) > 0)
    # Küçük sınıf yalnızca kısa kelime
    kontrol("sınıf 1 kelimeleri en çok 4 harf", all(len(k) <= 4 for k in sinif_kelimeleri(1)))
    kontrol("sınıf 8 daha çok kelime içerir (kümülatif)",
            len(sinif_kelimeleri(8)) >= len(sinif_kelimeleri(1)))
    kontrol("tr_kucuk('İLMEK') == 'ilmek'", tr_kucuk("İLMEK") == "ilmek")
    kontrol("'elma' sınıf 1 havuzunda geçerli", gecerli_mi("ELMA", 1))


def test_uretim():
    print("\n[2] Bulmaca üretimi")
    for s in (1, 3, 5, 7):
        b = bulmaca_uret(s)
        kontrol(f"sınıf {s}: harf_havuzu dolu", len(b.get("harf_havuzu", [])) >= 3)
        kontrol(f"sınıf {s}: grid 2D dizi", isinstance(b.get("grid"), list) and b["grid"] and isinstance(b["grid"][0], list))
        kontrol(f"sınıf {s}: en az 1 grid kelimesi", len(b.get("kelimeler", [])) >= 1)
        kontrol(f"sınıf {s}: tema (ad+emoji+renk)",
                all(k in b.get("tema", {}) for k in ("ad", "emoji", "ana_renk_hex")))
        # Grid kelimeleri havuzdan türetilebilmeli
        sayac = Counter(tr_kucuk("".join(b["harf_havuzu"])))
        kontrol(f"sınıf {s}: grid kelimeleri havuzdan türetilebilir",
                all(_turetilebilir_mi(tr_kucuk(k["kelime"]), sayac) for k in b["kelimeler"]))
        # Her grid kelimesinin baslangic/yon alanı olmalı
        kontrol(f"sınıf {s}: grid kelime şeması tam",
                all({"kelime", "yon", "baslangic", "uzunluk"} <= set(k) for k in b["kelimeler"]))


def test_dogrulama():
    print("\n[3] Kelime doğrulama")
    random.seed(42)
    b = bulmaca_uret(3)
    grid_kelime = b["kelimeler"][0]["kelime"]
    durum, puan = kelime_dogrula(b, grid_kelime, 3)
    kontrol(f"grid kelimesi '{grid_kelime}' → 'grid' (+10)", durum == "grid" and puan == 10)

    durum, puan = kelime_dogrula(b, "zzqx", 3)
    kontrol("geçersiz 'zzqx' → 'gecersiz' (0)", durum == "gecersiz" and puan == 0)

    durum, puan = kelime_dogrula(b, "", 3)
    kontrol("boş kelime → 'gecersiz'", durum == "gecersiz" and puan == 0)

    # Bonus: önceden hesaplanmış bonus listesi varsa onu test et,
    # yoksa havuzdan türetilebilen ama grid'de olmayan bir kelime ara.
    bonus_listesi = b.get("bonus_kelimeler", [])
    if bonus_listesi:
        durum, puan = kelime_dogrula(b, bonus_listesi[0], 3)
        kontrol(f"bonus '{bonus_listesi[0]}' → 'bonus' (+15)", durum == "bonus" and puan == 15)
    else:
        # Türetilebilen, sınıf havuzunda olan, grid'de OLMAYAN bir kelime bul
        sayac = Counter(tr_kucuk("".join(b["harf_havuzu"])))
        grid_set = {tr_kucuk(k["kelime"]) for k in b["kelimeler"]}
        aday = next((w for w in kelime_seti(3)
                     if _turetilebilir_mi(w, sayac) and w not in grid_set), None)
        if aday:
            durum, puan = kelime_dogrula(b, aday, 3)
            kontrol(f"türetilebilir bonus '{aday}' → 'bonus' (+15)", durum == "bonus" and puan == 15)
        else:
            kontrol("bonus testi (atlandı — uygun aday yok)", True)


def test_motor_entegrasyon():
    print("\n[4] Egzersiz tipi kaydı")
    from core.egzersiz_tipleri import tip_var_mi, tip_meta
    kontrol("kelime_gezmece tipi kayıtlı", tip_var_mi("kelime_gezmece"))
    meta = tip_meta("kelime_gezmece")
    kontrol("puanlama 'serbest'", meta.get("puanlama") == "serbest")
    kontrol("icerik_uretici 'bulmaca'", meta.get("icerik_uretici") == "bulmaca")
    from core.egzersiz_prompts import prompt_var_mi, mock_uret
    kontrol("prompt kaydı var", prompt_var_mi("kelime_gezmece"))
    mock = mock_uret("kelime_gezmece", 3, None, 1)
    kontrol("mock üretici bulmaca döndürüyor", "harf_havuzu" in mock and "grid" in mock)


if __name__ == "__main__":
    print("=" * 60)
    print("KELIME GEZMECE SMOKE TEST")
    print("=" * 60)
    test_havuz()
    test_uretim()
    test_dogrulama()
    test_motor_entegrasyon()
    print("\n" + "=" * 60)
    print(f"SONUÇ: {basari}/{toplam} kontrol geçti")
    print("=" * 60)
    sys.exit(0 if basari == toplam else 1)
