"""Analiz metin havuzu — tek kaynak + yedek/silme + cevap üretimi + görünürlük smoke.

Kapsam: (1) goç 150 metni kanonik şemayla (sorular+id, dogru_cevap alanları, acik_sorular) yükler
+ eskileri okuma_parcalari'na taşır; (2) yedekle → temizle (onaysız 400, yedeksiz 400, onaylı
150 dışını siler); (3) geçmiş snapshot korunur (silme sonrası oturum metni durur); (4) tek kaynak:
kutulu-okuma + ai/speech yalnız bolum=analiz; (5) AI cevap üretimi (mock) dogru_cevap+guven yazar,
manuel'i korur; (6) metin ekleme → onay akışı (teacher beklemede → admin havuzda); (7) öğrenci
dogru_cevap görmez, eğitici görür.

    cd appbackend
    PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe tests/test_analiz_havuz_smoke.py
"""
import asyncio
import os
import sys

TEST_DB = "oba_test_analiz_havuz"
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
    import core.ai as ai_mod

    db = server.db
    await server.client.drop_database(TEST_DB)
    await db.users.insert_one({"id": "adm", "role": "admin", "ad": "Ad", "soyad": "Min"})
    await db.users.insert_one({"id": "koord", "role": "coordinator", "ad": "Ko", "soyad": "Or"})
    await db.users.insert_one({"id": "t1", "role": "teacher", "ad": "Öğ", "soyad": "One"})
    await db.users.insert_one({"id": "ogr1", "role": "student", "ad": "Öğ", "soyad": "Renci", "sinif": "3"})
    # Eski/kaynağı belirsiz metin (silinecek)
    await db.analiz_metinler.insert_one({"id": "eski1", "baslik": "Ormanda Macera", "icerik": "Eski metin gövdesi.",
        "kelime_sayisi": 3, "bolum": "analiz", "durum": "havuzda", "kaynak": "seed_oba_v1", "sorular": [], "acik_sorular": []})

    def H(u):
        return {"Authorization": f"Bearer {server.create_access_token({'sub': u})}"}

    async with AsyncClient(transport=ASGITransport(app=server.app), base_url="http://test") as ac:
        # ── 1) goç import: 150 kanonik ──
        r = await ac.post("/api/diagnostic/akici-okuma-goc", headers=H("adm"))
        j = r.json()
        check(r.status_code == 200 and j["toplam_metin"] == 150, f"150 metin işlendi ({j.get('toplam_metin')})")
        analiz_say = await db.analiz_metinler.count_documents({"bolum": "analiz", "kaynak": "akici_okuma_yeni"})
        check(analiz_say == 150, f"havuzda 150 Akıcı Okuma metni ({analiz_say})")
        check(await db.analiz_metinler.count_documents({"id": "eski1", "bolum": "okuma_parcalari"}) == 1, "eski metin okuma_parcalari'na taşındı (silinmedi)")
        ornek = await db.analiz_metinler.find_one({"bolum": "analiz", "kaynak": "akici_okuma_yeni", "sorular.0": {"$exists": True}})
        s0 = ornek["sorular"][0]
        check("id" in s0 and "secenekler" in s0 and "dogru_cevap" in s0 and "kontrol_gerekli" in s0, "ÇSS kanonik şema (id/secenekler/dogru_cevap/kontrol_gerekli)")
        check("acik_sorular" in ornek and "acik_uclu" not in ornek, "açık uçlu 'acik_sorular' alanında (acik_uclu temizlendi)")

        # ── 7) görünürlük: öğrenci dogru_cevap görmez, eğitici görür ──
        r_e = await ac.get(f"/api/diagnostic/texts?bolum=analiz", headers=H("adm"))
        r_o = await ac.get(f"/api/diagnostic/texts?bolum=analiz", headers=H("ogr1"))
        def _ilk_soru(resp):
            for m in resp.json():
                if m.get("sorular"):
                    return m["sorular"][0]
            return {}
        check("dogru_cevap" in _ilk_soru(r_e), "eğitici doğru cevabı görür")
        check("dogru_cevap" not in _ilk_soru(r_o), "öğrenci doğru cevabı GÖRMEZ")

        # ── 5) AI cevap üretimi (mock) ──
        ai_mod.GEMINI_API_KEY = "k"
        async def fake_cc(system, user, max_tokens=700, ozellik=""):
            return {"text": '[{"no":1,"dogru":"B","guven":"high","dayanak":"metindeki kanıt cümle"},{"no":2,"dogru":"A","guven":"low"},{"no":3,"dogru":"C","guven":"high"},{"no":4,"dogru":"D","guven":"high"},{"no":5,"dogru":"A","guven":"high"}]', "parsed": None, "error": None}
        ai_mod.call_claude = fake_cc
        # bir metnin ilk sorusunu MANUEL işaretle (korunmalı)
        man = await db.analiz_metinler.find_one({"bolum": "analiz", "sorular.0": {"$exists": True}})
        man["sorular"][0].update({"dogru_cevap": "C", "dogru_cevap_kaynak": "manuel", "kontrol_gerekli": False})
        await db.analiz_metinler.update_one({"id": man["id"]}, {"$set": {"sorular": man["sorular"]}})
        r = await ac.post("/api/diagnostic/analiz-havuz/cevap-uret?limit=200", headers=H("adm"))
        jc = r.json()
        check(r.status_code == 200 and jc["islenen_metin"] > 0 and jc["kalan_metin"] == 0, f"cevap üretimi tüm metinleri işledi ({jc.get('islenen_metin')})")
        man2 = await db.analiz_metinler.find_one({"id": man["id"]})
        check(man2["sorular"][0]["dogru_cevap"] == "C" and man2["sorular"][0]["dogru_cevap_kaynak"] == "manuel", "manuel doğru cevap korundu (AI ezmedi)")
        dolu = await db.analiz_metinler.find_one({"bolum": "analiz", "sorular.1": {"$exists": True}})
        check(any(s.get("dogru_cevap") for s in dolu["sorular"]), "AI otomatik doğru cevap yazdı")
        check(any(s.get("dayanak") for m2 in [await db.analiz_metinler.find_one({"sorular.dayanak": "metindeki kanıt cümle"})] if m2 for s in m2["sorular"]), "AI dayanak cümlesi saklandı")
        # Örneklem raporu ucu
        r = await ac.get("/api/diagnostic/analiz-havuz/cevap-ornek?n=10", headers=H("adm"))
        jo = r.json()
        check(r.status_code == 200 and jo["metin_sayisi"] == 10 and jo["toplam_soru"] > 0, f"cevap örneklemi 10 metin döndü ({jo.get('metin_sayisi')}/{jo.get('toplam_soru')})")
        check(all("dogru_cevap" in s and "dayanak" in s for m3 in jo["ornekler"] for s in m3["sorular"]), "örneklemde doğru cevap + dayanak var")
        # öğrenci dayanağı görmez
        check("dayanak" not in _ilk_soru(await ac.get("/api/diagnostic/texts?bolum=analiz", headers=H("ogr1"))), "öğrenci dayanak cümlesini GÖRMEZ")

        # ── 4) tek kaynak: kutulu-okuma + ai/speech yalnız bolum=analiz ──
        r = await ac.get("/api/kutulu-okuma/metin?sinif=3", headers=H("ogr1"))
        if r.status_code == 200 and r.json().get("metin"):
            mid = r.json()["metin"].get("id")
            src = await db.analiz_metinler.find_one({"id": mid})
            check(src and src.get("bolum") == "analiz", "Kutulu Okuma yalnız havuzdan (bolum=analiz) seçti")
        else:
            check(True, "Kutulu Okuma (metin yoksa atlandı)")
        r = await ac.get("/api/ai/speech/metinler?sinif=3", headers=H("ogr1"))
        sm = r.json().get("metinler", [])
        bolumler = []
        for x in sm[:5]:
            d = await db.analiz_metinler.find_one({"id": x["id"]})
            bolumler.append((d or {}).get("bolum"))
        hepsi_analiz = bool(bolumler) and all(b == "analiz" for b in bolumler)
        check(r.status_code == 200 and len(sm) > 0 and hepsi_analiz, f"AI Sesli Okuma havuzdan besleniyor ({len(sm)} metin)")

        # ── 6) metin ekleme → onay akışı (AI yok) ──
        yeni = {"baslik": "Öğretmen Metni", "icerik": "Öğretmenin elle girdiği metin.", "sorular": [], "acik_sorular": []}
        r = await ac.post("/api/diagnostic/texts", headers=H("t1"), json=yeni)
        yid = r.json().get("id")
        check(r.status_code == 200 and r.json().get("durum") == "beklemede", f"öğretmen eklediği metin beklemede ({r.json().get('durum')})")
        r = await ac.post(f"/api/diagnostic/texts/{yid}/admin-karar", headers=H("adm"), json={"onay": True})
        durum2 = (await db.analiz_metinler.find_one({"id": yid}) or {}).get("durum")
        check(durum2 == "havuzda", f"admin onayı → havuzda ({durum2})")

        # KOORDİNATÖR onayı: beklemede → havuzda (öğretmen ekledi)
        r = await ac.post("/api/diagnostic/texts", headers=H("t1"), json={"baslik": "Koord Onaylı", "icerik": "Metin.", "sorular": [], "acik_sorular": []})
        kid = r.json().get("id")
        r = await ac.post(f"/api/diagnostic/texts/{kid}/admin-karar", headers=H("koord"), json={"onay": True})
        dk = (await db.analiz_metinler.find_one({"id": kid}) or {}).get("durum")
        check(r.status_code == 200 and dk == "havuzda", f"koordinatör onayı → havuzda ({dk})")
        # KOORDİNATÖR, oylamadaki metni de onaylayabilir (admin eklerse durum=oylama)
        r = await ac.post("/api/diagnostic/texts", headers=H("adm"), json={"baslik": "Oylamalık", "icerik": "Metin.", "sorular": [], "acik_sorular": []})
        oid = r.json().get("id")
        check(r.json().get("durum") == "oylama", f"admin eklediği metin oylamada ({r.json().get('durum')})")
        r = await ac.post(f"/api/diagnostic/texts/{oid}/admin-karar", headers=H("koord"), json={"onay": True})
        do = (await db.analiz_metinler.find_one({"id": oid}) or {}).get("durum")
        check(do == "havuzda", f"koordinatör oylamadaki metni onayladı → havuzda ({do})")
        # öğretmen onaylayamaz (403)
        r = await ac.post("/api/diagnostic/texts", headers=H("t1"), json={"baslik": "Öğr2", "icerik": "M.", "sorular": [], "acik_sorular": []})
        check((await ac.post(f"/api/diagnostic/texts/{r.json().get('id')}/admin-karar", headers=H("t1"), json={"onay": True})).status_code == 403, "öğretmen admin-karar veremez (403)")

        # ── 2+3) yedekle → temizle (geçmiş snapshot korunur) ──
        # eski metne referanslı bir oturum (snapshot'lı) oluştur
        await db.diagnostic_oturumlar.insert_one({"id": "ot1", "ogrenci_id": "ogr1", "metin_id": "eski1",
            "metin_baslik": "Ormanda Macera", "metin_icerik": "Eski metin gövdesi.", "metin_kelime_sayisi": 3, "durum": "tamamlandi", "wpm": 80})
        check((await ac.post("/api/diagnostic/analiz-havuz/temizle?onay=true", headers=H("adm"))).status_code == 400, "yedek yokken silme reddedildi (400)")
        r = await ac.post("/api/diagnostic/analiz-havuz/yedekle", headers=H("adm"))
        check(r.status_code == 200 and r.json()["yedeklenen_metin"] >= 150, f"yedek alındı ({r.json().get('yedeklenen_metin')})")
        check((await ac.post("/api/diagnostic/analiz-havuz/temizle", headers=H("adm"))).status_code == 400, "onaysız silme reddedildi (400)")
        r = await ac.post("/api/diagnostic/analiz-havuz/temizle?onay=true", headers=H("adm"))
        jd = r.json()
        check(r.status_code == 200 and jd["korunan_akici"] == 150, f"150 korundu, {jd.get('silinen')} silindi")
        check(await db.analiz_metinler.count_documents({"kaynak": {"$ne": "akici_okuma_yeni"}}) == 0, "150 dışında metin kalmadı (tam silme)")
        ot = await db.diagnostic_oturumlar.find_one({"id": "ot1"})
        check(ot and ot.get("metin_icerik") == "Eski metin gövdesi.", "geçmiş ilerleme snapshot'ı BOZULMADI (metin silinse de duruyor)")
        check(await db.islem_log.find_one({"modul": "diagnostic", "islem": "analiz_havuz_temizle"}) is not None, "silme islem_log'a düştü")

    await server.client.drop_database(TEST_DB)


if __name__ == "__main__":
    asyncio.run(run())
    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    sys.exit(1 if _kalan else 0)
