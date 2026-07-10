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


# ─────────────────────────── Öğretmen VARYANT BİRLEŞTİRME (kümeleme) ───────────────────────────
def _unvan_sil(ad: str) -> str:
    s = re.sub(r"\b(hoca(m)?|öğretmen(im)?|ogretmen(im)?|hanım|bey)\b", "", tr_kucuk(ad))
    return re.sub(r"\s+", " ", s).strip()


def _fold_tokenset(ad: str) -> frozenset:
    """Ada unvan-temizliği + ascii-fold uygular, kelime kümesi döner (Türkçe duyarlı)."""
    return frozenset(t for t in _ascii_fold(_unvan_sil(ad)).split() if t)


def _lev(a: str, b: str) -> int:
    """Damerau-Levenshtein (bitişik harf yer değiştirmesi = 1). Küçük stringler için.
    'yildiirm'↔'yildirim' gibi transpozisyonlar 1 sayılır."""
    if a == b:
        return 0
    if abs(len(a) - len(b)) > 1:
        return 2
    la, lb = len(a), len(b)
    d = [[0] * (lb + 1) for _ in range(la + 1)]
    for i in range(la + 1):
        d[i][0] = i
    for j in range(lb + 1):
        d[0][j] = j
    for i in range(1, la + 1):
        for j in range(1, lb + 1):
            maliyet = 0 if a[i - 1] == b[j - 1] else 1
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + maliyet)
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                d[i][j] = min(d[i][j], d[i - 2][j - 2] + 1)
    return d[la][lb]


def _tokens_yakin(ta: frozenset, tb: frozenset) -> bool:
    """İki token kümesi kelime başına ≤1 harf farkıyla eşleşiyor mu (aynı boyutta)."""
    if len(ta) != len(tb) or not ta:
        return False
    kalan = set(tb)
    for x in ta:
        es = next((y for y in kalan if _lev(x, y) <= 1), None)
        if es is None:
            return False
        kalan.discard(es)
    return True


def _kanonik_sec(uyeler: list[str], agirlik: dict | None = None) -> str:
    """Kanonik yazım: en eksiksiz (en çok kelime), sonra en sık yazılan (baskın/doğru
    yazım), sonra en uzun. agirlik verilmezse hepsi 1 sayılır."""
    ag = agirlik or {}
    en = max(uyeler, key=lambda a: (len(_fold_tokenset(a)), ag.get(a.strip(), 1), len(_unvan_sil(a))))
    return normalize_ad(_unvan_sil(en))


def ogretmen_kumele(ham_adlar: list[str], mevcut_ogretmenler: list[dict] | None = None,
                    agirlik: dict | None = None) -> dict:
    """Ham öğretmen adı varyantlarını otomatik birleştirir (bariz aynı olanlar), gerçekten
    belirsiz olanları işaretler. Kurallar: (1) normalize aynı → birleş; (2) alt-küme tek
    süperkümeyle → birleş, çok süperküme → belirsiz; (3) diakritik eşitleme + kelime-başı
    Damerau≤1 komşu → ÖNERİ; ANCAK komşu TEK ise ve baskınsa (o yazım ≥3× daha sık, `agirlik`)
    yazım-hatası olarak OTOMATİK birleşir (nadir typo → yaygın doğru yazım). Yakın-sayımlı
    gerçek farklı kişiler birleşmez. Mevcut öğretmenlerle de aynı kural.

    agirlik: {kırpılmış_ham_ad → satır sayısı} (baskınlık + kanonik seçimi için).
    Dönüş: {harita: {ham_ad → {...}}, kumeler: [{...}]}"""
    mevcut_ogretmenler = mevcut_ogretmenler or []
    agirlik = agirlik or {}
    # Orijinal (kırpılmamış) adları koru → harita hem orijinal hem kırpılmış anahtarla erişilir.
    strip_map: dict = {}
    for a in dict.fromkeys(ham_adlar):
        if a and str(a).strip():
            strip_map.setdefault(str(a).strip(), []).append(a)
    adlar = list(strip_map.keys())
    tok = {a: _fold_tokenset(a) for a in adlar}
    adlar = [a for a in adlar if tok[a]]

    # (1) Birebir-fold grupları → düğümler
    fold_map: dict = {}
    for a in adlar:
        fold_map.setdefault(tok[a], []).append(a)
    dugum_tok = list(fold_map.keys())
    dugum_uye = [fold_map[t] for t in dugum_tok]
    n = len(dugum_tok)

    parent = list(range(n))
    def bul(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]; x = parent[x]
        return x
    def birlestir(x, y):
        parent[bul(x)] = bul(y)

    belirsiz_secenek: dict = {}   # dugum_idx → [kanonik superset seçenekleri]
    for i in sorted(range(n), key=lambda k: len(dugum_tok[k])):
        ti = dugum_tok[i]
        supersetler = [j for j in range(n) if j != i and ti < dugum_tok[j]]
        if not supersetler:
            continue
        maksimal = [j for j in supersetler
                    if not any(k != j and dugum_tok[j] < dugum_tok[k] for k in supersetler)]
        if len(maksimal) == 1:
            birlestir(i, maksimal[0])
        else:
            belirsiz_secenek[i] = [_kanonik_sec(dugum_uye[j], agirlik) for j in maksimal]

    # (3b) Baskınlık-tabanlı yazım-hatası birleştirme: nadir bir kümenin TEK Damerau≤1
    # komşusu varsa ve o komşu ≥3× daha sık yazılıyorsa (baskın doğru yazım) → birleş.
    # Yakın-sayımlı gerçek farklı kişiler (dominance sağlanmaz) birleşmez.
    def _kok_uyeleri(r):
        return [u for i in range(n) if bul(i) == r for u in dugum_uye[i]]
    def _kok_tok(r):
        return max((dugum_tok[i] for i in range(n) if bul(i) == r), key=len)
    def _kok_agir(r):
        return sum(agirlik.get(u, 1) for u in _kok_uyeleri(r))
    for r0 in sorted({bul(i) for i in range(n)}, key=lambda r: _kok_agir(r)):
        r = bul(r0)
        if r != r0:
            continue
        tr = _kok_tok(r)
        komsu = {bul(o) for o in {bul(i) for i in range(n)} if bul(o) != r and _tokens_yakin(tr, _kok_tok(bul(o)))}
        if len(komsu) == 1:
            b = next(iter(komsu))
            if _kok_agir(b) >= 3 * _kok_agir(r):
                birlestir(r, b)

    # Kümeleri topla
    kok_uyeler: dict = {}
    kok_belirsiz: dict = {}
    for i in range(n):
        r = bul(i)
        kok_uyeler.setdefault(r, []).extend(dugum_uye[i])
        if i in belirsiz_secenek:
            kok_belirsiz.setdefault(r, []).extend(belirsiz_secenek[i])

    # Mevcut öğretmen token'ları
    mev = [{"id": t.get("id"), "ad": f"{t.get('ad','')} {t.get('soyad','')}".strip(),
            "tok": _fold_tokenset(f"{t.get('ad','')} {t.get('soyad','')}")} for t in mevcut_ogretmenler]

    kumeler = []
    harita: dict = {}
    for ki, (r, uyeler) in enumerate(kok_uyeler.items()):
        kanonik = _kanonik_sec(uyeler, agirlik)
        ktok = _fold_tokenset(kanonik)
        # Mevcut öğretmenle eşleşme (aynı / alt-küme / üst-küme)
        esles = [m for m in mev if m["tok"] and (m["tok"] == ktok or ktok <= m["tok"] or m["tok"] <= ktok)]
        mevcut_id = esles[0]["id"] if len(esles) == 1 else None
        belirsiz = (r in kok_belirsiz) or (len(esles) > 1)
        oneriler = list(dict.fromkeys(kok_belirsiz.get(r, []) + [m["ad"] for m in esles]))
        # (3) Levenshtein≤1 komşuları öneri olarak ekle (otomatik birleştirme YOK)
        for m in mev:
            if m["id"] != mevcut_id and _tokens_yakin(ktok, m["tok"]) and m["ad"] not in oneriler:
                oneriler.append(m["ad"])
        kume = {"kume_id": ki, "kanonik": kanonik, "uyeler": sorted(set(uyeler)),
                "mevcut_id": mevcut_id, "belirsiz": belirsiz, "oneriler": oneriler[:5]}
        kumeler.append(kume)
        info = {"kanonik": kanonik, "mevcut_id": mevcut_id, "belirsiz": belirsiz,
                "oneriler": kume["oneriler"], "kume_id": ki,
                "birlesen": kume["uyeler"] if len(kume["uyeler"]) > 1 else []}
        for u in uyeler:  # u = kırpılmış ad
            harita[u] = info
            for orij in strip_map.get(u, []):  # orijinal (kırpılmamış) varyantlar da
                harita[orij] = info
    return {"harita": harita, "kumeler": kumeler}


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
    # Excel sayısal telefon hücresi "5052627395.0" gibi gelebilir → sondaki .0 kaldır.
    ham_tmp = re.sub(r"\.0+$", "", ham)
    uluslararasi = ham_tmp.lstrip().startswith("+")
    rakam = re.sub(r"\D", "", ham_tmp)
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
    # ISO / datetime biçimi (Excel tarih hücresi "2024-09-16 17:02:10") — önce onu dene.
    iso = re.match(r"(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})", metin)
    if iso:
        try:
            return datetime(int(iso.group(1)), int(iso.group(2)), int(iso.group(3)),
                            int(iso.group(4)), int(iso.group(5))).isoformat()
        except ValueError:
            return None
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
