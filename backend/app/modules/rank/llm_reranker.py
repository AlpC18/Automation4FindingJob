"""AI review of the best rule-ranked jobs.

The rule score is cheap but crude (keyword overlap). The top of that list is re-read
by the configured language model together with the candidate's CV, which returns a
calibrated score, a one-sentence verdict, strengths and gaps. Reviews are cached per
job and profile version, so re-ranking does not pay for the same judgement twice.
"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

from backend.app.core.config import settings
from backend.app.core.database import get_db_connection
from backend.app.core.llm_client import is_template_engine, llm_client
from backend.app.core.profile_versioning import ensure_profile_version

logger = logging.getLogger(__name__)

REVIEW_LIMIT = 20
MAX_PARALLEL_REVIEWS = 4
CV_CHARS = 3500
JOB_CHARS = 3000

SYSTEM_PROMPT = (
    "You are a strict technical recruiter. Judge how well ONE candidate fits ONE job, using only the "
    "candidate profile and the job text given. Weigh, in order: whether the role is the kind of work the "
    "candidate targets and can do; whether the required years of experience and seniority are within reach "
    "(a student or junior applying to a senior role is a poor fit even with matching keywords); skills the "
    "job requires that the profile shows evidence of; language and location requirements. Never invent "
    "experience. Reply with ONLY a JSON object: "
    '{"score": <integer 0-100>, "verdict": "<one sentence in Turkish>", '
    '"strengths": ["<up to 3 short Turkish phrases>"], "gaps": ["<up to 3 short Turkish phrases>"]}. '
    "Score guide: 85+ strong fit worth applying today; 70-84 good fit; 50-69 partial; below 50 poor."
)


def _candidate_brief(profile: Dict[str, Any]) -> str:
    roles = [profile.get("target_role"), *(profile.get("target_roles") or [])]
    return "\n".join([
        f"Target roles: {', '.join(dict.fromkeys(role for role in roles if role)) or 'not specified'}",
        f"Years of professional experience: {profile.get('years_of_experience') if profile.get('years_of_experience') not in (None, '') else 'not specified'}",
        f"Location: {profile.get('location') or 'not specified'} | Work preference: {profile.get('work_preference') or 'not specified'}",
        f"Languages: {', '.join(profile.get('languages') or []) or 'not specified'}",
        f"Skills: {', '.join(str(skill) for skill in (profile.get('skills') or [])) or 'not specified'}",
        f"CV text:\n{str(profile.get('raw_cv_text') or '')[:CV_CHARS]}",
    ])


def _job_brief(job: Dict[str, Any]) -> str:
    return "\n".join([
        f"Title: {job.get('title')}", f"Company: {job.get('company')}",
        f"Location: {job.get('location')} | Work mode: {job.get('remote_type')}",
        f"Description:\n{str(job.get('description') or '')[:JOB_CHARS]}",
    ])


def parse_review(raw: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Validate the model's JSON; None when it is unusable (the rule score then stands)."""
    try:
        score = float(raw.get("score"))
    except (TypeError, ValueError, AttributeError):
        return None
    if not 0 <= score <= 100:
        return None

    def phrases(value: Any) -> List[str]:
        return [str(item).strip()[:160] for item in value if str(item).strip()][:3] if isinstance(value, list) else []

    return {
        "score": round(score, 1),
        "verdict": str(raw.get("verdict") or "").strip()[:400],
        "strengths": phrases(raw.get("strengths")),
        "gaps": phrases(raw.get("gaps")),
    }


def _tier(score: float, red_flags: List[Any]) -> tuple:
    if score >= settings.MIN_ATS_MATCH_SCORE and not red_flags:
        return "High", "Pass"
    if score >= 50 and len(red_flags) <= 1:
        return "Medium", "Pass"
    return "Low", "Fail"


def _load_candidates(limit: int) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    try:
        rows = conn.cursor().execute(
            """SELECT id, title, company, location, remote_type, description, match_score, red_flags, ai_review_json
               FROM scraped_jobs
               WHERE stale_at IS NULL AND COALESCE(status, 'Draft') IN ('Draft', 'New', '')
               ORDER BY match_score DESC LIMIT ?""",
            (limit,),
        ).fetchall()
    finally:
        conn.close()
    return [dict(row) for row in rows]


def _save_reviews(reviews: Dict[str, Dict[str, Any]], jobs: List[Dict[str, Any]]) -> None:
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        for job in jobs:
            review = reviews.get(job["id"])
            if not review:
                continue
            try:
                red_flags = json.loads(job.get("red_flags") or "[]")
            except (TypeError, json.JSONDecodeError):
                red_flags = []
            tier, status = _tier(review["score"], red_flags)
            cursor.execute(
                "UPDATE scraped_jobs SET match_score = ?, match_tier = ?, match_status = ?, ai_review_json = ? WHERE id = ?",
                (review["score"], tier, status, json.dumps(review, ensure_ascii=False), job["id"]),
            )
        conn.commit()
    finally:
        conn.close()


async def review_top_jobs(profile: Dict[str, Any], limit: int = REVIEW_LIMIT) -> Dict[str, Any]:
    """Re-score the best rule-ranked jobs with the language model. Never raises: ranking must not fail because of it."""
    if llm_client.get_effective_provider() == "local_fallback":
        return {"status": "skipped", "reason": "no_ai_provider", "reviewed": 0, "reused": 0, "failed": 0}
    jobs = _load_candidates(limit)
    profile_version = ensure_profile_version(profile)
    candidate = _candidate_brief(profile)
    reviews: Dict[str, Dict[str, Any]] = {}
    pending = []
    for job in jobs:
        try:
            cached = json.loads(job.get("ai_review_json") or "{}")
        except (TypeError, json.JSONDecodeError):
            cached = {}
        if cached.get("profile_version") == profile_version and "score" in cached:
            reviews[job["id"]] = cached  # the rule pass just overwrote the score; put the cached judgement back
        else:
            pending.append(job)

    limiter = asyncio.Semaphore(MAX_PARALLEL_REVIEWS)

    async def review(job: Dict[str, Any]) -> None:
        async with limiter:
            try:
                result = await llm_client.generate_text(
                    SYSTEM_PROMPT, f"CANDIDATE\n{candidate}\n\nJOB\n{_job_brief(job)}", apply_humanizer=False,
                )
            except Exception as exc:  # one job's failure must not cancel the other reviews
                logger.warning("AI review failed for job %s (%s).", job["id"], type(exc).__name__)
                return
        if is_template_engine(result.get("provider_used")):
            return  # the provider did not answer; template text is not a judgement
        parsed = parse_review(llm_client.extract_json(result.get("text") or ""))
        if parsed:
            reviews[job["id"]] = {
                **parsed, "rule_score": job.get("match_score"), "provider": result.get("provider_used"),
                "profile_version": profile_version,
            }

    await asyncio.gather(*(review(job) for job in pending))
    _save_reviews(reviews, jobs)
    reviewed = sum(1 for job in pending if job["id"] in reviews)
    return {
        "status": "success" if reviewed or not pending else "failed",
        "reviewed": reviewed, "reused": len(jobs) - len(pending), "failed": len(pending) - reviewed,
    }
