"""CRM (/teachers, /students, /courses, /payments, /export) smoke testi.

Öğretmen-öğrenci ilişkisi ve otomatik muhasebe yan-etkilerini doğrular.
İzole test DB'sine karşı çalışır (oba_test_crm_smoke). Gerçek DB'ye dokunmaz.
    cd appbackend
    .venv/Scripts/python.exe tests/test_crm_smoke.py
"""
import asyncio
import os
import sys

TEST_DB = "oba_test_crm_smoke"
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
    import server
    from httpx import AsyncClient, ASGITransport

    await server.client.drop_database(TEST_DB)
    # CRM endpoint'lerinin çoğu auth'suz; öğrenci oluşturma için token gerekmez.
    transport = ASGITransport(app=server.app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1) Öğretmen oluştur
        r = await ac.post("/api/teachers", json={
            "ad": "Ayşe", "soyad": "Yıldız", "brans": "Türkçe",
            "telefon": "5551112233", "seviye": "uzman",
            "yapilmasi_gereken_odeme": 0,
        })
        check(r.status_code == 200, f"öğretmen oluştu (status={r.status_code})")
        teacher_id = r.json()["id"]

        # 2) Öğrenci oluştur → öğretmene ata, ödeme alanlarıyla
        r = await ac.post("/api/students", json={
            "ad": "Can", "soyad": "Demir", "sinif": "4",
            "veli_ad": "Veli", "veli_soyad": "Demir", "veli_telefon": "5559998877",
            "aldigi_egitim": "Hızlı Okuma", "kur": "1",
            "yapilmasi_gereken_odeme": 1000,
            "ogretmene_yapilacak_odeme": 300,
            "ogretmen_id": teacher_id,
        })
        check(r.status_code == 200, f"öğrenci oluştu (status={r.status_code})")
        student_id = r.json()["id"]

        # 3) Otomatik muhasebe: 2 ödeme kaydı (öğrenci alacak + öğretmen ücreti)
        r = await ac.get("/api/payments")
        kayitlar = r.json()
        check(len(kayitlar) == 2, f"2 otomatik ödeme kaydı oluştu ({len(kayitlar)})")
        tipler = sorted(k["tip"] for k in kayitlar)
        check(tipler == ["ogrenci", "ogretmen"], "ogrenci + ogretmen ödeme kayıtları mevcut")

        # 4) Öğretmen sayacı: ogrenci_sayisi=1, yapilmasi_gereken_odeme=300
        r = await ac.get(f"/api/teachers/{teacher_id}")
        t = r.json()
        check(t["ogrenci_sayisi"] == 1, "öğretmen ogrenci_sayisi 1'e çıktı")
        check(t["yapilmasi_gereken_odeme"] == 300, "öğretmene yapılacak ödeme 300 işlendi")

        # 5) teacher/students alt-listesi
        r = await ac.get(f"/api/teachers/{teacher_id}/students")
        check(r.status_code == 200 and len(r.json()) == 1, "öğretmenin öğrenci listesi 1 kayıt")

        # 6) Öğrenci ödemesi ekle → yapilan_odeme artmalı
        r = await ac.post("/api/payments", json={"tip": "ogrenci", "kisi_id": student_id, "miktar": 400})
        check(r.status_code == 200, "öğrenci ödemesi eklendi")
        r = await ac.get(f"/api/students/{student_id}")
        check(r.json()["yapilan_odeme"] == 400, "öğrenci yapilan_odeme 400 oldu")

        # 7) Kurs CRUD
        r = await ac.post("/api/courses", json={"ad": "Hızlı Okuma", "fiyat": 500, "sure": 10})
        check(r.status_code == 200, "kurs oluştu")
        course_id = r.json()["id"]
        r = await ac.put(f"/api/courses/{course_id}", json={"fiyat": 750})
        check(r.status_code == 200 and r.json()["fiyat"] == 750, "kurs güncellendi")

        # 8) Export tüm bölümleri içeriyor
        r = await ac.get("/api/export")
        e = r.json()
        check(all(k in e for k in ("ogretmenler", "ogrenciler", "kurslar", "odemeler")),
              "export tüm bölümleri içeriyor")
        check(len(e["ogrenciler"]) == 1 and len(e["ogretmenler"]) == 1, "export sayıları doğru")

        # 9) Öğrenci sil → öğretmen sayacı geri düşmeli
        r = await ac.delete(f"/api/students/{student_id}")
        check(r.status_code == 200, "öğrenci silindi")
        r = await ac.get(f"/api/teachers/{teacher_id}")
        check(r.json()["ogrenci_sayisi"] == 0, "öğrenci silinince sayaç 0'a döndü")

    await server.client.drop_database(TEST_DB)


def main():
    asyncio.run(run())
    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    sys.exit(0 if _kalan == 0 else 1)


if __name__ == "__main__":
    main()
