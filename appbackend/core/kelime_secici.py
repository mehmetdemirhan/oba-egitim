"""Kelime seçici — kelime egzersizleri için ortak öncelik mantığı.

Öncelik sırası:
  1. MEB müfredat kelimeleri (meb_kelimeleri koleksiyonu; o sınıf, durum=aktif,
     anlamı dolu) — yönetici tarafından yüklenen resmi liste.
  2. Genel Türkçe havuz (core/turkce_kelime_havuzu) ile tamamlanır.
  3. AI ile üretim (bu katmanda YOK) — çağıran modülün son çaresi.

Bu modül egzersiz modüllerinin İÇ mantığına dokunmadan, yalnızca "kelime seçim"
noktasında çağrılır.
"""
from __future__ import annotations

import random
import logging

from core.db import db
from core.turkce_kelime_havuzu import sinif_kelimeleri, tr_kucuk


async def meb_kelime_kayitlari(sinif: int, sadece_anlamli: bool = True,
                               limit: int = 500) -> list[dict]:
    """MEB kelime kayıtlarını (dict) döndürür. En az kullanılan önce."""
    try:
        sorgu: dict = {"sinif": int(sinif), "durum": "aktif"}
        if sadece_anlamli:
            sorgu["anlam"] = {"$nin": [None, ""]}
        docs = await db.meb_kelimeleri.find(sorgu).sort("kullanim_sayisi", 1).to_list(length=limit)
        for d in docs:
            d.pop("_id", None)
        return docs
    except Exception as ex:
        logging.warning(f"[kelime_secici] MEB sorgu hatası: {ex}")
        return []


async def meb_kelime_stringleri(sinif: int, sadece_anlamli: bool = False,
                                limit: int = 500) -> list[str]:
    """Sadece kelime string'lerini (küçük harf, tekilleştirilmiş) döndürür."""
    docs = await meb_kelime_kayitlari(sinif, sadece_anlamli=sadece_anlamli, limit=limit)
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
                     istatistik: bool = True) -> list[dict]:
    """Sınıf seviyesine uygun `sayi` kadar kelime döndürür.

    Öncelik: MEB (anlamlı) → genel havuz. Dönüş öğeleri:
      {"kelime", "anlam", "ornek_cumle", "kaynak": "meb"|"havuz"}

    tip: bazı egzersizler için ipucu (ör. "es_anlamli" AI gerektirir); şu an
    yalnızca kaynak önceliğini etkilemez, çağıran modül için bilgi amaçlı.
    """
    sayi = max(0, int(sayi))
    out: list[dict] = []
    gorulen: set[str] = set()

    meb = await meb_kelime_kayitlari(sinif, sadece_anlamli=True)
    random.shuffle(meb)
    for d in meb:
        k = tr_kucuk(str(d.get("kelime", "")).strip())
        if not k or k in gorulen:
            continue
        gorulen.add(k)
        out.append({
            "kelime": k,
            "anlam": d.get("anlam", ""),
            "ornek_cumle": d.get("ornek_cumle", ""),
            "kaynak": "meb",
        })
        if len(out) >= sayi:
            break

    if len(out) < sayi:
        havuz = list(sinif_kelimeleri(sinif))
        random.shuffle(havuz)
        for k in havuz:
            k = tr_kucuk(k)
            if k in gorulen:
                continue
            gorulen.add(k)
            out.append({"kelime": k, "anlam": "", "ornek_cumle": "", "kaynak": "havuz"})
            if len(out) >= sayi:
                break

    if istatistik:
        secilen_meb = [o["kelime"] for o in out if o["kaynak"] == "meb"]
        await _kullanim_artir(sinif, secilen_meb)

    return out
