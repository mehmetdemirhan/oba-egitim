"""AI CEO — Deniz Güçlendirme (S9) smoke testi.

Kapsar: 9b veri kalitesi (her kural ≥1 vaka), 9c sayı doğrulama, 9e insan çıktı örneklem
guard, 9f maliyet sıçraması, 9g ikinci göz, 9d ret otopsisi, 9a sınav (mock, gerçek
kuyruğa/karneye karışmaz).

    cd appbackend
    PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe tests/test_ai_ceo_deniz_guc_smoke.py
"""
import asyncio
import os
import sys
from datetime import datetime, timezone, timedelta

TEST_DB = "oba_test_ai_ceo_deniz_guc"
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


def _eski(g):
    return (datetime.now(timezone.utc) - timedelta(days=g)).isoformat()


async def run():
    import server
    from httpx import AsyncClient, ASGITransport
    import modules.ai_ceo.analiz as analiz_mod
    import modules.ai_ceo.deniz as deniz_mod

    db = server.db
    await server.client.drop_database(TEST_DB)
    await db.users.insert_one({"id": "adm", "role": "admin", "ad": "A", "soyad": "M"})

    # Fotoğraf: konsantrasyon %22 (Deniz eşiği 20 < 22 < Ayda 25) → ikinci göz; muhasebe/sayı az
    await db.ai_ceo_fotograflar.insert_one({"id": "f1", "tarih": _eski(0),
        "konsantrasyon": {"en_buyuk_ogretmen_ogrenci_payi": 22.0, "esik_yuzde": 25.0},
        "ogretmen": {"geciken_kur_sayisi": 2}, "muhasebe": {"tahsil_edilen": 500}})

    # 9b veri kalitesi vakaları
    await db.students.insert_one({"id": "s1", "arsivli": True, "yapilmasi_gereken_odeme": 1000, "yapilan_odeme": 0})  # arşivli açık alacak
    await db.kur_ucretleri.insert_one({"id": "kghost", "ogrenci_id": "ghost", "tutar": 100, "yapilan_odeme": 0})       # yetim
    await db.kur_ucretleri.insert_one({"id": "kneg", "ogrenci_id": "s1", "tutar": -5, "yapilan_odeme": 0})             # negatif
    await db.kur_ucretleri.insert_one({"id": "kdmg", "ogrenci_id": "s1", "tutar": 100, "yapilan_odeme": 100, "durum": "tamamlandi"})  # damgasız hakediş
    await db.payments.insert_one({"id": "p1", "tip": "ogrenci", "kisi_id": "s1", "miktar": 100, "vergi": None})        # vergi eksik

    # 9c sayı doğrulama: fotoğrafta olmayan büyük sayılar
    await db.ai_ceo_oneriler.insert_one({"id": "o1", "kategori": "tahsilat", "oncelik": "orta", "durum": "yeni",
        "ozet": "Tahsilat 99999 arttı, 88888 öğrenci, 77777 gün, 66666 ve 55555 kayıt.",
        "beklenen_etki": "", "zayif_dayanak": False, "tarih": _eski(1)})
    # 9d ret otopsisi: 40 gün önce reddedilmiş, karar anı metriği 1000; şimdi 500 → haklı çıktı
    await db.ai_ceo_oneriler.insert_one({"id": "o2", "kategori": "tahsilat", "oncelik": "orta", "durum": "reddedildi",
        "durum_tarih": _eski(40), "_karar_ani_metrik": 1000, "ozet": "x", "tarih": _eski(45)})

    # 9e insan çıktı ihlali: öğretmen Miran çıktısında kıyas
    await db.ai_ceo_miran.insert_one({"id": "m1", "ogretmen_id": "t1",
        "icerik": {"oneriler": [{"aciklama": "Diğer öğretmenler senden iyi."}]}, "tarih": _eski(1)})

    # 9f maliyet sıçraması: önceki ay 1 çağrı, bu ay 5
    await db.ai_request_log.insert_one({"id": "r0", "model": "x", "tarih": "2026-06-01T00:00:00"})
    for i in range(5):
        await db.ai_request_log.insert_one({"id": f"r{i+1}", "model": "x", "tarih": "2026-07-10T00:00:00"})

    def H(u):
        return {"Authorization": f"Bearer {server.create_access_token({'sub': u})}"}

    async with AsyncClient(transport=ASGITransport(app=server.app), base_url="http://test") as ac:
        # denetimin AI turu kapalı (deterministik bulgular + maliyet sayacı temiz kalsın)
        deniz_mod.GEMINI_API_KEY = ""
        # ── denetle → 9b/9c/9e/9f/9g bulgular ──
        r = await ac.post("/api/ai/ceo/deniz/denetle", headers=H("adm"))
        turler = {b["tur"] for b in r.json()["bulgular"]}
        for beklenen in ("yetim_kayit", "negatif_kayit", "arsivli_acik_alacak", "damgasiz_hakedis"):
            check(beklenen in turler, f"9b veri kalitesi: {beklenen}")
        check("dogrulanamayan_sayi" in turler, "9c sayı doğrulama bulgusu")
        check("ciktı_ihlali" in turler, "9e insan çıktı guard ihlali yakalandı")
        check("maliyet_sicramasi" in turler, "9f maliyet sıçraması bulgusu")
        check("ikinci_goz_konsantrasyon" in turler, "9g bağımsız ikinci göz (Ayda'nın kaçırdığı) bulgusu")
        # sayı doğrulama oranı denetime işlendi
        check(r.json()["denetim"].get("sayi_dogrulama_orani", 0) > 0, "sayı doğrulama oranı denetime işlendi")

        # ── 9f maliyet endpoint ──
        r = await ac.get("/api/ai/ceo/deniz/maliyet", headers=H("adm"))
        check(r.json()["maliyet"]["toplam_cagri"] == 6 and r.json()["maliyet"]["anormal_sicrama_yuzde"], "maliyet özeti + anormal sıçrama")

        # ── 9d ret otopsisi ──
        r = await ac.get("/api/ai/ceo/deniz/ret-otopsisi", headers=H("adm"))
        ro = r.json()["ret_otopsisi"]
        check(ro["reddedilen"] == 1 and ro["ret_sonrasi_hakli_cikti"] == 1, f"ret otopsisi: 1 red, 1 'haklı çıktı' ({ro})")

        # ── 9a sınav (mock Ayda; gerçek kuyruğa KARIŞMAZ) ──
        oncesi_oneri = await db.ai_ceo_oneriler.count_documents({})
        analiz_mod.GEMINI_API_KEY = "k"
        deniz_mod.GEMINI_API_KEY = "k"

        async def sahte(system, user, max_tokens=4000):
            # Sınav fotoğraflarındaki sorunları YAKALAYAN Ayda cevabı
            kat = "ogrenci_memnuniyeti" if "nps" in user.lower() or "-40" in user else "strateji"
            return {"error": None, "parsed": {"ozet": "s", "oneriler": [
                {"baslik": "Konsantrasyon ve memnuniyet", "kategori": kat, "oncelik": "yuksek",
                 "ozet": "konsantrasyon bağımlılığı ve memnuniyet/nps riski var", "beklenen_etki": "?",
                 "dayanak_metrikler": [{"metrik": "x", "deger": 80}]}]}}
        analiz_mod.call_claude = sahte
        r = await ac.post("/api/ai/ceo/deniz/sinav", headers=H("adm"))
        s = r.json()["sinav"]
        check(r.json().get("ok") and s["skor"] == 100.0, f"sınav skoru %100 (Ayda iki sorunu da yakaladı) ({s['skor']})")
        sonrasi_oneri = await db.ai_ceo_oneriler.count_documents({})
        check(sonrasi_oneri == oncesi_oneri, "sınav sonuçları gerçek öneri kuyruğuna KARIŞMADI")
        check(await db.ai_ceo_deniz_sinav.count_documents({}) == 1, "sınav sonucu ayrı koleksiyonda")

        # ── karne: sınav + sayı doğrulama alanları ──
        r = await ac.get("/api/ai/ceo/deniz/karne", headers=H("adm"))
        k = r.json()["karne"]
        check(k.get("sinav_skoru") == 100.0, "Deniz karnesinde sınav kalitesi")
        check(k.get("sayi_dogrulanamayan_orani") is not None, "Deniz karnesinde sayı doğrulama oranı")

    await server.client.drop_database(TEST_DB)


if __name__ == "__main__":
    asyncio.run(run())
    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    sys.exit(1 if _kalan else 0)
