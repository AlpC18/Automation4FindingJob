"""Encrypted, rotating SQLite backups and tenant-scoped recovery."""

import asyncio
import fcntl
import io
import json
import logging
import os
import re
import shutil
import sqlite3
import tempfile
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from backend.app.core.config import settings
from backend.app.core.database import is_postgres_database
from backend.app.core.security import _fernet

logger = logging.getLogger(__name__)
BACKUP_MAGIC = b"CAREER-AGENT-ENCRYPTED-BACKUP-V1\n"
BACKUP_PREFIX = "career-agent-"


def backup_directory() -> Path:
    configured = getattr(settings, "BACKUP_DIR", None)
    # An empty BACKUP_DIR= line parses as Path("."), which must not turn the working directory into the backup folder.
    if configured and str(configured) not in ("", "."):
        configured = Path(configured)
        if configured.exists() or configured.parent.exists():
            return configured
        logger.warning("BACKUP_DIR %s is unavailable (drive not connected?); using the local backup folder.", configured)
    return Path(settings.DATA_PATH) / "backups"


def _backup_files(data_root: Path, backup_root: Path) -> list[Path]:
    result = []
    resolved_backup = backup_root.resolve()
    for path in data_root.rglob("*"):
        if not path.is_file() or path.is_symlink():
            continue
        resolved = path.resolve()
        if resolved == resolved_backup or resolved_backup in resolved.parents:
            continue
        if path.name == ".app_encryption_key" or path.name.endswith(("-wal", "-shm")):
            continue
        result.append(path)
    return sorted(result)


def _snapshot_sqlite(source_path: Path, snapshot_path: Path) -> None:
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    uri = f"{source_path.resolve().as_uri()}?mode=ro"
    with sqlite3.connect(uri, uri=True, timeout=30) as source, sqlite3.connect(snapshot_path) as target:
        source.backup(target)
        result = target.execute("PRAGMA integrity_check").fetchone()
        if not result or result[0] != "ok":
            raise RuntimeError(f"SQLite integrity check failed for {source_path.name}.")


def create_sqlite_backup(*, force: bool = False) -> Optional[Path]:
    """Create a consistent, Fernet-encrypted snapshot of local application data."""
    if is_postgres_database():
        return None  # PostgreSQL uses the scheduled pg_dump container.
    fernet = _fernet()
    if not fernet:
        raise RuntimeError("Şifreli yedek için APP_ENCRYPTION_KEY yapılandırılmalı.")

    data_root = Path(settings.DATA_PATH).resolve()
    directory = backup_directory().resolve()
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    directory.chmod(0o700)
    lock_path = directory / ".backup.lock"
    with lock_path.open("a+b") as lock_file:
        os.chmod(lock_path, 0o600)
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return None

        backups = sorted(directory.glob(f"{BACKUP_PREFIX}*.cagbackup"), key=lambda item: item.stat().st_mtime, reverse=True)
        interval = max(60, int(getattr(settings, "BACKUP_INTERVAL_SECONDS", 86400)))
        if not force and backups and time.time() - backups[0].stat().st_mtime < interval:
            return backups[0]

        files = _backup_files(data_root, directory)
        if not files:
            return None
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        final_path = directory / f"{BACKUP_PREFIX}{stamp}.cagbackup"
        max_size = max(1, int(getattr(settings, "BACKUP_MAX_SIZE_MB", 512))) * 1024 * 1024

        with tempfile.TemporaryDirectory(prefix="career-agent-backup-") as temporary:
            temporary_root = Path(temporary)
            zip_path = temporary_root / "snapshot.zip"
            snapshot_root = temporary_root / "snapshot"
            database_files = []
            with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
                for source in files:
                    relative = source.relative_to(data_root).as_posix()
                    if source.suffix.lower() in {".db", ".sqlite", ".sqlite3"}:
                        snapshot_path = snapshot_root / relative
                        _snapshot_sqlite(source, snapshot_path)
                        archive.write(snapshot_path, relative)
                        database_files.append(relative)
                    else:
                        archive.write(source, relative)
                manifest = {
                    "format": 1,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "database_files": database_files,
                }
                archive.writestr("backup-manifest.json", json.dumps(manifest, separators=(",", ":")))

            if zip_path.stat().st_size > max_size:
                raise RuntimeError(f"Yedek boyutu yapılandırılan {max_size // (1024 * 1024)} MB sınırını aşıyor.")
            encrypted = BACKUP_MAGIC + fernet.encrypt(zip_path.read_bytes())
            partial_path = final_path.with_suffix(final_path.suffix + ".partial")
            try:
                with partial_path.open("xb") as output:
                    os.chmod(partial_path, 0o600)
                    output.write(encrypted)
                    output.flush()
                    os.fsync(output.fileno())
                os.replace(partial_path, final_path)
            finally:
                partial_path.unlink(missing_ok=True)

        retention_days = max(1, int(getattr(settings, "BACKUP_RETENTION_DAYS", 14)))
        cutoff = time.time() - retention_days * 86400
        for old_backup in directory.glob(f"{BACKUP_PREFIX}*.cagbackup"):
            if old_backup != final_path and old_backup.stat().st_mtime < cutoff:
                old_backup.unlink(missing_ok=True)
        return final_path


def _workspace_database_path(tenant_id: Optional[str]) -> Path:
    root = Path(settings.DATA_PATH)
    if tenant_id:
        safe_id = re.sub(r"[^a-zA-Z0-9]", "", tenant_id)
        if not safe_id:
            raise ValueError("Hesap için geçerli yedek veritabanı bulunamadı.")
        return root / "tenants" / f"{safe_id}.db"
    return root / "career_engine.db"


def restore_sqlite_workspace(contents: bytes, tenant_id: Optional[str]) -> str:
    """Restore one workspace DB after validation, preserving a pre-restore backup."""
    if is_postgres_database():
        raise ValueError("PostgreSQL geri yüklemesi Docker içindeki restore-postgres.sh ile yapılmalıdır.")
    if not contents.startswith(BACKUP_MAGIC) and not contents.startswith(b"SQLite format 3\x00"):
        raise ValueError("Dosya bu uygulamanın tanıdığı bir veritabanı veya şifreli yedek biçiminde değil.")
    is_encrypted = contents.startswith(BACKUP_MAGIC)
    fernet = _fernet() if is_encrypted else None
    if is_encrypted and not fernet:
        raise RuntimeError("Yedek açılamadı; APP_ENCRYPTION_KEY yapılandırılmalı.")
    if is_encrypted:
        try:
            zipped = fernet.decrypt(contents[len(BACKUP_MAGIC):])
        except Exception as exc:
            raise ValueError("Yedek açılamadı. Şifreleme anahtarı farklı veya dosya bozuk olabilir.") from exc
    else:
        zipped = contents

    relative_target = _workspace_database_path(tenant_id).relative_to(Path(settings.DATA_PATH)).as_posix()
    target_contents = None
    if zipped.startswith(b"SQLite format 3\x00"):
        target_contents = zipped
    else:
        try:
            with zipfile.ZipFile(io.BytesIO(zipped)) as archive:
                names = set(archive.namelist())
                if "backup-manifest.json" not in names:
                    raise ValueError("Yedek dosyasında doğrulama manifesti bulunamadı.")
                if archive.getinfo("backup-manifest.json").file_size > 1024 * 1024:
                    raise ValueError("Yedek manifesti beklenenden büyük.")
                manifest = json.loads(archive.read("backup-manifest.json"))
                if manifest.get("format") != 1 or relative_target not in manifest.get("database_files", []):
                    raise ValueError("Yedek bu çalışma alanını içermiyor.")
                if archive.getinfo(relative_target).file_size > max(1, int(getattr(settings, "BACKUP_MAX_SIZE_MB", 512))) * 1024 * 1024:
                    raise ValueError("Yedekteki çalışma alanı boyut sınırını aşıyor.")
                target_contents = archive.read(relative_target)
        except (zipfile.BadZipFile, json.JSONDecodeError, KeyError) as exc:
            raise ValueError("Yedek arşivi bozuk veya eksik.") from exc

    if not target_contents or not target_contents.startswith(b"SQLite format 3\x00"):
        raise ValueError("Yedekte geçerli bir SQLite çalışma alanı bulunamadı.")
    target = _workspace_database_path(tenant_id)
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(prefix=".restore-check-", suffix=".db", dir=target.parent, delete=False) as staged:
        staged_path = Path(staged.name)
        staged.write(target_contents)
        staged.flush()
        os.fsync(staged.fileno())
    try:
        with sqlite3.connect(f"{staged_path.resolve().as_uri()}?mode=ro", uri=True) as candidate:
            integrity = candidate.execute("PRAGMA integrity_check").fetchone()
            tables = {row[0] for row in candidate.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not integrity or integrity[0] != "ok" or not {"candidate_profile", "scraped_jobs"}.intersection(tables):
            raise ValueError("Yedek veritabanı uygulama şemasını geçemedi.")

        safety_backup = create_sqlite_backup(force=True)
        if not safety_backup:
            raise RuntimeError("Geri yükleme öncesi güvenlik yedeği oluşturulamadı.")
        for sidecar in (Path(f"{target}-wal"), Path(f"{target}-shm")):
            sidecar.unlink(missing_ok=True)
        os.replace(staged_path, target)
        return safety_backup.name
    finally:
        staged_path.unlink(missing_ok=True)


async def run_periodic_sqlite_backups() -> None:
    """Back up local SQLite data on startup and then at a bounded interval."""
    while True:
        try:
            result = await asyncio.to_thread(create_sqlite_backup)
            if result:
                logger.info("Encrypted SQLite backup available: %s", result.name)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Automatic SQLite backup failed.")
        await asyncio.sleep(max(60, int(getattr(settings, "BACKUP_INTERVAL_SECONDS", 86400))))
