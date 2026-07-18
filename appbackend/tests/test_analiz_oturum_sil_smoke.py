"""Okuma analizi oturumu — yarım kalan silme + 15 gün otomatik temizlik (ortak temizleyici).

Kapsam: (1) yarım analizi başlatan öğretmen + admin silebilir, başkası 403; (2) tamamlanmış
analiz bu yolla silinemez (400); (3) silme islem_log'a düşer; (4) 15 gün+ tamamlanmamış oturum
otomatik silinir, 13-15 gün olana başlatan öğretmene bildirim (silinmeden); (5) cron ucu.

    cd appbackend
    PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe tests/test_analiz_oturum_sil_smoke.py
"""
import asyncio
import os
import sys
from datetime import datetime, timezone, timedelta

TEST_DB = "oba_test_analiz_oturum_sil"
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
    import modules.diagnostic as diag

    db = server.db
    await server.client.drop_database(TEST_DB)
    await db.users.insert_one({"id": "adm", "role": "admin", "ad": "Ad", "soyad": "Min"})
    await db.users.insert_one({"id": "t1", "role": "teacher", "ad": "Öğ", "soyad": "Bir"})
    await db.users.insert_one({"id": "t2", "role": "teacher", "ad": "Öğ", "soyad": "İki"})
    now = datetime.now(timezone.utc)

    async def oturum(oid, ogr, durum="devam", gun=0):
        await db.diagnostic_oturumlar.insert_one({
            "id": oid, "ogrenci_id": "s1", "ogretmen_id": ogr, "durum": durum,
            "olusturma_tarihi": (now - timedelta(days=gun)).isoformat()})

    def H(u):
        return {"Authorization": f"Bearer {server.create_access_token({'sub': u})}"}

    async with AsyncClient(transport=ASGITransport(app=server.app), base_url="http://test") as ac:
        # ── 1) yetki: başkası silemez, başlatan öğretmen siler ──
        await oturum("o1", "t1")
        check((await ac.delete("/api/diagnostic/sessions/o1", headers=H("t2"))).status_code == 403, "başka öğretmen yarım analizi silemez → 403")
        r = await ac.delete("/api/diagnostic/sessions/o1", headers=H("t1"))
        check(r.status_code == 200 and r.json().get("taslak") is True, "başlatan öğretmen kendi yarım analizini sildi")
        check(await db.diagnostic_oturumlar.find_one({"id": "o1"}) is None, "oturum gerçekten silindi")
        # admin başka öğretmenin yarımını silebilir
        await oturum("o2", "t2")
        check((await ac.delete("/api/diagnostic/sessions/o2", headers=H("adm"))).status_code == 200, "admin herhangi yarım analizi silebilir")

        # ── 2) tamamlanmış analiz bu yolla silinemez ──
        await oturum("odone", "t1", durum="tamamlandi")
        check((await ac.delete("/api/diagnostic/sessions/odone", headers=H("adm"))).status_code == 400, "tamamlanmış analiz bu yolla silinemez → 400")
        check(await db.diagnostic_oturumlar.find_one({"id": "odone"}) is not None, "tamamlanmış analiz duruyor")

        # ── 3) silme islem_log'a düştü ──
        check(await db.islem_log.find_one({"modul": "diagnostic", "islem": "analiz_taslak_sil"}) is not None, "yarım silme islem_log'a düştü")

        # ── 4) otomatik temizlik: 15 gün+ silinir, 13-15 gün uyarılır ──
        await oturum("o_eski", "t1", gun=20)
        await oturum("o_orta", "t1", gun=14)
        await oturum("o_yeni", "t1", gun=0)
        res = await diag._analiz_temizlik()
        check(res["silinen"] == 1 and await db.diagnostic_oturumlar.find_one({"id": "o_eski"}) is None, f"15 gün+ yarım analiz otomatik silindi ({res['silinen']})")
        check(res["uyarilan"] == 1 and await db.diagnostic_oturumlar.find_one({"id": "o_orta"}) is not None, f"13-15 gün analiz uyarıldı, silinmedi ({res['uyarilan']})")
        check(await db.bildirimler.find_one({"alici_id": "t1", "tur": "analiz_taslak_uyari"}) is not None, "başlatan öğretmene silme ön uyarısı gitti")
        check(await db.diagnostic_oturumlar.find_one({"id": "o_yeni"}) is not None, "yeni yarım analiz korundu")
        check(await db.islem_log.find_one({"modul": "diagnostic", "islem": "analiz_oto_sil"}) is not None, "otomatik silme islem_log'a düştü")
        # tamamlanmış olanlara dokunmaz
        await oturum("odone2", "t1", durum="tamamlandi", gun=30)
        await diag._analiz_temizlik()
        check(await db.diagnostic_oturumlar.find_one({"id": "odone2"}) is not None, "eski TAMAMLANMIŞ analiz temizlikte silinmez")

        # ── 5) cron ucu ──
        from core.config import PUSH_CRON_TOKEN
        check((await ac.post(f"/api/diagnostic/gunluk-temizlik?anahtar={PUSH_CRON_TOKEN}")).status_code == 200, "cron temizlik ucu doğru anahtarla çalışıyor")
        if PUSH_CRON_TOKEN:
            check((await ac.post("/api/diagnostic/gunluk-temizlik?anahtar=yanlis")).status_code == 403, "cron ucu yanlış anahtarı reddediyor")

    await server.client.drop_database(TEST_DB)


if __name__ == "__main__":
    asyncio.run(run())
    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    sys.exit(1 if _kalan else 0)
