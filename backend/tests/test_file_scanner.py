import pytest

from backend.app.core.config import settings
from backend.app.core.file_scanner import enforce_upload_scan, scan_uploaded_file


class FakeClamConnection:
    def __init__(self, response):
        self.response = response
        self.sent = bytearray()

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def settimeout(self, _timeout):
        pass

    def sendall(self, value):
        self.sent.extend(value)

    def recv(self, _size):
        response, self.response = self.response, b""
        return response


def test_clamav_instream_clean_result(monkeypatch):
    import backend.app.core.file_scanner as scanner

    connection = FakeClamConnection(b"stream: OK\0")
    monkeypatch.setattr(settings, "CLAMAV_HOST", "clamav.test")
    monkeypatch.setattr(scanner.socket, "create_connection", lambda *_args, **_kwargs: connection)

    result = scan_uploaded_file(b"safe file bytes")

    assert result["status"] == "clean"
    assert connection.sent.startswith(b"zINSTREAM\0")
    assert connection.sent.endswith(b"\x00\x00\x00\x00")


def test_clamav_detected_file_is_rejected(monkeypatch):
    import backend.app.core.file_scanner as scanner

    monkeypatch.setattr(settings, "CLAMAV_HOST", "clamav.test")
    monkeypatch.setattr(scanner.socket, "create_connection", lambda *_args, **_kwargs: FakeClamConnection(b"stream: Eicar-Test-Signature FOUND\0"))

    with pytest.raises(ValueError, match="güvenlik taramasından"):
        enforce_upload_scan(b"malware test signature")


def test_production_upload_fails_closed_when_clamav_is_unavailable(monkeypatch):
    import backend.app.core.file_scanner as scanner

    monkeypatch.setattr(settings, "CLAMAV_HOST", "clamav.test")
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(scanner.socket, "create_connection", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("offline")))

    with pytest.raises(RuntimeError, match="tarama servisine ulaşılamıyor"):
        enforce_upload_scan(b"resume contents")


def test_unconfigured_scanner_is_development_only_compatibility(monkeypatch):
    monkeypatch.setattr(settings, "CLAMAV_HOST", "")
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")

    assert enforce_upload_scan(b"local test file")["status"] == "disabled"
