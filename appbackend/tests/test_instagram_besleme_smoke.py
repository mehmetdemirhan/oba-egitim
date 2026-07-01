"""Instagram beslemesi smoke testi (izole DB, mock RSS — ağ gerekmez).

    cd appbackend
    .venv/Scripts/python.exe tests/test_instagram_besleme_smoke.py

Kapsam:
  - RSS ayrıştırma (5 post) + senkronize → 5 kayıt; tekrar → 0 yeni (duplicate)
  - beğen ilk kez → +3 XP; tekrar → +0 (idempotent); kapatma → XP geri alınmaz
  - onur_ig_begen → +5; yorum → +10
  - öğrenci /etkilesim → 403; öğretmen → 200
"""
import asyncio
import os
import sys
import uuid

TEST_DB = "oba_test_instagram_smoke"
os.environ["MONGO_URL"] = os.environ.get("MONGO_URL_TEST", "mongodb://localhost:27017")
os.environ["DB_NAME"] = TEST_DB
os.environ.setdefault("SECRET_KEY", "test-secret-key")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_g = 0
_k = 0


def check(kosul, mesaj):
    global _g, _k
    if kosul:
        _g += 1; print(f"  [GECTI] {mesaj}")
    else:
        _k += 1; print(f"  [KALDI] {mesaj}")


def _mock_rss(n=5):
    items = ""
    for i in range(1, n + 1):
        items += f"""
  <item>
    <title>Doğa etkinliği {i}</title>
    <link>https://www.instagram.com/p/ABC00{i}/</link>
    <guid>https://www.instagram.com/p/ABC00{i}/</guid>
    <description><![CDATA[<img src="https://cdn/{i}.jpg"/> Kelebek gözlemi {i}]]></description>
    <pubDate>Wed, 0{i} Oct 2024 10:00:00 +0000</pubDate>
    <enclosure url="https://cdn/{i}.jpg" type="image/jpeg"/>
  </item>"""
    return f"""<?xml version="1.0"?>
<rss version="2.0" xmlns:media="http://search.yahoo.com/mrss/"><channel>
<title>Doğadaki Öğretmenim</title>{items}
</channel></rss>"""


async def run():
    import server
    import modules.instagram_beslemesi as ig
    from core.auth import create_access_token
    from httpx import AsyncClient, ASGITransport

    await server.client.drop_database(TEST_DB)

    adm = str(uuid.uuid4())
    tch = str(uuid.uuid4())
    stu = str(uuid.uuid4())
    await server.db.users.insert_one({"id": adm, "ad": "Admin", "soyad": "Y", "role": "admin"})
    await server.db.users.insert_one({"id": tch, "ad": "Ayşe", "soyad": "Ö", "role": "teacher", "puan": 0})
    await server.db.users.insert_one({"id": stu, "ad": "Ali", "soyad": "Y", "role": "student"})
    HA = {"Authorization": f"Bearer {create_access_token({'sub': adm})}"}
    HT = {"Authorization": f"Bearer {create_access_token({'sub': tch})}"}
    HS = {"Authorization": f"Bearer {create_access_token({'sub': stu})}"}

    # ── RSS ayrıştırma birim testi (stdlib/feedparser) ──
    postlar = ig._rss_ayristir(_mock_rss(5))
    check(len(postlar) == 5, f"5 post ayrıştırıldı (gelen {len(postlar)})")
    check(postlar[0]["instagram_post_id"] == "ABC001", f"post_id doğru (gelen {postlar[0]['instagram_post_id']})")
    check(postlar[0]["medya_url"] == "https://cdn/1.jpg", "medya_url çıkarıldı")

    # RSS getirmeyi mock'la (ağ yok)
    async def sahte_rss():
        return _mock_rss(5)
    ig._rss_ham_getir = sahte_rss

    transport = ASGITransport(app=server.app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # senkronize → 5 yeni
        r = await ac.post("/api/instagram/senkronize", headers=HA)
        check(r.status_code == 200 and r.json()["yeni"] == 5, f"senkronize 5 yeni (gelen {r.json() if r.status_code==200 else r.status_code})")
        # tekrar → 0 yeni
        r = await ac.post("/api/instagram/senkronize", headers=HA)
        check(r.json()["yeni"] == 0 and r.json()["mevcut"] == 5, "tekrar senkronda 0 yeni (duplicate atlandı)")

        # öğretmen postları görür
        r = await ac.get("/api/instagram/postlar", headers=HT)
        check(r.status_code == 200 and len(r.json()["postlar"]) == 5, "öğretmen 5 post görüyor")
        pid = r.json()["postlar"][0]["instagram_post_id"]

        # öğrenci etkileşim → 403
        r = await ac.post("/api/instagram/etkilesim", headers=HS, json={"instagram_post_id": pid, "eylem": "begen", "deger": True})
        check(r.status_code == 403, f"öğrenci etkileşim 403 (status={r.status_code})")

        # beğen ilk kez → +3
        r = await ac.post("/api/instagram/etkilesim", headers=HT, json={"instagram_post_id": pid, "eylem": "begen", "deger": True})
        check(r.status_code == 200 and r.json()["kazandigi_xp"] == 3, f"ilk beğen +3 (gelen {r.json()})")
        # tekrar beğen → +0
        r = await ac.post("/api/instagram/etkilesim", headers=HT, json={"instagram_post_id": pid, "eylem": "begen", "deger": True})
        check(r.json()["kazandigi_xp"] == 0, "tekrar beğen +0 (idempotent)")
        # beğeni kapat → +0, XP geri alınmaz
        r = await ac.post("/api/instagram/etkilesim", headers=HT, json={"instagram_post_id": pid, "eylem": "begen", "deger": False})
        check(r.json()["kazandigi_xp"] == 0, "beğeni kapatma +0")
        # tekrar aç → +0 (bir kez verildi)
        r = await ac.post("/api/instagram/etkilesim", headers=HT, json={"instagram_post_id": pid, "eylem": "begen", "deger": True})
        check(r.json()["kazandigi_xp"] == 0, "yeniden açma +0 (XP tekrar verilmez)")

        # onur_ig_begen → +5
        r = await ac.post("/api/instagram/etkilesim", headers=HT, json={"instagram_post_id": pid, "eylem": "onur_ig_begen", "deger": True})
        check(r.json()["kazandigi_xp"] == 5, f"onur beğen +5 (gelen {r.json()['kazandigi_xp']})")

        # yorum → +10
        r = await ac.post("/api/instagram/yorum", headers=HT, json={"instagram_post_id": pid, "yorum": "Harika bir etkinlik!"})
        check(r.json()["kazandigi_xp"] == 10, f"yorum +10 (gelen {r.json()['kazandigi_xp']})")
        # yorum düzenleme → +0
        r = await ac.post("/api/instagram/yorum", headers=HT, json={"instagram_post_id": pid, "yorum": "Güncellendi"})
        check(r.json()["kazandigi_xp"] == 0, "yorum düzenleme +0")

        # öğretmen toplam puan = 3 + 5 + 10 = 18
        u = await server.db.users.find_one({"id": tch})
        check(u.get("puan") == 18, f"öğretmen toplam puan 18 (gelen {u.get('puan')})")

        # post kullanıcı durumu güncel
        r = await ac.get("/api/instagram/postlar", headers=HT)
        p0 = next(p for p in r.json()["postlar"] if p["instagram_post_id"] == pid)
        kd = p0["kullanici_durumu"]
        check(kd["begen"] is True and kd["onur_ig_begen"] is True and kd["yorum"] == "Güncellendi", "kullanıcı_durumu doğru")
        check(kd["kazandigi_xp"] == 18, f"post kazandığı xp 18 (gelen {kd['kazandigi_xp']})")

        # durum (admin)
        r = await ac.get("/api/instagram/durum", headers=HA)
        check(r.status_code == 200 and r.json()["toplam_post"] == 5, "durum toplam_post 5")
        r = await ac.put("/api/instagram/durum", headers=HA, json={"aktif": False})
        check(r.json()["aktif"] is False, "aktif toggle çalışıyor")
        r = await ac.get("/api/instagram/durum", headers=HS)
        check(r.status_code == 403, "öğrenci durum 403")


if __name__ == "__main__":
    print("=" * 56)
    print("INSTAGRAM BESLEME SMOKE TEST")
    print("=" * 56)
    asyncio.run(run())
    print("\n" + "=" * 56)
    print(f"SONUC: {_g}/{_g + _k} kontrol gecti")
    print("=" * 56)
    sys.exit(0 if _k == 0 else 1)
