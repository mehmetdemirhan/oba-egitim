"""FAZ 4 rozet uçtan uca (E2E) smoke testi — 4 rol tam senaryo.

Akış:
  1. Öğrenci HTTP ile okuma kaydı ekler → EVENT tetiklenir → rozet otomatik
     verilir → 'rozet_kazandi' bildirimi düşer (fire-and-forget, poll ile beklenir)
  2. Veli çocuğunun rozet vitrinini görür (GET /rozet/ogrenci/{id})
  3. Admin yeni rozet oluşturur (manuel)
  4. Admin manuel ver → geri al
  5. Admin siler (kazananları temizleme seçeneği)

    cd appbackend
    .venv/Scripts/python.exe tests/test_rozet_e2e_smoke.py
"""
import asyncio
import os
import sys
import uuid

TEST_DB = "oba_test_rozet_e2e_smoke"
os.environ["MONGO_URL"] = os.environ.get("MONGO_URL_TEST", "mongodb://localhost:27017")
os.environ["DB_NAME"] = TEST_DB
os.environ.setdefault("SECRET_KEY", "test-secret-key")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_gecen = 0
_kalan = 0


def check(kosul, mesaj):
    global _gecen, _kalan
    if kosul:
        _gecen += 1
        print(f"  [GECTI] {mesaj}")
    else:
        _kalan += 1
        print(f"  [KALDI] {mesaj}")


async def _poll(coro_fn, kosul_fn, timeout=3.0, aralik=0.1):
    """Fire-and-forget event'in tamamlanmasını bekler."""
    import time
    gecti = 0.0
    while gecti < timeout:
        deger = await coro_fn()
        if kosul_fn(deger):
            return deger
        await asyncio.sleep(aralik)
        gecti += aralik
    return await coro_fn()


async def run():
    import server
    from core.auth import create_access_token
    from core.db import ensure_indexes
    from httpx import AsyncClient, ASGITransport

    await server.client.drop_database(TEST_DB)
    await ensure_indexes()

    # Roller
    adm = str(uuid.uuid4())
    stu_u, stu_s = str(uuid.uuid4()), str(uuid.uuid4())  # öğrenci user + student kaydı
    veli = str(uuid.uuid4())
    await server.db.users.insert_one({"id": adm, "ad": "Admin", "soyad": "Y", "role": "admin"})
    await server.db.users.insert_one({"id": stu_u, "ad": "Ali", "soyad": "Y", "role": "student", "linked_id": stu_s})
    await server.db.students.insert_one({"id": stu_s, "ad": "Ali", "soyad": "Y", "toplam_xp": 0})
    await server.db.users.insert_one({"id": veli, "ad": "Veli", "soyad": "Y", "role": "parent", "linked_id": stu_s})

    HA = {"Authorization": f"Bearer {create_access_token({'sub': adm})}"}
    HS = {"Authorization": f"Bearer {create_access_token({'sub': stu_u})}"}
    HV = {"Authorization": f"Bearer {create_access_token({'sub': veli})}"}

    transport = ASGITransport(app=server.app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # ── 1. Öğrenci okuma kaydı → EVENT → otomatik rozet ──
        r = await ac.post("/api/reading-logs", json={"kitap_adi": "Küçük Prens", "sure_dakika": 120}, headers=HS)
        check(r.status_code == 200, f"okuma kaydı oluşturuldu (status={r.status_code})")

        kazanimlar = await _poll(
            lambda: server.db.kazanilan_rozetler.find({"kullanici_id": stu_u}).to_list(length=None),
            lambda lst: len(lst) >= 2)
        kodlar = {k["rozet_kodu"] for k in kazanimlar}
        check(len(kazanimlar) >= 2, f"EVENT ile otomatik rozet verildi ({len(kazanimlar)} rozet: {kodlar})")
        check("okuma_ilk" in kodlar and "okuma_100" in kodlar, "okuma_ilk + okuma_100 otomatik kazanıldı")

        bild = await _poll(
            lambda: server.db.bildirimler.count_documents({"alici_id": stu_u, "tur": "rozet_kazandi"}),
            lambda n: n >= 2)
        check(bild >= 2, f"rozet_kazandi bildirimleri düştü ({bild})")

        # ── 2. Veli çocuğun rozetlerini görür ──
        r = await ac.get(f"/api/rozet/ogrenci/{stu_s}", headers=HV)
        check(r.status_code == 200, f"veli GET /rozet/ogrenci 200 (status={r.status_code})")
        vd = r.json()
        veli_kodlar = {k["rozet_kodu"] for k in vd.get("kazanilanlar", [])}
        check("okuma_ilk" in veli_kodlar, "veli çocuğun kazandığı rozetleri görüyor")
        check(vd.get("toplam", 0) > 0 and len(vd.get("tanimlar", [])) > 0, "veli tanım + kazanım listesi dolu")

        # ── 3. Admin yeni (manuel) rozet oluşturur ──
        yeni = {"kod": "e2e_ozel", "rol": "student", "ad": "E2E Özel Ödül", "ikon": "🎖️",
                "seviye": "altin", "odul_puan": 10, "kosul": {"metrik": "manuel"}}
        r = await ac.post("/api/rozet/tanim", json=yeni, headers=HA)
        check(r.status_code == 200, f"admin manuel rozet oluşturdu (status={r.status_code})")

        # ── 4. Admin manuel ver → geri al ──
        r = await ac.post("/api/rozet/student/e2e_ozel/ver", json={"user_id": stu_u}, headers=HA)
        check(r.status_code == 200 and r.json()["ok"], "admin manuel ver 200")
        var = await server.db.kazanilan_rozetler.count_documents({"kullanici_id": stu_u, "rozet_kodu": "e2e_ozel"})
        check(var == 1, "manuel verilen rozet kazanımlarda")
        r = await ac.post("/api/rozet/student/e2e_ozel/geri-al", json={"user_id": stu_u}, headers=HA)
        check(r.status_code == 200 and r.json()["silindi"], "geri al çalıştı")
        var2 = await server.db.kazanilan_rozetler.count_documents({"kullanici_id": stu_u, "rozet_kodu": "e2e_ozel"})
        check(var2 == 0, "geri alınan rozet kazanımlardan çıktı")

        # ── 5. Admin siler (kazananları temizle) ──
        await ac.post("/api/rozet/student/e2e_ozel/ver", json={"user_id": stu_u}, headers=HA)
        r = await ac.request("DELETE", "/api/rozet/student/e2e_ozel", json={"kazananlari_koru": False}, headers=HA)
        check(r.status_code == 200 and r.json()["silinen_kazanim"] == 1, f"sil + kazanımları temizle (gelen {r.json()})")
        r = await ac.get("/api/rozet/student/e2e_ozel")
        check(r.status_code == 404, "silinen rozet artık yok")

    await server.client.drop_database(TEST_DB)
    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    return _kalan == 0


if __name__ == "__main__":
    ok = asyncio.run(run())
    sys.exit(0 if ok else 1)
