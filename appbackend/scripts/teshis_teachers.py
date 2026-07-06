"""Teşhis — /api/teachers 500 hatasının GERÇEK sebebini bulur.

get_teachers endpoint'i (modules/crm.py) her teachers kaydını
`Teacher(**parse_from_mongo(teacher))` ile doğrular. TEK bir kayıt bile
`Teacher` şemasına uymazsa FastAPI tüm isteği 500 (ResponseValidationError)
yapar ve Öğretmenler sayfası KOMPLE boş görünür.

Bu script, endpoint'in yaptığı doğrulamanın BİREBİR aynısını her kayıt için
tek tek çalıştırır ve hangi kaydın hangi alanda patladığını yazar. Böylece
Render loglarını kurcalamadan gerçek sebep netleşir.

SALT-OKUNUR: hiçbir şey yazmaz/değiştirmez (sadece find eder).

Çalıştırma (appbackend dizininden; MONGO_URL/DB_NAME ortamdan okunur):
  Lokal:  .venv/Scripts/python.exe scripts/teshis_teachers.py
  Render: python scripts/teshis_teachers.py
Türkçe çıktı için Windows'ta: set PYTHONIOENCODING=utf-8
"""
import sys
import asyncio
from pathlib import Path

# appbackend kökünü path'e ekle (core.* / modules.* importları için)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


async def main():
    from core.db import db, parse_from_mongo
    # Endpoint'in kullandığı GERÇEK model — aynı import, aynı doğrulama.
    from modules.crm import Teacher

    print("═══ /api/teachers TEŞHİS (salt-okunur) ═══\n")

    teachers = await db.teachers.find().to_list(length=None)
    print(f"  teachers koleksiyonundaki kayıt sayısı: {len(teachers)}\n")

    gecerli = 0
    hatali = []  # (id, ad, hata_metni, eksik/yanlis alanlar)

    for t in teachers:
        try:
            # get_teachers ile BİREBİR aynı dönüşüm:
            Teacher(**parse_from_mongo(dict(t)))
            gecerli += 1
        except Exception as ex:
            kimlik = f"id={t.get('id')}  ad={t.get('ad','')} {t.get('soyad','')}".strip()
            # Pydantic ValidationError ise alan bazlı ayrıntıyı çıkar
            ayrinti = []
            errs = getattr(ex, "errors", None)
            if callable(errs):
                try:
                    for e in ex.errors():
                        loc = ".".join(str(x) for x in e.get("loc", ()))
                        ayrinti.append(f"{loc}: {e.get('msg')} (gelen={t.get(loc, '<yok>')!r})")
                except Exception:
                    ayrinti.append(f"{type(ex).__name__}: {ex}")
            else:
                ayrinti.append(f"{type(ex).__name__}: {ex}")
            hatali.append((kimlik, ayrinti))

    print(f"  ✓ Geçerli (Teacher'a çevrilen) kayıt : {gecerli}")
    print(f"  ✗ HATALI (endpoint'i 500 yapan) kayıt : {len(hatali)}\n")

    if hatali:
        print("─── HATALI KAYITLAR (her biri tek başına /api/teachers'ı 500 yapar) ───")
        for kimlik, ayrinti in hatali:
            print(f"\n  ● {kimlik}")
            for a in ayrinti:
                print(f"      - {a}")
        print("\n  → Düzeltme: yukarıdaki alanları geçerli değere getirin, VEYA")
        print("    Teacher modelini bu alanlara toleranslı yapın (ör. Optional + default).")
    else:
        print("  Tüm kayıtlar geçerli. 500'ün sebebi /api/teachers ŞEMA doğrulaması DEĞİL.")
        print("  Sonraki adım: Render loglarındaki traceback'in son satırına bakın")
        print("  (ör. count_documents, farklı endpoint, veya auth katmanı).")

    # Ek sinyal: reconcile'ın eklediği alanlar var mı? (yalnız bilgi amaçlı)
    user_idli = sum(1 for t in teachers if t.get("user_id"))
    print(f"\n  (bilgi) user_id taşıyan teachers kaydı: {user_idli}/{len(teachers)}")
    print("═══ TEŞHİS TAMAMLANDI ═══")


if __name__ == "__main__":
    asyncio.run(main())
