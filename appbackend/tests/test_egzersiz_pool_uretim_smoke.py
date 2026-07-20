"""Kelime-anlam egzersizleri onaylı havuzdan TAZE üretilir (aynı içerik tekrarı yok).

Kullanıcı geri bildirimi: aynı egzersiz tekrar tekrar aynı içeriği veriyordu (AI
başarısız → statik mock). Çözüm: kelime_anlam_eslestirme/hafiza_karti onaylı MEB
havuzundaki kelime+anlam çiftlerinden yerel ve her seferinde farklı üretilir.

İzole test DB'sine karşı çalışır.
    cd appbackend && .venv/Scripts/python.exe tests/test_egzersiz_pool_uretim_smoke.py
"""
import asyncio, os, sys, uuid

TEST_DB = "oba_test_egz_pool"
os.environ["MONGO_URL"] = os.environ.get("MONGO_URL_TEST", "mongodb://localhost:27017")
os.environ["DB_NAME"] = TEST_DB
os.environ.setdefault("SECRET_KEY", "test-secret-key")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_g = 0; _k = 0
def check(k, m):
    global _g, _k
    _g += 1 if k else 0; _k += 0 if k else 1
    print(f"  [{'GECTI' if k else 'KALDI'}] {m}")


async def run():
    import server
    from core.auth import create_access_token
    from httpx import AsyncClient, ASGITransport
    await server.client.drop_database(TEST_DB)

    TIP = "kelime_anlam_eslestirme"; SINIF = 3
    # Onaylı MEB havuzunu anlamlı kelimelerle doldur
    for i in range(40):
        await server.db.meb_kelimeleri.insert_one({
            "id": str(uuid.uuid4()), "kelime": f"kelime{i}", "sinif": SINIF, "ders": "turkce",
            "anlam": f"kelime{i} kısa anlamı", "durum": "aktif", "onaylandi": True, "kullanim_sayisi": 0,
        })

    sid = str(uuid.uuid4()); uid = str(uuid.uuid4())
    await server.db.users.insert_one({"id": uid, "role": "student", "linked_id": sid, "sinif": SINIF})
    H = {"Authorization": f"Bearer {create_access_token({'sub': uid})}"}

    transport = ASGITransport(app=server.app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        icerikler = []
        for _ in range(4):
            r = await ac.post("/api/egzersiz/oturum", json={"tip": TIP, "sinif": SINIF}, headers=H)
            if r.status_code == 200:
                ciftler = r.json().get("icerik", {}).get("ciftler", [])
                icerikler.append(tuple(sorted(c.get("sol", "") for c in ciftler)))

        check(len(icerikler) == 4, f"4 oturum açıldı ({len(icerikler)})")
        check(all(len(x) >= 3 for x in icerikler), "her egzersizde ≥3 kelime-anlam çifti (havuzdan)")
        # Havuzdan gelen kelimeler (statik mock 'cömert/mütevazı' DEĞİL)
        tum_kelimeler = {w for ic in icerikler for w in ic}
        check(all(w.startswith("kelime") for w in tum_kelimeler), f"içerik onaylı havuzdan (mock değil): {list(tum_kelimeler)[:4]}")
        check(len(set(icerikler)) >= 3, f"turlar FARKLI içerik (tekrar yok): {len(set(icerikler))}/4 özgün")

    print(f"\nSONUC: {_g}/{_g + _k} kontrol gecti")
    await server.client.drop_database(TEST_DB)
    return _k == 0


if __name__ == "__main__":
    sys.exit(0 if asyncio.run(run()) else 1)
