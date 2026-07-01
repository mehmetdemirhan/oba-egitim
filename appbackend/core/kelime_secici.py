"""Kelime seçici — kelime egzersizleri için ortak öncelik mantığı.

Öncelik sırası:
  1. MEB müfredat kelimeleri (meb_kelimeleri; o sınıf, durum=aktif, anlamı dolu)
     — yönetici tarafından yüklenen resmi liste.
  2. AI Eğit / kitap kelimeleri (meb_kelime_haritasi) — öğretmenin yüklediği
     kitaplardan çıkarılan/hafızaya alınan kelimeler (köprülenmiştir).
  3. Genel Türkçe havuz (core/turkce_kelime_havuzu) ile tamamlanır.
  4. AI ile üretim (bu katmanda YOK) — çağıran modülün son çaresi.

Bu modül egzersiz modüllerinin İÇ mantığına dokunmadan, yalnızca "kelime seçim"
noktasında çağrılır.
"""
from __future__ import annotations

import random
import logging

from core.db import db
from core.turkce_kelime_havuzu import sinif_kelimeleri, tr_kucuk


async def meb_kelime_kayitlari(sinif: int, sadece_anlamli: bool = True,
                               limit: int = 500, ders_filtre: list | None = None) -> list[dict]:
    """MEB kelime kayıtlarını (dict) döndürür — İKİ havuz köprülü, öncelik sırasıyla:

      1. meb_kelimeleri  — yönetici MEB müfredatı (durum=aktif); en az kullanılan önce.
      2. meb_kelime_haritasi — AI Eğit / kitaptan çıkarılan kelimeler (ders alanı yok,
         Türkçe/genel sayılır; durum alanı yok, hepsi aktif kabul edilir).

    Kelime bazında tekilleştirilir (müfredat kaydı önceliklidir). ders_filtre yalnızca
    meb_kelimeleri'ne uygulanır; harita yalnızca ders_filtre None veya 'turkce'
    içeriyorsa dahil edilir (harita kitap/Türkçe kaynaklıdır).
    """
    out: list[dict] = []
    gorulen: set[str] = set()

    # 1) Müfredat (meb_kelimeleri)
    try:
        sorgu: dict = {"sinif": int(sinif), "durum": "aktif"}
        if sadece_anlamli:
            sorgu["anlam"] = {"$nin": [None, ""]}
        if ders_filtre:
            sorgu["ders"] = {"$in": list(ders_filtre)}
        docs = await db.meb_kelimeleri.find(sorgu).sort("kullanim_sayisi", 1).to_list(length=limit)
        for d in docs:
            k = tr_kucuk(str(d.get("kelime", "")).strip())
            if not k or k in gorulen:
                continue
            gorulen.add(k)
            d.pop("_id", None)
            out.append(d)
    except Exception as ex:
        logging.warning(f"[kelime_secici] meb_kelimeleri sorgu hatası: {ex}")

    # 2) AI Eğit / kitap haritası (meb_kelime_haritasi) — Türkçe/genel kaynak
    harita_dahil = (not ders_filtre) or ("turkce" in ders_filtre)
    if harita_dahil and len(out) < limit:
        try:
            h_sorgu: dict = {"sinif": int(sinif)}
            if sadece_anlamli:
                h_sorgu["anlam"] = {"$nin": [None, ""]}
            h_docs = await db.meb_kelime_haritasi.find(h_sorgu).to_list(length=limit)
            for d in h_docs:
                k = tr_kucuk(str(d.get("kelime", "")).strip())
                if not k or k in gorulen:
                    continue
                gorulen.add(k)
                d.pop("_id", None)
                d.setdefault("ders", "turkce")
                out.append(d)
                if len(out) >= limit:
                    break
        except Exception as ex:
            logging.warning(f"[kelime_secici] meb_kelime_haritasi sorgu hatası: {ex}")

    return out


async def meb_kelime_stringleri(sinif: int, sadece_anlamli: bool = False,
                                limit: int = 500, ders_filtre: list | None = None) -> list[str]:
    """Sadece kelime string'lerini (küçük harf, tekilleştirilmiş) döndürür."""
    docs = await meb_kelime_kayitlari(sinif, sadece_anlamli=sadece_anlamli, limit=limit, ders_filtre=ders_filtre)
    gorulen: set[str] = set()
    out: list[str] = []
    for d in docs:
        k = tr_kucuk(str(d.get("kelime", "")).strip())
        if k and k not in gorulen:
            gorulen.add(k)
            out.append(k)
    return out


async def _kullanim_artir(sinif: int, kelimeler: list[str]):
    """Seçilen MEB kelimelerinin kullanım sayacını artırır (istatistik)."""
    if not kelimeler:
        return
    try:
        await db.meb_kelimeleri.update_many(
            {"sinif": int(sinif), "kelime": {"$in": kelimeler}},
            {"$inc": {"kullanim_sayisi": 1}},
        )
    except Exception as ex:
        logging.warning(f"[kelime_secici] kullanım artırma hatası: {ex}")


async def kelime_sec(sinif: int, sayi: int, tip: str = "genel",
                     ders_filtre: list | None = None, meb_orani: float = 0.7,
                     istatistik: bool = True) -> list[dict]:
    """Sınıf seviyesine uygun `sayi` kadar kelime döndürür.

    Öncelik: MEB (anlamlı, ders_filtre'ye uyan) → genel havuz. Dönüş öğeleri:
      {"kelime", "anlam", "ornek_cumle", "ders", "kaynak": "meb"|"havuz"}

    ders_filtre: None → tüm dersler karışık; liste → yalnızca o dersler.
    meb_orani: MEB kelimelerinin hedef oranı (0-1). Havuz yetersizse MEB ile
      tamamlanır; MEB yetersizse havuzla tamamlanır (yani öncelik yine MEB'de).
    """
    sayi = max(0, int(sayi))
    meb_hedef = sayi if meb_orani >= 1 else max(1, round(sayi * meb_orani))
    out: list[dict] = []
    gorulen: set[str] = set()

    meb = await meb_kelime_kayitlari(sinif, sadece_anlamli=True, ders_filtre=ders_filtre)
    random.shuffle(meb)

    def _meb_ekle(hedef):
        for d in meb:
            if len(out) >= hedef:
                break
            k = tr_kucuk(str(d.get("kelime", "")).strip())
            if not k or k in gorulen:
                continue
            gorulen.add(k)
            out.append({
                "kelime": k, "anlam": d.get("anlam", ""),
                "ornek_cumle": d.get("ornek_cumle", ""),
                "ders": d.get("ders", "turkce"), "kaynak": "meb",
            })

    # 1) MEB'den hedef orana kadar
    _meb_ekle(min(meb_hedef, sayi))

    # 2) Genel havuzla tamamla
    if len(out) < sayi:
        havuz = list(sinif_kelimeleri(sinif))
        random.shuffle(havuz)
        for k in havuz:
            k = tr_kucuk(k)
            if k in gorulen:
                continue
            gorulen.add(k)
            out.append({"kelime": k, "anlam": "", "ornek_cumle": "", "ders": None, "kaynak": "havuz"})
            if len(out) >= sayi:
                break

    # 3) Hâlâ eksikse kalan MEB kelimeleriyle tamamla (öncelik MEB'de)
    if len(out) < sayi:
        _meb_ekle(sayi)

    if istatistik:
        secilen_meb = [o["kelime"] for o in out if o["kaynak"] == "meb"]
        await _kullanim_artir(sinif, secilen_meb)

    return out
