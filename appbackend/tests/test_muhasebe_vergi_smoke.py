"""Muhasebe vergi + kur-kaydı bazlı satır smoke testi (yeni özellikler).

Doğrular:
  - Vergi ayarı (PUT /ayarlar/vergi_ayarlari, admin) + oran GET.
  - Tahsilatta brüt/vergi/net; oran DEĞİŞİNCE eski kayıt kendi oranıyla kalır.
  - /muhasebe/ozet vergi (toplam_vergi / net_tahsilat / kasa_net).
  - Kur-kaydı bazlı satırlar: her kur = satır, FIFO ödenen, tam sütunlar.
  - PATCH /muhasebe/kur-ucreti (tutar → öğrenci beklenen delta).
  - Kur atlama = yeni temiz satır.

İzole test DB (oba_test_muhasebe_vergi). Çalıştırma:
  cd appbackend && PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe tests/test_muhasebe_vergi_smoke.py
"""
import asyncio
import os
import sys

TEST_DB = "oba_test_muhasebe_vergi"
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

    admin_id, acc_id = str(uuid.uuid4()), str(uuid.uuid4())
    await server.db.users.insert_many([
        {"id": admin_id, "ad": "Yon", "soyad": "Etici", "role": "admin"},
        {"id": acc_id, "ad": "Muh", "soyad": "Asebe", "role": "accountant"},
    ])
    H_admin = {"Authorization": f"Bearer {create_access_token({'sub': admin_id})}"}
    H_acc = {"Authorization": f"Bearer {create_access_token({'sub': acc_id})}"}

    tid = str(uuid.uuid4())
    await server.db.teachers.insert_one({"id": tid, "ad": "Zeynep", "soyad": "Hoca",
                                         "yapilmasi_gereken_odeme": 0.0, "yapilan_odeme": 0.0})
    sid = str(uuid.uuid4())
    await server.db.students.insert_one({
        "id": sid, "ad": "Ali", "soyad": "Yilmaz", "sinif": "8-A", "kur": "Kur 1",
        "veli_ad": "Ayse", "veli_soyad": "Yilmaz", "veli_telefon": "5550001122",
        "ogretmen_id": tid, "olusturma_tarihi": "2026-01-01T00:00:00",
        "yapilmasi_gereken_odeme": 0.0, "yapilan_odeme": 0.0, "ogretmene_yapilacak_odeme": 300.0,
    })

    transport = ASGITransport(app=server.app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1) Vergi ayarı
        r = await ac.put("/api/ayarlar/vergi_ayarlari", headers=H_admin, json={"degerler": {"vergi_orani": 15}})
        check(r.status_code == 200, f"vergi oranı 15 ayarlandı ({r.status_code})")
        r = await ac.get("/api/ayarlar/vergi_ayarlari", headers=H_admin)
        check(r.status_code == 200 and r.json().get("degerler", {}).get("vergi_orani") == 15, "vergi oranı 15 döndü")

        # 2) Tahsilat vergi hesabı (oran 15)
        r = await ac.post("/api/payments", headers=H_acc, json={"tip": "ogrenci", "kisi_id": sid, "miktar": 1000})
        p1 = r.json()
        check(r.status_code == 200 and p1.get("vergi") == 150.0 and p1.get("net") == 850.0 and p1.get("vergi_orani") == 15,
              f"tahsilat vergi=150 net=850 oran=15 (vergi={p1.get('vergi')})")

        # Oran 20 → eski kayıt DEĞİŞMEZ, yeni kayıt 20
        await ac.put("/api/ayarlar/vergi_ayarlari", headers=H_admin, json={"degerler": {"vergi_orani": 20}})
        r = await ac.post("/api/payments", headers=H_acc, json={"tip": "ogrenci", "kisi_id": sid, "miktar": 1000})
        p2 = r.json()
        check(p2.get("vergi") == 200.0 and p2.get("vergi_orani") == 20, f"yeni tahsilat oran 20 (vergi={p2.get('vergi')})")
        r = await ac.get("/api/payments", headers=H_acc)
        eski = next((p for p in r.json() if p["id"] == p1["id"]), None)
        check(eski and eski.get("vergi") == 150.0 and eski.get("vergi_orani") == 15,
              "oran değişince ESKİ kayıt kendi oranıyla (vergi 150) kaldı")

        # 3) ozet vergi (bu noktada yalnız sid var: yapilan_odeme=2000)
        r = await ac.get("/api/muhasebe/ozet", headers=H_acc)
        o = r.json()
        check(o.get("vergi", {}).get("toplam_vergi") == 350.0, f"ozet toplam_vergi=350 ({o.get('vergi',{}).get('toplam_vergi')})")
        check(o.get("vergi", {}).get("net_tahsilat") == 1650.0, f"ozet net_tahsilat=1650 ({o.get('vergi',{}).get('net_tahsilat')})")
        check("kasa_net" in o, "ozet kasa_net alanı var")

        # 4) Kur-kaydı bazlı satırlar — ayrı öğrenci (kontrollü ödenen=700)
        sid2 = str(uuid.uuid4())
        await server.db.students.insert_one({
            "id": sid2, "ad": "Veli", "soyad": "Kan", "sinif": "7-B", "kur": "",
            "veli_ad": "Can", "veli_soyad": "Kan", "veli_telefon": "5559998877",
            "ogretmen_id": tid, "olusturma_tarihi": "2026-02-01T00:00:00",
            "yapilmasi_gereken_odeme": 0.0, "yapilan_odeme": 700.0,
        })
        await ac.post(f"/api/muhasebe/ogrenci/{sid2}/kur-ucreti", headers=H_acc,
                      json={"kur_adi": "Kur 1", "tutar": 600, "baslangic_tarihi": "2026-02-01"})
        await ac.post(f"/api/muhasebe/ogrenci/{sid2}/kur-ucreti", headers=H_acc,
                      json={"kur_adi": "Kur 2", "tutar": 400, "baslangic_tarihi": "2026-06-01"})
        r = await ac.get("/api/muhasebe/kisiler", headers=H_acc)
        satirlar = [x for x in r.json().get("ogrenciler", []) if x.get("kisi_id") == sid2]
        check(len(satirlar) == 2, f"öğrenci 2 kur satırı olarak listelendi ({len(satirlar)})")
        s_kur1 = next((x for x in satirlar if x.get("kur") == "Kur 1"), None)
        s_kur2 = next((x for x in satirlar if x.get("kur") == "Kur 2"), None)
        # FIFO: 700 → Kur1 600 (tam, kalan 0), Kur2 100 (kalan 300)
        check(s_kur1 and s_kur1["yapilmasi_gereken_odeme"] == 600 and s_kur1["yapilan_odeme"] == 600 and s_kur1["kalan"] == 0,
              "Kur 1: beklenen 600, FIFO ödenen 600, kalan 0")
        check(s_kur2 and s_kur2["yapilan_odeme"] == 100 and s_kur2["kalan"] == 300,
              "Kur 2: FIFO ödenen 100, kalan 300")
        check(s_kur1 and s_kur1.get("ogretmen_ad") == "Zeynep Hoca" and s_kur1.get("sinif") == "7-B"
              and s_kur1.get("veli_telefon") == "5559998877" and bool(s_kur1.get("kayit_zamani")),
              "kur satırı tam sütunları taşıyor (öğretmen/sınıf/telefon/kayıt zamanı)")

        # 5) Kur PATCH (tutar → öğrenci beklenen delta)
        kur1_id = s_kur1["kur_ucreti_id"]
        r = await ac.patch(f"/api/muhasebe/kur-ucreti/{kur1_id}", headers=H_acc, json={"tutar": 800})
        check(r.status_code == 200 and r.json().get("delta") == 200.0, f"kur tutar 600→800, delta 200 ({r.status_code})")
        s2 = await server.db.students.find_one({"id": sid2})
        check(s2 and s2.get("yapilmasi_gereken_odeme") == 1200.0,
              f"öğrenci beklenen 1000→1200 (delta yansıdı) ({s2.get('yapilmasi_gereken_odeme') if s2 else None})")

        # 6) Kur atlama = yeni temiz satır
        await ac.post(f"/api/muhasebe/ogrenci/{sid2}/kur-ucreti", headers=H_acc, json={"kur_adi": "Kur 3", "tutar": 500})
        r = await ac.get("/api/muhasebe/kisiler", headers=H_acc)
        satir3 = [x for x in r.json().get("ogrenciler", []) if x.get("kisi_id") == sid2]
        check(len(satir3) == 3, f"kur atlama sonrası 3 satır ({len(satir3)})")
        yeni = next((x for x in satir3 if x.get("kur") == "Kur 3"), None)
        check(yeni and yeni["yapilmasi_gereken_odeme"] == 500, "yeni kur satırı temiz (kendi beklenen 500)")

    await server.client.drop_database(TEST_DB)


def main():
    asyncio.run(run())
    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    sys.exit(0 if _kalan == 0 else 1)


if __name__ == "__main__":
    main()
