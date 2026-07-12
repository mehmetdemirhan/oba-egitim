"""Admin dashboard analitik (huni + nakit akışı + yaşlandırma + öğretmen perf) smoke.

Elle kurgulanmış senaryoyla: huni geçiş oranları; 30 gün beklemede penceresi; nakit
akışı bileşen tutarlılığı (tahsilat−vergi−ödeme=net); yaşlandırma kovaları toplamı =
toplam açık alacak; yenileme yetersiz-veri eşiği (<3 tamamlanmış kur); yalnız admin.
İzole DB (oba_test_dash_analitik). Gerçek DB'ye dokunmaz.
"""
import asyncio
import os
import sys
from datetime import datetime, timezone, timedelta

TEST_DB = "oba_test_dash_analitik"
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
    admin_id, acc_id = str(uuid.uuid4()), str(uuid.uuid4())
    tA, tB = str(uuid.uuid4()), str(uuid.uuid4())
    await server.db.users.insert_many([
        {"id": admin_id, "ad": "Yön", "soyad": "E", "role": "admin"},
        {"id": acc_id, "ad": "Muh", "soyad": "A", "role": "accountant"},
    ])
    await server.db.teachers.insert_many([
        {"id": tA, "ad": "Ahmet", "soyad": "A"},
        {"id": tB, "ad": "Berk", "soyad": "B"},
    ])

    def iso(gun_once):
        return (datetime.now(timezone.utc) - timedelta(days=gun_once)).isoformat()

    S = {n: str(uuid.uuid4()) for n in ("s1", "s2", "s3", "s4", "sage", "sb")}
    await server.db.students.insert_many([
        {"id": S["s1"], "ad": "S1", "soyad": "X", "ogretmen_id": tA, "aldigi_egitim": "Genel", "yapilan_odeme": 0},
        {"id": S["s2"], "ad": "S2", "soyad": "X", "ogretmen_id": tA, "aldigi_egitim": "Genel", "yapilan_odeme": 0},
        {"id": S["s3"], "ad": "S3", "soyad": "X", "ogretmen_id": tA, "aldigi_egitim": "Genel", "yapilan_odeme": 0},
        {"id": S["s4"], "ad": "S4", "soyad": "X", "ogretmen_id": tA, "aldigi_egitim": "Genel", "yapilan_odeme": 0},
        {"id": S["sage"], "ad": "SA", "soyad": "X", "ogretmen_id": tA, "aldigi_egitim": "Genel", "yapilan_odeme": 0,
         "yapilmasi_gereken_odeme": 1000},
        {"id": S["sb"], "ad": "SB", "soyad": "Y", "ogretmen_id": tB, "aldigi_egitim": "Genel", "yapilan_odeme": 0},
    ])
    # Kur kayıtları — tutar=0 (yaşlandırmayı etkilemesin); sage tutarlı açık alacak
    await server.db.kur_ucretleri.insert_many([
        # s1: kur1 tamamlandı 40g önce + kur2 açık → 1→2 geçti
        {"id": "a1", "ogrenci_id": S["s1"], "kur_adi": "1", "durum": "tamamlandi", "tutar": 0, "baslangic_tarihi": iso(60), "tamamlanma_tarihi": iso(40)},
        {"id": "a2", "ogrenci_id": S["s1"], "kur_adi": "2", "durum": "acik", "tutar": 0, "baslangic_tarihi": iso(40)},
        # s2: kur1 tamamlandı 40g önce, sonraki yok → geçmedi (30g penceresi dışı)
        {"id": "b1", "ogrenci_id": S["s2"], "kur_adi": "1", "durum": "tamamlandi", "tutar": 0, "baslangic_tarihi": iso(60), "tamamlanma_tarihi": iso(40)},
        # s3: kur1 tamamlandı 10g önce, sonraki yok → BEKLEMEDE
        {"id": "c1", "ogrenci_id": S["s3"], "kur_adi": "1", "durum": "tamamlandi", "tutar": 0, "baslangic_tarihi": iso(30), "tamamlanma_tarihi": iso(10)},
        # s4: kur1+kur2 tamamlandı 40g önce + kur3 açık → 1→2 ve 2→3 geçti
        {"id": "d1", "ogrenci_id": S["s4"], "kur_adi": "1", "durum": "tamamlandi", "tutar": 0, "baslangic_tarihi": iso(80), "tamamlanma_tarihi": iso(50)},
        {"id": "d2", "ogrenci_id": S["s4"], "kur_adi": "2", "durum": "tamamlandi", "tutar": 0, "baslangic_tarihi": iso(50), "tamamlanma_tarihi": iso(40)},
        {"id": "d3", "ogrenci_id": S["s4"], "kur_adi": "3", "durum": "acik", "tutar": 0, "baslangic_tarihi": iso(40)},
        # sage: açık alacak (tutar 1000, başlangıç 40g önce) → 31-60 kovası
        {"id": "e1", "ogrenci_id": S["sage"], "kur_adi": "1", "durum": "acik", "tutar": 1000, "baslangic_tarihi": iso(40)},
        # sb (tB): yalnız 1 tamamlanmış kur → yetersiz veri
        {"id": "f1", "ogrenci_id": S["sb"], "kur_adi": "1", "durum": "tamamlandi", "tutar": 0, "baslangic_tarihi": iso(60), "tamamlanma_tarihi": iso(40)},
    ])
    # Nakit akışı: bu ay tahsilat 1000/vergi 150 + öğretmen ödemesi 200
    await server.db.payments.insert_many([
        {"id": str(uuid.uuid4()), "tip": "ogrenci", "kisi_id": S["s1"], "miktar": 1000, "vergi": 150, "tarih": iso(1)},
        {"id": str(uuid.uuid4()), "tip": "ogretmen", "kisi_id": tA, "miktar": 200, "tarih": iso(1)},
    ])
    # Anket: tA memnuniyet ort 4.5
    await server.db.veli_anketleri.insert_many([
        {"id": str(uuid.uuid4()), "ogretmen_id": tA, "yanitlar": [{"puan": 4}, {"puan": 5}]},
    ])

    H_admin = {"Authorization": f"Bearer {create_access_token({'sub': admin_id})}"}
    H_acc = {"Authorization": f"Bearer {create_access_token({'sub': acc_id})}"}

    transport = ASGITransport(app=server.app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        check((await ac.get("/api/dashboard/analitik", headers=H_acc)).status_code == 403,
              "accountant analitik göremez (yalnız admin, 403)")
        r = await ac.get("/api/dashboard/analitik", headers=H_admin)
        check(r.status_code == 200, f"analitik 200 ({r.status_code})")
        d = r.json()

        # ── Huni ──
        # Huni GLOBAL: kur1 tamamlayan = s1,s2,s3,s4 + sb(tB) = 5; geçen = s1,s4 = 2; beklemede = s3
        h1 = next((x for x in d["huni"] if x["kur"] == 1), None)
        check(h1 and h1["tamamlayan"] == 5 and h1["gecen"] == 2 and h1["beklemede"] == 1,
              f"huni L1: tamamlayan=5, geçen=2, beklemede=1 ({h1})")
        check(h1 and h1["oran"] == 50.0, f"huni L1 oran = 2/(5-1)=50.0 ({h1 and h1['oran']})")
        h2 = next((x for x in d["huni"] if x["kur"] == 2), None)
        check(h2 and h2["tamamlayan"] == 1 and h2["gecen"] == 1 and h2["oran"] == 100.0,
              f"huni L2: tamamlayan=1, oran=100 ({h2})")

        # ── Nakit akışı: son ay net = tahsilat − vergi − ödeme ──
        son = d["nakit_akisi"][-1]
        check(son["tahsilat"] == 1000 and son["vergi"] == 150 and son["ogretmen_odeme"] == 200,
              f"nakit bileşenleri (1000/150/200) — {son}")
        check(son["net"] == son["tahsilat"] - son["vergi"] - son["ogretmen_odeme"] == 650,
              f"net = tahsilat−vergi−ödeme = 650 ({son['net']})")

        # ── Yaşlandırma: toplam = tek açık alacak (1000), 31-60 kovası ──
        yas = d["yaslandirma"]
        toplam = round(sum(yas[k]["toplam"] for k in yas), 2)
        sayi = sum(yas[k]["sayi"] for k in yas)
        check(toplam == 1000.0 and sayi == 1, f"yaşlandırma toplam=1000, sayı=1 (açık alacak) — {yas}")
        check(yas["31-60"]["toplam"] == 1000.0, "40 günlük alacak 31-60 kovasında")

        # ── Öğretmen performansı ──
        pA = next((x for x in d["ogretmen_performans"] if x["ogretmen_id"] == tA), None)
        pB = next((x for x in d["ogretmen_performans"] if x["ogretmen_id"] == tB), None)
        check(pA and pA["aktif_ogrenci"] == 5, f"tA aktif öğrenci=5 ({pA and pA['aktif_ogrenci']})")
        check(pA and pA["memnuniyet"] == 4.5, f"tA memnuniyet ort=4.5 ({pA and pA['memnuniyet']})")
        check(pA and pA["yenileme_yetersiz"] is False and pA["yenileme_orani"] is not None,
              f"tA yenileme oranı hesaplandı (≥3 tamamlanmış) — {pA and pA['yenileme_orani']}")
        check(pB and pB["yenileme_yetersiz"] is True and pB["yenileme_orani"] is None,
              "tB yenileme oranı 'yetersiz veri' (<3 tamamlanmış kur)")
        # sıralama: aktif öğrenci azalan (tA=5 önce)
        check(d["ogretmen_performans"][0]["ogretmen_id"] == tA, "varsayılan sıralama aktif öğrenci azalan")

    await server.client.drop_database(TEST_DB)


if __name__ == "__main__":
    asyncio.run(run())
    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    sys.exit(1 if _kalan else 0)
