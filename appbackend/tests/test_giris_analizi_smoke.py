"""Giriş Analizi — yeni özellikler smoke testi (Faz 1+).

Kapsam (Faz 1):
- oturum_tipi otomatik atama (ilk tamamlanmışsa ilk_analiz, sonra ara_analiz) + elle seçim
- rapor_tipi="olcum"
- Rapor ölçütleri paneli: GET/PUT /admin/rapor-ayarlari/{tip} (+ tümü)
- dogruluk_seviyesi / kur önerisi ayardan okuma

İzole test DB (oba_test_giris_analizi). Gerçek DB'ye dokunmaz.
    cd appbackend && .venv/Scripts/python.exe tests/test_giris_analizi_smoke.py
"""
import asyncio
import os
import sys

TEST_DB = "oba_test_giris_analizi"
os.environ["MONGO_URL"] = os.environ.get("MONGO_URL_TEST", "mongodb://localhost:27017")
os.environ["DB_NAME"] = TEST_DB
os.environ.setdefault("SECRET_KEY", "test-secret-key")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_gecen = 0
_kalan = 0


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

    admin_id = str(uuid.uuid4())
    await server.db.users.insert_one({"id": admin_id, "role": "admin", "ad": "Yön", "soyad": "Etici"})
    H = {"Authorization": f"Bearer {create_access_token({'sub': admin_id})}"}

    # Metin + öğrenci
    metin_id = str(uuid.uuid4())
    await server.db.analiz_metinler.insert_one({
        "id": metin_id, "baslik": "Test Metni", "icerik": "kelime " * 100, "kelime_sayisi": 100,
        "sinif_seviyesi": "4", "tur": "hikaye", "durum": "havuzda"})
    ogr_id = str(uuid.uuid4())
    await server.db.students.insert_one({"id": ogr_id, "ad": "Test", "soyad": "Öğrenci", "sinif": "4", "kur": "Kur 1"})

    transport = ASGITransport(app=server.app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1) İlk oturum → otomatik ilk_analiz
        r = await ac.post("/api/diagnostic/sessions", headers=H, json={"ogrenci_id": ogr_id, "metin_id": metin_id})
        check(r.status_code == 200, f"oturum başlatıldı (status={r.status_code})")
        ot1 = r.json()
        check(ot1.get("oturum_tipi") == "ilk_analiz", f"ilk oturum → ilk_analiz ({ot1.get('oturum_tipi')})")
        # tamamla
        r = await ac.post(f"/api/diagnostic/sessions/{ot1['id']}/complete", headers=H,
                          json={"sure_saniye": 60, "hatalar": [{"tip": "atlama", "kelime": "x"}], "ogretmen_kur": ""})
        check(r.status_code == 200 and r.json()["wpm"] == 100.0, f"oturum tamamlandı wpm=100 ({r.json().get('wpm')})")

        # 2) İkinci oturum (ilk tamamlandı) → otomatik ara_analiz
        r = await ac.post("/api/diagnostic/sessions", headers=H, json={"ogrenci_id": ogr_id, "metin_id": metin_id})
        check(r.json().get("oturum_tipi") == "ara_analiz", f"ikinci oturum → ara_analiz ({r.json().get('oturum_tipi')})")

        # 3) Elle kur_sonu_analiz seçimi
        r = await ac.post("/api/diagnostic/sessions", headers=H,
                          json={"ogrenci_id": ogr_id, "metin_id": metin_id, "oturum_tipi": "kur_sonu_analiz"})
        ot3 = r.json()
        check(ot3.get("oturum_tipi") == "kur_sonu_analiz", "elle kur_sonu_analiz seçildi")

        # 4) Rapor → rapor_tipi=olcum
        r = await ac.post("/api/diagnostic/rapor", headers=H, json={
            "oturum_id": ot1["id"], "anlama": {}, "prozodik": {}, "ogretmen_notu": "iyi"})
        check(r.status_code == 200 and r.json().get("rapor_tipi") == "olcum",
              f"rapor rapor_tipi=olcum (status={r.status_code}, tip={r.json().get('rapor_tipi')})")

        # 5) Rapor ölçütleri paneli — tümü + tekil + PUT (anlama maddesi ekle)
        r = await ac.get("/api/admin/rapor-ayarlari", headers=H)
        tumu = r.json()
        check(all(t in tumu for t in ("okuma_hizi_normlari", "dogruluk_esikleri", "anlama_rubrik_maddeleri",
              "prozodik_olcutler", "gelisim_degisim_esikleri")), "tüm ayar tipleri geldi")
        r = await ac.get("/api/admin/rapor-ayarlari/anlama_rubrik_maddeleri", headers=H)
        rubrik = r.json()["degerler"]
        check(len(rubrik) == 4 and rubrik[0]["maddeler"], "anlama rubriği 4 boyut + maddeler")
        # yeni madde ekle
        rubrik[0]["maddeler"].append({"id": "yeni_madde", "etiket": "Yeni Test Maddesi"})
        r = await ac.put("/api/admin/rapor-ayarlari/anlama_rubrik_maddeleri", headers=H, json={"degerler": rubrik})
        check(r.status_code == 200, "anlama rubriği güncellendi")
        r = await ac.get("/api/admin/rapor-ayarlari/anlama_rubrik_maddeleri", headers=H)
        idler = [m["id"] for m in r.json()["degerler"][0]["maddeler"]]
        check("yeni_madde" in idler, "yeni madde kalıcı yazıldı")

        # 6) dogruluk eşiği güncelle → kur önerisi/etiket ayardan
        r = await ac.put("/api/admin/rapor-ayarlari/kur_onerisi_esikleri", headers=H,
                         json={"degerler": {"kur3_dogruluk": 99, "kur2_dogruluk": 90}})
        check(r.status_code == 200, "kur önerisi eşikleri güncellendi")

        # 7) GELİŞİM RAPORU: ot3'ü (kur_sonu) tamamla + ölçüm raporu, sonra ot1↔ot3 karşılaştır
        await ac.post(f"/api/diagnostic/sessions/{ot3['id']}/complete", headers=H,
                      json={"sure_saniye": 40, "hatalar": [], "ogretmen_kur": "Kur 2"})  # daha hızlı + hatasız
        r = await ac.post("/api/diagnostic/rapor", headers=H, json={
            "oturum_id": ot3["id"], "anlama": {"ana_fikir": "iyi", "konu": "iyi"},
            "prozodik": {"vurgu": 4, "tonlama": 4}, "ogretmen_notu": "gelişti"})
        check(r.status_code == 200, "ot3 ölçüm raporu oluştu")
        # Gelişim raporu (rapor eksikse 400 olurdu)
        r = await ac.post("/api/diagnostic/gelisim-raporu", headers=H, json={
            "ogrenci_id": ogr_id, "ilk_oturum_id": ot1["id"], "son_oturum_id": ot3["id"], "ders_sayisi": 12})
        check(r.status_code == 200, f"gelişim raporu oluştu (status={r.status_code})")
        gr = r.json()
        check(gr.get("rapor_tipi") == "gelisim", "rapor_tipi=gelisim")
        check(len(gr.get("ozet_tablo", [])) == 4, f"özet tablo 4 metrik ({len(gr.get('ozet_tablo', []))})")
        metrikler = {m["metrik"]: m for m in gr["ozet_tablo"]}
        # ot1: 60sn/100kelime=100wpm, 1 hata → dogruluk 99; ot3: 40sn=150wpm, 0 hata → 100
        check(metrikler["wpm"]["son_test"] == 150.0 and metrikler["wpm"]["degisim"] == 50.0,
              f"wpm ön=100 son=150 değişim=50 ({metrikler['wpm']})")
        check(metrikler["wpm"]["gelisim_duzeyi"] == "Anlamlı Gelişim", "wpm +50 → Anlamlı Gelişim")
        check(all("normlara_gore_duzey" in m for m in gr["ozet_tablo"]), "her metrikte normlara göre düzey var")
        check(bool(gr.get("hata_analizi", {}).get("on_test") is not None), "hata analizi ön/son var")
        check(gr.get("ilk_rapor_id") and gr.get("son_rapor_id"), "ilk/son rapor referansları saklandı")
        # PDF üretimi (gelişim + ölçüm) — reportlab pipeline
        r = await ac.get(f"/api/diagnostic/rapor/{gr['id']}/pdf", headers=H)
        check(r.status_code == 200 and r.content[:4] == b"%PDF", f"gelişim raporu PDF üretildi ({r.status_code})")
        olcum_rapor_id = (await ac.post("/api/diagnostic/rapor", headers=H, json={
            "oturum_id": ot3["id"], "anlama": {"ana_fikir": "iyi"}, "prozodik": {"vurgu": 4}})).json()["id"]
        r = await ac.get(f"/api/diagnostic/rapor/{olcum_rapor_id}/pdf", headers=H)
        check(r.status_code == 200 and r.content[:4] == b"%PDF", "ölçüm raporu PDF hâlâ üretiliyor (regresyon yok)")
        # Eksik rapor senaryosu: yeni oturum, raporu yok → 400
        r = await ac.post("/api/diagnostic/sessions", headers=H, json={"ogrenci_id": ogr_id, "metin_id": metin_id})
        ot4 = r.json()
        r = await ac.post("/api/diagnostic/gelisim-raporu", headers=H, json={
            "ogrenci_id": ogr_id, "ilk_oturum_id": ot1["id"], "son_oturum_id": ot4["id"]})
        check(r.status_code == 400, f"raporsuz oturumda gelişim raporu 400 ({r.status_code})")

        # yetki: öğretmen panele erişemez
        t_id = str(uuid.uuid4())
        await server.db.users.insert_one({"id": t_id, "role": "teacher", "ad": "Öğ", "soyad": "Rt"})
        Ht = {"Authorization": f"Bearer {create_access_token({'sub': t_id})}"}
        r = await ac.get("/api/admin/rapor-ayarlari", headers=Ht)
        check(r.status_code == 403, f"öğretmen rapor ayarları panelinden 403 ({r.status_code})")

    await server.client.drop_database(TEST_DB)


def main():
    asyncio.run(run())
    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    sys.exit(0 if _kalan == 0 else 1)


if __name__ == "__main__":
    main()
