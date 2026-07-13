"""Dönem bazlı öğretmen ödemesi (ayın 15'i) — smoke testi (İŞ 1).

Doğrular: dönem sınırları (önceki ay 15 HARİÇ → bu ay 15 DAHİL); öğretmen payı
eğitim türü bazlı; öğretmen payı ayarı admin+accountant düzenler, öğretmen 403;
dönem ödemesi kaydı + toplam; aynı öğretmen+dönem iki kez ödenemez (409); ödenen
kur mühürlenir, sonraki sorguda çıkmaz ama başka döneme de girmez; geçmiş liste.
İzole DB (oba_test_ogretmen_donem). Gerçek DB'ye dokunmaz.
"""
import asyncio
import os
import sys

TEST_DB = "oba_test_ogretmen_donem"
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
    admin_id, acc_id, uT = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
    tA = str(uuid.uuid4())  # teacher record
    await server.db.users.insert_many([
        {"id": admin_id, "ad": "Yön", "soyad": "Etici", "role": "admin"},
        {"id": acc_id, "ad": "Muh", "soyad": "Asebe", "role": "accountant"},
        {"id": uT, "ad": "Öğr", "soyad": "A", "role": "teacher", "linked_id": tA},
    ])
    await server.db.teachers.insert_one(
        {"id": tA, "ad": "Öğr", "soyad": "A", "yapilmasi_gereken_odeme": 0.0, "yapilan_odeme": 0.0})

    # Öğrenciler (hepsi tA'nın)
    S = {n: str(uuid.uuid4()) for n in ("s1", "s2", "s3", "s4")}
    await server.db.students.insert_many([
        {"id": S["s1"], "ad": "Bir", "soyad": "X", "ogretmen_id": tA, "aldigi_egitim": "Hızlı Okuma"},
        {"id": S["s2"], "ad": "İki", "soyad": "Y", "ogretmen_id": tA, "aldigi_egitim": "Genel Ders"},
        {"id": S["s3"], "ad": "Üç", "soyad": "Z", "ogretmen_id": tA, "aldigi_egitim": "Genel Ders"},
        {"id": S["s4"], "ad": "Dört", "soyad": "W", "ogretmen_id": tA, "aldigi_egitim": "Genel Ders"},
    ])
    # SPEC B: hakediş ödeme-bazlı — dönem ataması ÖDEME tamamlanma tarihine göre.
    # Dönem 2026-07-15 aralığı: 2026-06-15 (HARİÇ) → 2026-07-15 (DAHİL)
    await server.db.kur_ucretleri.insert_many([
        {"id": "k1", "ogrenci_id": S["s1"], "kur_adi": "1", "durum": "tamamlandi", "egitim_turu": "Hızlı Okuma", "odeme_tamamlanma_tarihi": "2026-06-16T10:00:00"},  # İÇERDE
        {"id": "k2", "ogrenci_id": S["s2"], "kur_adi": "1", "durum": "tamamlandi", "egitim_turu": "Genel Ders", "odeme_tamamlanma_tarihi": "2026-07-15T09:00:00"},   # İÇERDE (15 dahil)
        {"id": "k3", "ogrenci_id": S["s3"], "kur_adi": "1", "durum": "tamamlandi", "egitim_turu": "Genel Ders", "odeme_tamamlanma_tarihi": "2026-06-15T09:00:00"},   # DIŞARDA (15 hariç)
        {"id": "k4", "ogrenci_id": S["s4"], "kur_adi": "1", "durum": "tamamlandi", "egitim_turu": "Genel Ders", "odeme_tamamlanma_tarihi": "2026-07-16T09:00:00"},   # DIŞARDA (sonraki dönem)
    ])

    H_admin = {"Authorization": f"Bearer {create_access_token({'sub': admin_id})}"}
    H_acc = {"Authorization": f"Bearer {create_access_token({'sub': acc_id})}"}
    H_t = {"Authorization": f"Bearer {create_access_token({'sub': uT})}"}

    transport = ASGITransport(app=server.app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # ── Öğretmen payı ayarı: accountant düzenler, öğretmen 403 ──
        r = await ac.put("/api/muhasebe/ayarlar/ogretmen-paylari", headers=H_acc,
                         json={"degerler": {"genel": 500, "turler": {"Hızlı Okuma": 800}}})
        check(r.status_code == 200, f"accountant öğretmen payı ayarladı ({r.status_code})")
        check((await ac.put("/api/muhasebe/ayarlar/ogretmen-paylari", headers=H_t,
                            json={"degerler": {"genel": 1}})).status_code == 403, "öğretmen payı ayarı değiştiremez (403)")
        g = (await ac.get("/api/muhasebe/ayarlar", headers=H_acc)).json()
        check(g.get("ogretmen_paylari", {}).get("genel") == 500, "öğretmen payı ayarı okundu")

        # ── Dönem 2026-07-15: sınırlar ──
        r = await ac.get("/api/muhasebe/ogretmen-donem?donem=2026-07-15", headers=H_acc)
        check(r.status_code == 200, f"dönem listesi 200 ({r.status_code})")
        ogretmenler = r.json().get("ogretmenler", [])
        grup = next((o for o in ogretmenler if o["ogretmen_id"] == tA), None)
        check(grup is not None, "öğretmen dönem grubunda")
        kur_seti = sorted(c["kur_ucreti_id"] for c in (grup["kurlar"] if grup else []))
        check(kur_seti == ["k1", "k2"], f"yalnız dönem-içi kurlar (k1,k2) — geldi {kur_seti}")
        check(grup and grup["toplam"] == 1300.0, f"toplam = 800(Hızlı)+500(genel)=1300 ({grup and grup['toplam']})")

        check((await ac.get("/api/muhasebe/ogretmen-donem?donem=2026-07-15", headers=H_t)).status_code == 403,
              "öğretmen dönem listesini göremez (403)")

        # ── Ödemeyi kaydet ──
        r = await ac.post("/api/muhasebe/ogretmen-donem/ode", headers=H_acc, json={"ogretmen_id": tA, "donem": "2026-07-15"})
        check(r.status_code == 200 and r.json().get("toplam") == 1300.0 and r.json().get("kur_sayisi") == 2,
              f"dönem ödemesi kaydedildi (1300, 2 kur) ({r.status_code})")
        # teacher.yapilan_odeme arttı (mevcut bakiye katmanı)
        t = await server.db.teachers.find_one({"id": tA})
        check(t and t.get("yapilan_odeme") == 1300.0, "öğretmen ödenen bakiyesi arttı (katmanlı)")

        # ── İdempotency: tekrar → 409 ──
        check((await ac.post("/api/muhasebe/ogretmen-donem/ode", headers=H_acc, json={"ogretmen_id": tA, "donem": "2026-07-15"})).status_code == 409,
              "aynı öğretmen+dönem tekrar ödenemez (409)")
        # ödenen kurlar artık dönemde çıkmaz
        r = await ac.get("/api/muhasebe/ogretmen-donem?donem=2026-07-15", headers=H_acc)
        grup2 = next((o for o in r.json().get("ogretmenler", []) if o["ogretmen_id"] == tA), None)
        check(grup2 is None, "ödenen dönemde artık ödenecek kur yok")

        # ── k4 sonraki dönemde (2026-08-15) çıkar, çift ödenmez ──
        r = await ac.get("/api/muhasebe/ogretmen-donem?donem=2026-08-15", headers=H_acc)
        grup3 = next((o for o in r.json().get("ogretmenler", []) if o["ogretmen_id"] == tA), None)
        kur3 = sorted(c["kur_ucreti_id"] for c in (grup3["kurlar"] if grup3 else []))
        check(kur3 == ["k4"], f"k4 sonraki dönemde (2026-08-15) çıkıyor — {kur3}")

        # ── Geçmiş ──
        r = await ac.get("/api/muhasebe/ogretmen-donem/gecmis", headers=H_acc)
        ods = r.json().get("odemeler", [])
        check(any(o["donem"] == "2026-07-15" and o["toplam"] == 1300.0 for o in ods), "geçmiş dönem ödemesi listede")

    await server.client.drop_database(TEST_DB)


if __name__ == "__main__":
    asyncio.run(run())
    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    sys.exit(1 if _kalan else 0)
