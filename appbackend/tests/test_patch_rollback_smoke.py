"""Faz 4 — otomatik rollback smoke testi.

Bozuk bir GÜNCELLEME (import edilemeyen v2) yüklenince sistem otomatik olarak
önceki çalışan sürüme (v1) döner; modül bozulmaz. Yeni kurulumda hata olursa
dosyalar tamamen kaldırılır.
    cd appbackend
    .venv/Scripts/python.exe tests/test_patch_rollback_smoke.py
"""
import importlib
import io
import json
import os
import shutil
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "oba_test_patch_rb")
os.environ.setdefault("SECRET_KEY", "test-secret-key")

AD = "test_rb_yama"
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


def zip_ile(ad, ver, py):
    manifest = {"name": ad, "version": ver, "description": "t", "author": "T",
                "type": "backend", "core": False}
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", json.dumps(manifest))
        zf.writestr(f"{ad}.py", py)
    return buf.getvalue()


def main():
    from core import patch_manager as pm

    def temizle():
        for p in [pm.MODULES_DIR / f"{AD}.py", pm.MANIFESTS_DIR / f"{AD}.json",
                  pm.MODULES_DIR / "test_rb_yeni.py", pm.MANIFESTS_DIR / "test_rb_yeni.json"]:
            try:
                p.unlink()
            except FileNotFoundError:
                pass
        shutil.rmtree(pm.VERSIONS_DIR / AD, ignore_errors=True)

    temizle()
    try:
        # v1 — sağlam
        iyi = ("VERSION = '1.0.0'\nfrom fastapi import APIRouter\nrouter = APIRouter()\n"
               "@router.get('/test-rb/ping')\nasync def ping():\n    return {'v': VERSION}\n")
        r = pm.install_patch(zip_ile(AD, "1.0.0", iyi))
        check(r["ok"], "v1.0.0 (sağlam) kuruldu")

        # v2 — güvenli ama import edilemez (modül düzeyinde NameError)
        bozuk = ("VERSION = '2.0.0'\nfrom fastapi import APIRouter\nrouter = APIRouter()\n"
                 "BOZUK_REFERANS_xyz + 1\n")
        r = pm.install_patch(zip_ile(AD, "2.0.0", bozuk))
        check(not r["ok"], "bozuk v2.0.0 reddedildi (ok=False)")
        check(r.get("rolled_back") is True, "otomatik rollback tetiklendi")

        # canlı dosya v1.0.0'a döndü mü
        live = (pm.MODULES_DIR / f"{AD}.py").read_text(encoding="utf-8")
        check("VERSION = '1.0.0'" in live, "canlı dosya v1.0.0'a geri döndü")
        man = pm.manifest_oku(AD)
        check(man and man.get("version") == "1.0.0", "manifest v1.0.0")

        # modül gerçekten import edilebiliyor (bozulmadı)
        importlib.invalidate_caches()
        mod = "modules." + AD
        if mod in sys.modules:
            importlib.reload(sys.modules[mod])
            m = sys.modules[mod]
        else:
            m = importlib.import_module(mod)
        check(getattr(m, "VERSION", None) == "1.0.0", "import edilen modül VERSION=1.0.0")

        # YENİ kurulum hatası → dosya kalmaz
        r = pm.install_patch(zip_ile("test_rb_yeni", "1.0.0",
                                     "from fastapi import APIRouter\nrouter=APIRouter()\nYINE_BOZUK_abc\n"))
        check(not r["ok"], "bozuk YENİ modül reddedildi")
        check(not (pm.MODULES_DIR / "test_rb_yeni.py").exists(), "bozuk yeni modül diske kalmadı")
    finally:
        temizle()

    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    sys.exit(0 if _kalan == 0 else 1)


if __name__ == "__main__":
    main()
