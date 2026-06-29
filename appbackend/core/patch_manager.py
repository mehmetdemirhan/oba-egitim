"""Modül Yöneticisi (yama sistemi) çekirdeği — ZIP yükleme, manifest, yerleştirme.

Joomla benzeri modül yönetimi. Bir ZIP paketi:
  - manifest.json  (zorunlu)  — modül meta verisi
  - *.py           — backend dosyaları → appbackend/modules/
  - *.jsx          — frontend dosyaları → frontend/src/modules/
  - *.png / *.css  — statik dosyalar → frontend/src/modules/

GÜVENLİK KARARI: Yüklenen .py dosyaları HER ZAMAN modules/'a yerleşir; core/ ve
modules/__init__.py'ye yazmak yasaktır (patch_security ile engellenir). manifest
içindeki `core: true` yalnızca "kapatılamaz modül" (toggle koruma) anlamına gelir,
dosyanın core/'a yazılacağı anlamına GELMEZ.

Faz 1: manifest oku/doğrula + güvenli yerleştirme + modül listele.
Faz 2 (güvenlik), Faz 3 (versiyon), Faz 4 (rollback) bu dosyaya eklenir.
"""
import io
import json
import shutil
import zipfile
import importlib
from datetime import datetime, timezone
from pathlib import Path

# ── Dizinler ──
APP_ROOT = Path(__file__).resolve().parent.parent          # appbackend/
PROJECT_ROOT = APP_ROOT.parent                              # oba-egitim/
MODULES_DIR = APP_ROOT / "modules"
CORE_DIR = APP_ROOT / "core"
MANIFESTS_DIR = MODULES_DIR / "manifests"
VERSIONS_DIR = APP_ROOT / "eski_versiyonlar"               # sürüm yedekleri
FRONTEND_MODULES_DIR = PROJECT_ROOT / "frontend" / "src" / "modules"

# Kaç eski sürüm saklanır (mevcut + bu kadar geçmiş)
MAX_VERSIONS = 3

# Toggle ile kapatılamayacak (her zaman aktif) çekirdek modüller
KORUMALI_MODULLER = {"yedekleme", "auth_api", "dashboard", "bildirim", "admin_patch", "seed"}

MANIFEST_REQUIRED = ("name", "version", "description", "author", "type")
GECERLI_TIPLER = ("backend", "frontend", "both")


# ─────────────────────────────────────────────
# Dizin garantisi
# ─────────────────────────────────────────────
def _ensure_dirs():
    MANIFESTS_DIR.mkdir(parents=True, exist_ok=True)
    VERSIONS_DIR.mkdir(parents=True, exist_ok=True)
    FRONTEND_MODULES_DIR.mkdir(parents=True, exist_ok=True)


# ─────────────────────────────────────────────
# Manifest
# ─────────────────────────────────────────────
def read_manifest_from_zip(data: bytes) -> dict:
    """ZIP içinden manifest.json'u okur (kök veya herhangi bir alt dizinde)."""
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        manifest_name = None
        for n in zf.namelist():
            if Path(n).name == "manifest.json" and not n.endswith("/"):
                manifest_name = n
                break
        if not manifest_name:
            raise ValueError("ZIP içinde manifest.json bulunamadı.")
        raw = zf.read(manifest_name).decode("utf-8")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"manifest.json geçersiz JSON: {e}")


def validate_manifest(m: dict) -> list:
    """Manifest'i doğrular, hata listesi döner (boş = geçerli)."""
    errs = []
    if not isinstance(m, dict):
        return ["manifest bir JSON nesnesi olmalı"]
    for f in MANIFEST_REQUIRED:
        if not m.get(f):
            errs.append(f"manifest.{f} zorunlu")
    tip = m.get("type")
    if tip and tip not in GECERLI_TIPLER:
        errs.append(f"manifest.type '{tip}' geçersiz (backend/frontend/both olmalı)")
    ad = m.get("name", "")
    if ad and not _gecerli_modul_adi(ad):
        errs.append(f"manifest.name '{ad}' geçersiz (yalnız harf/rakam/alt-çizgi)")
    return errs


def _gecerli_modul_adi(ad: str) -> bool:
    return bool(ad) and all(c.isalnum() or c == "_" for c in ad) and not ad[0].isdigit()


# ─────────────────────────────────────────────
# ZIP içeriğini sınıflandır + güvenli çıkar
# ─────────────────────────────────────────────
def _guvenli_uye(name: str) -> bool:
    """Path traversal / mutlak yol / gizli yol koruması."""
    if not name or name.endswith("/"):
        return False
    p = Path(name)
    if p.is_absolute():
        return False
    parts = p.parts
    if ".." in parts:
        return False
    return True


def classify_zip(data: bytes) -> dict:
    """ZIP üyelerini hedeflerine göre sınıflandırır (yerleştirmeden)."""
    plan = {"backend": [], "frontend": [], "static": [], "skipped": [], "rejected": []}
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        for n in zf.namelist():
            if n.endswith("/"):
                continue
            base = Path(n).name
            if base == "manifest.json":
                plan["skipped"].append(n)
                continue
            if not _guvenli_uye(n):
                plan["rejected"].append(n)
                continue
            ext = Path(n).suffix.lower()
            if ext == ".py":
                # core/ veya __init__.py hedefleri yasak
                if base == "__init__.py":
                    plan["rejected"].append(n)
                else:
                    plan["backend"].append(n)
            elif ext == ".jsx":
                plan["frontend"].append(n)
            elif ext in (".png", ".css", ".js", ".jpg", ".jpeg", ".svg"):
                plan["static"].append(n)
            else:
                plan["skipped"].append(n)
    return plan


def _hedef_yol(zip_entry: str, kategori: str) -> Path:
    base = Path(zip_entry).name
    if kategori == "backend":
        return MODULES_DIR / base
    return FRONTEND_MODULES_DIR / base


def yerlestir(data: bytes, plan: dict) -> list:
    """Plan'a göre dosyaları diske yazar. Yazılan hedef yolların listesini döner."""
    _ensure_dirs()
    yazilan = []
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        for kategori in ("backend", "frontend", "static"):
            for entry in plan[kategori]:
                hedef = _hedef_yol(entry, "backend" if kategori == "backend" else "frontend")
                hedef.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(entry) as src, open(hedef, "wb") as dst:
                    shutil.copyfileobj(src, dst)
                yazilan.append(str(hedef))
    return yazilan


# ─────────────────────────────────────────────
# Manifest deposu (kurulu modüller)
# ─────────────────────────────────────────────
def _manifest_path(name: str) -> Path:
    return MANIFESTS_DIR / f"{name}.json"


def manifest_kaydet(m: dict):
    _ensure_dirs()
    _manifest_path(m["name"]).write_text(
        json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def manifest_oku(name: str) -> dict | None:
    p = _manifest_path(name)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def list_modules() -> list:
    """Kurulu tüm modüllerin manifest'lerini döner (UI için)."""
    _ensure_dirs()
    out = []
    for p in sorted(MANIFESTS_DIR.glob("*.json")):
        try:
            m = json.loads(p.read_text(encoding="utf-8"))
            m.setdefault("active", True)
            m.setdefault("core", m["name"] in KORUMALI_MODULLER)
            out.append(m)
        except Exception:
            continue
    return out


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def import_check(backend_entries: list) -> list:
    """Yerleşen backend modüllerini import etmeyi dener. Hata listesi döner."""
    hatalar = []
    importlib.invalidate_caches()
    import sys
    for entry in backend_entries:
        mod_adi = "modules." + Path(entry).stem
        try:
            if mod_adi in sys.modules:
                importlib.reload(sys.modules[mod_adi])
            else:
                importlib.import_module(mod_adi)
        except Exception as e:
            hatalar.append(f"{mod_adi}: {type(e).__name__}: {e}")
    return hatalar


def _yerlesenleri_sil(yollar: list):
    for y in yollar:
        try:
            Path(y).unlink()
        except FileNotFoundError:
            pass


# ─────────────────────────────────────────────
# Kurulum (Faz 1: temel) — güvenlik/versiyon/rollback sonraki fazlarda eklenir
# ─────────────────────────────────────────────
def install_patch(data: bytes) -> dict:
    """ZIP yamayı kurar. Sonuç: {ok, name, version, placed_files, warnings, errors}."""
    sonuc = {"ok": False, "name": None, "version": None,
             "placed_files": [], "warnings": [], "errors": []}

    # 1) manifest
    try:
        manifest = read_manifest_from_zip(data)
    except Exception as e:
        sonuc["errors"].append(str(e))
        return sonuc
    hatalar = validate_manifest(manifest)
    if hatalar:
        sonuc["errors"].extend(hatalar)
        return sonuc

    name = manifest["name"]
    sonuc["name"] = name
    sonuc["version"] = manifest.get("version")

    # 1.5) GÜVENLİK TARAMASI (AST) — yerleştirmeden ÖNCE
    from core import patch_security
    guvenlik = patch_security.scan_zip(data)
    sonuc["warnings"].extend(guvenlik["warnings"])
    if guvenlik["errors"]:
        sonuc["errors"].append("Güvenlik taraması başarısız (tehlikeli kod):")
        sonuc["errors"].extend(guvenlik["errors"])
        return sonuc

    # 2) sınıflandır
    plan = classify_zip(data)
    if plan["rejected"]:
        sonuc["errors"].append(
            "Reddedilen güvensiz dosyalar (path traversal / core/ / __init__): "
            + ", ".join(plan["rejected"])
        )
        return sonuc
    if not (plan["backend"] or plan["frontend"] or plan["static"]):
        sonuc["errors"].append("ZIP içinde yerleştirilecek dosya yok.")
        return sonuc

    # 3) yerleştir
    try:
        yazilan = yerlestir(data, plan)
    except Exception as e:
        sonuc["errors"].append(f"Dosya yerleştirme hatası: {e}")
        return sonuc
    sonuc["placed_files"] = yazilan

    # 3.5) IMPORT KONTROLÜ — backend modülleri gerçekten import edilebiliyor mu?
    import_hatalari = import_check(plan["backend"])
    if import_hatalari:
        # Yerleşen dosyaları geri al (tam sürümlü rollback Faz 4'te)
        _yerlesenleri_sil(yazilan)
        sonuc["placed_files"] = []
        sonuc["errors"].append("Import kontrolü başarısız (modül yüklenemiyor):")
        sonuc["errors"].extend(import_hatalari)
        return sonuc

    # 4) manifest kaydet
    manifest.setdefault("core", name in KORUMALI_MODULLER)
    manifest.setdefault("active", True)
    manifest["installed_at"] = _now()
    manifest["backend_files"] = [Path(p).name for p in plan["backend"]]
    manifest["frontend_files"] = [Path(p).name for p in (plan["frontend"] + plan["static"])]
    manifest_kaydet(manifest)

    sonuc["ok"] = True
    return sonuc
