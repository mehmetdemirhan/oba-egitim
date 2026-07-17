"""AI CEO — Denetçi "Deniz" (S8 temel + S10 karne) smoke testi.

Kapsar: deterministik kontroller (her kural ≥1 vaka); AI denetim turu (mock) ek bulgu;
bulgu durum (geçerli/geçersiz/çözüldü) + yönetim skoru; iyileştirme notu ONAYSIZ analize
girmez (guard, oto self-modifikasyon yok); Deniz karnesi; persona sızıntısı (Deniz yalnız
admin; teacher/coordinator 403).

    cd appbackend
    PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe tests/test_ai_ceo_deniz_smoke.py
"""
import asyncio
import os
import sys
from datetime import datetime, timezone, timedelta

TEST_DB = "oba_test_ai_ceo_deniz"
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
    from modules.ai_ceo import personalar
    import modules.ai_ceo.deniz as deniz_mod

    db = server.db
    await server.client.drop_database(TEST_DB)
    await db.users.insert_one({"id": "adm", "role": "admin", "ad": "A", "soyad": "M"})
    await db.users.insert_one({"id": "koor", "role": "coordinator", "ad": "K", "soyad": "O"})
    await db.users.insert_one({"id": "t1", "role": "teacher", "ad": "T", "soyad": "1"})

    # Deterministik kontrolleri tetikleyecek veri: 6 öneri, 4 zayıf, hepsi 'tahsilat', 3'ü aynı
    # başlık, hepsi 8 gün eski 'yeni' → dayanak_zayifligi + tekrar + kategori_dengesizligi + takili
    oneriler = []
    for i in range(6):
        oneriler.append({"id": f"o{i}", "analiz_id": "a", "baslik": "Tekrar" if i < 3 else f"B{i}",
                         "kategori": "tahsilat", "oncelik": "orta", "ozet": "x",
                         "zayif_dayanak": i < 4, "dayanaklar": [], "durum": "yeni", "tarih": _eski(8)})
    await db.ai_ceo_oneriler.insert_many(oneriler)
    # Miran geri bildirim düşüşü: 5 geri bildirim, 1 faydalı
    for i in range(5):
        await db.ai_ceo_miran_geribildirim.insert_one({"miran_id": f"m{i}", "ogretmen_id": "t1", "faydali": i == 0})

    def H(u):
        return {"Authorization": f"Bearer {server.create_access_token({'sub': u})}"}

    async with AsyncClient(transport=ASGITransport(app=server.app), base_url="http://test") as ac:
        # ── persona sızıntısı ──
        check(personalar.gorunur_mu("deniz", "admin") is True, "Deniz admin'e görünür")
        check(personalar.gorunur_mu("deniz", "teacher") is False and personalar.gorunur_mu("deniz", "coordinator") is False, "Deniz öğretmen/koordinatöre görünmez")
        r = await ac.get("/api/ai/ceo/deniz/son", headers=H("t1"))
        check(r.status_code == 403, "öğretmen Deniz'e erişemez → 403")
        r = await ac.post("/api/ai/ceo/deniz/denetle", headers=H("koor"))
        check(r.status_code == 403, "koordinatör Deniz denetimi çalıştıramaz → 403 (yalnız admin)")

        # ── S8: denetle (AI turu mock) ──
        deniz_mod.GEMINI_API_KEY = "k"

        async def sahte(system, user, max_tokens=2000, **kw):
            return {"error": None, "parsed": {"ozet": "Genel tutarlılık orta.",
                    "ek_bulgular": [{"tur": "mantik_zayifligi", "onem": "orta", "ozet": "Bir öneri kanıtsız.", "kanit": "x"}],
                    "iyilestirme_plani": "Zayıf dayanaklı önerileri azalt; kategori çeşitliliğini artır."}}
        deniz_mod.call_claude = sahte
        r = await ac.post("/api/ai/ceo/deniz/denetle", headers=H("adm"))
        check(r.status_code == 200 and r.json().get("ok"), "Deniz denetimi çalıştı")
        bulgular = r.json()["bulgular"]
        turler = {b["tur"] for b in bulgular}
        for beklenen in ("dayanak_zayifligi", "tekrarlanan_oneri", "kategori_dengesizligi", "beklemede_takili", "miran_geri_bildirim_dususu"):
            check(beklenen in turler, f"deterministik kural yakaladı: {beklenen}")
        check("mantik_zayifligi" in turler, "AI denetim turu ek bulgu ekledi")
        check(any(b["onem"] == "kritik" for b in bulgular), "kritik bulgu var (dayanak zayıflığı)")
        check(await db.bildirimler.find_one({"tur": "ai_ceo_anomali"}) is not None, "kritik bulgu admin bildirimi düştü")

        # ── bulgu durum → yönetim skoru ──
        krit = next(b for b in bulgular if b["onem"] == "kritik")
        r = await ac.put(f"/api/ai/ceo/deniz/bulgu/{krit['id']}/durum", headers=H("adm"), json={"durum": "admin_gecerli"})
        check(r.status_code == 200, "bulgu 'geçerli' işaretlendi")
        sk = (await ac.get("/api/ai/ceo/yonetim-skoru", headers=H("adm"))).json()["skor"]
        check(sk["kirilim"].get("bulgu_degerlendirildi", 0) == 4, f"bulgu değerlendirme yönetim skoruna işlendi (+4) ({sk['kirilim'].get('bulgu_degerlendirildi')})")
        await ac.put(f"/api/ai/ceo/deniz/bulgu/{krit['id']}/durum", headers=H("adm"), json={"durum": "cozuldu"})

        # ── S10: Deniz karnesi ──
        r = await ac.get("/api/ai/ceo/deniz/karne", headers=H("adm"))
        k = r.json()["karne"]
        check(k["bulgu_dogrulugu"] == 100.0, f"bulgu doğruluğu %100 (1 değerlendirilen, geçerli) ({k['bulgu_dogrulugu']})")
        check(k["yakalama_degeri"] == 100.0, f"kritik yakalama %100 (1 kritik çözüldü) ({k['yakalama_degeri']})")

        # ── S8c: iyileştirme notu ONAY GUARD ──
        r = await ac.post("/api/ai/ceo/deniz/not", headers=H("adm"), json={"metin": "Zayıf dayanakları azalt."})
        nid = r.json()["not"]["id"]
        check(r.json()["not"]["onayli"] is False, "denetim notu ONAYSIZ (taslak)")
        # onaysız not sonraki analize GİRMEZ (guard): analiz onayli not arar
        an_not = await db.ai_ceo_denetim_notlari.find_one({"onayli": True})
        check(an_not is None, "onaysız not analize referans olmaz (oto self-modifikasyon yok)")
        r = await ac.post(f"/api/ai/ceo/deniz/not/{nid}/onayla", headers=H("adm"))
        check(r.status_code == 200, "not onaylandı")
        check(await db.ai_ceo_denetim_notlari.find_one({"id": nid}) and (await db.ai_ceo_denetim_notlari.find_one({"id": nid}))["onayli"] is True, "onaydan sonra not analize girmeye uygun")
        # teacher not ekleyemez
        r = await ac.post("/api/ai/ceo/deniz/not", headers=H("t1"), json={"metin": "hack"})
        check(r.status_code == 403, "öğretmen denetim notu ekleyemez → 403")

    await server.client.drop_database(TEST_DB)


if __name__ == "__main__":
    asyncio.run(run())
    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    sys.exit(1 if _kalan else 0)
