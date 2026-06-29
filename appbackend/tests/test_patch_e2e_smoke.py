"""Faz 7 — uçtan uca (manuel senaryo) HTTP yaşam döngüsü smoke testi.

Gerçek admin API üzerinden: yükle → listele → pasif/aktif → güncelle (sürüm
arşivle) → sürümler → geri yükle → sil. Ayrıca çekirdek modül koruma (400).
registry.json yedeklenir/geri yüklenir; test modülü tamamen temizlenir.
    cd appbackend
    .venv/Scripts/python.exe tests/test_patch_e2e_smoke.py
"""
import asyncio
import io
import json
import os
import shutil
import sys
import uuid
import zipfile

TEST_DB = "oba_test_patch_e2e"
os.environ["MONGO_URL"] = os.environ.get("MONGO_URL_TEST", "mongodb://localhost:27017")
os.environ["DB_NAME"] = TEST_DB
os.environ.setdefault("SECRET_KEY", "test-secret-key")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

AD = "test_e2e_yama"
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


def zip_ver(ver, saglam=True):
    manifest = {"name": AD, "version": ver, "description": f"e2e sürüm {ver}",
                "author": "E2E", "type": "backend", "core": False}
    if saglam:
        py = f"VERSION='{ver}'\nfrom fastapi import APIRouter\nrouter=APIRouter()\n"
    else:
        py = f"VERSION='{ver}'\nfrom fastapi import APIRouter\nrouter=APIRouter()\nBOZUK_xyz\n"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", json.dumps(manifest))
        zf.writestr(f"{AD}.py", py)
    return buf.getvalue()


async def run():
    import server
    from core.auth import create_access_token
    from core import patch_manager as pm, registry
    from httpx import AsyncClient, ASGITransport

    reg_yedek = registry.REGISTRY_PATH.read_text(encoding="utf-8")

    def temizle():
        for p in [pm.MODULES_DIR / f"{AD}.py", pm.MANIFESTS_DIR / f"{AD}.json"]:
            try:
                p.unlink()
            except FileNotFoundError:
                pass
        shutil.rmtree(pm.VERSIONS_DIR / AD, ignore_errors=True)

    await server.client.drop_database(TEST_DB)
    temizle()
    admin_id = str(uuid.uuid4())
    await server.db.users.insert_one({"id": admin_id, "ad": "A", "soyad": "B", "role": "admin"})
    H = {"Authorization": f"Bearer {create_access_token({'sub': admin_id})}"}

    transport = ASGITransport(app=server.app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test", timeout=30.0) as ac:
            def files(zb):
                return {"dosya": ("y.zip", zb, "application/zip")}

            # 1) yükle v1
            r = await ac.post("/api/admin/moduller/yukle", files=files(zip_ver("1.0.0")), headers=H)
            check(r.status_code == 200, f"v1 yüklendi ({r.status_code})")

            # 2) listede
            r = await ac.get("/api/admin/moduller", headers=H)
            mod = next((m for m in r.json() if m["name"] == AD), None)
            check(mod and mod["version"] == "1.0.0" and mod["active"], "modül listede, v1, aktif")

            # 3) pasif yap
            r = await ac.put(f"/api/admin/moduller/{AD}/durum", json={"active": False}, headers=H)
            check(r.status_code == 200, "pasif yapıldı")
            r = await ac.get("/api/admin/moduller", headers=H)
            check(not next(m for m in r.json() if m["name"] == AD)["active"], "liste pasif gösteriyor")

            # 4) tekrar aktif
            r = await ac.put(f"/api/admin/moduller/{AD}/durum", json={"active": True}, headers=H)
            check(r.status_code == 200, "tekrar aktif")

            # 5) güncelle v2 (arşivle)
            r = await ac.post("/api/admin/moduller/yukle", files=files(zip_ver("2.0.0")), headers=H)
            check(r.status_code == 200, "v2 güncelleme yüklendi")

            # 6) sürümler → 1.0.0 arşivde
            r = await ac.get(f"/api/admin/moduller/{AD}/versiyonlar", headers=H)
            vs = [v["version"] for v in r.json()]
            check("1.0.0" in vs, f"v1 arşivde ({vs})")

            # 7) geri yükle v1
            r = await ac.post(f"/api/admin/moduller/{AD}/geri-yukle/1.0.0", headers=H)
            check(r.status_code == 200, "1.0.0'a geri yüklendi")
            r = await ac.get("/api/admin/moduller", headers=H)
            check(next(m for m in r.json() if m["name"] == AD)["version"] == "1.0.0", "sürüm v1.0.0")

            # 8) çekirdek koruma
            r = await ac.put("/api/admin/moduller/yedekleme/durum", json={"active": False}, headers=H)
            check(r.status_code == 400, "çekirdek modül pasifleştirme 400")
            r = await ac.delete("/api/admin/moduller/yedekleme", headers=H)
            check(r.status_code == 400, "çekirdek modül silme 400")

            # 9) sil
            r = await ac.delete(f"/api/admin/moduller/{AD}", headers=H)
            check(r.status_code == 200, "modül silindi")
            r = await ac.get("/api/admin/moduller", headers=H)
            check(not any(m["name"] == AD for m in r.json()), "liste modülsüz")
    finally:
        registry.REGISTRY_PATH.write_text(reg_yedek, encoding="utf-8")
        temizle()
        await server.client.drop_database(TEST_DB)


def main():
    asyncio.run(run())
    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    sys.exit(0 if _kalan == 0 else 1)


if __name__ == "__main__":
    main()
