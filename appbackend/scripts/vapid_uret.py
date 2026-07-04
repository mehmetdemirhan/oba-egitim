"""VAPID anahtar üreteci — Web Push için (bir kez çalıştırılır, idempotent).

.env'de VAPID_PUBLIC_KEY / VAPID_PRIVATE_KEY yoksa üretip ekler. Private key PEM'i
tek satırda (\\n kaçışlı) saklanır; core/config bunu çözer. Public key (applicationServerKey)
tarayıcının pushManager.subscribe'ında kullanılır — frontend bunu /push/vapid-public'ten çeker.

Üretim (Render): bu script'le ÜRETMEYİN — kendi anahtarınızı üretip Render env'e girin
(private key gizli kalmalı; her ortam kendi çiftini kullanır).

    cd appbackend && .venv/Scripts/python.exe scripts/vapid_uret.py
"""
import base64
from pathlib import Path

from py_vapid import Vapid01
from cryptography.hazmat.primitives import serialization

ENV = Path(__file__).resolve().parent.parent / ".env"


def main():
    metin = ENV.read_text(encoding="utf-8") if ENV.exists() else ""
    if "VAPID_PUBLIC_KEY" in metin:
        print("ℹ️  VAPID anahtarları .env'de zaten var — atlandı.")
        return
    v = Vapid01()
    v.generate_keys()
    priv_pem = v.private_pem().decode().replace("\n", "\\n")
    pub_raw = v.public_key.public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    appkey = base64.urlsafe_b64encode(pub_raw).rstrip(b"=").decode()

    ekle = (
        "\n# --- Web Push (VAPID) ---\n"
        f"VAPID_PUBLIC_KEY={appkey}\n"
        f'VAPID_PRIVATE_KEY="{priv_pem}"\n'
        "VAPID_SUBJECT=mailto:admin@oba.com\n"
    )
    with ENV.open("a", encoding="utf-8") as f:
        f.write(ekle)
    print("✅ VAPID anahtarları .env'e eklendi.")
    print(f"   Public (applicationServerKey): {appkey}")


if __name__ == "__main__":
    main()
