"""Geriye dönük migration: mevcut kur>1 öğrenciler için 'üst kur' XP kaydı.

- Sınıflandırma KUR NUMARASINA göre (kur>1 → üst kur / kur atlama).
- İDEMPOTENT: öğrenci+kur başına XP'ye sayılan (kaynak!=manuel) kayıt zaten varsa
  atlar. Tekrar çalıştırmak mükerrer XP ÜRETMEZ.
- kur_atlamalari.ogretmen_id = students.ogretmen_id (teachers.id) — XP tablosu +
  rozet motoru bununla eşler. tarih = öğrencinin olusturma_tarihi (dashboard
  'kur atlayan' doğru döneme düşsün, bu ayı şişirmesin).
- Sonda etkilenen öğretmenler için rozet_degerlendir bir kez (seviye/rozet otomatik).

Çalıştırma (env MONGO_URL/DB_NAME uygulama ile aynı):
  cd appbackend && PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe scripts/migrate_ust_kur_xp.py
"""
import asyncio
import os
import re
import sys
import uuid
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _kur_no(kur):
    try:
        s = re.sub(r"\D", "", str(kur if kur is not None else ""))
        return int(s) if s else None
    except Exception:
        return None


async def main():
    from core.db import db
    from core.rozet_motor import rozet_degerlendir

    olusturulan = 0
    atlanan = 0
    etkilenen_tid = set()

    students = await db.students.find(
        {}, {"_id": 0, "id": 1, "kur": 1, "ogretmen_id": 1, "olusturma_tarihi": 1}).to_list(length=None)
    for s in students:
        kur_no = _kur_no(s.get("kur"))
        tid = s.get("ogretmen_id")
        if kur_no is None or kur_no <= 1 or not tid:
            continue  # kur<=1 (yeni kayıt) veya öğretmensiz → atla
        # İdempotent: bu öğrenci+kur için XP'ye sayılan kayıt zaten var mı?
        zaten = False
        async for k in db.kur_atlamalari.find(
                {"ogrenci_id": s["id"], "kaynak": {"$ne": "manuel"}},
                {"_id": 0, "yeni_kur": 1, "yeni_kur_no": 1}):
            n = k.get("yeni_kur_no")
            if n is None:
                n = _kur_no(k.get("yeni_kur"))
            if n == kur_no:
                zaten = True
                break
        if zaten:
            atlanan += 1
            continue
        await db.kur_atlamalari.insert_one({
            "id": str(uuid.uuid4()),
            "ogrenci_id": s["id"],
            "ogretmen_id": tid,
            "eski_kur": "",
            "yeni_kur": str(s.get("kur")),
            "yeni_kur_no": kur_no,
            "kaynak": "migrasyon",  # != "manuel" → XP'ye sayılır
            "tarih": s.get("olusturma_tarihi") or datetime.now(timezone.utc).isoformat(),
        })
        olusturulan += 1
        etkilenen_tid.add(tid)

    rozet_verilen = 0
    for tid in etkilenen_tid:
        u = await db.users.find_one({"linked_id": tid}, {"_id": 0, "id": 1})
        if u and u.get("id"):
            try:
                yeni = await rozet_degerlendir(u["id"], "kur_atlama")
                rozet_verilen += len(yeni or [])
            except Exception as ex:
                print(f"  rozet uyarı ({tid}): {ex}")

    print(f"Migration tamam: {olusturulan} üst-kur XP kaydı oluşturuldu, {atlanan} zaten vardı (atlandı).")
    print(f"Etkilenen öğretmen: {len(etkilenen_tid)}, yeni verilen rozet: {rozet_verilen}.")


if __name__ == "__main__":
    asyncio.run(main())
