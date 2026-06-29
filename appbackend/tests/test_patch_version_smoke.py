"""Faz 3 — sürüm yönetimi (arşiv + 3-rotasyon + restore) smoke testi.

Aynı modülün 5 sürümünü kurar; arşivde yalnızca son 3 önceki sürüm kalmalı,
en eski silinmeli. Ardından eski bir sürüme geri yükler ve canlı dosyanın
değiştiğini doğrular.
    cd appbackend
    .venv/Scripts/python.exe tests/test_patch_version_smoke.py
"""
import io
import json
import os
import shutil
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "oba_test_patch_ver")
os.environ.setdefault("SECRET_KEY", "test-secret-key")

AD = "test_ver_yama"
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


def zip_ver(ver):
    manifest = {"name": AD, "version": ver, "description": f"sürüm {ver}",
                "author": "T", "type": "backend", "core": False}
    py = (f"VERSION = '{ver}'\n"
          "from fastapi import APIRouter\nrouter = APIRouter()\n")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", json.dumps(manifest))
        zf.writestr(f"{AD}.py", py)
    return buf.getvalue()


def main():
    from core import patch_manager as pm

    from core import registry

    def temizle():
        for p in [pm.MODULES_DIR / f"{AD}.py", pm.MANIFESTS_DIR / f"{AD}.json"]:
            try:
                p.unlink()
            except FileNotFoundError:
                pass
        shutil.rmtree(pm.VERSIONS_DIR / AD, ignore_errors=True)
        registry.remove_module(AD)

    temizle()
    try:
        for ver in ["1.0.0", "2.0.0", "3.0.0", "4.0.0", "5.0.0"]:
            r = pm.install_patch(zip_ver(ver))
            check(r["ok"], f"v{ver} kuruldu")

        # canlı sürüm 5.0.0
        live = (pm.MODULES_DIR / f"{AD}.py").read_text(encoding="utf-8")
        check("VERSION = '5.0.0'" in live, "canlı dosya v5.0.0")

        # arşiv: 3 sürüm (2,3,4); en eski (1.0.0) silinmiş
        versions = pm.list_versions(AD)
        etiketler = [v["version"] for v in versions]
        check(len(versions) == 3, f"arşivde 3 sürüm var ({len(versions)})")
        check("1.0.0" not in etiketler, "en eski (1.0.0) rotasyonla silindi")
        check(set(etiketler) == {"2.0.0", "3.0.0", "4.0.0"}, f"arşiv = 2/3/4 ({etiketler})")
        check(not (pm.VERSIONS_DIR / AD / "1.0.0").exists(), "1.0.0 dizini diskten silindi")

        # geri yükle → 3.0.0
        r = pm.restore_version(AD, "3.0.0")
        check(r["ok"], f"3.0.0'a geri yüklendi :: {r.get('errors')}")
        live = (pm.MODULES_DIR / f"{AD}.py").read_text(encoding="utf-8")
        check("VERSION = '3.0.0'" in live, "canlı dosya artık v3.0.0")
        man = pm.manifest_oku(AD)
        check(man and man.get("version") == "3.0.0", "manifest v3.0.0'a döndü")

        # olmayan sürüm
        r = pm.restore_version(AD, "9.9.9")
        check(not r["ok"], "olmayan sürüm geri yükleme reddedildi")
    finally:
        temizle()

    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    sys.exit(0 if _kalan == 0 else 1)


if __name__ == "__main__":
    main()
