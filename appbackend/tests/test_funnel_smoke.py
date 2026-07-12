"""Veli Mesaj Funnel smoke — onaylı kuyruk + KVKK consent gate + segmentler.

Doğrular:
  - Yetki: yalnız admin/accountant; öğretmen → 403.
  - Segment kuralları doğru kişileri buluyor (ödeme/yenileme/tebrik ayrışıyor).
  - Şablon değişken doldurma ({veli_adi}/{ogrenci_adi}/{kur_no}/{kalan_borc}).
  - KVKK: onaysız veliye PAZARLAMA gönderilmez (onaysiz); HİZMET onaysıza gider
    ama 'ret'e saygı duyar. Onay 'var' olunca pazarlama kuyruğa girer.
  - Onaysız gönderim yolu YOK (onayla yalnız 'kuyrukta' alıcılara gönderir — mock).
  - Maliyet tahmini = kuyrukta × birim ücret.

Kanal MOCK'lanır — gerçek SMS gönderilmez. İzole DB. Çalıştırma:
  cd appbackend && PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe tests/test_funnel_smoke.py
"""
import asyncio
import os
import sys
from datetime import datetime, timezone, timedelta

TEST_DB = "oba_test_funnel"
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


def _iso(gun_once):
    return (datetime.now(timezone.utc) - timedelta(days=gun_once)).isoformat()


async def run():
    import uuid
    import server
    from core.auth import create_access_token
    import core.mesaj_kanallari as mk
    from httpx import AsyncClient, ASGITransport

    await server.client.drop_database(TEST_DB)

    # MOCK SMS kanalı — gerçek gönderim yok, gönderilenleri kaydeder
    class MockSMS:
        ad = "sms"; birim_ucret = 0.15
        def __init__(self): self.gonderilenler = []
        @property
        def kurulu(self): return True
        async def gonder(self, telefon, metin, tur="hizmet", meta=None):
            self.gonderilenler.append({"telefon": telefon, "metin": metin, "tur": tur, "meta": meta})
            return mk.KanalSonuc(True, saglayici_id=f"mock-{len(self.gonderilenler)}")
        def bilgi(self): return {"ad": "sms", "kurulu": True, "birim_ucret": 0.15}
    mock = MockSMS()
    mk.KANALLAR["sms"] = mock

    admin_id, acc_id, tuser_id = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
    tid = str(uuid.uuid4())
    await server.db.users.insert_many([
        {"id": admin_id, "ad": "Yon", "soyad": "Etici", "role": "admin"},
        {"id": acc_id, "ad": "Muh", "soyad": "Asebe", "role": "accountant"},
        {"id": tuser_id, "ad": "Ogr", "soyad": "Etmen", "role": "teacher", "linked_id": tid},
    ])

    # S_odeme: borçlu, ödemesiz → ödeme (hizmet). S_yen: kuru 10g önce bitti, açık kur yok →
    # yenileme (pazarlama). S_teb: kuru 2g önce bitti → tebrik (pazarlama).
    s_odeme, s_yen, s_teb, s_yd = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
    await server.db.students.insert_many([
        {"id": s_odeme, "ad": "Ali", "soyad": "Yilmaz", "kur": "2", "veli_ad": "Ayşe", "veli_soyad": "Yilmaz",
         "veli_telefon": "0555 111 0001", "ogretmen_id": tid, "yapilmasi_gereken_odeme": 1000.0, "yapilan_odeme": 0.0},
        # Yurt dışı veli (ABD numarası) — SMS gönderilemez, kuyrukta 'yurtdisi'
        {"id": s_yd, "ad": "Deniz", "soyad": "Ada", "kur": "2", "veli_ad": "Derya", "veli_soyad": "Ada",
         "veli_telefon": "+1 202 555 0100", "ogretmen_id": tid, "yapilmasi_gereken_odeme": 500.0, "yapilan_odeme": 0.0},
        {"id": s_yen, "ad": "Can", "soyad": "Kaya", "kur": "1", "veli_ad": "Cem", "veli_soyad": "Kaya",
         "veli_telefon": "0555 111 0002", "ogretmen_id": tid, "yapilmasi_gereken_odeme": 0.0, "yapilan_odeme": 0.0},
        {"id": s_teb, "ad": "Efe", "soyad": "Demir", "kur": "3", "veli_ad": "Eda", "veli_soyad": "Demir",
         "veli_telefon": "0555 111 0003", "ogretmen_id": tid, "yapilmasi_gereken_odeme": 0.0, "yapilan_odeme": 0.0},
    ])
    await server.db.kur_ucretleri.insert_many([
        {"id": str(uuid.uuid4()), "ogrenci_id": s_yen, "kur_adi": "1", "durum": "tamamlandi", "tamamlanma_tarihi": _iso(10)},
        {"id": str(uuid.uuid4()), "ogrenci_id": s_teb, "kur_adi": "3", "durum": "tamamlandi", "tamamlanma_tarihi": _iso(2)},
    ])

    H_admin = {"Authorization": f"Bearer {create_access_token({'sub': admin_id})}"}
    H_acc = {"Authorization": f"Bearer {create_access_token({'sub': acc_id})}"}
    H_teacher = {"Authorization": f"Bearer {create_access_token({'sub': tuser_id})}"}

    transport = ASGITransport(app=server.app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Yetki
        r = await ac.get("/api/funnel/segmentler", headers=H_teacher)
        check(r.status_code == 403, f"öğretmen funnel'a erişemez (403) ({r.status_code})")

        # Segment sayıları
        r = await ac.get("/api/funnel/segmentler", headers=H_admin)
        seg = {s["ad"]: s["alici_sayisi"] for s in r.json()["segmentler"]}
        check(seg.get("odeme") == 2 and seg.get("yenileme") == 1 and seg.get("tebrik") == 1,
              f"segmentler doğru ayrıştı odeme/yenileme/tebrik=2/1/1 ({seg})")

        # Segment alıcıları + doğru kişi
        r = await ac.get("/api/funnel/segmentler/odeme", headers=H_acc)
        od = r.json()["alicilar"]
        s_od = next((x for x in od if x["ogrenci_id"] == s_odeme), None)
        check(len(od) == 2 and s_od and s_od["kalan_borc"] == 1000.0,
              f"ödeme segmenti 2 alıcı (S_odeme kalan 1000) ({len(od)})")

        # Şablon (pazarlama) + değişken doldurma
        r = await ac.post("/api/funnel/sablonlar", headers=H_admin, json={
            "ad": "Yenileme", "kanal": "sms", "tur": "pazarlama",
            "metin": "Sn {veli_adi}, {ogrenci_adi} {kur_no}. kuru bitti. Borç: {kalan_borc}"})
        sablon_paz = r.json()["id"]

        # Pazarlama + onaysız → onaysiz (GÖNDERİLMEZ), maliyet 0
        r = await ac.post("/api/funnel/gonderim", headers=H_admin, json={"segment": "yenileme", "sablon_id": sablon_paz})
        g = r.json()
        alici = g["alicilar"][0]
        check(g["ozet"]["kuyrukta"] == 0 and g["ozet"]["onaysiz"] == 1 and g["tahmini_maliyet"] == 0.0,
              f"pazarlama+onaysız → onaysiz, maliyet 0 ({g['ozet']})")
        check(alici["durum"] == "onaysiz" and "Cem Kaya" in alici["mesaj"] and "1. kuru" in alici["mesaj"],
              f"değişken dolduruldu + onaysiz ({alici['mesaj'][:40]})")

        # Onay 'var' → pazarlama kuyruğa girer + maliyet
        await ac.put("/api/funnel/onay", headers=H_admin, json={"telefon": "0555 111 0002", "durum": "var"})
        r = await ac.post("/api/funnel/gonderim", headers=H_admin, json={"segment": "yenileme", "sablon_id": sablon_paz})
        g2 = r.json()
        check(g2["ozet"]["kuyrukta"] == 1 and abs(g2["tahmini_maliyet"] - 0.15) < 1e-6,
              f"onay 'var' → kuyrukta 1, maliyet 0.15 ({g2['ozet']}, {g2['tahmini_maliyet']})")

        # Onayla (mock) → 1 gönderim; onaysiz alıcı olmadığından hepsi gider
        r = await ac.post(f"/api/funnel/gonderim/{g2['id']}/onayla", headers=H_admin)
        onceki = len(mock.gonderilenler)
        check(r.status_code == 200 and r.json()["ozet"]["gonderildi"] == 1 and onceki == 1,
              f"onayla → mock 1 SMS gönderdi ({r.json()['ozet']})")
        check(mock.gonderilenler[-1]["tur"] == "pazarlama", "pazarlama türü kanala iletildi (İYS filtresi için)")

        # HİZMET segmenti: onaysıza GİDER (ödeme, S_odeme onayı yok)
        r = await ac.post("/api/funnel/sablonlar", headers=H_admin, json={
            "ad": "Borç", "kanal": "sms", "tur": "hizmet", "metin": "Borcunuz {kalan_borc}"})
        sablon_hiz = r.json()["id"]
        r = await ac.post("/api/funnel/gonderim", headers=H_acc, json={"segment": "odeme", "sablon_id": sablon_hiz})
        gh = r.json()
        yd = next((a for a in gh["alicilar"] if a["ogrenci_id"] == s_yd), None)
        check(gh["ozet"]["kuyrukta"] == 1 and gh["ozet"]["yurtdisi"] == 1 and yd and yd["durum"] == "yurtdisi",
              f"hizmet onaysıza gider (kuyrukta 1); yurt dışı numara ayrı (yurtdisi 1) ({gh['ozet']})")
        # Yurt dışı gönderilmez + hata sayılmaz
        onceki_yd = len(mock.gonderilenler)
        r2 = await ac.post(f"/api/funnel/gonderim/{gh['id']}/onayla", headers=H_acc)
        check(r2.json()["ozet"]["gonderildi"] == 1 and r2.json()["ozet"]["hata"] == 0
              and len(mock.gonderilenler) == onceki_yd + 1,
              f"yurt dışı gönderilmez, hata sayılmaz (1 gönderildi, 0 hata) ({r2.json()['ozet']})")

        # Parça-bazlı maliyet: 80 Türkçe karakter → 2 SMS parçası → 2×birim
        r = await ac.post("/api/funnel/sablonlar", headers=H_admin, json={"ad": "Uzun", "kanal": "sms", "tur": "hizmet", "metin": "ç" * 80})
        s_uzun = r.json()["id"]
        r = await ac.post("/api/funnel/gonderim", headers=H_acc, json={"segment": "odeme", "sablon_id": s_uzun})
        gu = r.json()
        check(gu["ozet"]["kuyrukta"] == 1 and gu["ozet"]["toplam_parca"] == 2 and abs(gu["tahmini_maliyet"] - 0.30) < 1e-6,
              f"parça-bazlı maliyet: 2 parça × 0.15 = 0.30 ({gu['ozet'].get('toplam_parca')}, {gu['tahmini_maliyet']})")

        # 'ret' → hizmet bile GİTMEZ (opt-out'a saygı)
        await ac.put("/api/funnel/onay", headers=H_admin, json={"telefon": "0555 111 0001", "durum": "ret"})
        r = await ac.post("/api/funnel/gonderim", headers=H_acc, json={"segment": "odeme", "sablon_id": sablon_hiz})
        check(r.json()["ozet"]["kuyrukta"] == 0, f"'ret' → hizmet bile gitmez (kuyrukta 0) ({r.json()['ozet']})")

        # ONAYSIZ GÖNDERİM YOLU YOK: tümü onaysiz olan gönderimde onayla → mock 0 yeni gönderim
        r = await ac.post("/api/funnel/gonderim", headers=H_admin, json={"segment": "tebrik", "sablon_id": sablon_paz})
        g_teb = r.json()  # S_teb onayı yok → pazarlama → onaysiz
        onceki = len(mock.gonderilenler)
        r = await ac.post(f"/api/funnel/gonderim/{g_teb['id']}/onayla", headers=H_admin)
        check(r.json()["ozet"]["gonderildi"] == 0 and len(mock.gonderilenler) == onceki,
              f"onaysız gönderim yolu YOK (0 gönderildi, mock artmadı) ({r.json()['ozet']})")

    await server.client.drop_database(TEST_DB)


def main():
    asyncio.run(run())
    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    sys.exit(0 if _kalan == 0 else 1)


if __name__ == "__main__":
    main()
