"""Egzersiz Motoru: kütüphane kapı (100) + öğrenci bazlı tekrarsızlık (Bölüm 2 #1,#2).

Kapsar:
- Aynı öğrenciye aynı içerik ikinci kez GÖSTERİLMEZ (havuz tükenene dek hep yeni).
- Kütüphane KUTUPHANE_KAP'a ulaşınca yeni içerik ÜRETİLMEZ (AI çağrılmaz);
  öğrenci hepsini görünce en eski görülen yeniden gösterilir (üretim yok → sayı sabit).

Testte AI çağrısını önlemek için içerikler önceden seed'lenir ve KUTUPHANE_KAP
küçük (3) yapılır. İzole test DB'sine karşı çalışır.
    cd appbackend && .venv/Scripts/python.exe tests/test_egzersiz_kutuphane_smoke.py
"""
import asyncio, os, sys, uuid

TEST_DB = "oba_test_egz_kutuphane"
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
    import modules.egzersiz_motoru as motor
    from core.auth import create_access_token
    from httpx import AsyncClient, ASGITransport
    await server.client.drop_database(TEST_DB)

    motor.KUTUPHANE_KAP = 3   # test için küçük kap

    TIP = "kelime_anlam_eslestirme"; SINIF = 3
    sid = str(uuid.uuid4()); uid = str(uuid.uuid4())
    await server.db.users.insert_one({"id": uid, "role": "student", "linked_id": sid, "sinif": SINIF})
    H = {"Authorization": f"Bearer {create_access_token({'sub': uid})}"}

    # Kap kadar (3) aktif içerik seed'le → AI üretimine gerek kalmaz
    seed_ids = []
    for i in range(3):
        iid = str(uuid.uuid4()); seed_ids.append(iid)
        await server.db.egzersiz_icerikler.insert_one({
            "id": iid, "tip": TIP, "sinif": SINIF, "zorluk": "orta",
            "icerik": {"ciftler": [{"sol": f"kelime{i}", "sag": f"anlam{i}"}]},
            "durum": "aktif", "kullanim_sayisi": 0, "mock": True, "kaynak": "seed",
        })

    async def oturum_ac(ac):
        r = await ac.post("/api/egzersiz/oturum", json={"tip": TIP, "sinif": SINIF}, headers=H)
        return r.status_code, r.json()

    transport = ASGITransport(app=server.app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        gorulen = []
        for _ in range(3):
            st, y = await oturum_ac(ac)
            if st == 200:
                gorulen.append(y.get("icerik_id"))
        check(len(set(gorulen)) == 3, f"ilk 3 oturum FARKLI içerik (tekrarsızlık): {len(set(gorulen))} özgün")
        check(set(gorulen) == set(seed_ids), "gösterilenler seed havuzundan (yeni üretim yok)")

        icerik_sayi_once = await server.db.egzersiz_icerikler.count_documents({"tip": TIP, "durum": "aktif"})
        # 4. oturum: öğrenci hepsini gördü + kap dolu → üretim YOK, tekrar göster
        st, y4 = await oturum_ac(ac)
        icerik_sayi_sonra = await server.db.egzersiz_icerikler.count_documents({"tip": TIP, "durum": "aktif"})
        check(st == 200 and y4.get("icerik_id") in seed_ids, f"kap dolunca mevcut içerik yeniden ({y4.get('icerik_id') in seed_ids})")
        check(icerik_sayi_sonra == icerik_sayi_once == 3, f"kap dolu → yeni içerik ÜRETİLMEDİ (AI yok): {icerik_sayi_once}→{icerik_sayi_sonra}")

    print(f"\nSONUC: {_g}/{_g + _k} kontrol gecti")
    await server.client.drop_database(TEST_DB)
    return _k == 0


if __name__ == "__main__":
    sys.exit(0 if asyncio.run(run()) else 1)
