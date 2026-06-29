"""Faz 2 — yama güvenlik (AST) + import kontrolü smoke testi.

Tehlikeli kod içeren ZIP reddedilir ve diske YAZILMAZ. Syntax/import hatalı
modül reddedilir ve geri alınır. Uyarı (httpx) içeren modül kurulur.
    cd appbackend
    .venv/Scripts/python.exe tests/test_patch_security_smoke.py
"""
import io
import json
import os
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "oba_test_patch_sec")
os.environ.setdefault("SECRET_KEY", "test-secret-key")

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


def zip_ile(ad, py_kod, manifest_extra=None):
    manifest = {"name": ad, "version": "1.0.0", "description": "test",
                "author": "T", "type": "backend", "core": False}
    if manifest_extra:
        manifest.update(manifest_extra)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", json.dumps(manifest))
        zf.writestr(f"{ad}.py", py_kod)
    return buf.getvalue()


def main():
    from core import patch_manager as pm
    from core import patch_security as ps

    adlar = ["test_sec_dangerous", "test_sec_syntax", "test_sec_import",
             "test_sec_warn", "test_sec_ok"]

    def temizle():
        for a in adlar:
            for p in [pm.MODULES_DIR / f"{a}.py", pm.MANIFESTS_DIR / f"{a}.json"]:
                try:
                    p.unlink()
                except FileNotFoundError:
                    pass

    temizle()
    try:
        # 1) os.system + eval + subprocess → güvenlik HATASI, dosya YAZILMAZ
        kod = ("import os, subprocess\n"
               "from fastapi import APIRouter\nrouter = APIRouter()\n"
               "def x():\n    os.system('ls')\n    eval('1+1')\n    subprocess.run(['ls'])\n")
        sc = ps.scan_python_source(kod)
        check(len(sc["errors"]) >= 3, f"AST: 3+ tehlike yakalandı ({len(sc['errors'])})")
        r = pm.install_patch(zip_ile("test_sec_dangerous", kod))
        check(not r["ok"] and any("Güvenlik" in e for e in r["errors"]), "tehlikeli zip reddedildi")
        check(not (pm.MODULES_DIR / "test_sec_dangerous.py").exists(), "tehlikeli dosya diske YAZILMADI")

        # 2) os.remove / shutil.rmtree → HATA
        kod2 = "import os, shutil\nos.remove('a')\nshutil.rmtree('b')\n"
        sc2 = ps.scan_python_source(kod2)
        check(len(sc2["errors"]) >= 2, "AST: dosya silme yakalandı")

        # 3) network (socket/urllib) → HATA
        kod3 = "import socket\nimport urllib.request\n"
        sc3 = ps.scan_python_source(kod3)
        check(len(sc3["errors"]) >= 2, "AST: ağ importları yakalandı")

        # 4) syntax hatası → reddedilir
        r = pm.install_patch(zip_ile("test_sec_syntax", "def broken(:\n  pass\n"))
        check(not r["ok"], "syntax hatalı zip reddedildi")
        check(not (pm.MODULES_DIR / "test_sec_syntax.py").exists(), "syntax hatalı dosya yok")

        # 5) güvenli ama import edilemeyen (NameError) → import check reddeder + geri alır
        kod5 = "from fastapi import APIRouter\nrouter = APIRouter()\nYOK_DEGISKEN_xyz\n"
        r = pm.install_patch(zip_ile("test_sec_import", kod5))
        check(not r["ok"] and any("Import" in e for e in r["errors"]), "import hatalı zip reddedildi")
        check(not (pm.MODULES_DIR / "test_sec_import.py").exists(), "import hatalı dosya geri alındı")

        # 6) __init__.py hedefi → reddedilir
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("manifest.json", json.dumps({"name": "test_sec_init", "version": "1.0.0",
                        "description": "t", "author": "T", "type": "backend"}))
            zf.writestr("__init__.py", "x=1\n")
        r = pm.install_patch(buf.getvalue())
        check(not r["ok"], "__init__.py içeren zip reddedildi")

        # 7) httpx importu → UYARI ama kurulur
        kod7 = "import httpx\nfrom fastapi import APIRouter\nrouter = APIRouter()\n"
        r = pm.install_patch(zip_ile("test_sec_warn", kod7))
        check(r["ok"], "httpx'li modül kuruldu (uyarıyla)")
        check(any("httpx" in w for w in r["warnings"]), "httpx uyarısı raporlandı")

        # 8) tamamen temiz modül → kurulur, uyarısız
        kod8 = "from fastapi import APIRouter\nrouter = APIRouter()\n@router.get('/x')\nasync def x():\n    return {}\n"
        r = pm.install_patch(zip_ile("test_sec_ok", kod8))
        check(r["ok"] and not r["warnings"], "temiz modül uyarısız kuruldu")
    finally:
        temizle()

    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    sys.exit(0 if _kalan == 0 else 1)


if __name__ == "__main__":
    main()
