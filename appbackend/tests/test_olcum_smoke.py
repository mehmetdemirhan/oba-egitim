"""Ölçüm Metinleri (bolum="olcum") smoke.

Kapsam:
 1) POST /diagnostic/olcum-import → 29 metin, bolum=olcum, durum=havuzda, tur=olcum,
    GERÇEK sinif_seviyesi, her metinde açık uçlu Bloom soruları. İdempotent (2. çağrı korur).
 2) Kategori ayrımı: bolum=olcum yalnız 29'u; bolum=analiz Ölçüm'ü GÖSTERMEZ; bolum yok → Ölçüm hariç.
 3) Sınıf filtresi: sinif_seviyesi=3 → 3 metin; =lise → 5 metin; yok ("tüm seviyeler") → 29.
 4) Bloom şeması: acik_sorular[0] kategori 6 kanonik Bloom'dan; öğrenci model_cevap GÖRMEZ, eğitici görür.
 5) Onay akışı: öğretmenin EKLEDİĞİ Ölçüm metni doğrudan havuza DÜŞMEZ (beklemede); acik_sorular saklanır.
 6) Ortak gövde: AI Sesli Okuma (ai/speech) Ölçüm gövdelerinden de besleniyor.
 7) göç non-clobber: akici-okuma-goc Ölçüm metinlerine DOKUNMAZ.

    cd appbackend
    PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe tests/test_olcum_smoke.py
"""
import asyncio
import os
import sys

TEST_DB = "oba_test_olcum"
os.environ["MONGO_URL"] = os.environ.get("MONGO_URL_TEST", "mongodb://localhost:27017")
os.environ["DB_NAME"] = TEST_DB
os.environ.setdefault("SECRET_KEY", "test-secret-key")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_gecen = _kalan = 0
BLOOM = {"Hatırlama", "Anlama", "Uygulama", "Analiz", "Yaratma", "Değerlendirme"}


def check(k, m):
    global _gecen, _kalan
    if k:
        _gecen += 1; print(f"  [GECTI] {m}")
    else:
        _kalan += 1; print(f"  [KALDI] {m}")


async def run():
    import server
    from httpx import AsyncClient, ASGITransport

    db = server.db
    await server.client.drop_database(TEST_DB)
    await db.users.insert_one({"id": "adm", "role": "admin", "ad": "Ad", "soyad": "Min"})
    await db.users.insert_one({"id": "t1", "role": "teacher", "ad": "Öğ", "soyad": "One"})
    await db.users.insert_one({"id": "ogr1", "role": "student", "ad": "Öğ", "soyad": "Renci", "sinif": "3"})
    # Bir Okuma Metni (analiz) — Ölçüm'den ayrı kaldığını doğrulamak için
    await db.analiz_metinler.insert_one({"id": "okuma1", "baslik": "Okuma Metni", "icerik": "Okuma gövdesi.",
        "kelime_sayisi": 2, "bolum": "analiz", "sinif_seviyesi": None, "durum": "havuzda",
        "kaynak": "akici_okuma_yeni", "sorular": [], "acik_sorular": []})

    def H(u):
        return {"Authorization": f"Bearer {server.create_access_token({'sub': u})}"}

    async with AsyncClient(transport=ASGITransport(app=server.app), base_url="http://test") as ac:
        # ── 1) içe aktarım ──
        r = await ac.post("/api/diagnostic/olcum-import", headers=H("adm"))
        j = r.json()
        check(r.status_code == 200 and j["metin"] == 29 and j["eklendi"] == 29, f"29 Ölçüm metni yüklendi (eklendi={j.get('eklendi')})")
        say = await db.analiz_metinler.count_documents({"bolum": "olcum", "durum": "havuzda"})
        check(say == 29, f"havuzda 29 Ölçüm metni (durum=havuzda, onaydan muaf) ({say})")
        ornek = await db.analiz_metinler.find_one({"bolum": "olcum", "sinif_seviyesi": "8"})
        check(ornek and ornek.get("tur") == "olcum" and ornek.get("kaynak") == "olcum", "Ölçüm metni tur=olcum, kaynak=olcum")
        check(bool(ornek) and len(ornek.get("acik_sorular", [])) >= 10, f"Ölçüm metninde >=10 açık uçlu soru ({len(ornek.get('acik_sorular', []))})")
        s0 = ornek["acik_sorular"][0]
        check(s0.get("kategori") in BLOOM and s0.get("soru") and ("model_cevap" in s0) and ("subjektif" in s0),
              f"açık uçlu şema (kategori={s0.get('kategori')}, subjektif={s0.get('subjektif')})")
        # 2. çağrı idempotent
        j2 = (await ac.post("/api/diagnostic/olcum-import", headers=H("adm"))).json()
        check(j2["eklendi"] == 0 and j2["korundu"] == 29, f"idempotent (2. çağrı eklendi=0, korundu={j2.get('korundu')})")

        # ── 2) kategori ayrımı ──
        n_olcum = len((await ac.get("/api/diagnostic/texts?bolum=olcum", headers=H("adm"))).json())
        analiz_list = (await ac.get("/api/diagnostic/texts?bolum=analiz", headers=H("adm"))).json()
        n_analiz_olcum = sum(1 for m in analiz_list if m.get("bolum") == "olcum")
        default_list = (await ac.get("/api/diagnostic/texts", headers=H("adm"))).json()
        n_default_olcum = sum(1 for m in default_list if m.get("bolum") == "olcum")
        check(n_olcum == 29, f"bolum=olcum → 29 metin ({n_olcum})")
        check(n_analiz_olcum == 0 and any(m["id"] == "okuma1" for m in analiz_list), "bolum=analiz Ölçüm'ü GÖSTERMEZ ama Okuma'yı gösterir")
        check(n_default_olcum == 0, "varsayılan görünüm (bolum yok) Ölçüm'ü GÖSTERMEZ")

        # ── 3) sınıf filtresi ──
        n3 = len((await ac.get("/api/diagnostic/texts?bolum=olcum&sinif_seviyesi=3", headers=H("adm"))).json())
        nlise = len((await ac.get("/api/diagnostic/texts?bolum=olcum&sinif_seviyesi=lise", headers=H("adm"))).json())
        check(n3 == 3, f"sinif_seviyesi=3 → 3 Ölçüm metni ({n3})")
        check(nlise == 5, f"sinif_seviyesi=lise → 5 Ölçüm metni ({nlise})")
        check(n_olcum == 29, "sınıf filtresi yok (Tüm seviyeler) → 29")

        # ── 4) görünürlük: öğrenci model_cevap görmez ──
        def _ilk_acik(resp):
            for m in resp.json():
                if m.get("acik_sorular"):
                    return m["acik_sorular"][0]
            return {}
        r_e = await ac.get("/api/diagnostic/texts?bolum=olcum&sinif_seviyesi=3", headers=H("adm"))
        r_o = await ac.get("/api/diagnostic/texts?bolum=olcum&sinif_seviyesi=3", headers=H("ogr1"))
        check("model_cevap" in _ilk_acik(r_e), "eğitici açık uçlu model cevabı GÖRÜR")
        check("model_cevap" not in _ilk_acik(r_o), "öğrenci açık uçlu model cevabı GÖRMEZ")

        # ── 5) onay akışı: öğretmenin eklediği Ölçüm metni beklemede (havuza düşmez) ──
        yeni = {"baslik": "Yeni Ölçüm Metni", "icerik": "Öğretmenin eklediği ölçüm gövdesi.", "bolum": "olcum",
                "sinif_seviyesi": "4", "acik_sorular": [
                    {"no": 1, "kategori": "Hatırlama", "soru": "Soru 1?", "model_cevap": "Cevap 1."},
                    {"no": 2, "kategori": "Değerlendirme", "soru": "Görüşün?", "model_cevap": "(Öğrenci cevabı)"}]}
        r = await ac.post("/api/diagnostic/texts", headers=H("t1"), json=yeni)
        yid = r.json().get("id")
        doc = await db.analiz_metinler.find_one({"id": yid})
        check(r.status_code == 200 and doc.get("durum") == "beklemede", f"öğretmenin Ölçüm metni ONAY BEKLİYOR ({doc.get('durum')}) — havuza düşmedi")
        check(doc.get("bolum") == "olcum" and len(doc.get("acik_sorular", [])) == 2, "yeni Ölçüm metni bolum=olcum + açık uçlu sorular saklandı")
        check(doc["acik_sorular"][1]["subjektif"] is True, "'(Öğrenci cevabı)' → subjektif=True normalize edildi")
        # onay → havuzda
        await ac.post(f"/api/diagnostic/texts/{yid}/admin-karar", headers=H("adm"), json={"onay": True, "direkt": True})
        check((await db.analiz_metinler.find_one({"id": yid})).get("durum") == "havuzda", "admin onayı → Ölçüm metni havuzda")

        # ── 6) ortak gövde: AI Sesli Okuma Ölçüm gövdelerinden de besleniyor ──
        besinci = await db.analiz_metinler.find_one({"bolum": "olcum", "sinif_seviyesi": "5"})
        sm = (await ac.get("/api/ai/speech/metinler?sinif=5", headers=H("ogr1"))).json().get("metinler", [])
        check(any(x.get("id") == besinci["id"] for x in sm), "AI Sesli Okuma listesi Ölçüm (5. sınıf) gövdesini içeriyor")

        # ── 7) göç non-clobber: akici-okuma-goc Ölçüm'e dokunmaz ──
        await ac.post("/api/diagnostic/akici-okuma-goc", headers=H("adm"))
        kalan_olcum = await db.analiz_metinler.count_documents({"bolum": "olcum"})
        check(kalan_olcum >= 29, f"akici-okuma-goc sonrası Ölçüm metinleri KORUNDU ({kalan_olcum} >= 29)")

    await server.client.drop_database(TEST_DB)


if __name__ == "__main__":
    asyncio.run(run())
    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    sys.exit(1 if _kalan else 0)
