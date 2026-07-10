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
    H_admin = {"Authorization": f"Bearer {create_access_token({'sub': admin_id})}"}
    H_acc = {"Authorization": f"Bearer {create_access_token({'sub': acc_id})}"}
    H_teacher = {"Authorization": f"Bearer {create_access_token({'sub': teacher_id})}"}
    H_student = {"Authorization": f"Bearer {create_access_token({'sub': student_uid})}"}

    # Ödeme hedefi: veli (ödeme sütunları için gerekli) + eğitim/CRM alanları (sızmamalı)
    sid = str(uuid.uuid4())
    await server.db.students.insert_one({
        "id": sid, "ad": "Ali", "soyad": "Yılmaz",
        "veli_ad": "Ayşe", "veli_soyad": "Yılmaz", "veli_telefon": "5550001122",
        "yapilmasi_gereken_odeme": 1000.0, "yapilan_odeme": 0.0,
        "ogretmene_yapilacak_odeme": 300.0,
        # Eğitim/CRM verisi — muhasebe panelinde GÖRÜNMEMELİ:
        "aldigi_egitim": "GİZLİ EĞİTİM", "sinif": "GİZLİ SINIF", "notlar": "GİZLİ NOT",
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
        # 3a) veli + ödeme alanları döner (düzenlenebilir sütunlar için gerekli)
        check(ogr is not None and ogr.get("veli_ad") == "Ayşe" and ogr.get("yapilmasi_gereken_odeme") == 1000.0,
              "kişiler veli + ödeme alanlarını içeriyor")
        # 3b) eğitim/CRM verisi SIZMAZ
        check(ogr is not None and "aldigi_egitim" not in ogr and "sinif" not in ogr and "notlar" not in ogr,
              "kişiler yanıtı eğitim/CRM verisi (aldigi_egitim/sinif/notlar) sızdırmıyor")

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

        # 6b) Satır içi düzenleme (PATCH) — veli + para alanı + not
        r = await ac.patch(f"/api/muhasebe/kisi/ogrenci/{sid}", headers=H_acc,
                           json={"veli_ad": "Yeni", "veli_soyad": "Veli", "muhasebe_notu": "eylüle ertelendi"})
        check(r.status_code == 200, f"accountant PATCH kişi (veli/not) 200 ({r.status_code})")
        st = await server.db.students.find_one({"id": sid})
        check(st.get("veli_ad") == "Yeni" and st.get("muhasebe_notu") == "eylüle ertelendi",
              "PATCH veli_ad + muhasebe_notu yazıldı")
        r = await ac.patch(f"/api/muhasebe/kisi/ogrenci/{sid}", headers=H_acc, json={"yapilan_odeme": 500})
        st = await server.db.students.find_one({"id": sid})
        check(r.status_code == 200 and st.get("yapilan_odeme") == 500.0, "PATCH para alanı (yapilan_odeme) 500")
        # negatif para reddedilir
        r = await ac.patch(f"/api/muhasebe/kisi/ogrenci/{sid}", headers=H_acc, json={"yapilan_odeme": -10})
        check(r.status_code == 422, f"negatif para 422 ({r.status_code})")
        # whitelist dışı alan yok sayılır (sinif düzenlenemez)
        r = await ac.patch(f"/api/muhasebe/kisi/ogrenci/{sid}", headers=H_acc, json={"sinif": "99"})
        check(r.status_code == 400, "whitelist dışı alan (sinif) reddedildi")

        # 6c) Kur ücreti ekleme → beklenen toplam artar + kur_ucretleri kaydı
        before = (await server.db.students.find_one({"id": sid}))["yapilmasi_gereken_odeme"]
        r = await ac.post(f"/api/muhasebe/ogrenci/{sid}/kur-ucreti", headers=H_acc,
                          json={"kur_adi": "Kur 3", "tutar": 750, "baslangic_tarihi": "2025-09-01"})
        check(r.status_code == 200 and abs(r.json().get("yeni_beklenen", 0) - (before + 750)) < 0.01,
              f"kur ücreti eklendi, beklenen +750 ({r.status_code})")
        after = (await server.db.students.find_one({"id": sid}))["yapilmasi_gereken_odeme"]
        check(abs(after - (before + 750)) < 0.01, f"yapilmasi_gereken_odeme {before}→{after}")
        kr = await ac.get(f"/api/muhasebe/ogrenci/{sid}/kur-ucretleri", headers=H_acc)
        check(kr.status_code == 200 and any(o["kur_adi"] == "Kur 3" for o in kr.json().get("ogeler", [])),
              "kur_ucretleri listesinde yeni kayıt var")

        # 6d) Audit log düştü mü
        log_say = await server.db.islem_log.count_documents({"hedef_id": sid, "modul": "muhasebe"})
        check(log_say >= 3, f"islem_log (modül=muhasebe) kayıtları düştü ({log_say})")
        r = await ac.get(f"/api/muhasebe/log?hedef_id={sid}", headers=H_admin)
        check(r.status_code == 200 and len(r.json().get("kayitlar", [])) >= 3, "admin log okuyabiliyor")
        r = await ac.get("/api/muhasebe/log", headers=H_acc)
        check(r.status_code == 403, "accountant log okuyamaz (yalnız admin)")

        # 7) teacher/student erişemez
        check((await ac.get("/api/payments", headers=H_teacher)).status_code == 403, "teacher /payments 403")
        check((await ac.get("/api/muhasebe/ozet", headers=H_teacher)).status_code == 403, "teacher /muhasebe/ozet 403")
        check((await ac.get("/api/payments", headers=H_student)).status_code == 403, "student /payments 403")
        check((await ac.get("/api/muhasebe/kisiler", headers=H_student)).status_code == 403, "student /muhasebe/kisiler 403")
        r = await ac.patch(f"/api/muhasebe/kisi/ogrenci/{sid}", headers=H_teacher, json={"yapilan_odeme": 1})
        check(r.status_code == 403, f"teacher PATCH kişi 403 ({r.status_code})")
        r = await ac.post(f"/api/muhasebe/ogrenci/{sid}/kur-ucreti", headers=H_student, json={"kur_adi": "X", "tutar": 1})
        check(r.status_code == 403, f"student kur ücreti 403 ({r.status_code})")

        # 8) accountant eğitim ucuna erişemez
        r = await ac.get("/api/meb-kelime/liste", headers=H_acc)
        check(r.status_code == 403, f"accountant eğitim ucuna (/meb-kelime/liste) 403 ({r.status_code})")

    await server.client.drop_database(TEST_DB)


if __name__ == "__main__":
    asyncio.run(run())
    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    sys.exit(1 if _kalan else 0)
