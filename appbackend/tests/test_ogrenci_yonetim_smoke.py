"""Öğretmen öğrenci düzenle/kaldır (sahiplik + soft-delete + audit) smoke testi.

Doğrular: öğretmen kendi öğrencisini düzenler/kaldırır; başkasının öğrencisine
dokunamaz (403); soft-delete muhasebeyi korur (payments durur); verisi olmayan
öğrenci kalıcı silinebilir; islem_log audit; İşlem Kayıtları yalnız yönetici.
İzole DB (oba_test_ogrenci_yonetim). Gerçek DB'ye dokunmaz.
"""
import asyncio
import os
import sys

TEST_DB = "oba_test_ogrenci_yonetim"
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
    import uuid
    import server
    from core.auth import create_access_token
    from httpx import AsyncClient, ASGITransport

    await server.client.drop_database(TEST_DB)
    admin_id = str(uuid.uuid4())
    tA, tB = str(uuid.uuid4()), str(uuid.uuid4())          # teacher record id'leri
    uA, uB = str(uuid.uuid4()), str(uuid.uuid4())          # teacher user id'leri
    await server.db.users.insert_many([
        {"id": admin_id, "ad": "Yön", "soyad": "Etici", "role": "admin"},
        {"id": uA, "ad": "Öğr", "soyad": "A", "role": "teacher", "linked_id": tA},
        {"id": uB, "ad": "Öğr", "soyad": "B", "role": "teacher", "linked_id": tB},
    ])
    await server.db.teachers.insert_many([
        {"id": tA, "ad": "Öğr", "soyad": "A", "ogrenci_sayisi": 0, "atanan_ogrenciler": [], "yapilmasi_gereken_odeme": 0, "yapilan_odeme": 0},
        {"id": tB, "ad": "Öğr", "soyad": "B", "ogrenci_sayisi": 0, "atanan_ogrenciler": [], "yapilmasi_gereken_odeme": 0, "yapilan_odeme": 0},
    ])
    H_admin = {"Authorization": f"Bearer {create_access_token({'sub': admin_id})}"}
    HA = {"Authorization": f"Bearer {create_access_token({'sub': uA})}"}
    HB = {"Authorization": f"Bearer {create_access_token({'sub': uB})}"}

    transport = ASGITransport(app=server.app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yeni = {"ad": "Ali", "soyad": "Veli", "sinif": "3", "veli_ad": "Ayşe", "veli_soyad": "Veli",
                "veli_telefon": "5551112233", "aldigi_egitim": "Hızlı Okuma", "kur": "1"}
        # Öğretmen A öğrenci oluşturur (ogretmen_id kendine sabitlenir)
        r = await ac.post("/api/students", headers=HA, json=yeni)
        check(r.status_code == 200, f"öğretmen A öğrenci ekledi ({r.status_code})")
        sid = r.json()["id"]
        check(r.json()["ogretmen_id"] == tA, "öğrenci A öğretmenine bağlandı")

        # A kendi öğrencisini düzenler → 200 + audit
        r = await ac.put(f"/api/students/{sid}", headers=HA, json={"sinif": "4", "veli_telefon": "5559998877"})
        check(r.status_code == 200 and r.json()["sinif"] == "4", "A kendi öğrencisini düzenledi")
        log = await server.db.islem_log.count_documents({"modul": "ogrenci", "islem": "duzenle", "hedef_id": sid})
        check(log >= 2, f"düzenleme audit'e düştü (değişen 2 alan) ({log})")

        # B başkasının öğrencisini düzenleyemez / kaldıramaz → 403
        check((await ac.put(f"/api/students/{sid}", headers=HB, json={"sinif": "9"})).status_code == 403,
              "B başka öğretmenin öğrencisini DÜZENLEYEMEZ (403)")
        check((await ac.delete(f"/api/students/{sid}", headers=HB)).status_code == 403,
              "B başka öğretmenin öğrencisini KALDIRAMAZ (403)")

        # Veri oluştur (öğrenci ödemesi) → soft-delete gerektirir
        await server.db.payments.insert_one({"id": str(uuid.uuid4()), "tip": "ogrenci", "kisi_id": sid, "miktar": 100})
        r = await ac.delete(f"/api/students/{sid}", headers=HA)
        check(r.status_code == 200 and r.json()["mod"] == "pasif", "verisi olan öğrenci PASİFE alındı")
        st = await server.db.students.find_one({"id": sid})
        check(st and st.get("arsivli") is True, "öğrenci arsivli=true")
        check(await server.db.payments.count_documents({"kisi_id": sid}) == 1, "soft-delete ödeme kaydını KORUDU (muhasebe bütünlüğü)")
        # Aktif listede görünmez
        liste = (await ac.get("/api/students", headers=HA)).json()
        check(not any(s["id"] == sid for s in liste), "pasif öğrenci aktif /students listesinde yok")

        # Verisi olmayan öğrenci + kalici=true → gerçek silme
        r = await ac.post("/api/students", headers=HA, json={**yeni, "ad": "Bos", "veli_telefon": "5550000000"})
        sid2 = r.json()["id"]
        r = await ac.delete(f"/api/students/{sid2}?kalici=true", headers=HA)
        check(r.status_code == 200 and r.json()["mod"] == "kalici", "verisi olmayan öğrenci KALICI silindi")
        check(await server.db.students.find_one({"id": sid2}) is None, "kalıcı silinen öğrenci DB'de yok")

        # İşlem Kayıtları: yönetici okur, öğretmen okuyamaz
        r = await ac.get("/api/islem-log?modul=ogrenci", headers=H_admin)
        check(r.status_code == 200 and len(r.json()["kayitlar"]) >= 3, "yönetici İşlem Kayıtları'nı okuyabiliyor")
        check((await ac.get("/api/islem-log", headers=HA)).status_code == 403, "öğretmen İşlem Kayıtları'na erişemez (403)")

    await server.client.drop_database(TEST_DB)


if __name__ == "__main__":
    asyncio.run(run())
    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    sys.exit(1 if _kalan else 0)
