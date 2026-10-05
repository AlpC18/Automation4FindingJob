"""
Persistent Seen Jobs Tracker
Adapted from MadsLorentzen/ai-job-search seen_jobs.json concept.

Maintains a persistent record of all jobs encountered across scrape runs.
Key differences from our existing DB-based approach:
- Uses canonical dedup keys (job_key.py) for consistent deduplication
- Tracks job lifecycle: new → ranked → applied → skipped
- Records first_seen timestamp, portal source, and scoring history
- Supports deadline-based expiry sweeps
- Export/import JSON for portability

Storage: JSON file at data/seen_jobs.json
"""

import json
from datetime import datetime, date
from pathlib import Path
from typing import Dict, Any, List, Optional, Set, Tuple

from backend.app.tools.job_key import make_job_key
from backend.app.core.config import settings
from backend.app.core.database import get_db_connection, is_postgres_database
from backend.app.core.event_logger import agent_logger
from backend.app.core.tenant import get_tenant_id

SEEN_JOBS_PATH = settings.DATA_PATH / "seen_jobs.json"


class SeenJobsTracker:
    """Persistent dedup tracker for seen job postings."""

    def __init__(self, path: Path = SEEN_JOBS_PATH):
        self.path = path
        self._use_database = is_postgres_database()
        self._scope_data: Dict[str, Dict[str, Dict[str, Any]]] = {}
        self._loaded_scopes: Set[str] = set()

    def _scope(self):
        return get_tenant_id() or "__shared__"

    def _scoped_path(self):
        tenant_id = get_tenant_id()
        if not tenant_id:
            return self.path
        safe_id = "".join(ch for ch in tenant_id if ch.isalnum())
        return settings.DATA_PATH / "tenants" / safe_id / "seen_jobs.json"

    @property
    def _data(self):
        scope = self._scope()
        if scope not in self._loaded_scopes:
            self._loaded_scopes.add(scope)
            self._scope_data[scope] = {}
            self._load()
        return self._scope_data[scope]

    @_data.setter
    def _data(self, value):
        scope = self._scope()
        self._scope_data[scope] = value
        self._loaded_scopes.add(scope)

    def _load(self):
        """Load seen jobs from disk."""
        if self._use_database:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS seen_jobs (
                    id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("SELECT id, payload FROM seen_jobs")
            rows = cursor.fetchall()
            conn.commit()
            conn.close()
            for row in rows:
                try:
                    self._data[row["id"]] = json.loads(row["payload"])
                except (TypeError, json.JSONDecodeError):
                    continue
            return

        path = self._scoped_path()
        if path.is_file():
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    self._data = raw
                elif isinstance(raw, list):
                    # Migration from old list format
                    for entry in raw:
                        key = make_job_key(
                            entry.get("company", ""),
                            entry.get("title", ""),
                            entry.get("url", "")
                        )
                        self._data[key] = entry
                    self._save()
            except (json.JSONDecodeError, OSError) as e:
                agent_logger.log_event("SEEN_JOBS", f"Error loading seen_jobs.json: {e}")
                self._data = {}

    def _save(self):
        """Persist to disk."""
        if self._use_database:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS seen_jobs (
                    id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("DELETE FROM seen_jobs")
            cursor.executemany(
                "INSERT INTO seen_jobs (id, payload) VALUES (?, ?)",
                [(key, json.dumps(value, ensure_ascii=False)) for key, value in self._data.items()],
            )
            conn.commit()
            conn.close()
            return

        path = self._scoped_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

    def is_seen(self, company: str, title: str, url: str = "") -> bool:
        """Check if a job has been seen before."""
        key = make_job_key(company, title, url)
        return key in self._data

    def get_key(self, company: str, title: str, url: str = "") -> str:
        """Get the canonical key for a job posting."""
        return make_job_key(company, title, url)

    def add(
        self,
        company: str,
        title: str,
        url: str = "",
        portal: str = "",
        location: str = "",
        extra: Optional[Dict[str, Any]] = None,
    ) -> Tuple[str, bool]:
        """
        Add a job to the seen list.

        Returns:
            (key, is_new): The canonical key and whether this was a new entry.
        """
        key = make_job_key(company, title, url)
        is_new = key not in self._data

        if is_new:
            self._data[key] = {
                "company": company,
                "title": title,
                "url": url,
                "portal": portal,
                "location": location,
                "status": "new",
                "first_seen": datetime.now().isoformat(),
                "last_seen": datetime.now().isoformat(),
                **(extra or {}),
            }
            agent_logger.log_event(
                "SEEN_JOBS",
                f"NEW job: {company} — {title} [{portal}]"
            )
        else:
            # Update last_seen timestamp
            self._data[key]["last_seen"] = datetime.now().isoformat()

        self._save()
        return key, is_new

    def mark_status(self, key: str, status: str, notes: Optional[str] = None) -> bool:
        """
        Update the status of a seen job.

        Valid statuses: new, ranked, applied, skipped, expired, rejected,
                       no_response, hired, interview
        """
        if key not in self._data:
            return False
        self._data[key]["status"] = status
        self._data[key]["status_updated_at"] = datetime.now().isoformat()
        if notes:
            self._data[key]["status_notes"] = notes
        self._save()
        return True

    def mark_applied(
        self,
        key: str,
        notes: Optional[str] = None,
        confirmed: bool = False,
    ) -> bool:
        """Record the Kanban Applied stage without fabricating portal success.

        ``confirmed`` is intentionally explicit. A drag-and-drop or simulated
        browser flow can move a job to the Applied stage while the external
        portal submission is still unverified; only the verified path sets it
        to true and records an application timestamp.
        """
        if key not in self._data:
            return False
        entry = self._data[key]
        entry["status"] = "applied"
        entry["status_updated_at"] = datetime.now().isoformat()
        entry["submission_confirmed"] = bool(confirmed)
        entry["application_execution_mode"] = "live" if confirmed else "simulation"
        if confirmed:
            entry["applied_at"] = datetime.now().isoformat()
        if notes:
            entry["status_notes"] = notes
        self._save()
        return True

    def set_score(
        self,
        key: str,
        score: float,
        strengths: Optional[List[str]] = None,
        gaps: Optional[List[str]] = None,
        deadline: Optional[str] = None,
    ) -> bool:
        """Record ranking score and evaluation for a job."""
        if key not in self._data:
            return False

        self._data[key]["match_score"] = score
        self._data[key]["scored_at"] = datetime.now().isoformat()

        if strengths is not None:
            self._data[key]["strengths"] = strengths
        if gaps is not None:
            self._data[key]["gaps"] = gaps
        if deadline is not None:
            self._data[key]["deadline"] = deadline

        if self._data[key].get("status") == "new":
            self._data[key]["status"] = "ranked"

        self._save()
        return True

    def get_new_jobs(self) -> Dict[str, Dict[str, Any]]:
        """Get all jobs with status 'new' (not yet ranked or acted on)."""
        return {
            k: v for k, v in self._data.items()
            if v.get("status") == "new"
        }

    def get_ranked_jobs(self, min_score: float = 0.0) -> Dict[str, Dict[str, Any]]:
        """Get ranked jobs above a minimum score."""
        return {
            k: v for k, v in self._data.items()
            if v.get("status") == "ranked"
            and v.get("match_score", 0) >= min_score
        }

    def sweep_expired(self, dry_run: bool = True) -> List[Dict[str, Any]]:
        """
        Check ranked jobs for expired deadlines and mark them.

        Returns list of expired entries.
        """
        expired = []
        today = date.today()

        for key, entry in self._data.items():
            if entry.get("status") not in ("ranked", "new"):
                continue

            deadline_str = entry.get("deadline")
            if not deadline_str:
                continue

            try:
                deadline_date = date.fromisoformat(deadline_str.strip())
            except (ValueError, AttributeError):
                continue

            if deadline_date < today:
                expired.append({
                    "key": key,
                    "company": entry.get("company"),
                    "title": entry.get("title"),
                    "deadline": deadline_str,
                    "days_past": (today - deadline_date).days,
                })
                if not dry_run:
                    entry["status"] = "expired"
                    entry["expired_at"] = datetime.now().isoformat()

        if not dry_run and expired:
            self._save()
            agent_logger.log_event(
                "SEEN_JOBS",
                f"Expired {len(expired)} jobs past their deadline"
            )

        return expired

    def get_closing_soon(self, days: int = 7) -> List[Dict[str, Any]]:
        """Get ranked jobs with deadlines within the next N days."""
        closing = []
        today = date.today()

        for key, entry in self._data.items():
            if entry.get("status") not in ("ranked", "new"):
                continue

            deadline_str = entry.get("deadline")
            if not deadline_str:
                continue

            try:
                deadline_date = date.fromisoformat(deadline_str.strip())
            except (ValueError, AttributeError):
                continue

            days_left = (deadline_date - today).days
            if 0 <= days_left <= days:
                closing.append({
                    "key": key,
                    "company": entry.get("company"),
                    "title": entry.get("title"),
                    "deadline": deadline_str,
                    "days_left": days_left,
                    "match_score": entry.get("match_score", 0),
                })

        return sorted(closing, key=lambda x: x["days_left"])

    def stats(self) -> Dict[str, Any]:
        """Return tracker statistics."""
        status_counts: Dict[str, int] = {}
        portal_counts: Dict[str, int] = {}

        for entry in self._data.values():
            status = entry.get("status", "unknown")
            status_counts[status] = status_counts.get(status, 0) + 1

            portal = entry.get("portal", "unknown")
            portal_counts[portal] = portal_counts.get(portal, 0) + 1

        return {
            "total_jobs": len(self._data),
            "by_status": status_counts,
            "by_portal": portal_counts,
        }

    def export_json(self) -> str:
        """Export all data as JSON string."""
        return json.dumps(self._data, ensure_ascii=False, indent=2)

    def get_all(self) -> Dict[str, Dict[str, Any]]:
        """Get all tracked jobs."""
        return dict(self._data)


# Module-level singleton
seen_jobs_tracker = SeenJobsTracker()
