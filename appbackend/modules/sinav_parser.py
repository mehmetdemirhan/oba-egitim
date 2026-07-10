"""Sınav PDF ayrıştırıcı — MEB LGS/Bursluluk sözel kağıtları.

Bu dosya bir ROUTE modülü DEĞİL (registry.json'a eklenmez); `modules/sinav.py`
tarafından import edilen saf bir yardımcıdır.

Yaklaşım (a_2026_sozel.pdf üzerinde doğrulanmış — 40/40 soru, 50/50 cevap):
  * PyMuPDF (fitz) tek bağımlılık; owner-password'lu PDF'i doğrudan okur (qpdf yok).
  * Koordinat-bazlı: soru numaraları sol margin (x0<~52) ve sağ-sütun margin'inde
    (~272<x0<300) "N." deseniyle tespit edilir; gövde metni ~x0=64'te başladığı
    için soru numarası sola taşar ve güvenilir işaret olur.
  * Bölüm (ders) sınırı: soru numarası her ders başında 1'e sıfırlanır + "TESTİ
    BİTTİ" ayraçları. Ders sırası sabit: Türkçe → İnkılap → Din → İngilizce.
    İngilizce bilinçli olarak ATLANIR (kapı kapatılmaz; enum genişletilebilir).
  * Her soru için sayfadaki bölgesi yüksek çözünürlükte PNG olarak kırpılır
    (soruBolgeGorseli). Altı çizili ifadeler ve görsel-seçenekli sorular bu
    görüntüde korunur — metin çıkarımının kaybettiği bilgi burada durur.
  * Cevap anahtarı son sayfadan (ders başlıklı, "N. X" formatı) çıkarılır ve
    (ders, soruNo) ile eşleştirilir.
"""
import base64
import re
from typing import List, Dict, Optional

try:
    import fitz  # PyMuPDF
except ImportError:  # pragma: no cover
    fitz = None

# ── Sabitler ──────────────────────────────────────────────────────────────
# Ders sırası SABİT (MEB sözel kağıdı düzeni). İngilizce en sonda ve atlanır.
DERS_SIRASI = ["turkce", "inkilap_tarihi", "din_kulturu", "ingilizce"]
DERS_ETIKET = {
    "turkce": "Türkçe",
    "inkilap_tarihi": "T.C. İnkılap Tarihi ve Atatürkçülük",
    "din_kulturu": "Din Kültürü ve Ahlak Bilgisi",
    "ingilizce": "İngilizce",
}
# Beklenen soru sayıları (doğrulama/segmentasyon güvencesi için).
DERS_BEKLENEN = {"turkce": 20, "inkilap_tarihi": 10, "din_kulturu": 10, "ingilizce": 10}
ATLANAN_DERSLER = {"ingilizce"}

# Soru numarası deseni: "3." / "12." (nokta bitişli 1-2 haneli sayı, tek kelime)
_QNO = re.compile(r"^(\d{1,2})\.$")
# Bölüm giriş sayfasındaki yönerge numaralarını ("1. Bu testte 20 soru vardır.",
# "2. Cevaplarınızı, cevap kâğıdına işaretleyiniz.") gerçek sorulardan ayırmak için:
# bu numaraları takip eden metin bu kalıpla başlar → yanlış-pozitif elenir.
_YONERGE = re.compile(r"^(Bu testte|Cevaplarınızı)", re.IGNORECASE)
# Cevap anahtarı çifti: "1. A" / "1.   A"
_ANAHTAR = re.compile(r"(\d{1,2})\.\s+([A-D])\b")
# Seçenek satırı başı: "A)" "B)" ...
_SECENEK = re.compile(r"^([A-D])\)\s*(.*)$")

_RENDER_OLCEK = 2.0   # get_pixmap matrix ölçeği (2x ≈ 144 DPI, admin/öğrenci için net)
_FOOTER_MARJI = 55    # sayfa alt bilgisi (sayfa no / "Diğer sayfaya geçiniz") payı
_UST_MARJI = 6        # soru numarasının biraz üstünden başla
_ICERIK_PAD = 8       # içerik-bbox sıkılaştırmasından sonra alt boşluk payı


def _kitapcik_turu(doc) -> str:
    """Kapak sayfasından kitapçık türünü (A/B) çıkar; bulunamazsa 'A'."""
    try:
        for w in doc.load_page(0).get_text("words"):
            t = w[4].strip().upper()
            if t in ("A", "B") and w[1] < 120:  # kapak üst kısmı
                return t
    except Exception:
        pass
    return "A"


def _sayfa_sorulari(page) -> List[dict]:
    """Sayfadaki soru-no adaylarını (col, y0, no) döndürür (okuma sırasında).

    Bölüm giriş sayfalarındaki yönerge numaraları ("1. Bu testte...", "2.
    Cevaplarınızı...") takip eden metne bakılarak elenir.
    """
    mid = page.rect.width / 2
    ws = page.get_text("words")
    bulunan = []
    for i, w in enumerate(ws):
        x0, y0, txt = w[0], w[1], w[4]
        m = _QNO.match(txt)
        if not m:
            continue
        # sol margin veya sağ-sütun margin'inde mi?
        if not (x0 < 52 or (272 < x0 < 300)):
            continue
        # takip eden metin yönerge kalıbıyla başlıyorsa → gerçek soru değil, atla
        sonraki = " ".join(ws[j][4] for j in range(i + 1, min(i + 5, len(ws))))
        if _YONERGE.match(sonraki.strip()):
            continue
        col = "L" if x0 < mid else "R"
        bulunan.append({"col": col, "y0": y0, "no": int(m.group(1)), "x0": x0})
    # okuma sırası: önce sol sütun (yukarıdan aşağı), sonra sağ sütun
    bulunan.sort(key=lambda q: (0 if q["col"] == "L" else 1, q["y0"]))
    return bulunan


def _icerik_alt_siniri(page, x0: float, x1: float, y_ust: float, y_alt: float) -> float:
    """Verilen kutu içindeki son içerik kelimesinin altını bulup boşluğu kırp."""
    en_alt = y_ust
    for w in page.get_text("words"):
        wx0, wy0, wx1, wy1 = w[0], w[1], w[2], w[3]
        # kutu içinde mi (yatayda kesişiyor, dikeyde aralıkta)?
        if wx1 > x0 and wx0 < x1 and wy0 >= y_ust - 2 and wy1 <= y_alt + 2:
            if wy1 > en_alt:
                en_alt = wy1
    if en_alt <= y_ust:
        return y_alt
    return min(y_alt, en_alt + _ICERIK_PAD)


def _bolge_png(page, x0: float, y0: float, x1: float, y1: float) -> bytes:
    """Sayfa bölgesini PNG byte'ına render eder."""
    clip = fitz.Rect(x0, y0 - _UST_MARJI, x1, y1)
    pix = page.get_pixmap(clip=clip, matrix=fitz.Matrix(_RENDER_OLCEK, _RENDER_OLCEK))
    return pix.tobytes("png")


def _bolge_metni(page, x0: float, y0: float, x1: float, y1: float) -> str:
    """Kutu içindeki metni okuma sırasında (satır-satır) toplar."""
    kelimeler = []
    for w in page.get_text("words"):
        wx0, wy0, wx1 = w[0], w[1], w[2]
        if wx0 >= x0 - 2 and wx1 <= x1 + 2 and wy0 >= y0 - _UST_MARJI and wy0 <= y1:
            kelimeler.append((round(wy0, 1), wx0, w[4]))
    kelimeler.sort(key=lambda k: (k[0], k[1]))
    # aynı satırdaki kelimeleri boşlukla, satırları newline ile birleştir
    satirlar, mevcut_y, buf = [], None, []
    for y, _x, t in kelimeler:
        if mevcut_y is None or abs(y - mevcut_y) <= 3:
            buf.append(t)
            mevcut_y = y if mevcut_y is None else mevcut_y
        else:
            satirlar.append(" ".join(buf))
            buf, mevcut_y = [t], y
    if buf:
        satirlar.append(" ".join(buf))
    return "\n".join(satirlar).strip()


def _metni_ayristir(metin: str) -> Dict:
    """Ham bölge metnini {soruMetni, secenekler{A..D}} olarak ayır (best-effort)."""
    satirlar = metin.split("\n")
    govde, secenekler, aktif = [], {}, None
    for s in satirlar:
        m = _SECENEK.match(s.strip())
        if m:
            aktif = m.group(1)
            secenekler[aktif] = m.group(2).strip()
        elif aktif and s.strip():
            secenekler[aktif] += " " + s.strip()  # şık devam satırı
        else:
            govde.append(s)
    # baştaki "N." soru numarasını gövdeden temizle
    govde_metni = "\n".join(govde).strip()
    govde_metni = re.sub(r"^\d{1,2}\.\s*", "", govde_metni)
    return {"soruMetni": govde_metni, "secenekler": secenekler}


def _sayfa_kirpimlari(page) -> List[dict]:
    """Bir sayfadaki her soru için kırpım kutusu + metin üretir."""
    W = page.rect.width
    mid = W / 2
    y_alt_sabit = page.rect.height - _FOOTER_MARJI
    sol_x = (33, mid - 2)
    sag_x = (mid + 2, W - 30)
    tam_x = (33, W - 30)

    qs = _sayfa_sorulari(page)
    if not qs:
        return []

    sonuc = []
    # Tek soru → tam-sayfa (görsel-seçenekli / uzun okuma parçası vakası)
    if len(qs) == 1:
        q = qs[0]
        x0, x1 = tam_x
        y1 = _icerik_alt_siniri(page, x0, x1, q["y0"], y_alt_sabit)
        sonuc.append(_soru_dict(page, q, x0, x1, y1, "FULL"))
        return sonuc

    # İki soru, farklı sütun → sütun bazlı kırpım
    cols = {q["col"] for q in qs}
    if len(qs) == 2 and len(cols) == 2:
        for q in qs:
            x0, x1 = sol_x if q["col"] == "L" else sag_x
            y1 = _icerik_alt_siniri(page, x0, x1, q["y0"], y_alt_sabit)
            sonuc.append(_soru_dict(page, q, x0, x1, y1, q["col"]))
        return sonuc

    # Genel geri-dönüş: her soruyu, okuma sırasında bir sonrakine kadar tam-genişlik
    # dilimle (admin onayda görsel referansla düzeltir).
    for i, q in enumerate(qs):
        x0, x1 = tam_x
        y_sonraki = qs[i + 1]["y0"] if i + 1 < len(qs) else y_alt_sabit
        y1 = _icerik_alt_siniri(page, x0, x1, q["y0"], y_sonraki)
        sonuc.append(_soru_dict(page, q, x0, x1, y1, "FULL"))
    return sonuc


def _soru_dict(page, q, x0, x1, y1, sutun) -> dict:
    png = _bolge_png(page, x0, q["y0"], x1, y1)
    ham_metin = _bolge_metni(page, x0, q["y0"], x1, y1)
    ayr = _metni_ayristir(ham_metin)
    # gösterim türü ön-tahmini: 4 temiz metin şıkkı çıktıysa "metin", yoksa "gorsel"
    dolu_secenek = sum(1 for v in ayr["secenekler"].values() if v)
    gosterim = "metin" if dolu_secenek >= 4 and len(ayr["soruMetni"]) > 15 else "gorsel"
    return {
        "soruNo": q["no"],
        "sayfa": page.number + 1,
        "sutun": sutun,
        "soruMetni": ayr["soruMetni"],
        "secenekler": ayr["secenekler"],
        "soruBolgeGorseli_b64": base64.b64encode(png).decode("ascii"),
        "gosterimTuru": gosterim,
    }


def _cevap_anahtari(doc) -> Dict[str, Dict[int, str]]:
    """Son sayfadan ders bazlı cevap anahtarını çıkar.

    Numaralar ders bazında sıfırlandığı için, çiftler soru-no sıfırlamasıyla
    segmentlere ayrılır ve DERS_SIRASI ile eşleştirilir.
    """
    last = doc.load_page(doc.page_count - 1)
    ciftler = _ANAHTAR.findall(last.get_text())
    gruplar, mevcut, onceki = [], [], 0
    for no_s, harf in ciftler:
        no = int(no_s)
        if no == 1 and mevcut:  # yeni ders bloğu
            gruplar.append(mevcut)
            mevcut = []
        mevcut.append((no, harf))
        onceki = no
    if mevcut:
        gruplar.append(mevcut)

    anahtar: Dict[str, Dict[int, str]] = {}
    for idx, grup in enumerate(gruplar):
        if idx >= len(DERS_SIRASI):
            break
        ders = DERS_SIRASI[idx]
        anahtar[ders] = {no: harf for no, harf in grup}
    return anahtar


def parse_sinav_pdf(pdf_bytes: bytes) -> Dict:
    """MEB sözel sınav PDF'ini ayrıştırır.

    Dönüş:
      {
        "kitapcikTuru": "A"|"B",
        "sorular": [ {ders, soruNo, sayfa, soruMetni, secenekler, gosterimTuru,
                      soruBolgeGorseli_b64, dogruCevap}, ... ],   # İngilizce hariç
        "uyarilar": [str, ...],
        "istatistik": {ders: {"bulunan": n, "beklenen": m}, ...},
      }
    """
    if fitz is None:
        raise RuntimeError("PyMuPDF (fitz) kurulu değil — PDF ayrıştırılamıyor.")

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    kitapcik = _kitapcik_turu(doc)
    anahtar = _cevap_anahtari(doc)
    uyarilar: List[str] = []

    # 1) Tüm içerik sayfalarındaki kırpımları okuma sırasında topla.
    tum_kirpimlar = []  # her biri _soru_dict + geçici alanlar
    for pno in range(2, doc.page_count - 1):  # kapak(1-2) sonrası .. cevap anahtarı öncesi
        page = doc.load_page(pno)
        tum_kirpimlar.extend(_sayfa_kirpimlari(page))

    # 2) Soru numarası sıfırlamasıyla ders segmentlerine böl.
    segmentler, mevcut = [], []
    for k in tum_kirpimlar:
        if k["soruNo"] == 1 and mevcut:
            segmentler.append(mevcut)
            mevcut = []
        mevcut.append(k)
    if mevcut:
        segmentler.append(mevcut)

    # 3) Segmentleri DERS_SIRASI ile eşleştir, İngilizce'yi atla, cevabı bağla.
    sorular = []
    istatistik = {}
    for idx, seg in enumerate(segmentler):
        if idx >= len(DERS_SIRASI):
            uyarilar.append(f"Beklenmeyen ek bölüm (segment {idx + 1}) atlandı.")
            continue
        ders = DERS_SIRASI[idx]
        istatistik[ders] = {"bulunan": len(seg), "beklenen": DERS_BEKLENEN.get(ders, 0)}
        if ders in ATLANAN_DERSLER:
            continue
        ders_anahtar = anahtar.get(ders, {})
        for k in seg:
            dogru = ders_anahtar.get(k["soruNo"])
            if not dogru:
                uyarilar.append(f"{DERS_ETIKET[ders]} {k['soruNo']}. soru: cevap anahtarı eşleşmedi.")
            sorular.append({
                "ders": ders,
                "soruNo": k["soruNo"],
                "sayfa": k["sayfa"],
                "soruMetni": k["soruMetni"],
                "secenekler": k["secenekler"],
                "gosterimTuru": k["gosterimTuru"],
                "soruBolgeGorseli_b64": k["soruBolgeGorseli_b64"],
                "dogruCevap": dogru,
            })

    # 4) Kapsam doğrulaması → uyarı üret (>%15 eksikse çağıran karar verir).
    for ders, exp in DERS_BEKLENEN.items():
        if ders in ATLANAN_DERSLER:
            continue
        bulunan = istatistik.get(ders, {}).get("bulunan", 0)
        if bulunan < exp:
            uyarilar.append(f"{DERS_ETIKET[ders]}: {bulunan}/{exp} soru bulundu (eksik).")

    return {
        "kitapcikTuru": kitapcik,
        "sorular": sorular,
        "uyarilar": uyarilar,
        "istatistik": istatistik,
    }
