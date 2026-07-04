"""Tema uçtan uca (E2E) smoke testi — çözümleme zinciri + logo + backward-compat.

    cd appbackend
    .venv/Scripts/python.exe tests/test_tema_e2e_smoke.py
"""
import asyncio
import os
import sys
import uuid
from pathlib import Path

TEST_DB = "oba_test_tema_e2e_smoke"
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
    import server
    from core.auth import create_access_token
    from core.db import ensure_indexes
    from core.tema_varsayilan import TEMALAR
    from httpx import AsyncClient, ASGITransport

    await server.client.drop_database(TEST_DB)
    await ensure_indexes()
    for t in TEMALAR:
        await server.db.theme_configs.insert_one({**t})

    adm, stu = str(uuid.uuid4()), str(uuid.uuid4())
    await server.db.users.insert_one({"id": adm, "role": "admin"})
    await server.db.users.insert_one({"id": stu, "role": "student", "linked_id": str(uuid.uuid4())})
    HA = {"Authorization": f"Bearer {create_access_token({'sub': adm})}"}
    HS = {"Authorization": f"Bearer {create_access_token({'sub': stu})}"}

    yuklenen_logo = None
    transport = ASGITransport(app=server.app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1) Öğrenci: rol varsayılanı cream, tokenlar dolu
        r = await ac.get("/api/tema/aktif", headers=HS)
        d = r.json()
        check(d["tema"]["kod"] == "ogrenci_cream", "öğrenci → ogrenci_cream (rol default)")
        light = d["tema"]["modlar"]["light"]
        check(all(k in light for k in ["primary", "surface", "text", "background", "border"]), "cream tokenları tam")

        # 2) Admin sistem temasını orman yapar
        r = await ac.post("/api/tema/aktif-yap/orman", headers=HA)
        check(r.status_code == 200, "admin sistem tema = orman")

        # 3) Öğrenci hâlâ cream (rol default sistemi override eder)
        r = await ac.get("/api/tema/aktif", headers=HS)
        check(r.json()["tema"]["kod"] == "ogrenci_cream", "öğrenci rol-default > sistem (cream korunur)")

        # 4) Öğrenci kendi tercihini gece_yarisi/dark yapar
        r = await ac.post("/api/tema/kullanici/tercih", json={"tema_kodu": "gece_yarisi", "mod": "dark"}, headers=HS)
        check(r.status_code == 200, "öğrenci tercih kaydetti")
        r = await ac.get("/api/tema/aktif", headers=HS)
        check(r.json()["tema"]["kod"] == "gece_yarisi" and r.json()["mod"] == "dark", "kullanıcı tercihi > rol-default")
        check(r.json()["kaynak"] == "kullanici", "kaynak=kullanici")

        # 5) Logo yükleme (multipart)
        png = bytes.fromhex("89504e470d0a1a0a0000000d49484452")  # minik PNG başlığı
        r = await ac.post("/api/tema/logo", files={"dosya": ("logo.png", png, "image/png")}, headers=HA)
        check(r.status_code == 200 and r.json()["logo_url"].startswith("/uploads/logo/"), f"logo yüklendi (status={r.status_code})")
        yuklenen_logo = r.json().get("logo_url")
        ayar = await server.db.sistem_ayarlari.find_one({"tip": "tema_ayarlari"})
        check(ayar and ayar.get("logo_url") == yuklenen_logo, "logo_url tema_ayarlari'na yazıldı")

        # 6) Backward-compat: eski /ayarlar/{tip} hâlâ çalışıyor
        r = await ac.get("/api/rozet/tanim")
        check(r.status_code == 200, "diğer modüller (rozet) etkilenmedi")

    # temizlik: yüklenen logo dosyasını sil
    if yuklenen_logo:
        p = Path(__file__).resolve().parent.parent / yuklenen_logo.lstrip("/")
        try: p.unlink()
        except Exception: pass

    await server.client.drop_database(TEST_DB)
    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    return _kalan == 0


if __name__ == "__main__":
    ok = asyncio.run(run())
    sys.exit(0 if ok else 1)
