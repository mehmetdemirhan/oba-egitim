"""Kelime Gezmece — saf Python çapraz bulmaca (crossword) üretici.

3. parti kütüphane KULLANILMAZ. Algoritma:
  1. Sınıf seviyesine uygun bir "tohum" kelime seçilir; harfleri harf havuzunu
     oluşturur (4-7 harf).
  2. Havuzun harflerinden türetilebilen tüm sınıf-uygun kelimeler bulunur.
  3. En uzun kelime grid'in ortasına yerleştirilir; diğerleri kesişen harflerden
     greedy + geri izleme (backtracking) ile yerleştirilir.
  4. Yerleşemeyen geçerli kelimeler "bonus kelime" listesine düşer.

Çıktı şeması (core/egzersiz_tipleri.py KELIME_GEZMECE ile uyumlu):
  {
    "harf_havuzu": ["e","l","m","a"],
    "grid": [["e","l","m","a"], [".",".",".","."], ...],   # '.' = boş
    "kelimeler": [{"kelime","yon","baslangic":[r,c],"uzunluk"}],
    "bonus_kelimeler": ["lam","ela", ...],
    "tema": {"ad","emoji","ana_renk_hex"}
  }

NOT: Üretim çalışma zamanında AI çağırmaz; tamamen yerel ve hızlıdır.
"""
from __future__ import annotations

import random
from collections import Counter

from core.turkce_kelime_havuzu import sinif_kelimeleri, kelime_seti, tr_kucuk

# ─────────────────────────────────────────────────────────────
# Sınıf seviyesine göre zorluk parametreleri
#   havuz: harf havuzu uzunluğu (tohum kelime uzunluğu)
#   grid:  grid'e yerleştirilecek kelime sayısı hedefi (min, max)
#   bonus: bonus kelime sayısı (min, max)
# ─────────────────────────────────────────────────────────────
ZORLUK = {
    1: {"havuz": (3, 4), "grid": (3, 5), "bonus": (2, 3)},
    2: {"havuz": (3, 4), "grid": (3, 5), "bonus": (2, 3)},
    3: {"havuz": (4, 5), "grid": (5, 8), "bonus": (4, 6)},
    4: {"havuz": (4, 5), "grid": (5, 8), "bonus": (4, 6)},
    5: {"havuz": (5, 6), "grid": (8, 12), "bonus": (6, 10)},
    6: {"havuz": (5, 6), "grid": (8, 12), "bonus": (6, 10)},
    7: {"havuz": (6, 7), "grid": (12, 15), "bonus": (10, 15)},
    8: {"havuz": (6, 7), "grid": (12, 15), "bonus": (10, 15)},
}

GRID_MAX = 13  # Güvenlik tavanı — grid bu boyutu aşarsa kelime bonusa düşer.

# Sınıf bazlı harf havuzu uzunluk TAVANI (seviye artsa da aşılmaz).
#   1-2. sınıf → 5, 3-4 → 6, 5-6 → 7, 7-8 → 8
HAVUZ_TAVAN = {1: 5, 2: 5, 3: 6, 4: 6, 5: 7, 6: 7, 7: 8, 8: 8}

# Sınıf gruplarına göre tema seçenekleri (yalnızca isim+emoji+ana renk).
# Renkler core paletinden: mint, pembe, lavanta, sky, şeftali.
TEMALAR = {
    "1-2": [
        {"ad": "Bahçe", "emoji": "🌱", "ana_renk_hex": "#A7E8BD"},
        {"ad": "Sevimli Hayvanlar", "emoji": "🐱", "ana_renk_hex": "#FFB5A7"},
        {"ad": "Renkler", "emoji": "🌈", "ana_renk_hex": "#C7B8EA"},
        {"ad": "Meyveler", "emoji": "🍎", "ana_renk_hex": "#FFD6A5"},
        {"ad": "Oyuncaklar", "emoji": "🧸", "ana_renk_hex": "#BFE6FF"},
    ],
    "3-4": [
        {"ad": "Çiçek Tarlası", "emoji": "🌸", "ana_renk_hex": "#FFB5A7"},
        {"ad": "Deniz Canlıları", "emoji": "🐬", "ana_renk_hex": "#BFE6FF"},
        {"ad": "Spor", "emoji": "⚽", "ana_renk_hex": "#A7E8BD"},
        {"ad": "Meslekler", "emoji": "👨‍🍳", "ana_renk_hex": "#C7B8EA"},
    ],
    "5-6": [
        {"ad": "Bilim", "emoji": "🔬", "ana_renk_hex": "#BFE6FF"},
        {"ad": "Tarih", "emoji": "📜", "ana_renk_hex": "#FFD6A5"},
        {"ad": "Edebiyat", "emoji": "📚", "ana_renk_hex": "#C7B8EA"},
        {"ad": "Coğrafya", "emoji": "🌍", "ana_renk_hex": "#A7E8BD"},
    ],
    "7-8": [
        {"ad": "Felsefe", "emoji": "💭", "ana_renk_hex": "#C7B8EA"},
        {"ad": "Teknoloji", "emoji": "💻", "ana_renk_hex": "#BFE6FF"},
        {"ad": "Sanat", "emoji": "🎨", "ana_renk_hex": "#FFB5A7"},
        {"ad": "Bilim İnsanları", "emoji": "🚀", "ana_renk_hex": "#A7E8BD"},
    ],
}


def _tema_sec(sinif: int) -> dict:
    if sinif <= 2:
        grup = "1-2"
    elif sinif <= 4:
        grup = "3-4"
    elif sinif <= 6:
        grup = "5-6"
    else:
        grup = "7-8"
    return dict(random.choice(TEMALAR[grup]))


# ─────────────────────────────────────────────────────────────
# Harf havuzundan türetilebilirlik
# ─────────────────────────────────────────────────────────────
def _turetilebilir_mi(kelime: str, havuz_sayac: Counter) -> bool:
    """Kelime, havuzdaki harf çoklu-kümesinden (her harf en çok havuzdaki kadar)
    oluşturulabilir mi?"""
    ks = Counter(kelime)
    for harf, adet in ks.items():
        if adet > havuz_sayac.get(harf, 0):
            return False
    return True


def _adaylari_bul(harf_havuzu: list[str], sinif: int) -> list[str]:
    """Havuz harflerinden türetilebilen, sınıf-uygun tüm kelimeler (uzun→kısa)."""
    sayac = Counter(harf_havuzu)
    adaylar = [k for k in sinif_kelimeleri(sinif) if _turetilebilir_mi(k, sayac)]
    # Uzun kelimeler önce (grid omurgası), eşit uzunlukta rastgele çeşitlilik
    random.shuffle(adaylar)
    adaylar.sort(key=len, reverse=True)
    return adaylar


def _seviye_parametreleri(sinif: int, seviye_no: int):
    """Sınıf + seviye numarasına göre zorluk parametrelerini hesaplar.

    Zorluk artışı (sınıf tavanları korunarak):
      - seviye 1-3: temel harf sayısı, farklı temalar
      - seviye 4-6: +1 harf
      - seviye 7+ : +1 harf ve daha fazla grid kelimesi

    Dönüş: ((havuz_min, havuz_max), (grid_min, grid_max), (bonus_min, bonus_max))
    """
    z = ZORLUK.get(sinif, ZORLUK[3])
    hmin, hmax = z["havuz"]
    gmin, gmax = z["grid"]
    bmin, bmax = z["bonus"]

    ek = 0 if seviye_no <= 3 else (1 if seviye_no <= 6 else 2)
    tavan = HAVUZ_TAVAN.get(sinif, 7)
    yeni_hmax = min(hmax + ek, tavan)
    yeni_hmin = min(hmin + (1 if ek > 0 else 0), yeni_hmax)

    if seviye_no >= 7:
        gmin += 1
        gmax += 2

    return (yeni_hmin, yeni_hmax), (gmin, gmax), (bmin, bmax)


def _tohum_sec(sinif: int, hedef_aday: int,
               havuz_uzunluk: tuple[int, int] | None = None) -> tuple[list[str], list[str]]:
    """Bol sayıda alt kelime türeten bir tohum seçer.

    Dönüş: (harf_havuzu, adaylar). Birçok rastgele tohum denenir; en çok aday
    üreten seçilir. `havuz_uzunluk` verilirse tohum kelime uzunluğu bununla
    (aksi halde ZORLUK varsayılanıyla) sınırlanır.
    """
    havuz_min, havuz_max = havuz_uzunluk or ZORLUK.get(sinif, ZORLUK[3])["havuz"]
    kelimeler = sinif_kelimeleri(sinif)
    # Tohum adayları: havuz uzunluk aralığındaki kelimeler
    tohum_adaylari = [k for k in kelimeler if havuz_min <= len(k) <= havuz_max]
    if not tohum_adaylari:
        tohum_adaylari = [k for k in kelimeler if len(k) <= havuz_max] or kelimeler

    en_iyi: tuple[list[str], list[str]] | None = None
    en_iyi_skor = -1
    denemeler = min(40, max(10, len(tohum_adaylari)))
    for _ in range(denemeler):
        tohum = random.choice(tohum_adaylari)
        havuz = list(tohum)
        adaylar = _adaylari_bul(havuz, sinif)
        skor = len(adaylar)
        if skor > en_iyi_skor:
            en_iyi_skor = skor
            en_iyi = (havuz, adaylar)
        if skor >= hedef_aday:
            break
    return en_iyi if en_iyi else ([], [])


# ─────────────────────────────────────────────────────────────
# Çapraz bulmaca yerleştirme (sözlük tabanlı sanal koordinat sistemi)
# ─────────────────────────────────────────────────────────────
class _Izgara:
    """Sözlük tabanlı sanal grid (koordinatlar negatif olabilir)."""

    def __init__(self):
        self.hucreler: dict[tuple[int, int], str] = {}
        self.yerlesimler: list[dict] = []

    def harf(self, r: int, c: int) -> str | None:
        return self.hucreler.get((r, c))

    def _yerlesebilir(self, kelime: str, r: int, c: int, dr: int, dc: int,
                      ilk: bool) -> bool:
        """kelime, (r,c) başlangıçla (dr,dc) yönünde yerleşebilir mi?"""
        kesisim = 0
        # Başlangıçtan hemen önceki ve bitişten hemen sonraki hücre boş olmalı.
        if self.harf(r - dr, c - dc) is not None:
            return False
        if self.harf(r + dr * len(kelime), c + dc * len(kelime)) is not None:
            return False
        for i, ch in enumerate(kelime):
            rr, cc = r + dr * i, c + dc * i
            mevcut = self.harf(rr, cc)
            if mevcut is not None:
                if mevcut != ch:
                    return False
                kesisim += 1  # geçerli kesişim noktası
            else:
                # Boş hücre: dik komşuları boş olmalı (yan yana kelime oluşmasın).
                # Dik yön = (dc, dr)
                if self.harf(rr + dc, cc + dr) is not None:
                    return False
                if self.harf(rr - dc, cc - dr) is not None:
                    return False
        # İlk kelime hariç en az bir kesişim şart (kelimeler bağlı kalsın).
        if not ilk and kesisim == 0:
            return False
        return True

    def yerlestir(self, kelime: str, r: int, c: int, dr: int, dc: int):
        for i, ch in enumerate(kelime):
            self.hucreler[(r + dr * i, c + dc * i)] = ch
        self.yerlesimler.append({
            "kelime": kelime, "r": r, "c": c, "dr": dr, "dc": dc,
            "uzunluk": len(kelime),
        })

    def kelime_ekle(self, kelime: str) -> bool:
        """Kelimeyi mevcut grid'e kesişimle ekler. İlk kelime ortaya yatay konur."""
        if not self.yerlesimler:
            self.yerlestir(kelime, 0, 0, 0, 1)  # yatay
            return True
        # Her harf için, eşleşen mevcut hücrelere dik yönde yerleştirmeyi dene.
        adaylar: list[tuple[int, int, int, int]] = []
        for i, ch in enumerate(kelime):
            for (rr, cc), mevcut in self.hucreler.items():
                if mevcut != ch:
                    continue
                yerlesim = self._komsu_yonler(kelime, i, rr, cc)
                adaylar.extend(yerlesim)
        random.shuffle(adaylar)
        for (r, c, dr, dc) in adaylar:
            if self._yerlesebilir(kelime, r, c, dr, dc, ilk=False):
                self.yerlestir(kelime, r, c, dr, dc)
                return True
        return False

    def _komsu_yonler(self, kelime: str, i: int, rr: int, cc: int) -> list[tuple]:
        """kelime[i] harfini (rr,cc) hücresine denk getiren yatay/dikey başlangıçlar."""
        sonuc = []
        # Yatay yerleşim: başlangıç sütunu = cc - i
        sonuc.append((rr, cc - i, 0, 1))
        # Dikey yerleşim: başlangıç satırı = rr - i
        sonuc.append((rr - i, cc, 1, 0))
        return sonuc

    def normalize(self) -> tuple[list[list[str]], list[dict]]:
        """Sanal hücreleri 0-tabanlı 2D diziye taşır. (grid, kelimeler) döndürür."""
        if not self.hucreler:
            return [["."]], []
        rs = [r for (r, _) in self.hucreler]
        cs = [c for (_, c) in self.hucreler]
        r0, r1 = min(rs), max(rs)
        c0, c1 = min(cs), max(cs)
        h = r1 - r0 + 1
        w = c1 - c0 + 1
        grid = [["." for _ in range(w)] for _ in range(h)]
        for (r, c), ch in self.hucreler.items():
            grid[r - r0][c - c0] = ch
        kelimeler = []
        for y in self.yerlesimler:
            kelimeler.append({
                "kelime": y["kelime"],
                "yon": "yatay" if y["dc"] == 1 else "dikey",
                "baslangic": [y["r"] - r0, y["c"] - c0],
                "uzunluk": y["uzunluk"],
            })
        return grid, kelimeler


def _bulmaca_kur(adaylar: list[str], grid_min: int, grid_max: int):
    """Adaylardan bir çapraz bulmaca kurar.

    Dönüş: (grid, kelimeler, yerlesen_set)
    """
    izgara = _Izgara()
    yerlesen: set[str] = set()
    for kelime in adaylar:
        if kelime in yerlesen:
            continue
        if len(izgara.yerlesimler) >= grid_max:
            break
        if izgara.kelime_ekle(kelime):
            # Grid taşma kontrolü
            grid, _ = izgara.normalize()
            if len(grid) > GRID_MAX or (grid and len(grid[0]) > GRID_MAX):
                # Son yerleşimi geri al
                son = izgara.yerlesimler.pop()
                for i in range(son["uzunluk"]):
                    rr, cc = son["r"] + son["dr"] * i, son["c"] + son["dc"] * i
                    # Yalnızca bu kelimeye özel (kesişmeyen) hücreleri sil
                    if not _baska_kelime_kullaniyor(izgara, rr, cc):
                        izgara.hucreler.pop((rr, cc), None)
                continue
            yerlesen.add(kelime)
    grid, kelimeler = izgara.normalize()
    return grid, kelimeler, yerlesen


def _baska_kelime_kullaniyor(izgara: _Izgara, r: int, c: int) -> bool:
    for y in izgara.yerlesimler:
        for i in range(y["uzunluk"]):
            if (y["r"] + y["dr"] * i, y["c"] + y["dc"] * i) == (r, c):
                return True
    return False


# ─────────────────────────────────────────────────────────────
# Genel API
# ─────────────────────────────────────────────────────────────
def bulmaca_uret(sinif: int = 3, seviye_no: int = 1) -> dict:
    """Sınıf seviyesine ve seviye numarasına uygun bir Kelime Gezmece bulmacası üretir.

    `seviye_no` arttıkça zorluk artar (bkz. _seviye_parametreleri); sınıf tavanları
    korunur. Çıktıya `seviye_no` ve `sinif` alanları eklenir (frontend ilerleme
    takibi için).
    """
    sinif = max(1, min(8, int(sinif)))
    seviye_no = max(1, int(seviye_no))
    (havuz_min, havuz_max), (grid_min, grid_max), (bonus_min, bonus_max) = \
        _seviye_parametreleri(sinif, seviye_no)

    harf_havuzu, adaylar = _tohum_sec(
        sinif, hedef_aday=grid_max + bonus_max + 2,
        havuz_uzunluk=(havuz_min, havuz_max))

    # Tohum başarısızsa (çok az aday) basit geri dönüş: en kısa kelimelerle dene.
    if len(adaylar) < 2:
        harf_havuzu = list("elma")
        adaylar = _adaylari_bul(harf_havuzu, sinif) or ["elma", "ela", "lam", "mal"]

    grid, kelimeler, yerlesen = _bulmaca_kur(adaylar, grid_min, grid_max)

    # Bonus: yerleşemeyen geçerli kelimeler (kısa → uzun), sınıf aralığında sınırla.
    bonus_aday = [k for k in adaylar if k not in yerlesen]
    bonus_aday.sort(key=len)
    bonus_kelimeler = bonus_aday[:bonus_max]

    # Harf havuzunu karıştır (oyun her seferinde farklı görünsün).
    havuz = list(harf_havuzu)
    random.shuffle(havuz)

    return {
        "harf_havuzu": havuz,
        "grid": grid,
        "kelimeler": kelimeler,
        "bonus_kelimeler": bonus_kelimeler,
        "tema": _tema_sec(sinif),
        "seviye_no": seviye_no,
        "sinif": sinif,
    }


def kelime_dogrula(icerik: dict, kelime: str, sinif: int) -> tuple[str, int]:
    """Bir kelimeyi içeriğe göre doğrular.

    Dönüş: (durum, puan_kazanildi)
      durum: "grid" (+10) | "bonus" (+15) | "gecersiz" (0)

    Kurallar:
      - Grid kelimelerinden biriyse → "grid"
      - Grid'de değil ama (önceden hesaplanmış bonus listesinde) VEYA
        (havuz harflerinden türetilebilen sınıf-uygun geçerli kelime) ise → "bonus"
      - Aksi halde → "gecersiz"
    """
    k = tr_kucuk((kelime or "").strip())
    if not k or len(k) < 2:
        return "gecersiz", 0

    grid_kelimeler = {tr_kucuk(str(g.get("kelime", ""))) for g in icerik.get("kelimeler", [])}
    if k in grid_kelimeler:
        return "grid", 10

    bonus = {tr_kucuk(str(b)) for b in icerik.get("bonus_kelimeler", [])}
    if k in bonus:
        return "bonus", 15

    # Havuzdan türetilebilen ve sınıf havuzunda yer alan geçerli kelime → bonus
    havuz_sayac = Counter(tr_kucuk("".join(icerik.get("harf_havuzu", []))))
    if _turetilebilir_mi(k, havuz_sayac) and k in kelime_seti(sinif):
        return "bonus", 15

    return "gecersiz", 0
