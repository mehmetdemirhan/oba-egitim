"""TIMI Rapor güçlendirme + taslak yönetimi + görünürlük smoke.

Kapsam: (A) puan dağılımından doğru metin bloklarının deterministik seçilmesi,
(B) tam anlatılı rapor + PDF üretimi, (C) metin bankası düzenleme (yetki), (D) taslak/rapor
silme yetkileri, (E) 15 gün otomatik silme + 2 gün önce ön bildirim, (F) görünürlük uçları.

    cd appbackend
    PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe tests/test_timi_rapor_smoke.py
"""
import asyncio
import os
import sys
from datetime import datetime, timezone, timedelta

TEST_DB = "oba_test_timi_rapor"
os.environ["MONGO_URL"] = os.environ.get("MONGO_URL_TEST", "mongodb://localhost:27017")
os.environ["DB_NAME"] = TEST_DB
os.environ.setdefault("SECRET_KEY", "test-secret-key")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_gecen = _kalan = 0
REF = {"dilsel": 0, "mantiksal_matematiksel": 5, "mekansal": 6, "muziksel": 4, "bedensel": 3, "kisisel": 6, "kisilerarasi": 4}


def check(k, m):
    global _gecen, _kalan
    if k:
        _gecen += 1; print(f"  [GECTI] {m}")
    else:
        _kalan += 1; print(f"  [KALDI] {m}")


async def run():
    import server
    from httpx import AsyncClient, ASGITransport
    import modules.timi as timi_mod
    from modules.timi_metin import seviyele, timi_rapor_uret

    db = server.db
    await server.client.drop_database(TEST_DB)
    await db.users.insert_one({"id": "adm", "role": "admin", "ad": "Ad", "soyad": "Min"})
    await db.users.insert_one({"id": "coord", "role": "coordinator", "ad": "Ko", "soyad": "Or"})
    await db.users.insert_one({"id": "t1", "role": "teacher", "ad": "Öğ", "soyad": "One"})
    await db.users.insert_one({"id": "t2", "role": "teacher", "ad": "Öğ", "soyad": "Two"})
    await db.students.insert_one({"id": "s1", "ad": "Karan", "soyad": "Özdemir", "sinif": "11", "ogretmen_id": "t1"})

    def H(u):
        return {"Authorization": f"Bearer {server.create_access_token({'sub': u})}"}

    now = datetime.now(timezone.utc)

    async with AsyncClient(transport=ASGITransport(app=server.app), base_url="http://test") as ac:
        # ── A) Deterministik metin seçimi ──
        s = seviyele(REF)
        check(s["baskin"] == ["mekansal", "kisisel"] and s["dusuk"] == ["dilsel", "bedensel"]
              and s["orta"] == ["mantiksal_matematiksel", "muziksel", "kisilerarasi"],
              f"referans puanları doğru seviyelendi ({s['baskin']}/{s['orta']}/{s['dusuk']})")
        r_ref = timi_rapor_uret(REF)
        basliklar = [b["baslik"] for b in r_ref["bolumler"]]
        bekle = ["Genel Değerlendirme", "Güçlü Yönler", "Orta Düzeyde Gelişmiş Alanlar",
                 "Geliştirilmesi Desteklenebilecek Alanlar", "Eğitimsel Öneriler", "Sonuç"]
        check(basliklar == bekle, f"6 bölüm tam ve sıralı ({len(basliklar)})")
        # tek baskın (dilsel) → güçlü yönlerde dilsel bloğu
        r_dil = timi_rapor_uret({"dilsel": 8, "mantiksal_matematiksel": 2, "mekansal": 1, "muziksel": 1, "bedensel": 0, "kisisel": 1, "kisilerarasi": 2})
        guclu = next(b for b in r_dil["bolumler"] if b["baslik"] == "Güçlü Yönler")["maddeler"]
        check(any("ifade" in m or "Okuma" in m for m in guclu), "dilsel baskın → dilsel güçlü blokları seçildi")
        # dengeli profil → dengeli genel değerlendirme
        r_dng = timi_rapor_uret({k: 4 for k in REF})
        check("dengeli" in r_dng["bolumler"][0]["paragraf"], "tüm alanlar eşit → 'dengeli' genel değerlendirme")

        # ── B) API rapor + PDF ──
        await db.timi_sonuclar.insert_one({"id": "rap_ref", "ogrenci_id": "s1", "ogretmen_id": "t1",
            "durum": "tamamlandi", "kategori_puanlari": REF, "baskin_zeka_alanlari": ["mekansal", "kisisel"],
            "created_at": now.isoformat(), "uygulama_tarihi": now.isoformat(), "notlar": "Sakin, işbirlikçi."})
        r = await ac.get("/api/timi/rap_ref/rapor", headers=H("t1"))
        check(r.status_code == 200 and len(r.json()["rapor"]["bolumler"]) == 6, f"GET /rapor → 6 bölüm ({r.status_code})")
        r = await ac.get("/api/timi/rap_ref/pdf", headers=H("t1"))
        check(r.status_code == 200 and r.content[:4] == b"%PDF", f"PDF üretildi (%PDF) ({r.status_code}, {r.content[:4]})")

        # ── C) Metin bankası düzenleme (yetki + etki) ──
        check((await ac.get("/api/timi/rapor-metinleri", headers=H("adm"))).status_code == 200, "admin metin bankasını okur")
        check((await ac.get("/api/timi/rapor-metinleri", headers=H("coord"))).status_code == 200, "koordinatör metin bankasını okur")
        check((await ac.get("/api/timi/rapor-metinleri", headers=H("t1"))).status_code == 403, "öğretmen metin bankasını okuyamaz (403)")
        r = await ac.put("/api/timi/rapor-metinleri", headers=H("adm"), json={"metinler": {"dilsel": {"guclu": ["ÖZEL GÜÇLÜ MADDE"]}}})
        check(r.status_code == 200, "admin metin bankasını kaydetti")
        check((await ac.put("/api/timi/rapor-metinleri", headers=H("t1"), json={"metinler": {}})).status_code == 403, "öğretmen metin bankasını düzenleyemez (403)")
        await db.timi_sonuclar.insert_one({"id": "rap_dil", "ogrenci_id": "s1", "ogretmen_id": "t1", "durum": "tamamlandi",
            "kategori_puanlari": {"dilsel": 8, "mantiksal_matematiksel": 2, "mekansal": 1, "muziksel": 1, "bedensel": 0, "kisisel": 1, "kisilerarasi": 2},
            "created_at": now.isoformat()})
        r = await ac.get("/api/timi/rap_dil/rapor", headers=H("adm"))
        guclu2 = next(b for b in r.json()["rapor"]["bolumler"] if b["baslik"] == "Güçlü Yönler")["maddeler"]
        check(guclu2 == ["ÖZEL GÜÇLÜ MADDE"], f"düzenlenen metin rapora yansıdı ({guclu2})")

        # ── D) Taslak / rapor silme yetkileri ──
        r = await ac.post("/api/timi/baslat", json={"ogrenci_id": "s1"}, headers=H("t1"))
        tid = r.json()["id"]
        check((await ac.delete(f"/api/timi/{tid}", headers=H("t2"))).status_code == 403, "başka öğretmen taslağı silemez (403)")
        r = await ac.delete(f"/api/timi/{tid}", headers=H("t1"))
        check(r.status_code == 200 and r.json().get("taslak") is True, "uygulayan öğretmen kendi taslağını sildi")
        check((await ac.delete("/api/timi/rap_ref", headers=H("t1"))).status_code == 403, "öğretmen tamamlanmış raporu silemez (403)")
        check((await ac.delete("/api/timi/rap_ref", headers=H("adm"))).status_code == 400, "admin onaysız tamamlanmış rapor silemez (400)")
        r = await ac.delete("/api/timi/rap_ref?onay=true", headers=H("adm"))
        check(r.status_code == 200, "admin onayla tamamlanmış raporu sildi")
        check(await db.islem_log.find_one({"modul": "timi", "islem": "rapor_sil"}) is not None, "silme islem_log'a düştü")

        # ── E) 15 gün otomatik silme + 2 gün önce ön bildirim ──
        await db.timi_sonuclar.insert_one({"id": "d_eski", "ogrenci_id": "s1", "ogretmen_id": "t1", "durum": "devam", "created_at": (now - timedelta(days=20)).isoformat()})
        await db.timi_sonuclar.insert_one({"id": "d_orta", "ogrenci_id": "s1", "ogretmen_id": "t1", "durum": "devam", "created_at": (now - timedelta(days=14)).isoformat()})
        await db.timi_sonuclar.insert_one({"id": "d_yeni", "ogrenci_id": "s1", "ogretmen_id": "t1", "durum": "devam", "created_at": now.isoformat()})
        res = await timi_mod._taslak_temizlik()
        check(res["silinen"] == 1 and await db.timi_sonuclar.find_one({"id": "d_eski"}) is None, f"15 gün+ taslak silindi ({res['silinen']})")
        check(await db.timi_sonuclar.find_one({"id": "d_orta"}) is not None and res["uyarilan"] == 1, f"13-15 gün taslak uyarıldı, silinmedi ({res['uyarilan']})")
        check(await db.bildirimler.find_one({"alici_id": "t1", "tur": "timi_taslak_uyari"}) is not None, "öğretmene silme ön uyarısı bildirimi gitti")
        check(await db.timi_sonuclar.find_one({"id": "d_yeni"}) is not None, "yeni taslak korundu")
        check(await db.islem_log.find_one({"modul": "timi", "islem": "taslak_oto_sil"}) is not None, "otomatik silme islem_log'a düştü")
        # cron uç (token korumalı — doğru anahtarla 200, yanlışla 403)
        from core.config import PUSH_CRON_TOKEN
        check((await ac.post(f"/api/timi/gunluk-temizlik?anahtar={PUSH_CRON_TOKEN}")).status_code == 200, "cron temizlik ucu doğru anahtarla çalışıyor")
        if PUSH_CRON_TOKEN:
            check((await ac.post("/api/timi/gunluk-temizlik?anahtar=yanlis")).status_code == 403, "cron temizlik ucu yanlış anahtarı reddediyor (403)")

        # ── F) Görünürlük uçları ──
        r = await ac.get("/api/timi/ogrenci/s1", headers=H("t1"))
        check(r.status_code == 200 and any(x["id"] == "rap_dil" for x in r.json()), "öğrenci TIMI geçmişi listeleniyor")
        r = await ac.get("/api/timi/sessions", headers=H("t1"))
        idler = {x["id"] for x in r.json()}
        check("rap_dil" in idler and "d_orta" in idler, "sessions: öğretmen kendi tamamlanmış + taslaklarını görür")

    await server.client.drop_database(TEST_DB)


if __name__ == "__main__":
    asyncio.run(run())
    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    sys.exit(1 if _kalan else 0)
