"""Öğretmen Başarılarım endpoint smoke testi.

GET /api/ogretmen/basarilarim → 200, tüm alanlar dolu, kur_basarilari alanı mevcut.
Yetki: öğrenci → 403. Zaman serisi 12 haftalık.
İzole test DB'sine karşı çalışır.

    cd appbackend
    .venv/Scripts/python.exe tests/test_ogretmen_basarilarim_smoke.py
"""
import asyncio
import os
import sys
import uuid
from datetime import datetime, timedelta

TEST_DB = "oba_test_ogretmen_basarilarim_smoke"
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
    now = datetime.utcnow()

    t1 = str(uuid.uuid4())   # test edilen öğretmen
    t2 = str(uuid.uuid4())   # 2. öğretmen (sıralama için)
    await server.db.users.insert_one({"id": t1, "ad": "Ayşe", "soyad": "Öğretmen", "role": "teacher", "puan": 5000})
    await server.db.users.insert_one({"id": t2, "ad": "Mehmet", "soyad": "Öğretmen", "role": "teacher", "puan": 9000})

    # Öğrenciler (t1'e bağlı)
    s1, s2 = str(uuid.uuid4()), str(uuid.uuid4())
    await server.db.students.insert_one({"id": s1, "ad": "Ali", "soyad": "Yılmaz", "ogretmen_id": t1})
    await server.db.students.insert_one({"id": s2, "ad": "Ece", "soyad": "Demir", "ogretmen_id": t1})
    # s1 son 7 gün içinde okuma → aktif
    await server.db.reading_logs.insert_one({"id": str(uuid.uuid4()), "ogrenci_id": s1, "tarih": now.isoformat(), "sure_dakika": 20})

    # Öğrenci user (403 testi)
    su = str(uuid.uuid4())
    await server.db.users.insert_one({"id": su, "ad": "Ali", "soyad": "Yılmaz", "role": "student", "linked_id": s1})

    # Rozetler (t1)
    await server.db.kazanilan_rozetler.insert_one({"id": str(uuid.uuid4()), "kullanici_id": t1, "rozet_kodu": "icerik_ilk", "kazanma_tarihi": (now - timedelta(days=3)).isoformat()})
    await server.db.kazanilan_rozetler.insert_one({"id": str(uuid.uuid4()), "kullanici_id": t1, "rozet_kodu": "oy_ilk", "kazanma_tarihi": (now - timedelta(days=20)).isoformat()})

    # Veli anketleri (t1)
    await server.db.veli_anketleri.insert_one({"id": str(uuid.uuid4()), "ogretmen_id": t1, "yanitlar": [{"puan": 5}, {"puan": 4}], "tavsiye": True})
    await server.db.veli_anketleri.insert_one({"id": str(uuid.uuid4()), "ogretmen_id": t1, "yanitlar": [{"puan": 4}], "tavsiye": True})

    # İçerikler (t1 ekledi)
    await server.db.gelisim_icerik.insert_one({"id": str(uuid.uuid4()), "ekleyen_id": t1, "durum": "yayinda", "tarih": (now - timedelta(days=5)).isoformat(), "oylar": {}})
    await server.db.gelisim_icerik.insert_one({"id": str(uuid.uuid4()), "ekleyen_id": t1, "durum": "beklemede", "tarih": (now - timedelta(days=1)).isoformat(), "oylar": {}})
    # t1'in oy verdiği bir içerik
    await server.db.gelisim_icerik.insert_one({"id": str(uuid.uuid4()), "ekleyen_id": t2, "durum": "oylama", "tarih": now.isoformat(), "oylar": {t1: {"onay": True}}})

    # Kur atlamaları (t1) — s1: 3 atlama (kur 1→4), s2: 1 atlama
    for eski, yeni in [(1, 2), (2, 3), (3, 4)]:
        await server.db.kur_atlamalari.insert_one({"id": str(uuid.uuid4()), "ogretmen_id": t1, "ogrenci_id": s1, "eski_kur": eski, "yeni_kur": yeni, "tarih": now.isoformat()})
    await server.db.kur_atlamalari.insert_one({"id": str(uuid.uuid4()), "ogretmen_id": t1, "ogrenci_id": s2, "eski_kur": 1, "yeni_kur": 2, "tarih": now.isoformat()})

    HT = {"Authorization": f"Bearer {create_access_token({'sub': t1})}"}
    HS = {"Authorization": f"Bearer {create_access_token({'sub': su})}"}

    transport = ASGITransport(app=server.app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # ── Öğrenci → 403 ──
        r = await ac.get("/api/ogretmen/basarilarim", headers=HS)
        check(r.status_code == 403, f"öğrenci 403 (status={r.status_code})")

        # ── Öğretmen → 200 ──
        r = await ac.get("/api/ogretmen/basarilarim", headers=HT)
        check(r.status_code == 200, f"öğretmen 200 (status={r.status_code})")
        d = r.json()

        # Ana alanlar
        for alan in ["ogretmen_id", "ad_soyad", "puan_bilgisi", "rozetler", "veli_degerlendirmesi",
                     "ogrenci_ozet", "icerik_ozet", "kur_basarilari", "zaman_serisi"]:
            check(alan in d, f"'{alan}' alanı response'ta var")

        # Puan bilgisi
        pb = d["puan_bilgisi"]
        check(pb["sira"] == 2 and pb["toplam_ogretmen"] == 2, f"sıra 2/2 (gelen {pb['sira']}/{pb['toplam_ogretmen']})")
        check(pb["toplam_xp"] >= 5000, f"toplam_xp >= 5000 (puan+rozet) (gelen {pb['toplam_xp']})")
        check(bool(pb["motivasyon_mesaji"]), "motivasyon mesajı dolu")

        # Rozetler
        rz = d["rozetler"]
        check(rz["kazanilan_sayisi"] == 2, f"2 rozet (gelen {rz['kazanilan_sayisi']})")
        check(rz["toplam_rozet"] > 0, "toplam_rozet > 0")
        check(len(rz["son_kazanilanlar"]) == 2, f"son_kazanilanlar 2 (gelen {len(rz['son_kazanilanlar'])})")

        # Veli
        check(d["veli_degerlendirmesi"]["toplam_anket"] == 2, "2 veli anketi")
        check(abs(d["veli_degerlendirmesi"]["ortalama"] - 4.25) < 0.3, f"veli ortalama ~4.3 (gelen {d['veli_degerlendirmesi']['ortalama']})")

        # Öğrenci özet
        oo = d["ogrenci_ozet"]
        check(oo["toplam_ogrenci"] == 2, f"2 öğrenci (gelen {oo['toplam_ogrenci']})")
        check(oo["aktif_ogrenci"] == 1, f"1 aktif öğrenci (gelen {oo['aktif_ogrenci']})")

        # İçerik özet
        io = d["icerik_ozet"]
        check(io["olusturulan_icerik"] == 2, f"2 içerik oluşturuldu (gelen {io['olusturulan_icerik']})")
        check(io["onaylanan_icerik"] == 1, f"1 onaylanan içerik (gelen {io['onaylanan_icerik']})")
        check(io["oy_verdigi_icerik"] == 1, f"1 oy verdiği içerik (gelen {io['oy_verdigi_icerik']})")

        # Kur başarıları — alan HER ZAMAN mevcut
        kb = d["kur_basarilari"]
        check("kur_atlatilan_ogrenci_sayisi" in kb and "en_uzun_takip" in kb, "kur_basarilari alanları mevcut")
        check(kb["kur_atlatilan_ogrenci_sayisi"] == 2, f"2 öğrenciye kur atlatıldı (gelen {kb['kur_atlatilan_ogrenci_sayisi']})")
        eu = kb["en_uzun_takip"]
        check(eu and eu["kur_sayisi"] == 3, f"en uzun takip 3 kur (gelen {eu and eu['kur_sayisi']})")
        check(eu and eu["ogrenci_adi"] == "Ali Yılmaz", f"en uzun takip öğrencisi Ali Yılmaz (gelen {eu and eu['ogrenci_adi']})")
        check(eu and eu["baslangic_kur"] == 1 and eu["mevcut_kur"] == 4, "kur 1→4")

        # Zaman serisi
        zs = d["zaman_serisi"]
        check(len(zs["etiketler"]) == 12 and len(zs["xp_gelisim"]) == 12 and len(zs["rozet_gelisim"]) == 12,
              "zaman serisi 12 haftalık (3 dizi eşit uzunlukta)")
        check(zs["xp_gelisim"] == sorted(zs["xp_gelisim"]), "xp_gelisim kümülatif (azalmayan)")
        check(zs["xp_gelisim"][-1] == pb["toplam_xp"], f"xp serisi gerçek toplama sabitlendi (son={zs['xp_gelisim'][-1]}, toplam={pb['toplam_xp']})")
        check(zs["rozet_gelisim"][-1] == 2, f"rozet serisi sonu 2 (gelen {zs['rozet_gelisim'][-1]})")

    await server.client.drop_database(TEST_DB)
    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    return _kalan == 0


if __name__ == "__main__":
    ok = asyncio.run(run())
    sys.exit(0 if ok else 1)
