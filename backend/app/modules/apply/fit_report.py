"""Per-job resume fit: what the posting asks for, what the CV shows, and what to change for this application.

Everything here is read from the saved profile, saved projects and the posting. The percentage is how
well the CV matches the posting, not a probability of being hired.
"""

import re
from typing import Any, Dict, List

from backend.app.modules.apply.claim_check import _COMMON_TECH, _mentions, _project_text
from backend.app.modules.rank.scoring_engine import _SENIOR_TITLE, role_relevance

MAX_PROJECTS = 2
MAX_EDITS = 3


def _years(profile: Dict[str, Any]) -> str:
    years = profile.get("years_of_experience")
    return f"{years} year{'s' if str(years) != '1' else ''} of experience" if years else ""


def build_fit_report(profile: Dict[str, Any], projects: List[Dict[str, Any]], job: Dict[str, Any]) -> Dict[str, Any]:
    skills = [str(skill) for skill in profile.get("skills") or []]
    posting = f"{job.get('title') or ''}\n{job.get('description') or ''}"
    cv_text = " ".join([str(profile.get("raw_cv_text") or ""), " ".join(skills), *(_project_text(project) for project in projects)])
    vocabulary = list(dict.fromkeys([*skills, *(tech for project in projects for tech in project.get("tech_stack") or []), *_COMMON_TECH]))
    asked = [term for term in vocabulary if len(term) > 1 and _mentions(posting, term)]
    have = [term for term in asked if _mentions(cv_text, term)]
    missing = [term for term in asked if term not in have]
    coverage = round(100 * len(have) / len(asked)) if asked else None

    roles = [role for role in [profile.get("target_role"), *(profile.get("target_roles") or [])] if role]
    relevance = role_relevance(job.get("title") or "", roles)
    senior = bool(_SENIOR_TITLE.search(job.get("title") or ""))

    ranked = sorted(projects, key=lambda project: -sum(1 for term in have if _mentions(_project_text(project), term)))
    best = [project for project in ranked if any(_mentions(_project_text(project), term) for term in have)][:MAX_PROJECTS]
    ordered_skills = [*[skill for skill in skills if skill in have], *[skill for skill in skills if skill not in have]]
    summary = ", ".join(part for part in [
        f"{job.get('title') or roles[0] if roles else 'Developer'} candidate",
        _years(profile),
        f"working with {', '.join(have[:5])}" if have else "",
    ] if part) + "."

    edits = []
    if have:
        edits.append(f"Put these first in your skills line, they are named in the posting: {', '.join(have[:6])}.")
    if missing:
        edits.append(f"The posting asks for {', '.join(missing[:5])}, which your CV does not show. Add one only if you have really used it; otherwise leave it out.")
    if best:
        edits.append(f"Lead with {' and '.join(str(project.get('title')).split('/')[0].strip() for project in best)}: of your saved projects they share the most with this posting.")
    if not str(profile.get("summary") or "").strip():
        edits.append("Your CV has no summary. Use the suggested line below as the first line for this application.")
    if senior and (profile.get("years_of_experience") or 0) < 3:
        edits.append("This is a senior title and your CV shows under three years. Expect a low reply rate; apply only if the posting's requirements read lower than its title.")

    return {
        "job_id": job.get("id"), "title": job.get("title"), "company": job.get("company"),
        "match_percent": job.get("match_score"),
        "breakdown": {
            "skills_named_in_posting": len(asked), "skills_you_show": len(have), "skill_coverage_percent": coverage,
            "role_match_percent": round(relevance * 100) if relevance is not None else None, "senior_title": senior,
        },
        "keywords_you_have": have, "keywords_missing": missing,
        "edits": edits[:MAX_EDITS] if not senior else [*edits[:MAX_EDITS - 1], edits[-1]],
        "tailored": {
            "summary_line": re.sub(r"\s+", " ", summary), "skills_order": ordered_skills[:15],
            "projects_to_show": [{"title": project.get("title"), "tech_stack": project.get("tech_stack") or []} for project in best],
        },
        "note": "The percentage measures how closely your CV matches this posting. It is not a chance of being hired.",
    }
