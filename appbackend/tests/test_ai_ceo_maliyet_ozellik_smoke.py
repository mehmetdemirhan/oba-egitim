"""AI CEO — A2: maliyet özellik-bazlı çağrı kırılımı. Merkezi sayaç (call_claude /
gemini_grounded_call) çağrıyı yapan özelliği ai_request_log'a etiketler; maliyet özeti +
Deniz maliyet bulgusu bu kırılımı taşır.

    cd appbackend
    PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe tests/test_ai_ceo_maliyet_ozellik_smoke.py
"""
import asyncio
import os
import sys

TEST_DB = "oba_test_ai_ceo_maliyet_ozellik"
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
    import server  # DB bağlar
    import core.ai as ai_mod
    import modules.ai_ceo.deniz_guc as guc

    db = server.db
    await server.client.drop_database(TEST_DB)

    # ── 1) Merkezi sayaç: call_claude özelliği etiketler ──
    ai_mod.GEMINI_API_KEY = "k"

    async def fake_gemini(prompt, system="", max_tokens=4000):
        return '{"ok": 1}'
    ai_mod._gemini_call = fake_gemini

    await ai_mod.call_claude("s", "u", ozellik="ceo_analiz")
    check(await db.ai_request_log.find_one({"ozellik": "ceo_analiz"}) is not None, "call_claude özelliği ai_request_log'a etiketledi")
    await ai_mod.call_claude("s", "u")  # etiketsiz çağrı
    check(await db.ai_request_log.find_one({"ozellik": "diger"}) is not None, "özelliksiz çağrı 'diger' olarak etiketlendi (merkezî varsayılan)")

    # ── 2) maliyet_ozet + maliyet_bulgu özellik kırılımını taşır (+ sıçrama) ──
    await db.ai_request_log.delete_many({})
    for i in range(2):  # önceki ay: 2 çağrı
        await db.ai_request_log.insert_one({"id": f"p{i}", "model": "m", "ozellik": "ceo_analiz", "tarih": "2026-06-10T00:00:00"})
    for i in range(6):  # bu ay: 6 çağrı (4 pazar + 2 denetim) → %200 sıçrama
        await db.ai_request_log.insert_one({"id": f"c{i}", "model": "m", "ozellik": ("pazar_arastirma" if i < 4 else "denetim"), "tarih": "2026-07-10T00:00:00"})

    oz = await guc.maliyet_ozet()
    check(oz["ozellik_dagilimi"].get("pazar_arastirma") == 4 and oz["ozellik_dagilimi"].get("ceo_analiz") == 2,
          f"maliyet_ozet özellik dağılımı doğru ({oz['ozellik_dagilimi']})")
    # en çok çağıran özellik başta (azalan sıralı)
    ilk = next(iter(oz["ozellik_dagilimi"]))
    check(ilk == "pazar_arastirma", f"özellik dağılımı azalan sıralı (ilk={ilk})")

    bulgular = await guc.maliyet_bulgu()
    kanit = bulgular[0]["kanit"] if bulgular else {}
    check(bool(kanit.get("ozellik_dagilimi")), "Deniz maliyet bulgusu özellik-bazlı kırılımı kanıtta taşıyor")

    # ── 3) eski (etiketsiz) loglar 'etiketsiz' altında toplanır ──
    await db.ai_request_log.insert_one({"id": "eski", "model": "m", "tarih": "2026-07-11T00:00:00"})
    oz2 = await guc.maliyet_ozet()
    check(oz2["ozellik_dagilimi"].get("etiketsiz") == 1, "eski etiketsiz loglar 'etiketsiz' altında sayılıyor")

    await server.client.drop_database(TEST_DB)


if __name__ == "__main__":
    asyncio.run(run())
    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    sys.exit(1 if _kalan else 0)
