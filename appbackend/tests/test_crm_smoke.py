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
    import uuid
    import server
    from core.auth import create_access_token
    from httpx import AsyncClient, ASGITransport

    await server.client.drop_database(TEST_DB)
    # Öğrenci oluşturma artık kimlik ister; admin token'ı kullanılır.
    admin_id = str(uuid.uuid4())
    await server.db.users.insert_one({"id": admin_id, "ad": "Yön", "soyad": "Etici", "role": "admin"})
    H_admin = {"Authorization": f"Bearer {create_access_token({'sub': admin_id})}"}
    transport = ASGITransport(app=server.app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 0) /teachers artık auth ister (admin/koordinatör) — token'sız 403
        r = await ac.post("/api/teachers", json={"ad": "X", "soyad": "Y", "brans": "T", "telefon": "5", "seviye": "yeni"})
        check(r.status_code in (401, 403), f"token'sız /teachers reddedildi (status={r.status_code})")

        # 1) Öğretmen oluştur (admin)
        r = await ac.post("/api/teachers", headers=H_admin, json={
            "ad": "Ayşe", "soyad": "Yıldız", "brans": "Türkçe",
            "telefon": "5551112233", "seviye": "uzman",
            "yapilmasi_gereken_odeme": 0,
        })
        check(r.status_code == 200, f"öğretmen oluştu (status={r.status_code})")
        teacher_id = r.json()["id"]

        # 2) Öğrenci oluştur (admin) → öğretmene ata, ödeme alanlarıyla
        r = await ac.post("/api/students", json={
            "ad": "Can", "soyad": "Demir", "sinif": "4",
            "veli_ad": "Veli", "veli_soyad": "Demir", "veli_telefon": "5559998877",
            "aldigi_egitim": "Hızlı Okuma", "kur": "1",
            "yapilmasi_gereken_odeme": 1000,
            "ogretmene_yapilacak_odeme": 300,
            "ogretmen_id": teacher_id,
        }, headers=H_admin)
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

        # 10) Öğretmen kendi öğrencisini ekler: teacher_id zorlanır, mali alanlar yok sayılır
        teacher_user_id = str(uuid.uuid4())
        await server.db.users.insert_one({"id": teacher_user_id, "ad": "Ayşe", "soyad": "Yıldız",
                                          "role": "teacher", "linked_id": teacher_id})
        H_teacher = {"Authorization": f"Bearer {create_access_token({'sub': teacher_user_id})}"}
        r = await ac.post("/api/students", json={
            "ad": "Ela", "soyad": "Kaya", "sinif": "3",
            "veli_ad": "Veli", "veli_soyad": "Kaya", "veli_telefon": "5550001122",
            "aldigi_egitim": "Anlama Becerileri", "kur": "2",
            "yapilmasi_gereken_odeme": 5000, "ogretmene_yapilacak_odeme": 999,
            "ogretmen_id": "SAHTE_BASKA_OGRETMEN",
        }, headers=H_teacher)
        check(r.status_code == 200, f"öğretmen öğrenci ekledi (status={r.status_code})")
        yeni = r.json()
        check(yeni["ogretmen_id"] == teacher_id, "ogretmen_id öğretmene zorlandı (body yok sayıldı)")
        check(yeni["yapilmasi_gereken_odeme"] == 0 and yeni["ogretmene_yapilacak_odeme"] == 0,
              "mali alanlar yok sayıldı (0)")
        r = await ac.get(f"/api/teachers/{teacher_id}")
        check(r.json()["ogrenci_sayisi"] == 1, "öğretmen sayacı tekrar 1")
        # öğretmenin eklemesi mali kayıt üretmemeli (hâlâ 2 otomatik kayıt + 1 manuel = 3)
        r = await ac.get("/api/payments")
        check(len(r.json()) == 3, f"öğretmen ekleme yeni ödeme kaydı üretmedi ({len(r.json())})")

        # 11) Öğretmen /students listesinde mali alanlar gizli
        r = await ac.get("/api/students", headers=H_teacher)
        check(r.status_code == 200 and len(r.json()) >= 1, "öğretmen /students listesini aldı")
        ogr = r.json()[0]
        check(all(a not in ogr for a in ("yapilmasi_gereken_odeme", "yapilan_odeme",
              "ogretmene_yapilacak_odeme")), "öğretmen listesinde mali alanlar yok")
        # admin aynı listede mali alanları görür
        r = await ac.get("/api/students", headers=H_admin)
        check("yapilmasi_gereken_odeme" in r.json()[0], "admin listesinde mali alanlar mevcut")

        # 12) Admin, öğretmenin eklediği öğrenciye sonradan ücret atar (PUT /students)
        ela_id = yeni["id"]
        r = await ac.put(f"/api/students/{ela_id}", json={
            "yapilmasi_gereken_odeme": 1200, "ogretmene_yapilacak_odeme": 400,
        }, headers=H_admin)
        check(r.status_code == 200, f"admin öğrenciyi güncelledi (status={r.status_code})")
        r = await ac.get(f"/api/students/{ela_id}")
        s = r.json()
        check(s["yapilmasi_gereken_odeme"] == 1200, "admin ödeme tutarını kaydetti (1200)")
        check(s["ogretmene_yapilacak_odeme"] == 400, "admin öğretmen payını kaydetti (400)")
        # öğretmen toplam alacağı 400'e yükseldi (0 → 400)
        r = await ac.get(f"/api/teachers/{teacher_id}")
        check(r.json()["yapilmasi_gereken_odeme"] == 400, "öğretmen toplam ödemesi 400'e güncellendi")
        # muhasebe borç tutarı = yapilmasi_gereken_odeme - yapilan_odeme = 1200
        check(max(0, s["yapilmasi_gereken_odeme"] - s["yapilan_odeme"]) == 1200, "öğrenci borç tutarı 1200")

        # 13) Öğretmen PUT ile mali alan göndermeye çalışırsa yok sayılır
        r = await ac.put(f"/api/students/{ela_id}", json={
            "kur": "5", "yapilmasi_gereken_odeme": 99999, "ogretmene_yapilacak_odeme": 88888,
        }, headers=H_teacher)
        check(r.status_code == 200, "öğretmen güncelleme isteği geçti")
        r = await ac.get(f"/api/students/{ela_id}")
        s = r.json()
        check(s["kur"] == "5", "öğretmen mali olmayan alanı (kur) güncelleyebildi")
        check(s["yapilmasi_gereken_odeme"] == 1200 and s["ogretmene_yapilacak_odeme"] == 400,
              "öğretmenin gönderdiği mali alanlar yok sayıldı")

        # 14) /teachers ile tek adımda hesap oluşturma (user ↔ teacher köprüsü)
        r = await ac.post("/api/teachers", headers=H_admin, json={
            "ad": "Koord", "soyad": "İnan", "brans": "Yönetim", "telefon": "5553334455",
            "seviye": "uzman", "hesap_olustur": True, "email": "koord@test.local",
            "hesap_rol": "coordinator",
        })
        check(r.status_code == 200, f"hesaplı öğretmen oluştu (status={r.status_code})")
        tj = r.json()
        check(tj.get("user_id") and tj.get("hesap", {}).get("gecici_sifre"),
              "user_id + geçici şifre döndü")
        # köprü: teacher.user_id = user.id ve user.linked_id = teacher.id
        yeni_user = await server.db.users.find_one({"email": "koord@test.local"})
        check(yeni_user and yeni_user["linked_id"] == tj["id"] and yeni_user["role"] == "coordinator",
              "user.linked_id = teacher.id ve rol=coordinator")
        check(yeni_user.get("sifre_degistirme_zorunlu") is True, "yeni hesap şifre değiştirme zorunlu")
        # geçici şifre ile login çalışmalı + must_change_password=true
        r = await ac.post("/api/auth/login", json={"email_or_phone": "koord@test.local",
                                                    "password": tj["hesap"]["gecici_sifre"]})
        check(r.status_code == 200 and r.json().get("must_change_password") is True,
              "geçici şifre ile login + must_change_password=true")

    await server.client.drop_database(TEST_DB)


def main():
    asyncio.run(run())
    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    sys.exit(0 if _kalan == 0 else 1)


if __name__ == "__main__":
    main()
