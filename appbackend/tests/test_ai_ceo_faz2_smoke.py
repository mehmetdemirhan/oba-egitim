"""FAZ 2 smoke — trend grafikleri + Deniz kapsam genişletme + SHA doğrulama + Squad limit.

Dürüstlük: veri yoksa yeterli_veri=false (uydurma yok). Deniz yeni denetimler DETERMİNİSTİK.

    cd appbackend
    PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe tests/test_ai_ceo_faz2_smoke.py
"""
import asyncio
import os
import sys

TEST_DB = "oba_test_faz2"
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
    from modules.ai_ceo import deniz_kapsam as K
    from modules.ai_ceo.ayaz_v1 import _olay_hash, _GENESIS

    db = server.db
    await server.client.drop_database(TEST_DB)
    await db.users.insert_one({"id": "koord", "role": "coordinator", "ad": "Ko", "soyad": "O"})
    await db.users.insert_one({"id": "t1", "role": "teacher", "ad": "Öğ", "soyad": "B"})

    def H(u):
        return {"Authorization": f"Bearer {server.create_access_token({'sub': u})}"}

    async with AsyncClient(transport=ASGITransport(app=server.app), base_url="http://test") as ac:
        # ── BOŞ DB → tüm trendler yeterli_veri=false ──
        for yol in ["/api/ai/ceo/karar/trend", "/api/ai/squad/scorecard/trend",
                    "/api/ai/squad/deploy-queue/bekleme-trend", "/api/ai/squad/orkestrator/trend"]:
            r = (await ac.get(yol, headers=H("koord"))).json()
            check(r["yeterli_veri"] is False, f"boş DB → {yol.split('/')[-1]} yeterli_veri false")

        # ── Karar net etki trendi (2 ölçüm noktası) ──
        await db.ai_ceo_proposals.insert_one({"id": "k1", "title": "Pilot", "measurement": {"olcumler": [
            {"tarih": "2026-07-10T00:00:00+00:00", "net_etki": 3.0, "pilot_deger": 8, "kontrol_deger": 5, "genel_deger": 7},
            {"tarih": "2026-07-17T00:00:00+00:00", "net_etki": 5.0, "pilot_deger": 10, "kontrol_deger": 5, "genel_deger": 8}]}})
        r = (await ac.get("/api/ai/ceo/karar/trend", headers=H("koord"))).json()
        check(r["yeterli_veri"] and r["net_nokta_sayisi"] == 2, "karar trend: 2 net etki noktası → yeterli")

        # ── Scorecard trendi (atlas 2 hafta) ──
        await db.ai_atlas_reports.insert_many([
            {"rapor_id": "a1", "mimari_onay": True, "tarih": "2026-07-08T00:00:00+00:00"},
            {"rapor_id": "a2", "mimari_onay": False, "tarih": "2026-07-15T00:00:00+00:00"}])
        r = (await ac.get("/api/ai/squad/scorecard/trend", headers=H("koord"))).json()
        check(r["yeterli_veri"] and len(r["ajanlar"]["atlas"]) == 2, "scorecard trend: atlas 2 haftalık nokta")

        # ── Deploy bekleme trendi (2 entegre kayıt, 2 hafta) ──
        await db.squad_deploy_queue.insert_many([
            {"id": "d1", "durum": "entegre_edildi", "tarih": "2026-07-06T00:00:00+00:00", "entegrasyon_tarihi": "2026-07-08T00:00:00+00:00"},
            {"id": "d2", "durum": "entegre_edildi", "tarih": "2026-07-13T00:00:00+00:00", "entegrasyon_tarihi": "2026-07-16T00:00:00+00:00"}])
        r = (await ac.get("/api/ai/squad/deploy-queue/bekleme-trend", headers=H("koord"))).json()
        check(r["yeterli_veri"] and len(r["seri"]) == 2 and r["seri"][0]["ort_bekleme_gun"] == 2.0,
              "deploy bekleme trend: 2 hafta, ilk hafta ort 2 gün")

        # ── Deniz kapsam: KARAR dayanak zayıflığı (deterministik generator, doğrudan) ──
        await db.ai_ceo_proposals.insert_many([
            {"id": "z1", "_kaynak": "deterministik", "evidence": [], "veri_kalitesi": 20, "title": "A"},
            {"id": "z2", "_kaynak": "deterministik", "evidence": [], "veri_kalitesi": 10, "title": "B"}])
        bulgular = await K.karar_dayanak_kontrol()
        check(any(b["tur"] == "karar_dayanak_zayifligi" for b in bulgular), "Deniz: karar dayanak zayıflığı bulgusu üretildi")

        # ── Deniz kapsam: Ayaz hash-chain kırılması ──
        await db.ayaz_audit.insert_one({"event_id": "e0", "task_id": "T1", "seq": 0, "previous_hash": _GENESIS,
                                        "event_hash": "SAHTE_HASH", "actor": "sistem", "action": "test",
                                        "timestamp": "2026-07-18T00:00:00+00:00", "metadata": {}})
        z = await K.ayaz_zincir_kontrol()
        check(any(b["tur"] == "ayaz_audit_zincir_kirilmasi" and b["onem"] == "kritik" for b in z),
              "Deniz: Ayaz hash-chain kırılması KRİTİK bulgu")
        # sağlam zincir → bulgu YOK (dürüstlük: temizse sessiz)
        await db.ayaz_audit.delete_many({})
        h0 = _olay_hash("T2", 0, _GENESIS, "sistem", "olustur", "2026-07-18T00:00:00+00:00", {})
        await db.ayaz_audit.insert_one({"event_id": "e1", "task_id": "T2", "seq": 0, "previous_hash": _GENESIS,
                                        "event_hash": h0, "actor": "sistem", "action": "olustur",
                                        "timestamp": "2026-07-18T00:00:00+00:00", "metadata": {}})
        check(await K.ayaz_zincir_kontrol() == [], "Deniz: sağlam zincirde bulgu yok (temiz=sessiz)")

        # ── Deniz kapsam: Squad ret örüntüsü (Nova baskın) ──
        await db.ai_squad_pipeline_runs.insert_many([
            {"task_id": f"r{i}", "asama": "reddedildi", "adimlar": [{"ajan": "Nova", "sonuc": "vize yok, reddedildi"}]}
            for i in range(4)])
        rp = await K.squad_ret_oruntu_kontrol()
        check(any(b["tur"] == "squad_ret_oruntusu" and b["kanit"]["baskin_ajan"] == "Nova" for b in rp),
              "Deniz: Squad ret örüntüsü (Nova baskın) bulgusu")

        # ── SHA doğrulama (format) ──
        r = (await ac.get("/api/ai/squad/deploy-queue/sha-dogrula", params={"ref": "xyz"}, headers=H("koord"))).json()
        check(r["gecerli"] is False, "SHA doğrula: geçersiz format → gecerli false")
        r = (await ac.get("/api/ai/squad/deploy-queue/sha-dogrula", params={"ref": "a" * 40}, headers=H("koord"))).json()
        check(r["gecerli"] is None and r["tur"] == "git_sha", "SHA doğrula: geçerli format ama GitHub yok → doğrulanamadı (None)")
        r = (await ac.get("/api/ai/squad/deploy-queue/sha-dogrula", params={"ref": "https://x.vercel.app"}, headers=H("koord"))).json()
        check(r["tur"] == "vercel", "SHA doğrula: Vercel referansı tanındı")

        # ── Squad limit durumu ──
        r = (await ac.get("/api/ai/squad/orkestrator/limit-durum", headers=H("koord"))).json()
        check(r["gunluk_limit"] == 50 and r["tahmini_aylik_maliyet"] is None, "Squad limit: varsayılan 50/gün, maliyet tanımsız (birim ücret 0)")

        # ── RBAC ──
        check((await ac.get("/api/ai/squad/scorecard/trend", headers=H("t1"))).status_code == 403, "öğretmen trend göremez (403)")

    await server.client.drop_database(TEST_DB)


if __name__ == "__main__":
    asyncio.run(run())
    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    sys.exit(1 if _kalan else 0)
