"""AI CEO — damgasız hakediş bulgusu KALİBRASYONU (yanlış-pozitif giderme).

Kural: Öğretmen hakedişi ancak 'yeni kur / eğitim tamamlandı' (durum=tamamlandi) İŞARETİ +
ödemenin bitmesi (kalan≈0) ile oluşur. Bulgu yalnız İKİSİ de olduğu halde damga
(odeme_tamamlanma_tarihi) yoksa üretilmeli. Aşağıdaki NORMAL durumlar hata SAYILMAMALI:
  - ödeme bitti ama öğretmen işaretlemedi (durum!=tamamlandi)
  - eğitim tamamlandı ama ödeme bitmedi (kalan>0)
  - tamamlandı + ödendi + zaten damgalı

    cd appbackend
    PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe tests/test_ai_ceo_hakedis_kalibrasyon_smoke.py
"""
import asyncio
import os
import sys

TEST_DB = "oba_test_ai_ceo_hakedis_kalib"
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
    import modules.ai_ceo.deniz_guc as G
    import modules.ai_ceo.miran as miran_mod

    db = server.db
    await server.client.drop_database(TEST_DB)
    for sid in ("s_a", "s_b", "s_c", "s_d"):
        await db.students.insert_one({"id": sid, "ad": sid, "soyad": "T"})
    # (1) ödeme bitti ama öğretmen işaretlemedi → NORMAL
    await db.kur_ucretleri.insert_one({"id": "k_a", "ogrenci_id": "s_a", "durum": "aktif", "tutar": 1000, "yapilan_odeme": 1000})
    # (2) eğitim tamamlandı ama ödeme bitmedi → NORMAL
    await db.kur_ucretleri.insert_one({"id": "k_b", "ogrenci_id": "s_b", "durum": "tamamlandi", "tutar": 1000, "yapilan_odeme": 0})
    # (3) tamamlandı + ödendi + damga YOK → GERÇEK EKSİK (tek bu işaretlenmeli)
    await db.kur_ucretleri.insert_one({"id": "k_c", "ogrenci_id": "s_c", "durum": "tamamlandi", "tutar": 1000, "yapilan_odeme": 1000})
    # (4) tamamlandı + ödendi + zaten damgalı → NORMAL
    await db.kur_ucretleri.insert_one({"id": "k_d", "ogrenci_id": "s_d", "durum": "tamamlandi", "tutar": 1000, "yapilan_odeme": 1000, "odeme_tamamlanma_tarihi": "2026-07-01T00:00:00"})

    # ── Deniz veri kalitesi ──
    bulgular = await G.veri_kalitesi_kontrol()
    dmg = next((b for b in bulgular if b["tur"] == "damgasiz_hakedis"), None)
    check(dmg is not None and dmg["kanit"]["sayi"] == 1, f"Deniz: yalnız 1 gerçek eksik işaretlendi ({dmg and dmg['kanit']['sayi']})")
    if dmg:
        idler = {o.get("kur_id") for o in dmg["kanit"]["ornekler"]}
        check(idler == {"k_c"}, f"Deniz: sadece k_c (tamamlandı+ödendi+damgasız) → {idler}")

    # ── Miran muhasebe verisi ──
    veri = await miran_mod._muhasebe_veri()
    check(veri["damgasiz_tamamlanan"] == 1, f"Miran: işaretsiz sayısı 1 ({veri['damgasiz_tamamlanan']})")
    check(veri["damgasiz_idler"] == ["s_c"], f"Miran: yalnız s_c öğrencisi ({veri['damgasiz_idler']})")

    # Yanlış-pozitif olmadığını açıkça doğrula
    check("k_a" not in (idler if dmg else set()) and veri["damgasiz_tamamlanan"] == 1,
          "ödeme bitti+işaretlenmedi (k_a) hata SAYILMADI")

    await server.client.drop_database(TEST_DB)


if __name__ == "__main__":
    asyncio.run(run())
    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    sys.exit(1 if _kalan else 0)
