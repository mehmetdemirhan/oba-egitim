"""AI CEO — Kurul analitik S6-A (konsantrasyon + birim ekonomi + senaryo + kohort) smoke.

Kapsar: konsantrasyon riski bloğu + eşik anomalisi + Ayda kuyruğuna risk görevi; birim
ekonomi (LTV/marj); senaryo matematiği + varsayım etiketi; kohort yenileme eğrisi.

    cd appbackend
    PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe tests/test_ai_ceo_kurul_smoke.py
"""
import asyncio
import os
import sys

TEST_DB = "oba_test_ai_ceo_kurul"
os.environ["MONGO_URL"] = os.environ.get("MONGO_URL_TEST", "mongodb://localhost:27017")
os.environ["DB_NAME"] = TEST_DB
os.environ.setdefault("SECRET_KEY", "test-secret-key")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_gecen = _kalan = 0


def check(k, m):
    global _gecen, _kalan
    if k:
        _gecen += 1; print(f"  [GECTI] {m}")
    else:
        _kalan += 1; print(f"  [KALDI] {m}")


async def run():
    import server
    from httpx import AsyncClient, ASGITransport

    db = server.db
    await server.client.drop_database(TEST_DB)
    await db.users.insert_one({"id": "adm", "role": "admin", "ad": "A", "soyad": "M"})
    # 5 öğrenci: 4'ü t1 (80% > %25 eşik), 4'ü 'Genel' tür; gelir/kur/vergi
    for i, (oid, ogr, tur, ay) in enumerate([
        ("s1", "t1", "Genel", "2026-01-05T00:00:00"), ("s2", "t1", "Genel", "2026-01-08T00:00:00"),
        ("s3", "t1", "Genel", "2026-02-03T00:00:00"), ("s4", "t1", "Genel", "2026-02-06T00:00:00"),
        ("s5", "t2", "Hızlı", "2026-02-09T00:00:00")]):
        await db.students.insert_one({"id": oid, "ogretmen_id": ogr, "aldigi_egitim": tur,
                                      "yapilmasi_gereken_odeme": 1000, "yapilan_odeme": 1000,
                                      "kur": "2" if i < 3 else "1", "olusturma_tarihi": ay})
        await db.kur_ucretleri.insert_one({"id": f"k{i}", "ogrenci_id": oid, "tutar": 1000, "yapilan_odeme": 1000, "ogretmen_pay": 300})
        await db.payments.insert_one({"id": f"p{i}", "tip": "ogrenci", "kisi_id": oid, "miktar": 1000, "vergi": 150, "tarih": ay})
    await db.teachers.insert_one({"id": "t1", "yapilan_odeme": 1000})
    await db.teachers.insert_one({"id": "t2", "yapilan_odeme": 200})

    def H(u):
        return {"Authorization": f"Bearer {server.create_access_token({'sub': u})}"}

    async with AsyncClient(transport=ASGITransport(app=server.app), base_url="http://test") as ac:
        r = await ac.post("/api/ai/ceo/fotograf/cek", headers=H("adm"))
        foto = r.json()["fotograf"]
        kons = foto["konsantrasyon"]
        check(kons["en_buyuk_ogretmen_ogrenci_payi"] == 80.0, f"en büyük öğretmen öğrenci payı %80 ({kons['en_buyuk_ogretmen_ogrenci_payi']})")
        check(kons["en_buyuk_tur_payi"] == 80.0, "en büyük tür payı %80")
        be = foto["birim_ekonomi"]
        # brut=5000, vergi=750, ogt=1200 → net=3050; LTV=3050/5=610; marj=3050/5=610
        check(be["toplam_net"] == 3050.0, f"toplam net = 5000-750-1200 = 3050 ({be['toplam_net']})")
        check(be["ltv_ogrenci_basi_net"] == 610.0, f"LTV = net/öğrenci = 610 ({be['ltv_ogrenci_basi_net']})")
        check(be["kur_basi_net_marj"] == 610.0, "kur başı net marj = 610")

        # anomali: konsantrasyon riski kartı
        r = await ac.get("/api/ai/ceo/anomali", headers=H("adm"))
        tips = [a["tip"] for a in r.json()["anomaliler"]]
        check("konsantrasyon_riski" in tips, f"konsantrasyon riski anomalisi ({tips})")
        # Ayda kuyruğuna risk azaltma görevi eklendi (fotograf/cek tetikledi)
        r = await ac.get("/api/ai/ceo/kuyruk", headers=H("adm"))
        check(any(o.get("baslik") == "Konsantrasyon riskini azalt" for o in r.json()["kuyruk"]), "Ayda kuyruğuna 'Konsantrasyon riskini azalt' görevi eklendi")
        # ikinci fotoğraf çekimi çift görev eklemez
        await ac.post("/api/ai/ceo/fotograf/cek", headers=H("adm"))
        r = await ac.get("/api/ai/ceo/kuyruk", headers=H("adm"))
        check(sum(1 for o in r.json()["kuyruk"] if o.get("baslik") == "Konsantrasyon riskini azalt") == 1, "konsantrasyon görevi çiftlenmedi (idempotent)")

        # senaryo simülasyonu — hacim sabit (esneklik yok)
        r = await ac.post("/api/ai/ceo/senaryo", headers=H("adm"), json={"kur_ucreti_degisim_yuzde": 10, "ogretmen_payi_degisim_yuzde": 0})
        s = r.json()["senaryo"]
        # yeni brut=5500, vergi %15=825, ogt=1200 → net=3475; delta=+425
        check(abs(s["senaryo"]["net"] - 3475) < 1, f"senaryo net = 3475 (+10% fiyat) ({s['senaryo']['net']})")
        check(abs(s["net_delta"] - 425) < 1, f"net delta +425 ({s['net_delta']})")
        check("sabit" in s["varsayim"].lower(), "esneklik yoksa 'hacim sabit' varsayımı etiketli")
        # esneklikli senaryo → varsayım açıkça etiketli
        r = await ac.post("/api/ai/ceo/senaryo", headers=H("adm"), json={"kur_ucreti_degisim_yuzde": 10, "esneklik": 0.5})
        check("esnek" in r.json()["senaryo"]["varsayim"].lower(), "esneklik varsayımı AÇIKÇA etiketli")

        # kohort
        r = await ac.get("/api/ai/ceo/kohort", headers=H("adm"))
        koh = {c["ay"]: c for c in r.json()["kohortlar"]}
        check("2026-01" in koh and koh["2026-01"]["toplam"] == 2, "2026-01 kohortu 2 öğrenci")
        check(koh["2026-01"]["yenileme_orani"] == 100.0, f"2026-01 kohortu yenileme %100 (ikisi de kur>1) ({koh['2026-01']['yenileme_orani']})")

    await server.client.drop_database(TEST_DB)


if __name__ == "__main__":
    asyncio.run(run())
    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    sys.exit(1 if _kalan else 0)
