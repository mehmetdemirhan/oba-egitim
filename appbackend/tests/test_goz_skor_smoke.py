"""Göz egzersizi skoru + kişisel rekor smoke testi (Bölüm 2 #4).

Kapsar:
- POST /egzersiz/goz/skor skoru kaydeder; skor doğruluk+süre+zorluk ile hesaplanır.
- Hızlı VE doğru → yüksek; yavaş/hatalı → düşük; zor → daha yüksek.
- yeni_rekor bayrağı + kişisel rekor doğru; GET /egzersiz/goz/rekorlar tip bazlı en yüksek.

İzole test DB'sine karşı çalışır. Gerçek DB'ye dokunmaz.
    cd appbackend && .venv/Scripts/python.exe tests/test_goz_skor_smoke.py
"""
import asyncio, os, sys, uuid

TEST_DB = "oba_test_goz_skor"
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

    sid = str(uuid.uuid4()); uid = str(uuid.uuid4())
    await server.db.users.insert_one({"id": uid, "role": "student", "linked_id": sid})
    H = {"Authorization": f"Bearer {create_access_token({'sub': uid})}"}

    transport = ASGITransport(app=server.app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        async def skor(tip, dogru, yanlis, sure, zorluk):
            r = await ac.post("/api/egzersiz/goz/skor", json={"tip": tip, "dogru": dogru, "yanlis": yanlis, "sure_sn": sure, "zorluk": zorluk}, headers=H)
            return r.status_code, r.json()

        st, y = await skor("metin_arama", 10, 0, 30, 3)
        check(st == 200 and y["skor"] > 0 and y["yeni_rekor"] is True, f"ilk skor kaydı + yeni rekor ({y})")
        ilk = y["skor"]

        st, hizli = await skor("metin_arama", 10, 0, 10, 3)  # aynı doğru, daha hızlı
        check(hizli["skor"] > ilk, f"hızlı bitiren daha yüksek skor ({hizli['skor']} > {ilk})")
        check(hizli["yeni_rekor"] is True and hizli["rekor"] == hizli["skor"], "rekor güncellendi")

        st, hatali = await skor("metin_arama", 5, 5, 30, 3)  # yarısı yanlış
        check(hatali["skor"] < ilk, f"hatalı tur düşük skor ({hatali['skor']} < {ilk})")
        check(hatali["yeni_rekor"] is False, "düşük skor rekoru kırmaz")

        st, zor = await skor("kelime_arama", 10, 0, 30, 5)
        st, kolay = await skor("kelime_arama", 10, 0, 30, 1)
        check(zor["skor"] > kolay["skor"], f"zor egzersiz daha çok puan ({zor['skor']} > {kolay['skor']})")

        r = await ac.get("/api/egzersiz/goz/rekorlar", headers=H)
        rek = r.json()
        check(r.status_code == 200 and rek.get("metin_arama", {}).get("rekor") == hizli["skor"], "rekorlar tip bazlı en yüksek")
        check(rek.get("metin_arama", {}).get("oynanma") == 3, f"oynanma sayısı doğru ({rek.get('metin_arama')})")

    print(f"\nSONUC: {_g}/{_g + _k} kontrol gecti")
    await server.client.drop_database(TEST_DB)
    return _k == 0


if __name__ == "__main__":
    sys.exit(0 if asyncio.run(run()) else 1)
