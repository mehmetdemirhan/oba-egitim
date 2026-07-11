"""Kur>1 = 'üst kur/kur atlama' sınıflandırması + öğretmen XP smoke.

Doğrular:
  - Doğrudan kur>1 kayıt → öğretmene kur-atlama XP kaydı (kaynak=ust_kur_kayit).
  - kur=1 kayıt → kur atlama kaydı YOK (yeni kayıt).
  - Aynı öğrenci+kur → XP MÜKERRER işlenmez (idempotent).
  - "Yeni Kura Geçir" (kur_gecis) → kur_atlamalari + XP.
  - Öğretmen XP kırılımı kur bileşeni artıyor (türetilmiş, +7/atlama).
  - Dashboard: yeni_kayit yalnız kur==1; kur>1 → bu_ay_ust_kur.
  - Migration: geriye dönük kur>1 → tek kayıt (kaynak=migrasyon), idempotent.

İzole DB (oba_test_ust_kur_xp). Çalıştırma:
  cd appbackend && PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe tests/test_ust_kur_xp_smoke.py
"""
import asyncio
import os
import sys

TEST_DB = "oba_test_ust_kur_xp"
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


def _ogr(kur, ogretmen_id):
    return {"ad": "Test", "soyad": "Ogr", "sinif": "8", "veli_ad": "V", "veli_soyad": "K",
            "veli_telefon": "5550000000", "aldigi_egitim": "genel", "kur": kur, "ogretmen_id": ogretmen_id}


async def run():
    import uuid
    import server
    from core.auth import create_access_token
    from httpx import AsyncClient, ASGITransport

    await server.client.drop_database(TEST_DB)

    admin_id, tuser_id = str(uuid.uuid4()), str(uuid.uuid4())
    tid = str(uuid.uuid4())  # teachers.id
    await server.db.users.insert_many([
        {"id": admin_id, "ad": "Yon", "soyad": "Etici", "role": "admin"},
        {"id": tuser_id, "ad": "Zeynep", "soyad": "Hoca", "role": "teacher", "linked_id": tid},
    ])
    await server.db.teachers.insert_one({"id": tid, "ad": "Zeynep", "soyad": "Hoca"})
    H_admin = {"Authorization": f"Bearer {create_access_token({'sub': admin_id})}"}

    transport = ASGITransport(app=server.app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # ── A) Doğrudan kur=3 kayıt → XP ──
        r = await ac.post("/api/students", headers=H_admin, json=_ogr("3", tid))
        sid3 = r.json()["id"]
        recs = await server.db.kur_atlamalari.find({"ogrenci_id": sid3}).to_list(length=None)
        check(r.status_code == 200 and len(recs) == 1 and recs[0].get("kaynak") == "ust_kur_kayit"
              and recs[0].get("ogretmen_id") == tid and recs[0].get("yeni_kur_no") == 3,
              f"kur=3 kayıt → 1 kur_atlamalari (ust_kur_kayit, tid, kur3) ({len(recs)})")

        # kur=1 kayıt → kayıt YOK
        r = await ac.post("/api/students", headers=H_admin, json=_ogr("1", tid))
        sid1 = r.json()["id"]
        recs1 = await server.db.kur_atlamalari.find({"ogrenci_id": sid1}).to_list(length=None)
        check(len(recs1) == 0, f"kur=1 kayıt → kur atlama kaydı YOK (yeni kayıt) ({len(recs1)})")

        # XP kırılımı kur == 7
        r = await ac.get(f"/api/teachers/{tid}/detay-ozet", headers=H_admin)
        kur_xp = (r.json().get("gelisim", {}).get("kirilim", {}) or {}).get("kur")
        check(kur_xp == 7, f"öğretmen kur XP = 7 (1 atlama × 7) ({kur_xp})")

        # ── B) İdempotent: aynı öğrenci+kur ──
        from modules.crm import kur_atlama_xp_kaydet
        s3doc = await server.db.students.find_one({"id": sid3})
        yeniden = await kur_atlama_xp_kaydet(s3doc, "3", kaynak="tekrar")
        recs = await server.db.kur_atlamalari.find({"ogrenci_id": sid3}).to_list(length=None)
        check(yeniden is False and len(recs) == 1, f"aynı öğrenci+kur → mükerrer XP yok (idempotent) ({len(recs)})")

        # ── C) kur_gecis (kur=1 → 2) → XP ──
        r = await ac.post(f"/api/students/{sid1}/kur-gecis", headers=H_admin, json={})
        recsG = await server.db.kur_atlamalari.find({"ogrenci_id": sid1}).to_list(length=None)
        s1doc = await server.db.students.find_one({"id": sid1})
        check(r.status_code == 200 and len(recsG) == 1 and recsG[0].get("kaynak") == "kur_gecis"
              and recsG[0].get("yeni_kur_no") == 2 and s1doc.get("kur") == "2",
              f"kur_gecis → kur_atlamalari (kur_gecis, kur2) + öğrenci kur=2 ({r.status_code})")
        r = await ac.get(f"/api/teachers/{tid}/detay-ozet", headers=H_admin)
        kur_xp2 = (r.json().get("gelisim", {}).get("kirilim", {}) or {}).get("kur")
        check(kur_xp2 == 14, f"öğretmen kur XP = 14 (2 atlama × 7) ({kur_xp2})")

        # ── D) Dashboard: yeni_kayit yalnız kur==1 ──
        r = await ac.get("/api/dashboard")
        d = r.json()
        # bu ay: sid3(kur3), sid1(gecis→kur2) → ikisi de kur>1 (üst kur); yeni_kayit=0
        check(d.get("bu_ay_yeni_kayit") == 0 and d.get("bu_ay_ust_kur") == 2,
              f"dashboard: yeni_kayit=0, ust_kur=2 ({d.get('bu_ay_yeni_kayit')},{d.get('bu_ay_ust_kur')})")
        await ac.post("/api/students", headers=H_admin, json=_ogr("1", tid))  # gerçek yeni kayıt
        r = await ac.get("/api/dashboard")
        d2 = r.json()
        check(d2.get("bu_ay_yeni_kayit") == 1 and d2.get("bu_ay_ust_kur") == 2,
              f"yeni kur=1 kayıt → yeni_kayit=1 (ust_kur sabit 2) ({d2.get('bu_ay_yeni_kayit')},{d2.get('bu_ay_ust_kur')})")

        # ── E) Migration: geriye dönük kur>1 (idempotent) ──
        sidL = str(uuid.uuid4())
        await server.db.students.insert_one({
            "id": sidL, "ad": "Eski", "soyad": "Kayit", "sinif": "7", "kur": "4",
            "ogretmen_id": tid, "olusturma_tarihi": "2026-03-01T00:00:00",
            "yapilmasi_gereken_odeme": 0.0, "yapilan_odeme": 0.0,
        })
        import importlib.util
        mig_yol = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts", "migrate_ust_kur_xp.py")
        spec = importlib.util.spec_from_file_location("migrate_ust_kur_xp", mig_yol)
        mig = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mig)
        await mig.main()
        recsL = await server.db.kur_atlamalari.find({"ogrenci_id": sidL}).to_list(length=None)
        check(len(recsL) == 1 and recsL[0].get("kaynak") == "migrasyon" and recsL[0].get("yeni_kur_no") == 4
              and recsL[0].get("tarih") == "2026-03-01T00:00:00",
              f"migration: legacy kur=4 → 1 kayıt (migrasyon, tarih=kayıt) ({len(recsL)})")
        recs3 = await server.db.kur_atlamalari.find({"ogrenci_id": sid3}).to_list(length=None)
        check(len(recs3) == 1, f"migration mevcut kaydı ÇOĞALTMADI (idempotent) ({len(recs3)})")
        await mig.main()  # ikinci kez
        recsL2 = await server.db.kur_atlamalari.find({"ogrenci_id": sidL}).to_list(length=None)
        check(len(recsL2) == 1, f"migration ikinci çalıştırma → mükerrer YOK ({len(recsL2)})")

    await server.client.drop_database(TEST_DB)


def main():
    asyncio.run(run())
    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    sys.exit(0 if _kalan == 0 else 1)


if __name__ == "__main__":
    main()
