"""Bildirim aksiyon smoke: tümünü-oku + tekil okundu endpoint'leri.

Sorun teşhisi: "Tümünü oku" çalışıyor mu? Backend mi frontend mi?
Doğrular:
  - Okunmamış sayacı doğru.
  - PUT /bildirimler/tumunu-oku → tüm okunmamışları okundu yapar, sayaç 0.
  - PUT /bildirimler/{id}/okundu → tekil okundu.
  - Route çakışması yok (tumunu-oku, {id}/okundu ile karışmıyor).
  - Bir kullanıcının tumunu-oku'su BAŞKA kullanıcının bildirimlerini etkilemez.

İzole DB (oba_test_bildirim_aksiyon). Çalıştırma:
  cd appbackend && PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe tests/test_bildirim_aksiyon_smoke.py
"""
import asyncio
import os
import sys

TEST_DB = "oba_test_bildirim_aksiyon"
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


async def run():
    import uuid
    import server
    from core.auth import create_access_token
    from httpx import AsyncClient, ASGITransport

    await server.client.drop_database(TEST_DB)

    u1, u2 = str(uuid.uuid4()), str(uuid.uuid4())
    await server.db.users.insert_many([
        {"id": u1, "ad": "Bir", "soyad": "User", "role": "teacher"},
        {"id": u2, "ad": "Iki", "soyad": "User", "role": "teacher"},
    ])
    # u1'e 3 okunmamış + 1 okunmuş; u2'ye 2 okunmamış
    def bildirim(alici, okundu, tur="gorev_atandi", ilgili=None):
        return {"id": str(uuid.uuid4()), "alici_id": alici, "tur": tur, "baslik": "x",
                "icerik": "y", "okundu": okundu, "ilgili_id": ilgili, "tarih": "2026-07-01T00:00:00"}
    await server.db.bildirimler.insert_many([
        bildirim(u1, False), bildirim(u1, False), bildirim(u1, False, "risk_yuksek", "ogr-1"), bildirim(u1, True),
        bildirim(u2, False), bildirim(u2, False),
    ])

    H1 = {"Authorization": f"Bearer {create_access_token({'sub': u1})}"}
    H2 = {"Authorization": f"Bearer {create_access_token({'sub': u2})}"}

    transport = ASGITransport(app=server.app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Başlangıç sayaç
        r = await ac.get("/api/bildirimler/okunmamis", headers=H1)
        check(r.status_code == 200 and r.json().get("sayi") == 3, f"u1 okunmamış=3 ({r.json()})")

        # Tekil okundu
        r = await ac.get("/api/bildirimler", headers=H1)
        ilk_okunmamis = next((b for b in r.json() if not b["okundu"]), None)
        r = await ac.put(f"/api/bildirimler/{ilk_okunmamis['id']}/okundu", headers=H1)
        check(r.status_code == 200, f"tekil okundu 200 ({r.status_code})")
        r = await ac.get("/api/bildirimler/okunmamis", headers=H1)
        check(r.json().get("sayi") == 2, f"tekil sonrası okunmamış=2 ({r.json()})")

        # TÜMÜNÜ OKU — asıl teşhis
        r = await ac.put("/api/bildirimler/tumunu-oku", headers=H1)
        check(r.status_code == 200 and r.json().get("ok") is True, f"tumunu-oku 200/ok ({r.status_code} {r.text[:80]})")
        r = await ac.get("/api/bildirimler/okunmamis", headers=H1)
        check(r.json().get("sayi") == 0, f"tumunu-oku sonrası u1 okunmamış=0 ({r.json()})")

        # İzolasyon: u2 etkilenmedi
        r = await ac.get("/api/bildirimler/okunmamis", headers=H2)
        check(r.json().get("sayi") == 2, f"u2 hâlâ okunmamış=2 (izolasyon) ({r.json()})")

        # ilgili_id payload'da geliyor mu (frontend yönlendirme için şart)
        r = await ac.get("/api/bildirimler", headers=H1)
        risk = next((b for b in r.json() if b.get("tur") == "risk_yuksek"), None)
        check(risk is not None and risk.get("ilgili_id") == "ogr-1",
              f"bildirim payload'ı ilgili_id taşıyor ({risk.get('ilgili_id') if risk else None})")

    await server.client.drop_database(TEST_DB)


def main():
    asyncio.run(run())
    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    sys.exit(0 if _kalan == 0 else 1)


if __name__ == "__main__":
    main()
