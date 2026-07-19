# -*- coding: utf-8 -*-
"""olcum_parts/*.json ÇAPRAZ DOĞRULAMA — alt-ajan çıktısı kaynakla birebir mi?

Alt-ajanlar bazı uzun/düzensiz dosyalarda içerik UYDURDU/atladı (gözlemlendi).
Bu betik her sorunun `soru` ve (subjektif olmayan) `cevap` metninin, o dosyanın
HAM metninde (sorular_ham/cevap_ham/tam_ham) GERÇEKTEN bulunup bulunmadığını
kontrol eder. Bulunamayan = uydurma/paraphrase/yanlış eşleme → İNSAN KONTROLÜ.

Normalize: küçük harf + boşluk/noktalama at → alt-dize araması (yalnız boşluk
eklemeleri toleranslı; kelime değişikliği yakalanır).

Çıktı: konsol raporu (metin başına: soru sayısı, bulunamayan soru/cevap no'ları).
"""
import re
import json
import glob
from pathlib import Path

_DATA = Path(__file__).resolve().parent.parent / "data"
HAM = _DATA / "olcum_ham.json"
PARTS = _DATA / "olcum_parts"


def _norm(s: str) -> str:
    s = (s or "").lower()
    # Türkçe tırnak/tire çeşitlerini sadeleştir, sonra harf-dışını at
    s = s.replace("’", "'").replace("“", '"').replace("”", '"').replace("–", "-")
    return re.sub(r"[^0-9a-zçğıiöşü]", "", s)


def main():
    ham = {x["dosya"]: x for x in json.load(open(HAM, encoding="utf-8"))}
    parcalar = {}
    for pf in sorted(glob.glob(str(PARTS / "*.json"))):
        for k in json.load(open(pf, encoding="utf-8")):
            parcalar[k["dosya"]] = k

    print("═══ ÖLÇÜM ÇAPRAZ DOĞRULAMA (soru/cevap kaynakta var mı?) ═══\n")
    toplam_sorunlu = 0
    for dosya, h in ham.items():
        p = parcalar.get(dosya)
        if not p:
            print(f"‼ PARÇA YOK: {dosya}")
            toplam_sorunlu += 1
            continue
        kaynak_soru = _norm(h.get("sorular_ham", "") + h.get("tam_ham", ""))
        kaynak_cevap = _norm(h.get("cevap_ham", "") + h.get("tam_ham", ""))
        sorular = p.get("sorular", [])
        soru_yok, cevap_yok, bos_cevap = [], [], []
        for q in sorular:
            no = q.get("no")
            sn = _norm(q.get("soru", ""))
            if not sn:
                soru_yok.append(f"{no}(boş)")
            elif sn[:40] not in kaynak_soru:
                soru_yok.append(no)
            cev = q.get("cevap", "")
            cn = _norm(cev)
            if not cn:
                if not q.get("subjektif"):
                    bos_cevap.append(no)
            elif cn[:40] not in kaynak_cevap:
                cevap_yok.append(no)

        n = len(sorular)
        sorunlu = soru_yok or cevap_yok or bos_cevap or n < 10
        if sorunlu:
            toplam_sorunlu += 1
            print(f"‼ [{str(p.get('sinif_seviyesi')):>4}] {p.get('baslik','')[:32]:32} | soru={n}")
            if soru_yok:
                print(f"      SORU kaynakta yok/boş: {soru_yok}")
            if cevap_yok:
                print(f"      CEVAP kaynakta yok (paraphrase?): {cevap_yok}")
            if bos_cevap:
                print(f"      CEVAP boş (subjektif değil): {bos_cevap}")
        else:
            print(f"  ✓ [{str(p.get('sinif_seviyesi')):>4}] {p.get('baslik','')[:32]:32} | soru={n} — tüm soru/cevap kaynakta")

    print(f"\nSorunlu/incelenecek metin: {toplam_sorunlu}/{len(ham)}")


if __name__ == "__main__":
    main()
