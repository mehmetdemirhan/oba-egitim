"""Muhasebe + Öğrenci Yönetimi paketi smoke.

Kapsam:
- (1) Öğrenci bazlı vergi oranı → tahsilatta ESAS alınır (global değil), geçmiş korunur.
- (2) Aylık reklam gideri → dashboard nakit akışında 'reklam' + Net'ten düşülür.
- (4) 'Eğitime devam etmedi' → aktif listeden/dashboard sayımından düşer; durum=ayrildi listelenir.
- (6) admin/koordinatör başka öğretmenin öğrencisi için kur atlarsa audit'e vekaleten işareti.

İzole test DB. cd appbackend && .venv/Scripts/python.exe tests/test_muhasebe_ogrenci_paket_smoke.py
"""
import asyncio
import os
import sys
import uuid

TEST_DB = "oba_test_muh_ogr_paket"
os.environ["MONGO_URL"] = os.environ.get("MONGO_URL_TEST", "mongodb://localhost:27017")
os.environ["DB_NAME"] = TEST_DB
os.environ.setdefault("SECRET_KEY", "test-secret-key")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_gecen = 0
_kalan = 0


def check(kosul, mesaj):
    global _gecen, _kalan
    if kosul:
        _gecen += 1; print(f"  [GECTI] {mesaj}")
    else:
        _kalan += 1; print(f"  [KALDI] {mesaj}")


async def run():
    import server
    from core.auth import create_access_token
    from core.db import db
    from httpx import AsyncClient, ASGITransport

    await server.client.drop_database(TEST_DB)
    adm = str(uuid.uuid4()); tid = str(uuid.uuid4()); sid = str(uuid.uuid4()); sid2 = str(uuid.uuid4())
    await db.users.insert_one({"id": adm, "role": "admin", "ad": "Yön", "soyad": "E"})
    await db.teachers.insert_one({"id": tid, "ad": "Öğ", "soyad": "T"})
    await db.students.insert_one({"id": sid, "ad": "Ali", "soyad": "K", "ogretmen_id": tid, "sinif": "3",
                                  "veli_ad": "V", "veli_soyad": "K", "veli_telefon": "5551112233", "kur": "Kur 1", "aldigi_egitim": "Hızlı Okuma",
                                  "yapilmasi_gereken_odeme": 1000, "yapilan_odeme": 0})
    await db.students.insert_one({"id": sid2, "ad": "Ece", "soyad": "M", "ogretmen_id": tid, "sinif": "3",
                                  "veli_ad": "V", "veli_soyad": "M", "veli_telefon": "5552223344", "kur": "Kur 1", "aldigi_egitim": "Hızlı Okuma",
                                  "yapilmasi_gereken_odeme": 1000, "yapilan_odeme": 0})
    H = {"Authorization": f"Bearer {create_access_token({'sub': adm})}"}

    async with AsyncClient(transport=ASGITransport(app=server.app), base_url="http://test") as ac:
        # (1) Öğrenci bazlı vergi oranı = 5 (global 15 varsayılan)
        r = await ac.patch(f"/api/muhasebe/kisi/ogrenci/{sid}", headers=H, json={"vergi_orani": 5})
        check(r.status_code == 200, "öğrenci vergi oranı %5 atandı")
        # Tahsilat → vergi öğrenci oranından (1000 * %5 = 50), net 950
        r = await ac.post("/api/payments", headers=H, json={"tip": "ogrenci", "kisi_id": sid, "miktar": 1000})
        pj = r.json()
        check(r.status_code == 200 and abs(pj.get("vergi", 0) - 50) < 0.01,
              f"tahsilat vergisi öğrenci oranından (50 beklenir, {pj.get('vergi')})")
        check(abs(pj.get("net", 0) - 950) < 0.01, f"net 950 ({pj.get('net')})")
        # global oranlı ikinci öğrenci → vergi 150
        r = await ac.post("/api/payments", headers=H, json={"tip": "ogrenci", "kisi_id": sid2, "miktar": 1000})
        check(abs(r.json().get("vergi", 0) - 150) < 0.01, f"global oranlı öğrenci vergisi 150 ({r.json().get('vergi')})")

        # (2) Reklam gideri
        ay = "2026-07"
        r = await ac.put("/api/muhasebe/reklam-gideri", headers=H, json={"ay": ay, "tutar": 3000})
        check(r.status_code == 200, "reklam gideri kaydedildi")
        r = await ac.get("/api/dashboard/analitik", headers=H)
        nk = {n["ay"]: n for n in r.json().get("nakit_akisi", [])}
        check(ay in nk and nk[ay].get("reklam") == 3000, f"nakit akışında reklam=3000 ({nk.get(ay, {}).get('reklam')})")
        # Net reklam'ı düşer: tahsilat(2000) - vergi(200) - ogr_odeme(0) - reklam(3000) = -1200
        check(abs(nk[ay]["net"] - (nk[ay]["tahsilat"] - nk[ay]["vergi"] - nk[ay]["ogretmen_odeme"] - 3000)) < 0.01,
              f"Net = Tahsilat−Vergi−Öğr−Reklam ({nk[ay]['net']})")

        # (4) Eğitime devam etmedi
        r = await ac.get("/api/dashboard", headers=H)
        aktif_once = r.json().get("toplam_ogrenci")
        r = await ac.post(f"/api/students/{sid2}/ayril", headers=H, json={"kategori": "Fiyat", "neden": "Pahalı"})
        check(r.status_code == 200, "öğrenci 'eğitime devam etmedi' işaretlendi")
        r = await ac.get("/api/students", headers=H)
        check(not any(s.get("id") == sid2 for s in r.json()), "ayrılan öğrenci aktif listede yok")
        r = await ac.get("/api/students?durum=ayrildi", headers=H)
        check(any(s.get("id") == sid2 for s in r.json()), "ayrılan öğrenci 'durum=ayrildi' listesinde")
        r = await ac.get("/api/dashboard", headers=H)
        check(r.json().get("toplam_ogrenci") == aktif_once - 1, f"aktif öğrenci sayımı 1 azaldı ({aktif_once}→{r.json().get('toplam_ogrenci')})")
        # geri al
        r = await ac.post(f"/api/students/{sid2}/ayril-geri-al", headers=H)
        check(r.status_code == 200, "ayrılma geri alındı")

        # (6) Vekaleten kur atlama → audit vekaleten işareti
        r = await ac.post(f"/api/students/{sid}/kur-gecis", headers=H, json={})
        check(r.status_code == 200, "admin vekaleten kur atladı")
        log = await db.islem_log.find_one({"islem": "kur_gecis", "hedef_id": sid})
        check(log and (log.get("ekstra") or {}).get("vekaleten_ogretmen_id") == tid,
              f"audit'te vekaleten_ogretmen_id işareti var ({(log or {}).get('ekstra')})")

    await server.client.drop_database(TEST_DB)


def main():
    asyncio.run(run())
    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    sys.exit(0 if _kalan == 0 else 1)


if __name__ == "__main__":
    main()
