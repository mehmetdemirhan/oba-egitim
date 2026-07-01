"""Puan Tablosu role göre filtreleme smoke testi.

Öğrenci ?rol=ogrenci → sadece öğrenciler, sıralı, kendini vurgular.
Öğrenci ?rol=ogretmen → 403.
Öğretmen ?rol=ogretmen → isimsiz agrega + motivasyon (isim/sıra listesi YOK).
Öğretmen ?rol=ogrenci → 403.
Admin → ikisini de çekebilir. Geçersiz rol → 400.
İzole test DB'sine karşı çalışır.

    cd appbackend
    .venv/Scripts/python.exe tests/test_puan_tablosu_rol_smoke.py
"""
import asyncio
import os
import sys
import uuid

TEST_DB = "oba_test_puan_tablosu_rol_smoke"
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
    from core.auth import create_access_token
    from httpx import AsyncClient, ASGITransport

    await server.client.drop_database(TEST_DB)

    # Öğretmenler (db.users) — farklı puanlar
    t1 = str(uuid.uuid4())  # test edilen öğretmen (orta sıra)
    t2 = str(uuid.uuid4())  # en yüksek
    t3 = str(uuid.uuid4())  # en düşük
    await server.db.users.insert_one({"id": t1, "ad": "Ayşe", "soyad": "Öğretmen", "role": "teacher", "puan": 4000})
    await server.db.users.insert_one({"id": t2, "ad": "Mehmet", "soyad": "Öğretmen", "role": "teacher", "puan": 9000})
    await server.db.users.insert_one({"id": t3, "ad": "Zeynep", "soyad": "Öğretmen", "role": "teacher", "puan": 1000})

    # Admin
    adm = str(uuid.uuid4())
    await server.db.users.insert_one({"id": adm, "ad": "Admin", "soyad": "Yönetici", "role": "admin"})

    # Öğrenciler (db.students) + öğrenci user (db.users)
    s1 = str(uuid.uuid4())  # en yüksek xp
    s2 = str(uuid.uuid4())  # orta (test edilen öğrenci)
    s3 = str(uuid.uuid4())  # en düşük
    await server.db.students.insert_one({"id": s1, "ad": "Ali", "soyad": "Yılmaz", "sinif": 3, "toplam_xp": 8888})
    await server.db.students.insert_one({"id": s2, "ad": "Veli", "soyad": "Kaya", "sinif": 3, "toplam_xp": 5000})
    await server.db.students.insert_one({"id": s3, "ad": "Ece", "soyad": "Demir", "sinif": 3, "toplam_xp": 100})
    su = str(uuid.uuid4())
    await server.db.users.insert_one({"id": su, "ad": "Veli", "soyad": "Kaya", "role": "student", "linked_id": s2})

    HT = {"Authorization": f"Bearer {create_access_token({'sub': t1})}"}
    HA = {"Authorization": f"Bearer {create_access_token({'sub': adm})}"}
    HS = {"Authorization": f"Bearer {create_access_token({'sub': su})}"}

    transport = ASGITransport(app=server.app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # ── Öğrenci: rol=ogrenci ──
        r = await ac.get("/api/puan-tablosu", params={"rol": "ogrenci"}, headers=HS)
        check(r.status_code == 200, f"öğrenci rol=ogrenci 200 (status={r.status_code})")
        d = r.json()
        liste = d.get("siralama", [])
        check(len(liste) == 3, f"3 öğrenci döndü (adet={len(liste)})")
        check(all(x["rol"] == "student" for x in liste), "tüm kayıtlar student rolünde")
        # Sıralama: xp azalan
        check([x["xp"] for x in liste] == [8888, 5000, 100], "öğrenciler XP'ye göre azalan sıralı")
        check(liste[0]["ad_soyad"] == "Ali Yılmaz" and liste[0]["sira"] == 1, "en yüksek öğrenci 1. sırada, isimli")
        # Kendini vurgular
        ben = [x for x in liste if x.get("ben")]
        check(len(ben) == 1 and ben[0]["id"] == s2, "öğrenci kendini 'ben' olarak görüyor")

        # ── Öğrenci: rol=ogretmen → 403 ──
        r = await ac.get("/api/puan-tablosu", params={"rol": "ogretmen"}, headers=HS)
        check(r.status_code == 403, f"öğrenci rol=ogretmen 403 (status={r.status_code})")

        # ── Öğretmen: rol=ogretmen → agrega (isim yok) ──
        r = await ac.get("/api/puan-tablosu", params={"rol": "ogretmen"}, headers=HT)
        check(r.status_code == 200, f"öğretmen rol=ogretmen 200 (status={r.status_code})")
        d = r.json()
        check(d.get("toplam_ogretmen") == 3, f"toplam_ogretmen=3 (gelen={d.get('toplam_ogretmen')})")
        check(d.get("kullanicinin_sirasi") == 2, f"öğretmen sırası 2 (gelen={d.get('kullanicinin_sirasi')})")
        check(d.get("kullanicinin_puani") == 4000, f"öğretmen puanı 4000 (gelen={d.get('kullanicinin_puani')})")
        ist = d.get("istatistikler", {})
        check(ist.get("en_yuksek_puan") == 9000 and ist.get("en_dusuk_puan") == 1000, "en yüksek/düşük doğru")
        check(ist.get("ortalama_puan_ogretmen") == round((9000 + 4000 + 1000) / 3), "ortalama doğru")
        check(ist.get("medyan") == 4000, f"medyan 4000 (gelen={ist.get('medyan')})")
        check(bool(d.get("motivasyon_mesaji")), "motivasyon mesajı var")
        # İSİM/SIRA LİSTESİ DÖNMEMELİ
        metin = str(d)
        check("siralama" not in d and "Ayşe" not in metin and "Mehmet" not in metin and "Zeynep" not in metin,
              "öğretmen yanıtı isim/sıra listesi içermiyor")

        # ── Öğretmen: rol=ogrenci → 403 ──
        r = await ac.get("/api/puan-tablosu", params={"rol": "ogrenci"}, headers=HT)
        check(r.status_code == 403, f"öğretmen rol=ogrenci 403 (status={r.status_code})")

        # ── Admin: ikisini de çekebilir ──
        r = await ac.get("/api/puan-tablosu", params={"rol": "ogrenci"}, headers=HA)
        check(r.status_code == 200, f"admin rol=ogrenci 200 (status={r.status_code})")
        r = await ac.get("/api/puan-tablosu", params={"rol": "ogretmen"}, headers=HA)
        check(r.status_code == 200, f"admin rol=ogretmen 200 (status={r.status_code})")

        # ── Geçersiz rol → 400 ──
        r = await ac.get("/api/puan-tablosu", params={"rol": "veli"}, headers=HA)
        check(r.status_code == 400, f"geçersiz rol 400 (status={r.status_code})")

    await server.client.drop_database(TEST_DB)
    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    return _kalan == 0


if __name__ == "__main__":
    ok = asyncio.run(run())
    sys.exit(0 if ok else 1)
