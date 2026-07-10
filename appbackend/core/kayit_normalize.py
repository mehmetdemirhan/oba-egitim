"""Toplu kayıt içe-aktarımı — ham (kirli) veri normalizasyonu.

Kurumun Google Sheets kayıt listesindeki tutarsız verileri temizler. Tüm
fonksiyonlar SAFtır (yan etkisiz), böylece birim-test edilebilir ve içe-aktarım
motorundan bağımsız çalışır. Sonuçlar her zaman admin eşleştirme ekranında
onaydan geçer — bu modül yalnız ÖNERİ üretir.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from difflib import SequenceMatcher

_TR_MAP = str.maketrans("İIŞĞÜÖÇ", "iışğüöç")


def tr_kucuk(s: str) -> str:
    """Türkçe küçük harf (İ→i, I→ı)."""
    if not s:
        return ""
    return str(s).translate(_TR_MAP).lower().strip()


def _ascii_fold(s: str) -> str:
    """Karşılaştırma için Türkçe/aksanlı harfleri ASCII'ye indirger (ş→s, ı→i…)."""
    s = tr_kucuk(s)
    degis = {"ş": "s", "ğ": "g", "ü": "u", "ö": "o", "ç": "c", "ı": "i", "â": "a", "î": "i", "û": "u"}
    s = "".join(degis.get(ch, ch) for ch in s)
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", s).strip()


def normalize_ad(s: str) -> str:
    """Ad-soyadı temizler: fazla boşlukları kırpar, her kelimeyi Türkçe baş-harf
    büyük yapar. 'kÜbra   özdemir' → 'Kübra Özdemir'."""
    if not s:
        return ""
    s = re.sub(r"\s+", " ", str(s).strip())
    parcalar = []
    for kelime in s.split(" "):
        if not kelime:
            continue
        ilk = kelime[0].translate(str.maketrans("iı", "İI")).upper() if kelime[0] in "iı" else kelime[0].upper()
        parcalar.append(ilk + tr_kucuk(kelime[1:]))
    return " ".join(parcalar)


# ─────────────────────────── Öğretmen benzerlik eşleştirme ───────────────────────────
def ad_benzerlik(a: str, b: str) -> float:
    """İki adın benzerlik skoru (0-1). Türkçe/büyük-küçük duyarsız; token örtüşmesi +
    dizi benzerliğinin karışımı. Kısmi ad ('Jülide' ↔ 'Jülide Beren Külahlı') tolere."""
    fa, fb = _ascii_fold(a), _ascii_fold(b)
    if not fa or not fb:
        return 0.0
    if fa == fb:
        return 1.0
    ta, tb = set(fa.split()), set(fb.split())
    ortak = ta & tb
    # Bir taraf diğerinin alt-kümesiyse (kısmi ad) yüksek skor.
    if ortak and (ortak == ta or ortak == tb):
        return 0.9 + 0.1 * (len(ortak) / max(len(ta), len(tb)))
    token_skor = len(ortak) / max(len(ta | tb), 1)
    dizi_skor = SequenceMatcher(None, fa, fb).ratio()
    return round(0.6 * token_skor + 0.4 * dizi_skor, 3)


def ogretmen_eslestir(ham_ad: str, ogretmenler: list[dict], esik: float = 0.55) -> dict:
    """Ham öğretmen adını mevcut öğretmenlerle eşleştirir.
    ogretmenler: [{id, ad, soyad}]. Dönüş: {oneriler:[{id, ad, skor}], en_iyi, otomatik}.
    'seher hocam' gibi ekleri ('hoca/hocam/öğretmen') temizler."""
    temiz = re.sub(r"\b(hoca(m)?|öğretmen(im)?|ogretmen(im)?|hanım|bey)\b", "", tr_kucuk(ham_ad)).strip()
    temiz = re.sub(r"\s+", " ", temiz)
    oneriler = []
    for t in ogretmenler:
        tam = f"{t.get('ad','')} {t.get('soyad','')}".strip()
        skor = ad_benzerlik(temiz, tam)
        if skor >= esik:
            oneriler.append({"id": t.get("id"), "ad": tam, "skor": skor})
    oneriler.sort(key=lambda o: o["skor"], reverse=True)
    en_iyi = oneriler[0] if oneriler else None
    # Tek ve güçlü eşleşme → otomatik uygulanabilir; birden çok yakın → admin seçer.
    otomatik = bool(en_iyi and en_iyi["skor"] >= 0.9 and
                    (len(oneriler) == 1 or oneriler[1]["skor"] < 0.8))
    return {"oneriler": oneriler[:5], "en_iyi": en_iyi, "otomatik": otomatik}


# ─────────────────────────── Öğrenci adı ───────────────────────────
_YER_ADLARI = {"amerika", "ingiltere", "almanya", "fransa", "hollanda", "belcika", "avusturya"}


def normalize_ogrenci_ad(s: str) -> dict:
    """Öğrenci adını değerlendirir. Dönüş: {ad, soyad, gecerli, sebep}.
    Geçersiz (elle tamamlanacak): boş, '?', tek kelime (yalnız soyadı), yer adı."""
    ham = re.sub(r"\s+", " ", str(s or "").strip())
    if not ham or ham == "?" or "?" in ham:
        return {"ad": "", "soyad": "", "gecerli": False, "sebep": "ad_eksik"}
    if _ascii_fold(ham) in _YER_ADLARI:
        return {"ad": normalize_ad(ham), "soyad": "", "gecerli": False, "sebep": "yer_adi"}
    parcalar = ham.split(" ")
    if len(parcalar) < 2:
        # Tek kelime → büyük olasılıkla yalnız soyadı; elle tamamlanmalı.
        return {"ad": "", "soyad": normalize_ad(ham), "gecerli": False, "sebep": "tek_kelime"}
    return {"ad": normalize_ad(parcalar[0]), "soyad": normalize_ad(" ".join(parcalar[1:])),
            "gecerli": True, "sebep": ""}


# ─────────────────────────── Sınıf ───────────────────────────
def normalize_sinif(s: str) -> int | None:
    """'3.sınıf'/'2'/'8. Sınıf'/'sınıf'/'?' → int veya None (çözülemeyen)."""
    if s is None:
        return None
    m = re.search(r"\d+", str(s))
    if not m:
        return None
    n = int(m.group())
    return n if 1 <= n <= 12 else None


# ─────────────────────────── Kur (çoklu olabilir) ───────────────────────────
def normalize_kur(s: str) -> list[int]:
    """'2'/'3.kur'/'2kur'/'6 kur'/'4. ve 5. kur'/'8' → [int...].
    've'/'-'/'/' ile ayrılan çift kurları iki kayıt olarak döndürür."""
    if s is None:
        return []
    metin = tr_kucuk(str(s))
    sayilar = [int(x) for x in re.findall(r"\d+", metin)]
    # Aynı sayı tekrarını koru sırayı; 1-12 dışını ele.
    out = []
    for n in sayilar:
        if 1 <= n <= 12 and n not in out:
            out.append(n)
    return out


# ─────────────────────────── Telefon (E.164) ───────────────────────────
def normalize_telefon(s: str) -> dict:
    """TR varsayılan; '+' ile başlayan uluslararası korunur. Dönüş: {e164, gecerli, ham}.
    '05331397406'/'0 532 560 88 18'/'+90 542…'/'5052627395' → +90…; ABD/DE/UK +… korunur."""
    ham = str(s or "").strip()
    if not ham:
        return {"e164": None, "gecerli": False, "ham": ham}
    uluslararasi = ham.lstrip().startswith("+")
    rakam = re.sub(r"\D", "", ham)
    if not rakam:
        return {"e164": None, "gecerli": False, "ham": ham}
    if uluslararasi:
        # + korunur; en az 8 rakam bekle.
        e164 = "+" + rakam
        return {"e164": e164, "gecerli": len(rakam) >= 8, "ham": ham}
    # TR yerel biçimleri
    if rakam.startswith("90") and len(rakam) == 12:
        return {"e164": "+" + rakam, "gecerli": True, "ham": ham}
    if rakam.startswith("0") and len(rakam) == 11:
        return {"e164": "+90" + rakam[1:], "gecerli": True, "ham": ham}
    if len(rakam) == 10 and rakam.startswith("5"):
        return {"e164": "+90" + rakam, "gecerli": True, "ham": ham}
    # Tanınmayan uzunluk → işaretle
    return {"e164": "+90" + rakam if len(rakam) >= 10 else None, "gecerli": False, "ham": ham}


# ─────────────────────────── Tarih ───────────────────────────
def normalize_tarih(s: str) -> str | None:
    """Karışık tarih formatlarını ISO'ya çevirir; parse edilemezse None (satırı engelleme).
    '16.09.2024 17:02:10'/'01.11.2024 12.14' → ISO; '29.11.0202' gibi bozuk → None."""
    if not s:
        return None
    metin = str(s).strip()
    m = re.search(r"(\d{1,2})[.\-/](\d{1,2})[.\-/](\d{2,4})", metin)
    if not m:
        return None
    gun, ay, yil = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if yil < 100:
        yil += 2000
    if not (2000 <= yil <= 2100 and 1 <= ay <= 12 and 1 <= gun <= 31):
        return None
    saat = dk = 0
    ms = re.search(r"(\d{1,2})[:.](\d{2})", metin[m.end():])
    if ms:
        saat, dk = int(ms.group(1)), int(ms.group(2))
        if saat > 23 or dk > 59:
            saat = dk = 0
    try:
        return datetime(yil, ay, gun, saat, dk).isoformat()
    except ValueError:
        return None


# ─────────────────────────── Notlar sınıflandırma (kural tabanlı) ───────────────────────────
_ODEME_KURALLARI = [
    ("odendi", ["ödendi", "ödedi", "odendi", "odedi"]),
    ("odenmedi", ["ödenmedi", "odenmedi", "ödeme yok"]),
    ("tamamlandi", ["bitti", "tamamladı", "tamamlandı", "tamamladi", "tamamlandi"]),
    ("iptal", ["iptal", "iade edildi", "iade"]),
]
# Hassas eğitim/sağlık ifadeleri — MUHASEBEYE YAZILMAZ, eğitim notuna gider.
_EGITIM_ANAHTARLARI = [
    "disleksi", "dehb", "dikkat eksikliği", "zihinsel", "engelli", "terapi",
    "otizm", "hiperaktiv", "özel gereksinim", "ozel gereksinim", "disgrafi", "diskalkuli",
]
# Taksit/erteleme kalıpları — açıklamaya gider ama etiketlenir.
_TAKSIT_KALIP = re.compile(r"(taksit|kaldı|ramazandan sonra|\d{1,2}\s*(ocak|şubat|subat|mart|nisan|mayıs|mayis|haziran|temmuz|ağustos|agustos|eylül|eylul|ekim|kasım|kasim|aralık|aralik))", re.IGNORECASE)


def siniflandir_not(s: str) -> dict:
    """Notlar kolonunu üç türe ayırır (kural tabanlı; AI opsiyonel, admin onaylar).
    Dönüş: {odeme_durumu, egitim_notu, aciklama, taksit_notu}."""
    ham = str(s or "").strip()
    if not ham:
        return {"odeme_durumu": None, "egitim_notu": "", "aciklama": "", "taksit_notu": ""}
    dusuk = tr_kucuk(ham)

    odeme = None
    for etiket, kelimeler in _ODEME_KURALLARI:
        if any(k in dusuk for k in kelimeler):
            odeme = etiket
            break

    egitim = ham if any(a in dusuk for a in _EGITIM_ANAHTARLARI) else ""
    taksit = ham if _TAKSIT_KALIP.search(ham) else ""

    # Ödeme/eğitim/taksit dışında kalan serbest metin → açıklama.
    aciklama = ""
    if not egitim:
        # Ödeme etiketi net bir tek kelimeyse açıklamaya taşıma; aksi halde serbest metni koru.
        temiz = ham
        if odeme and dusuk in sum([k for _, k in _ODEME_KURALLARI], []):
            temiz = ""
        aciklama = temiz if not taksit else ham
    return {"odeme_durumu": odeme, "egitim_notu": egitim, "aciklama": aciklama, "taksit_notu": taksit}
