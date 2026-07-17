"""AI CEO modülü — kapsamlı smoke testi (Ayda + Miran).

Kapsar: sistem fotoğrafı + otonom envanter (yeni koleksiyon otomatik); KVKK payload
kişisel-veri taraması; Gemini MOCK analiz→parse→sakla + dayanak doğrulama (güçlü/zayıf);
mektup ONAYSIZ gönderilemez (API seviyesinde); Miran üslup guard (kıyas/tutar) + öğretmen
yalnız kendi verisi (403); PERSONA SIZINTISI YOK; karne/anomali/hedef; yetkiler.

    cd appbackend
    PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe tests/test_ai_ceo_smoke.py
"""
import asyncio
import json
import os
import re
import sys

TEST_DB = "oba_test_ai_ceo"
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
    import server
    from httpx import AsyncClient, ASGITransport
    from modules.ai_ceo import personalar
    import modules.ai_ceo.analiz as analiz_mod
    import modules.ai_ceo.miran as miran_mod

    db = server.db
    await server.client.drop_database(TEST_DB)

    # ── seed ──
    await db.users.insert_one({"id": "adm", "role": "admin", "ad": "Ad", "soyad": "Min"})
    await db.users.insert_one({"id": "t1", "role": "teacher", "ad": "Öğ", "soyad": "Bir"})
    await db.users.insert_one({"id": "t2", "role": "teacher", "ad": "Öğ", "soyad": "İki"})
    # KVKK: teacher'da telefon+email VAR → payload'a SIZMAMALI
    await db.teachers.insert_one({"id": "t1", "ad": "Ali", "soyad": "Veli", "seviye": "yeni",
                                  "telefon": "5559998877", "email": "gizli@ornek.com",
                                  "atanan_ogrenciler": ["s1", "s2"], "yapilmasi_gereken_odeme": 1000, "yapilan_odeme": 400})
    await db.teachers.insert_one({"id": "t2", "ad": "Ay", "soyad": "Koç", "seviye": "yeni", "atanan_ogrenciler": ["s3"]})
    for sid, sinif, il in [("s1", "3", "Ankara"), ("s2", "5", "Ankara"), ("s3", "2", "İzmir")]:
        await db.students.insert_one({"id": sid, "ad": "Ö", "soyad": sid, "sinif": sinif, "il": il,
                                      "yapilmasi_gereken_odeme": 1000, "yapilan_odeme": 500})
    # gecikme riski: s1'in kuru 40 gün önce açılmış (geciken)
    await db.kur_ucretleri.insert_one({"id": "k1", "ogrenci_id": "s1", "kur_adi": "1", "tutar": 1000,
                                       "yapilan_odeme": 400, "durum": "acik", "baslangic_tarihi": "2026-06-01T00:00:00"})
    # KARIŞIK tz kur: baslangic NAIVE + tamamlanma AWARE — fotoğraf ort_kur_suresi hesabı
    # eskiden burada "offset-naive vs offset-aware" hatası fırlatıyordu.
    await db.kur_ucretleri.insert_one({"id": "kmix", "ogrenci_id": "s2", "kur_adi": "1", "tutar": 1000,
                                       "yapilan_odeme": 1000, "durum": "tamamlandi",
                                       "baslangic_tarihi": "2026-05-01T00:00:00",            # naive
                                       "tamamlanma_tarihi": "2026-05-20T00:00:00+00:00"})    # aware
    await db.veli_anketleri.insert_one({"puan": 4})

    def H(uid):
        return {"Authorization": f"Bearer {server.create_access_token({'sub': uid})}"}

    async with AsyncClient(transport=ASGITransport(app=server.app), base_url="http://test") as ac:
        # ── 1) SİSTEM FOTOĞRAFI + OTONOM ENVANTER ──
        # yeni/bilinmeyen bir koleksiyon → envantere otomatik girmeli
        await db.yepyeni_modul_verisi.insert_one({"x": 1, "tarih": "2026-07-16T00:00:00"})
        r = await ac.post("/api/ai/ceo/fotograf/cek", headers=H("adm"))
        check(r.status_code == 200, f"fotograf/cek 200 ({r.status_code})")
        foto = r.json()["fotograf"]
        check(all(k in foto for k in ("ogretmen", "muhasebe", "ogrenci", "kullanim", "envanter")), "fotoğraf tüm blokları içeriyor")
        # KARIŞIK tz kur → ort süre HATASIZ hesaplandı (naive/aware regresyonu)
        check("_hata" not in foto["ogretmen"], "öğretmen bloğu hatasız (naive/aware karışımı fırlatmadı)")
        check(abs((foto["ogretmen"].get("ort_kur_suresi_gun") or 0) - 19) < 0.6, f"karışık-tz kurdan ort süre ~19 gün ({foto['ogretmen'].get('ort_kur_suresi_gun')})")
        kol = foto["envanter"]["koleksiyonlar"]
        check("yepyeni_modul_verisi" in kol, "otonom envanter yeni koleksiyonu otomatik kapsadı")
        check(foto["ogrenci"]["aktif"] == 3, f"ogrenci.aktif=3 ({foto['ogrenci']['aktif']})")

        # ── 2) KVKK — payload'da kişisel iletişim verisi YOK ──
        blob = json.dumps(foto, ensure_ascii=False)
        check("5559998877" not in blob, "telefon payload'a sızmadı")
        check("gizli@ornek.com" not in blob, "e-posta payload'a sızmadı")
        check(not re.search(r"[\w.]+@[\w.]+\.\w+", blob), "payload'da hiç e-posta örüntüsü yok")

        # ── 3) ANALİZ (Gemini MOCK) + DAYANAK DOĞRULAMA ──
        gercek_deger = foto["muhasebe"]["tahsil_edilen"]  # fotoğrafta GERÇEKTEN var
        analiz_mod.GEMINI_API_KEY = "test-key"

        async def sahte_analiz(system, user, max_tokens=4000, **kw):
            return {"text": "", "error": None, "parsed": {
                "ozet": "Genel durum iyi.",
                "oneriler": [
                    {"baslik": "Tahsilatı hızlandır", "kategori": "tahsilat", "oncelik": "yuksek",
                     "ozet": "Bekleyen tahsilat var.", "beklenen_etki": "Tahsilat artışı",
                     "dayanak_metrikler": [{"metrik": "tahsil edilen", "deger": gercek_deger}]},
                    {"baslik": "Uydurma öneri", "kategori": "buyume", "oncelik": "dusuk",
                     "ozet": "Dayanağı hatalı.", "beklenen_etki": "?",
                     "dayanak_metrikler": [{"metrik": "hayali metrik", "deger": 123456789}]},
                ],
                "kesif_bulgulari": ["yepyeni_modul_verisi az kullanılıyor"]}}
        analiz_mod.call_claude = sahte_analiz

        r = await ac.post("/api/ai/ceo/analiz/calistir", headers=H("adm"))
        check(r.status_code == 200 and r.json().get("ok"), "analiz/calistir ok")
        oneriler = r.json()["oneriler"]
        o_guclu = next((o for o in oneriler if o["kategori"] == "tahsilat"), None)
        o_zayif = next((o for o in oneriler if o["baslik"] == "Uydurma öneri"), None)
        check(o_guclu and not o_guclu["zayif_dayanak"], "gerçek dayanak → zayif_dayanak=False (doğrulandı)")
        check(o_guclu and o_guclu["dayanaklar"][0]["dogrulandi"] is True, "dayanak fotoğrafta DOĞRULANDI (güçlü)")
        check(o_zayif and o_zayif["zayif_dayanak"] is True, "uydurma dayanak → 'zayıf dayanak' etiketi")

        # ── 4) ÖNERİ DURUM TAKİBİ ──
        r = await ac.put(f"/api/ai/ceo/oneri/{o_guclu['id']}/durum", headers=H("adm"), json={"durum": "uygulandi", "not": "denendi"})
        check(r.status_code == 200, "öneri durumu 'uygulandi' güncellendi")

        # ── 5) KARNE (deterministik) ──
        r = await ac.get("/api/ai/ceo/karne", headers=H("adm"))
        k = r.json()["karne"]
        check(r.status_code == 200 and k["toplam_oneri"] == 2, f"karne toplam_oneri=2 ({k['toplam_oneri']})")
        check(k["kabul_orani"] is not None and k["kabul_orani"] > 0, f"karne kabul_orani>0 ({k['kabul_orani']})")
        check(k["zayif_dayanak_orani"] == 50.0, f"zayıf dayanak oranı=50 ({k['zayif_dayanak_orani']})")

        # ── 6) MEKTUP — ONAYSIZ ÖĞRETMENE GİTMEZ ──
        r = await ac.post("/api/ai/ceo/mektup/uret", headers=H("adm"), json={"ogretmen_id": "t1"})
        check(r.status_code == 200, "mektup taslağı üretildi")
        mid = r.json()["mektup"]["id"]
        check(r.json()["mektup"]["onayli"] is False, "taslak onaysız (onayli=False)")
        # öğretmen henüz göremez
        r = await ac.get("/api/ai/ceo/mektuplarim", headers=H("t1"))
        check(r.status_code == 200 and len(r.json()["mektuplar"]) == 0, "onaysız mektup öğretmene GÖRÜNMÜYOR")
        # onayla → öğretmen görür
        r = await ac.post(f"/api/ai/ceo/mektup/{mid}/onayla", headers=H("adm"))
        check(r.status_code == 200, "mektup onaylandı")
        r = await ac.get("/api/ai/ceo/mektuplarim", headers=H("t1"))
        check(len(r.json()["mektuplar"]) == 1, "onaylı mektup öğretmene GÖRÜNÜYOR")
        # onaylı mektup artık düzenlenemez
        r = await ac.put(f"/api/ai/ceo/mektup/{mid}", headers=H("adm"), json={"icerik": {"x": 1}})
        check(r.status_code == 404, "onaylı mektup düzenlenemez (API guard)")
        # öğretmen mektup üretemez / admin uçlarına giremez
        r = await ac.post("/api/ai/ceo/mektup/uret", headers=H("t1"), json={"ogretmen_id": "t1"})
        check(r.status_code == 403, "öğretmen mektup üretemez → 403")
        # bildirim düştü mü
        check(await db.bildirimler.find_one({"alici_id": "t1", "tur": "ai_ceo_mektup"}) is not None, "onaylı mektup bildirimi düştü")

        # ── 7) MİRAN — üslup guard + yalnız kendi verisi ──
        miran_mod.GEMINI_API_KEY = "test-key"

        async def sahte_miran_ihlal(system, user, max_tokens=1200, **kw):
            return {"text": "", "error": None, "parsed": {
                "selam": "Selam", "kapanis": "Bitti",
                "oneriler": [{"baslik": "Kıyas", "aciklama": "Diğer öğretmenler senden iyi, tahsilat 5000₺."}]}}
        miran_mod.call_claude = sahte_miran_ihlal
        r = await ac.get("/api/ai/ceo/miran/benim", headers=H("t1"))
        check(r.status_code == 200, "miran/benim 200 (öğretmen)")
        mrn = r.json()["miran"]
        mblob = json.dumps(mrn["icerik"], ensure_ascii=False).lower()
        check("diğer öğretmen" not in mblob and "senden iyi" not in mblob, "Miran guard: kıyas ifadesi ENGELLENDİ")
        check("5000" not in mblob and "₺" not in mblob, "Miran guard: para/tutar ENGELLENDİ")
        check(mrn["kaynak"] == "deterministik", "guard ihlalinde deterministik güvenli mesaja düşüldü")
        mrn_id = mrn["id"]
        # başka öğretmen bu kayda geri bildirim veremez → 403
        r = await ac.post(f"/api/ai/ceo/miran/{mrn_id}/geri-bildirim", headers=H("t2"), json={"faydali": True})
        check(r.status_code == 403, "başka öğretmen Miran kaydına dokunamaz → 403")
        # sahibi geri bildirim verebilir → karneye işlenir
        r = await ac.post(f"/api/ai/ceo/miran/{mrn_id}/geri-bildirim", headers=H("t1"), json={"faydali": True})
        check(r.status_code == 200, "öğretmen kendi Miran'ına faydalı geri bildirimi verdi")

        # ── 8) PERSONA SIZINTISI YOK ──
        check(personalar.gorunur_mu("ayda", "teacher") is False, "Ayda öğretmene görünmez")
        check(personalar.gorunur_mu("miran", "admin") is False, "Miran admin'e görünmez")
        check(personalar.gorunur_mu("ayda", "admin") is True and personalar.gorunur_mu("miran", "teacher") is True, "her persona kendi tarafında görünür")
        # öğretmen Ayda uçlarına (analiz) giremez
        r = await ac.post("/api/ai/ceo/analiz/calistir", headers=H("t1"))
        check(r.status_code == 403, "öğretmen Ayda analizine erişemez → 403")

        # ── 9) HİYERARŞİ — Ayda görür: Miran'ın öğretmen odakları ──
        r = await ac.get("/api/ai/ceo/miran/odaklar", headers=H("adm"))
        odak = next((o for o in r.json()["odaklar"] if o["ogretmen_id"] == "t1"), None)
        check(odak and odak["odak_etiket"] == "Gecikme riski odaklı", f"Ayda t1 için odak='Gecikme riski' ({odak})")

        # ── 10) ANOMALİ (kural bazlı) ──
        # tahsilat düşüşü kur: fotoğraftaki trende iki ay ekleyelim
        await db.ai_ceo_fotograflar.update_one({"id": foto["id"]}, {"$set": {
            "muhasebe.tahsilat_trendi_son3ay": {"2026-05": 10000, "2026-06": 3000}}})
        r = await ac.get("/api/ai/ceo/anomali", headers=H("adm"))
        tips = [a["tip"] for a in r.json()["anomaliler"]]
        check("tahsilat_dususu" in tips, f"tahsilat düşüşü anomalisi yakalandı ({tips})")

        # ── 11) HEDEF gauge ──
        r = await ac.post("/api/ai/ceo/hedef", headers=H("adm"), json={"ad": "Yenileme", "tip": "aktif_ogrenci", "hedef_deger": 6})
        check(r.status_code == 200, "hedef eklendi")
        r = await ac.get("/api/ai/ceo/hedefler", headers=H("adm"))
        h = r.json()["hedefler"][0]
        check(h["gauge"]["ilerleme_yuzde"] == 50.0, f"gauge: aktif 3/hedef 6 = %50 ({h['gauge']['ilerleme_yuzde']})")

        # ── 12) GÜNLÜK RAPOR (deterministik) ──
        r = await ac.get("/api/ai/ceo/rapor/gunluk", headers=H("adm"))
        check(r.status_code == 200 and r.json()["rapor"]["yorum"], "günlük rapor + yorum üretildi")

        # ── 13) PAZAR ARAŞTIRMASI (grounding) — başarı + 'yapılandırılmadı' + 403 ──
        import modules.ai_ceo.pazar as pazar_mod

        async def sahte_grounded_ok(prompt, system="", max_tokens=3000, **kw):
            return {"text": "Rakip X 199₺/ay; fırsat: fiyat esnekliği.", "model": "gemini-2.0-flash", "error": None,
                    "kaynaklar": [{"baslik": "Rakip X", "url": "https://ornek.com/x"}]}
        pazar_mod.gemini_grounded_call = sahte_grounded_ok
        r = await ac.post("/api/ai/ceo/pazar-arastirma", headers=H("adm"), json={})
        check(r.status_code == 200 and r.json().get("ok"), "pazar araştırması (grounding) başarılı")
        check(len(r.json()["arastirma"]["kaynaklar"]) == 1 and r.json()["arastirma"]["kaynaklar"][0]["url"].startswith("http"), "kaynak linkleri döndü")

        async def sahte_grounded_yok(prompt, system="", max_tokens=3000, **kw):
            return {"text": "", "kaynaklar": [], "model": None, "error": "Grounding başarısız: tool desteklenmiyor"}
        pazar_mod.gemini_grounded_call = sahte_grounded_yok
        r = await ac.post("/api/ai/ceo/pazar-arastirma", headers=H("adm"), json={})
        check(r.status_code == 200 and r.json().get("ok") is False and r.json().get("durum") == "yapilandirilmadi",
              "grounding yoksa 'yapılandırılmadı' (uydurma YOK)")
        r = await ac.post("/api/ai/ceo/pazar-arastirma", headers=H("t1"), json={})
        check(r.status_code == 403, "öğretmen pazar araştırması yapamaz → 403")

    await server.client.drop_database(TEST_DB)


if __name__ == "__main__":
    asyncio.run(run())
    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    sys.exit(1 if _kalan else 0)
