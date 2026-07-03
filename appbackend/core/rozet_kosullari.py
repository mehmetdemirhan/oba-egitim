"""Rozet koşulları — veri-odaklı koşul tanımları (tek doğruluk kaynağı).

ilerleme.py:rozet_kontrol içindeki sabit if-else koşulları buraya birebir
çevrildi. Hem migration (scripts/migrate_rozetler.py) hem de motor fallback'i
(core.rozet_motor) bu haritayı kullanır.

Koşul formatı:
    {"metrik": <str>, "operator": ">="|">"|"=="|"<="|"<", "esik": <sayı>,
     "ve": [ {alt koşul}, ... ]  # OPSİYONEL — hepsi AND ile bağlanır
    }

Bileşik (AND) koşullar için "ve" listesi kullanılır (ör. gorev_20, veli_*).
Manuel rozetler için: {"metrik": "manuel", "operator": None, "esik": None}.
"""

# ─────────────────────────────────────────────
# ÖĞRETMEN ROZET KOŞULLARI
# ─────────────────────────────────────────────
OGRETMEN_KOSULLARI = {
    # İçerik
    "icerik_ilk": {"metrik": "icerik_sayisi", "operator": ">=", "esik": 1},
    "icerik_5":   {"metrik": "icerik_sayisi", "operator": ">=", "esik": 5},
    "icerik_20":  {"metrik": "icerik_sayisi", "operator": ">=", "esik": 20},
    "icerik_50":  {"metrik": "icerik_sayisi", "operator": ">=", "esik": 50},
    # Kalite (oy)
    "oy_ilk": {"metrik": "kalite_oyu", "operator": ">=", "esik": 1},
    "oy_20":  {"metrik": "kalite_oyu", "operator": ">=", "esik": 20},
    "oy_50":  {"metrik": "kalite_oyu", "operator": ">=", "esik": 50},
    # Eğitimci (görev atama)
    "gorev_ilk": {"metrik": "gorev_atama_sayisi", "operator": ">=", "esik": 1},
    "gorev_20":  {"metrik": "gorev_atama_sayisi", "operator": ">=", "esik": 20,
                  "ve": [{"metrik": "gorev_tamamlanan", "operator": ">=", "esik": 10}]},
    "ilham_veren":     {"metrik": "ogrenci_ort_streak", "operator": ">=", "esik": 7},
    "yildiz_egitimci": {"metrik": "ogrenci_ort_streak", "operator": ">=", "esik": 10},
    # Kur atlatma
    "kur_ilk": {"metrik": "kur_atlama_sayisi", "operator": ">=", "esik": 1},
    "kur_20":  {"metrik": "kur_atlama_sayisi", "operator": ">=", "esik": 20},
    "kur_30":  {"metrik": "kur_atlama_sayisi", "operator": ">=", "esik": 30},
    "kur_50":  {"metrik": "kur_atlama_sayisi", "operator": ">=", "esik": 50},
    "kur_100": {"metrik": "kur_atlama_sayisi", "operator": ">=", "esik": 100},
    # Veli değerlendirme (bileşik)
    "veli_ilk": {"metrik": "veli_anket_sayisi", "operator": ">=", "esik": 1,
                 "ve": [{"metrik": "veli_anket_ort", "operator": ">=", "esik": 4}]},
    "veli_20":  {"metrik": "veli_anket_sayisi", "operator": ">=", "esik": 20,
                 "ve": [{"metrik": "veli_anket_ort", "operator": ">=", "esik": 4.5}]},
    "veli_30":  {"metrik": "veli_anket_sayisi", "operator": ">=", "esik": 30,
                 "ve": [{"metrik": "veli_anket_ort", "operator": ">=", "esik": 4.5},
                        {"metrik": "veli_tavsiye_orani", "operator": ">=", "esik": 90}]},
    "veli_100": {"metrik": "veli_anket_sayisi", "operator": ">=", "esik": 100,
                 "ve": [{"metrik": "veli_anket_ort", "operator": ">=", "esik": 4.8},
                        {"metrik": "veli_tavsiye_orani", "operator": ">=", "esik": 95}]},
    # Gelişim
    "gelisim_ilk":   {"metrik": "gelisim_tamamlama", "operator": ">=", "esik": 1},
    "gelisim_10":    {"metrik": "gelisim_tamamlama", "operator": ">=", "esik": 10},
    "gelisim_uzman": {"metrik": "gelisim_tamamlama", "operator": ">=", "esik": 30},
    # İletişim
    "mesaj_ilk":    {"metrik": "mesaj_sayisi", "operator": ">=", "esik": 1},
    "kopru_kurucu": {"metrik": "mesaj_ogrenci_veli_kopru", "operator": ">=", "esik": 1},
    # Egzersiz
    "egz_ilk":    {"metrik": "egzersiz_tur_sayisi", "operator": ">=", "esik": 1},
    "egz_tamset": {"metrik": "egzersiz_tur_sayisi", "operator": ">=", "esik": 14},
}

# ─────────────────────────────────────────────
# ÖĞRENCİ ROZET KOŞULLARI
# ─────────────────────────────────────────────
OGRENCI_KOSULLARI = {
    # Okuma (dakika)
    "okuma_ilk":  {"metrik": "okuma_kayit_sayisi", "operator": ">=", "esik": 1},
    "okuma_100":  {"metrik": "okuma_dakikasi", "operator": ">=", "esik": 100},
    "okuma_500":  {"metrik": "okuma_dakikasi", "operator": ">=", "esik": 500},
    "okuma_2000": {"metrik": "okuma_dakikasi", "operator": ">=", "esik": 2000},
    # Streak (giriş serisi)
    "streak_3":  {"metrik": "giris_serisi", "operator": ">=", "esik": 3},
    "streak_7":  {"metrik": "giris_serisi", "operator": ">=", "esik": 7},
    "streak_21": {"metrik": "giris_serisi", "operator": ">=", "esik": 21},
    "streak_60": {"metrik": "giris_serisi", "operator": ">=", "esik": 60},
    # Kitap (farklı kitap sayısı)
    "kitap_1":  {"metrik": "kitap_sayisi", "operator": ">=", "esik": 1},
    "kitap_5":  {"metrik": "kitap_sayisi", "operator": ">=", "esik": 5},
    "kitap_15": {"metrik": "kitap_sayisi", "operator": ">=", "esik": 15},
    "kitap_30": {"metrik": "kitap_sayisi", "operator": ">=", "esik": 30},
    # Görev (tamamlanan)
    "gorev_ilk": {"metrik": "gorev_tamamlama", "operator": ">=", "esik": 1},
    "gorev_10":  {"metrik": "gorev_tamamlama", "operator": ">=", "esik": 10},
    "gorev_30":  {"metrik": "gorev_tamamlama", "operator": ">=", "esik": 30},
    "gorev_100": {"metrik": "gorev_tamamlama", "operator": ">=", "esik": 100},
    # Egzersiz
    "egz_ilk": {"metrik": "egzersiz_sayisi", "operator": ">=", "esik": 1},
    "egz_20":  {"metrik": "egzersiz_sayisi", "operator": ">=", "esik": 20},
    "egz_14":  {"metrik": "egzersiz_tur_sayisi", "operator": ">=", "esik": 14},
    # Orman (1 dk okuma = 1 ağaç)
    "orman_ilk": {"metrik": "orman_agac_sayisi", "operator": ">=", "esik": 1},
    "orman_50":  {"metrik": "orman_agac_sayisi", "operator": ">=", "esik": 50},
    "orman_200": {"metrik": "orman_agac_sayisi", "operator": ">=", "esik": 200},
    # Lig (toplam XP)
    "lig_gumus": {"metrik": "lig_xp", "operator": ">=", "esik": 200},
    "lig_altin": {"metrik": "lig_xp", "operator": ">=", "esik": 500},
    "lig_elmas": {"metrik": "lig_xp", "operator": ">=", "esik": 1000},
}

# Metrik → insan-okunur açıklama (admin panel dropdown + doküman için)
METRIK_ACIKLAMALARI = {
    # öğretmen
    "icerik_sayisi": "Yayınlanan içerik sayısı",
    "kalite_oyu": "Verilen kalite oyu sayısı",
    "gorev_atama_sayisi": "Atanan görev sayısı",
    "gorev_tamamlanan": "Öğrencilerin tamamladığı görev sayısı",
    "ogrenci_ort_streak": "Öğrencilerin ortalama okuma serisi (gün)",
    "kur_atlama_sayisi": "Öğrencilere atlattığı kur sayısı",
    "veli_anket_sayisi": "Alınan veli anketi sayısı",
    "veli_anket_ort": "Veli anketi ortalama puanı (5 üzerinden)",
    "veli_tavsiye_orani": "Veli tavsiye oranı (%)",
    "gelisim_tamamlama": "Tamamlanan gelişim modülü sayısı",
    "mesaj_sayisi": "Gönderilen mesaj sayısı",
    "mesaj_ogrenci_veli_kopru": "Hem öğrenci hem veliye mesaj (1=evet)",
    # öğrenci
    "okuma_kayit_sayisi": "Okuma kaydı sayısı",
    "okuma_dakikasi": "Toplam okuma dakikası",
    "giris_serisi": "Ardışık okuma günü (streak)",
    "kitap_sayisi": "Okunan farklı kitap sayısı",
    "gorev_tamamlama": "Tamamlanan görev sayısı",
    "egzersiz_sayisi": "Tamamlanan egzersiz sayısı",
    "egzersiz_tur_sayisi": "Farklı egzersiz türü sayısı",
    "orman_agac_sayisi": "Orman ağaç sayısı (1 dk okuma = 1 ağaç)",
    "lig_xp": "Toplam XP (lig puanı)",
    # ortak
    "manuel": "Manuel verilir (admin)",
}


def kosul_getir(rol: str, kod: str) -> dict:
    """rol+kod için koşul döner; tanımsızsa manuel kabul edilir."""
    tablo = OGRETMEN_KOSULLARI if rol == "teacher" else OGRENCI_KOSULLARI
    return tablo.get(kod, {"metrik": "manuel", "operator": None, "esik": None})
