"""Metin okunabilirlik/zorluk sezgiseli — Kutulu Okuma metin seçimi için.

analiz_metinler koleksiyonundaki metinlere `zorluk ∈ {kolay, orta, zor}` etiketi
üretir. İki kullanım:
  - create_metin (tek yeni metin): mutlak eşikle `zorluk_hesapla(icerik)`.
  - backfill script (havuzun tamamı): sınıf içinde göreli sıralama (tercile) ile
    her sınıfa kolay/orta/zor dağılımı — kur bazlı seçim anlamlı olsun diye.

Sezgisel Türkçe metne göre kabadır ama yeterlidir: uzun kelimeler (çok heceli) ve
uzun cümleler zorluğu artırır. Kesin dilbilimsel ölçüm değildir.
"""
import re

ZORLUKLAR = ("kolay", "orta", "zor")

# create_metin (tek metin) için mutlak eşikler — okunabilirlik skoruna göre.
_ESIK_KOLAY = 8.5
_ESIK_ZOR = 11.5


def okunabilirlik_skoru(icerik: str) -> float:
    """Metnin okunabilirlik skoru (yüksek = daha zor). ortalama kelime uzunluğu +
    ağırlıklı ortalama cümle uzunluğu."""
    if not icerik or not icerik.strip():
        return 0.0
    kelimeler = icerik.split()
    n_kelime = len(kelimeler)
    if n_kelime == 0:
        return 0.0
    # Cümle sayısı: . ! ? … ayraçları
    cumleler = [c for c in re.split(r"[.!?…]+", icerik) if c.strip()]
    n_cumle = max(1, len(cumleler))
    ort_kelime_uzunluk = sum(len(k) for k in kelimeler) / n_kelime
    ort_cumle_uzunluk = n_kelime / n_cumle
    return ort_kelime_uzunluk + 0.35 * ort_cumle_uzunluk


def zorluk_hesapla(icerik: str) -> str:
    """Tek metin için mutlak eşikle zorluk etiketi (create_metin akışı)."""
    skor = okunabilirlik_skoru(icerik)
    if skor < _ESIK_KOLAY:
        return "kolay"
    if skor > _ESIK_ZOR:
        return "zor"
    return "orta"


def zorluk_dagit_gorece(skorlar: list) -> list:
    """Aynı sınıftaki metinlerin skor listesini alıp göreli tercile ile
    kolay/orta/zor dağıtır. Girdi sırasını koruyarak etiket listesi döner.

    - 1 metin  → ["orta"]
    - 2 metin  → ["kolay", "zor"]
    - 3+ metin → alt üçte bir kolay, orta üçte bir orta, üst üçte bir zor
    """
    n = len(skorlar)
    if n == 0:
        return []
    if n == 1:
        return ["orta"]
    if n == 2:
        # düşük skor kolay, yüksek skor zor
        return ["kolay", "zor"] if skorlar[0] <= skorlar[1] else ["zor", "kolay"]
    # Sıralı indeksler; tercile sınırları
    sirali = sorted(range(n), key=lambda i: skorlar[i])
    etiketler = [None] * n
    for rank, idx in enumerate(sirali):
        oran = rank / n  # 0..1
        etiketler[idx] = "kolay" if oran < 1 / 3 else ("orta" if oran < 2 / 3 else "zor")
    return etiketler
