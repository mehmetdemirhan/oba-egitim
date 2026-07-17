"""TIMI (Teele Çoklu Zeka Envanteri) modülü smoke testi.

İki aşama:
  1) Saf puanlama fonksiyonları (DB gerektirmez): puanlama anahtarının bütünlüğü
     (her kategori tam 8 kez), örnek forma denk gelen 28 seçimin (3,4,4,1,8,5,3)
     totallerini üretmesi, baskın alan tespiti.
  2) API akışı (izole test DB'sine karşı): baslat → yanit → tamamla → sorgu.

Çalıştırma:
    cd appbackend
    .venv/Scripts/python.exe tests/test_timi_smoke.py
"""
import asyncio
import os
import sys
import uuid

TEST_DB = "oba_test_timi_smoke"
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


# Örnek uygulama formundaki (Çınar DOĞANCI, 04.08.2024) totalleri
# (dilsel 3, mantıksal 4, mekansal 4, müziksel 1, bedensel 8, kişisel 5,
# kişilerarası 3) üreten, puanlama anahtarıyla doğrulanmış bir seçim vektörü.
ORNEK_YANITLAR = [
    {"kart_no": 1, "secim": "B"}, {"kart_no": 2, "secim": "B"}, {"kart_no": 3, "secim": "B"},
    {"kart_no": 4, "secim": "B"}, {"kart_no": 5, "secim": "B"}, {"kart_no": 6, "secim": "B"},
    {"kart_no": 7, "secim": "B"}, {"kart_no": 8, "secim": "B"}, {"kart_no": 9, "secim": "B"},
    {"kart_no": 10, "secim": "B"}, {"kart_no": 11, "secim": "A"}, {"kart_no": 12, "secim": "B"},
    {"kart_no": 13, "secim": "B"}, {"kart_no": 14, "secim": "A"}, {"kart_no": 15, "secim": "B"},
    {"kart_no": 16, "secim": "B"}, {"kart_no": 17, "secim": "A"}, {"kart_no": 18, "secim": "B"},
    {"kart_no": 19, "secim": "A"}, {"kart_no": 20, "secim": "A"}, {"kart_no": 21, "secim": "A"},
    {"kart_no": 22, "secim": "A"}, {"kart_no": 23, "secim": "B"}, {"kart_no": 24, "secim": "A"},
    {"kart_no": 25, "secim": "A"}, {"kart_no": 26, "secim": "B"}, {"kart_no": 27, "secim": "A"},
    {"kart_no": 28, "secim": "A"},
]
BEKLENEN_TOTALLER = {
    "dilsel": 3, "mantiksal_matematiksel": 4, "mekansal": 4, "muziksel": 1,
    "bedensel": 8, "kisisel": 5, "kisilerarasi": 3,
}


def saf_kontroller():
    from modules.timi import (
        TIMI_KARTLAR, TIMI_KATEGORILER, TIMI_KART_SAYISI,
        timi_puanla, baskin_zeka_alanlari,
    )
    print("[1] Saf puanlama fonksiyonları")

    check(len(TIMI_KARTLAR) == TIMI_KART_SAYISI == 28, "28 kart tanımlı")

    # Anahtar bütünlüğü: her kategori tam 8 kez görsel olarak görünür
    sayac = {i: 0 for i in range(1, 8)}
    for a_cat, b_cat in TIMI_KARTLAR.values():
        sayac[a_cat] += 1
        sayac[b_cat] += 1
    check(all(v == 8 for v in sayac.values()),
          f"her kategori tam 8 kez görünüyor ({sayac})")
    check(sum(sayac.values()) == 56, "toplam 56 görsel (28 kart x 2)")

    # Örnek form totalleri
    puanlar = timi_puanla(ORNEK_YANITLAR)
    check(puanlar == BEKLENEN_TOTALLER,
          f"örnek form totalleri (3,4,4,1,8,5,3) doğru → {puanlar}")
    check(sum(puanlar.values()) == 28, "puan toplamı 28 (her kart 1 puan)")

    # Baskın alan
    baskin = baskin_zeka_alanlari(puanlar)
    check(baskin == ["bedensel"], f"baskın zeka alanı = bedensel (8/8) → {baskin}")

    # Eşitlik durumunda hepsi listelenir
    esit = {k: 0 for k in BEKLENEN_TOTALLER}
    esit["dilsel"] = 4
    esit["muziksel"] = 4
    check(set(baskin_zeka_alanlari(esit)) == {"dilsel", "muziksel"},
          "eşitlikte tüm baskın alanlar listeleniyor")

    # Kategori anahtarları timi_scoring_key.json ile birebir
    beklenen_keyler = {"dilsel", "mantiksal_matematiksel", "mekansal", "muziksel",
                       "bedensel", "kisisel", "kisilerarasi"}
    check({TIMI_KATEGORILER[i]["key"] for i in range(1, 8)} == beklenen_keyler,
          "7 kategori anahtarı doğru")


async def api_kontroller():
    print("[2] API akışı")
    import server
    from core.auth import create_access_token
    from httpx import AsyncClient, ASGITransport

    await server.client.drop_database(TEST_DB)

    teacher_id = str(uuid.uuid4())
    await server.db.users.insert_one({"id": teacher_id, "ad": "Ogr", "soyad": "T", "role": "teacher", "puan": 0})
    TH = {"Authorization": f"Bearer {create_access_token({'sub': teacher_id})}"}

    ogr_id = str(uuid.uuid4())
    await server.db.students.insert_one({"id": ogr_id, "ad": "Cinar", "soyad": "Doganci", "sinif": "1", "toplam_xp": 0})

    transport = ASGITransport(app=server.app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Meta
        r = await ac.get("/api/timi/meta", headers=TH)
        check(r.status_code == 200 and r.json().get("kart_sayisi") == 28, "meta okundu (28 kart)")
        check("uyari_notu" in r.json() and len(r.json()["uyari_notu"]) > 0, "psikometrik uyarı notu meta'da mevcut")

        # Baslat
        r = await ac.post("/api/timi/baslat", json={"ogrenci_id": ogr_id}, headers=TH)
        check(r.status_code == 200, f"oturum başlatıldı (status={r.status_code})")
        sonuc_id = r.json()["id"]
        check(r.json().get("sinif_seviyesi") == "1", "sınıf seviyesi öğrenciden otomatik çekildi")

        # Kademeli yanıt kaydı (ilk 2 kart) + düzeltme (kart 1 üzerine yazma)
        await ac.patch(f"/api/timi/{sonuc_id}/yanit", json={"kart_no": 1, "secim": "A"}, headers=TH)
        r = await ac.patch(f"/api/timi/{sonuc_id}/yanit", json={"kart_no": 1, "secim": "B"}, headers=TH)
        check(r.status_code == 200 and r.json()["yanit_sayisi"] == 1, "aynı kartın yanıtı üzerine yazıldı (geri dön düzeltmesi)")

        # Eksik yanıtla tamamla → 400
        r = await ac.post(f"/api/timi/{sonuc_id}/tamamla", json={"yanitlar": ORNEK_YANITLAR[:5]}, headers=TH)
        check(r.status_code == 400, "eksik yanıtla tamamlama reddedildi (400)")

        # Tam yanıtla tamamla
        r = await ac.post(f"/api/timi/{sonuc_id}/tamamla", json={"yanitlar": ORNEK_YANITLAR, "notlar": "Sakin, işbirlikçi."}, headers=TH)
        check(r.status_code == 200, f"envanter tamamlandı (status={r.status_code})")
        body = r.json()
        check(body.get("kategori_puanlari") == BEKLENEN_TOTALLER,
              f"API kategori puanları (3,4,4,1,8,5,3) → {body.get('kategori_puanlari')}")
        check(body.get("baskin_zeka_alanlari") == ["bedensel"], "API baskın alan = bedensel")
        check(body.get("durum") == "tamamlandi", "durum tamamlandi")

        # Öğrenci geçmişi
        r = await ac.get(f"/api/timi/ogrenci/{ogr_id}", headers=TH)
        check(r.status_code == 200 and len(r.json()) == 1, "öğrenci TIMI geçmişi listelendi")

        # Panel listesi
        r = await ac.get("/api/timi/sessions", headers=TH)
        check(r.status_code == 200 and any(s["id"] == sonuc_id for s in r.json()), "sessions listesinde")

        # Öğrenci rolü uygulayamaz (403)
        student_id = str(uuid.uuid4())
        await server.db.users.insert_one({"id": student_id, "ad": "X", "soyad": "Y", "role": "student", "puan": 0})
        SH = {"Authorization": f"Bearer {create_access_token({'sub': student_id})}"}
        r = await ac.post("/api/timi/baslat", json={"ogrenci_id": ogr_id}, headers=SH)
        check(r.status_code == 403, "öğrenci rolü envanter başlatamaz (403)")

        # ── Puanlama anahtarı yönetimi (Koordinatör/Yönetici) + geçmiş korunması ──
        admin_id = str(uuid.uuid4())
        await server.db.users.insert_one({"id": admin_id, "ad": "Adm", "soyad": "N", "role": "admin", "puan": 0})
        AH = {"Authorization": f"Bearer {create_access_token({'sub': admin_id})}"}

        r = await ac.get("/api/timi/anahtar", headers=AH)
        check(r.status_code == 200 and r.json().get("dengeli") is True, "anahtar okundu, varsayılan dengeli (her kategori 8×)")
        kartlar = r.json()["kartlar"]

        r = await ac.put("/api/timi/anahtar", json={"kartlar": kartlar}, headers=TH)
        check(r.status_code == 403, "öğretmen anahtarı düzenleyemez (403)")

        # Kart 1 B: mekansal(3) → mantıksal(2) — dengeyi bozar ama engellenmez
        for k in kartlar:
            if k["kart_no"] == 1:
                k["b_kategori"] = 2
        r = await ac.put("/api/timi/anahtar", json={"kartlar": kartlar}, headers=AH)
        check(r.status_code == 200 and r.json().get("dengeli") is False, "admin anahtarı değiştirdi (denge bozuk, engellenmedi)")

        # Yeni uygulama güncel anahtarla puanlanır (aynı yanıtlar, farklı sonuç)
        r = await ac.post("/api/timi/baslat", json={"ogrenci_id": ogr_id}, headers=TH)
        yeni_id = r.json()["id"]
        r = await ac.post(f"/api/timi/{yeni_id}/tamamla", json={"yanitlar": [y for y in ORNEK_YANITLAR]}, headers=TH)
        yp = r.json()["kategori_puanlari"]
        check(yp["mekansal"] == 3 and yp["mantiksal_matematiksel"] == 5, "yeni sonuç güncel anahtarla puanlandı (mekansal 4→3, mantıksal 4→5)")

        # Değişiklikten ÖNCE tamamlanan eski sonuç YENİDEN HESAPLANMAZ
        r = await ac.get(f"/api/timi/{sonuc_id}", headers=AH)
        check(r.json()["kategori_puanlari"]["mekansal"] == 4, "eski sonuç korundu (mekansal hâlâ 4, yeniden hesaplanmadı)")

        r = await ac.post("/api/timi/anahtar/varsayilana-don", headers=AH)
        check(r.status_code == 200 and r.json().get("dengeli") is True, "varsayılan anahtara sıfırlandı")

    await server.client.drop_database(TEST_DB)


async def _hepsi():
    # saf_kontroller modules.timi'yi import eder; core.db motor/gridfs bağlanması için
    # bunun çalışan loop İÇİNDE olması gerekir (Python 3.14).
    saf_kontroller()
    await api_kontroller()


def main():
    try:
        asyncio.run(_hepsi())
    except Exception as e:
        print(f"  [UYARI] API aşaması çalıştırılamadı (MongoDB gerekli): {type(e).__name__}: {e}")
    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    sys.exit(0 if _kalan == 0 else 1)


if __name__ == "__main__":
    main()
