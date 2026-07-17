"""AI CEO — Deniz bulgu detayı + çözüm promptu + Kontrol Et (P1/P2/P3) smoke.

Kapsar: bulgu detay + kanıt (örnekler/derin link) + çözüm (şablon prompt vs operasyonel
adım); Kontrol Et → çözüldü/devam/AI-erteleme + karne + islem_log.

    cd appbackend
    PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe tests/test_ai_ceo_deniz_cozum_smoke.py
"""
import asyncio
import os
import sys

TEST_DB = "oba_test_ai_ceo_deniz_cozum"
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
    import modules.ai_ceo.deniz as deniz_mod

    db = server.db
    await server.client.drop_database(TEST_DB)
    await db.users.insert_one({"id": "adm", "role": "admin", "ad": "A", "soyad": "M"})
    await db.students.insert_one({"id": "s1"})
    # yetim kur (kritik) + damgasız hakediş (orta)
    await db.kur_ucretleri.insert_one({"id": "kghost", "ogrenci_id": "ghost", "tutar": 100, "yapilan_odeme": 0})
    await db.kur_ucretleri.insert_one({"id": "kdmg", "ogrenci_id": "s1", "tutar": 100, "yapilan_odeme": 100, "durum": "tamamlandi"})

    def H(u):
        return {"Authorization": f"Bearer {server.create_access_token({'sub': u})}"}

    async with AsyncClient(transport=ASGITransport(app=server.app), base_url="http://test") as ac:
        deniz_mod.GEMINI_API_KEY = ""  # deterministik denetim
        r = await ac.post("/api/ai/ceo/deniz/denetle", headers=H("adm"))
        bulgular = {b["tur"]: b for b in r.json()["bulgular"]}
        yetim = bulgular["yetim_kayit"]; damga = bulgular["damgasiz_hakedis"]

        # ── P1: detay + kanıt (derin link örnekleri) ──
        r = await ac.get(f"/api/ai/ceo/deniz/bulgu/{yetim['id']}", headers=H("adm"))
        d = r.json()
        check(r.status_code == 200, "bulgu detay 200")
        ornek = (d["bulgu"]["kanit"] or {}).get("ornekler")
        check(ornek and ornek[0].get("kur_id") == "kghost", "kanıt derin link örneği (kur_id=kghost)")

        # ── P2: çözüm — şablon prompt vs operasyonel adım ──
        cz = d["cozum"]
        check(cz["tip"] == "prompt", "yetim → kod düzeltmesi (prompt tipi)")
        check("refactor/modular-server" in cz["prompt"] and "TEST ŞARTI" in cz["prompt"], "prompt formatı (test şartı + deploy kapanışı)")
        check("SORUN" in cz["prompt"] and "KANIT" in cz["prompt"], "prompt sorun+kanıt içeriyor")
        r2 = await ac.get(f"/api/ai/ceo/deniz/bulgu/{damga['id']}", headers=H("adm"))
        cz2 = r2.json()["cozum"]
        check(cz2["tip"] == "operasyonel" and "adim" in cz2, "damgasız hakediş → operasyonel adım kartı")

        # AI-turu bulgusu → prompt'a dönüşür
        await db.ai_ceo_deniz_bulgular.insert_one({"id": "bai", "denetim_id": "x", "tur": "mantik", "onem": "orta",
                                                   "ozet": "AI bulgusu", "kaynak": "ai", "durum": "yeni", "tarih": "2026-07-16T00:00:00"})
        r = await ac.get("/api/ai/ceo/deniz/bulgu/bai", headers=H("adm"))
        check(r.json()["cozum"]["tip"] == "prompt" and "refactor/modular-server" in r.json()["cozum"]["prompt"], "AI-turu bulgusu prompt formatına dönüştü")

        # ── P3: Kontrol Et ──
        # damgasız hâlâ var → devam
        r = await ac.post(f"/api/ai/ceo/deniz/bulgu/{damga['id']}/kontrol", headers=H("adm"))
        check(r.json()["durum"] == "devam", "Kontrol Et: hâlâ var → 'devam' + güncel kanıt")
        # AI bulgu → sonraki tur
        r = await ac.post("/api/ai/ceo/deniz/bulgu/bai/kontrol", headers=H("adm"))
        check(r.json()["durum"] == "sonraki_tur", "AI-turu bulgu → 'sonraki_tur' (ayrı AI çağrısı yok)")
        # yetim'i DÜZELT (ghost kur sil) → kontrol → çözüldü
        await db.kur_ucretleri.delete_one({"id": "kghost"})
        r = await ac.post(f"/api/ai/ceo/deniz/bulgu/{yetim['id']}/kontrol", headers=H("adm"))
        check(r.json()["durum"] == "cozuldu" and r.json()["bulgu_durum"] == "cozuldu", "Kontrol Et: sorun giderildi → 'çözüldü'")
        gb = await db.ai_ceo_deniz_bulgular.find_one({"id": yetim["id"]})
        check(gb.get("cozulme_tarihi"), "çözülme tarihi damgalandı")
        # karne: kritik yakalama arttı (yetim kritikti, çözüldü)
        r = await ac.get("/api/ai/ceo/deniz/karne", headers=H("adm"))
        check(r.json()["karne"]["yakalama_degeri"] == 100.0, f"karne kritik yakalama %100 ({r.json()['karne']['yakalama_degeri']})")
        # islem_log
        check(await db.islem_log.find_one({"islem": "deniz_kontrol"}) is not None, "Kontrol Et islem_log'a düştü")

    await server.client.drop_database(TEST_DB)


if __name__ == "__main__":
    asyncio.run(run())
    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    sys.exit(1 if _kalan else 0)
