"""Datetime timezone kök düzeltmesi — naive/aware karışımı regresyon testi.

Hata: "can't compare offset-naive and offset-aware datetimes". Kök neden: Mongo'da
tarihler karışık saklanmış (utcnow → naive ISO, now(utc) → aware ISO); parse_from_mongo
string→datetime çevirirken tz-durumunu koruyup naive/aware KARIŞIMI üretiyordu.

Doğrular:
  - core.zaman.simdi() daima aware; aware() normalize guard'ı naive/aware/str/None kapsar.
  - parse_from_mongo naive VE aware ISO string'i DAİMA aware UTC'ye çevirir.
  - Karışık kayıtların (naive + aware) tarih alanları KARŞILAŞTIRILINCA hata FIRLAMAZ.
  - Mongo round-trip: iki karışık kayıt okunup karşılaştırıldığında sıralama doğru + hatasız.

    cd appbackend
    PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe tests/test_datetime_tz_smoke.py
"""
import asyncio
import os
import sys
from datetime import datetime, timezone

TEST_DB = "oba_test_datetime_tz"
os.environ["MONGO_URL"] = os.environ.get("MONGO_URL_TEST", "mongodb://localhost:27017")
os.environ["DB_NAME"] = TEST_DB
os.environ.setdefault("SECRET_KEY", "test-secret-key")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_gecen = _kalan = 0


def check(kosul, mesaj):
    global _gecen, _kalan
    if kosul:
        _gecen += 1; print(f"  [GECTI] {mesaj}")
    else:
        _kalan += 1; print(f"  [KALDI] {mesaj}")


async def run():
    from core.zaman import simdi, aware, iso, gun_farki
    from core.db import db, parse_from_mongo, prepare_for_mongo, client

    await client.drop_database(TEST_DB)

    # ── 1) zaman helper'ları ──
    check(simdi().tzinfo is not None, "simdi() timezone-aware")
    check(aware("2026-07-17T10:00:00") .tzinfo is not None, "aware(naive-str) → aware")
    check(aware("2026-07-17T10:00:00+03:00").utcoffset().total_seconds() == 0, "aware(offsetli-str) → UTC")
    check(aware(datetime(2026, 7, 17)).tzinfo is not None, "aware(naive-datetime) → aware")
    check(aware(None) is None and aware("") is None, "aware(None/boş) → None")
    check("+00:00" in iso(), "iso() aware UTC string üretir")

    # ── 2) Kritik: naive vs aware KARŞILAŞTIRMA hata fırlatmaz ──
    naive = datetime(2026, 7, 10, 12, 0, 0)          # utcnow() gibi (tz-siz)
    awr = datetime(2026, 7, 15, 12, 0, 0, tzinfo=timezone.utc)  # now(utc) gibi
    hata = False
    try:
        _ = aware(naive) < aware(awr)   # normalize sonrası güvenli
    except TypeError:
        hata = True
    check(not hata, "aware() ile normalize → naive vs aware karşılaştırma HATASIZ")
    check(aware(naive) < aware(awr), "normalize sonrası doğru sıralama (naive<aware)")
    check(abs(gun_farki(naive, awr) - 5) < 0.01, f"gun_farki karışık tarihlerde doğru (5) ({gun_farki(naive, awr)})")

    # ── 3) parse_from_mongo naive & aware ISO'yu AWARE'e normalize eder ──
    naive_kayit = parse_from_mongo({"tarih": "2026-07-10T12:00:00"})           # naive ISO (utcnow deseni)
    aware_kayit = parse_from_mongo({"tarih": "2026-07-15T12:00:00+00:00"})     # aware ISO (now(utc) deseni)
    check(naive_kayit["tarih"].tzinfo is not None, "parse_from_mongo(naive ISO) → aware")
    check(aware_kayit["tarih"].tzinfo is not None, "parse_from_mongo(aware ISO) → aware")
    # Bu iki alanı KARŞILAŞTIRMAK eskiden hata fırlatırdı:
    hata2 = False
    try:
        _ = naive_kayit["tarih"] < aware_kayit["tarih"]
    except TypeError:
        hata2 = True
    check(not hata2, "parse_from_mongo çıktısı karışık kayıtlarda karşılaştırma HATASIZ")
    check(naive_kayit["tarih"] < aware_kayit["tarih"], "karışık kayıtlar doğru sıralanıyor")

    # ── 4) Mongo round-trip: karışık saklanmış iki kayıt ──
    # Biri naive string (eski utcnow deseni), biri aware string (yeni now(utc) deseni)
    await db.demo_kayitlar.insert_one({"id": "a", "olusturma_tarihi": "2026-07-01T09:00:00"})
    await db.demo_kayitlar.insert_one({"id": "b", "olusturma_tarihi": "2026-07-20T09:00:00+00:00"})
    kayitlar = [parse_from_mongo(k) for k in await db.demo_kayitlar.find({}, {"_id": 0}).to_list(length=10)]
    hata3 = False
    try:
        siralı = sorted(kayitlar, key=lambda k: k["olusturma_tarihi"])  # karışık tz sıralama
    except TypeError:
        hata3 = True
    check(not hata3, "Mongo'dan okunan karışık-tz kayıtlar HATASIZ sıralanır")
    check(not hata3 and siralı[0]["id"] == "a" and siralı[1]["id"] == "b", "sıralama doğru (a<b)")
    check(all(k["olusturma_tarihi"].tzinfo is not None for k in kayitlar), "tüm okunan tarihler aware")

    # ── 5) prepare_for_mongo aware datetime → string (round-trip tutarlı) ──
    hazir = prepare_for_mongo({"tarih": simdi()})
    check(isinstance(hazir["tarih"], str), "prepare_for_mongo(aware dt) → ISO string")
    check(parse_from_mongo(hazir)["tarih"].tzinfo is not None, "round-trip sonrası yine aware")

    await client.drop_database(TEST_DB)


if __name__ == "__main__":
    asyncio.run(run())
    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    sys.exit(1 if _kalan else 0)
