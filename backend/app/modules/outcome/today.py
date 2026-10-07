"""Today's action list: one prioritized queue built from every workflow's pending work."""

from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from backend.app.core.database import get_db_connection

HIGH_MATCH_SCORE = 70
MAX_ACTIONS_PER_KIND = 5
CLOSING_SOON_DAYS = 3

# Order is the priority: a recruiter waiting for an answer outranks a new listing.
ACTION_KINDS = (
    "inbox_reply",
    "follow_up_due",
    "confirm_submission",
    "approve_draft",
    "closing_soon",
    "new_matches",
)


def next_steps(job: Dict[str, Any]) -> List[Dict[str, str]]:
    """What a job's current stage unlocks: finishing one step always points at the next one."""
    status = job.get("status") or "Draft"
    if status == "Applied" and job.get("submission_confirmed"):
        return [{"kind": "follow_up", "href": "/follow-up"}]
    return []


def _action(kind: str, key: Any, href: str, title: str = "", company: str = "", **meta: Any) -> Dict[str, Any]:
    return {"id": f"{kind}:{key}", "kind": kind, "href": href, "title": title or "", "company": company or "", **meta}


def build_today_actions(
    *,
    board: Dict[str, List[Dict[str, Any]]],
    auto_queue: List[Dict[str, Any]],
    follow_ups: List[Dict[str, Any]],
    inbox_messages: List[Dict[str, Any]],
    new_match_count: int,
    closing_soon: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Turn raw workflow state into the ordered list of things the candidate should do next."""
    found: Dict[str, List[Dict[str, Any]]] = {kind: [] for kind in ACTION_KINDS}

    for message in inbox_messages:
        if message.get("status") == "UNREAD" and message.get("classification") != "REJECTION":
            found["inbox_reply"].append(_action(
                "inbox_reply", message.get("id"), "/inbox", message.get("subject"),
                message.get("sender_name") or message.get("sender_email"),
                classification=message.get("classification"),
            ))

    follow_up_jobs = set()
    for item in follow_ups:
        job_id = item.get("job_key") or item.get("job_id")
        if job_id in follow_up_jobs:  # day-7 and day-14 reminders for one job are a single task
            continue
        follow_up_jobs.add(job_id)
        found["follow_up_due"].append(_action(
            "follow_up_due", job_id, "/follow-up", item.get("title"), item.get("company"),
            days=item.get("days_since_applied") or item.get("due_day"),
        ))

    for item in auto_queue:
        if item.get("status") == "awaiting_user_submission":
            found["confirm_submission"].append(_action(
                "confirm_submission", f"auto:{item.get('job_key')}", "/auto-apply", item.get("title"), item.get("company"),
            ))
        elif item.get("status") == "pending_approval":
            found["approve_draft"].append(_action(
                "approve_draft", f"auto:{item.get('job_key')}", "/auto-apply", item.get("title"), item.get("company"),
            ))

    for job in board.get("Applied", []):
        if not job.get("submission_confirmed"):
            found["confirm_submission"].append(_action(
                "confirm_submission", job.get("id"), "/kanban", job.get("title"), job.get("company"),
            ))
    for job in board.get("Human Review", []):
        found["approve_draft"].append(_action("approve_draft", job.get("id"), "/kanban", job.get("title"), job.get("company")))
    for job in closing_soon:
        found["closing_soon"].append(_action(
            "closing_soon", job.get("id"), f"/jobs?scope=current&minMatch={HIGH_MATCH_SCORE}", job.get("title"), job.get("company"),
            days=job.get("days_left"),
        ))

    if new_match_count > 0:
        found["new_matches"].append(_action(
            "new_matches", "feed", f"/jobs?scope=current&minMatch={HIGH_MATCH_SCORE}", count=new_match_count,
        ))

    counts = {kind: len(items) for kind, items in found.items() if items}
    actions = [action for kind in ACTION_KINDS for action in found[kind][:MAX_ACTIONS_PER_KIND]]
    return {"actions": actions, "counts": counts, "total": sum(counts.values())}


def _count_new_matches() -> int:
    conn = get_db_connection()
    try:
        row = conn.cursor().execute(
            """SELECT COUNT(*) AS total FROM scraped_jobs
               WHERE stale_at IS NULL
                 AND COALESCE(status, 'Draft') IN ('Draft', 'New', '')
                 AND COALESCE(cover_letter, '') = ''
                 AND match_score >= ?""",
            (HIGH_MATCH_SCORE,),
        ).fetchone()
        return int(row["total"] if row else 0)
    finally:
        conn.close()


def _closing_soon_jobs(today: Optional[date] = None) -> List[Dict[str, Any]]:
    """High-match jobs not yet acted on whose application deadline falls within the next few days."""
    today = today or datetime.now().date()
    conn = get_db_connection()
    try:
        rows = conn.cursor().execute(
            """SELECT id, title, company, deadline FROM scraped_jobs
               WHERE stale_at IS NULL
                 AND COALESCE(status, 'Draft') IN ('Draft', 'New', '')
                 AND match_score >= ?
                 AND deadline >= ? AND deadline <= ?
               ORDER BY deadline ASC, match_score DESC""",
            (HIGH_MATCH_SCORE, today.isoformat(), (today + timedelta(days=CLOSING_SOON_DAYS)).isoformat()),
        ).fetchall()
    finally:
        conn.close()
    return [{**dict(row), "days_left": (date.fromisoformat(row["deadline"]) - today).days} for row in rows]


def get_today_actions() -> Dict[str, Any]:
    # Imported here: these modules pull in the scraping/LLM stack, which the pure builder does not need.
    from backend.app.modules.apply.auto_apply_pipeline import auto_apply_pipeline
    from backend.app.modules.outcome.follow_up_scheduler import get_pending_follow_ups
    from backend.app.modules.outcome.inbox_agent import inbox_agent
    from backend.app.modules.outcome.kanban_manager import kanban_manager

    return build_today_actions(
        board=kanban_manager.get_kanban_board(),
        auto_queue=auto_apply_pipeline.list_queue(),
        follow_ups=get_pending_follow_ups(),
        inbox_messages=inbox_agent.get_all_messages(status="UNREAD"),  # the builder only acts on unread mail
        new_match_count=_count_new_matches(),
        closing_soon=_closing_soon_jobs(),
    )
