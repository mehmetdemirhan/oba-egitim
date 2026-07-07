"""TIMI (Teele Çoklu Zeka Envanteri) smoke testi.

Kapsar:
- Puanlama anahtarı dengesi: her kategori tam 8 kez görsel olarak görünür.
- timi_puanla: Çınar DOĞANCI örneği (28 seçim) → kategori toplamları (3,4,4,1,8,5,3).
- baskin_alanlar: en yüksek + eşitlik.
- Endpoint e2e: baslat → yanit (28) → tamamla → ogrenci geçmişi + tek getir.
- Rol: öğrenci uygulayamaz (403); eksik yanıtla tamamlama 400.

İzole test DB'sine karşı çalışır (oba_test_timi). Gerçek DB'ye dokunmaz.
    cd appbackend
    .venv/Scripts/python.exe tests/test_timi_smoke.py
"""
import asyncio
import os
import sys
import uuid

TEST_DB = "oba_test_timi"
os.environ["MONGO_URL"] = os.environ.get("MONGO_URL_TEST", "mongodb://localhost:27017")
os.environ["DB_NAME"] = TEST_DB
os.environ.setdefault("SECRET_KEY", "test-secret-key")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_gecen = 0
_kalan = 0

# Çınar DOĞANCI örnek formu: 28 kart için A/B seçimleri → beklenen (3,4,4,1,8,5,3)
CINAR = "ABAABABBABBBBABBBBABBABBBBAB"
CINAR_BEKLENEN = {
    "dilsel": 3, "mantiksal_matematiksel": 4, "mekansal": 4,
    "muziksel": 1, "bedensel": 8, "kisisel": 5, "kisilerarasi": 3,
}


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
    from modules.timi import (
        timi_puanla, baskin_alanlar, KART_MAP, KATEGORI_NO_KEY, KATEGORI_SIRA, TOPLAM_KART,
    )
    from httpx import AsyncClient, ASGITransport

    await server.client.drop_database(TEST_DB)

    # ── 1) Anahtar dengesi: her kategori tam 8 kez ──
    sayac = {i: 0 for i in range(1, 8)}
    for kart in KART_MAP.values():
        sayac[kart["A"]] += 1
        sayac[kart["B"]] += 1
    check(TOPLAM_KART == 28 and len(KART_MAP) == 28, "28 kart yüklendi")
    check(all(sayac[i] == 8 for i in range(1, 8)), f"her kategori tam 8 kez ({sayac})")
    check(len(KATEGORI_SIRA) == 7, "7 kategori")

    # ── 2) Çınar örneği puanlama ──
    yanitlar = [{"kart_no": i + 1, "secim": CINAR[i]} for i in range(28)]
    puan = timi_puanla(yanitlar)
    check(puan == CINAR_BEKLENEN, f"Çınar toplamları (3,4,4,1,8,5,3) → {puan}")
    # sıraya göre demet: (dilsel, mantiksal, mekansal, muziksel, bedensel, kisisel, kisilerarasi)
    demet = tuple(puan[k] for k in KATEGORI_SIRA)
    check(demet == (3, 4, 4, 1, 8, 5, 3), f"sıralı demet {demet}")

    # ── 3) baskin_alanlar ──
    check(baskin_alanlar(puan) == ["bedensel"], "baskın alan = bedensel (8)")
    check(sorted(baskin_alanlar({"dilsel": 8, "mekansal": 8, "muziksel": 2, "mantiksal_matematiksel": 0,
                                 "bedensel": 0, "kisisel": 0, "kisilerarasi": 0})) == ["dilsel", "mekansal"],
          "eşitlikte tüm baskın alanlar listelenir")

    # ── Test kullanıcıları ──
    ogr_rec = str(uuid.uuid4())
    await server.db.students.insert_one({"id": ogr_rec, "ad": "Çınar", "soyad": "Doğancı", "sinif": "3"})
    teacher_id = str(uuid.uuid4())
    await server.db.users.insert_one({"id": teacher_id, "role": "teacher", "ad": "Öğ", "soyad": "Retmen"})
    H_t = {"Authorization": f"Bearer {create_access_token({'sub': teacher_id})}"}
    stu_id = str(uuid.uuid4())
    await server.db.users.insert_one({"id": stu_id, "role": "student", "linked_id": ogr_rec})
    H_s = {"Authorization": f"Bearer {create_access_token({'sub': stu_id})}"}

    transport = ASGITransport(app=server.app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # ── 4) meta ──
        r = await ac.get("/api/timi/meta", headers=H_t)
        check(r.status_code == 200 and r.json()["toplam_kart"] == 28 and len(r.json()["kategoriler"]) == 7,
              "meta: 28 kart + 7 kategori")

        # ── 5) baslat ──
        r = await ac.post("/api/timi/baslat", headers=H_t, json={"ogrenci_id": ogr_rec})
        check(r.status_code == 200, f"baslat 200 (status={r.status_code})")
        sid = r.json()["id"]
        check(r.json()["durum"] == "devam" and r.json()["sinif_seviyesi"] == "3",
              "oturum devam + sınıf öğrenciden çekildi")

        # ── 6) 28 yanıt işaretle (tek tek) ──
        for i in range(28):
            r = await ac.patch(f"/api/timi/{sid}/yanit", headers=H_t, json={"kart_no": i + 1, "secim": CINAR[i]})
            assert r.status_code == 200, r.text
        check(r.json()["yanit_sayisi"] == 28, "28 yanıt kaydedildi")
        # aynı kartı yeniden işaretle → tekilleşir (sayı artmaz)
        r = await ac.patch(f"/api/timi/{sid}/yanit", headers=H_t, json={"kart_no": 1, "secim": "B"})
        check(r.json()["yanit_sayisi"] == 28, "aynı kart yeniden işaretlenince yanıt sayısı sabit (tekil)")
        # düzeltmeyi geri al (kart 1 → A, Çınar profili korunsun)
        await ac.patch(f"/api/timi/{sid}/yanit", headers=H_t, json={"kart_no": 1, "secim": "A"})

        # ── 7) geçersiz yanıt ──
        r = await ac.patch(f"/api/timi/{sid}/yanit", headers=H_t, json={"kart_no": 99, "secim": "A"})
        check(r.status_code == 400, "geçersiz kart no 400")
        r = await ac.patch(f"/api/timi/{sid}/yanit", headers=H_t, json={"kart_no": 5, "secim": "C"})
        check(r.status_code == 400, "geçersiz seçim 400")

        # ── 8) tamamla → puanla ──
        r = await ac.post(f"/api/timi/{sid}/tamamla", headers=H_t, json={"notlar": "Gözlem"})
        check(r.status_code == 200, f"tamamla 200 (status={r.status_code})")
        tj = r.json()
        check(tj["durum"] == "tamamlandi" and tj["kategori_puanlari"] == CINAR_BEKLENEN,
              "tamamlandı + kategori puanları doğru")
        check(tj["baskin_zeka_alanlari"] == ["bedensel"] and tj["notlar"] == "Gözlem",
              "baskın alan bedensel + not kaydedildi")

        # ── 9) eksik yanıtla tamamlama 400 ──
        r2 = await ac.post("/api/timi/baslat", headers=H_t, json={"ogrenci_id": ogr_rec})
        sid2 = r2.json()["id"]
        await ac.patch(f"/api/timi/{sid2}/yanit", headers=H_t, json={"kart_no": 1, "secim": "A"})
        r = await ac.post(f"/api/timi/{sid2}/tamamla", headers=H_t, json={})
        check(r.status_code == 400, "eksik yanıtla tamamlama 400")

        # ── 10) öğrenci geçmişi (2 oturum) + tek getir ──
        r = await ac.get(f"/api/timi/ogrenci/{ogr_rec}", headers=H_t)
        check(r.status_code == 200 and len(r.json()) == 2, "öğrenci TIMI geçmişi 2 oturum")
        r = await ac.get(f"/api/timi/{sid}", headers=H_t)
        check(r.status_code == 200 and r.json()["id"] == sid, "tek oturum getir")

        # ── 11) rol: öğrenci uygulayamaz ──
        r = await ac.post("/api/timi/baslat", headers=H_s, json={"ogrenci_id": ogr_rec})
        check(r.status_code == 403, "öğrenci TIMI başlatamaz (403)")

        # ── 12) tümünü tek seferde tamamla (yanitlar gövdede) ──
        r3 = await ac.post("/api/timi/baslat", headers=H_t, json={"ogrenci_id": ogr_rec})
        sid3 = r3.json()["id"]
        r = await ac.post(f"/api/timi/{sid3}/tamamla", headers=H_t,
                          json={"yanitlar": yanitlar})
        check(r.status_code == 200 and r.json()["kategori_puanlari"] == CINAR_BEKLENEN,
              "tek seferde yanıtlarla tamamlama da doğru puanlar")

    await server.client.drop_database(TEST_DB)


def main():
    asyncio.run(run())
    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    sys.exit(0 if _kalan == 0 else 1)


if __name__ == "__main__":
    main()
