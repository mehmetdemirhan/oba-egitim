"""Tekrarlanan bildirimleri temizler (aynı alıcı + tür + içerik → en yenisini tut).

Eski kod/seed'in ürettiği spam duplicate'leri (ör. 211x "Mehmet Kaya son 7 gün...")
siler. Idempotent; tekrar çalıştırmak güvenlidir. Yeni cooldown mantığı gelecekte
duplicate üretmez; bu script sadece MEVCUT birikmiş veriyi temizler.

    cd appbackend && .venv/Scripts/python.exe scripts/temizle_duplicate_bildirim.py
"""
import asyncio
import sys
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


async def main():
    from core.db import db
    once = await db.bildirimler.count_documents({})
    gruplar = defaultdict(list)
    async for b in db.bildirimler.find({}, {"alici_id": 1, "tur": 1, "icerik": 1, "tarih": 1}):
        gruplar[(b.get("alici_id"), b.get("tur"), b.get("icerik"))].append(b)

    silinecek = []
    for _key, items in gruplar.items():
        if len(items) > 1:
            items.sort(key=lambda x: x.get("tarih", ""), reverse=True)  # en yeni başta
            silinecek.extend(x["_id"] for x in items[1:])              # en yeniyi tut, gerisini sil

    print(f"Toplam bildirim (önce): {once}")
    print(f"Silinecek duplicate: {len(silinecek)}")
    if silinecek:
        # $in çok büyükse parçalara böl
        silindi = 0
        for i in range(0, len(silinecek), 1000):
            r = await db.bildirimler.delete_many({"_id": {"$in": silinecek[i:i + 1000]}})
            silindi += r.deleted_count
        print(f"Silinen: {silindi}")
    print(f"Toplam bildirim (sonra): {await db.bildirimler.count_documents({})}")


if __name__ == "__main__":
    asyncio.run(main())
