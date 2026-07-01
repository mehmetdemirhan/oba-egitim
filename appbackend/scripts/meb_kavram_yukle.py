"""Toplu MEB kavram yükleme scripti.

Kullanım (appbackend dizininde):
    set PYTHONIOENCODING=utf-8
    .venv/Scripts/python.exe scripts/meb_kavram_yukle.py <ders_kodu> <json_dosyasi>

Örnek:
    .venv/Scripts/python.exe scripts/meb_kavram_yukle.py turkce meb_anahtar_kavramlar.json

ders_kodu: turkce | hayat_bilgisi | sosyal_bilgiler | din_kulturu | inkilap_tarihi
JSON formatı: {"1": ["kavram1", "kavram2"], "2": [...], ...}

Her sınıf için kelimeler meb_kelimeleri koleksiyonuna eklenir (mevcutlar atlanır),
ardından AI anlam/örnek üretimi çalıştırılır (senkron — script bitmeden tamamlanır).
"""
import asyncio
import json
import os
import sys
import uuid
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def run(ders: str, json_yolu: str):
    from core.db import db
    from modules.meb_kelime import (
        DERSLER, _ders_gecerli, _sinif_derste, _tr_kucuk, _zorluk, _ai_kuyrugu_isle,
    )

    if not _ders_gecerli(ders):
        print(f"Geçersiz ders: {ders}. Seçenekler: {', '.join(DERSLER)}")
        return
    if not os.path.exists(json_yolu):
        print(f"Dosya bulunamadı: {json_yolu}")
        return

    with open(json_yolu, encoding="utf-8") as f:
        veri = json.load(f)

    print(f"== {DERSLER[ders]['ad']} kavram yükleme ==")
    now = datetime.utcnow().isoformat()
    islenecek_siniflar = []
    for sinif_str, kelimeler in veri.items():
        try:
            sinif = int(sinif_str)
        except (TypeError, ValueError):
            print(f"  ! '{sinif_str}' geçersiz sınıf, atlandı")
            continue
        if not _sinif_derste(ders, sinif):
            print(f"  ! {sinif}. sınıf bu derste yok, atlandı")
            continue
        yeni = 0
        for ham in (kelimeler or []):
            k = _tr_kucuk(str(ham).strip())
            if len(k) < 2:
                continue
            if await db.meb_kelimeleri.find_one({"kelime": k, "sinif": sinif, "ders": ders}):
                continue
            await db.meb_kelimeleri.insert_one({
                "id": str(uuid.uuid4()), "kelime": k, "sinif": sinif, "ders": ders,
                "kaynak_dosya": os.path.basename(json_yolu), "anlam": "", "ornek_cumle": "",
                "zorluk": _zorluk(k, sinif), "durum": "aktif", "onaylandi": True,
                "etiketler": [], "ai_uretim_tarihi": None, "yukleme_tarihi": now,
                "yukleyen_id": "script", "yukleyen_ad": "Toplu Yükleme", "kullanim_sayisi": 0,
            })
            yeni += 1
        print(f"  {sinif}. sınıf: {yeni} yeni kelime")
        if yeni:
            islenecek_siniflar.append(sinif)

    # AI üretimi (senkron — script bitmeden tamamlansın)
    for sinif in islenecek_siniflar:
        print(f"  AI üretimi: {sinif}. sınıf…")
        await _ai_kuyrugu_isle(sinif, ders)
    print("Tamamlandı.")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Kullanım: python scripts/meb_kavram_yukle.py <ders_kodu> <json_dosyasi>")
        sys.exit(1)
    asyncio.run(run(sys.argv[1], sys.argv[2]))
