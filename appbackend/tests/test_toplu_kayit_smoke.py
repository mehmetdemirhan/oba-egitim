"""Toplu Kayıt Aktarımı (parse → taslak → uygula) uçtan uca smoke testi.

Doğrular: yükle+kuyruklar, PUT düzeltme, dry-run (yazmaz), uygula (öğrenci/veli/
öğretmen + kur-alacak + bakiye), idempotency (aynı dosya tekrar → mükerrer yok),
xlsx raporları. İzole DB (oba_test_toplu_kayit_smoke).
    cd appbackend
    .venv/Scripts/python.exe tests/test_toplu_kayit_smoke.py
"""
import asyncio
import os
import sys

TEST_DB = "oba_test_toplu_kayit_smoke"
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


CSV = (
    "kayıt tarihi,öğretmen,öğrenci,sınıf,kur,veli adı soyadı,,veli telefonu,notlar,durum,\n"
    "16.09.2024 17:02,seher hocam,Ali Yılmaz,3.sınıf,2,Ayşe Yılmaz,,05331397406,ödendi,Tamamlandı,\n"
    "01.11.2024 12.14,kÜbra özdemir,Ali Yılmaz,3,3,Ayşe Yılmaz,,05331397406,Disleksisi var,Tamamlandı,\n"
    ",Jülide,polat,2,4. ve 5. kur,Fatma Kaya,,+90 542 558 14 90,ramazandan sonra,,\n"
)


async def run():
    import uuid
    import server
    from core.auth import create_access_token
    from httpx import AsyncClient, ASGITransport

    await server.client.drop_database(TEST_DB)
    admin_id = str(uuid.uuid4())
    await server.db.users.insert_one({"id": admin_id, "ad": "Yön", "soyad": "Etici", "role": "admin"})
    H = {"Authorization": f"Bearer {create_access_token({'sub': admin_id})}"}
    # Eşleşecek öğretmenler
    await server.db.teachers.insert_many([
        {"id": "t-seher", "ad": "Seher", "soyad": "Akbaş", "yapilmasi_gereken_odeme": 0, "yapilan_odeme": 0},
        {"id": "t-kubra", "ad": "Kübra", "soyad": "Özdemir", "yapilmasi_gereken_odeme": 0, "yapilan_odeme": 0},
    ])

    transport = ASGITransport(app=server.app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1) Yükle
        r = await ac.post("/api/toplu-kayit/yukle", headers=H,
                          files={"dosya": ("liste.csv", CSV.encode("utf-8"), "text/csv")})
        check(r.status_code == 200, f"yükle 200 ({r.status_code})")
        tid = r.json()["taslak_id"]
        ozet = r.json()["ozet"]
        check(ozet["toplam_satir"] == 3, f"3 veri satırı (başlık atlandı) ({ozet['toplam_satir']})")
        check(ozet["temiz"] == 2 and ozet["elle"] == 1,
              f"kuyruk: temiz=2 (öğretmen otomatik eşleşti), elle=1 (polat) → {ozet}")

        # Taslak: öğretmen otomatik seçimi + çift kur + not sınıflandırma
        t = (await ac.get(f"/api/toplu-kayit/taslak/{tid}", headers=H)).json()
        s1 = next(s for s in t["satirlar"] if s["satir_no"] == 1)
        check(s1["secili_ogretmen_id"] == "t-seher", "'seher hocam' → t-seher otomatik seçildi")
        s2 = next(s for s in t["satirlar"] if s["satir_no"] == 2)
        check(s2["norm"]["egitim_notu"] and s2["norm"]["odeme_durumu"] != "iptal",
              "'Disleksisi var' → eğitim notu (muhasebeye değil)")
        s3 = next(s for s in t["satirlar"] if s["satir_no"] == 3)
        check(s3["norm"]["kurlar"] == [4, 5], "'4. ve 5. kur' → [4,5]")
        check(s3["kuyruk"] == "elle", "'polat' → elle kuyruğu")

        # 2) PUT: varsayılan ücret + polat satırını düzelt (elle tamamla)
        r = await ac.put(f"/api/toplu-kayit/taslak/{tid}", headers=H, json={
            "varsayilan_ucret": 1000,
            "satir_guncelle": [{"satir_no": 3, "secili_ogretmen_id": "t-kubra",
                                "norm": {"ogrenci_ad": "Deniz", "ogrenci_soyad": "Polat"}, "kuyruk": "temiz"}]})
        check(r.status_code == 200, "PUT 200")

        # 3) DRY-RUN — hiçbir şey yazmaz
        u0 = await server.db.users.count_documents({})
        st0 = await server.db.students.count_documents({})
        r = await ac.post(f"/api/toplu-kayit/uygula/{tid}?dry_run=true", headers=H)
        rap = r.json()["rapor"]
        check(r.status_code == 200 and r.json()["dry_run"] is True, "dry-run 200")
        check(rap["ogrenci_olusturuldu"] == 2 and rap["veli_olusturuldu"] == 2 and rap["ogretmen_eslesti"] == 2,
              f"dry-run planı: 2 öğrenci, 2 veli, 2 öğretmen eşleşti → {rap}")
        check(await server.db.users.count_documents({}) == u0 and await server.db.students.count_documents({}) == st0,
              "dry-run DB'ye YAZMADI")

        # 4) GERÇEK uygula
        r = await ac.post(f"/api/toplu-kayit/uygula/{tid}", headers=H)
        rap = r.json()["rapor"]
        check(r.status_code == 200, "uygula 200")
        # Ali Yılmaz: iki satır aynı öğrenci (tel+ad+soyad) → tek öğrenci, iki kur
        ali = await server.db.students.find_one({"ad": "Ali", "soyad": "Yılmaz"})
        check(ali is not None, "Ali Yılmaz öğrencisi oluştu (iki satır birleşti)")
        check(ali["yapilmasi_gereken_odeme"] == 2000.0, f"Ali beklenen = 2×1000 (iki kur) ({ali['yapilmasi_gereken_odeme']})")
        check(ali["yapilan_odeme"] == 1000.0, f"Ali ödenen = 1000 (Kur 2 ödendi) ({ali['yapilan_odeme']})")
        check(ali.get("egitim_notu"), "Ali eğitim notu (Disleksi) öğrenci kaydında")
        kur_say = await server.db.kur_ucretleri.count_documents({"ogrenci_id": ali["id"]})
        check(kur_say == 2, f"Ali için 2 kur alacağı ({kur_say})")
        # Veli tek hesap (telefon anahtar)
        veli = await server.db.users.count_documents({"role": "parent", "telefon": "+905331397406"})
        check(veli == 1, f"veli tek parent hesabı ({veli})")
        # Öğrenci user hesabı
        check(await server.db.users.count_documents({"role": "student", "linked_id": ali["id"]}) == 1, "Ali için student user hesabı")
        # Deniz Polat (düzeltilen) + çift kur [4,5]
        deniz = await server.db.students.find_one({"ad": "Deniz", "soyad": "Polat"})
        check(deniz is not None and await server.db.kur_ucretleri.count_documents({"ogrenci_id": deniz["id"]}) == 2,
              "Deniz Polat + 2 kur (4 ve 5)")

        # 5) İdempotency: aynı dosya tekrar → mükerrer YOK
        u_before = await server.db.users.count_documents({})
        st_before = await server.db.students.count_documents({})
        r2 = await ac.post("/api/toplu-kayit/yukle", headers=H,
                           files={"dosya": ("liste.csv", CSV.encode("utf-8"), "text/csv")})
        tid2 = r2.json()["taslak_id"]
        await ac.put(f"/api/toplu-kayit/taslak/{tid2}", headers=H, json={
            "varsayilan_ucret": 1000,
            "satir_guncelle": [{"satir_no": 3, "secili_ogretmen_id": "t-kubra",
                                "norm": {"ogrenci_ad": "Deniz", "ogrenci_soyad": "Polat"}, "kuyruk": "temiz"}]})
        r2 = await ac.post(f"/api/toplu-kayit/uygula/{tid2}", headers=H)
        rap2 = r2.json()["rapor"]
        check(await server.db.users.count_documents({}) == u_before, "tekrar-uygulama YENİ kullanıcı oluşturmadı (idempotent)")
        check(await server.db.students.count_documents({}) == st_before, "tekrar-uygulama YENİ öğrenci oluşturmadı")
        check(rap2["ogrenci_eslesti"] >= 2 and rap2["ogrenci_olusturuldu"] == 0, f"tekrar: eşleşti≥2, oluşturuldu=0 → {rap2}")
        ali2 = await server.db.students.find_one({"ad": "Ali", "soyad": "Yılmaz"})
        check(ali2["yapilmasi_gereken_odeme"] == 2000.0, "tekrar-uygulama bakiyeyi ŞİŞİRMEDİ (kur idempotent)")

        # 6) Raporlar (xlsx)
        rs = await ac.get(f"/api/toplu-kayit/rapor/{tid}/sifreler.xlsx", headers=H)
        check(rs.status_code == 200 and "spreadsheet" in rs.headers.get("content-type", ""), "şifreler.xlsx indirildi")
        rh = await ac.get(f"/api/toplu-kayit/rapor/{tid}/hatalar.xlsx", headers=H)
        check(rh.status_code == 200, "hatalar.xlsx indirildi")

        # 7) Zaten uygulanmış taslak tekrar uygulanamaz
        r = await ac.post(f"/api/toplu-kayit/uygula/{tid}", headers=H)
        check(r.status_code == 400, "uygulanmış taslak tekrar uygulanamaz (400)")

    await server.client.drop_database(TEST_DB)


if __name__ == "__main__":
    asyncio.run(run())
    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    sys.exit(1 if _kalan else 0)
