"""Toplu kayıt normalizasyon (core/kayit_normalize) birim smoke testi.

DB gerektirmez — saf fonksiyonlar. Görevdeki gerçek kirli veri örneklerini doğrular.
    cd appbackend
    .venv/Scripts/python.exe tests/test_kayit_normalize_smoke.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.kayit_normalize import (
    normalize_ad, ogretmen_eslestir, normalize_ogrenci_ad, normalize_sinif,
    normalize_kur, normalize_telefon, normalize_tarih, siniflandir_not,
)

_gecen = _kalan = 0


def check(kosul, mesaj):
    global _gecen, _kalan
    if kosul:
        _gecen += 1; print(f"  [GECTI] {mesaj}")
    else:
        _kalan += 1; print(f"  [KALDI] {mesaj}")


def run():
    # Ad normalize
    check(normalize_ad("kÜbra   özdemir") == "Kübra Özdemir", "ad normalize (kÜbra özdemir)")
    check(normalize_ad("PERİHAN") == "Perihan", "ad normalize (PERİHAN)")

    # Öğretmen eşleştirme
    ogr = [{"id": "1", "ad": "Seher", "soyad": "Akbaş"},
           {"id": "2", "ad": "Kübra", "soyad": "Özdemir"},
           {"id": "3", "ad": "Jülide Beren", "soyad": "Külahlı"}]
    check(ogretmen_eslestir("seher hocam", ogr)["en_iyi"]["id"] == "1", "'seher hocam' → Seher Akbaş")
    check(ogretmen_eslestir("kÜbra özdemir", ogr)["otomatik"] is True, "'kÜbra özdemir' otomatik eşleşir")
    check(ogretmen_eslestir("Jülide", ogr)["en_iyi"]["id"] == "3", "kısmi ad 'Jülide' → Jülide Beren Külahlı")
    check(ogretmen_eslestir("Kübra uzunçayır", ogr)["en_iyi"] is None or
          ogretmen_eslestir("Kübra uzunçayır", ogr)["otomatik"] is False, "'Kübra uzunçayır' otomatik DEĞİL")

    # Öğrenci adı
    check(normalize_ogrenci_ad("Ali Yılmaz")["gecerli"] is True, "geçerli öğrenci adı")
    check(normalize_ogrenci_ad("polat")["gecerli"] is False, "tek kelime → geçersiz (elle)")
    check(normalize_ogrenci_ad("?")["gecerli"] is False, "'?' → geçersiz")
    check(normalize_ogrenci_ad("amerika")["sebep"] == "yer_adi", "yer adı → geçersiz")

    # Sınıf
    check(normalize_sinif("3.sınıf") == 3 and normalize_sinif("8. Sınıf") == 8, "sınıf parse")
    check(normalize_sinif("sınıf") is None and normalize_sinif("?") is None, "çözülemeyen sınıf None")

    # Kur (çoklu)
    check(normalize_kur("2. Kur") == [2], "tek kur")
    check(normalize_kur("4. ve 5. kur") == [4, 5], "çift kur → [4,5]")

    # Telefon E.164
    check(normalize_telefon("05331397406")["e164"] == "+905331397406", "TR 0533… → +90")
    check(normalize_telefon("0 532 560 88 18")["e164"] == "+905325608818", "boşluklu TR")
    check(normalize_telefon("+90 542 558 14 90")["e164"] == "+905425581490", "+90 korunur")
    check(normalize_telefon("5052627395")["e164"] == "+905052627395", "10 haneli 5…")
    check(normalize_telefon("+15515746746")["e164"] == "+15515746746" and
          normalize_telefon("+15515746746")["gecerli"] is True, "ABD +1 korunur")
    check(normalize_telefon("abc")["gecerli"] is False, "geçersiz telefon işaretlenir")

    # Tarih
    check(normalize_tarih("16.09.2024 17:02:10") == "2024-09-16T17:02:00", "tarih+saat parse")
    check(normalize_tarih("29.11.0202") is None, "bozuk tarih → None")

    # Notlar sınıflandırma
    check(siniflandir_not("ödendi")["odeme_durumu"] == "odendi", "ödeme: ödendi")
    check(siniflandir_not("ödenmedi")["odeme_durumu"] == "odenmedi", "ödeme: ödenmedi")
    check(siniflandir_not("iptal")["odeme_durumu"] == "iptal", "ödeme: iptal")
    check(siniflandir_not("Disleksisi var")["egitim_notu"] != "", "hassas bilgi → eğitim notu")
    check(siniflandir_not("Disleksisi var")["odeme_durumu"] is None, "hassas bilgi muhasebeye YAZILMAZ")
    check(siniflandir_not("ramazandan sonra")["taksit_notu"] != "", "erteleme → taksit notu")
    check(siniflandir_not("veliyle görüşüldü")["aciklama"] == "veliyle görüşüldü", "serbest metin → açıklama")


if __name__ == "__main__":
    run()
    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    sys.exit(1 if _kalan else 0)
