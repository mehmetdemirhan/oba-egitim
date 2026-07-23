"""Kalite Kontrol genişletme smoke: öğretmen özet + admin analitik + rozet + changelog ajanı.

- /egzersiz-kalite/ozet: toplam/xp/seri/bar + rozet ilerlemesi
- /egzersiz-kalite/analitik: kapsam/katılım/askıda/liderlik/trend
- Kalite badge'leri kanonik rozet motorundan kazanılır (ekk_ilk/ekk_10)
- Changelog ajanı: teknik commit filtreleme + taslak + admin onay → duyurular

cd appbackend && .venv/Scripts/python.exe tests/test_kalite_genisletme_smoke.py
"""
import asyncio
import os
import sys
import uuid

TEST_DB = "oba_test_kalite_genis"
os.environ["MONGO_URL"] = os.environ.get("MONGO_URL_TEST", "mongodb://localhost:27017")
os.environ["DB_NAME"] = TEST_DB
os.environ.setdefault("SECRET_KEY", "test-secret-key")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_g = 0
_k = 0


def check(k, m):
    global _g, _k
    if k:
        _g += 1; print(f"  [GECTI] {m}")
    else:
        _k += 1; print(f"  [KALDI] {m}")


async def run():
    import server
    from core.auth import create_access_token
    from core.db import db
    from core.zaman import iso
    from core.rozet_motor import rozet_degerlendir
    import modules.duyuru_ajan as aj
    from httpx import AsyncClient, ASGITransport

    await server.client.drop_database(TEST_DB)
    adm = str(uuid.uuid4()); t1 = str(uuid.uuid4())
    await db.users.insert_one({"id": adm, "role": "admin", "ad": "Yön", "soyad": "E"})
    await db.users.insert_one({"id": t1, "role": "teacher", "ad": "Öğr", "soyad": "Bir", "puan": 0})
    for i in range(3):
        await db.egzersiz_icerikler.insert_one({"id": str(uuid.uuid4()), "tip": "anagram", "sinif": 3,
                                                "durum": "aktif", "kalite_toplam_degerlendirme": 1 if i == 0 else 0})
    for i in range(11):
        await db.egzersiz_kalite_degerlendirme.insert_one({"id": str(uuid.uuid4()), "egzersiz_id": str(uuid.uuid4()),
            "ogretmen_id": t1, "ogretmen_ad": "Öğr Bir", "tarih": iso(), "uygun": True,
            "degisiklik_talebi": "düzelt" if i < 5 else None})

    H1 = {"Authorization": f"Bearer {create_access_token({'sub': t1})}"}
    Ha = {"Authorization": f"Bearer {create_access_token({'sub': adm})}"}

    async with AsyncClient(transport=ASGITransport(app=server.app), base_url="http://test") as ac:
        # A/E/F: öğretmen özeti
        r = await ac.get("/api/egzersiz-kalite/ozet", headers=H1); o = r.json()
        check(o["toplam_degerlendirme"] == 11, f"özet toplam=11 ({o['toplam_degerlendirme']})")
        check(o["kazanilan_xp"] == 21, f"özet XP=21 (11*1+5*2) ({o['kazanilan_xp']})")
        check(o["degisiklik_talebi_sayisi"] == 5, "değişiklik talebi=5")
        check(0 < o["bar_dolum"] <= 1, f"kalite barı dolumu ({o['bar_dolum']})")
        check(any(rz["id"] == "ekk_10" and rz["ilerleme"] >= 10 for rz in o["rozetler"]), "ekk_10 rozet ilerlemesi 10/10 (özet)")

        # Rozet kanonik motordan işlenir (degerlendir endpoint'i tetikler; testte elle çağırıyoruz)
        await rozet_degerlendir(t1, "kalite_kontrol")
        kaz = await db.kazanilan_rozetler.distinct("rozet_kodu", {"kullanici_id": t1})
        check("ekk_ilk" in kaz and "ekk_10" in kaz and "ekk_degisiklik" in kaz, f"kanonik rozetler kazanıldı ({[k for k in kaz if k.startswith('ekk')]})")
        # Kazanım sonrası özet 'kazanildi' bayrağını yansıtır
        r = await ac.get("/api/egzersiz-kalite/ozet", headers=H1)
        check(any(rz["id"] == "ekk_10" and rz["kazanildi"] for rz in r.json()["rozetler"]), "ekk_10 rozeti kazanıldı (özet güncellendi)")

        # B: admin analitik
        r = await ac.get("/api/egzersiz-kalite/analitik", headers=Ha); a = r.json()
        check(a["toplam_egzersiz"] == 3 and a["degerlendirilmis"] == 1 and a["hic_degerlendirilmemis"] == 2, "analitik kapsam 1/3")
        check(a["katilan_ogretmen"] == 1, "katılan öğretmen=1")
        check(len(a["trend"]) == 14 and a["trend"][-1]["sayi"] == 11, "14 günlük trend + bugün=11")
        check(len(a["liderlik"]) == 1 and a["liderlik"][0]["sayi"] == 11, "liderlik tablosu")

        # Öğretmen analitiğe erişemez
        r = await ac.get("/api/egzersiz-kalite/analitik", headers=H1)
        check(r.status_code == 403, f"öğretmen analitiğe 403 ({r.status_code})")

        # C: changelog ajanı — teknik filtre + taslak + onay
        check(aj._teknik_mi("Merge: refactor registry") and not aj._teknik_mi("Öğretmen kalite değerlendirmesi"), "teknik commit filtresi")

        async def sahte(limit=40):   # yeni imza: (liste, hata) döner
            return ([{"sha": "s1", "mesaj": "Veli anketine TC alanı eklendi", "tarih": "2026-07-23"},
                     {"sha": "s2", "mesaj": "Merge: refactor registry", "tarih": "2026-07-22"}], None)

        async def sahte_ai(sistem, msg, **kw):
            return {"parsed": {"girisler": [{"baslik": "Veli TC bilgisi", "icerik": "Veli kaydına T.C. kimlik alanı eklendi."}]}, "text": "", "error": None}
        aj._commitleri_cek = sahte; aj.call_claude = sahte_ai

        r = await ac.post("/api/duyuru-taslak/tara", headers=Ha); s = r.json()
        check(s["aday"] == 1 and s["olusan_taslak"] == 1, f"1 teknik-dışı commit → 1 taslak (aday={s['aday']})")
        r = await ac.get("/api/duyuru-taslak", headers=Ha); tas = r.json()["taslaklar"]
        check(len(tas) >= 1 and any(t["baslik"] == "Veli TC bilgisi" for t in tas), "taslak onay kuyruğunda")
        tid = [t for t in tas if t["baslik"] == "Veli TC bilgisi"][0]["id"]
        r = await ac.post(f"/api/duyuru-taslak/{tid}/onayla", headers=Ha, json={})
        check(r.status_code == 200 and r.json().get("yayinlandi"), "taslak onaylandı → yayınlandı")
        d = await db.duyurular.find_one({"baslik": "Veli TC bilgisi"})
        check(d and d.get("aktif") is True, "duyurular'da (Yeni Ne Var) yayında + aktif")
        # Öğretmen taslak kuyruğuna erişemez
        r = await ac.get("/api/duyuru-taslak", headers=H1)
        check(r.status_code == 403, f"öğretmen taslak kuyruğuna 403 ({r.status_code})")

    await server.client.drop_database(TEST_DB)


def main():
    asyncio.run(run())
    print(f"\nSONUC: {_g}/{_g + _k} kontrol gecti")
    sys.exit(0 if _k == 0 else 1)


if __name__ == "__main__":
    main()
