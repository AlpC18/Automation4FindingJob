"""Apify account validation, usage reporting, and a conservative local spend guard."""

import hashlib
import time
import uuid
from typing import Any

import httpx

from backend.app.modules.scrape.source_registry import apify_tokens

FREE_PLAN_ALLOWANCE_USD = 5.0
USAGE_CACHE_SECONDS = 60
SNAPSHOT_INTERVAL_SECONDS = 600
_last_snapshot_at = 0.0
_cache: dict[str, tuple[float, dict[str, Any]]] = {}
# ponytail: in-memory; the last-scan figure is unknown after a restart until the next scan runs.
_last_scan: dict[str, Any] = {}


def _fingerprint(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()[:12]


def _fetch_status(token: str, slot: int) -> dict[str, Any]:
    fingerprint = _fingerprint(token)
    cached = _cache.get(fingerprint)
    if cached and cached[0] > time.monotonic():
        return {**cached[1], "slot": slot}

    headers = {"Accept": "application/json", "Authorization": f"Bearer {token}"}
    try:
        with httpx.Client(timeout=12) as client:
            user_response = client.get("https://api.apify.com/v2/users/me", headers=headers)
            usage_response = client.get("https://api.apify.com/v2/users/me/usage/monthly", headers=headers)
        if user_response.status_code >= 400 or usage_response.status_code >= 400:
            code = user_response.status_code if user_response.status_code >= 400 else usage_response.status_code
            result = {"fingerprint": fingerprint, "masked": f"••••{token[-4:]}", "valid": False, "used_usd": None, "remaining_usd": None, "budget_usd": 0, "error": f"Apify kimlik doğrulaması/kota isteği başarısız (HTTP {code})."}
        else:
            user = user_response.json().get("data", {})
            usage = usage_response.json().get("data", {})
            account_id = str(user.get("id") or "")
            used = float(usage.get("totalUsageCreditsUsdAfterVolumeDiscount") or 0)
            result = {
                "fingerprint": fingerprint,
                "masked": f"••••{token[-4:]}",
                "valid": bool(account_id),
                "account_id": account_id,
                "used_usd": used,
                "remaining_usd": max(0.0, FREE_PLAN_ALLOWANCE_USD - used),
                "budget_usd": FREE_PLAN_ALLOWANCE_USD,
                "cycle_start": (usage.get("usageCycle") or {}).get("startAt"),
                "cycle_end": (usage.get("usageCycle") or {}).get("endAt"),
                "error": None if account_id else "Apify hesap bilgisi alınamadı.",
            }
    except (httpx.HTTPError, ValueError, TypeError, KeyError):
        result = {"fingerprint": fingerprint, "masked": f"••••{token[-4:]}", "valid": False, "used_usd": None, "remaining_usd": None, "budget_usd": 0, "error": "Apify kullanım durumu alınamadı; bu anahtar harcama için kullanılmıyor."}

    _cache[fingerprint] = (time.monotonic() + USAGE_CACHE_SECONDS, result)
    return {**result, "slot": slot}


def _tokens(source: str = "linkedin") -> list[str]:
    tokens = apify_tokens(source)
    return list(dict.fromkeys(token.strip() for token in tokens if token and token.strip()))


def mark_scan_start() -> None:
    """Remember usage before a scan. Apify reports spend with a delay, so the scan's cost is read later as 'spend since'."""
    _last_scan.update(started_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), used_before=get_apify_quota_summary()["used_usd"])


def get_apify_quota_summary(source: str = "linkedin", force_refresh: bool = False) -> dict[str, Any]:
    tokens = _tokens(source)
    if force_refresh:
        for token in tokens:
            _cache.pop(_fingerprint(token), None)
    statuses = [_fetch_status(token, slot) for slot, token in enumerate(tokens, start=1)]
    accounts: dict[str, dict[str, Any]] = {}
    for status in statuses:
        account_id = status.get("account_id")
        if account_id and status["valid"]:
            accounts.setdefault(account_id, status)
    used = sum(float(item.get("used_usd") or 0) for item in accounts.values())
    budget = len(accounts) * FREE_PLAN_ALLOWANCE_USD
    return {
        "source": source,
        "configured_keys": len(tokens),
        "valid_keys": sum(1 for item in statuses if item["valid"]),
        "invalid_keys": sum(1 for item in statuses if not item["valid"]),
        "distinct_accounts": len(accounts),
        "budget_usd": budget,
        "theoretical_budget_usd": len(tokens) * FREE_PLAN_ALLOWANCE_USD,
        "used_usd": round(used, 4),
        "remaining_usd": round(max(0.0, budget - used), 4),
        "percent_used": round(min(100.0, used / budget * 100), 1) if budget else 0,
        "cycle_start": next((item.get("cycle_start") for item in accounts.values() if item.get("cycle_start")), None),
        "cycle_end": next((item.get("cycle_end") for item in accounts.values() if item.get("cycle_end")), None),
        "accounts": [
            {key: value for key, value in item.items() if key != "account_id"}
            for item in statuses
        ],
        "last_scan_cost_usd": round(max(0.0, used - _last_scan["used_before"]), 4) if _last_scan else None,
        "last_scan_started_at": _last_scan.get("started_at"),
        "checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "budget_note": "Uygulama güvenlik sınırı: hesap başına en fazla 5 USD. Apify plan/kredi bakiyesi değildir.",
    }


def select_apify_account(source: str, max_charge_usd: float) -> tuple[str, float]:
    """Pick a validated account with headroom; fail closed if usage cannot be verified."""
    tokens = _tokens(source)
    statuses = [_fetch_status(token, slot) for slot, token in enumerate(tokens, start=1)]
    available: list[tuple[str, float]] = []
    seen_accounts: set[str] = set()
    for token, status in zip(tokens, statuses):
        account_id = status.get("account_id")
        if not status["valid"] or not account_id or account_id in seen_accounts:
            continue
        seen_accounts.add(account_id)
        remaining = float(status.get("remaining_usd") or 0)
        if remaining > 0:
            available.append((token, remaining))
    if available:
        # Keep using the earliest configured account until its $5 local guard is exhausted.
        token, remaining = available[0]
        return token, min(max_charge_usd, remaining)
    if not tokens:
        raise RuntimeError(f"{source.capitalize()} Apify tokenı ayarlanmamış. Kaynaklar sayfasından anahtar ekleyin.")
    raise RuntimeError("Kullanılabilir doğrulanmış Apify hesabı/kotası yok. Kaynaklar sayfasındaki hesap durumlarını kontrol edin.")


def invalidate_apify_token_usage(token: str) -> None:
    """Discard cached usage immediately after an Actor attempt so the next run can rotate at the cap."""
    _cache.pop(_fingerprint(token), None)


def record_quota_snapshot(summary: dict[str, Any]) -> None:
    """Persist only aggregate spend telemetry; tokens and account IDs never enter history."""
    # The header badge asks on every page load; one row per interval is enough for the history chart.
    global _last_snapshot_at
    now = time.monotonic()
    if _last_snapshot_at and now - _last_snapshot_at < SNAPSHOT_INTERVAL_SECONDS:
        return
    _last_snapshot_at = now
    from backend.app.core.database import get_db_connection
    conn = get_db_connection()
    try:
        conn.cursor().execute(
            """INSERT INTO apify_usage_history
               (id, source, configured_keys, valid_keys, budget_usd, used_usd, remaining_usd, percent_used)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (uuid.uuid4().hex, summary.get("source", "linkedin"), int(summary.get("configured_keys", 0)),
             int(summary.get("valid_keys", 0)), float(summary.get("budget_usd", 0)), float(summary.get("used_usd", 0)),
             float(summary.get("remaining_usd", 0)), float(summary.get("percent_used", 0))),
        )
        conn.commit()
    finally:
        conn.close()


def list_quota_snapshots(limit: int = 24) -> list[dict[str, Any]]:
    from backend.app.core.database import get_db_connection
    conn = get_db_connection()
    try:
        rows = conn.cursor().execute("SELECT * FROM apify_usage_history ORDER BY checked_at DESC LIMIT ?", (max(1, min(limit, 100)),)).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()
