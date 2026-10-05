#!/usr/bin/env python3
"""Create a private local .env with fresh secrets without printing them."""

import argparse
import base64
import os
import secrets
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / ".env.example"
DESTINATION = ROOT / ".env"
LOCAL_KEY = ROOT / "backend" / "data" / ".app_encryption_key"
DATA_DIRECTORY = ROOT / "backend" / "data"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--isolated-ports",
        action="store_true",
        help="Use alternate host ports so Docker can run beside the local dev server.",
    )
    args = parser.parse_args()

    if DESTINATION.exists():
        raise SystemExit(".env zaten var; mevcut sırları korumak için üzerine yazılmadı.")

    if LOCAL_KEY.exists():
        encryption_key = LOCAL_KEY.read_text(encoding="ascii").strip()
    elif any(path.is_file() and path.stat().st_size for path in DATA_DIRECTORY.rglob("*.db")):
        raise SystemExit("Mevcut veritabanı bulundu ancak yerel şifreleme anahtarı yok. Yeni anahtar üretmek mevcut sırları erişilemez kılabilir; eski .env yedeğini geri yükleyin.")
    else:
        encryption_key = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode("ascii")

    replacements = {
        "API_AUTH_TOKEN": secrets.token_hex(32),
        "APP_ENCRYPTION_KEY": encryption_key,
        "AUTH_SECRET_KEY": secrets.token_hex(48),
        "REDIS_PASSWORD": secrets.token_urlsafe(36),
        "POSTGRES_PASSWORD": secrets.token_urlsafe(36),
    }
    if args.isolated_ports:
        replacements.update({
            "BACKEND_PORT": "18000",
            "FRONTEND_PORT": "13000",
            "POSTGRES_PORT": "15432",
            "REDIS_PORT": "16379",
            "BACKEND_PUBLIC_URL": "http://localhost:18000",
            "FRONTEND_PUBLIC_URL": "http://localhost:13000",
            "PUBLIC_API_URL": "http://localhost:18000/api",
            "NEXT_PUBLIC_API_URL": "http://localhost:18000/api",
            "CORS_ORIGINS": "http://localhost:13000,http://127.0.0.1:13000",
            "GOOGLE_REDIRECT_URI": "http://localhost:18000/api/inbox/oauth/google/callback",
            "MICROSOFT_REDIRECT_URI": "http://localhost:18000/api/inbox/oauth/microsoft/callback",
        })

    found = set()
    lines = []
    for line in TEMPLATE.read_text(encoding="utf-8").splitlines(keepends=True):
        key, separator, _value = line.partition("=")
        if separator and key in replacements:
            line = f"{key}={replacements[key]}\n"
            found.add(key)
        lines.append(line)
    missing = replacements.keys() - found
    if missing:
        raise SystemExit(f".env.example içinde beklenen ayar yok: {', '.join(sorted(missing))}")

    descriptor = os.open(DESTINATION, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as env_file:
            env_file.writelines(lines)
            env_file.flush()
            os.fsync(env_file.fileno())
    except Exception:
        DESTINATION.unlink(missing_ok=True)
        raise

    if args.isolated_ports:
        print("Özel izinli .env oluşturuldu; Docker adresleri: http://localhost:13000 (web), http://localhost:18000 (API).")
    else:
        print("Özel izinli .env oluşturuldu. Gizli değerler ekrana yazdırılmadı; sağlayıcı anahtarlarını bu dosyada yapılandırabilirsiniz.")


if __name__ == "__main__":
    main()
