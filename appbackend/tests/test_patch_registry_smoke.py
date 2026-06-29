"""Faz 6 — registry/dinamik loader: liste + toggle + core-koruma + pasif-exclude + delete.

registry.json'u yedekleyip test sonunda geri yükler (kalıcı değişiklik yapmaz).
    cd appbackend
    .venv/Scripts/python.exe tests/test_patch_registry_smoke.py
"""
import io
import json
import os
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "oba_test_patch_reg")
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


def main():
    import asyncio
    # Modül importları (core.db GridFS) bir event loop ister — kur.
    asyncio.set_event_loop(asyncio.new_event_loop())
    from core import registry, patch_manager as pm
    from fastapi import APIRouter

    yedek = registry.REGISTRY_PATH.read_text(encoding="utf-8")  # geri yükleme için
    TEMP = "test_reg_yama"

    def temizle():
        for p in [pm.MODULES_DIR / f"{TEMP}.py", pm.MANIFESTS_DIR / f"{TEMP}.json"]:
            try:
                p.unlink()
            except FileNotFoundError:
                pass

    try:
        # liste
        mods = pm.list_modules()
        adlar = {m["name"] for m in mods}
        check(len(mods) >= 31, f"list_modules ≥31 modül ({len(mods)})")
        check("yedekleme" in adlar and "risk" in adlar, "bilinen modüller listede")
        yed = next(m for m in mods if m["name"] == "yedekleme")
        risk = next(m for m in mods if m["name"] == "risk")
        check(yed["core"] is True, "yedekleme core=True")
        check(risk["core"] is False, "risk core=False")

        # core kapatılamaz
        try:
            registry.set_active("yedekleme", False)
            check(False, "core modül kapatma engellendi")
        except ValueError:
            check(True, "core modül (yedekleme) kapatılamadı (ValueError)")

        # pasif exclude: risk'i kapat → register_routers'ta risk route'ları yok
        def routes_for(name_substr):
            ar = APIRouter(prefix="/api")
            registry.register_routers(ar)
            return [r.path for r in ar.routes if name_substr in r.path]

        check(len(routes_for("/risk-skor")) > 0, "risk aktifken route'ları var")
        registry.set_active("risk", False)
        check(registry.is_active("risk") is False, "risk pasife alındı")
        check(len(routes_for("/risk-skor")) == 0, "risk pasifken route'ları YOK (exclude)")
        registry.set_active("risk", True)
        check(len(routes_for("/risk-skor")) > 0, "risk tekrar aktif → route'lar geri geldi")

        # delete: geçici modül kur, sil
        manifest = {"name": TEMP, "version": "1.0.0", "description": "t", "author": "T",
                    "type": "backend", "core": False}
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("manifest.json", json.dumps(manifest))
            zf.writestr(f"{TEMP}.py", "from fastapi import APIRouter\nrouter=APIRouter()\n")
        r = pm.install_patch(buf.getvalue())
        check(r["ok"], "geçici modül kuruldu")
        check(registry.is_active(TEMP), "geçici modül registry'de")
        d = pm.delete_module(TEMP)
        check(d["ok"], "modül silindi")
        check(not (pm.MODULES_DIR / f"{TEMP}.py").exists(), "dosya silindi")
        check(TEMP not in {e["name"] for e in registry.load_registry()}, "registry'den çıktı")

        # core silinemez
        d = pm.delete_module("yedekleme")
        check(not d["ok"], "core modül (yedekleme) silinemedi")
    finally:
        registry.REGISTRY_PATH.write_text(yedek, encoding="utf-8")  # geri yükle
        temizle()

    print(f"\nSONUC: {_gecen}/{_gecen + _kalan} kontrol gecti")
    sys.exit(0 if _kalan == 0 else 1)


if __name__ == "__main__":
    main()
