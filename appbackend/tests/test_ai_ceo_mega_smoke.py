"""AI CEO MEGA paket (S1/S3/S4/S5/S7) smoke testi.

Kapsar: ünvan tek konfig (Sistem Danışmanı); karar kuyruğu (karar→düşme, ertele→geri gelme
+ PUAN VERMEZ, 7 gün vurgusu); yönetim skoru deterministik + gözden-kaçan-yok rozeti;
stratejik plan (taslak→onay→referans, vizyon etiketi, onaylı düzenlenemez); Miran muhasebe
kartı yalnız accountant + kapsam sızıntısı (tutar var / pedagojik yok).

    cd appbackend
    PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe tests/test_ai_ceo_mega_smoke.py
"""
import asyncio
import json
import os
import sys
from datetime import datetime, timezone, timedelta

TEST_DB = "oba_test_ai_ceo_mega"
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


def _iso_gun_once(g):
    return (datetime.now(timezone.utc) - timedelta(days=g)).isoformat()


async def run():
    import server
    from httpx import AsyncClient, ASGITransport
    from modules.ai_ceo import personalar
    import modules.ai_ceo.analiz as analiz_mod
    import modules.ai_ceo.miran as miran_mod

    db = server.db
    await server.client.drop_database(TEST_DB)
    await db.users.insert_one({"id": "adm", "role": "admin", "ad": "A", "soyad": "M"})
    await db.users.insert_one({"id": "acc", "role": "accountant", "ad": "Mu", "soyad": "Ha"})
    await db.users.insert_one({"id": "t1", "role": "teacher", "ad": "Ö", "soyad": "B"})

    def H(u):
        return {"Authorization": f"Bearer {server.create_access_token({'sub': u})}"}

    async with AsyncClient(transport=ASGITransport(app=server.app), base_url="http://test") as ac:
        # ── S1: ünvan tek konfig ──
        check(personalar.persona("miran")["unvan"] == "Sistem Danışmanı", "S1: Miran ünvanı 'Sistem Danışmanı' (tek konfig)")

        # ── S3: karar kuyruğu — öneri tohumla (direkt) ──
        oneriler = [
            {"id": "o_yuksek", "analiz_id": "a1", "baslik": "Kritik", "kategori": "tahsilat", "oncelik": "yuksek",
             "ozet": "x", "dayanaklar": [], "zayif_dayanak": False, "durum": "yeni", "tarih": _iso_gun_once(1)},
            {"id": "o_dusuk", "analiz_id": "a1", "baslik": "Düşük", "kategori": "buyume", "oncelik": "dusuk",
             "ozet": "y", "dayanaklar": [], "zayif_dayanak": False, "durum": "yeni", "tarih": _iso_gun_once(1)},
            {"id": "o_eski", "analiz_id": "a1", "baslik": "Eski", "kategori": "tahsilat", "oncelik": "orta",
             "ozet": "z", "dayanaklar": [], "zayif_dayanak": False, "durum": "yeni", "tarih": _iso_gun_once(9)},
        ]
        await db.ai_ceo_oneriler.insert_many(oneriler)
        r = await ac.get("/api/ai/ceo/kuyruk", headers=H("adm"))
        j = r.json()
        check(j["bekleyen_sayi"] == 3, f"kuyruk 3 açık öneri ({j['bekleyen_sayi']})")
        check(j["kuyruk"][0]["id"] == "o_yuksek", "kuyruk öncelik sıralı (yüksek ilk)")
        check(j["gozden_kacan_sayi"] == 1 and any(o["id"] == "o_eski" and o["gozden_kaciyor"] for o in j["kuyruk"]),
              "7 günden eski öneri 'gözden kaçıyor' işaretli")
        # kategori filtre
        r = await ac.get("/api/ai/ceo/kuyruk?kategori=tahsilat", headers=H("adm"))
        check(r.json()["bekleyen_sayi"] == 2, "kategori filtresi (tahsilat=2)")

        # Ertele → kuyruktan düşer (gelecek tarih), PUAN VERMEZ
        r = await ac.put("/api/ai/ceo/oneri/o_dusuk/durum", headers=H("adm"),
                         json={"durum": "ertelendi", "ertele_tarih": (datetime.now(timezone.utc) + timedelta(days=5)).isoformat()})
        check(r.status_code == 200, "ertele isteği ok")
        r = await ac.get("/api/ai/ceo/kuyruk", headers=H("adm"))
        check(all(o["id"] != "o_dusuk" for o in r.json()["kuyruk"]), "ertelenen öğe kuyruktan düştü")
        sk = (await ac.get("/api/ai/ceo/yonetim-skoru", headers=H("adm"))).json()["skor"]
        check(sk["puan"] == 0, f"ertele PUAN VERMEDİ ({sk['puan']})")

        # Süresi geçmiş ertele → geri gelir
        await db.ai_ceo_oneriler.update_one({"id": "o_dusuk"}, {"$set": {"ertele_tarih": _iso_gun_once(1)}})
        r = await ac.get("/api/ai/ceo/kuyruk", headers=H("adm"))
        check(any(o["id"] == "o_dusuk" for o in r.json()["kuyruk"]), "süresi geçen ertele kuyruğa geri geldi")

        # ── S4: karar → puan (öncelik ağırlıklı), durum takibi sürer ──
        r = await ac.put("/api/ai/ceo/oneri/o_yuksek/durum", headers=H("adm"), json={"durum": "uygulaniyor"})
        check(r.status_code == 200, "yüksek öncelikli öneri karara bağlandı")
        r = await ac.get("/api/ai/ceo/kuyruk", headers=H("adm"))
        check(all(o["id"] != "o_yuksek" for o in r.json()["kuyruk"]), "karar verilen öğe kuyruktan düştü")
        check(await db.ai_ceo_oneriler.find_one({"id": "o_yuksek"}) is not None, "öğe silinmedi (durum takibi sürüyor)")
        sk = (await ac.get("/api/ai/ceo/yonetim-skoru", headers=H("adm"))).json()["skor"]
        check(sk["puan"] == 10, f"yüksek karar = 10 puan ({sk['puan']})")
        check(sk["seviye"] == "Acemi Yönetici", "seviye Acemi Yönetici")
        check(sk["gozden_kacan_yok"] is False, "kuyruk doluyken 'gözden kaçan yok' SÖNÜK")
        # etkinlik puanı (brifing okuma)
        r = await ac.post("/api/ai/ceo/yonetim/etkinlik", headers=H("adm"), json={"tur": "brifing_okundu", "ref": "b1"})
        check(r.json()["kazanilan_puan"] == 5, "brifing okuma +5 puan")
        # idempotent
        r = await ac.post("/api/ai/ceo/yonetim/etkinlik", headers=H("adm"), json={"tur": "brifing_okundu", "ref": "b1"})
        check(r.json()["kazanilan_puan"] == 0, "aynı brifing tekrar puanlanmaz (idempotent)")

        # ── S5: stratejik plan ──
        r = await ac.post("/api/ai/ceo/plan", headers=H("adm"), json={"baslik": "Q3", "hedefler": [
            {"ad": "Yenileme", "metrik": "%", "mevcut": 55, "hedef": 65},
            {"ad": "NPS", "metrik": "puan", "mevcut": 40, "hedef": 55},
            {"ad": "Aktif öğrenci", "metrik": "adet", "mevcut": 100, "hedef": 130}]})
        check(r.status_code == 200, "3 hedefli plan oluşturuldu")
        pid = r.json()["plan"]["id"]
        check(r.json()["plan"]["durum"] == "taslak", "plan taslak")
        r = await ac.post("/api/ai/ceo/plan", headers=H("adm"), json={"hedefler": [{"ad": "x"}]})
        check(r.status_code == 400, "2'den az hedef reddedilir (3-5 kuralı)")
        r = await ac.post(f"/api/ai/ceo/plan/{pid}/onayla", headers=H("adm"))
        check(r.status_code == 200, "plan onaylandı")
        r = await ac.put(f"/api/ai/ceo/plan/{pid}", headers=H("adm"), json={"baslik": "yeni"})
        check(r.status_code == 404, "onaylı plan düzenlenemez (guard)")
        sk = (await ac.get("/api/ai/ceo/yonetim-skoru", headers=H("adm"))).json()["skor"]
        check(sk["puan"] == 30, f"plan onayı +15 (toplam 30) ({sk['puan']})")

        # vizyon önerisi etiketi (strateji + zayıf dayanak → vizyon, zayıf sayılmaz)
        analiz_mod.GEMINI_API_KEY = "k"

        async def sahte(system, user, max_tokens=4000):
            return {"error": None, "parsed": {"ozet": "s", "oneriler": [
                {"baslik": "Yeni il aç", "kategori": "strateji", "oncelik": "orta", "ozet": "büyüme",
                 "beklenen_etki": "?", "dayanak_metrikler": [{"metrik": "sektör trendi", "deger": 999999}]}]}}
        analiz_mod.call_claude = sahte
        await db.ai_ceo_fotograflar.insert_one({"id": "f1", "tarih": _iso_gun_once(0), "ogrenci": {"aktif": 3}})
        r = await ac.post("/api/ai/ceo/analiz/calistir", headers=H("adm"))
        viz = next((o for o in r.json()["oneriler"] if o["kategori"] == "strateji"), None)
        check(viz and viz.get("vizyon_onerisi") is True, "strateji önerisi 'vizyon önerisi' etiketli")
        check(viz and viz.get("zayif_dayanak") is False, "vizyon önerisi 'zayıf dayanak' sayılmadı")

        # ── S7: Miran muhasebe — accountant, tutar VAR / pedagojik YOK ──
        await db.kur_ucretleri.insert_one({"id": "km", "ogrenci_id": "sx", "tutar": 1000, "yapilan_odeme": 200,
                                           "durum": "acik", "baslangic_tarihi": _iso_gun_once(75)})  # 60+ yaşlanan
        await db.kur_ucretleri.insert_one({"id": "kh", "ogrenci_id": "sy", "tutar": 1000, "yapilan_odeme": 1000,
                                           "ogretmen_id": "t1", "ogretmen_pay": 500,
                                           "odeme_tamamlanma_tarihi": _iso_gun_once(2)})  # damgalı, hakediş yaklaşan

        async def sahte_ped(system, user, max_tokens=1200):  # pedagojik sızıntılı AI → guard deterministik'e düşürür
            return {"error": None, "parsed": {"selam": "s", "kapanis": "k",
                    "oneriler": [{"baslik": "risk", "aciklama": "Öğrencinin risk skoru yüksek, 5000₺ alacak var."}]}}
        miran_mod.GEMINI_API_KEY = "k"
        miran_mod.call_claude = sahte_ped
        r = await ac.get("/api/ai/ceo/miran/muhasebe", headers=H("acc"))
        check(r.status_code == 200, "muhasebe Miran kartı (accountant) 200")
        blob = json.dumps(r.json()["miran"]["icerik"], ensure_ascii=False).lower()
        check("risk skoru" not in blob, "ters guard: pedagojik veri (risk skoru) SIZMADI")
        check(r.json()["miran"]["kaynak"] == "deterministik", "pedagojik ihlalde deterministik'e düşüldü")
        check("₺" in blob or "alacak" in blob or "hakediş" in blob or "hakedis" in blob, "muhasebe Miran'ı tutar/finans KONUŞUYOR")
        # öğretmen muhasebe kartına erişemez
        r = await ac.get("/api/ai/ceo/miran/muhasebe", headers=H("t1"))
        check(r.status_code == 403, "öğretmen muhasebe Miran'ına erişemez → 403")

    await server.client.drop_database(TEST_DB)


if __name__ == "__main__":
    asyncio.run(run())
    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    sys.exit(1 if _kalan else 0)
