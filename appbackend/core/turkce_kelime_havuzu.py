"""Sınıf seviyesine göre Türkçe kelime havuzu (Kelime Gezmece için).

Bu havuz, çapraz bulmaca üretimi (core/bulmaca_olusturucu.py) ve kelime doğrulama
için kullanılır. Kelimeler TDK uyumlu, çocuk dostu; argo/teknik terim içermez.

Tasarım:
  - `MASTER_KELIMELER`: tüm sınıflarda kullanılabilen geniş ortak liste (çoğunlukla
    2-7 harf, sık kullanılan, somut kelimeler). Çapraz bulmaca kısa kelimelerle
    çalıştığı için ağırlık kısa kelimelerdedir.
  - Sınıf seviyesi, kelime UZUNLUĞU ile ölçeklenir: küçük sınıflar yalnızca kısa
    kelimeleri görür, büyük sınıflar daha uzunları da görür (kümülatif).

Genişletme: scripts/kelime_havuzu_uret.py ile AI'dan yeni kelimeler türetip bu
listeye elle eklenebilir. Üretim tek seferliktir; çalışma zamanında AI çağrılmaz.
"""
from __future__ import annotations

# Türkçe küçük harfe çevirme (I/İ özel durumu)
_TR_BUYUK = "ABCÇDEFGĞHIİJKLMNOÖPRSŞTUÜVYZ"
_TR_KUCUK = "abcçdefgğhıijklmnoöprsştuüvyz"
_CEVIRI = {b: k for b, k in zip(_TR_BUYUK, _TR_KUCUK)}


def tr_kucuk(s: str) -> str:
    """Türkçe kurallarına uygun küçük harfe çevirir (İ→i, I→ı)."""
    return "".join(_CEVIRI.get(ch, ch.lower()) for ch in (s or ""))


# ─────────────────────────────────────────────────────────────
# Ana kelime listesi — sık kullanılan, somut, çocuk dostu Türkçe kelimeler.
# (Bilinçli olarak kısa kelime ağırlıklı; çapraz bulmaca için ideal.)
# ─────────────────────────────────────────────────────────────
MASTER_KELIMELER: list[str] = [
    # 2 harf
    "ev", "su", "el", "al", "at", "ot", "un", "ay", "ad", "ak", "ek", "en",
    "et", "ip", "iz", "ok", "oy", "ya", "ye", "is", "us", "az", "ön", "üs",
    # 3 harf — hayvanlar, doğa, nesneler
    "kuş", "baş", "taş", "diş", "kaş", "saç", "göz", "söz", "toz", "buz",
    "kız", "yüz", "can", "kan", "ana", "ata", "ada", "oda", "top", "kap",
    "sap", "tas", "kar", "nar", "bal", "dal", "gül", "göl", "kol", "yol",
    "bel", "sel", "tel", "yel", "dil", "fil", "kil", "pul", "kul", "gün",
    "dün", "yün", "tuz", "kül", "boş", "koş", "düş", "saz", "köy", "ses",
    "tat", "kek", "bez", "kürk", "arı", "inek", "kuyu", "süt",
    # 4 harf — daha çok somut isim
    "elma", "armut", "masa", "kapı", "araba", "kalem", "okul", "deniz",
    "kitap", "çiçek", "bulut", "yağmur", "kuzu", "balık", "kedi", "köpek",
    "tavşan", "ördek", "horoz", "tavuk", "kelebek", "karınca", "böcek",
    "ağaç", "yaprak", "orman", "çimen", "tohum", "filiz", "meyve", "sebze",
    "domates", "biber", "patates", "soğan", "havuç", "salata", "ekmek",
    "peynir", "zeytin", "yumurta", "süt", "bal", "şeker", "tuzlu", "çorba",
    "yemek", "tabak", "kaşık", "çatal", "bardak", "şişe", "kova", "sepet",
    "top", "balon", "uçak", "tren", "gemi", "bisiklet", "kamyon", "otobüs",
    "ev", "bahçe", "çatı", "duvar", "pencere", "merdiven", "anahtar",
    "lamba", "halı", "yastık", "yatak", "dolap", "sandalye", "ayna",
    # Renkler
    "sarı", "mavi", "yeşil", "kırmızı", "mor", "pembe", "turuncu", "beyaz",
    "siyah", "gri", "kahve", "lacivert",
    # Vücut
    "el", "kol", "ayak", "bacak", "burun", "kulak", "ağız", "dudak",
    "parmak", "saç", "kaş", "yanak", "diz", "omuz", "boyun", "sırt",
    # Doğa / hava
    "güneş", "ay", "yıldız", "gökyüzü", "rüzgar", "kar", "buz", "sis",
    "şimşek", "gökkuşağı", "dağ", "tepe", "ova", "nehir", "göl", "deniz",
    "kum", "kaya", "mağara", "çöl", "ada", "kıyı", "dalga",
    # Okul
    "defter", "silgi", "cetvel", "boya", "çanta", "sınıf", "öğretmen",
    "öğrenci", "ders", "tahta", "harita", "küre", "soru", "cevap", "ödev",
    # Aile / kişiler
    "anne", "baba", "dede", "nine", "abla", "abi", "kardeş", "bebek",
    "teyze", "amca", "hala", "dayı", "komşu", "arkadaş", "çocuk", "insan",
    # Meslekler
    "doktor", "hemşire", "polis", "itfaiye", "aşçı", "terzi", "marangoz",
    "çiftçi", "balıkçı", "pilot", "şoför", "berber", "ressam", "müzisyen",
    # Spor / oyun
    "futbol", "voleybol", "basketbol", "yüzme", "koşu", "atlama", "salıncak",
    "kaydırak", "ip", "zıpzıp", "yapboz", "oyuncak", "kukla", "uçurtma",
    # Duygular / sıfatlar
    "mutlu", "üzgün", "kızgın", "neşeli", "yorgun", "uykulu", "aç", "tok",
    "büyük", "küçük", "uzun", "kısa", "geniş", "dar", "kalın", "ince",
    "sıcak", "soğuk", "ılık", "yumuşak", "sert", "hızlı", "yavaş", "güzel",
    "temiz", "kirli", "dolu", "boş", "yeni", "eski", "açık", "kapalı",
    # Zaman / mevsim
    "sabah", "öğle", "akşam", "gece", "bugün", "yarın", "dün", "hafta",
    "ilkbahar", "yaz", "sonbahar", "kış", "mevsim", "saat", "dakika",
    # Bilim / 5-8 sınıf
    "atom", "molekül", "enerji", "ışık", "ses", "kuvvet", "hareket",
    "gezegen", "uzay", "yörünge", "hücre", "doku", "organ", "iskelet",
    "kalp", "akciğer", "mide", "beyin", "kemik", "kas", "damar", "kan",
    "asit", "baz", "tuz", "karışım", "element", "bileşik", "mıknatıs",
    # Coğrafya / tarih / 5-8
    "kıta", "okyanus", "iklim", "tarım", "sanayi", "ticaret", "nüfus",
    "kanyon", "vadi", "yarımada", "körfez", "boğaz", "akarsu", "baraj",
    "tarih", "uygarlık", "destan", "efsane", "kale", "saray", "müze",
    "anıt", "heykel", "resim", "şiir", "roman", "hikaye", "masal",
    # Soyut / 7-8
    "bilgi", "düşünce", "mantık", "felsefe", "ahlak", "erdem", "özgürlük",
    "sorumluluk", "saygı", "sevgi", "dürüstlük", "adalet", "barış", "umut",
]


def _benzersiz_temiz(liste: list[str]) -> list[str]:
    """Boşları temizle, küçük harfe çevir, tekrarları kaldır, sırayı koru."""
    gorulen: set[str] = set()
    out: list[str] = []
    for k in liste:
        k = tr_kucuk(k.strip())
        if not k or k in gorulen:
            continue
        gorulen.add(k)
        out.append(k)
    return out


_MASTER = _benzersiz_temiz(MASTER_KELIMELER)


# Sınıf → izin verilen maksimum kelime uzunluğu (kümülatif zorluk).
# Küçük sınıflar yalnızca kısa kelimeleri görür.
SINIF_MAX_UZUNLUK = {1: 4, 2: 4, 3: 5, 4: 5, 5: 6, 6: 6, 7: 7, 8: 8}
MIN_UZUNLUK = 2


def sinif_kelimeleri(sinif: int) -> list[str]:
    """Verilen sınıf için uygun (uzunluk filtreli) kelime listesi."""
    ust = SINIF_MAX_UZUNLUK.get(int(sinif), 6)
    return [k for k in _MASTER if MIN_UZUNLUK <= len(k) <= ust]


def kelime_seti(sinif: int) -> set[str]:
    """Sınıf için kelime kümesi (hızlı doğrulama)."""
    return set(sinif_kelimeleri(sinif))


def gecerli_mi(kelime: str, sinif: int) -> bool:
    """Kelime, sınıf havuzunda var mı? (Türkçe küçük harfe normalize ederek)"""
    return tr_kucuk((kelime or "").strip()) in kelime_seti(sinif)


def tum_kelimeler() -> list[str]:
    """Tüm benzersiz master kelimeler."""
    return list(_MASTER)
