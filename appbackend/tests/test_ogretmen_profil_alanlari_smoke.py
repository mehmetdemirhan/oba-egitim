"""Öğretmen opsiyonel profil alanları (il/ilçe, kargo adresi, mezuniyet) smoke testi.

Doğrular:
  1) Admin POST /teachers ile yeni alanları kaydeder; GET /teachers/{id} döndürür.
  2) PUT /teachers/{id} alanları günceller.
  3) Öğretmen kendi profilinde (PUT/GET /ogretmen/profil) alanları düzenler+görür.
  4) GÖRÜNÜRLÜK: kargo_adresi + mezuniyet (universite/fakulte/bolum) öğretmenin
     profil-public ucundan öğrenci/veliye SIZMAZ.

    cd appbackend
    PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe tests/test_ogretmen_profil_alanlari_smoke.py
"""
import asyncio
import os
import sys

TEST_DB = "oba_test_ogretmen_profil_alanlari"
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
    import server
    from httpx import AsyncClient, ASGITransport

    db = server.db
    await server.client.drop_database(TEST_DB)

    await db.users.insert_one({"id": "adm", "role": "admin", "ad": "Ad", "soyad": "Min"})
    await db.users.insert_one({"id": "t1", "role": "teacher", "ad": "Öğ", "soyad": "Bir", "email": "t1@x.com"})
    await db.users.insert_one({"id": "veli1", "role": "parent", "ad": "Ve", "soyad": "Li"})
    await db.users.insert_one({"id": "ogr1", "role": "student", "ad": "Öğ", "soyad": "Renci"})
    # Self-profil + görünürlük için teacher dokümanı (id = user id → _ogretmen_id)
    await db.teachers.insert_one({"id": "t1", "ad": "Öğ", "soyad": "Bir", "brans": "Türkçe", "seviye": "yeni"})

    def H(uid):
        return {"Authorization": f"Bearer {server.create_access_token({'sub': uid})}"}

    async with AsyncClient(transport=ASGITransport(app=server.app), base_url="http://test") as ac:
        # 1) POST /teachers — yeni alanlarla oluştur
        r = await ac.post("/api/teachers", headers=H("adm"), json={
            "ad": "Ayşe", "soyad": "Yıl", "brans": "Matematik", "telefon": "555", "seviye": "yeni",
            "il": "Ankara", "ilce": "Çankaya", "kargo_adresi": "Kızılay No:1",
            "universite": "ODTÜ", "fakulte": "Eğitim", "bolum": "Matematik Öğr.",
        })
        check(r.status_code == 200, f"POST /teachers 200 ({r.status_code})")
        tid = r.json().get("id")
        r = await ac.get(f"/api/teachers/{tid}", headers=H("adm"))
        j = r.json()
        check(j.get("il") == "Ankara" and j.get("ilce") == "Çankaya", "il/ilçe kaydedildi+döndü")
        check(j.get("kargo_adresi") == "Kızılay No:1", "kargo_adresi kaydedildi")
        check(j.get("universite") == "ODTÜ" and j.get("bolum") == "Matematik Öğr.", "mezuniyet kaydedildi")

        # 2) PUT /teachers/{id} — güncelle
        r = await ac.put(f"/api/teachers/{tid}", headers=H("adm"), json={"il": "İstanbul", "fakulte": "Fen"})
        check(r.status_code == 200, "PUT /teachers 200")
        j = (await ac.get(f"/api/teachers/{tid}", headers=H("adm"))).json()
        check(j.get("il") == "İstanbul" and j.get("fakulte") == "Fen", "PUT alanları güncelledi")

        # 3) Öğretmen kendi profili — PUT + GET round-trip
        r = await ac.put("/api/ogretmen/profil", headers=H("t1"), json={
            "il": "İzmir", "ilce": "Konak", "kargo_adresi": "Ev adresi",
            "universite": "Ege", "fakulte": "Edebiyat", "bolum": "Türk Dili",
        })
        check(r.status_code == 200, f"PUT /ogretmen/profil 200 ({r.status_code})")
        p = (await ac.get("/api/ogretmen/profil", headers=H("t1"))).json()
        check(p.get("il") == "İzmir" and p.get("kargo_adresi") == "Ev adresi", "self-profil il+kargo döndü")
        check(p.get("universite") == "Ege" and p.get("bolum") == "Türk Dili", "self-profil mezuniyet döndü")

        # 4) GÖRÜNÜRLÜK — profil-public'te kargo + mezuniyet ASLA yok (veli + öğrenci)
        for rol, uid in [("veli", "veli1"), ("öğrenci", "ogr1")]:
            pub = (await ac.get("/api/ogretmen/t1/profil-public", headers=H(uid))).json()
            gizli_var = any(k in pub for k in ("kargo_adresi", "universite", "fakulte", "bolum"))
            check(not gizli_var, f"{rol}: kargo+mezuniyet profil-public'te YOK")
            check(pub.get("ad") == "Öğ", f"{rol}: kimlik (ad) yine de görünür")

    await server.client.drop_database(TEST_DB)


if __name__ == "__main__":
    asyncio.run(run())
    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    sys.exit(1 if _kalan else 0)
