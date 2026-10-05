"""ClamAV INSTREAM scanner for user-provided files."""

import socket
import struct
from typing import Any

from backend.app.core.config import settings


def scan_uploaded_file(content: bytes) -> dict[str, Any]:
    """Scan bytes without writing uploaded files to disk."""
    if not settings.CLAMAV_HOST.strip():
        return {"status": "disabled", "scanner": "clamav"}

    try:
        timeout = max(1, settings.CLAMAV_TIMEOUT_SECONDS)
        with socket.create_connection((settings.CLAMAV_HOST, settings.CLAMAV_PORT), timeout=timeout) as connection:
            connection.settimeout(timeout)
            connection.sendall(b"zINSTREAM\0")
            view = memoryview(content)
            for offset in range(0, len(content), 1024 * 1024):
                chunk = view[offset : offset + 1024 * 1024]
                connection.sendall(struct.pack("!I", len(chunk)))
                connection.sendall(chunk)
            connection.sendall(struct.pack("!I", 0))
            response = bytearray()
            while b"\0" not in response and len(response) < 4096:
                block = connection.recv(1024)
                if not block:
                    break
                response.extend(block)

        message = response.decode("utf-8", errors="replace").strip("\0\r\n ")
        if message.endswith(": OK"):
            return {"status": "clean", "scanner": "clamav"}
        if message.endswith(" FOUND"):
            return {"status": "infected", "scanner": "clamav", "detail": message[:240]}
        return {"status": "unavailable", "scanner": "clamav", "detail": "Scanner returned an invalid response."}
    except (OSError, TimeoutError) as exc:
        return {"status": "unavailable", "scanner": "clamav", "detail": str(exc)[:240]}


def enforce_upload_scan(content: bytes) -> dict[str, Any]:
    """Reject infected files and fail closed when production scanning is down."""
    result = scan_uploaded_file(content)
    if result["status"] == "infected":
        raise ValueError("Yüklenen dosya güvenlik taramasından geçemedi.")
    if result["status"] == "unavailable" and settings.ENVIRONMENT.lower() == "production":
        raise RuntimeError("Dosya tarama servisine ulaşılamıyor; dosya işlenmedi.")
    return result
