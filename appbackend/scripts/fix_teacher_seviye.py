"""Tek seferlik hedefli düzeltme — 'seviye' alanı eksik olan TEK teacher kaydını onarır.

Arka plan: /api/teachers (modules/crm.py get_teachers) her kaydı `Teacher` şemasıyla
doğrular. `seviye` zorunlu (TeacherLevel enum) ve default'u yoktur; eksikse o kayıt
tüm listeyi 500 (ResponseValidationError) yapar. teshis_teachers.py bu kaydı buldu:
    id=de95b57e-63cf-43c6-a98a-2efc3b39b9d2  (Derya Akpınar)  → seviye eksik

Bu script SADECE o kaydı hedefler ve YALNIZCA seviye eksik/geçersizse "yeni" yazar.
Başka hiçbir alana/kayda dokunmaz. İdempotent — tekrar çalıştırmak güvenlidir.

VARSAYILAN MOD = DRY-RUN (hiçbir şey yazmaz). Uygulamak için: --apply

Çalıştırma (appbackend dizininden; MONGO_URL/DB_NAME ortamdan okunur):
  Önizleme:  .venv/Scripts/python.exe scripts/fix_teacher_seviye.py
  Uygula:    .venv/Scripts/python.exe scripts/fix_teacher_seviye.py --apply
Türkçe çıktı için Windows'ta: set PYTHONIOENCODING=utf-8
"""
import sys
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

APPLY = "--apply" in sys.argv  # bayrak yoksa dry-run

HEDEF_ID = "de95b57e-63cf-43c6-a98a-2efc3b39b9d2"  # Derya Akpınar
VARSAYILAN_SEVIYE = "yeni"  # TeacherLevel.YENI


async def main():
    from core.db import db
    from core.auth import TeacherLevel

    gecerli_seviyeler = {e.value for e in TeacherLevel}
    mod = "UYGULA (--apply)" if APPLY else "DRY-RUN (önizleme — hiçbir şey yazılmaz)"
    print("═══ teacher.seviye HEDEFLİ DÜZELTME ═══")
    print(f"  Mod: {mod}")
    print(f"  Hedef id: {HEDEF_ID}")
    print(f"  Geçerli seviyeler: {sorted(gecerli_seviyeler)}\n")

    t = await db.teachers.find_one({"id": HEDEF_ID})
    if not t:
        print("  ✗ Kayıt bulunamadı. (DB_NAME doğru mu? Kayıt silinmiş olabilir.)")
        print("═══ İPTAL ═══")
        return

    ad = f"{t.get('ad','')} {t.get('soyad','')}".strip() or "(isimsiz)"
    mevcut = t.get("seviye", "<yok>")
    print(f"  Kayıt: {ad}  (mevcut seviye={mevcut!r})")

    # Yalnızca seviye eksik/geçersizse dokun — zaten geçerliyse hiçbir şey yapma.
    if t.get("seviye") in gecerli_seviyeler:
        print("  ✓ seviye zaten geçerli — değişiklik gerekmiyor. (idempotent)")
        print("═══ TAMAMLANDI ═══")
        return

    print(f"  → seviye = {VARSAYILAN_SEVIYE!r} yazılacak (yalnız bu alan, yalnız bu kayıt)")
    if APPLY:
        sonuc = await db.teachers.update_one(
            {"id": HEDEF_ID}, {"$set": {"seviye": VARSAYILAN_SEVIYE}})
        print(f"  ✓ Yazıldı (matched={sonuc.matched_count}, modified={sonuc.modified_count})")
        # Doğrulama: kayıt artık Teacher şemasına uyuyor mu?
        from core.db import parse_from_mongo
        from modules.crm import Teacher
        yeni = await db.teachers.find_one({"id": HEDEF_ID})
        try:
            Teacher(**parse_from_mongo(dict(yeni)))
            print("  ✓ Doğrulama: kayıt artık Teacher şemasına UYUYOR. /api/teachers düzelmeli.")
        except Exception as ex:
            print(f"  ✗ Doğrulama BAŞARISIZ — başka bir alan da bozuk olabilir: {ex}")
    else:
        print("\n  ⚠  DRY-RUN: hiçbir şey yazılmadı. Uygulamak için: --apply")
    print("═══ TAMAMLANDI ═══")


if __name__ == "__main__":
    asyncio.run(main())
