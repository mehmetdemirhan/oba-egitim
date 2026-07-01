"""Öğretmen profil modülü smoke testi (izole test DB).

    cd appbackend
    .venv/Scripts/python.exe tests/test_ogretmen_profil_smoke.py

Kapsam:
  - GET /ogretmen/profil → teacher 200, öğrenci 403
  - PUT /ogretmen/profil → izinli alanlar güncellenir; email/seviye korunur
  - PUT /admin/profil-gorunurluk → sadece admin; öğretmen 403
  - GET /ogretmen/{id}/profil-public → görünürlük filtresi (veli/öğrenci/admin)
  - POST /ogretmen/profil/foto → dosya yükler, URL döner
"""
import asyncio
import io
import os
import sys
import uuid

TEST_DB = "oba_test_ogretmen_profil_smoke"
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


def _png_bytes():
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (600, 600), (120, 90, 200)).save(buf, format="PNG")
    return buf.getvalue()


async def run():
    import server
    from core.auth import create_access_token
    from httpx import AsyncClient, ASGITransport

    await server.client.drop_database(TEST_DB)

    trec = str(uuid.uuid4())        # teacher kaydı (teachers.id)
    tuser = str(uuid.uuid4())       # teacher user (users.id)
    await server.db.teachers.insert_one({
        "id": trec, "ad": "Ayşe", "soyad": "Öğretmen", "brans": "Türkçe",
        "telefon": "05001112233", "seviye": "uzman", "olusturma_tarihi": "2024-04-15T00:00:00",
    })
    await server.db.users.insert_one({
        "id": tuser, "ad": "Ayşe", "soyad": "Öğretmen", "role": "teacher",
        "linked_id": trec, "email": "ayse@oba.com",
    })

    su = str(uuid.uuid4())          # öğrenci
    await server.db.users.insert_one({"id": su, "ad": "Ali", "soyad": "Yılmaz", "role": "student"})
    veli = str(uuid.uuid4())        # veli
    await server.db.users.insert_one({"id": veli, "ad": "Veli", "soyad": "Baba", "role": "parent"})
    adm = str(uuid.uuid4())         # admin
    await server.db.users.insert_one({"id": adm, "ad": "Admin", "soyad": "Yön", "role": "admin"})

    HT = {"Authorization": f"Bearer {create_access_token({'sub': tuser})}"}
    HS = {"Authorization": f"Bearer {create_access_token({'sub': su})}"}
    HV = {"Authorization": f"Bearer {create_access_token({'sub': veli})}"}
    HA = {"Authorization": f"Bearer {create_access_token({'sub': adm})}"}

    transport = ASGITransport(app=server.app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # ── GET kendi profil ──
        r = await ac.get("/api/ogretmen/profil", headers=HS)
        check(r.status_code == 403, f"öğrenci /ogretmen/profil 403 (status={r.status_code})")

        r = await ac.get("/api/ogretmen/profil", headers=HT)
        check(r.status_code == 200, f"öğretmen /ogretmen/profil 200 (status={r.status_code})")
        d = r.json()
        check(d.get("email") == "ayse@oba.com", "email profilde görünüyor")
        check(d.get("brans") == "Türkçe", "brans doğru")
        check(isinstance(d.get("bildirim_tercihleri"), dict) and d["bildirim_tercihleri"].get("email") is True,
              "bildirim_tercihleri varsayılanı geldi")
        check(d.get("egitim_gecmisi") == [] and d.get("sertifikalar") == [], "liste alanlar boş varsayılan")

        # ── PUT profil: izinli günceller, korumalı alanlar değişmez ──
        r = await ac.put("/api/ogretmen/profil", headers=HT, json={
            "sehir": "İzmir", "kisa_biyografi": "x" * 600, "deneyim_yili": "7",
            "egitim_gecmisi": [{"okul": "A Üniv.", "bolum": "Türk Dili", "yil": 2015}],
            "bildirim_tercihleri": {"email": False, "push": True, "veli_mesaji": True,
                                    "ogrenci_mesaji": False, "admin_duyuru": True},
            # korumalı alanlar — YOK SAYILMALI
            "email": "hack@x.com", "seviye": "stajyer", "ogretmen_payi": 999,
        })
        check(r.status_code == 200, f"PUT profil 200 (status={r.status_code})")
        d = r.json()
        check(d.get("sehir") == "İzmir", "sehir güncellendi")
        check(len(d.get("kisa_biyografi", "")) == 500, "kısa biyografi 500'e kırpıldı")
        check(d.get("deneyim_yili") == 7, "deneyim_yili int'e çevrildi")
        check(len(d.get("egitim_gecmisi", [])) == 1, "eğitim geçmişi eklendi")
        check(d.get("email") == "ayse@oba.com", "email KORUNDU (değişmedi)")
        check(d.get("seviye") == "uzman", "seviye KORUNDU (değişmedi)")
        check(d["bildirim_tercihleri"].get("email") is False, "bildirim tercihi güncellendi")

        # users senkron: ad/telefon PUT'ta yoktu → değişmemeli; sehir teachers'ta
        trec_doc = await server.db.teachers.find_one({"id": trec})
        check(trec_doc.get("seviye") == "uzman", "teachers.seviye DB'de korundu")
        check("email" not in trec_doc or trec_doc.get("email") != "hack@x.com", "teachers'a email sızmadı")

        # ── Admin görünürlük ──
        r = await ac.get("/api/admin/profil-gorunurluk", headers=HS)
        check(r.status_code == 403, f"öğretmen görünürlük GET 403 (status={r.status_code})")
        r = await ac.get("/api/admin/profil-gorunurluk", headers=HA)
        check(r.status_code == 200 and "ayarlar" in r.json(), "admin görünürlük GET 200")

        # sehir'i 'admin' yap
        r = await ac.put("/api/admin/profil-gorunurluk", headers=HA,
                         json={"ayarlar": {"sehir": "admin"}})
        check(r.status_code == 200 and r.json()["ayarlar"]["sehir"] == "admin", "sehir görünürlüğü 'admin' yapıldı")
        check(r.json()["ayarlar"]["bildirim_tercihleri"] == "sadece_kendisi",
              "bildirim_tercihleri her zaman sadece_kendisi")

        # ── Public profil filtresi ──
        # sehir=admin → veli GÖREMEZ, admin GÖRÜR
        r = await ac.get(f"/api/ogretmen/{trec}/profil-public", headers=HV)
        check(r.status_code == 200, "veli public 200")
        dv = r.json()
        check("sehir" not in dv, "veli sehir'i GÖREMEZ (admin seviyesi)")
        check("bildirim_tercihleri" not in dv, "bildirim_tercihleri public'te YOK")
        check(dv.get("ad") == "Ayşe", "veli ad'ı görüyor (kimlik)")
        check("email" not in dv, "public'te email YOK")

        r = await ac.get(f"/api/ogretmen/{trec}/profil-public", headers=HA)
        da = r.json()
        check("sehir" in da, "admin sehir'i GÖRÜR")

        # kisa_biyografi 'herkes' → öğrenci de görür
        r = await ac.get(f"/api/ogretmen/{trec}/profil-public", headers=HS)
        ds = r.json()
        check("kisa_biyografi" in ds, "öğrenci 'herkes' alanını (kısa biyografi) görür")
        check("sehir" not in ds, "öğrenci sehir'i görmez")

        # ── Foto yükleme ──
        r = await ac.post("/api/ogretmen/profil/foto", headers=HT,
                          files={"dosya": ("t.png", _png_bytes(), "image/png")})
        check(r.status_code == 200, f"foto yükleme 200 (status={r.status_code})")
        check(r.json().get("profil_fotografi_url", "").endswith(f"{trec}.jpg"),
              "foto URL'i döndü")
        # yanlış tip → 400
        r = await ac.post("/api/ogretmen/profil/foto", headers=HT,
                          files={"dosya": ("t.txt", b"merhaba", "text/plain")})
        check(r.status_code == 400, f"geçersiz tip 400 (status={r.status_code})")


if __name__ == "__main__":
    print("=" * 56)
    print("OGRETMEN PROFIL SMOKE TEST")
    print("=" * 56)
    asyncio.run(run())
    print("\n" + "=" * 56)
    print(f"SONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    print("=" * 56)
    sys.exit(0 if _kalan == 0 else 1)
