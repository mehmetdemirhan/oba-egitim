# -*- coding: utf-8 -*-
"""ÖLÇÜM METİNLERİ PDF'lerini metin katmanından çıkarır (Gemini GEREKMEZ — bu
dosyaların ToUnicode eşlemesi çalışıyor, PyMuPDF birebir temiz Türkçe veriyor).

Her PDF 3 mantıksal bölüme ayrılır:
  1) başlık + (kelime_sayisi) + gövde   → "Anlama Soruları"na kadar
  2) sorular_ham                        → "Anlama Soruları" ile "Cevap Anahtarı" arası
  3) cevap_ham                          → "Cevap Anahtarı" sonrası

sinif_seviyesi klasör adından türetilir (1..8 sayısal, "lise").

Çıktı: appbackend/data/olcum_ham.json  (29 kayıt, ham 3 bölüm — parse ETMEZ).
Bu adım deterministik ve kayıpsızdır; soru/cevap yapılandırması ayrı adımda.

Çalıştırma (appbackend dizininden):
  set PYTHONIOENCODING=utf-8
  .venv/Scripts/python.exe scripts/olcum_extract.py
"""
import os
import re
import json
import glob
from pathlib import Path

import fitz  # PyMuPDF

KOK = Path(__file__).resolve().parent.parent.parent   # proje kökü
KAYNAK_DIR = KOK / "ÖLÇÜM METİNLERİ"
CIKTI = Path(__file__).resolve().parent.parent / "data" / "olcum_ham.json"

# Klasör adı → sinif_seviyesi (1..8 int, "lise")
def _sinif_coz(klasor: str):
    # Türkçe İ/ı sorununu aş: İ→I, sonra lower (Python "LİSE".lower() → "li̇se")
    s = klasor.replace("İ", "I").replace("ı", "i").strip().lower()
    if "lise" in s:
        return "lise"
    m = re.match(r"(\d+)", s)
    return int(m.group(1)) if m else None


def _sayfalari_birlestir(doc) -> str:
    # Sayfaları tek boşlukla birleştir; satır sonları anlamlı değil (akış metni).
    return "\n".join(p.get_text() for p in doc)


def _bol(tam: str):
    """(baslik, kelime_sayisi, govde, sorular_ham, cevap_ham) döner."""
    # 1) "Anlama Soruları" / "Cevap Anahtarı" ayraçları — büyük/küçük harf ve
    #    Türkçe i/ı toleranslı (LİSE dosyaları CAPS: "ANLAMA SORULARI").
    m_sor = re.search(r"anlama\s*sorular[ıi]", tam, re.IGNORECASE)
    m_cev = re.search(r"cevap\s*anahtar[ıi]", tam, re.IGNORECASE)

    if m_sor:
        bas_govde = tam[:m_sor.start()]
        if m_cev:
            sorular_ham = tam[m_sor.end():m_cev.start()]
            cevap_ham = tam[m_cev.end():]
        else:
            sorular_ham = tam[m_sor.end():]
            cevap_ham = ""
    else:
        bas_govde = tam
        sorular_ham = ""
        cevap_ham = tam[m_cev.end():] if m_cev else ""

    # 2) başlık + (kelime sayısı) — ilk parantez içindeki sayı
    bg = bas_govde.strip()
    m_wc = re.search(r"\((\d+)\)", bg)
    if m_wc:
        baslik = bg[:m_wc.start()].strip()
        kelime_sayisi = int(m_wc.group(1))
        govde = bg[m_wc.end():].strip()
    else:
        baslik = ""
        kelime_sayisi = None
        govde = bg

    return baslik, kelime_sayisi, govde, sorular_ham.strip(), cevap_ham.strip()


def main():
    kayitlar = []
    for klasor in sorted(os.listdir(KAYNAK_DIR)):
        kp = KAYNAK_DIR / klasor
        if not kp.is_dir():
            continue
        sinif = _sinif_coz(klasor)
        for pdf in sorted(glob.glob(str(kp / "*.pdf"))):
            doc = fitz.open(pdf)
            tam = _sayfalari_birlestir(doc)
            baslik, wc, govde, sorular_ham, cevap_ham = _bol(tam)
            kayitlar.append({
                "dosya": os.path.basename(pdf),
                "klasor": klasor,
                "sinif_seviyesi": sinif,
                "sayfa": doc.page_count,
                "baslik": baslik,
                "kelime_sayisi": wc,
                "govde": govde,
                "sorular_ham": sorular_ham,
                "cevap_ham": cevap_ham,
                # başlıksız/farklı biçimli dosyalar için tam ham metin (yapılandırma yedeği)
                "tam_ham": tam,
                # kaba gerçek kelime sayısı (doğrulama için)
                "govde_gercek_kelime": len(govde.split()),
            })

    CIKTI.parent.mkdir(exist_ok=True)
    with open(CIKTI, "w", encoding="utf-8") as f:
        json.dump(kayitlar, f, ensure_ascii=False, indent=2)

    print(f"✓ {len(kayitlar)} PDF çıkarıldı → {CIKTI}")
    # Özet + uyarılar
    for k in kayitlar:
        uyari = []
        if not k["baslik"]:
            uyari.append("BAŞLIK-YOK")
        if k["kelime_sayisi"] is None:
            uyari.append("KELİME-YOK")
        if not k["sorular_ham"]:
            uyari.append("SORU-YOK")
        if not k["cevap_ham"]:
            uyari.append("CEVAP-YOK")
        fark = ""
        if k["kelime_sayisi"]:
            d = abs(k["govde_gercek_kelime"] - k["kelime_sayisi"])
            if d > max(15, k["kelime_sayisi"] * 0.25):
                fark = f" ⚠kelime-fark({k['govde_gercek_kelime']}≠{k['kelime_sayisi']})"
        bayrak = ("  ‼ " + ",".join(uyari)) if uyari else ""
        print(f"  [{str(k['sinif_seviyesi']):>4}] {k['baslik'][:38]:38} wc={k['kelime_sayisi']}{fark}{bayrak}")


if __name__ == "__main__":
    main()
