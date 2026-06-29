"""Yama güvenlik tarayıcısı — yüklenen kodun statik (AST) analizi.

Yüklenen .py dosyaları Python AST ile parse edilir; tehlikeli desenler
yakalanır. .jsx dosyaları için temel regex tabanlı XSS/eval kontrolü yapılır.

Sonuç sözlüğü: {"errors": [...], "warnings": [...]}
  - errors  → yükleme REDDEDİLİR
  - warnings→ yükleme devam eder ama admin'e gösterilir
"""
import ast
import re
from pathlib import Path

# Tehlikeli fonksiyon çağrıları (nokta-ayrımlı tam ad) → HATA
TEHLIKELI_CAGRILAR = {
    "os.system", "os.popen", "os.remove", "os.unlink", "os.rmdir",
    "os.removedirs", "os.kill", "os.execv", "os.execve",
    "subprocess.call", "subprocess.run", "subprocess.Popen",
    "subprocess.check_output", "subprocess.check_call", "subprocess.getoutput",
    "shutil.rmtree", "shutil.move",
}
# Tehlikeli builtin çağrıları (tek isim) → HATA
TEHLIKELI_BUILTIN = {"eval", "exec", "compile", "__import__"}

# Tehlikeli importlar → HATA (düşük seviye / sistem / ağ)
TEHLIKELI_IMPORTLAR = {
    "subprocess", "socket", "ctypes", "ftplib", "telnetlib", "smtplib",
    "pty", "multiprocessing", "urllib", "urllib.request", "http.client",
    "importlib",
}
# Uyarı verilen importlar (ağ/serileştirme) → WARNING
UYARI_IMPORTLAR = {"requests", "httpx", "aiohttp", "pickle", "marshal", "http"}

# core/ veya __init__ hedefleri — patch_manager da engeller, burada da raporlanır
YASAK_DOSYA_DESEN = ("__init__.py",)


def _dotted(node) -> str:
    """Attribute zincirini 'os.path.join' gibi düz metne çevirir."""
    parcalar = []
    while isinstance(node, ast.Attribute):
        parcalar.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parcalar.append(node.id)
    return ".".join(reversed(parcalar))


def scan_python_source(code: str, dosya: str = "<py>") -> dict:
    """Tek bir Python kaynağını tarar."""
    errors, warnings = [], []
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return {"errors": [f"{dosya}: sözdizimi hatası — {e}"], "warnings": []}

    for node in ast.walk(tree):
        # import kontrolü
        if isinstance(node, ast.Import):
            for al in node.names:
                kok = al.name.split(".")[0]
                if al.name in TEHLIKELI_IMPORTLAR or kok in TEHLIKELI_IMPORTLAR:
                    errors.append(f"{dosya}:{node.lineno} tehlikeli import: {al.name}")
                elif kok in UYARI_IMPORTLAR:
                    warnings.append(f"{dosya}:{node.lineno} dikkat: ağ/serileştirme importu '{al.name}'")
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            kok = mod.split(".")[0]
            if mod in TEHLIKELI_IMPORTLAR or kok in TEHLIKELI_IMPORTLAR:
                errors.append(f"{dosya}:{node.lineno} tehlikeli import: from {mod}")
            elif kok in UYARI_IMPORTLAR:
                warnings.append(f"{dosya}:{node.lineno} dikkat: ağ/serileştirme importu 'from {mod}'")
        # çağrı kontrolü
        elif isinstance(node, ast.Call):
            f = node.func
            if isinstance(f, ast.Name) and f.id in TEHLIKELI_BUILTIN:
                errors.append(f"{dosya}:{node.lineno} yasak çağrı: {f.id}()")
            elif isinstance(f, ast.Attribute):
                ad = _dotted(f)
                if ad in TEHLIKELI_CAGRILAR:
                    errors.append(f"{dosya}:{node.lineno} yasak çağrı: {ad}()")
                # kısmi eşleşme: *.system / *.rmtree gibi
                elif f.attr in ("system", "rmtree", "Popen") and ad not in TEHLIKELI_CAGRILAR:
                    warnings.append(f"{dosya}:{node.lineno} şüpheli çağrı: {ad}()")
    return {"errors": errors, "warnings": warnings}


JSX_TEHLIKELI = [
    (r"dangerouslySetInnerHTML", "dangerouslySetInnerHTML kullanımı (XSS riski)"),
    (r"\beval\s*\(", "eval() kullanımı"),
    (r"\bnew\s+Function\s*\(", "new Function() kullanımı"),
    (r"\.innerHTML\s*=", "innerHTML atama (XSS riski)"),
    (r"document\.write\s*\(", "document.write() kullanımı"),
]


def scan_jsx_source(code: str, dosya: str = "<jsx>") -> dict:
    """JSX/JS için temel XSS/eval uyarı taraması (hepsi WARNING)."""
    warnings = []
    for desen, mesaj in JSX_TEHLIKELI:
        for m in re.finditer(desen, code):
            satir = code[: m.start()].count("\n") + 1
            warnings.append(f"{dosya}:{satir} {mesaj}")
    return {"errors": [], "warnings": warnings}


def scan_zip(data: bytes) -> dict:
    """ZIP içindeki tüm .py/.jsx dosyalarını tarar (yerleştirmeden önce)."""
    import io
    import zipfile

    errors, warnings = [], []
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        for n in zf.namelist():
            if n.endswith("/"):
                continue
            base = Path(n).name
            ext = Path(n).suffix.lower()
            if base == "manifest.json":
                continue
            if base in YASAK_DOSYA_DESEN:
                errors.append(f"{n}: {base} değiştirilemez (yasak hedef)")
                continue
            if ext == ".py":
                try:
                    src = zf.read(n).decode("utf-8")
                except Exception as e:
                    errors.append(f"{n}: okunamadı ({e})")
                    continue
                r = scan_python_source(src, n)
                errors += r["errors"]
                warnings += r["warnings"]
            elif ext == ".jsx" or ext == ".js":
                try:
                    src = zf.read(n).decode("utf-8")
                except Exception:
                    continue
                r = scan_jsx_source(src, n)
                warnings += r["warnings"]
    return {"errors": errors, "warnings": warnings}
