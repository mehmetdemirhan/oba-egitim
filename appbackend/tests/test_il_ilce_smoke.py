"""İl/İlçe alanları + Öğrenci Dağılımı haritası + toplu-kayit Şehir→il smoke testi.
    cd appbackend
    .venv/Scripts/python.exe tests/test_il_ilce_smoke.py
"""
import asyncio
import os
import sys

TEST_DB = "oba_test_il_ilce_smoke"
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
    from httpx import AsyncClient, ASGITransport

    db = server.db
    await server.client.drop_database(TEST_DB)
    await db.users.insert_one({"id": "adm", "role": "admin", "ad": "Ad", "soyad": "Min"})
    H = {"Authorization": f"Bearer {server.create_access_token({'sub': 'adm'})}"}

    def ogr(ad, il):
        return {"ad": ad, "soyad": "Ö", "sinif": "5", "veli_ad": "V", "veli_soyad": "L",
                "veli_telefon": "5", "aldigi_egitim": "Genel", "kur": "1", "il": il, "ilce": ""}

    async with AsyncClient(transport=ASGITransport(app=server.app), base_url="http://test") as ac:
        # 1) Öğrenci oluştur — il/ilce persist
        r = await ac.post("/api/students", headers=H, json={**ogr("Ali", "Bursa"), "ilce": "Nilüfer"})
        check(r.status_code == 200 and r.json().get("il") == "Bursa" and r.json().get("ilce") == "Nilüfer",
              "create: il/ilce kaydedildi")
        sid = r.json()["id"]

        # 2) Öğrenci güncelle (PUT) — il/ilce değişir
        r = await ac.put(f"/api/students/{sid}", headers=H, json={"il": "İzmir", "ilce": "Konak"})
        check(r.status_code == 200, "update PUT 200")
        s = await db.students.find_one({"id": sid})
        check(s.get("il") == "İzmir" and s.get("ilce") == "Konak", "update: il/ilce güncellendi")

        # 3) Birden fazla ilde öğrenci → dağılım
        for ad, il in [("B", "İstanbul"), ("C", "İstanbul"), ("D", "Ankara")]:
            await ac.post("/api/students", headers=H, json=ogr(ad, il))

        # 4) turkiye-harita: ogrenci_sayisi + toplam + en yoğun
        r = await ac.get("/api/istatistik/turkiye-harita", headers=H)
        check(r.status_code == 200, "harita ucu 200")
        j = r.json()
        check(j.get("toplam_ogrenci") == 4, f"toplam öğrenci=4 ({j.get('toplam_ogrenci')})")
        ist = next((i for i in j["iller"] if i["il"] == "İstanbul"), None)
        check(ist and ist.get("ogrenci_sayisi") == 2, "İstanbul ogrenci_sayisi=2")
        en_yogun = j.get("en_yogun_iller", [])
        check(len(en_yogun) >= 1 and en_yogun[0]["il"] == "İstanbul" and en_yogun[0]["ogrenci_sayisi"] == 2,
              f"en yoğun il İstanbul (2) ({en_yogun[:1]})")

        # 5) Arşivli öğrenci dağılıma dahil değil
        await ac.put(f"/api/students/{sid}", headers=H, json={"arsivli": True})
        r = await ac.get("/api/istatistik/turkiye-harita", headers=H)
        izmir = next((i for i in r.json()["iller"] if i["il"] == "İzmir"), None)
        check(izmir is None or izmir.get("ogrenci_sayisi") == 0, "arşivli öğrenci dağılımda yok")

        # 6) Toplu-kayit Şehir→il eşlemesi (kolon 10) — norm çıktısı il taşır
        from modules.toplu_kayit import _satir_isle, _VARSAYILAN_KOLON
        check(_VARSAYILAN_KOLON.get("il") == 10, "toplu kolon eşlemesinde il=10")
        satir = ["01.01.2025", "Öğretmen A", "Ahmet Yılmaz", "5", "1", "Veli A", "", "5551112233", "", "aktif", "Trabzon"]
        sonuc = _satir_isle(satir, _VARSAYILAN_KOLON, {}, 1)
        il_norm = (sonuc or {}).get("norm", {}).get("il")
        check(il_norm == "Trabzon", f"toplu Şehir→il: {il_norm}")

    await server.client.drop_database(TEST_DB)


def main():
    asyncio.run(run())
    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    sys.exit(0 if _kalan == 0 else 1)


if __name__ == "__main__":
    main()
