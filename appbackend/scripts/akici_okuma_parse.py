"""AKICI OKUMA METİNLERİ YENİ.docx → yapısal JSON + doğrulama raporu.

Format (150 metin): başlık "Metin Adı (kelimeSayısı)" → metin paragrafları →
"OKUDUĞUNU ANLAMA SORULARI N" → 5 çoktan seçmeli (A-D) → "Açık Uçlu Sorular:" → ~5 açık uçlu.

Kullanım:
    cd appbackend && .venv/Scripts/python.exe scripts/akici_okuma_parse.py
Çıktı: data/akici_okuma_metinleri.json + konsola doğrulama raporu.
"""
import os
import re
import json

KOK = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DOCX = os.path.join(KOK, "AKICI OKUMA METİNLERİ YENİ.docx")
CIKTI = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "akici_okuma_metinleri.json")

BASLIK_RE = re.compile(r"^(.+?)\s*\((\d+)\)\s*$")
SIK_RE = re.compile(r"^([A-Da-d])[\)\.\-]\s*(.+)$")


def parse():
    import docx
    d = docx.Document(DOCX)
    paras = [p.text.strip() for p in d.paragraphs]

    # Başlık satırlarının indexleri (metin sınırları)
    basliklar = []
    for i, t in enumerate(paras):
        m = BASLIK_RE.match(t)
        if m and 0 < len(m.group(1).strip()) < 80 and not m.group(1).strip().upper().startswith("OKUDU"):
            basliklar.append((i, m.group(1).strip(), int(m.group(2))))

    metinler = []
    uyarilar = []
    for bi, (idx, ad, kelime) in enumerate(basliklar):
        son = basliklar[bi + 1][0] if bi + 1 < len(basliklar) else len(paras)
        blok = paras[idx + 1:son]
        # anlama sorusu işareti
        anlama_idx = next((j for j, t in enumerate(blok) if "OKUDUĞUNU ANLAMA SORULARI" in t.upper()), None)
        acik_idx = next((j for j, t in enumerate(blok) if "AÇIK UÇLU" in t.upper()), None)
        if anlama_idx is None:
            uyarilar.append(f"[{ad}] 'OKUDUĞUNU ANLAMA SORULARI' işareti yok")
            icerik = "\n".join([b for b in blok if b])
            metinler.append({"baslik": ad, "kelime_sayisi": kelime, "icerik": icerik, "sorular": [], "acik_uclu": []})
            continue
        icerik = "\n".join([b for b in blok[:anlama_idx] if b])

        soru_blok = blok[anlama_idx + 1:acik_idx] if acik_idx is not None else blok[anlama_idx + 1:]
        acik_blok = blok[acik_idx + 1:] if acik_idx is not None else []

        # Çoktan seçmeli — İKİ format da desteklenir: (A) soru+şıklar tek paragrafta
        # (\n'li), (B) soru ve her şık ayrı paragrafta. Tüm satırları düzleştirip yürü.
        satirlar = []
        for t in soru_blok:
            for s in t.split("\n"):
                s = s.strip()
                if s:
                    satirlar.append(s)
        sorular = []
        i = 0
        while i < len(satirlar):
            s = satirlar[i]
            if SIK_RE.match(s):  # başıboş şık → atla
                i += 1
                continue
            soru_metni = re.sub(r"^\s*\d+[\.\)]\s*", "", s).strip()
            secenekler = {}
            k = i + 1
            while k < len(satirlar) and len(secenekler) < 4:
                ms = SIK_RE.match(satirlar[k])
                if ms:
                    secenekler[ms.group(1).upper()] = ms.group(2).strip()
                    k += 1
                else:
                    break
            if soru_metni and len(secenekler) >= 2:
                sorular.append({"soru": soru_metni, "secenekler": secenekler})
                i = k
            else:
                i += 1

        acik_uclu = []
        for t in acik_blok:
            if t and not t.upper().startswith("AÇIK"):
                acik_uclu.append(re.sub(r"^\s*\d+[\.\)]\s*", "", t).strip())

        if len(sorular) != 5:
            uyarilar.append(f"[{ad}] çoktan seçmeli soru sayısı {len(sorular)} (beklenen 5)")
        if len(icerik) < 20:
            uyarilar.append(f"[{ad}] metin içeriği çok kısa ({len(icerik)} karakter)")

        metinler.append({
            "baslik": ad, "kelime_sayisi": kelime, "icerik": icerik,
            "sorular": sorular, "acik_uclu": acik_uclu,
        })

    return metinler, uyarilar


def main():
    print("docx yükleniyor (33MB)...")
    metinler, uyarilar = parse()
    toplam_mc = sum(len(m["sorular"]) for m in metinler)
    toplam_acik = sum(len(m["acik_uclu"]) for m in metinler)
    tam5 = sum(1 for m in metinler if len(m["sorular"]) == 5)

    print("\n=== DOĞRULAMA RAPORU ===")
    print(f"Toplam metin: {len(metinler)}")
    print(f"5 çoktan seçmeli sorusu TAM olan metin: {tam5} / {len(metinler)}")
    print(f"Toplam çoktan seçmeli soru: {toplam_mc}")
    print(f"Toplam açık uçlu soru: {toplam_acik}")
    print(f"Kelime sayısı aralığı: {min(m['kelime_sayisi'] for m in metinler)} – {max(m['kelime_sayisi'] for m in metinler)}")
    print(f"Format uyarısı: {len(uyarilar)}")
    for u in uyarilar[:25]:
        print("  ! " + u)
    if len(uyarilar) > 25:
        print(f"  ... ve {len(uyarilar) - 25} uyarı daha")

    os.makedirs(os.path.dirname(CIKTI), exist_ok=True)
    with open(CIKTI, "w", encoding="utf-8") as f:
        json.dump(metinler, f, ensure_ascii=False, indent=1)
    print(f"\nYapısal veri kaydedildi: {CIKTI}")


if __name__ == "__main__":
    main()
