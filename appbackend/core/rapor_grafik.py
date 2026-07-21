"""Giriş Analizi raporu için reportlab.graphics ile SUNUCU TARAFI vektör grafikler.
Her fonksiyon PDF'e gömülebilen bir `Drawing` (Flowable) döndürür — matplotlib gerekmez.

ÖNEMLİ (v2 #2): Grafik içi metinler PDF gövdesiyle AYNI Türkçe fontu kullanır
(set_font ile ayarlanır). Aksi halde Helvetica'da ı/İ/ğ/ş glifleri yok → ■ olur.
"""
from __future__ import annotations
import math

from reportlab.lib import colors
from reportlab.graphics.shapes import Drawing, String, Rect, Wedge, Line, Polygon, Circle

# Kurumsal palet (mevcut mavi #1F4E79 ile uyumlu, zenginleştirilmiş)
LACIVERT = colors.HexColor('#1F4E79')
MAVI = colors.HexColor('#2E75B6')
YESIL = colors.HexColor('#2E9E5B')
KOYU_YESIL = colors.HexColor('#1E7A44')   # 4. bant (Çok İyi) — mevcut yeşilden farklı ton
SARI = colors.HexColor('#E8B93B')
KIRMIZI = colors.HexColor('#D9534F')
GRI = colors.HexColor('#B8C4CE')
ACIK = colors.HexColor('#EAF1F8')

# Grafik metin fontu — PDF gövdesiyle aynı Türkçe font (set_font ile ayarlanır).
_FONT = 'Helvetica'
_FONTB = 'Helvetica-Bold'


def set_font(normal: str, bold: str) -> None:
    """PDF'in kayıtlı Türkçe fontunu grafik metinleri için de kullan (TRFont/TRFontBold)."""
    global _FONT, _FONTB
    _FONT = normal or 'Helvetica'
    _FONTB = bold or 'Helvetica-Bold'


def _renk_duzey(oran: float):
    if oran >= 0.75:
        return YESIL
    if oran >= 0.5:
        return SARI
    return KIRMIZI


def hiz_gauge(wpm: float, norm: float = 0, genislik=220, yukseklik=136) -> Drawing:
    """Yarım daire okuma hızı göstergesi: 3 bant + değeri gösteren iğne."""
    wpm = max(0, float(wpm or 0))
    ust = max(150.0, wpm * 1.35, (norm or 0) * 1.6)
    d = Drawing(genislik, yukseklik)
    cx, cy, r = genislik / 2, 26, 82
    for a1, a2, renk in [(180, 120, KIRMIZI), (120, 60, SARI), (60, 0, YESIL)]:
        d.add(Wedge(cx, cy, r, a2, a1, yradius=r, fillColor=renk, strokeColor=colors.white, strokeWidth=1))
        d.add(Wedge(cx, cy, r * 0.62, a2, a1, yradius=r * 0.62, fillColor=colors.white, strokeColor=None))
    oran = min(1.0, wpm / ust)
    aci = math.radians(180 - oran * 180)
    d.add(Line(cx, cy, cx + r * 0.9 * math.cos(aci), cy + r * 0.9 * math.sin(aci), strokeColor=LACIVERT, strokeWidth=3))
    d.add(Circle(cx, cy, 5, fillColor=LACIVERT, strokeColor=colors.white))
    d.add(String(cx, cy + 36, f"{int(round(wpm))}", fontSize=26, fillColor=LACIVERT, textAnchor='middle', fontName=_FONTB))
    d.add(String(cx, cy + 22, "kelime/dakika", fontSize=8, fillColor=colors.grey, textAnchor='middle', fontName=_FONT))
    if norm:
        d.add(String(cx, cy - 14, f"Sınıf normu ≈ {int(round(norm))}", fontSize=7, fillColor=colors.grey, textAnchor='middle', fontName=_FONT))
    return d


def dogruluk_donut(yuzde: float, genislik=120, yukseklik=120) -> Drawing:
    yuzde = max(0, min(100, float(yuzde or 0)))
    d = Drawing(genislik, yukseklik)
    cx, cy, r = genislik / 2, yukseklik / 2, 50
    renk = _renk_duzey(yuzde / 100)
    d.add(Circle(cx, cy, r, fillColor=ACIK, strokeColor=None))
    if yuzde >= 99.95:
        d.add(Circle(cx, cy, r, fillColor=renk, strokeColor=None))
    elif yuzde > 0:
        d.add(Wedge(cx, cy, r, 90, 90 - (yuzde / 100 * 360), yradius=r, fillColor=renk, strokeColor=None))
    d.add(Circle(cx, cy, r * 0.62, fillColor=colors.white, strokeColor=None))
    d.add(String(cx, cy - 2, f"%{int(round(yuzde))}", fontSize=20, fillColor=LACIVERT, textAnchor='middle', fontName=_FONTB))
    d.add(String(cx, cy - 18, "doğruluk", fontSize=8, fillColor=colors.grey, textAnchor='middle', fontName=_FONT))
    return d


def prozodik_bar(toplam: float, genislik=320, yukseklik=54) -> Drawing:
    """4 bantlı prozodik göstergesi (Word paritesi): 4–6 Zayıf · 7–9 Orta · 10–12 İyi · 13–20 Çok İyi.
    Dördüncü segment (Çok İyi) için mevcut yeşilden farklı KOYU YEŞİL ton kullanılır."""
    toplam = max(0, min(20, float(toplam or 0)))
    d = Drawing(genislik, yukseklik)
    x0, bar_w, bar_h, y0 = 10, genislik - 20, 16, 22
    # Segment sınırları (0–20 ölçekte): tamsayı puanlar → [.,6.5) Zayıf, [6.5,9.5) Orta,
    # [9.5,12.5) İyi, [12.5,20] Çok İyi. Renkler: kırmızı/sarı/yeşil/koyu yeşil.
    for a, b, renk in [(0, 6.5, KIRMIZI), (6.5, 9.5, SARI), (9.5, 12.5, YESIL), (12.5, 20, KOYU_YESIL)]:
        d.add(Rect(x0 + bar_w * a / 20, y0, bar_w * (b - a) / 20, bar_h, fillColor=renk, strokeColor=colors.white, strokeWidth=0.5))
    mx = x0 + bar_w * toplam / 20
    d.add(Polygon([mx, y0 + bar_h + 6, mx - 5, y0 + bar_h + 14, mx + 5, y0 + bar_h + 14], fillColor=LACIVERT, strokeColor=colors.white))
    d.add(String(mx, y0 + bar_h + 16, f"{int(round(toplam))}/20", fontSize=9, fillColor=LACIVERT, textAnchor='middle', fontName=_FONTB))
    for etk, xo in [("Zayıf", 3.2), ("Orta", 8), ("İyi", 11), ("Çok İyi", 16.2)]:
        d.add(String(x0 + bar_w * xo / 20, y0 - 10, etk, fontSize=7, fillColor=colors.grey, textAnchor='middle', fontName=_FONT))
    return d


def yatay_bar_dagilim(veriler: list, genislik=300, satir_yuk=16, baslik_alani=110) -> Drawing:
    veriler = [(e, max(0, int(s or 0))) for e, s in veriler if s]
    if not veriler:
        return Drawing(genislik, 10)
    enb = max(s for _, s in veriler) or 1
    h = len(veriler) * satir_yuk + 8
    d = Drawing(genislik, h)
    bar_alan = genislik - baslik_alani - 30
    for i, (etk, s) in enumerate(veriler):
        y = h - (i + 1) * satir_yuk
        d.add(String(4, y + 3, etk[:22], fontSize=7.5, fillColor=colors.HexColor('#333333'), fontName=_FONT))
        w = bar_alan * s / enb
        d.add(Rect(baslik_alani, y, max(1, w), satir_yuk - 6, fillColor=MAVI, strokeColor=None))
        d.add(String(baslik_alani + w + 4, y + 3, str(s), fontSize=8, fillColor=LACIVERT, fontName=_FONTB))
    return d


def anlama_radar(eksenler: list, degerler: list, genislik=250, yukseklik=210, maxv=3) -> Drawing | None:
    """ÖZEL çizim radar (SpiderChart yerine) — etiket fontu tam kontrol edilir (v2 #2).
    eksenler: [etiket], degerler: [0..maxv]. En az 3 eksen gerekir."""
    n = len(eksenler)
    if n < 3:
        return None
    d = Drawing(genislik, yukseklik)
    cx, cy = genislik / 2, yukseklik / 2 - 2
    R = min(genislik, yukseklik) / 2 - 40

    def nokta(i, frac):
        a = math.pi / 2 - 2 * math.pi * i / n
        return cx + R * frac * math.cos(a), cy + R * frac * math.sin(a)

    # Grid halkaları
    for frac in (0.34, 0.67, 1.0):
        pts = []
        for i in range(n):
            pts.extend(nokta(i, frac))
        d.add(Polygon(pts, fillColor=None, strokeColor=GRI, strokeWidth=0.4))
    # Eksenler + etiketler
    for i, etk in enumerate(eksenler):
        ex, ey = nokta(i, 1.0)
        d.add(Line(cx, cy, ex, ey, strokeColor=GRI, strokeWidth=0.4))
        a = math.pi / 2 - 2 * math.pi * i / n
        lx, ly = cx + (R + 12) * math.cos(a), cy + (R + 12) * math.sin(a)
        anchor = 'middle' if abs(math.cos(a)) < 0.35 else ('start' if math.cos(a) > 0 else 'end')
        d.add(String(lx, ly - 3, str(etk), fontSize=7.5, fillColor=colors.HexColor('#333333'), textAnchor=anchor, fontName=_FONT))
    # Veri poligonu
    pts = []
    for i, v in enumerate(degerler):
        frac = max(0.0, min(1.0, (float(v or 0)) / maxv))
        pts.extend(nokta(i, frac if frac > 0 else 0.02))
    d.add(Polygon(pts, fillColor=colors.Color(0.18, 0.31, 0.47, 0.35), strokeColor=LACIVERT, strokeWidth=1.5))
    return d


def norm_karsilastirma(ogrenci_wpm: float, norm_wpm: float, genislik=300, yukseklik=64) -> Drawing:
    ogr = max(0, float(ogrenci_wpm or 0)); nrm = max(0, float(norm_wpm or 0))
    ust = max(ogr, nrm, 1) * 1.2
    d = Drawing(genislik, yukseklik)
    x0, bar_w, bh = 96, genislik - 130, 14
    for i, (etk, deger, renk) in enumerate([("Öğrenci", ogr, MAVI), ("Sınıf normu", nrm, GRI)]):
        y = yukseklik - (i + 1) * 26
        d.add(String(4, y + 3, etk, fontSize=8, fillColor=colors.HexColor('#333333'), fontName=_FONT))
        w = bar_w * deger / ust
        d.add(Rect(x0, y, max(1, w), bh, fillColor=renk, strokeColor=None))
        d.add(String(x0 + w + 4, y + 3, f"{int(round(deger))}", fontSize=8, fillColor=LACIVERT, fontName=_FONTB))
    return d
