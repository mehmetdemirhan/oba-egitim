"""Kur süresi gecikme uyarısı (35 gün) — smoke testi (İŞ 2).

Doğrular: aktif + başlangıcı 35 günü aşan kur "geciken" listede; ≤35 gün ve
tamamlanmış kurlar listede değil; ilk taramada öğretmen+admin+accountant'a bildirim;
haftalık cooldown (son_uyari<7 gün → tekrar bildirim yok, ≥7 gün → hatırlatma);
liste ucu admin+accountant'a açık, öğretmen 403.
İzole DB (oba_test_kur_gecikme). Gerçek DB'ye dokunmaz.
"""
import asyncio
import os
import sys
from datetime import datetime, timezone, timedelta

TEST_DB = "oba_test_kur_gecikme"
os.environ["MONGO_URL"] = os.environ.get("MONGO_URL_TEST", "mongodb://localhost:27017")
os.environ["DB_NAME"] = TEST_DB
os.environ.setdefault("SECRET_KEY", "test-secret-key")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_gecen = _kalan = 0


def check(kosul, mesaj):
    global _gecen, _kalan
    if kosul:
        _gecen += 1; print(f"  [GECTI] {mesaj}")
    else:
        _kalan += 1; print(f"  [KALDI] {mesaj}")


async def run():
    import uuid
    import server
    from core.auth import create_access_token
    from httpx import AsyncClient, ASGITransport

    await server.client.drop_database(TEST_DB)
    admin_id, acc_id, uT, tA = (str(uuid.uuid4()) for _ in range(4))
    await server.db.users.insert_many([
        {"id": admin_id, "ad": "Yön", "soyad": "E", "role": "admin"},
        {"id": acc_id, "ad": "Muh", "soyad": "A", "role": "accountant"},
        {"id": uT, "ad": "Öğr", "soyad": "A", "role": "teacher", "linked_id": tA},
    ])
    sid = str(uuid.uuid4())
    await server.db.students.insert_one({"id": sid, "ad": "Ali", "soyad": "V", "ogretmen_id": tA})

    simdi = datetime.now(timezone.utc)
    esik_asan = (simdi - timedelta(days=40)).isoformat()
    yeni = (simdi - timedelta(days=10)).isoformat()
    await server.db.kur_ucretleri.insert_many([
        {"id": "kold", "ogrenci_id": sid, "kur_adi": "2", "durum": "acik", "baslangic_tarihi": esik_asan},   # GECİKEN
        {"id": "knew", "ogrenci_id": sid, "kur_adi": "3", "durum": "acik", "baslangic_tarihi": yeni},          # taze
        {"id": "kdone", "ogrenci_id": sid, "kur_adi": "1", "durum": "tamamlandi", "baslangic_tarihi": esik_asan},  # kapalı
    ])

    H_admin = {"Authorization": f"Bearer {create_access_token({'sub': admin_id})}"}
    H_acc = {"Authorization": f"Bearer {create_access_token({'sub': acc_id})}"}
    H_t = {"Authorization": f"Bearer {create_access_token({'sub': uT})}"}

    async def throttle_sil():
        await server.db.sistem_ayarlari.delete_one({"tip": "gecikme_son_kontrol"})

    async def gecikme_bildirim_sayisi():
        return await server.db.bildirimler.count_documents({"tur": "kur_gecikme", "ilgili_id": "kold"})

    transport = ASGITransport(app=server.app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # ── Liste: yalnız geciken (kold) ──
        r = await ac.get("/api/muhasebe/geciken-kurlar", headers=H_acc)
        check(r.status_code == 200, f"geciken-kurlar 200 ({r.status_code})")
        kurlar = r.json().get("kurlar", [])
        idler = sorted(k["kur_ucreti_id"] for k in kurlar)
        check(idler == ["kold"], f"yalnız geciken kur (kold) — {idler}")
        check(r.json().get("sayi") == 1 and kurlar[0]["gun"] >= 39, f"sayi=1, gün≈40 ({kurlar[0]['gun'] if kurlar else '-'})")

        # ── İlk taramada bildirim: öğretmen + admin + accountant (3) ──
        check(await gecikme_bildirim_sayisi() == 3, f"3 alıcıya gecikme bildirimi (öğretmen+admin+accountant)")
        for aid, kim in ((uT, "öğretmen"), (admin_id, "admin"), (acc_id, "accountant")):
            n = await server.db.bildirimler.count_documents({"alici_id": aid, "tur": "kur_gecikme"})
            check(n == 1, f"{kim} bildirimi aldı")

        # ── Haftalık cooldown: son_uyari taze → tekrar taramada bildirim YOK ──
        await throttle_sil()
        await ac.get("/api/muhasebe/geciken-kurlar", headers=H_acc)
        check(await gecikme_bildirim_sayisi() == 3, "cooldown içinde tekrar bildirim yok (hâlâ 3)")

        # ── 8 gün önce uyarıldıysa → hatırlatma (yeni bildirim) ──
        await server.db.kur_ucretleri.update_one({"id": "kold"},
            {"$set": {"son_uyari_tarihi": (simdi - timedelta(days=8)).isoformat()}})
        await throttle_sil()
        await ac.get("/api/muhasebe/geciken-kurlar", headers=H_acc)
        check(await gecikme_bildirim_sayisi() == 6, f"7+ gün sonra hatırlatma gönderildi (6)")

        # ── Yetki: öğretmen listeyi göremez (403) ──
        check((await ac.get("/api/muhasebe/geciken-kurlar", headers=H_t)).status_code == 403,
              "öğretmen geciken-kurlar listesini göremez (403)")

    await server.client.drop_database(TEST_DB)


if __name__ == "__main__":
    asyncio.run(run())
    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    sys.exit(1 if _kalan else 0)
