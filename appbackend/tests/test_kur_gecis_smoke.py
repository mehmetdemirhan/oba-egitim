"""Kur geçişi akışı (öğretmen tetikler → muhasebeye otomatik yansır) smoke testi.

Doğrular: öğretmen kendi öğrencisini bir üst kura geçirir; yeni alacak satırı
Ayarlar'daki eğitim-türü bazlı ücretle + vergi snapshot'ıyla oluşur; önceki kur
"tamamlandi" olur ama satır/borç kaybolmaz; mükerrer kur engellenir (409);
başka öğretmen 403 alır; öğretmene dönen yanıtta TUTAR yoktur ve öğretmen
GET /students'ta mali alan görmez; audit + admin/accountant bildirimi düşer;
Ayarlar kur_ucretleri generic uçla okunur/yazılır.
İzole DB (oba_test_kur_gecis). Gerçek DB'ye dokunmaz.
"""
import asyncio
import os
import sys

TEST_DB = "oba_test_kur_gecis"
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
    tA, tB = str(uuid.uuid4()), str(uuid.uuid4())
    uA, uB = str(uuid.uuid4()), str(uuid.uuid4())
    await server.db.users.insert_many([
        {"id": admin_id, "ad": "Yön", "soyad": "Etici", "role": "admin"},
        {"id": acc_id, "ad": "Muh", "soyad": "Asebe", "role": "accountant"},
        {"id": uA, "ad": "Öğr", "soyad": "A", "role": "teacher", "linked_id": tA},
        {"id": uB, "ad": "Öğr", "soyad": "B", "role": "teacher", "linked_id": tB},
    ])
    await server.db.teachers.insert_many([
        {"id": tA, "ad": "Öğr", "soyad": "A", "ogrenci_sayisi": 0, "atanan_ogrenciler": [], "yapilmasi_gereken_odeme": 0, "yapilan_odeme": 0},
        {"id": tB, "ad": "Öğr", "soyad": "B", "ogrenci_sayisi": 0, "atanan_ogrenciler": [], "yapilmasi_gereken_odeme": 0, "yapilan_odeme": 0},
    ])
    # Ayarlar: eğitim türü bazlı kur ücreti + genel varsayılan; vergi %15
    await server.db.sistem_ayarlari.insert_many([
        {"tip": "kur_ucretleri", "degerler": {"genel": 1000, "turler": {"Hızlı Okuma": 1500}}},
        {"tip": "vergi_ayarlari", "degerler": {"vergi_orani": 15}},
    ])
    H_admin = {"Authorization": f"Bearer {create_access_token({'sub': admin_id})}"}
    HA = {"Authorization": f"Bearer {create_access_token({'sub': uA})}"}
    HB = {"Authorization": f"Bearer {create_access_token({'sub': uB})}"}

    transport = ASGITransport(app=server.app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # ── Öğretmen A öğrenci oluşturur (kur 1, Hızlı Okuma) ──
        yeni = {"ad": "Ali", "soyad": "Veli", "sinif": "3", "veli_ad": "Ayşe", "veli_soyad": "Veli",
                "veli_telefon": "5551112233", "aldigi_egitim": "Hızlı Okuma", "kur": "1"}
        r = await ac.post("/api/students", headers=HA, json=yeni)
        check(r.status_code == 200, f"öğretmen A öğrenci ekledi ({r.status_code})")
        sid = r.json()["id"]

        # Önceki (kur 1) açık alacak satırı — muhasebe eklemiş gibi (tamamlandi testi için)
        kur1_id = str(uuid.uuid4())
        await server.db.kur_ucretleri.insert_one(
            {"id": kur1_id, "ogrenci_id": sid, "kur_adi": "1", "tutar": 1500.0,
             "durum": "acik", "tarih": "2026-01-01T00:00:00"})
        await server.db.students.update_one({"id": sid}, {"$inc": {"yapilmasi_gereken_odeme": 1500}})

        # ── Öğretmen A: kur geçişi (kur_no verilmez → 2 olmalı) ──
        r = await ac.post(f"/api/students/{sid}/kur-gecis", headers=HA, json={"baslangic_tarihi": "2026-07-01"})
        check(r.status_code == 200, f"öğretmen kur geçişi yaptı ({r.status_code})")
        body = r.json()
        check(body.get("yeni_kur") == 2, f"yeni kur otomatik 2 önerildi ({body.get('yeni_kur')})")
        check("tutar" not in body, "öğretmen yanıtında TUTAR görünmüyor")

        # Yeni kur kaydı: tutar eğitim-türü bazlı (1500), durum acik, vergi snapshot
        yeni_kur = await server.db.kur_ucretleri.find_one({"ogrenci_id": sid, "kur_adi": "2"})
        check(yeni_kur is not None, "yeni kur (2) alacak satırı oluştu")
        check(yeni_kur and yeni_kur.get("tutar") == 1500.0, f"tutar eğitim türü ücretinden geldi ({yeni_kur and yeni_kur.get('tutar')})")
        check(yeni_kur and yeni_kur.get("durum") == "acik", "yeni kur durumu 'acik'")
        check(yeni_kur and yeni_kur.get("vergi_orani") == 15, f"vergi oranı snapshot'landı ({yeni_kur and yeni_kur.get('vergi_orani')})")

        # Önceki kur (1) tamamlandı ama SATIR/BORÇ duruyor
        kur1 = await server.db.kur_ucretleri.find_one({"id": kur1_id})
        check(kur1 and kur1.get("durum") == "tamamlandi", "önceki kur (1) 'tamamlandi' işaretlendi")
        check(kur1 and kur1.get("tutar") == 1500.0, "önceki kurun borcu/satırı kaybolmadı")

        # Öğrenci: kur güncellendi, beklenen +1500 arttı (1500 → 3000)
        ogr = await server.db.students.find_one({"id": sid})
        check(ogr and ogr.get("kur") == "2", "öğrenci güncel kuru 2")
        check(ogr and ogr.get("yapilmasi_gereken_odeme") == 3000.0, f"beklenen tutar arttı ({ogr and ogr.get('yapilmasi_gereken_odeme')})")

        # ── Öğretmen mali alan görmez (GET /students strip) ──
        rl = await ac.get("/api/students", headers=HA)
        srow = next((s for s in rl.json() if s["id"] == sid), None)
        check(srow is not None and "yapilmasi_gereken_odeme" not in srow, "öğretmen GET /students'ta tutar görmüyor")
        check(srow and srow.get("kur") == "2", "öğretmen güncel kuru görüyor (mali değil)")

        # ── Mükerrer koruma: aynı kur no (2) tekrar → 409 ──
        r = await ac.post(f"/api/students/{sid}/kur-gecis", headers=HA, json={"kur_no": 2})
        check(r.status_code == 409, f"mükerrer kur engellendi (409) — geldi {r.status_code}")

        # ── Başka öğretmen (B) → 403 ──
        r = await ac.post(f"/api/students/{sid}/kur-gecis", headers=HB, json={})
        check(r.status_code == 403, f"başka öğretmen kur geçişi yapamaz (403) — geldi {r.status_code}")

        # ── Audit ──
        alog = await server.db.islem_log.count_documents({"modul": "ogrenci", "islem": "kur_gecis", "hedef_id": sid})
        check(alog >= 1, f"kur geçişi audit'e düştü ({alog})")

        # ── Bildirim: admin + accountant ──
        badmin = await server.db.bildirimler.count_documents({"alici_id": admin_id, "tur": "kur_gecisi"})
        bacc = await server.db.bildirimler.count_documents({"alici_id": acc_id, "tur": "kur_gecisi"})
        check(badmin >= 1, f"admin'e kur geçişi bildirimi düştü ({badmin})")
        check(bacc >= 1, f"muhasebeye kur geçişi bildirimi düştü ({bacc})")

        # ── Ayarlar generic uç: admin okur/yazar ──
        r = await ac.get("/api/ayarlar/kur_ucretleri", headers=H_admin)
        check(r.status_code == 200 and r.json().get("degerler", {}).get("genel") == 1000,
              "admin kur_ucretleri ayarını okudu")
        r = await ac.put("/api/ayarlar/kur_ucretleri", headers=H_admin,
                         json={"degerler": {"genel": 1200, "turler": {"Hızlı Okuma": 1800}}})
        check(r.status_code == 200, f"admin kur_ucretleri güncelledi ({r.status_code})")
        r = await ac.put("/api/ayarlar/kur_ucretleri", headers=HA,
                         json={"degerler": {"genel": 5}})
        check(r.status_code == 403, f"öğretmen ayar değiştiremez (403) — geldi {r.status_code}")

        # ── Explicit kur_no ile atlamalı geçiş (5) ──
        r = await ac.post(f"/api/students/{sid}/kur-gecis", headers=HA, json={"kur_no": 5})
        check(r.status_code == 200 and r.json().get("yeni_kur") == 5, "explicit kur_no ile geçiş çalışıyor")
        k5 = await server.db.kur_ucretleri.find_one({"ogrenci_id": sid, "kur_adi": "5"})
        check(k5 and k5.get("tutar") == 1800.0, f"güncellenen ayar tutarı uygulandı ({k5 and k5.get('tutar')})")

    await server.client.drop_database(TEST_DB)


if __name__ == "__main__":
    asyncio.run(run())
    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    sys.exit(1 if _kalan else 0)
