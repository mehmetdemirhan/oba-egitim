"""Faz 1 — Modül Yöneticisi temel smoke testi.

Bellekte bir ZIP yama oluşturur, /admin/moduller/yukle ile yükler, dosyanın
modules/'a indiğini ve listede göründüğünü doğrular. Admin-dışı 403 alır.
Test sonunda oluşturduğu dosyaları temizler. Gerçek dosya sistemine yazar
(yama sistemi dosya tabanlı) ama yalnızca 'test_ornek_yama' adlı modülü kullanır.
    cd appbackend
    .venv/Scripts/python.exe tests/test_patch_smoke.py
"""
import asyncio
import io
import json
import os
import sys
import uuid
import zipfile

TEST_DB = "oba_test_patch_smoke"
os.environ["MONGO_URL"] = os.environ.get("MONGO_URL_TEST", "mongodb://localhost:27017")
os.environ["DB_NAME"] = TEST_DB
os.environ.setdefault("SECRET_KEY", "test-secret-key")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

MODUL_ADI = "test_ornek_yama"
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


def ornek_zip() -> bytes:
    manifest = {
        "name": MODUL_ADI,
        "version": "1.0.0",
        "description": "Faz 1 smoke için örnek yama modülü.",
        "author": "Test",
        "type": "backend",
        "core": False,
    }
    py = (
        "from fastapi import APIRouter\n"
        "router = APIRouter()\n\n"
        "@router.get('/test-ornek-yama/ping')\n"
        "async def ping():\n"
        "    return {'pong': True}\n"
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False))
        zf.writestr(f"{MODUL_ADI}.py", py)
    return buf.getvalue()


def temizle():
    from core import patch_manager as pm
    from core import registry
    for p in [pm.MODULES_DIR / f"{MODUL_ADI}.py", pm.MANIFESTS_DIR / f"{MODUL_ADI}.json"]:
        try:
            p.unlink()
        except FileNotFoundError:
            pass
    registry.remove_module(MODUL_ADI)


async def run():
    import server
    from core.auth import create_access_token
    from core import patch_manager as pm
    from httpx import AsyncClient, ASGITransport

    await server.client.drop_database(TEST_DB)
    temizle()

    admin_id = str(uuid.uuid4())
    ogr_id = str(uuid.uuid4())
    await server.db.users.insert_one({"id": admin_id, "ad": "A", "soyad": "B", "role": "admin"})
    await server.db.users.insert_one({"id": ogr_id, "ad": "O", "soyad": "G", "role": "student"})
    H = {"Authorization": f"Bearer {create_access_token({'sub': admin_id})}"}
    H_ogr = {"Authorization": f"Bearer {create_access_token({'sub': ogr_id})}"}

    zip_bytes = ornek_zip()
    transport = ASGITransport(app=server.app)
    async with AsyncClient(transport=transport, base_url="http://test", timeout=30.0) as ac:
        # Admin-dışı 403
        r = await ac.post("/api/admin/moduller/yukle",
                          files={"dosya": ("y.zip", zip_bytes, "application/zip")}, headers=H_ogr)
        check(r.status_code == 403, f"öğrenci yükleme 403 aldı (status={r.status_code})")

        # Admin yükleme
        r = await ac.post("/api/admin/moduller/yukle",
                          files={"dosya": ("y.zip", zip_bytes, "application/zip")}, headers=H)
        check(r.status_code == 200, f"admin yükleme 200 (status={r.status_code}) :: {r.text[:200]}")
        body = r.json()
        check(body.get("name") == MODUL_ADI, "yanıt modül adını içeriyor")
        check("restart_uyarisi" in body, "restart uyarısı dönüyor")

        # Dosya modules/'a indi mi
        check((pm.MODULES_DIR / f"{MODUL_ADI}.py").exists(), "modül .py dosyası modules/'a indi")
        check((pm.MANIFESTS_DIR / f"{MODUL_ADI}.json").exists(), "manifest manifests/'e kaydedildi")

        # Liste
        r = await ac.get("/api/admin/moduller", headers=H)
        check(r.status_code == 200, "modül listesi 200")
        adlar = [m["name"] for m in r.json()]
        check(MODUL_ADI in adlar, "yüklenen modül listede görünüyor")

        # Manifest oku → yerleşen dosya kaydı
        man = pm.manifest_oku(MODUL_ADI)
        check(man and man.get("backend_files") == [f"{MODUL_ADI}.py"], "manifest backend_files doğru")

        # manifest.json olmayan zip reddedilmeli
        bad = io.BytesIO()
        with zipfile.ZipFile(bad, "w") as zf:
            zf.writestr("rastgele.py", "x = 1\n")
        r = await ac.post("/api/admin/moduller/yukle",
                          files={"dosya": ("bad.zip", bad.getvalue(), "application/zip")}, headers=H)
        check(r.status_code == 400, "manifest'siz zip 400 ile reddedildi")

    temizle()
    await server.client.drop_database(TEST_DB)


def main():
    try:
        asyncio.run(run())
    finally:
        temizle()
    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    sys.exit(0 if _kalan == 0 else 1)


if __name__ == "__main__":
    main()
