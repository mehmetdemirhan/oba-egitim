"""Egzersiz Motoru (/egzersiz/* yeni motor) smoke testi.

Tip listesi → içerik üret → oturum başlat → cevap → bitir → geçmiş → içerikler
akışını uçtan uca doğrular. AI key yokken mock içerik kullanılır (deterministik).
İzole test DB'sine karşı çalışır.
    cd appbackend
    .venv/Scripts/python.exe tests/test_egzersiz_motoru_smoke.py
"""
import asyncio
import os
import sys
import uuid

TEST_DB = "oba_test_egzersiz_motoru_smoke"
os.environ["MONGO_URL"] = os.environ.get("MONGO_URL_TEST", "mongodb://localhost:27017")
os.environ["DB_NAME"] = TEST_DB
os.environ.setdefault("SECRET_KEY", "test-secret-key")
# AI key'lerini boşalt → deterministik mock içerik (load_dotenv mevcut env'i ezmez)
for _k in ("GEMINI_API_KEY", "GEMINI_API_KEY_2", "GEMINI_API_KEY_3", "ANTHROPIC_API_KEY"):
    os.environ[_k] = ""
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

    uid = str(uuid.uuid4())
    await server.db.users.insert_one({"id": uid, "ad": "Ogr", "soyad": "Test", "role": "student"})
    await server.db.students.insert_one({"id": uid, "ad": "Ogr", "soyad": "Test", "sinif": 3, "toplam_xp": 0})
    H = {"Authorization": f"Bearer {create_access_token({'sub': uid})}"}

    # Kütüphane endpoint'leri için öğretmen + admin kullanıcıları
    ogr_id = str(uuid.uuid4())
    await server.db.users.insert_one({"id": ogr_id, "ad": "Ayse", "soyad": "Ogretmen", "role": "teacher"})
    HT = {"Authorization": f"Bearer {create_access_token({'sub': ogr_id})}"}
    adm_id = str(uuid.uuid4())
    await server.db.users.insert_one({"id": adm_id, "ad": "Yonetici", "soyad": "Admin", "role": "admin"})
    HA = {"Authorization": f"Bearer {create_access_token({'sub': adm_id})}"}

    transport = ASGITransport(app=server.app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Tip listesi
        r = await ac.get("/api/egzersiz/tipler", headers=H)
        check(r.status_code == 200, f"tipler 200 (status={r.status_code})")
        tipler = r.json().get("tipler", [])
        check(any(t["id"] == "demo" for t in tipler), "demo tipi listede")

        # sınıf filtresi
        r = await ac.get("/api/egzersiz/tipler?sinif=3", headers=H)
        check(r.status_code == 200 and any(t["id"] == "demo" for t in r.json()["tipler"]), "sınıf filtresi çalıştı")

        # 2. İçerik üret
        r = await ac.post("/api/egzersiz/uret", json={"tip": "demo", "sinif": 3}, headers=H)
        check(r.status_code == 200, f"içerik üret 200 (status={r.status_code})")
        icerik_doc = r.json()
        check("sorular" in icerik_doc.get("icerik", {}) and len(icerik_doc["icerik"]["sorular"]) == 3, "üretilen içerikte 3 soru var")
        icerik_id = icerik_doc["id"]

        # bilinmeyen tip reddedilir
        r = await ac.post("/api/egzersiz/uret", json={"tip": "yok_boyle", "sinif": 3}, headers=H)
        check(r.status_code == 400, "bilinmeyen tip 400 döndü")

        # 3. Oturum başlat (verilen içerikle)
        r = await ac.post("/api/egzersiz/oturum", json={"tip": "demo", "sinif": 3, "icerik_id": icerik_id}, headers=H)
        check(r.status_code == 200, f"oturum başlat 200 (status={r.status_code})")
        oturum = r.json()
        oturum_id = oturum["oturum_id"]
        check(oturum["toplam_soru"] == 3, "oturum toplam_soru=3")

        # 4. Cevap — doğru (mock'ta soru 0'ın doğrusu indeks 0)
        r = await ac.post(f"/api/egzersiz/oturum/{oturum_id}/cevap", json={"soru_no": 0, "cevap": 0}, headers=H)
        check(r.status_code == 200 and r.json()["dogru"] is True, "doğru cevap doğru işaretlendi")
        # Cevap — yanlış (soru 1'in doğrusu indeks 1, biz 3 veriyoruz)
        r = await ac.post(f"/api/egzersiz/oturum/{oturum_id}/cevap", json={"soru_no": 1, "cevap": 3}, headers=H)
        check(r.status_code == 200 and r.json()["dogru"] is False, "yanlış cevap yanlış işaretlendi")

        # 5. Bitir
        r = await ac.post(f"/api/egzersiz/oturum/{oturum_id}/bitir", json={"sure_sn": 42}, headers=H)
        check(r.status_code == 200, f"bitir 200 (status={r.status_code})")
        sonuc = r.json()
        check(sonuc["dogru_sayisi"] == 1 and sonuc["toplam_soru"] == 3, "puanlama doğru (1/3)")
        check(sonuc["xp"] >= 0, "xp hesaplandı")

        # XP öğrenciye eklendi mi
        st = await server.db.students.find_one({"id": uid})
        check(st.get("toplam_xp", 0) == sonuc["xp"], "XP öğrenciye eklendi")

        # 6. Geçmiş
        r = await ac.get(f"/api/egzersiz/gecmis/{uid}", headers=H)
        check(r.status_code == 200 and len(r.json()["oturumlar"]) == 1, "geçmişte 1 oturum")
        check(r.json()["oturumlar"][0]["durum"] == "tamamlandi", "oturum tamamlandı")

        # 7. İçerikler (kütüphane) — öğrenci 403, öğretmen 200
        r = await ac.get("/api/egzersiz/icerikler?tip=demo&sinif=3", headers=H)
        check(r.status_code == 403, "öğrenci kütüphaneye erişemez (403)")
        r = await ac.get("/api/egzersiz/icerikler?tip=demo&sinif=3", headers=HT)
        check(r.status_code == 200 and len(r.json()["icerikler"]) >= 1, "öğretmen içerikleri listeledi")
        check("toplam" in r.json() and "sayfa" in r.json(), "kütüphane sayfalama alanları döndü")

        # ── FAZ 1: Tier 1 tipleri (eslesme + sira grader yolları) ──
        r = await ac.get("/api/egzersiz/tipler", headers=H)
        tip_idler = {t["id"] for t in r.json()["tipler"]}
        for beklenen in ("kelime_anlam_eslestirme", "cloze_bosluk_doldurma",
                         "es_karsit_anlamli", "karisik_cumle_siralama", "hikaye_olay_siralama"):
            check(beklenen in tip_idler, f"{beklenen} listede")

        # Eşleştirme (puanlama=eslesme): doğru anlam eşleşmesi doğru işaretlenir
        r = await ac.post("/api/egzersiz/uret", json={"tip": "kelime_anlam_eslestirme", "sinif": 3}, headers=H)
        check(r.status_code == 200, f"eslestirme üret 200 (status={r.status_code})")
        es = r.json()
        ciftler = es["icerik"]["ciftler"]
        check(len(ciftler) >= 2, "eslestirmede en az 2 çift")
        r = await ac.post("/api/egzersiz/oturum",
                          json={"tip": "kelime_anlam_eslestirme", "sinif": 3, "icerik_id": es["id"]}, headers=H)
        check(r.json()["toplam_soru"] == len(ciftler), "eslestirme toplam_soru = çift sayısı")
        es_oturum = r.json()["oturum_id"]
        r = await ac.post(f"/api/egzersiz/oturum/{es_oturum}/cevap",
                          json={"soru_no": 0, "cevap": {"sol": 0, "sag": ciftler[0]["sag"]}}, headers=H)
        check(r.status_code == 200 and r.json()["dogru"] is True, "eslestirme doğru eşleşme doğru işaretlendi")

        # Sıralama (puanlama=sira): tek soru, doğru sıra doğru işaretlenir
        r = await ac.post("/api/egzersiz/uret", json={"tip": "karisik_cumle_siralama", "sinif": 3}, headers=H)
        sr = r.json()
        dogru_sira = sr["icerik"]["dogru_sira"]
        r = await ac.post("/api/egzersiz/oturum",
                          json={"tip": "karisik_cumle_siralama", "sinif": 3, "icerik_id": sr["id"]}, headers=H)
        check(r.json()["toplam_soru"] == 1, "sıralama toplam_soru = 1")
        sr_oturum = r.json()["oturum_id"]
        r = await ac.post(f"/api/egzersiz/oturum/{sr_oturum}/cevap",
                          json={"soru_no": 0, "cevap": dogru_sira}, headers=H)
        check(r.status_code == 200 and r.json()["dogru"] is True, "sıralama doğru sıra doğru işaretlendi")

        # ── FAZ 2: Tier 2 (okuduğunu anlama, metin + secmeli) ──
        r = await ac.get("/api/egzersiz/tipler", headers=H)
        tip_idler = {t["id"] for t in r.json()["tipler"]}
        for beklenen in ("bes_n_bir_k", "ana_fikir", "cikarim", "sebep_sonuc", "tahmin_et"):
            check(beklenen in tip_idler, f"{beklenen} listede")

        # 5N1K üret: metin + sorular gelir; oturum + doğru cevap doğru işaretlenir
        r = await ac.post("/api/egzersiz/uret", json={"tip": "bes_n_bir_k", "sinif": 3}, headers=H)
        check(r.status_code == 200, f"5n1k üret 200 (status={r.status_code})")
        t2 = r.json()
        check("metin" in t2["icerik"] and len(t2["icerik"]["metin"]) > 0, "5n1k içeriğinde metin var")
        sorular2 = t2["icerik"]["sorular"]
        check(len(sorular2) >= 1, "5n1k en az 1 soru")
        r = await ac.post("/api/egzersiz/oturum",
                          json={"tip": "bes_n_bir_k", "sinif": 3, "icerik_id": t2["id"]}, headers=H)
        check(r.json()["toplam_soru"] == len(sorular2), "5n1k toplam_soru = soru sayısı")
        t2_oturum = r.json()["oturum_id"]
        r = await ac.post(f"/api/egzersiz/oturum/{t2_oturum}/cevap",
                          json={"soru_no": 0, "cevap": sorular2[0]["dogru"]}, headers=H)
        check(r.status_code == 200 and r.json()["dogru"] is True, "5n1k doğru cevap doğru işaretlendi")

        # ── FAZ 3: Tier 3 (kelime oyunları — serbest + secmeli) ──
        r = await ac.get("/api/egzersiz/tipler", headers=H)
        tip_idler = {t["id"] for t in r.json()["tipler"]}
        for beklenen in ("anagram", "bulmaca", "hafiza_karti", "kelime_yagmuru",
                         "kelime_merdiveni", "baglam_ipucu"):
            check(beklenen in tip_idler, f"{beklenen} listede")

        # Anagram (puanlama=serbest): tek puanlama; istemci doğru der → dogru True
        r = await ac.post("/api/egzersiz/uret", json={"tip": "anagram", "sinif": 3}, headers=H)
        check(r.status_code == 200, f"anagram üret 200 (status={r.status_code})")
        ag = r.json()
        check("kelime" in ag["icerik"], "anagram içeriğinde kelime var")
        r = await ac.post("/api/egzersiz/oturum",
                          json={"tip": "anagram", "sinif": 3, "icerik_id": ag["id"]}, headers=H)
        check(r.json()["toplam_soru"] == 1, "anagram toplam_soru = 1 (serbest)")
        ag_oturum = r.json()["oturum_id"]
        r = await ac.post(f"/api/egzersiz/oturum/{ag_oturum}/cevap",
                          json={"soru_no": 0, "cevap": True}, headers=H)
        check(r.status_code == 200 and r.json()["dogru"] is True, "anagram serbest doğru işaretlendi")

        # Hafıza kartları (serbest): içerikte ciftler var
        r = await ac.post("/api/egzersiz/uret", json={"tip": "hafiza_karti", "sinif": 3}, headers=H)
        check(r.status_code == 200 and len(r.json()["icerik"].get("ciftler", [])) >= 2, "hafiza_karti çiftleri üretildi")

        # Kelime yağmuru (serbest): dogrular + yanlislar
        r = await ac.post("/api/egzersiz/uret", json={"tip": "kelime_yagmuru", "sinif": 3}, headers=H)
        yg = r.json()["icerik"]
        check(len(yg.get("dogrular", [])) >= 1 and len(yg.get("yanlislar", [])) >= 1, "kelime_yagmuru doğru/yanlış kelimeler var")

        # Bulmaca (serbest): ipucu-kelime listesi
        r = await ac.post("/api/egzersiz/uret", json={"tip": "bulmaca", "sinif": 3}, headers=H)
        check(len(r.json()["icerik"].get("kelimeler", [])) >= 1, "bulmaca öğeleri üretildi")

        # Kelime merdiveni (secmeli): standart çoktan seçmeli akış
        r = await ac.post("/api/egzersiz/uret", json={"tip": "kelime_merdiveni", "sinif": 4}, headers=H)
        md = r.json()
        sorular_md = md["icerik"]["sorular"]
        check(len(sorular_md) >= 1, "kelime_merdiveni soruları üretildi")
        r = await ac.post("/api/egzersiz/oturum",
                          json={"tip": "kelime_merdiveni", "sinif": 4, "icerik_id": md["id"]}, headers=H)
        md_oturum = r.json()["oturum_id"]
        r = await ac.post(f"/api/egzersiz/oturum/{md_oturum}/cevap",
                          json={"soru_no": 0, "cevap": sorular_md[0]["dogru"]}, headers=H)
        check(r.status_code == 200 and r.json()["dogru"] is True, "kelime_merdiveni doğru cevap işaretlendi")

        # ── FAZ 4: Tier 4 (gelişmiş beceriler — hepsi secmeli) ──
        r = await ac.get("/api/egzersiz/tipler", headers=H)
        tip_idler = {t["id"] for t in r.json()["tipler"]}
        for beklenen in ("frayer", "anlam_haritasi", "venn", "tekerleme", "sight_words", "diyalog"):
            check(beklenen in tip_idler, f"{beklenen} listede")

        # Frayer: kelime + sorular; oturum + doğru cevap
        r = await ac.post("/api/egzersiz/uret", json={"tip": "frayer", "sinif": 4}, headers=H)
        check(r.status_code == 200 and "kelime" in r.json()["icerik"], "frayer kelime alanı üretildi")
        fr = r.json()
        sorular_fr = fr["icerik"]["sorular"]
        r = await ac.post("/api/egzersiz/oturum",
                          json={"tip": "frayer", "sinif": 4, "icerik_id": fr["id"]}, headers=H)
        check(r.json()["toplam_soru"] == len(sorular_fr), "frayer toplam_soru = soru sayısı")
        fr_oturum = r.json()["oturum_id"]
        r = await ac.post(f"/api/egzersiz/oturum/{fr_oturum}/cevap",
                          json={"soru_no": 0, "cevap": sorular_fr[0]["dogru"]}, headers=H)
        check(r.status_code == 200 and r.json()["dogru"] is True, "frayer doğru cevap işaretlendi")

        # Venn: a + b + sorular
        r = await ac.post("/api/egzersiz/uret", json={"tip": "venn", "sinif": 4}, headers=H)
        vn = r.json()["icerik"]
        check("a" in vn and "b" in vn and len(vn.get("sorular", [])) >= 1, "venn a/b/sorular üretildi")

        # Anlam haritası: merkez
        r = await ac.post("/api/egzersiz/uret", json={"tip": "anlam_haritasi", "sinif": 3}, headers=H)
        check("merkez" in r.json()["icerik"], "anlam_haritasi merkez üretildi")

        # Diyalog: metin + sorular (metinli)
        r = await ac.post("/api/egzersiz/uret", json={"tip": "diyalog", "sinif": 3}, headers=H)
        dg = r.json()["icerik"]
        check("metin" in dg and len(dg.get("sorular", [])) >= 1, "diyalog metin + sorular üretildi")

        # Tekerleme: metin + sorular
        r = await ac.post("/api/egzersiz/uret", json={"tip": "tekerleme", "sinif": 2}, headers=H)
        check("metin" in r.json()["icerik"], "tekerleme metin üretildi")

        # Sight words: sorular
        r = await ac.post("/api/egzersiz/uret", json={"tip": "sight_words", "sinif": 2}, headers=H)
        check(len(r.json()["icerik"].get("sorular", [])) >= 1, "sight_words soruları üretildi")

        # ── FAZ 5: Fonolojik farkındalık (7 alt tip, secmeli + seslendir) ──
        # Tüm fonoloji tipleri (sınıf filtresiz tam liste) kayıtlı mı?
        r = await ac.get("/api/egzersiz/tipler", headers=H)
        tip_idler = {t["id"] for t in r.json()["tipler"]}
        fon_tipler = ("hece_sayma", "hece_birlestirme", "ilk_ses", "son_ses",
                      "kafiye", "ses_birlestirme", "ses_cikarma")
        for beklenen in fon_tipler:
            check(beklenen in tip_idler, f"{beklenen} listede")

        # Sınıf filtresi: ses_cikarma (sinif_min=2) 1. sınıfta GÖRÜNMEZ, 2. sınıfta görünür
        r1 = {t["id"] for t in (await ac.get("/api/egzersiz/tipler?sinif=1", headers=H)).json()["tipler"]}
        check("ilk_ses" in r1 and "ses_cikarma" not in r1, "1. sınıf filtresi doğru (ilk_ses var, ses_cikarma yok)")
        r2 = {t["id"] for t in (await ac.get("/api/egzersiz/tipler?sinif=2", headers=H)).json()["tipler"]}
        check("ses_cikarma" in r2, "ses_cikarma 2. sınıf listesinde")

        # Her fonoloji tipi: üret → seslendir alanı var → oturum → doğru cevap (grade 2 hepsine uyar)
        for tip in fon_tipler:
            r = await ac.post("/api/egzersiz/uret", json={"tip": tip, "sinif": 2}, headers=H)
            check(r.status_code == 200, f"{tip} üret 200 (status={r.status_code})")
            doc = r.json()
            sorular_f = doc["icerik"]["sorular"]
            check(len(sorular_f) >= 1 and "seslendir" in sorular_f[0], f"{tip} seslendir alanı var")
            r = await ac.post("/api/egzersiz/oturum",
                              json={"tip": tip, "sinif": 2, "icerik_id": doc["id"]}, headers=H)
            ot = r.json()["oturum_id"]
            r = await ac.post(f"/api/egzersiz/oturum/{ot}/cevap",
                              json={"soru_no": 0, "cevap": sorular_f[0]["dogru"]}, headers=H)
            check(r.status_code == 200 and r.json()["dogru"] is True, f"{tip} doğru cevap işaretlendi")

        # ── Cache stratejisi: icerik_id verilmeden oturum cache'ten içerik kullanır ──
        # İzole bir (tip, sınıf) hazırla: tek içerik üret, sonra icerik_id'siz oturum aç.
        r = await ac.post("/api/egzersiz/uret", json={"tip": "demo", "sinif": 7}, headers=H)
        cache_id = r.json()["id"]
        adet_once = await server.db.egzersiz_icerikler.count_documents({"tip": "demo", "sinif": 7})
        check(adet_once == 1, "cache: demo s7 için tek içerik var")
        # icerik_id VERİLMEDEN oturum → cache'teki içerik yeniden kullanılmalı (yeni üretim YOK)
        r = await ac.post("/api/egzersiz/oturum", json={"tip": "demo", "sinif": 7}, headers=H)
        check(r.json().get("icerik_id") == cache_id, "cache: oturum mevcut içeriği yeniden kullandı")
        adet_sonra = await server.db.egzersiz_icerikler.count_documents({"tip": "demo", "sinif": 7})
        check(adet_sonra == 1, "cache: yeni içerik ÜRETİLMEDİ (AI çağrısı atlandı)")
        # kullanım sayısı arttı mı (en az kullanılan seçimi için)
        secilen = await server.db.egzersiz_icerikler.find_one({"id": cache_id})
        check(secilen.get("kullanim_sayisi", 0) >= 1, "cache: kullanım sayısı arttı")
        check(secilen.get("son_kullanim_tarihi"), "cache: son_kullanim_tarihi damgalandı")

        # ── KÜTÜPHANE: varyant üret / detay / arşivle / sil ──
        # Bir orijinal içerik üret (es_karsit_anlamli s4)
        r = await ac.post("/api/egzersiz/uret", json={"tip": "es_karsit_anlamli", "sinif": 4}, headers=H)
        orijinal_id = r.json()["id"]
        # Yeni kayıtta kütüphane alanları var mı
        od = await server.db.egzersiz_icerikler.find_one({"id": orijinal_id})
        check(od.get("durum") == "aktif", "kütüphane: yeni içerik durum=aktif")
        check(od.get("varyant_grubu") == orijinal_id, "kütüphane: orijinalin varyant_grubu kendi id'si")

        # Varyant üret — öğrenci 403, öğretmen 200
        r = await ac.post(f"/api/egzersiz/icerik/{orijinal_id}/varyant-uret", headers=H)
        check(r.status_code == 403, "varyant üret: öğrenci 403")
        r = await ac.post(f"/api/egzersiz/icerik/{orijinal_id}/varyant-uret", headers=HT)
        check(r.status_code == 200, f"varyant üret: öğretmen 200 (status={r.status_code})")
        varyant = r.json()
        check(varyant["id"] != orijinal_id, "varyant: yeni id üretildi")
        check(varyant["varyant_grubu"] == orijinal_id, "varyant: aynı varyant grubunda")
        check(varyant.get("olusturan_rol") == "teacher", "varyant: olusturan_rol=teacher")
        # Orijinal hâlâ aktif (arşivlenmedi)
        od2 = await server.db.egzersiz_icerikler.find_one({"id": orijinal_id})
        check(od2.get("durum") == "aktif", "varyant: orijinal aktif kaldı (silinmedi/arşivlenmedi)")

        # Detay + kardeşler (en az 2 varyant)
        r = await ac.get(f"/api/egzersiz/icerik/{orijinal_id}", headers=HT)
        check(r.status_code == 200 and r.json().get("varyant_sayisi", 0) >= 2, "detay: kardeş varyantlar listelendi")
        check(any(k["kendisi"] for k in r.json()["kardesler"]), "detay: kendisi işaretlendi")

        # Arşivle — öğretmen 403, admin 200
        r = await ac.patch(f"/api/egzersiz/icerik/{varyant['id']}/arsivle", headers=HT)
        check(r.status_code == 403, "arşivle: öğretmen 403 (sadece admin)")
        r = await ac.patch(f"/api/egzersiz/icerik/{varyant['id']}/arsivle", headers=HA)
        check(r.status_code == 200, f"arşivle: admin 200 (status={r.status_code})")
        arsiv = await server.db.egzersiz_icerikler.find_one({"id": varyant["id"]})
        check(arsiv.get("durum") == "arsivli", "arşivle: durum=arsivli oldu")
        # Aktif listede artık görünmemeli, arsivli filtresinde görünmeli
        r = await ac.get("/api/egzersiz/icerikler?tip=es_karsit_anlamli&sinif=4&durum=aktif", headers=HT)
        aktif_idler = {i["id"] for i in r.json()["icerikler"]}
        check(varyant["id"] not in aktif_idler, "arşivle: aktif listede yok")
        r = await ac.get("/api/egzersiz/icerikler?tip=es_karsit_anlamli&sinif=4&durum=arsivli", headers=HT)
        check(varyant["id"] in {i["id"] for i in r.json()["icerikler"]}, "arşivle: arşivli listede var")

        # Sil — öğretmen 403, admin 200 (hard delete)
        r = await ac.delete(f"/api/egzersiz/icerik/{varyant['id']}", headers=HT)
        check(r.status_code == 403, "sil: öğretmen 403 (sadece admin)")
        r = await ac.delete(f"/api/egzersiz/icerik/{varyant['id']}", headers=HA)
        check(r.status_code == 200, f"sil: admin 200 (status={r.status_code})")
        check(await server.db.egzersiz_icerikler.find_one({"id": varyant["id"]}) is None, "sil: kayıt DB'den kalktı")

        # Bilinmeyen içerik → 404
        r = await ac.get("/api/egzersiz/icerik/yok_boyle_id", headers=HT)
        check(r.status_code == 404, "detay: bilinmeyen içerik 404")

    await server.client.drop_database(TEST_DB)


def main():
    asyncio.run(run())
    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    sys.exit(0 if _kalan == 0 else 1)


if __name__ == "__main__":
    main()
