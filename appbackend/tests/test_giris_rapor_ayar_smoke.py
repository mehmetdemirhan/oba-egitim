"""Giriş Analizi rapor ayarları smoke: metin bankası (A) + sınıf kategorileri (EK).

Kapsar:
- GET/PUT/reset /diagnostic/rapor-metinleri (admin/koord); öğretmen 403.
- GET/PUT /diagnostic/sinif-kategorileri; GET /diagnostic/anlama-gruplari (sınıfa göre).
- Varsayılan: 1. sınıf → 4.1-4.4 pasif; 3. sınıf → hepsi aktif.
- Etiket haritaları (B/C) ve sonuç paragrafı (A) birim testi.

İzole test DB'sine karşı çalışır.
    cd appbackend && .venv/Scripts/python.exe tests/test_giris_rapor_ayar_smoke.py
"""
import asyncio, os, sys, uuid

TEST_DB = "oba_test_giris_rapor_ayar"
os.environ["MONGO_URL"] = os.environ.get("MONGO_URL_TEST", "mongodb://localhost:27017")
os.environ["DB_NAME"] = TEST_DB
os.environ.setdefault("SECRET_KEY", "test-secret-key")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_g = 0; _k = 0
def check(k, m):
    global _g, _k
    _g += 1 if k else 0; _k += 0 if k else 1
    print(f"  [{'GECTI' if k else 'KALDI'}] {m}")


async def run():
    import server
    import core.giris_rapor as G
    from core.auth import create_access_token
    from httpx import AsyncClient, ASGITransport
    await server.client.drop_database(TEST_DB)

    # Birim: etiketler (B/C) + sonuç paragrafı (A)
    check(G.metin_turu_ad("olcum") == "Ölçüm Metni" and G.metin_turu_ad("OLCUM") == "Ölçüm Metni", "B: metin türü etiketi")
    check(G.hata_turu_ad("harf_atlama") == "Harf Atlama" and G.hata_turu_ad("kendi_kendine_duzeltme") == "Kendi Kendine Düzeltme", "C: hata etiketi")
    check(G.pasif_gruplar(None, 1) == {"4.1", "4.2", "4.3", "4.4"} and G.pasif_gruplar(None, 3) == set(), "EK: varsayılan pasif gruplar")
    r = {"ogrenci_ad": "Ela", "hiz_deger": "yeterli", "dogruluk_yuzde": 91, "anlama_yuzde": 78, "prozodik_toplam": 17}
    p3 = " ".join(G.sonuc_paragrafi_uret(r, None, True)); p1 = " ".join(G.sonuc_paragrafi_uret(r, None, False))
    check("Ela" in p3 and "Önerilen adım" in p3, "A: paragraf ad + öneri")
    check("Okuduğunu anlama" in p3 and "Okuduğunu anlama" not in p1, "A: 1. sınıfta anlama cümlesi yok")

    admin = str(uuid.uuid4()); teacher = str(uuid.uuid4())
    await server.db.users.insert_one({"id": admin, "role": "admin", "ad": "Ad", "soyad": "Min"})
    await server.db.users.insert_one({"id": teacher, "role": "teacher"})
    HA = {"Authorization": f"Bearer {create_access_token({'sub': admin})}"}
    HT = {"Authorization": f"Bearer {create_access_token({'sub': teacher})}"}

    transport = ASGITransport(app=server.app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Metin bankası
        r = await ac.get("/api/diagnostic/rapor-metinleri", headers=HA)
        check(r.status_code == 200 and "giris" in r.json().get("metinler", {}), "metin bankası GET")
        check((await ac.get("/api/diagnostic/rapor-metinleri", headers=HT)).status_code == 403, "öğretmen metin bankası göremez")
        yeni = r.json()["metinler"]; yeni["giris"] = "ÖZEL GİRİŞ {ad}."
        pr = await ac.put("/api/diagnostic/rapor-metinleri", json={"metinler": yeni}, headers=HA)
        check(pr.status_code == 200, "metin bankası PUT")
        r2 = await ac.get("/api/diagnostic/rapor-metinleri", headers=HA)
        check(r2.json()["metinler"]["giris"] == "ÖZEL GİRİŞ {ad}.", "kaydedilen metin okunuyor")
        rr = await ac.post("/api/diagnostic/rapor-metinleri/varsayilana-don", headers=HA)
        r3 = await ac.get("/api/diagnostic/rapor-metinleri", headers=HA)
        check(rr.status_code == 200 and r3.json()["metinler"]["giris"] != "ÖZEL GİRİŞ {ad}.", "varsayılana dön")

        # Sınıf kategorileri
        r = await ac.get("/api/diagnostic/sinif-kategorileri", headers=HA)
        check(r.status_code == 200 and r.json()["kategoriler"].get("1") == ["4.1", "4.2", "4.3", "4.4"], "sınıf kategorileri varsayılan")
        pr = await ac.put("/api/diagnostic/sinif-kategorileri", json={"kategoriler": {"1": ["4.1", "4.2"]}}, headers=HA)
        check(pr.status_code == 200, "sınıf kategorileri PUT")

        # Anlama grupları (form için)
        r1 = await ac.get("/api/diagnostic/anlama-gruplari?sinif=1", headers=HT)
        check(r1.status_code == 200 and set(r1.json()["pasif"]) == {"4.1", "4.2"}, f"1. sınıf pasif=4.1,4.2 ({r1.json()})")
        r3g = await ac.get("/api/diagnostic/anlama-gruplari?sinif=3", headers=HT)
        check("4.5" in r3g.json()["aktif"] and not r3g.json()["pasif"], "3. sınıf hepsi aktif")

    print(f"\nSONUC: {_g}/{_g + _k} kontrol gecti")
    await server.client.drop_database(TEST_DB)
    return _k == 0


if __name__ == "__main__":
    sys.exit(0 if asyncio.run(run()) else 1)
