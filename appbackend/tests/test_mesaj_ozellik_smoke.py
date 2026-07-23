"""Mesaj özellikleri smoke: yıldız, ertele(+hatırlatma), yanıt, dosya eki (GridFS+MIME).

cd appbackend && .venv/Scripts/python.exe tests/test_mesaj_ozellik_smoke.py
"""
import asyncio
import os
import sys
import uuid
from datetime import timedelta

TEST_DB = "oba_test_mesaj_ozellik"
os.environ["MONGO_URL"] = os.environ.get("MONGO_URL_TEST", "mongodb://localhost:27017")
os.environ["DB_NAME"] = TEST_DB
os.environ.setdefault("SECRET_KEY", "test-secret-key")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_g = 0
_k = 0


def check(k, m):
    global _g, _k
    if k:
        _g += 1; print(f"  [GECTI] {m}")
    else:
        _k += 1; print(f"  [KALDI] {m}")


async def run():
    import server
    from core.auth import create_access_token
    from core.db import db
    from core.zaman import simdi
    from httpx import AsyncClient, ASGITransport

    await server.client.drop_database(TEST_DB)
    a = str(uuid.uuid4()); b = str(uuid.uuid4())
    await db.users.insert_one({"id": a, "role": "teacher", "ad": "Melek", "soyad": "Aygün"})
    await db.users.insert_one({"id": b, "role": "accountant", "ad": "Muh", "soyad": "Ase"})
    Ha = {"Authorization": f"Bearer {create_access_token({'sub': a})}"}
    Hb = {"Authorization": f"Bearer {create_access_token({'sub': b})}"}
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 60
    exe = b"MZ" + b"\x00" * 60

    async with AsyncClient(transport=ASGITransport(app=server.app), base_url="http://test") as ac:
        # Ek: geçerli PNG
        r = await ac.post("/api/mesajlar/ek-yukle", headers=Ha, files={"dosya": ("ss.png", png, "image/png")})
        check(r.status_code == 200 and r.json()["tur"] == "gorsel", "PNG ek yüklendi (görsel)")
        ek = r.json()
        # Yasak uzantı + sahte MIME reddi
        check((await ac.post("/api/mesajlar/ek-yukle", headers=Ha, files={"dosya": ("v.exe", exe, "x")})).status_code == 422, ".exe reddedildi")
        check((await ac.post("/api/mesajlar/ek-yukle", headers=Ha, files={"dosya": ("f.png", exe, "image/png")})).status_code == 422, "sahte png (magic) reddedildi")

        # Ekli mesaj (Melek → Muhasebe)
        r = await ac.post("/api/mesajlar", headers=Ha, json={"alici_id": b, "konu": "Ödeme", "icerik": "Ekli", "ekler": [ek]})
        mid = r.json()["id"]
        check(len(r.json().get("ekler", [])) == 1, "mesaj eki bağlandı")
        # Alıcı rol-görünen-ad: Muhasebe, gönderen Melek Aygün görür
        check(r.json().get("gonderen_ad") == "Melek Aygün", "gönderen adı korunuyor (Melek Aygün)")

        # Alıcı eki indirir; 3. kişi indiremez
        check((await ac.get(f"/api/mesajlar/ek/{ek['dosya_id']}", headers=Hb)).status_code == 200, "alıcı eki indirdi")
        c = str(uuid.uuid4()); await db.users.insert_one({"id": c, "role": "teacher"})
        Hc = {"Authorization": f"Bearer {create_access_token({'sub': c})}"}
        check((await ac.get(f"/api/mesajlar/ek/{ek['dosya_id']}", headers=Hc)).status_code == 403, "yabancı ek erişimi 403")

        # Yıldız
        r = await ac.put(f"/api/mesajlar/{mid}/yildiz", headers=Hb, json={"yildiz": True})
        check(r.status_code == 200 and r.json()["yildiz"], "yıldızlandı")
        r = await ac.put(f"/api/mesajlar/{mid}/yildiz", headers=Hb, json={"yildiz": False})
        check(r.json()["yildiz"] is False, "yıldız kaldırıldı")

        # Ertele (gelecek) → gelen kutusundan gizli, ertelenenler listesinde
        gelecek = (simdi() + timedelta(hours=3)).isoformat()
        r = await ac.put(f"/api/mesajlar/{mid}/ertele", headers=Hb, json={"ertele_zaman": gelecek})
        check(r.status_code == 200 and r.json()["ertele_zaman"], "mesaj ertelendi")
        m = await db.mesajlar.find_one({"id": mid})
        check(m.get("ertele_zaman") == gelecek and m.get("ertele_bildirildi") is False, "erteleme kaydı + bildirim bayrağı sıfır")

        # Ertele değiştir → geçmiş zaman → hatırlatma
        gecmis = (simdi() - timedelta(minutes=5)).isoformat()
        await ac.put(f"/api/mesajlar/{mid}/ertele", headers=Hb, json={"ertele_zaman": gecmis})
        await ac.get("/api/mesajlar", headers=Hb)   # aktifken kontrol → hatırlatma tetiklenir
        bil = await db.bildirimler.count_documents({"alici_id": b, "tur": "mesaj_ertelendi"})
        check(bil == 1, f"erteleme hatırlatma bildirimi oluştu ({bil})")
        m = await db.mesajlar.find_one({"id": mid})
        check(m.get("ertele_bildirildi") is True, "hatırlatma bir kez gönderildi (bayrak set)")

        # Ertelemeyi iptal
        r = await ac.put(f"/api/mesajlar/{mid}/ertele", headers=Hb, json={"ertele_zaman": None})
        check(r.status_code == 200 and r.json()["ertele_zaman"] is None, "erteleme iptal edildi")

        # Yanıt: Muhasebe → Melek (aynı thread, ekli yanıt)
        r = await ac.post("/api/mesajlar/ek-yukle", headers=Hb, files={"dosya": ("belge.pdf", b"%PDF-1.4 test", "application/pdf")})
        ek2 = r.json()
        check(r.status_code == 200 and ek2["tur"] == "belge", "PDF ek (belge) yüklendi")
        r = await ac.post("/api/mesajlar", headers=Hb, json={"alici_id": a, "konu": "Re: Ödeme", "icerik": "Aldım", "ekler": [ek2]})
        check(r.status_code == 200 and r.json()["alici_id"] == a, "yanıt aynı thread'e (Muhasebe→Melek)")

    await server.client.drop_database(TEST_DB)


def main():
    asyncio.run(run())
    print(f"\nSONUC: {_g}/{_g + _k} kontrol gecti")
    sys.exit(0 if _k == 0 else 1)


if __name__ == "__main__":
    main()
