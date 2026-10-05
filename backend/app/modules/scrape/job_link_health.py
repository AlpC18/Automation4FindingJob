"""Safe, on-demand source-link health checks for scraped job records."""

import ipaddress
import socket
from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
from typing import Any
from urllib.parse import urljoin, urlsplit

import httpx

from backend.app.core.database import get_db_connection

_link_check_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="job-link-check")


def _public_http_url(value: str) -> tuple[bool, str]:
    try:
        parsed = urlsplit((value or "").strip())
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
            return False, "Yalnızca kullanıcı bilgisi içermeyen HTTP/HTTPS linkleri kontrol edilebilir."
        host = parsed.hostname.lower().rstrip(".")
        if host in {"localhost", "localhost.localdomain"}:
            return False, "Yerel host adresleri güvenlik nedeniyle kontrol edilemez."
        addresses = {item[4][0] for item in socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)}
        if not addresses:
            return False, "Alan adı çözümlenemedi."
        for address in addresses:
            ip = ipaddress.ip_address(address)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified:
                return False, "Özel veya yerel ağ adresleri güvenlik nedeniyle kontrol edilemez."
        return True, ""
    except (ValueError, OSError):
        return False, "Link alan adı çözümlenemedi veya biçimi geçersiz."


def _save(job_id: str, result: dict[str, Any]) -> dict[str, Any]:
    conn = get_db_connection()
    try:
        conn.cursor().execute(
            """INSERT INTO job_link_checks(job_id, status, status_code, checked_url, final_url, error_text, checked_at)
               VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(job_id) DO UPDATE SET status=excluded.status, status_code=excluded.status_code,
               checked_url=excluded.checked_url, final_url=excluded.final_url, error_text=excluded.error_text,
               checked_at=CURRENT_TIMESTAMP""",
            (job_id, result["status"], result.get("status_code"), result.get("checked_url", ""), result.get("final_url", ""), result.get("error", "")),
        )
        conn.commit()
    finally:
        conn.close()
    return {"job_id": job_id, **result}


def check_job_link(job_id: str) -> dict[str, Any]:
    conn = get_db_connection()
    try:
        row = conn.cursor().execute("SELECT url FROM scraped_jobs WHERE id = ?", (job_id,)).fetchone()
    finally:
        conn.close()
    if not row:
        raise ValueError("Job not found")
    url = (row["url"] if isinstance(row, dict) else row[0]) or ""
    valid, reason = _public_http_url(url)
    if not valid:
        return _save(job_id, {"status": "invalid", "status_code": None, "checked_url": url, "final_url": "", "error": reason})

    current = url
    try:
        with httpx.Client(timeout=8, follow_redirects=False, headers={"User-Agent": "CareerAgentLinkCheck/1.0"}) as client:
            for _ in range(4):
                response = client.get(current)
                if 300 <= response.status_code < 400 and response.headers.get("location"):
                    current = urljoin(current, response.headers["location"])
                    valid, reason = _public_http_url(current)
                    if not valid:
                        return _save(job_id, {"status": "blocked", "status_code": response.status_code, "checked_url": url, "final_url": current, "error": reason})
                    continue
                status = "reachable" if response.status_code < 400 else "broken"
                return _save(job_id, {"status": status, "status_code": response.status_code, "checked_url": url, "final_url": current, "error": "" if status == "reachable" else f"HTTP {response.status_code}"})
        return _save(job_id, {"status": "broken", "status_code": None, "checked_url": url, "final_url": current, "error": "Çok fazla yönlendirme."})
    except (httpx.HTTPError, OSError) as exc:
        return _save(job_id, {"status": "unreachable", "status_code": None, "checked_url": url, "final_url": current, "error": str(exc)[:300]})


def get_job_link_check(job_id: str) -> dict[str, Any] | None:
    conn = get_db_connection()
    try:
        row = conn.cursor().execute("SELECT * FROM job_link_checks WHERE job_id = ?", (job_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_job_link_checks(job_ids: list[str]) -> dict[str, dict[str, Any]]:
    if not job_ids:
        return {}
    conn = get_db_connection()
    try:
        placeholders = ",".join("?" for _ in job_ids)
        rows = conn.cursor().execute(f"SELECT * FROM job_link_checks WHERE job_id IN ({placeholders})", job_ids).fetchall()
        return {row["job_id"]: dict(row) for row in rows}
    finally:
        conn.close()


def _run_checks(job_ids: list[str], tenant_id: str | None) -> None:
    from backend.app.core.database import use_tenant

    tenant_context = use_tenant(tenant_id) if tenant_id else nullcontext()
    with tenant_context:
        for job_id in job_ids:
            try:
                check_job_link(job_id)
            except Exception:
                continue


def schedule_job_link_checks(job_ids: list[str]) -> int:
    """Queue checks for new listings; use Celery when reachable, threads otherwise."""
    distinct_ids = list(dict.fromkeys(job_id for job_id in job_ids if job_id))
    if not distinct_ids:
        return 0

    from backend.app.core.tenant import get_tenant_id
    tenant_id = get_tenant_id()
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        for job_id in distinct_ids:
            row = cursor.execute("SELECT url FROM scraped_jobs WHERE id = ?", (job_id,)).fetchone()
            if not row:
                continue
            url = row["url"] if isinstance(row, dict) else row[0]
            cursor.execute(
                """INSERT INTO job_link_checks(job_id, status, checked_url, checked_at)
                   VALUES (?, 'queued', ?, CURRENT_TIMESTAMP)
                   ON CONFLICT(job_id) DO UPDATE SET status='queued', checked_url=excluded.checked_url,
                   status_code=NULL, final_url='', error_text='', checked_at=CURRENT_TIMESTAMP""",
                (job_id, url or ""),
            )
        conn.commit()
    finally:
        conn.close()

    try:
        from backend.app.core.config import settings
        from backend.app.tasks.celery_app import check_redis_connection
        if settings.USE_CELERY and check_redis_connection():
            from backend.app.tasks.worker_tasks import task_check_job_links
            task_check_job_links.delay(distinct_ids, tenant_id)
            return len(distinct_ids)
    except Exception:
        pass

    _link_check_executor.submit(_run_checks, distinct_ids, tenant_id)
    return len(distinct_ids)
