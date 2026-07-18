"""AI Dikkat — duplike route temizliği sonrası bütünlük smoke.

Kapsam: POST /ai/dikkat/kaydet ve GET /ai/dikkat/gecmis artık TEKİL (gölge duplike'ler kaldırıldı);
canlı KANONİK sürüm (#193/#240 — iç içe metrikler/analiz şeması, _dikkat_skoru_hesapla,
okuma_dna.boyutlar.dikkat_suresi) çalışıyor; ölü #251/#355'in düz şeması (dikkat_skoru/seviye/
ai_yorum top-level) YAZILMIYOR.

    cd appbackend
    PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe tests/test_ai_dikkat_smoke.py
"""
import asyncio
import os
import sys

TEST_DB = "oba_test_ai_dikkat"
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

    db = server.db
    await server.client.drop_database(TEST_DB)
    await db.users.insert_one({"id": "stud1", "role": "student", "ad": "Öğ", "soyad": "R"})
    # Kanonik #193 okuma_dna'yı yalnız MEVCUT doküman varsa günceller (upsert yok) → tohumla
    await db.okuma_dna.insert_one({"ogrenci_id": "stud1", "boyutlar": {}})

    def H(u):
        return {"Authorization": f"Bearer {server.create_access_token({'sub': u})}"}

    # ── Route bütünlüğü: duplike kalktı, tekil kaldı ──
    def route_say(path, method):
        return sum(1 for r in server.app.routes if getattr(r, "path", None) == path and method in getattr(r, "methods", set()))
    check(route_say("/api/ai/dikkat/kaydet", "POST") == 1, f"POST /ai/dikkat/kaydet TEKİL ({route_say('/api/ai/dikkat/kaydet','POST')})")
    check(route_say("/api/ai/dikkat/gecmis/{ogrenci_id}", "GET") == 1, f"GET /ai/dikkat/gecmis TEKİL ({route_say('/api/ai/dikkat/gecmis/{ogrenci_id}','GET')})")

    async with AsyncClient(transport=ASGITransport(app=server.app), base_url="http://test") as ac:
        # ── Kanonik #193 sözleşmesi: kaydet ──
        govde = {"sure_sn": 120, "kelime_sayisi": 100, "geri_scroll_sayisi": 2,
                 "zorluk_kelimeler": ["kel"], "duraklamalar": 1, "sinif": 3, "kitap_adi": "Kitap", "bolum": "1"}
        r = await ac.post("/api/ai/dikkat/kaydet", headers=H("stud1"), json=govde)
        body = r.json()
        check(r.status_code == 200 and "dikkat_skoru" in body and "id" in body, f"kaydet çalıştı (dikkat_skoru + id) ({r.status_code})")

        # ── dikkat_log KANONİK (iç içe) şemada, ölü düz şemada DEĞİL ──
        kayit = await db.dikkat_log.find_one({"ogrenci_id": "stud1"})
        check(isinstance(kayit.get("metrikler"), dict) and isinstance(kayit.get("analiz"), dict) and "kitap_adi" in kayit,
              "dikkat_log KANONİK şema (iç içe metrikler/analiz + kitap_adi)")
        check("seviye" not in kayit and "ai_yorum" not in kayit and "dikkat_skoru" not in kayit,
              "ölü #251'in düz şeması (top-level seviye/ai_yorum/dikkat_skoru) YAZILMADI")

        # ── okuma_dna KANONİK yol (boyutlar.dikkat_suresi) ──
        dna = await db.okuma_dna.find_one({"ogrenci_id": "stud1"})
        check(dna and isinstance(dna.get("boyutlar"), dict) and "dikkat_suresi" in dna["boyutlar"],
              "okuma_dna KANONİK yol güncellendi (boyutlar.dikkat_suresi)")

        # ── gecmis ──
        r = await ac.get("/api/ai/dikkat/gecmis/stud1", headers=H("stud1"))
        gec = r.json()
        check(r.status_code == 200 and isinstance(gec, list) and len(gec) == 1 and "metrikler" in gec[0],
              f"gecmis kaydı döndürüyor ({len(gec) if isinstance(gec, list) else '?'})")

    await server.client.drop_database(TEST_DB)


if __name__ == "__main__":
    asyncio.run(run())
    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    sys.exit(1 if _kalan else 0)
