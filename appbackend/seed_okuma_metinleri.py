"""
OBA okuma metinleri yükleme scripti.

Kök dizindeki 'okuma_metinleri analiz.docx' dosyasındaki 32 metni
(8 sınıf x 4 metin) analiz_metinler koleksiyonuna 'havuzda' durumunda yazar.
Idempotent: kaynak='seed_oba_v1' etiketiyle aynı (sinif, baslik) varsa atlar.

Kullanım:
  python seed_okuma_metinleri.py             → tüm 32 metni yükler
  python seed_okuma_metinleri.py --sinif=3   → sadece 3. sınıfın 4 metnini yükler
"""

import argparse
import asyncio
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from docx import Document
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

DOCX_PATH = ROOT_DIR.parent / "okuma_metinleri analiz.docx"
SEED_TAG = "seed_oba_v1"

SINIF_RE = re.compile(r"^\s*(\d+)\.\s*S[Iı][Nn][Iı][Ff]\s*$")
METIN_BASLIK_RE = re.compile(
    r"^\s*(\d+)\.\s*(.+?)\s*\|\s*T[üu]r:\s*(.+?)\s*\|\s*(\d+)\s*kelime\s*$",
    re.IGNORECASE,
)


def parse_docx(path: Path):
    """Word dosyasını parse eder, [{sinif, baslik, tur, kelime_sayisi, icerik}] döner."""
    if not path.exists():
        raise FileNotFoundError(f"Dosya yok: {path}")

    doc = Document(str(path))
    metinler = []
    aktif_sinif = None
    aktif_metin = None

    for p in doc.paragraphs:
        text = (p.text or "").strip()
        if not text:
            if aktif_metin is not None:
                aktif_metin["paragraflar"].append("")
            continue

        m_sinif = SINIF_RE.match(text)
        if m_sinif:
            if aktif_metin is not None:
                metinler.append(aktif_metin)
                aktif_metin = None
            aktif_sinif = int(m_sinif.group(1))
            continue

        m_baslik = METIN_BASLIK_RE.match(text)
        if m_baslik and aktif_sinif is not None:
            if aktif_metin is not None:
                metinler.append(aktif_metin)
            aktif_metin = {
                "sinif": aktif_sinif,
                "baslik": m_baslik.group(2).strip(),
                "tur": m_baslik.group(3).strip(),
                "kelime_sayisi": int(m_baslik.group(4)),
                "paragraflar": [],
            }
            continue

        if aktif_metin is not None:
            aktif_metin["paragraflar"].append(text)

    if aktif_metin is not None:
        metinler.append(aktif_metin)

    for m in metinler:
        m["icerik"] = "\n\n".join(m["paragraflar"]).strip()
        m["icerik"] = re.sub(r"\n{3,}", "\n\n", m["icerik"])
        del m["paragraflar"]

    return metinler


async def seed(sinif_filter: int | None = None):
    metinler = parse_docx(DOCX_PATH)
    print(f"Word dosyasından {len(metinler)} metin parse edildi.")

    if sinif_filter is not None:
        metinler = [m for m in metinler if m["sinif"] == sinif_filter]
        print(f"Filtre: sadece sınıf {sinif_filter} → {len(metinler)} metin.")

    by_sinif = {}
    for m in metinler:
        by_sinif.setdefault(m["sinif"], []).append(m["baslik"])
    for s in sorted(by_sinif):
        print(f"  Sınıf {s}: {len(by_sinif[s])} metin — {by_sinif[s]}")

    if sinif_filter is None and len(metinler) != 32:
        print(f"⚠ UYARI: 32 metin bekleniyordu, {len(metinler)} bulundu. Yine de devam ediliyor.")

    mongo_url = os.environ["MONGO_URL"]
    db_name = os.environ["DB_NAME"]
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]

    eklenen = 0
    atlanan = 0
    simdi = datetime.now(timezone.utc).isoformat()

    for m in metinler:
        var_mi = await db.analiz_metinler.find_one({
            "kaynak": SEED_TAG,
            "sinif_seviyesi": str(m["sinif"]),
            "baslik": m["baslik"],
        })
        if var_mi:
            atlanan += 1
            continue

        doc = {
            "id": str(uuid.uuid4()),
            "baslik": m["baslik"],
            "icerik": m["icerik"],
            "kelime_sayisi": m["kelime_sayisi"],
            "sinif_seviyesi": str(m["sinif"]),
            "tur": m["tur"],
            "durum": "havuzda",
            "ekleyen_id": "system",
            "ekleyen_ad": "OBA Sistem",
            "oylar": {},
            "olusturma_tarihi": simdi,
            "yayin_tarihi": simdi,
            "kaynak": SEED_TAG,
        }
        await db.analiz_metinler.insert_one(doc)
        eklenen += 1

    print(f"\nSonuç: {eklenen} eklendi, {atlanan} atlandı (zaten var).")
    client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--sinif", type=int, default=None, help="Sadece bu sınıfı yükle (1-8)")
    args = parser.parse_args()
    asyncio.run(seed(sinif_filter=args.sinif))
