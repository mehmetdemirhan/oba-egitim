"""FAZ 2 rozet motoru smoke testi.

Doğrulananlar:
  - kullanici_metrikleri metrikleri doğru hesaplıyor (öğrenci + öğretmen)
  - rozet_degerlendir fallback (db.rozetler boş) yolunda kod tanımlarını kullanıyor
  - Bileşik (AND) koşullar (gorev_20) doğru değerlendiriliyor
  - Veri-odaklı yol: db.rozetler dolu ise koşullar oradan okunuyor (operator+esik)
  - Bildirim tetikleniyor, motor idempotent
  - Operatör mantığı (_op_uygula)

    cd appbackend
    .venv/Scripts/python.exe tests/test_rozet_motor_smoke.py
"""
import asyncio
import os
import sys
import uuid
from datetime import datetime, timedelta

TEST_DB = "oba_test_rozet_motor_smoke"
os.environ["MONGO_URL"] = os.environ.get("MONGO_URL_TEST", "mongodb://localhost:27017")
os.environ["DB_NAME"] = TEST_DB
os.environ.setdefault("SECRET_KEY", "test-secret-key")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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
    import server  # noqa
    from core.db import db, ensure_indexes
    from core.rozet_motor import (
        rozet_degerlendir, rozet_tetikle, kullanici_metrikleri, metrik_hesapla, _op_uygula,
    )

    await server.client.drop_database(TEST_DB)
    await ensure_indexes()
    now = datetime.utcnow()

    # ── Operatör birim testleri ──
    check(_op_uygula(5, ">=", 5) and _op_uygula(6, ">=", 5), ">= operatörü doğru")
    check(not _op_uygula(4, ">=", 5), ">= sınır altı reddediliyor")
    check(_op_uygula(3, "<", 5) and not _op_uygula(5, "<", 5), "< operatörü doğru")
    check(not _op_uygula(5, None, None), "manuel/None koşul otomatik verilmiyor")

    # ── ÖĞRENCİ senaryosu (fallback: db.rozetler boş) ──
    su, s1 = str(uuid.uuid4()), str(uuid.uuid4())
    await db.users.insert_one({"id": su, "role": "student", "linked_id": s1, "ad": "Ali"})
    await db.students.insert_one({"id": s1, "ad": "Ali", "toplam_xp": 250})
    # 3 gün ardışık okuma, 120 dk toplam, 2 farklı kitap
    for i, (dk, kitap) in enumerate([(50, "A"), (40, "A"), (30, "B")]):
        await db.reading_logs.insert_one({
            "id": str(uuid.uuid4()), "ogrenci_id": s1,
            "tarih": (now - timedelta(days=i)).isoformat(), "sure_dakika": dk, "kitap_adi": kitap})

    m = await kullanici_metrikleri(su, "student")
    check(m["okuma_dakikasi"] == 120, f"okuma_dakikasi=120 (gelen {m['okuma_dakikasi']})")
    check(m["kitap_sayisi"] == 2, f"kitap_sayisi=2 (gelen {m['kitap_sayisi']})")
    check(m["giris_serisi"] == 3, f"giris_serisi=3 (gelen {m['giris_serisi']})")
    check(m["okuma_kayit_sayisi"] == 3, f"okuma_kayit_sayisi=3 (gelen {m['okuma_kayit_sayisi']})")
    check(m["lig_xp"] == 250, f"lig_xp=250 (gelen {m['lig_xp']})")
    check(await metrik_hesapla(su, "student", "okuma_dakikasi") == 120, "metrik_hesapla tek metrik doğru")

    yeni = await rozet_degerlendir(su, "test")
    kodlar = {y["rozet_kodu"] for y in yeni}
    # 120 dk → okuma_ilk, okuma_100, orman_ilk, orman_50; 2 kitap → kitap_1; streak 3 → streak_3; lig_xp 250 → lig_gumus
    for beklenen in ["okuma_ilk", "okuma_100", "kitap_1", "streak_3", "orman_50", "lig_gumus"]:
        check(beklenen in kodlar, f"öğrenci '{beklenen}' rozetini kazandı")
    check("okuma_500" not in kodlar, "okuma_500 (500 dk) KAZANILMADI (eşik altı)")
    check("streak_7" not in kodlar, "streak_7 KAZANILMADI (eşik altı)")

    bildirim_say = await db.bildirimler.count_documents({"alici_id": su, "tur": "rozet_kazandi"})
    check(bildirim_say == len(yeni), f"her rozet için bildirim ({bildirim_say}/{len(yeni)})")

    # Idempotent
    yeni2 = await rozet_degerlendir(su, "test")
    check(len(yeni2) == 0, "ikinci değerlendirme 0 yeni rozet (idempotent)")

    # ── ÖĞRETMEN bileşik koşul (gorev_20 = 20 atanan AND 10 tamamlanan) ──
    tu, tl = str(uuid.uuid4()), str(uuid.uuid4())
    await db.users.insert_one({"id": tu, "role": "teacher", "linked_id": tl, "ad": "Ayşe"})
    # 20 görev ata, ama sadece 5 tamamlanan → gorev_20 sağlanmamalı, gorev_ilk sağlanmalı
    for i in range(20):
        await db.gorevler.insert_one({
            "id": str(uuid.uuid4()), "atayan_id": tu, "hedef_id": str(uuid.uuid4()),
            "durum": "tamamlandi" if i < 5 else "beklemede", "baslik": f"G{i}"})
    m2 = await kullanici_metrikleri(tu, "teacher")
    check(m2["gorev_atama_sayisi"] == 20 and m2["gorev_tamamlanan"] == 5,
          f"öğretmen görev metrikleri (atama={m2['gorev_atama_sayisi']}, tamam={m2['gorev_tamamlanan']})")
    yeni_t = await rozet_degerlendir(tu, "test")
    kodlar_t = {y["rozet_kodu"] for y in yeni_t}
    check("gorev_ilk" in kodlar_t, "öğretmen gorev_ilk kazandı")
    check("gorev_20" not in kodlar_t, "gorev_20 KAZANILMADI (bileşik: 5<10 tamamlanan)")
    # 10 tamamlanana çıkar → gorev_20 sağlanmalı
    await db.gorevler.update_many({"atayan_id": tu, "durum": "beklemede"}, {"$set": {"durum": "tamamlandi"}}, )
    yeni_t2 = await rozet_degerlendir(tu, "test")
    check("gorev_20" in {y["rozet_kodu"] for y in yeni_t2}, "gorev_20 KAZANILDI (20 atama + ≥10 tamamlanan)")

    # ── VERİ-ODAKLI yol: db.rozetler dolu → koşullar oradan okunur ──
    sd, sd_l = str(uuid.uuid4()), str(uuid.uuid4())
    await db.users.insert_one({"id": sd, "role": "student", "linked_id": sd_l, "ad": "Veri"})
    await db.students.insert_one({"id": sd_l, "toplam_xp": 0})
    await db.reading_logs.insert_one({"id": str(uuid.uuid4()), "ogrenci_id": sd_l,
                                      "tarih": now.isoformat(), "sure_dakika": 120, "kitap_adi": "X"})
    # KOD tanımlarında OLMAYAN özel rozetler ekle → motor db'den okuduğunu kanıtlar
    await db.rozetler.insert_one({"rol": "student", "kod": "ozel_dusuk", "ad": "Özel Düşük",
        "ikon": "🎯", "kategori": "test", "seviye": "bronz", "odul_puan": 3, "aktif": True,
        "kosul": {"metrik": "okuma_dakikasi", "operator": ">=", "esik": 50}})
    await db.rozetler.insert_one({"rol": "student", "kod": "ozel_yuksek", "ad": "Özel Yüksek",
        "ikon": "🏆", "kategori": "test", "seviye": "elmas", "odul_puan": 9, "aktif": True,
        "kosul": {"metrik": "okuma_dakikasi", "operator": ">=", "esik": 9999}})
    yeni_d = await rozet_degerlendir(sd, "test")
    kodlar_d = {y["rozet_kodu"] for y in yeni_d}
    check(kodlar_d == {"ozel_dusuk"}, f"veri-odaklı: yalnız 'ozel_dusuk' kazanıldı (gelen {kodlar_d})")
    check("okuma_ilk" not in kodlar_d, "db dolu iken kod-fallback DEVREDIŞI (yalnız db tanımları)")

    # ── Fire-and-forget wrapper ──
    se, se_l = str(uuid.uuid4()), str(uuid.uuid4())
    await db.users.insert_one({"id": se, "role": "student", "linked_id": se_l})
    await db.students.insert_one({"id": se_l, "toplam_xp": 0})
    await db.reading_logs.insert_one({"id": str(uuid.uuid4()), "ogrenci_id": se_l,
                                      "tarih": now.isoformat(), "sure_dakika": 60, "kitap_adi": "Y"})
    await rozet_tetikle(se, "kitap_bitti")  # exception fırlatmamalı
    kazanildi = await db.kazanilan_rozetler.count_documents({"kullanici_id": se})
    check(kazanildi >= 1, f"rozet_tetikle rozet verdi ({kazanildi} rozet)")

    await server.client.drop_database(TEST_DB)
    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    return _kalan == 0


if __name__ == "__main__":
    ok = asyncio.run(run())
    sys.exit(0 if ok else 1)
