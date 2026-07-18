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


def _iso_gun_once(n):
    from datetime import datetime, timezone, timedelta
    return (datetime.now(timezone.utc) - timedelta(days=n)).isoformat()


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

        # ── Otomatik checkpoint ölçümü (gerçek metrik, uydurma yok) ──
        from datetime import datetime, timezone, timedelta
        eski = (datetime.now(timezone.utc) - timedelta(days=20)).isoformat()
        await db.ai_ceo_proposals.insert_one({"id": "imp1", "persona": "Ayda", "status": "implemented", "uygulama_tarihi": eski,
            "measurement": {"primary_metric": "ogretmen.yenileme_orani", "baseline": 40.0, "target": 55.0, "checkpoints": [14, 30], "olcumler": []}})
        async def fake_foto():
            return {"id": "f1", "ogretmen": {"yenileme_orani_yuzde": 50.0}, "muhasebe": {}, "ogrenci": {}, "kullanim": {}, "birim_ekonomi": {}, "nps": {}}
        kz.F.sistem_fotografi = fake_foto
        res = await kz.olcum_calistir()
        check(res["guncellenen_teklif"] >= 1, f"checkpoint ölçümü çalıştı ({res['guncellenen_teklif']})")
        p = await db.ai_ceo_proposals.find_one({"id": "imp1"})
        olc = p["measurement"]["olcumler"]
        check(any(o["gun"] == 14 and o["deger"] == 50.0 for o in olc), "gün 14: GERÇEK metrik değeri 50.0 kaydedildi (uydurma yok)")
        check(any(o["gun"] == 14 and abs(o["ilerleme_yuzde"] - 66.7) < 0.2 for o in olc), "hedefe ilerleme %66.7 hesaplandı ((50-40)/(55-40))")
        check(not any(o["gun"] == 30 for o in olc), "gün 30 (20 gün geçti, henüz gelmedi) ölçülmedi")
        await kz.olcum_calistir()
        p2 = await db.ai_ceo_proposals.find_one({"id": "imp1"})
        check(sum(1 for o in p2["measurement"]["olcumler"] if o["gun"] == 14) == 1, "idempotent: gün 14 tekrar eklenmez")

        # ── FAZ 3: otonom deney grupları (pilot/kontrol) + segment ölçümü ──
        teklif_f3 = dict(AI_TEKLIF)
        teklif_f3["id"] = "imp_faz3"
        teklif_f3["title"] = "Kur 1 Öğrencileri İçin Yoğunlaştırılmış Sezon"
        teklif_f3["status"] = "approved"
        teklif_f3["measurement"] = dict(AI_TEKLIF["measurement"])  # kopya (olcumler paylaşımını önle)
        await db.ai_ceo_proposals.insert_one(teklif_f3)
        for i in range(4):  # 4 aktif Kur 1 öğrencisi → 2 pilot / 2 kontrol
            await db.students.insert_one({"id": f"f3_s{i}", "kur": "Kur 1", "arsivli": False, "mezun": False})
        r = await ac.post("/api/ai/ceo/karar/teklif/imp_faz3/uygula", headers=H("adm"))
        check(r.status_code == 200 and r.json()["status"] == "implemented", "Faz 3: onaylı teklif uygulandı (implemented)")
        pilots = await db.students.count_documents({"ai_experiments.pilot_groups": "imp_faz3"})
        controls = await db.students.count_documents({"ai_experiments.control_groups": "imp_faz3"})
        check(pilots == 2 and controls == 2, f"Faz 3: öğrenciler %50/%50 otonom bölündü (pilot {pilots}/kontrol {controls}, db.students'e mühürlendi)")
        # 15 gün geçmiş gibi yap → gün 14 checkpoint tetiklensin
        await db.ai_ceo_proposals.update_one({"id": "imp_faz3"}, {"$set": {"uygulama_tarihi": _iso_gun_once(15)}})
        res_f3 = await kz.olcum_calistir()
        check(res_f3["guncellenen_teklif"] >= 1, "Faz 3: ölçüm motoru çalıştı")
        pf3 = await db.ai_ceo_proposals.find_one({"id": "imp_faz3"})
        o14 = next((o for o in pf3["measurement"]["olcumler"] if o["gun"] == 14), None)
        check(o14 is not None and o14["pilot_deger"] is not None and o14["kontrol_deger"] is not None,
              "Faz 3: gün 14 pilot+kontrol segment değerleri hesaplandı (uydurma yok)")
        check(o14 is not None and "net_etki" in o14 and "genel_deger" in o14,
              "Faz 3: net deney etkisi (pilot−kontrol) + kurum-geneli değer kaydedildi")

        # ── FAZ 2.5: otonom ajan araçları (tool-calling) + audit ──
        from modules.ai_ceo.tools_engine import get_metric, compare_periods, find_segments
        # NPS tohumla: Kur 1 düşük (n=4), Kur 3 yüksek (n=4) → find_segments Kur 1'i yakalamalı
        for i in range(4):
            await db.ai_ceo_nps.insert_one({"id": f"nps1_{i}", "kur": "Kur 1", "puan": 3, "ogrenci_takma": f"tk1_{i}"})
            await db.ai_ceo_nps.insert_one({"id": f"nps3_{i}", "kur": "Kur 3", "puan": 9, "ogrenci_takma": f"tk3_{i}"})
        for i in range(4):  # find_segments distinct kur için Kur 3 öğrencisi de olsun
            await db.students.insert_one({"id": f"k3_{i}", "kur": "Kur 3", "arsivli": False, "mezun": False})

        m_res = await get_metric("ogretmen.veli_memnuniyeti", filters={"kur": "Kur 1"}, teklif_id="test_agent")
        check("value" in m_res and m_res["value"] == 3.0 and m_res["sample_size"] == 4,
              f"Faz 2.5: get_metric Kur 1 NPS segmentini GERÇEK hesapladı (değer {m_res['value']}, n={m_res['sample_size']})")
        t_res = await compare_periods("ogretmen.yenileme_orani", teklif_id="test_agent")
        check("trend" in t_res and "delta" in t_res, "Faz 2.5: compare_periods trend + delta döndürdü")
        s_res = await find_segments("ogretmen.veli_memnuniyeti", ["kur"], teklif_id="test_agent")
        check(isinstance(s_res, list) and any("kur=Kur 1" in b["segment"] for b in s_res),
              f"Faz 2.5: find_segments ortalamadan sapan Kur 1 segmentini yakaladı ({len(s_res)} bulgu)")
        audit = await db.ai_ceo_tool_runs.count_documents({"teklif_id": "test_agent"})
        check(audit == 3, f"Faz 2.5: yalnız PUBLIC araç çağrıları audit'e mühürlendi ({audit}=3, iç get_metric loglanmadı)")

    await server.client.drop_database(TEST_DB)


if __name__ == "__main__":
    asyncio.run(run())
    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    sys.exit(1 if _kalan else 0)
