"""Metin kalite geri bildirimi smoke — XP anti-farm + escalation eşiği + karar akışı + RBAC.

    cd appbackend
    PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe tests/test_metin_kalite_smoke.py
"""
import asyncio
import os
import sys

TEST_DB = "oba_test_metin_kalite"
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
    for u in [("t1", "teacher"), ("t2", "teacher"), ("s1", "student"), ("admin1", "admin")]:
        await db.users.insert_one({"id": u[0], "role": u[1], "ad": "X", "soyad": "Y", "puan": 0})
    # İki metin (okuma + ölçüm)
    await db.analiz_metinler.insert_one({"id": "m1", "baslik": "İyi metin", "bolum": "analiz", "durum": "havuzda"})
    await db.analiz_metinler.insert_one({"id": "m2", "baslik": "Kötü metin", "bolum": "olcum", "durum": "havuzda"})

    def H(u):
        return {"Authorization": f"Bearer {server.create_access_token({'sub': u})}"}

    async with AsyncClient(transport=ASGITransport(app=server.app), base_url="http://test") as ac:
        # ── Öğretmen ilk geri bildirim → XP (+3) ──
        r = (await ac.post("/api/metin-kalite/geri-bildirim", json={"metin_id": "m1", "yildiz": 5, "yorum": "harika"}, headers=H("t1"))).json()
        check(r["ok"] and r["ilk_mi"] and r["xp_kazanildi"] == 3, "ilk geri bildirim → +3 XP")
        u = await db.users.find_one({"id": "t1"})
        check(u["puan"] == 3, "users.puan +3 işlendi (leaderboard etkinlik kanalı)")

        # ── Aynı metne 2. kez → XP YOK (anti-farm), yıldız güncellenir ──
        r = (await ac.post("/api/metin-kalite/geri-bildirim", json={"metin_id": "m1", "yildiz": 4}, headers=H("t1"))).json()
        check(r["ilk_mi"] is False and r["xp_kazanildi"] == 0, "aynı metne 2. puan → XP yok (anti-farm)")
        u = await db.users.find_one({"id": "t1"})
        check(u["puan"] == 3, "puan artmadı (çiftlik önlendi)")
        check(r["kalite"]["sayi"] == 1 and r["kalite"]["ort"] == 4.0, "tek oy → ort 4.0 (güncellendi)")

        # ── Tek düşük oy henüz riskli DEĞİL (sayı < 2) ──
        await ac.post("/api/metin-kalite/geri-bildirim", json={"metin_id": "m2", "yildiz": 1}, headers=H("t1"))
        r = (await ac.get("/api/metin-kalite/riskli", headers=H("admin1"))).json()
        check(r["sayi"] == 0, "tek 1-yıldız → henüz riskli değil (eşik: oy≥2)")

        # ── İkinci düşük oy → riskli (ort<2.0 & oy≥2) → admin kuyruğu ──
        r = (await ac.post("/api/metin-kalite/geri-bildirim", json={"metin_id": "m2", "yildiz": 1, "yorum": "çok kötü"}, headers=H("t2"))).json()
        check(r["kalite"]["riskli"] is True and r["kalite"]["ort"] == 1.0, "2×1-yıldız → riskli (ort 1.0)")
        r = (await ac.get("/api/metin-kalite/riskli", headers=H("admin1"))).json()
        check(r["sayi"] == 1 and r["metinler"][0]["id"] == "m2", "riskli metin admin kuyruğunda")
        check(len(r["metinler"][0]["yorumlar"]) >= 1, "kuyrukta kanıt yorumları var")

        # ── İyi metin (m1) kuyruğa DÜŞMEZ ──
        check(all(m["id"] != "m1" for m in r["metinler"]), "iyi metin (m1) admin kuyruğunda değil")

        # ── Admin kararı: çıkarıldı → reddedildi + incelendi → kuyruktan çıkar ──
        r = (await ac.post("/api/metin-kalite/m2/karar", json={"karar": "cikarildi", "not": "içerik uygunsuz"}, headers=H("admin1"))).json()
        check(r["ok"] and r["durum"] == "reddedildi", "karar 'cikarildi' → durum reddedildi")
        m = await db.analiz_metinler.find_one({"id": "m2"})
        check(m["kalite"]["incelendi"] is True and m["durum"] == "reddedildi", "incelendi=true + havuzdan çıktı")
        r = (await ac.get("/api/metin-kalite/riskli", headers=H("admin1"))).json()
        check(r["sayi"] == 0, "karar verilmiş metin TEKRAR kuyruğa düşmez")

        # ── Keşif yolu tekrarlayan görev sayacı (t1: m1 + m2 = 2 farklı metin) ──
        r = (await ac.get("/api/ai/ceo/deneyim/benim", headers=H("t1"))).json()
        dnym = r.get("deneyim", r)  # yanıt {"deneyim": {...}} ile sarılı
        sg = next((g for g in dnym.get("surekli_gorevler", []) if g["id"] == "metin_kalite_denetcisi"), None)
        check(sg is not None and sg["sayac"] == 2, "keşif: 'metin kalitesi denetçisi' sayaç=2 (tekrarlayan görev)")

        # ── RBAC ──
        check((await ac.post("/api/metin-kalite/geri-bildirim", json={"metin_id": "m1", "yildiz": 3}, headers=H("s1"))).status_code == 403, "öğrenci puan veremez (403)")
        check((await ac.get("/api/metin-kalite/riskli", headers=H("t1"))).status_code == 403, "öğretmen riskli kuyruğu göremez (403)")
        check((await ac.post("/api/metin-kalite/m1/karar", json={"karar": "korundu"}, headers=H("t1"))).status_code == 403, "öğretmen karar veremez (403)")

    await server.client.drop_database(TEST_DB)


if __name__ == "__main__":
    asyncio.run(run())
    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    sys.exit(1 if _kalan else 0)
