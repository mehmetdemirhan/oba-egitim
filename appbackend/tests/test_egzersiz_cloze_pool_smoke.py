"""Cloze (boşluk doldurma) onaylı OKUMA METİNLERİNDEN üretilir (AI'sız, taze).

Kullanıcı isteği: "havuzdaki okuma metinlerini kelime ve anlam temelli egzersizlerde
kullanabilir". Cloze artık analiz_metinler havuzundan gerçek metinlerle üretilir;
boşluk kelimeleri metinden, çeldiriciler onaylı kelime havuzundan gelir.

İzole test DB'sine karşı çalışır.
    cd appbackend && .venv/Scripts/python.exe tests/test_egzersiz_cloze_pool_smoke.py
"""
import asyncio, os, sys, uuid

TEST_DB = "oba_test_egz_cloze"
os.environ["MONGO_URL"] = os.environ.get("MONGO_URL_TEST", "mongodb://localhost:27017")
os.environ["DB_NAME"] = TEST_DB
os.environ.setdefault("SECRET_KEY", "test-secret-key")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_g = 0; _k = 0
def check(k, m):
    global _g, _k
    _g += 1 if k else 0; _k += 0 if k else 1
    print(f"  [{'GECTI' if k else 'KALDI'}] {m}")

METIN = ("Ali sabah erkenden uyandı ve pencereden dışarı baktı. Bahçedeki ağaçlar "
         "rüzgarda usulca sallanıyordu. Kahvaltısını yaptıktan sonra okuluna gitmek için "
         "hazırlandı. Yolda komşusunun köpeği neşeyle ona doğru koştu. Ali güzel bir gün "
         "geçireceğini düşünerek okulun bahçesine girdi ve arkadaşlarını selamladı.")


async def run():
    import server
    from core.auth import create_access_token
    from httpx import AsyncClient, ASGITransport
    await server.client.drop_database(TEST_DB)

    TIP = "cloze_bosluk_doldurma"; SINIF = 3
    await server.db.analiz_metinler.insert_one({
        "id": str(uuid.uuid4()), "baslik": "Ali'nin Sabahı", "icerik": METIN,
        "bolum": "analiz", "durum": "havuzda", "sinif_seviyesi": SINIF, "kelime_sayisi": len(METIN.split()),
    })
    for i in range(30):
        await server.db.meb_kelimeleri.insert_one({
            "id": str(uuid.uuid4()), "kelime": f"cel{i}kelime", "sinif": SINIF, "ders": "turkce",
            "anlam": f"anlam {i}", "durum": "aktif", "onaylandi": True, "kullanim_sayisi": 0,
        })

    sid = str(uuid.uuid4()); uid = str(uuid.uuid4())
    await server.db.users.insert_one({"id": uid, "role": "student", "linked_id": sid, "sinif": SINIF})
    H = {"Authorization": f"Bearer {create_access_token({'sub': uid})}"}

    transport = ASGITransport(app=server.app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        turlar = []
        for _ in range(3):
            r = await ac.post("/api/egzersiz/oturum", json={"tip": TIP, "sinif": SINIF}, headers=H)
            if r.status_code == 200:
                sorular = r.json().get("icerik", {}).get("sorular", [])
                turlar.append(sorular)

        check(len(turlar) == 3, f"3 cloze oturumu açıldı ({len(turlar)})")
        check(all(len(s) >= 2 for s in turlar), "her turda ≥2 boşluk sorusu")
        s0 = turlar[0][0]
        check("___" in s0.get("soru", "") and len(s0.get("secenekler", [])) == 4, "boşluk + 4 seçenek")
        dogru_kel = s0["secenekler"][s0["dogru"]]
        check(dogru_kel.lower() in METIN.lower(), f"doğru cevap METİNDEN geliyor: '{dogru_kel}'")
        imzalar = {tuple(x.get("soru", "") for x in s) for s in turlar}
        check(len(imzalar) >= 2, f"turlar farklı (tekrar yok): {len(imzalar)}/3 özgün")

    print(f"\nSONUC: {_g}/{_g + _k} kontrol gecti")
    await server.client.drop_database(TEST_DB)
    return _k == 0


if __name__ == "__main__":
    sys.exit(0 if asyncio.run(run()) else 1)
