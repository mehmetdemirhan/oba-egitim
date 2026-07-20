"""Giriş Analizi raporu için reportlab.graphics ile SUNUCU TARAFI vektör grafikler.
Her fonksiyon PDF'e gömülebilen bir `Drawing` (Flowable) döndürür — matplotlib gerekmez.

Grafikler: okuma hızı göstergesi (gauge), doğruluk donut'u, hata dağılımı bar,
anlama/Bloom radar (örümcek), prozodik renk bantlı bar, sınıf normu karşılaştırma.
"""
from __future__ import annotations
import math

from reportlab.lib import colors
from reportlab.graphics.shapes import Drawing, String, Rect, Wedge, Line, Polygon, Circle, Group
from reportlab.graphics.charts.spider import SpiderChart

# Kurumsal palet (mevcut mavi #1F4E79 ile uyumlu, zenginleştirilmiş)
LACIVERT = colors.HexColor('#1F4E79')
MAVI = colors.HexColor('#2E75B6')
YESIL = colors.HexColor('#2E9E5B')
SARI = colors.HexColor('#E8B93B')
KIRMIZI = colors.HexColor('#D9534F')
GRI = colors.HexColor('#B8C4CE')
ACIK = colors.HexColor('#EAF1F8')


def _renk_duzey(oran: float):
    """0..1 orana göre kırmızı/sarı/yeşil."""
    if oran >= 0.75:
        return YESIL
    if oran >= 0.5:
        return SARI
    return KIRMIZI


def hiz_gauge(wpm: float, norm: float = 0, genislik=220, yukseklik=130) -> Drawing:
    """Yarım daire okuma hızı göstergesi: 3 bant + değeri gösteren iğne. norm verilirse
    ölçek ona göre; yoksa 0..max(150, 1.3*wpm)."""
    wpm = max(0, float(wpm or 0))
    ust = max(150.0, wpm * 1.35, (norm or 0) * 1.6)
    d = Drawing(genislik, yukseklik)
    cx, cy, r = genislik / 2, 20, 82
    # 3 bant (kırmızı/sarı/yeşil), 180°→0°
    bantlar = [(180, 120, KIRMIZI), (120, 60, SARI), (60, 0, YESIL)]
    for a1, a2, renk in bantlar:
        d.add(Wedge(cx, cy, r, a2, a1, yradius=r, fillColor=renk, strokeColor=colors.white, strokeWidth=1))
        d.add(Wedge(cx, cy, r * 0.62, a2, a1, yradius=r * 0.62, fillColor=colors.white, strokeColor=None))
    # İğne
    oran = min(1.0, wpm / ust)
    aci = math.radians(180 - oran * 180)
    ix, iy = cx + r * 0.9 * math.cos(aci), cy + r * 0.9 * math.sin(aci)
    d.add(Line(cx, cy, ix, iy, strokeColor=LACIVERT, strokeWidth=3))
    d.add(Circle(cx, cy, 5, fillColor=LACIVERT, strokeColor=colors.white))
    # Değer + etiket
    d.add(String(cx, cy + 34, f"{int(round(wpm))}", fontSize=26, fillColor=LACIVERT, textAnchor='middle', fontName='Helvetica-Bold'))
    d.add(String(cx, cy + 20, "kelime/dakika", fontSize=8, fillColor=colors.grey, textAnchor='middle'))
    if norm:
        d.add(String(cx, cy - 12, f"Sınıf normu ≈ {int(round(norm))}", fontSize=7, fillColor=colors.grey, textAnchor='middle'))
    return d


def dogruluk_donut(yuzde: float, genislik=120, yukseklik=120) -> Drawing:
    """Doğruluk oranı halka (donut) grafiği; ortada %."""
    yuzde = max(0, min(100, float(yuzde or 0)))
    d = Drawing(genislik, yukseklik)
    cx, cy, r = genislik / 2, yukseklik / 2, 50
    renk = _renk_duzey(yuzde / 100)
    d.add(Circle(cx, cy, r, fillColor=ACIK, strokeColor=None))
    if yuzde >= 99.95:
        d.add(Circle(cx, cy, r, fillColor=renk, strokeColor=None))   # tam halka (360° wedge sıfıra böler)
    elif yuzde > 0:
        d.add(Wedge(cx, cy, r, 90, 90 - (yuzde / 100 * 360), yradius=r, fillColor=renk, strokeColor=None))
    d.add(Circle(cx, cy, r * 0.62, fillColor=colors.white, strokeColor=None))
    d.add(String(cx, cy - 2, f"%{int(round(yuzde))}", fontSize=20, fillColor=LACIVERT, textAnchor='middle', fontName='Helvetica-Bold'))
    d.add(String(cx, cy - 18, "doğruluk", fontSize=8, fillColor=colors.grey, textAnchor='middle'))
    return d


def prozodik_bar(toplam: float, genislik=300, yukseklik=54) -> Drawing:
    """Prozodik toplam (/20) için kırmızı/sarı/yeşil bantlı yatay bar + işaretçi."""
    toplam = max(0, min(20, float(toplam or 0)))
    d = Drawing(genislik, yukseklik)
    x0, bar_w, bar_h, y0 = 10, genislik - 20, 16, 22
    # Zeminler: 0-9 kırmızı, 10-13 sarı, 14-20 yeşil
    for a, b, renk in [(0, 10, KIRMIZI), (10, 14, SARI), (14, 20, YESIL)]:
        d.add(Rect(x0 + bar_w * a / 20, y0, bar_w * (b - a) / 20, bar_h, fillColor=renk, strokeColor=colors.white, strokeWidth=0.5))
    # İşaretçi (üçgen)
    mx = x0 + bar_w * toplam / 20
    d.add(Polygon([mx, y0 + bar_h + 6, mx - 5, y0 + bar_h + 14, mx + 5, y0 + bar_h + 14], fillColor=LACIVERT, strokeColor=colors.white))
    d.add(String(mx, y0 + bar_h + 16, f"{int(round(toplam))}/20", fontSize=9, fillColor=LACIVERT, textAnchor='middle', fontName='Helvetica-Bold'))
    for etk, xo in [("Zayıf", 2.5), ("Orta", 11.5), ("İyi", 17)]:
        d.add(String(x0 + bar_w * xo / 20, y0 - 10, etk, fontSize=7, fillColor=colors.grey, textAnchor='middle'))
    return d


def yatay_bar_dagilim(veriler: list, genislik=300, satir_yuk=16, baslik_alani=110) -> Drawing:
    """[(etiket, sayi)] için basit yatay bar dağılımı (hata türleri gibi)."""
    veriler = [(e, max(0, int(s or 0))) for e, s in veriler if s]
    if not veriler:
        return Drawing(genislik, 10)
    enb = max(s for _, s in veriler) or 1
    h = len(veriler) * satir_yuk + 8
    d = Drawing(genislik, h)
    bar_alan = genislik - baslik_alani - 30
    for i, (etk, s) in enumerate(veriler):
        y = h - (i + 1) * satir_yuk
        d.add(String(4, y + 3, etk[:22], fontSize=7.5, fillColor=colors.HexColor('#333333')))
        w = bar_alan * s / enb
        d.add(Rect(baslik_alani, y, max(1, w), satir_yuk - 6, fillColor=MAVI, strokeColor=None))
        d.add(String(baslik_alani + w + 4, y + 3, str(s), fontSize=8, fillColor=LACIVERT, fontName='Helvetica-Bold'))
    return d


def anlama_radar(eksenler: list, degerler: list, genislik=250, yukseklik=210) -> Drawing | None:
    """eksenler: [etiket], degerler: [0..3]. En az 3 eksen gerekir. Örümcek grafiği."""
    if len(eksenler) < 3:
        return None
    d = Drawing(genislik, yukseklik)
    sp = SpiderChart()
    sp.x, sp.y, sp.width, sp.height = 24, 14, genislik - 48, yukseklik - 36
    sp.data = [degerler]
    sp.labels = eksenler
    sp.strands[0].strokeColor = LACIVERT
    sp.strands[0].fillColor = colors.Color(0.18, 0.31, 0.47, 0.35)
    sp.strands[0].strokeWidth = 1.5
    sp.spokes.strokeColor = GRI
    for lab in sp.labels:
        pass
    try:
        sp.strandLabels.format = None
    except Exception:
        pass
    d.add(sp)
    return d


def norm_karsilastirma(ogrenci_wpm: float, norm_wpm: float, genislik=300, yukseklik=64) -> Drawing:
    """Öğrenci okuma hızı vs sınıf normu — iki yatay çubuk."""
    ogr = max(0, float(ogrenci_wpm or 0)); nrm = max(0, float(norm_wpm or 0))
    ust = max(ogr, nrm, 1) * 1.2
    d = Drawing(genislik, yukseklik)
    x0, bar_w, bh = 96, genislik - 130, 14
    for i, (etk, deger, renk) in enumerate([("Öğrenci", ogr, MAVI), ("Sınıf normu", nrm, GRI)]):
        y = yukseklik - (i + 1) * 26
        d.add(String(4, y + 3, etk, fontSize=8, fillColor=colors.HexColor('#333333')))
        w = bar_w * deger / ust
        d.add(Rect(x0, y, max(1, w), bh, fillColor=renk, strokeColor=None))
        d.add(String(x0 + w + 4, y + 3, f"{int(round(deger))}", fontSize=8, fillColor=LACIVERT, fontName='Helvetica-Bold'))
    return d
