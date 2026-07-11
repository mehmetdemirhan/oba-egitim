"""Geriye dönük migration (standalone runner): kur>1 öğrenciler için üst-kur XP.

Mantık modules/admin_migrations.py'deki `_migrate_ust_kur_xp`'te (tek kaynak) —
aynısı admin endpoint'i POST /admin/migrations/ust-kur-xp tarafından da çağrılır.
İdempotent; tekrar çalıştırmak mükerrer XP üretmez.

Çalıştırma (env MONGO_URL/DB_NAME uygulama ile aynı):
  cd appbackend && PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe scripts/migrate_ust_kur_xp.py
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def main():
    from modules.admin_migrations import _migrate_ust_kur_xp
    sonuc = await _migrate_ust_kur_xp(dry_run=False)
    print(f"Migration tamam: {sonuc['olusturulan']} üst-kur XP kaydı oluşturuldu, "
          f"{sonuc['zaten_var']} zaten vardı (atlandı).")
    print(f"Etkilenen öğretmen: {sonuc['etkilenen_ogretmen_sayisi']}, "
          f"yeni verilen rozet: {sonuc['rozet_verilen']}.")
    for o in sonuc.get("ornekler", [])[:5]:
        print(f"  - {o['ogrenci']} kur={o['kur']} (no={o['kur_no']})")


if __name__ == "__main__":
    asyncio.run(main())
