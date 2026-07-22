"""Egzersiz Kalite Kontrol — öğretmen değerlendirmesi + otomatik askıya alma + XP smoke.

Senaryo: 2 öğretmen bir egzersize "uygun değil" der → egzersiz otomatik askıya alınır →
öğrenci seçiminden düşer → admin "bekleyenler" kuyruğunda görünür → admin tekrar aktif eder.
Ayrıca: sınıf uygunluğu agregasyonu, XP ödülü, çift değerlendirme engeli.

İzole test DB. cd appbackend && .venv/Scripts/python.exe tests/test_egzersiz_kalite_smoke.py
"""
import asyncio
import os
import sys
import uuid

TEST_DB = "oba_test_egz_kalite"
os.environ["MONGO_URL"] = os.environ.get("MONGO_URL_TEST", "mongodb://localhost:27017")
os.environ["DB_NAME"] = TEST_DB
os.environ.setdefault("SECRET_KEY", "test-secret-key")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_gecen = 0
_kalan = 0


def check(kosul, mesaj):
    global _gecen, _kalan
    if kosul:
        _gecen += 1; print(f"  [GECTI] {mesaj}")
    else:
        _kalan += 1; print(f"  [KALDI] {mesaj}")


async def run():
    import server
    from core.auth import create_access_token
    from core.db import db
    from modules.egzersiz_motoru import _aktif_sorgu
    from httpx import AsyncClient, ASGITransport

    await server.client.drop_database(TEST_DB)

    admin = str(uuid.uuid4()); t1 = str(uuid.uuid4()); t2 = str(uuid.uuid4())
    await db.users.insert_one({"id": admin, "role": "admin", "ad": "Yön", "soyad": "E", "puan": 0})
    await db.users.insert_one({"id": t1, "role": "teacher", "ad": "Öğr", "soyad": "Bir", "puan": 0})
    await db.users.insert_one({"id": t2, "role": "teacher", "ad": "Öğr", "soyad": "İki", "puan": 0})

    # 3 aktif egzersiz (farklı tip → dönüşümlü seçim testi)
    egz = []
    for i, tip in enumerate(["deyim_bosluk", "atasozu_bosluk", "kelime_anlam_eslestirme"]):
        eid = str(uuid.uuid4())
        await db.egzersiz_icerikler.insert_one({
            "id": eid, "tip": tip, "sinif": 3, "durum": "aktif", "mock": False,
            "konu": "test", "zorluk": "orta", "icerik": {"sorular": [{"soru": "x"}]},
            "kullanim_sayisi": 0, "kalite_toplam_degerlendirme": 0})
        egz.append(eid)
    A, B, C = egz

    Ha = {"Authorization": f"Bearer {create_access_token({'sub': admin})}"}
    H1 = {"Authorization": f"Bearer {create_access_token({'sub': t1})}"}
    H2 = {"Authorization": f"Bearer {create_access_token({'sub': t2})}"}

    async with AsyncClient(transport=ASGITransport(app=server.app), base_url="http://test") as ac:
        # 1) Öğretmen kuyruğu — 3 egzersiz, tip dönüşümlü
        r = await ac.get("/api/egzersiz-kalite/kuyruk?limit=3", headers=H1)
        check(r.status_code == 200 and len(r.json()["egzersizler"]) == 3, "öğretmen kuyruğu 3 egzersiz döndü")
        tipler = [e["tip"] for e in r.json()["egzersizler"]]
        check(len(set(tipler)) == 3, f"tip dönüşümlü seçim (farklı tipler: {tipler})")

        # 2) T1 → A "uygun değil"
        r = await ac.post("/api/egzersiz-kalite/degerlendir", headers=H1,
                          json={"egzersiz_id": A, "uygun": False, "degisiklik_talebi": "Sorular belirsiz."})
        check(r.status_code == 200, f"T1 değerlendirme kaydedildi ({r.status_code})")
        check(r.json().get("askiya_alindi") is False, "1 olumsuz oy → henüz askıya alınmadı")
        check(r.json().get("kazanilan_xp") == 3, f"XP: değerlendirme(1)+değişiklik(2)=3 ({r.json().get('kazanilan_xp')})")

        # 3) T1 aynı egzersizi tekrar → 409
        r = await ac.post("/api/egzersiz-kalite/degerlendir", headers=H1, json={"egzersiz_id": A, "uygun": True, "uygun_sinif_seviyeleri": [3]})
        check(r.status_code == 409, f"aynı öğretmen aynı egzersizi tekrar değerlendiremez ({r.status_code})")

        # 4) T1 kuyruğunda A artık YOK (değerlendirdi)
        r = await ac.get("/api/egzersiz-kalite/kuyruk?limit=5", headers=H1)
        check(A not in [e["egzersiz_id"] for e in r.json()["egzersizler"]], "değerlendirilen egzersiz T1 kuyruğunda görünmez")

        # 5) T2 → A "uygun değil" → EŞİK 2 → otomatik askıya
        r = await ac.post("/api/egzersiz-kalite/degerlendir", headers=H2,
                          json={"egzersiz_id": A, "uygun": False})
        check(r.status_code == 200 and r.json().get("askiya_alindi") is True, "2. olumsuz oy → OTOMATİK ASKIYA ALINDI")
        check(r.json().get("durum") == "askida", "durum=askida")

        # 6) Askıdaki egzersiz öğrenci seçiminden düşer (_aktif_sorgu ile eşleşmez)
        n = await db.egzersiz_icerikler.count_documents(_aktif_sorgu("deyim_bosluk", 3))
        check(n == 0, f"askıdaki egzersiz öğrenci seçim sorgusuna girmez ({n})")

        # 7) Admin bekleyenler kuyruğu — A + değişiklik talebi metni görünür
        r = await ac.get("/api/egzersiz-kalite/bekleyenler", headers=Ha)
        bek = r.json()["egzersizler"]
        check(len(bek) == 1 and bek[0]["egzersiz_id"] == A, "admin 'bekleyenler' kuyruğunda A var")
        talep_metinleri = [d.get("degisiklik_talebi") for d in bek[0]["degerlendirmeler"]]
        check("Sorular belirsiz." in talep_metinleri, "değişiklik talebi metni admin kuyruğunda görünür")
        check(bek[0]["uygun_degil_sayisi"] == 2, "uygun değil sayısı = 2")

        # 8) Öğretmen bekleyenlere erişemez (403)
        r = await ac.get("/api/egzersiz-kalite/bekleyenler", headers=H1)
        check(r.status_code == 403, f"öğretmen admin kuyruğuna erişemez ({r.status_code})")

        # 9) Admin → tekrar aktif et
        r = await ac.post(f"/api/egzersiz-kalite/{A}/aktif-et", headers=Ha)
        check(r.status_code == 200, "admin egzersizi tekrar aktifleştirdi")
        n = await db.egzersiz_icerikler.count_documents(_aktif_sorgu("deyim_bosluk", 3))
        check(n == 1, "tekrar aktif → öğrenci seçimine geri döndü")

        # 10) Sınıf uygunluğu: T1 → B "uygun" for [2,4] → kalite_uygun_siniflar
        r = await ac.post("/api/egzersiz-kalite/degerlendir", headers=H1,
                          json={"egzersiz_id": B, "uygun": True, "uygun_sinif_seviyeleri": [2, 4]})
        check(r.status_code == 200, "B 'uygun' [2,4] kaydedildi")
        Bdoc = await db.egzersiz_icerikler.find_one({"id": B})
        check(set(Bdoc.get("kalite_uygun_siniflar", [])) == {2, 4}, f"kalite_uygun_siniflar={Bdoc.get('kalite_uygun_siniflar')}")
        # B'nin kendi sınıfı 3; sınıf 2 sorgusunda kalite ile görünür
        n2 = await db.egzersiz_icerikler.count_documents(_aktif_sorgu("atasozu_bosluk", 2))
        check(n2 == 1, "sınıf-uygunluk: B, 2. sınıf seçim sorgusunda görünür (kendi sınıfı 3)")

        # 11) "Uygun" ama sınıf seçilmemiş → 400
        r = await ac.post("/api/egzersiz-kalite/degerlendir", headers=H2, json={"egzersiz_id": B, "uygun": True, "uygun_sinif_seviyeleri": []})
        check(r.status_code == 400, f"'uygun' için sınıf zorunlu ({r.status_code})")

        # 12) XP kalıcı yazıldı
        u1 = await db.users.find_one({"id": t1})
        check(u1.get("puan", 0) >= 3, f"T1 puanı işlendi ({u1.get('puan')})")

        # 13) Ayar güncelleme (eşik) admin
        r = await ac.put("/api/egzersiz-kalite/ayarlar", headers=Ha, json={"askiya_alma_esigi": 3})
        check(r.status_code == 200 and r.json()["degerler"]["askiya_alma_esigi"] == 3, "askıya alma eşiği güncellendi")

    await server.client.drop_database(TEST_DB)


def main():
    asyncio.run(run())
    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    sys.exit(0 if _kalan == 0 else 1)


if __name__ == "__main__":
    main()
