"""Görev içerik havuzu + film scraping + izle linki smoke testi.

Film scraping mock ile (başarılı + başarısız); havuza film ekleme + film alanları;
görevde izle linki (tekil + toplu).
    cd appbackend
    .venv/Scripts/python.exe tests/test_gorev_icerik_smoke.py
"""
import asyncio
import os
import sys
import urllib.request

TEST_DB = "oba_test_gorev_icerik_smoke"
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


class _FakeResp:
    def __init__(self, html):
        self._b = html.encode("utf-8")
    def read(self):
        return self._b
    def __enter__(self):
        return self
    def __exit__(self, *a):
        return False


FILM_HTML = """
<html><head>
<title>Esaretin Bedeli (1994) - sinemalar.com</title>
<meta property="og:title" content="Esaretin Bedeli (1994)" />
<meta property="og:description" content="Umut, iyi bir şeydir ve iyi şeyler asla ölmez." />
<meta property="og:image" content="https://sinemalar.com/afis/esaret.jpg" />
</head><body>Süre: 142 dakika</body></html>
"""


async def run():
    import server
    from httpx import AsyncClient, ASGITransport

    db = server.db
    await server.client.drop_database(TEST_DB)
    await db.users.insert_one({"id": "adm", "role": "admin", "ad": "Ad", "soyad": "Min"})
    await db.users.insert_one({"id": "ogr", "role": "student", "ad": "Öğ", "soyad": "R"})
    await db.students.insert_one({"id": "ogr", "ad": "Öğ", "soyad": "R"})
    H = {"Authorization": f"Bearer {server.create_access_token({'sub': 'adm'})}"}

    async with AsyncClient(transport=ASGITransport(app=server.app), base_url="http://test") as ac:
        # 1) Film scraping BAŞARILI (urlopen mock'lanır)
        orij = urllib.request.urlopen
        urllib.request.urlopen = lambda *a, **k: _FakeResp(FILM_HTML)
        try:
            r = await ac.post("/api/film-bilgi-cek", headers=H, json={"link": "https://www.sinemalar.com/film/123/esaretin-bedeli"})
        finally:
            urllib.request.urlopen = orij
        j = r.json()
        check(r.status_code == 200 and j.get("baslik") == "Esaretin Bedeli", f"scraping başlık ({j.get('baslik')})")
        check(j.get("yil") == "1994", f"scraping yıl ({j.get('yil')})")
        check("142" in (j.get("sure") or ""), f"scraping süre ({j.get('sure')})")
        check(j.get("gorsel", "").endswith("esaret.jpg"), "scraping afiş görseli")
        check("Umut" in (j.get("ozet") or ""), "scraping özet")

        # 2) Film scraping BAŞARISIZ (erişilemeyen) → boş, 200 (hata değil)
        r = await ac.post("/api/film-bilgi-cek", headers=H, json={"link": "https://yok-12345.invalid/x"})
        check(r.status_code == 200 and r.json().get("baslik") == "", "başarısız çekim → boş (hata değil)")

        # 3) Havuza film ekle (film alanlarıyla) → persist + GET film alanlarını döndürür
        r = await ac.post("/api/gelisim/icerik", headers=H, json={
            "baslik": "Esaretin Bedeli", "tur": "film", "aciklama": "Umut...", "hedef_kitle": "ogrenci",
            "film_link": "https://www.sinemalar.com/film/123",
            "film_izle_link": "https://youtube.com/watch?v=abc",
            "film_gorsel": "https://sinemalar.com/afis/esaret.jpg", "film_yil": "1994", "film_sure": "142 dk"})
        check(r.status_code == 200, "havuza film eklendi")
        icerik = await db.gelisim_icerik.find_one({"baslik": "Esaretin Bedeli", "tur": "film"})
        check(icerik and icerik.get("film_izle_link", "").endswith("abc"), "havuzda film_izle_link kaydedildi")

        # 4) GET /gelisim/icerik film alanlarını döndürüyor (havuzdan seçim için)
        await db.gelisim_icerik.update_one({"id": icerik["id"]}, {"$set": {"durum": "yayinda"}})
        r = await ac.get("/api/gelisim/icerik", headers=H)
        film = next((x for x in r.json() if x.get("tur") == "film"), None)
        check(film and film.get("film_gorsel"), "GET içerik film alanlarını (görsel) döndürüyor")

        # 5) Görev (tekil) izle linkiyle → öğrenciye izle_link taşınır
        r = await ac.post("/api/gorevler", headers=H, json={
            "hedef_id": "ogr", "hedef_tip": "ogrenci", "baslik": "Film izle", "tur": "film",
            "film_link": "https://www.sinemalar.com/film/123",
            "film_izle_link": "https://youtube.com/watch?v=abc"})
        check(r.status_code == 200 and r.json().get("film_izle_link", "").endswith("abc"), "tekil görevde izle linki")

        # 6) Görev (toplu) izle linkiyle
        r = await ac.post("/api/gorevler/toplu", headers=H, json={
            "hedef_tip": "ogrenci", "hedef_idler": ["ogr"],
            "gorev": {"baslik": "Toplu film", "tur": "film", "film_izle_link": "https://youtube.com/watch?v=xyz"}})
        check(r.status_code == 200, "toplu görev 200")
        g = await db.gorevler.find_one({"baslik": "Toplu film"})
        check(g and g.get("film_izle_link", "").endswith("xyz"), "toplu görevde izle linki")

    await server.client.drop_database(TEST_DB)


def main():
    asyncio.run(run())
    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    sys.exit(0 if _kalan == 0 else 1)


if __name__ == "__main__":
    main()
