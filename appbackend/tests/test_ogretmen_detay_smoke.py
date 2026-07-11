"""Admin öğretmen detay-özet smoke testi (GET /teachers/{id}/detay-ozet).

Doğrular:
  - Yetki: öğretmen kendi özetine erişemez (403); admin + koordinatör erişir.
  - teachers.id → users.id köprüsü (rozet/görev/TIMI users.id ile bağlı).
  - Aktivite sayımları (öğrenci aktif/pasif, kur dağılımı, görev oranı, ders, TIMI).
  - Gelişim (XP/rozet) + son işlemler (audit).
  - Boş veri (rozetsiz/öğrencisiz öğretmen) KIRILMADAN 0'larla döner; olmayan → 404.

İzole test DB (oba_test_ogretmen_detay). Çalıştırma:
  cd appbackend && PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe tests/test_ogretmen_detay_smoke.py
"""
import asyncio
import os
import sys

TEST_DB = "oba_test_ogretmen_detay"
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
    from core.sistem import get_ogretmen_rozetleri
    from httpx import AsyncClient, ASGITransport

    await server.client.drop_database(TEST_DB)

    admin_id, coord_id, tuser_id = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
    tid = str(uuid.uuid4())  # teachers.id
    await server.db.users.insert_many([
        {"id": admin_id, "ad": "Yon", "soyad": "Etici", "role": "admin"},
        {"id": coord_id, "ad": "Koor", "soyad": "Dinator", "role": "coordinator"},
        {"id": tuser_id, "ad": "Zeynep", "soyad": "Hoca", "role": "teacher", "linked_id": tid, "puan": 40},
    ])
    await server.db.teachers.insert_one({
        "id": tid, "ad": "Zeynep", "soyad": "Hoca", "brans": "Türkçe", "seviye": "uzman",
        "user_id": tuser_id, "yapilmasi_gereken_odeme": 500.0, "yapilan_odeme": 200.0,
    })
    # Öğrenciler (teachers.id ile) — 2 aktif (kur 2), 1 pasif
    await server.db.students.insert_many([
        {"id": str(uuid.uuid4()), "ad": "A", "soyad": "A", "ogretmen_id": tid, "kur": "2", "arsivli": False},
        {"id": str(uuid.uuid4()), "ad": "B", "soyad": "B", "ogretmen_id": tid, "kur": "2", "arsivli": False},
        {"id": str(uuid.uuid4()), "ad": "C", "soyad": "C", "ogretmen_id": tid, "kur": "1", "arsivli": True},
    ])
    # Görevler (atayan_id = users.id) — 2 atanan, 1 tamamlanan
    await server.db.gorevler.insert_many([
        {"id": str(uuid.uuid4()), "atayan_id": tuser_id, "baslik": "G1", "durum": "tamamlandi", "olusturma_tarihi": "2026-01-01T00:00:00"},
        {"id": str(uuid.uuid4()), "atayan_id": tuser_id, "baslik": "G2", "durum": "bekliyor", "olusturma_tarihi": "2026-02-01T00:00:00"},
    ])
    # Rozet (kullanici_id = users.id) — gerçek bir öğretmen rozet kodu
    rozet_def = await get_ogretmen_rozetleri()
    kod = rozet_def[0]["kod"]
    await server.db.kazanilan_rozetler.insert_one({"id": str(uuid.uuid4()), "kullanici_id": tuser_id, "rozet_kodu": kod, "kazanma_tarihi": "2026-01-15T00:00:00"})
    # Ders serisi (teachers.id) + TIMI (users.id) + islem_log (users.id)
    await server.db.ders_serileri.insert_one({"id": str(uuid.uuid4()), "ogretmen_id": tid, "durum": "aktif", "gun": 1})
    await server.db.timi_sonuclar.insert_one({"id": str(uuid.uuid4()), "ogretmen_id": tuser_id, "durum": "tamamlandi", "ogrenci_id": "x"})
    await server.db.islem_log.insert_one({"id": str(uuid.uuid4()), "kullanici_id": tuser_id, "kullanici_ad": "Zeynep Hoca", "modul": "ogrenci", "islem": "kur_gecis", "hedef_tip": "ogrenci", "tarih": "2026-02-10T00:00:00"})

    H_admin = {"Authorization": f"Bearer {create_access_token({'sub': admin_id})}"}
    H_coord = {"Authorization": f"Bearer {create_access_token({'sub': coord_id})}"}
    H_teacher = {"Authorization": f"Bearer {create_access_token({'sub': tuser_id})}"}

    transport = ASGITransport(app=server.app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Yetki: öğretmen → 403
        r = await ac.get(f"/api/teachers/{tid}/detay-ozet", headers=H_teacher)
        check(r.status_code == 403, f"öğretmen kendi detay-özetine erişemez (403) ({r.status_code})")

        # Admin → 200 + şekil
        r = await ac.get(f"/api/teachers/{tid}/detay-ozet", headers=H_admin)
        check(r.status_code == 200, f"admin detay-özet 200 ({r.status_code})")
        d = r.json()
        check(all(k in d for k in ("ogretmen", "gelisim", "aktivite", "son_islemler")), "4 bölüm anahtarı mevcut")
        og = d.get("aktivite", {}).get("ogrenci", {})
        check(og == {"aktif": 2, "pasif": 1, "toplam": 3}, f"öğrenci aktif/pasif/toplam=2/1/3 ({og})")
        check(any(x.get("kur") == "2" and x.get("sayi") == 2 for x in d["aktivite"].get("kur_dagilimi", [])), "kur dağılımı Kur 2 → 2 öğrenci")
        gv = d["aktivite"].get("gorev", {})
        check(gv.get("atanan") == 2 and gv.get("tamamlanan") == 1 and gv.get("oran") == 50, f"görev 2 atanan/1 tamam/%50 ({gv.get('atanan')},{gv.get('tamamlanan')},{gv.get('oran')})")
        check(d["aktivite"].get("ders", {}).get("aktif_seri") == 1, "aktif ders serisi 1")
        check(d["aktivite"].get("timi", {}).get("toplam") == 1, "TIMI toplam 1")
        gl = d.get("gelisim", {})
        check(gl.get("rozet_sayisi") == 1 and len(gl.get("rozetler", [])) == 1 and gl["rozetler"][0].get("kod") == kod,
              "rozet users.id köprüsüyle geldi (ikonlu)")
        check(gl["rozetler"][0].get("ikon"), "rozet ikonu dolu")
        check(isinstance(gl.get("toplam_xp"), (int, float)) and gl.get("toplam_ogretmen", 0) >= 1, "gelişim XP/sıra alanları sayısal")
        check(len(d.get("son_islemler", [])) >= 1 and d["son_islemler"][0].get("islem") == "kur_gecis", "son işlemler (audit) geldi")

        # Koordinatör → 200
        r = await ac.get(f"/api/teachers/{tid}/detay-ozet", headers=H_coord)
        check(r.status_code == 200, f"koordinatör de erişebilir ({r.status_code})")

        # Boş veri (rozetsiz/öğrencisiz öğretmen) → kırılmadan 0
        tid2 = str(uuid.uuid4())
        await server.db.teachers.insert_one({"id": tid2, "ad": "Bos", "soyad": "Ogretmen"})
        r = await ac.get(f"/api/teachers/{tid2}/detay-ozet", headers=H_admin)
        d2 = r.json()
        check(r.status_code == 200 and d2["gelisim"]["rozet_sayisi"] == 0 and d2["aktivite"]["ogrenci"]["toplam"] == 0,
              "veri yok → kırılmadan 0'larla döner")

        # Olmayan öğretmen → 404
        r = await ac.get(f"/api/teachers/{uuid.uuid4()}/detay-ozet", headers=H_admin)
        check(r.status_code == 404, f"olmayan öğretmen 404 ({r.status_code})")

    await server.client.drop_database(TEST_DB)


def main():
    asyncio.run(run())
    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    sys.exit(0 if _kalan == 0 else 1)


if __name__ == "__main__":
    main()
