"""AI CEO — Kurul analitik S6-B (NPS/müşteri sesi + kazanım + kurul PDF) smoke.

Kapsar: NPS gönderimi (öğrenci takma-ID, kişisel veri yok) + özet/dağılım; çıkış nedeni;
NPS sağlık skoru bileşeni + negatif NPS anomalisi; öğrenme kazanımı proxy bloğu; Kurul
Özeti PDF.

    cd appbackend
    PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe tests/test_ai_ceo_kurul_b_smoke.py
"""
import asyncio
import json
import os
import sys

TEST_DB = "oba_test_ai_ceo_kurul_b"
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
    await db.users.insert_one({"id": "adm", "role": "admin", "ad": "A", "soyad": "M"})
    await db.users.insert_one({"id": "veli", "role": "parent", "ad": "V", "soyad": "L"})
    # Kazanım proxy için: öğrenci kur 3 + 1 rozet → 3*15 + 1*5 = 50
    await db.students.insert_one({"id": "s1", "ogretmen_id": "t1", "aldigi_egitim": "Genel", "kur": "3"})
    await db.kazanilan_rozetler.insert_one({"kullanici_id": "s1", "rozet_kodu": "r1"})

    def H(u):
        return {"Authorization": f"Bearer {server.create_access_token({'sub': u})}"}

    async with AsyncClient(transport=ASGITransport(app=server.app), base_url="http://test") as ac:
        # ── NPS gönderimi (5 kayıt: 2 promoter, 3 detractor → NPS=-20) ──
        for puan, yorum in [(10, "Harika"), (9, "İyi"), (2, "Kötü"), (3, ""), (4, "İletişim zayıf")]:
            r = await ac.post("/api/ai/ceo/nps", headers=H("veli"), json={"ogrenci_id": "s1", "kur": "3", "puan": puan, "yorum": yorum})
            assert r.status_code == 200
        check(await db.ai_ceo_nps.count_documents({}) == 5, "5 NPS kaydı")
        # KVKK: gerçek öğrenci id saklanmaz, takma-ID saklanır
        bir = await db.ai_ceo_nps.find_one({})
        check("ogrenci_id" not in bir and str(bir.get("ogrenci_takma", "")).startswith("O-"), "NPS'te gerçek id yok, takma-ID var (KVKK)")
        r = await ac.get("/api/ai/ceo/nps/ozet", headers=H("adm"))
        oz = r.json()["nps"]
        check(oz["nps"] == -20.0, f"NPS = (2-3)/5×100 = -20 ({oz['nps']})")
        check(oz["promoter"] == 2 and oz["detractor"] == 3, "promoter=2, detractor=3")

        # geçersiz puan reddi
        r = await ac.post("/api/ai/ceo/nps", headers=H("veli"), json={"puan": 15})
        check(r.status_code == 400, "geçersiz NPS puanı (15) reddedildi")

        # ── çıkış nedeni ──
        r = await ac.post("/api/ai/ceo/cikis-nedeni", headers=H("adm"), json={"ogrenci_id": "s2", "neden": "fiyat"})
        check(r.status_code == 200, "çıkış nedeni kaydedildi")
        r = await ac.get("/api/ai/ceo/nps/ozet", headers=H("adm"))
        check(r.json()["cikis_dagilimi"].get("fiyat") == 1, "çıkış nedeni dağılımı (fiyat=1)")

        # ── fotoğraf: kazanım + NPS blokları + sağlık bileşeni ──
        r = await ac.post("/api/ai/ceo/fotograf/cek", headers=H("adm"))
        foto = r.json()["fotograf"]
        check(foto["kazanim"]["ort_kazanim"] == 50.0, f"kazanım proxy = 3*15+1*5 = 50 ({foto['kazanim']['ort_kazanim']})")
        check("yontem" in foto["kazanim"], "kazanım yöntemi (proxy) etiketli")
        check(foto["nps"]["nps"] == -20.0, "fotoğrafta NPS bloğu")
        r = await ac.get("/api/ai/ceo/saglik", headers=H("adm"))
        adlar = [b["ad"] for b in r.json()["saglik"]["bilesenler"]]
        check("NPS" in adlar, "NPS sağlık skoru bileşeni")

        # ── negatif NPS anomalisi ──
        r = await ac.get("/api/ai/ceo/anomali", headers=H("adm"))
        check("nps_dususu" in [a["tip"] for a in r.json()["anomaliler"]], "negatif NPS anomalisi üretildi")

        # ── Kurul Özeti PDF ──
        r = await ac.get("/api/ai/ceo/kurul-paketi/pdf", headers=H("adm"))
        check(r.status_code == 200 and r.headers.get("content-type") == "application/pdf", f"Kurul Özeti PDF döndü ({r.status_code})")
        check(r.content[:4] == b"%PDF", "geçerli PDF içeriği")

    await server.client.drop_database(TEST_DB)


if __name__ == "__main__":
    asyncio.run(run())
    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    sys.exit(1 if _kalan else 0)
