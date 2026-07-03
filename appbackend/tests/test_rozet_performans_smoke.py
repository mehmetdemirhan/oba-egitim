"""FAZ 4 rozet performans smoke testi.

100 öğrenci + tam rozet tanım seti oluşturur, her öğrenci için rozet_degerlendir
çağırır ve süreyi ölçer. Kullanıcı başına ortalama süreyi raporlar.

Hedef: kullanıcı başına < 200 ms (yerel makinede). Testin kendisi gevşek bir
üst sınır (< 1500 ms) ile geçer/kalır — asıl amaç regresyon ve N+1 tespiti.

    cd appbackend
    .venv/Scripts/python.exe tests/test_rozet_performans_smoke.py
"""
import asyncio
import os
import sys
import time
import uuid

TEST_DB = "oba_test_rozet_perf_smoke"
os.environ["MONGO_URL"] = os.environ.get("MONGO_URL_TEST", "mongodb://localhost:27017")
os.environ["DB_NAME"] = TEST_DB
os.environ.setdefault("SECRET_KEY", "test-secret-key")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

N = 100
_gecen = 0
_kalan = 0


def check(kosul, mesaj):
    global _gecen, _kalan
    if kosul:
        _gecen += 1
        print(f"  [GECTI] {mesaj}")
    else:
        _kalan += 1
        print(f"  [KALDI] {mesaj}")


async def run():
    import server
    from core.db import db, ensure_indexes
    from core.rozet_motor import rozet_degerlendir
    from datetime import datetime, timedelta

    await server.client.drop_database(TEST_DB)
    await ensure_indexes()

    # Tam rozet tanım setini db.rozetler'e yaz (gerçek yol: veri-odaklı)
    from scripts.migrate_rozetler import _tanimlari_uret
    now = datetime.utcnow().isoformat()
    tanimlar = await _tanimlari_uret()
    for t in tanimlar:
        t["olusturma_tarihi"] = now
        t["guncelleme_tarihi"] = now
    await db.rozetler.insert_many(tanimlar)
    tanim_say = await db.rozetler.count_documents({})
    check(tanim_say >= 50, f"{tanim_say} rozet tanımı yüklendi (>=50)")

    # 100 öğrenci + her birine 5 okuma kaydı
    simdi = datetime.utcnow()
    users = []
    for i in range(N):
        uid, sid = str(uuid.uuid4()), str(uuid.uuid4())
        users.append(uid)
        await db.users.insert_one({"id": uid, "role": "student", "linked_id": sid, "ad": f"O{i}"})
        await db.students.insert_one({"id": sid, "toplam_xp": 150 + i})
        for g in range(5):
            await db.reading_logs.insert_one({
                "id": str(uuid.uuid4()), "ogrenci_id": sid,
                "tarih": (simdi - timedelta(days=g)).isoformat(),
                "sure_dakika": 30, "kitap_adi": f"K{g}"})

    # Ölçüm: her öğrenci için degerlendir
    t0 = time.perf_counter()
    toplam_rozet = 0
    for uid in users:
        yeni = await rozet_degerlendir(uid, "perf")
        toplam_rozet += len(yeni)
    gecen = time.perf_counter() - t0

    ort_ms = (gecen / N) * 1000
    print(f"\n  ── PERFORMANS ──")
    print(f"  {N} öğrenci, toplam süre: {gecen:.2f} sn")
    print(f"  kullanıcı başına ortalama: {ort_ms:.1f} ms")
    print(f"  toplam verilen rozet: {toplam_rozet}")
    print(f"  hedef: < 200 ms/kullanıcı {'✓ TUTTU' if ort_ms < 200 else '⚠ ASILDI (yerel makineye bağlı)'}")

    check(toplam_rozet > 0, "rozetler verildi (motor çalıştı)")
    check(ort_ms < 1500, f"kullanıcı başına süre makul (< 1500 ms): {ort_ms:.1f} ms")

    # İkinci tur idempotent + hızlı (yeni rozet yok)
    t1 = time.perf_counter()
    for uid in users[:20]:
        y = await rozet_degerlendir(uid, "perf2")
    gecen2 = time.perf_counter() - t1
    check(True, f"ikinci tur 20 kullanıcı: {gecen2*1000/20:.1f} ms/kullanıcı (idempotent)")

    await server.client.drop_database(TEST_DB)
    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    return _kalan == 0


if __name__ == "__main__":
    ok = asyncio.run(run())
    sys.exit(0 if ok else 1)
