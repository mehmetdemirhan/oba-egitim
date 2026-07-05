"""PWA ikonlarını üretir (marka gradyanı + beyaz açık-kitap) → frontend/public/.

    cd appbackend && .venv/Scripts/python.exe scripts/pwa_ikon_uret.py
"""
from pathlib import Path
from PIL import Image, ImageDraw

CIKTI = Path(__file__).resolve().parent.parent.parent / "frontend" / "public"


def _hex(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


C1, C2 = _hex("F97316"), _hex("EF4444")


def uret(S: int, ad: str):
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    # Diagonal gradient
    grad = Image.new("RGB", (S, S))
    px = grad.load()
    for y in range(S):
        for x in range(S):
            t = (x + y) / (2 * S)
            px[x, y] = tuple(int(C1[i] + (C2[i] - C1[i]) * t) for i in range(3))
    # Yuvarlak köşe maskesi
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, S - 1, S - 1], radius=int(S * 0.22), fill=255)
    img.paste(grad, (0, 0), mask)
    # Beyaz açık kitap (iki sayfa)
    d = ImageDraw.Draw(img)
    m, cx = S * 0.26, S / 2
    top, bot = S * 0.33, S * 0.70
    d.polygon([(m, top + S * 0.035), (cx - S * 0.02, top), (cx - S * 0.02, bot), (m, bot - S * 0.035)], fill=(255, 255, 255, 255))
    d.polygon([(S - m, top + S * 0.035), (cx + S * 0.02, top), (cx + S * 0.02, bot), (S - m, bot - S * 0.035)], fill=(255, 255, 255, 255))
    # Orta cilt çizgisi
    d.rectangle([cx - S * 0.008, top, cx + S * 0.008, bot], fill=(255, 255, 255, 255))
    yol = CIKTI / ad
    img.save(yol)
    print(f"  ✓ {yol.name} ({S}x{S})")


if __name__ == "__main__":
    uret(192, "icon-192.png")
    uret(512, "icon-512.png")
    uret(180, "apple-touch-icon.png")
    print("PWA ikonları üretildi.")
