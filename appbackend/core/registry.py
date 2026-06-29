"""Modül kayıt defteri (registry) — dinamik router yükleme + aktif/pasif yönetimi.

modules/registry.json: SIRALI [{"name": ..., "active": bool}] listesi. Sıra
route eşleşmesi için kritiktir (catch-all / duplicate yollar). server.py bu
defteri okuyup AKTİF modüllerin router'ını dinamik dahil eder; pasif modüller
import EDİLMEZ (route tablosuna girmez).
"""
import json
import importlib
import logging
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parent.parent
REGISTRY_PATH = APP_ROOT / "modules" / "registry.json"

# Toggle ile kapatılamayan (her zaman aktif) çekirdek modüller
KORUMALI_MODULLER = {"yedekleme", "auth_api", "dashboard", "bildirim", "admin_patch", "seed"}


def load_registry() -> list:
    if REGISTRY_PATH.exists():
        try:
            return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        except Exception:
            logging.error("[registry] registry.json okunamadı, boş kabul ediliyor.")
    return []


def save_registry(entries: list):
    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    REGISTRY_PATH.write_text(
        json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def is_active(name: str) -> bool:
    for e in load_registry():
        if e["name"] == name:
            return bool(e.get("active", True))
    return True


def active_map() -> dict:
    return {e["name"]: bool(e.get("active", True)) for e in load_registry()}


def set_active(name: str, active: bool) -> list:
    if name in KORUMALI_MODULLER and not active:
        raise ValueError(f"'{name}' korumalı çekirdek modüldür, kapatılamaz.")
    reg = load_registry()
    for e in reg:
        if e["name"] == name:
            e["active"] = bool(active)
            break
    else:
        reg.append({"name": name, "active": bool(active)})
    save_registry(reg)
    return reg


def add_module(name: str, active: bool = True):
    reg = load_registry()
    if not any(e["name"] == name for e in reg):
        reg.append({"name": name, "active": bool(active)})
        save_registry(reg)


def remove_module(name: str):
    save_registry([e for e in load_registry() if e["name"] != name])


def register_routers(api_router) -> dict:
    """Aktif modüllerin router'ını sırayla api_router'a dahil eder.

    Bir modül import/registration sırasında patlarsa uygulama çökmesin diye
    hata loglanır ve atlanır (diğer modüller yüklenir).
    """
    yuklendi, hatali, pasif = [], [], []
    for e in load_registry():
        name = e["name"]
        if not e.get("active", True):
            pasif.append(name)
            continue
        try:
            mod = importlib.import_module(f"modules.{name}")
            router = getattr(mod, "router", None)
            if router is not None:
                api_router.include_router(router)
                yuklendi.append(name)
        except Exception as ex:
            logging.error(f"[registry] modül yüklenemedi: {name}: {type(ex).__name__}: {ex}")
            hatali.append(name)
    logging.info(
        f"[registry] {len(yuklendi)} modül yüklendi | {len(pasif)} pasif | {len(hatali)} hata"
    )
    return {"loaded": yuklendi, "passive": pasif, "failed": hatali}
