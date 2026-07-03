"""FAZ 3 rozet CRUD API smoke testi.

Doğrulananlar: /rozet/* CRUD, auth (öğretmen 403), duplicate 409, manuel ver +
bildirim, geri-al, kazananlar, sil (kazananları koru/temizle), import/export,
istatistik. Eski /rozetler/tanim geriye dönük uyumlu.

    cd appbackend
    .venv/Scripts/python.exe tests/test_rozet_crud_smoke.py
"""
import asyncio
import os
import sys
import uuid
from datetime import datetime

TEST_DB = "oba_test_rozet_crud_smoke"
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
    from core.db import ensure_indexes
    from httpx import AsyncClient, ASGITransport

    await server.client.drop_database(TEST_DB)
    await ensure_indexes()

    adm = str(uuid.uuid4())
    tea = str(uuid.uuid4())
    stu = str(uuid.uuid4())
    await server.db.users.insert_one({"id": adm, "ad": "Admin", "soyad": "Y", "role": "admin"})
    await server.db.users.insert_one({"id": tea, "ad": "Ayşe", "soyad": "Ö", "role": "teacher"})
    await server.db.users.insert_one({"id": stu, "ad": "Ali", "soyad": "Y", "role": "student"})
    HA = {"Authorization": f"Bearer {create_access_token({'sub': adm})}"}
    HT = {"Authorization": f"Bearer {create_access_token({'sub': tea})}"}

    transport = ASGITransport(app=server.app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # ── Public: tanım listesi (fallback koddan) ──
        r = await ac.get("/api/rozet/tanim")
        check(r.status_code == 200 and isinstance(r.json(), list) and len(r.json()) > 0,
              f"GET /rozet/tanim liste döndü (n={len(r.json()) if r.status_code==200 else '?'})")
        r = await ac.get("/api/rozet/tanim?rol=student")
        check(r.status_code == 200 and all(x["rol"] == "student" for x in r.json()), "rol filtresi çalışıyor")

        # Eski endpoint geriye dönük
        r = await ac.get("/api/rozetler/tanim")
        check(r.status_code == 200 and "ogretmen" in r.json() and "ogrenci" in r.json(),
              "eski /rozetler/tanim hâlâ çalışıyor (backward compat)")

        # ── Oluşturma (admin) ──
        yeni = {"kod": "test_rozet", "rol": "student", "ad": "Test Rozeti", "ikon": "🧪",
                "kategori": "test", "seviye": "gumus", "odul_puan": 7,
                "kosul": {"metrik": "okuma_dakikasi", "operator": ">=", "esik": 30}}
        r = await ac.post("/api/rozet/tanim", json=yeni, headers=HA)
        check(r.status_code == 200 and r.json()["kod"] == "test_rozet", f"admin rozet oluşturdu (status={r.status_code})")

        # Öğretmen oluşturamaz → 403
        r = await ac.post("/api/rozet/tanim", json={**yeni, "kod": "yasak"}, headers=HT)
        check(r.status_code == 403, f"öğretmen POST /rozet/tanim → 403 (status={r.status_code})")

        # Duplicate → 409
        r = await ac.post("/api/rozet/tanim", json=yeni, headers=HA)
        check(r.status_code == 409, f"aynı (rol,kod) tekrar → 409 (status={r.status_code})")

        # ── Getir + Güncelle ──
        r = await ac.get("/api/rozet/student/test_rozet")
        check(r.status_code == 200 and r.json()["odul_puan"] == 7, "GET /rozet/student/test_rozet doğru")
        r = await ac.put("/api/rozet/student/test_rozet", json={"odul_puan": 12, "seviye": "altin"}, headers=HA)
        check(r.status_code == 200 and r.json()["odul_puan"] == 12 and r.json()["seviye"] == "altin",
              "PUT güncelleme uygulandı")

        # ── Manuel ver + bildirim ──
        r = await ac.post("/api/rozet/student/test_rozet/ver", json={"user_id": stu}, headers=HA)
        check(r.status_code == 200 and r.json()["ok"], "manuel ver 200")
        bil = await server.db.bildirimler.count_documents({"alici_id": stu, "tur": "rozet_kazandi"})
        check(bil == 1, f"manuel ver bildirim gönderdi ({bil})")
        # tekrar ver → zaten vardı
        r = await ac.post("/api/rozet/student/test_rozet/ver", json={"user_id": stu}, headers=HA)
        check(r.status_code == 200 and r.json().get("zaten_vardi"), "ikinci manuel ver 'zaten_vardi'")

        # ── Kazananlar ──
        r = await ac.get("/api/rozet/student/test_rozet/kazananlar", headers=HA)
        check(r.status_code == 200 and r.json()["toplam"] == 1 and r.json()["kazananlar"][0]["kullanici_id"] == stu,
              "kazananlar listesi doğru")

        # ── İstatistik ──
        r = await ac.get("/api/rozet/istatistik", headers=HA)
        check(r.status_code == 200 and r.json()["toplam_kazanim"] >= 1, "istatistik toplam_kazanim >= 1")

        # ── Export / Import ──
        r = await ac.get("/api/rozet/export", headers=HA)
        check(r.status_code == 200 and len(r.json()["rozetler"]) >= 1, "export çalışıyor")
        imp = {"rozetler": [{"kod": "test_rozet", "rol": "student", "odul_puan": 3},
                            {"kod": "yeni_import", "rol": "teacher", "ad": "İçe Aktarılan", "odul_puan": 4}]}
        r = await ac.post("/api/rozet/import", json=imp, headers=HA)
        check(r.status_code == 200 and r.json()["eklenen"] == 1 and r.json()["guncellenen"] == 1,
              f"import 1 ekledi 1 güncelledi (gelen {r.json()})")

        # ── Geri-al ──
        r = await ac.post("/api/rozet/student/test_rozet/geri-al", json={"user_id": stu}, headers=HA)
        check(r.status_code == 200 and r.json()["silindi"], "geri-al çalıştı")

        # ── Sil (kazananları koru=False) ──
        await server.db.kazanilan_rozetler.insert_one(
            {"id": str(uuid.uuid4()), "kullanici_id": stu, "rozet_kodu": "test_rozet", "kazanma_tarihi": datetime.utcnow().isoformat()})
        r = await ac.request("DELETE", "/api/rozet/student/test_rozet", json={"kazananlari_koru": False}, headers=HA)
        check(r.status_code == 200 and r.json()["silinen_kazanim"] == 1, f"sil + kazanım temizle (gelen {r.json()})")
        r = await ac.get("/api/rozet/student/test_rozet")
        check(r.status_code == 404, "silinen rozet 404")

    await server.client.drop_database(TEST_DB)
    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    return _kalan == 0


if __name__ == "__main__":
    ok = asyncio.run(run())
    sys.exit(0 if ok else 1)
