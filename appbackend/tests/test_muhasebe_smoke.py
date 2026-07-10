"""Muhasebe (accountant rolü + /muhasebe/* + /payments koruması) smoke testi.

Doğrular:
  - accountant: /muhasebe/ozet + /muhasebe/kisiler + /payments CRUD (tam yetki)
  - teacher/student: /payments + /muhasebe/* → 403
  - accountant: eğitim ucuna (/meb-kelime/liste) → 403
  - /muhasebe/kisiler CRM detayı sızdırmaz (veli/not/telefon dönmez)
  - auth'suz /payments → 401/403

İzole test DB'sine karşı çalışır (oba_test_muhasebe_smoke). Gerçek DB'ye dokunmaz.
    cd appbackend
    .venv/Scripts/python.exe tests/test_muhasebe_smoke.py
"""
import asyncio
import os
import sys

TEST_DB = "oba_test_muhasebe_smoke"
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

    # Kullanıcılar (token 'sub' → db.users.id ile eşleşir)
    admin_id = str(uuid.uuid4())
    acc_id = str(uuid.uuid4())
    teacher_id = str(uuid.uuid4())
    student_uid = str(uuid.uuid4())
    await server.db.users.insert_many([
        {"id": admin_id, "ad": "Yön", "soyad": "Etici", "role": "admin"},
        {"id": acc_id, "ad": "Muh", "soyad": "Asebe", "role": "accountant"},
        {"id": teacher_id, "ad": "Öğ", "soyad": "Retmen", "role": "teacher"},
        {"id": student_uid, "ad": "Öğ", "soyad": "Renci", "role": "student"},
    ])
    H_acc = {"Authorization": f"Bearer {create_access_token({'sub': acc_id})}"}
    H_teacher = {"Authorization": f"Bearer {create_access_token({'sub': teacher_id})}"}
    H_student = {"Authorization": f"Bearer {create_access_token({'sub': student_uid})}"}

    # Ödeme hedefi: CRM detayı (veli/not/telefon) İÇEREN bir öğrenci kaydı
    sid = str(uuid.uuid4())
    await server.db.students.insert_one({
        "id": sid, "ad": "Ali", "soyad": "Veli",
        "yapilmasi_gereken_odeme": 1000.0, "yapilan_odeme": 0.0,
        "ogretmene_yapilacak_odeme": 300.0,
        "veli_adi": "GİZLİ VELİ", "notlar": "GİZLİ NOT", "telefon": "5550001122",
    })

    transport = ASGITransport(app=server.app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1) auth'suz /payments reddedilir (eskiden açıktı)
        r = await ac.get("/api/payments")
        check(r.status_code in (401, 403), f"auth'suz /payments reddedildi ({r.status_code})")

        # 2) accountant özet + kişiler
        r = await ac.get("/api/muhasebe/ozet", headers=H_acc)
        check(r.status_code == 200 and "ogrenci" in r.json() and "ogretmen" in r.json(),
              f"accountant /muhasebe/ozet 200 + alanlar ({r.status_code})")
        check(r.json()["ogrenci"]["beklenen"] == 1000.0, "özet beklenen tahsilat = 1000")

        r = await ac.get("/api/muhasebe/kisiler", headers=H_acc)
        ogr = next((o for o in r.json().get("ogrenciler", []) if o["id"] == sid), None)
        check(r.status_code == 200 and ogr is not None, "accountant /muhasebe/kisiler öğrenciyi döndü")
        # 3) CRM detayı SIZMAZ
        check(ogr is not None and "veli_adi" not in ogr and "notlar" not in ogr and "telefon" not in ogr,
              "kişiler yanıtı veli/not/telefon sızdırmıyor")
        check(ogr is not None and ogr.get("yapilmasi_gereken_odeme") == 1000.0,
              "kişiler ödeme alanlarını içeriyor")

        # 4) accountant POST /payments (tarih ile) → bakiye artar
        r = await ac.post("/api/payments", headers=H_acc, json={
            "tip": "ogrenci", "kisi_id": sid, "miktar": 400, "aciklama": "taksit",
            "tarih": "2025-03-01T00:00:00"})
        check(r.status_code == 200, f"accountant ödeme kaydetti ({r.status_code})")
        pid = r.json().get("id")
        check(str(r.json().get("tarih", ""))[:10] == "2025-03-01", "özel tarih onurlandırıldı")
        st = await server.db.students.find_one({"id": sid})
        check(st["yapilan_odeme"] == 400.0, f"ödeme sonrası yapilan_odeme=400 ({st['yapilan_odeme']})")

        # 5) accountant PUT /payments → miktar 400→600, bakiye +200
        r = await ac.put(f"/api/payments/{pid}", headers=H_acc, json={"miktar": 600})
        check(r.status_code == 200 and r.json().get("miktar") == 600, f"accountant ödeme düzeltti ({r.status_code})")
        st = await server.db.students.find_one({"id": sid})
        check(st["yapilan_odeme"] == 600.0, f"düzeltme sonrası yapilan_odeme=600 ({st['yapilan_odeme']})")

        # 6) accountant DELETE /payments → bakiye başa döner
        r = await ac.delete(f"/api/payments/{pid}", headers=H_acc)
        check(r.status_code == 200, f"accountant ödeme sildi ({r.status_code})")
        st = await server.db.students.find_one({"id": sid})
        check(st["yapilan_odeme"] == 0.0, f"silme sonrası yapilan_odeme=0 ({st['yapilan_odeme']})")

        # 7) teacher/student erişemez
        check((await ac.get("/api/payments", headers=H_teacher)).status_code == 403, "teacher /payments 403")
        check((await ac.get("/api/muhasebe/ozet", headers=H_teacher)).status_code == 403, "teacher /muhasebe/ozet 403")
        check((await ac.get("/api/payments", headers=H_student)).status_code == 403, "student /payments 403")
        check((await ac.get("/api/muhasebe/kisiler", headers=H_student)).status_code == 403, "student /muhasebe/kisiler 403")

        # 8) accountant eğitim ucuna erişemez
        r = await ac.get("/api/meb-kelime/liste", headers=H_acc)
        check(r.status_code == 403, f"accountant eğitim ucuna (/meb-kelime/liste) 403 ({r.status_code})")

    await server.client.drop_database(TEST_DB)


if __name__ == "__main__":
    asyncio.run(run())
    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    sys.exit(1 if _kalan else 0)
