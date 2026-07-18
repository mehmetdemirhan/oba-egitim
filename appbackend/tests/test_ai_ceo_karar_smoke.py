"""AI CEO — Kurumsal Karar Zekâsı (Faz 2) smoke.

Kapsam: metrik katalog seed + yetki; teklif üretimi (AI mock → yapılandırılmış) + deterministik
fallback (GERÇEK metrikten, UYDURMA YOK); yaşam döngüsü (karar→uygula→öğrenme); kurumsal hafıza;
yetki ayrımı (öğretmen 403, koordinatör okur/üretir, karar/hafıza yalnız admin).

    cd appbackend
    PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe tests/test_ai_ceo_karar_smoke.py
"""
import asyncio
import os
import sys

TEST_DB = "oba_test_ai_ceo_karar"
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


AI_TEKLIF = {
    "title": "Yenileme iyileştirme pilotu",
    "problem": {"statement": "Yenileme düşük.", "severity_score": 70, "affected_population": 100, "estimated_annual_loss": 500000.0},
    "evidence": [{"metric": "ogretmen.yenileme_orani", "segment": "genel", "current": 40.0, "previous": 50.0, "confidence": 0.8, "sample_size": 100, "data_quality_score": 90.0}],
    "hypotheses": [{"statement": "İlk ay devamsızlık etkiliyor.", "support": "high", "evidence_ids": ["ogretmen.yenileme_orani"], "test": "50 kişilik pilot"}],
    "alternatives": [{"name": "İlk 30 gün programı", "cost": 100000.0, "effort": "medium", "expected_effect": "high", "risk": "medium"}],
    "recommendation": {"selected_alternative": "İlk 30 gün programı", "rationale": "GDR yüksek.", "confidence": 0.8},
    "implementation": {"owner_role": "coordinator", "pilot_size": 50, "duration_days": 45, "steps": ["ara"], "estimated_cost": 100000.0},
    "measurement": {"primary_metric": "ogretmen.yenileme_orani", "baseline": 40.0, "target": 55.0, "guardrail_metrics": [], "checkpoints": [14, 30], "stop_conditions": []},
}


async def run():
    import server
    from httpx import AsyncClient, ASGITransport
    import core.ai as ai_mod
    import modules.ai_ceo.karar_zekasi as kz

    db = server.db
    await server.client.drop_database(TEST_DB)
    await db.users.insert_one({"id": "adm", "role": "admin", "ad": "Ad", "soyad": "Min"})
    await db.users.insert_one({"id": "koord", "role": "coordinator", "ad": "Ko", "soyad": "Or"})
    await db.users.insert_one({"id": "t1", "role": "teacher", "ad": "Öğ", "soyad": "Bir"})

    def H(u):
        return {"Authorization": f"Bearer {server.create_access_token({'sub': u})}"}

    async with AsyncClient(transport=ASGITransport(app=server.app), base_url="http://test") as ac:
        # ── Metrik katalog: seed + yetki ──
        r = await ac.get("/api/ai/ceo/karar/metrik-katalog", headers=H("koord"))
        check(r.status_code == 200 and len(r.json()["metrikler"]) >= 6, f"katalog seed + koordinatör okur ({len(r.json().get('metrikler', []))})")
        check((await ac.get("/api/ai/ceo/karar/metrik-katalog", headers=H("t1"))).status_code == 403, "öğretmen katalogu göremez (403)")

        # ── Deterministik motor (UYDURMA YOK) — birim ──
        katalog = await kz._katalog()
        foto_bad = {"ogretmen": {"yenileme_orani_yuzde": 30.0, "geciken_kur_sayisi": 2, "veli_memnuniyeti_5uzerinden": 4.0},
                    "muhasebe": {"beklenen_tahsilat": 1000, "tahsil_edilen": 950, "bekleyen_tahsilat": 50},
                    "kullanim": {"gorev_tamamlama_yuzde": 90.0}, "ogrenci": {}, "birim_ekonomi": {}, "nps": {}}
        ihl = kz._ihlal_eden_metrikler(foto_bad, katalog)
        check(any(i["metrik"]["key"] == "ogretmen.yenileme_orani" for i in ihl), "gerçek eşik ihlali saptandı (yenileme 30<45)")
        det = kz._deterministik_teklif(foto_bad, katalog, None)
        check(det["_kaynak"] == "deterministik" and det["evidence"][0]["current"] == 30.0, "deterministik teklif GERÇEK değeri (30.0) kullandı, uydurma yok")

        # ── AI mock ile teklif üret (yapılandırılmış) ──
        ai_mod.GEMINI_API_KEY = "k"
        async def fake_cc(system, user, max_tokens=3000, ozellik=""):
            return {"text": "", "parsed": dict(AI_TEKLIF), "error": None}
        ai_mod.call_claude = fake_cc
        r = await ac.post("/api/ai/ceo/karar/teklif-uret", headers=H("koord"))
        tk = r.json()["teklif"]
        check(r.status_code == 200 and tk["status"] == "awaiting_decision" and tk.get("_kaynak") == "ai" and "id" in tk and "tarih" in tk, f"AI teklifi üretildi (id/tarih/awaiting) ({r.status_code})")
        tid = tk["id"]
        check((await ac.post("/api/ai/ceo/karar/teklif-uret", headers=H("t1"))).status_code == 403, "öğretmen teklif üretemez (403)")

        # ── Deterministik yol (GEMINI yok) ──
        ai_mod.GEMINI_API_KEY = ""
        r = await ac.post("/api/ai/ceo/karar/teklif-uret", headers=H("adm"))
        check(r.status_code == 200 and r.json()["teklif"].get("_kaynak") == "deterministik", "GEMINI yokken deterministik teklif üretildi")

        # ── Yaşam döngüsü: karar → uygula → öğrenme ──
        check((await ac.post(f"/api/ai/ceo/karar/teklif/{tid}/karar", headers=H("koord"), json={"karar": "approved"})).status_code == 403, "koordinatör karar veremez (yalnız admin) (403)")
        r = await ac.post(f"/api/ai/ceo/karar/teklif/{tid}/karar", headers=H("adm"), json={"karar": "approved"})
        check(r.status_code == 200 and r.json()["status"] == "approved", "admin teklifi onayladı → approved")
        r = await ac.post(f"/api/ai/ceo/karar/teklif/{tid}/uygula", headers=H("adm"))
        check(r.status_code == 200 and r.json()["status"] == "implemented", "onaylı teklif uygulamaya alındı → implemented")
        r = await ac.post(f"/api/ai/ceo/karar/teklif/{tid}/ogrenme", headers=H("adm"), json={"expected_result": 55.0, "actual_result": 51.0, "lesson": "Pilot işe yaradı ama hedefin altında kaldı.", "execution_cost_actual": 95000.0})
        check(r.status_code == 200 and r.json()["learning"]["actual_result"] == 51.0, "öğrenme (beklenen vs gerçek + ders) kaydedildi")
        check(await db.ai_ceo_institution_memory.find_one({"key": f"lesson_{tid}", "approved": False}) is not None, "ders kurumsal hafızaya PATTERN adayı (onay bekler) olarak eklendi")
        check(await db.islem_log.find_one({"modul": "ai_ceo", "islem": "karar_teklif_karar"}) is not None, "karar islem_log'a düştü")

        # ── Kurumsal hafıza: admin ekler + onaylar ──
        check((await ac.post("/api/ai/ceo/karar/hafiza", headers=H("koord"), json={"type": "principle", "key": "x"})).status_code == 403, "koordinatör hafıza ekleyemez (403)")
        r = await ac.post("/api/ai/ceo/karar/hafiza", headers=H("adm"), json={"type": "principle", "key": "reading_speed_policy", "statement": "Okuma hızı 100 wpm altı öğrenci fiyat artışına dahil edilmez.", "approved": False})
        check(r.status_code == 200, "admin ilke ekledi (onaysız)")
        r = await ac.post("/api/ai/ceo/karar/hafiza/reading_speed_policy/onayla", headers=H("adm"))
        h = await db.ai_ceo_institution_memory.find_one({"key": "reading_speed_policy"})
        check(r.status_code == 200 and h.get("approved") is True, "ilke onaylandı (approved=true)")

        # ── Durum ucu ──
        r = await ac.get("/api/ai/ceo/karar/durum", headers=H("koord"))
        check(r.status_code == 200 and "saglik" in r.json() and "ihlaller" in r.json(), "durum ucu: fotoğraf + sağlık + ihlaller")

    await server.client.drop_database(TEST_DB)


if __name__ == "__main__":
    asyncio.run(run())
    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    sys.exit(1 if _kalan else 0)
