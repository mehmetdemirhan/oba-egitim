"""Ders Programı modülü smoke testi.

Seri oluştur → program (planlı hesaplama) → oturum taşı (materyalizasyon) →
yoklama → çakışma (409) → yetki (403) → değişiklik geçmişi akışını doğrular.
İzole test DB'sine karşı çalışır.

    cd appbackend
    .venv/Scripts/python.exe tests/test_ders_programi_smoke.py
"""
import asyncio
import os
import sys
import uuid
from datetime import date, timedelta

TEST_DB = "oba_test_ders_programi_smoke"
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

    t1 = str(uuid.uuid4())
    t2 = str(uuid.uuid4())
    adm = str(uuid.uuid4())
    ogr = str(uuid.uuid4())
    veli = str(uuid.uuid4())
    await server.db.users.insert_one({"id": t1, "ad": "Ali", "soyad": "Öğretmen", "role": "teacher"})
    await server.db.users.insert_one({"id": t2, "ad": "Veli", "soyad": "Öğretmen2", "role": "teacher"})
    await server.db.users.insert_one({"id": adm, "ad": "Admin", "soyad": "Yönetici", "role": "admin"})
    await server.db.students.insert_one({"id": ogr, "ad": "Can", "soyad": "Öğrenci", "sinif": 3,
                                         "ogretmen_id": t1, "veli_id": veli})

    H1 = {"Authorization": f"Bearer {create_access_token({'sub': t1})}"}
    H2 = {"Authorization": f"Bearer {create_access_token({'sub': t2})}"}
    HA = {"Authorization": f"Bearer {create_access_token({'sub': adm})}"}

    # Sabit bir hafta seç; serinin günü = bu tarihin haftalık günü
    ders_gunu = date(2026, 7, 6)  # haftanın günü test içinde hesaplanır
    gun = ders_gunu.weekday()
    bas_tarih = ders_gunu.isoformat()
    sonraki_gun = (ders_gunu + timedelta(days=1)).isoformat()

    transport = ASGITransport(app=server.app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1) Seri oluştur (teacher1)
        r = await ac.post("/api/ders/seri", json={
            "ogrenci_id": ogr, "gun": gun, "baslangic_saati": "15:00", "bitis_saati": "16:00",
            "baslangic_tarihi": bas_tarih,
        }, headers=H1)
        check(r.status_code == 200, f"seri oluştur 200 (status={r.status_code})")
        seri = r.json()
        check(seri.get("durum") == "aktif" and seri.get("ogrenci_ad") == "Can Öğrenci", "seri aktif + öğrenci adı çözüldü")
        seri_id = seri["id"]

        # 2) serilerim
        r = await ac.get("/api/ders/serilerim", headers=H1)
        check(r.status_code == 200 and any(s["id"] == seri_id for s in r.json()["seriler"]), "serilerim kendi serisini listeledi")

        # 3) Program: o gün için planlı oturum hesaplanmalı
        r = await ac.get(f"/api/ders/program?baslangic={bas_tarih}&bitis={bas_tarih}", headers=H1)
        check(r.status_code == 200, f"program 200 (status={r.status_code})")
        dersler = r.json()["dersler"]
        check(len(dersler) == 1 and dersler[0]["planli_mi"] is True, "planlı oturum hesaplandı (DB'de yok)")
        planli_id = dersler[0]["id"]
        check(planli_id.startswith("seri:"), "planlı oturum sanal id taşıyor")

        # 4) Oturumu taşı (sebep ile) → materyalize olur, yeni güne kayar
        r = await ac.put(f"/api/ders/oturum/{planli_id}/tasi", json={
            "tarih": sonraki_gun, "baslangic_saati": "15:00", "bitis_saati": "16:00",
            "sebep": "Öğretmen mazereti",
        }, headers=H1)
        check(r.status_code == 200, f"oturum taşı 200 (status={r.status_code})")
        tasinan = r.json()
        check(tasinan["tarih"] == sonraki_gun and tasinan["orijinal_tarih"] == bas_tarih, "taşıma orijinal tarihi sakladı")
        gercek_id = tasinan["id"]
        adet = await server.db.ders_oturumlari.count_documents({"seri_id": seri_id})
        check(adet == 1, "taşıma ders_oturumlari'na 1 kayıt yazdı (materyalizasyon)")

        # Program eski günde artık boş, yeni günde dolu
        r = await ac.get(f"/api/ders/program?baslangic={bas_tarih}&bitis={bas_tarih}", headers=H1)
        check(len(r.json()["dersler"]) == 0, "taşınan ders eski günde görünmüyor")
        r = await ac.get(f"/api/ders/program?baslangic={sonraki_gun}&bitis={sonraki_gun}", headers=H1)
        yeni_gun_dersler = r.json()["dersler"]
        check(len(yeni_gun_dersler) == 1 and yeni_gun_dersler[0]["tasima_sebebi"] == "Öğretmen mazereti", "taşınan ders yeni günde + sebep var")

        # 5) Yoklama gir
        r = await ac.post(f"/api/ders/oturum/{gercek_id}/yoklama", json={"durum": "katildi", "not": "Verimliydi"}, headers=H1)
        check(r.status_code == 200 and r.json()["yoklama"] == "katildi", "yoklama katıldı işaretlendi")

        # 6) Çakışma: aynı öğretmen, aynı gün, çakışan saat → 409
        r = await ac.post("/api/ders/seri", json={
            "ogrenci_id": ogr, "gun": gun, "baslangic_saati": "15:30", "bitis_saati": "16:30",
            "baslangic_tarihi": bas_tarih,
        }, headers=H1)
        check(r.status_code == 409, f"çakışan seri 409 (status={r.status_code})")

        # Çakışmayan saat → 200
        r = await ac.post("/api/ders/seri", json={
            "ogrenci_id": ogr, "gun": gun, "baslangic_saati": "17:00", "bitis_saati": "18:00",
            "baslangic_tarihi": bas_tarih,
        }, headers=H1)
        check(r.status_code == 200, f"çakışmayan seri 200 (status={r.status_code})")

        # 7) Yetki: teacher2 teacher1'in serisini düzenleyemez → 403
        r = await ac.put(f"/api/ders/seri/{seri_id}", json={"baslangic_saati": "14:00", "bitis_saati": "15:00", "sebep": "deneme"}, headers=H2)
        check(r.status_code == 403, f"başka öğretmen serisi düzenleme 403 (status={r.status_code})")

        # Sebep zorunlu: sebepsiz güncelleme → 400
        r = await ac.put(f"/api/ders/seri/{seri_id}", json={"baslangic_saati": "14:00", "bitis_saati": "15:00"}, headers=H1)
        check(r.status_code == 400, f"sebepsiz seri güncelleme 400 (status={r.status_code})")

        # Geçerli güncelleme (sebep ile)
        r = await ac.put(f"/api/ders/seri/{seri_id}", json={"baslangic_saati": "15:00", "bitis_saati": "16:00", "gun": gun, "sebep": "Saat netleştirme"}, headers=H1)
        check(r.status_code == 200, f"sebepli seri güncelleme 200 (status={r.status_code})")

        # 8) Admin değişiklik geçmişi → taşı + güncelle sebepleri gelir
        r = await ac.get("/api/ders/degisiklikler", headers=HA)
        check(r.status_code == 200, f"değişiklikler 200 (status={r.status_code})")
        degler = r.json()["degisiklikler"]
        sebepler = {d["sebep"] for d in degler}
        check("Öğretmen mazereti" in sebepler and "Saat netleştirme" in sebepler, "değişiklik geçmişi sebepleri içeriyor")
        check(any(d["tip"] == "oturum_tasi" for d in degler), "taşıma kaydı geçmişte var")

        # Teacher değişiklik geçmişine erişemez → 403
        r = await ac.get("/api/ders/degisiklikler", headers=H1)
        check(r.status_code == 403, "öğretmen değişiklik geçmişine erişemez (403)")

        # 9) Admin tüm serileri görebiliyor (öğretmen filtresiz)
        r = await ac.get("/api/ders/serilerim", headers=HA)
        check(r.status_code == 200 and any(s["id"] == seri_id for s in r.json()["seriler"]), "admin tüm serileri görüyor")

        # 10) Tek seferlik oturum + bildirim oluştu mu
        r = await ac.post("/api/ders/oturum", json={
            "ogrenci_id": ogr, "tarih": (ders_gunu + timedelta(days=10)).isoformat(),
            "baslangic_saati": "10:00", "bitis_saati": "11:00",
        }, headers=H1)
        check(r.status_code == 200 and r.json()["seri_id"] is None, "tek seferlik oturum oluştu")
        bildirim_sayisi = await server.db.bildirimler.count_documents({"alici_id": ogr})
        check(bildirim_sayisi >= 1, "öğrenciye değişiklik bildirimi gitti")

    await server.client.drop_database(TEST_DB)


def main():
    asyncio.run(run())
    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    sys.exit(0 if _kalan == 0 else 1)


if __name__ == "__main__":
    main()
