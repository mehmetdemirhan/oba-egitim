"""Kutulu Okuma smoke testi.

Kapsar:
- core.metin_zorluk sezgiseli (zorluk_hesapla + zorluk_dagit_gorece)
- GET /kutulu-okuma/metin: öğrencinin sinif + kur→zorluk ile metin seçimi ve
  kademeli fallback (sinif+zorluk → sinif → herhangi)
- POST /diagnostic/texts: yeni metne otomatik zorluk etiketi
- Ayarlar: /ayarlar/kutulu_okuma varsayılanı + admin PUT

İzole test DB'sine karşı çalışır (oba_test_kutulu_okuma). Gerçek DB'ye dokunmaz.
    cd appbackend
    .venv/Scripts/python.exe tests/test_kutulu_okuma_smoke.py
"""
import asyncio
import os
import sys

TEST_DB = "oba_test_kutulu_okuma"
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
    from core.metin_zorluk import zorluk_hesapla, zorluk_dagit_gorece, okunabilirlik_skoru
    from httpx import AsyncClient, ASGITransport

    await server.client.drop_database(TEST_DB)

    # ── 1) Sezgisel birim testleri ──
    kolay = "Ali top at. Kaç kaç? Su iç."
    zor = ("Küreselleşen dünyada sürdürülebilir kalkınma, ekonomik büyüme ile çevresel "
           "dengenin uzun vadeli uyumunu gerektiren çok boyutlu bir olgudur.")
    check(okunabilirlik_skoru(zor) > okunabilirlik_skoru(kolay), "zor metin skoru > kolay metin skoru")
    check(zorluk_hesapla("") == "kolay", "boş metin kolay (skor 0)")
    check(zorluk_hesapla(zor) in ("orta", "zor"), f"uzun/karmaşık metin orta|zor ({zorluk_hesapla(zor)})")
    # Göreli dağıtım
    check(zorluk_dagit_gorece([1.0]) == ["orta"], "tek metin → orta")
    check(sorted(zorluk_dagit_gorece([1.0, 5.0])) == ["kolay", "zor"], "iki metin → kolay+zor")
    d3 = zorluk_dagit_gorece([1.0, 2.0, 3.0])
    check(d3 == ["kolay", "orta", "zor"], f"üç metin → kolay/orta/zor ({d3})")

    # ── Test verisi: sınıf 4 için 3 metin (kolay/orta/zor) + sınıf 5 için 1 metin ──
    async def metin_ekle(sinif, zorluk, baslik):
        await server.db.analiz_metinler.insert_one({
            "id": str(uuid.uuid4()), "baslik": baslik, "icerik": f"{baslik} icerik metni buraya.",
            "kelime_sayisi": 4, "sinif_seviyesi": sinif, "tur": "hikaye",
            "zorluk": zorluk, "durum": "havuzda", "olusturma_tarihi": "2026-01-01T00:00:00",
        })
    await metin_ekle("4", "kolay", "S4 Kolay")
    await metin_ekle("4", "orta", "S4 Orta")
    await metin_ekle("4", "zor", "S4 Zor")
    await metin_ekle("5", "orta", "S5 Orta")
    # Havuzda OLMAYAN (beklemede) metin — seçilmemeli
    await server.db.analiz_metinler.insert_one({
        "id": str(uuid.uuid4()), "baslik": "Beklemede", "icerik": "x y z", "sinif_seviyesi": "4",
        "zorluk": "kolay", "durum": "beklemede", "olusturma_tarihi": "2026-01-01T00:00:00"})

    # ── Öğrenci: sinif 4, kur "Kur 2" → zorluk orta ──
    ogr_rec = str(uuid.uuid4())
    await server.db.students.insert_one({"id": ogr_rec, "ad": "Test", "soyad": "Öğrenci", "sinif": "4", "kur": "Kur 2"})
    ogr_user = str(uuid.uuid4())
    await server.db.users.insert_one({"id": ogr_user, "role": "student", "linked_id": ogr_rec, "ad": "Test", "soyad": "Öğrenci"})
    H_ogr = {"Authorization": f"Bearer {create_access_token({'sub': ogr_user})}"}

    admin_id = str(uuid.uuid4())
    await server.db.users.insert_one({"id": admin_id, "role": "admin", "ad": "Yön", "soyad": "Etici"})
    H_admin = {"Authorization": f"Bearer {create_access_token({'sub': admin_id})}"}

    transport = ASGITransport(app=server.app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # ── 2) Öğrenci metni: sinif 4 + kur2→orta eşleşmeli ──
        r = await ac.get("/api/kutulu-okuma/metin", headers=H_ogr)
        check(r.status_code == 200, f"kutulu-okuma/metin 200 (status={r.status_code})")
        m = r.json()
        check(m.get("sinif") == "4", f"öğrencinin sınıfına (4) uygun metin ({m.get('sinif')})")
        check(m.get("zorluk") == "orta" and m.get("eslesme") == "sinif_zorluk",
              f"kur 2 → zorluk orta eşleşti (zorluk={m.get('zorluk')}, eslesme={m.get('eslesme')})")
        check("Beklemede" not in m.get("baslik", ""), "beklemede metin seçilmedi (yalnız havuzda)")

        # ── 3) Zorluk fallback: kur yok → orta hedefler; o sınıfta orta var, gelir ──
        #      Sınıf 4'te 'zor' hedefi kaldıralım: kur 9 → zor; sınıf 4'te zor VAR.
        await server.db.students.update_one({"id": ogr_rec}, {"$set": {"kur": "Kur 9"}})
        r = await ac.get("/api/kutulu-okuma/metin", headers=H_ogr)
        check(r.json().get("zorluk") == "zor", "kur 9 → zorluk zor eşleşmesi")

        # ── 4) Sinif-only fallback: sınıf 5'te sadece 'orta' var; kur 9 (zor) istenince sinif'e düşer ──
        await server.db.students.update_one({"id": ogr_rec}, {"$set": {"sinif": "5", "kur": "Kur 9"}})
        r = await ac.get("/api/kutulu-okuma/metin", headers=H_ogr)
        j = r.json()
        check(j.get("sinif") == "5" and j.get("eslesme") == "sinif",
              f"sınıf 5'te zor yok → sinif fallback (eslesme={j.get('eslesme')})")

        # ── 5) Eğitici query override: ?sinif=4&zorluk=kolay ──
        r = await ac.get("/api/kutulu-okuma/metin?sinif=4&zorluk=kolay", headers=H_admin)
        check(r.status_code == 200 and r.json().get("zorluk") == "kolay", "query override sinif=4 zorluk=kolay")

        # ── 6) create_metin otomatik zorluk etiketi ──
        r = await ac.post("/api/diagnostic/texts", headers=H_admin, json={
            "baslik": "Yeni Metin", "icerik": zor, "sinif_seviyesi": "6", "tur": "bilgilendirici", "kelime_sayisi": 0})
        check(r.status_code == 200, f"metin eklendi (status={r.status_code})")
        check(r.json().get("zorluk") in ("kolay", "orta", "zor"), f"yeni metne otomatik zorluk ({r.json().get('zorluk')})")

        # ── 7) Ayar varsayılanı + admin PUT ──
        r = await ac.get("/api/ayarlar/kutulu_okuma", headers=H_admin)
        check(r.json().get("degerler", {}).get("kutu_basi_kelime") == 1, "ayar varsayılanı kutu_basi_kelime=1")
        r = await ac.put("/api/ayarlar/kutulu_okuma", headers=H_admin, json={"degerler": {"kutu_basi_kelime": 3}})
        check(r.status_code == 200, "admin ayar kaydetti")
        r = await ac.get("/api/ayarlar/kutulu_okuma", headers=H_admin)
        check(r.json().get("degerler", {}).get("kutu_basi_kelime") == 3, "ayar 3 olarak güncellendi")

    await server.client.drop_database(TEST_DB)


def main():
    asyncio.run(run())
    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    sys.exit(0 if _kalan == 0 else 1)


if __name__ == "__main__":
    main()
