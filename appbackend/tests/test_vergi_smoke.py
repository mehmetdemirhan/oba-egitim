"""Vergi (tahsilat vergisi) akışı smoke testi — Task 15.

Doğrular: POST /payments öğrenci ödemesine brüt/vergi/net'i tahsilat anındaki
orandan SABİTLER; öğretmen ödemesinde vergi yok; oran değişince eski kayıt kendi
snapshot'ını korur, yeni kayıt yeni oranı alır; PUT /payments miktarı değişince
vergi/net snapshot oranla yeniden hesaplanır; /muhasebe/ozet vergi toplamı
(explicit + orandan türetilen), net tahsilat ve net kasa'yı doğru hesaplar.
İzole DB (oba_test_vergi). Gerçek DB'ye dokunmaz.
"""
import asyncio
import os
import sys

TEST_DB = "oba_test_vergi"
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
    acc_id = str(uuid.uuid4())
    await server.db.users.insert_many([
        {"id": admin_id, "ad": "Yön", "soyad": "Etici", "role": "admin"},
        {"id": acc_id, "ad": "Muh", "soyad": "Asebe", "role": "accountant"},
    ])
    sid = str(uuid.uuid4()); tid = str(uuid.uuid4())
    await server.db.students.insert_one(
        {"id": sid, "ad": "Ali", "soyad": "Yılmaz", "veli_ad": "Ayşe", "veli_soyad": "Yılmaz",
         "veli_telefon": "5550001122", "yapilmasi_gereken_odeme": 5000.0, "yapilan_odeme": 0.0,
         "ogretmene_yapilacak_odeme": 0.0})
    await server.db.teachers.insert_one(
        {"id": tid, "ad": "Öğ", "soyad": "Retmen", "yapilmasi_gereken_odeme": 500.0, "yapilan_odeme": 0.0})
    # Vergi %15
    await server.db.sistem_ayarlari.insert_one({"tip": "vergi_ayarlari", "degerler": {"vergi_orani": 15}})

    H_admin = {"Authorization": f"Bearer {create_access_token({'sub': admin_id})}"}
    H_acc = {"Authorization": f"Bearer {create_access_token({'sub': acc_id})}"}

    transport = ASGITransport(app=server.app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1) Öğrenci tahsilatı → vergi %15 sabitlenir
        r = await ac.post("/api/payments", headers=H_acc, json={"tip": "ogrenci", "kisi_id": sid, "miktar": 1000})
        check(r.status_code == 200, f"öğrenci ödemesi oluştu ({r.status_code})")
        p1 = r.json(); p1_id = p1["id"]
        check(p1.get("brut") == 1000 and p1.get("vergi_orani") == 15, "brüt=1000, oran=15 sabitlendi")
        check(p1.get("vergi") == 150 and p1.get("net") == 850, f"vergi=150, net=850 ({p1.get('vergi')}/{p1.get('net')})")

        # 2) Öğretmen ödemesinde vergi YOK
        r = await ac.post("/api/payments", headers=H_acc, json={"tip": "ogretmen", "kisi_id": tid, "miktar": 200})
        check(r.status_code == 200 and r.json().get("vergi") is None, "öğretmen ödemesinde vergi yok")

        # 3) ozet: tahsil 1000, vergi 150, net tahsilat 850, net kasa 650
        o = (await ac.get("/api/muhasebe/ozet", headers=H_acc)).json()
        check(o["vergi"]["oran"] == 15, f"ozet oran 15 ({o['vergi']['oran']})")
        check(o["vergi"]["toplam_vergi"] == 150, f"ozet toplam vergi 150 ({o['vergi']['toplam_vergi']})")
        check(o["vergi"]["brut_tahsilat"] == 1000 and o["vergi"]["net_tahsilat"] == 850, "ozet brüt=1000, net tahsilat=850")
        check(o["kasa_net"] == 650, f"net kasa = 850 - 200(öğretmen) = 650 ({o['kasa_net']})")

        # 4) Oran %20'ye çıkar → yeni tahsilat 20, eski kayıt 15 snapshot'ını korur
        r = await ac.put("/api/ayarlar/vergi_ayarlari", headers=H_admin, json={"degerler": {"vergi_orani": 20}})
        check(r.status_code == 200, f"admin vergi oranını 20 yaptı ({r.status_code})")
        r = await ac.post("/api/payments", headers=H_acc, json={"tip": "ogrenci", "kisi_id": sid, "miktar": 1000})
        p2 = r.json()
        check(p2.get("vergi_orani") == 20 and p2.get("vergi") == 200, f"yeni kayıt %20 → vergi 200 ({p2.get('vergi')})")
        eski = await server.db.payments.find_one({"id": p1_id})
        check(eski.get("vergi_orani") == 15 and eski.get("vergi") == 150, "eski kayıt %15 snapshot'ını korudu")

        # 5) ozet: tahsil 2000, vergi 150+200=350, oran güncel 20
        o = (await ac.get("/api/muhasebe/ozet", headers=H_acc)).json()
        check(o["vergi"]["oran"] == 20, "ozet güncel oran 20")
        check(o["vergi"]["toplam_vergi"] == 350, f"ozet toplam vergi 150+200=350 ({o['vergi']['toplam_vergi']})")
        check(o["vergi"]["net_tahsilat"] == 1650, f"net tahsilat 2000-350=1650 ({o['vergi']['net_tahsilat']})")

        # 6) Vergi alanı OLMAYAN kayıt → ozet orandan TÜRETİR (500*20/100=100)
        await server.db.payments.insert_one(
            {"id": str(uuid.uuid4()), "tip": "ogrenci", "kisi_id": sid, "miktar": 500})
        await server.db.students.update_one({"id": sid}, {"$inc": {"yapilan_odeme": 500}})
        o = (await ac.get("/api/muhasebe/ozet", headers=H_acc)).json()
        check(o["vergi"]["toplam_vergi"] == 450, f"vergisiz kayıt orandan türetildi 350+100=450 ({o['vergi']['toplam_vergi']})")

        # 7) PUT miktar değişince vergi/net snapshot oranla (15) yeniden hesaplanır
        r = await ac.put(f"/api/payments/{p1_id}", headers=H_acc, json={"miktar": 2000})
        check(r.status_code == 200, f"ödeme miktarı güncellendi ({r.status_code})")
        guncel = await server.db.payments.find_one({"id": p1_id})
        check(guncel.get("vergi") == 300 and guncel.get("net") == 1700,
              f"miktar 2000 → vergi 2000*15%=300, net 1700 ({guncel.get('vergi')}/{guncel.get('net')})")

    await server.client.drop_database(TEST_DB)


if __name__ == "__main__":
    asyncio.run(run())
    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    sys.exit(1 if _kalan else 0)
