"""Fact-preserving, deterministic resume tailoring for a specific job."""

import re
from typing import Any, Dict, Iterable, List, Tuple


_WORD = re.compile(r"[^\W_]+(?:[+#.-][^\W_]+)*", re.UNICODE)
_STOP_WORDS = {
    "and", "are", "for", "from", "have", "into", "our", "the", "their", "this", "with",
    "you", "your", "will", "who", "work", "role", "team", "job", "experience",
    "ve", "ile", "için", "olan", "olarak", "bir", "bu", "çok", "deneyim", "pozisyon",
}


def _tokens(value: Any) -> set[str]:
    if not isinstance(value, str):
        return set()
    return {token.casefold() for token in _WORD.findall(value) if len(token) > 1 and token.casefold() not in _STOP_WORDS}


def _ranked(items: Iterable[Any], title_terms: set[str], description_terms: set[str], text_of) -> List[Tuple[int, Any]]:
    ranked = []
    for index, item in enumerate(items):
        terms = _tokens(text_of(item))
        score = len(terms & title_terms) * 3 + len(terms & description_terms)
        ranked.append((index, score, item))
    ranked.sort(key=lambda entry: (-entry[1], entry[0]))
    return [(score, item) for _, score, item in ranked]


def build_tailored_resume_profile(candidate_profile: Dict[str, Any], job_data: Dict[str, Any]) -> Dict[str, Any]:
    """Prioritize matching facts without rewriting or adding candidate claims."""
    source = dict(candidate_profile or {})
    title_terms = _tokens(job_data.get("title", ""))
    description_terms = _tokens(job_data.get("description", ""))

    skill_results = _ranked(
        source.get("skills") or [], title_terms, description_terms, lambda skill: str(skill)
    )
    experience = []
    for original in source.get("experience") or []:
        if not isinstance(original, dict):
            continue
        item = dict(original)
        bullets = item.get("bullets") or []
        ranked_bullets = _ranked(
            bullets, title_terms, description_terms, lambda bullet: str(bullet)
        )
        item["bullets"] = [bullet for _, bullet in ranked_bullets]
        experience.append(item)

    tailored = {
        **source,
        "skills": [skill for _, skill in skill_results],
        "experience": experience,
        "education": [dict(item) if isinstance(item, dict) else item for item in (source.get("education") or [])],
        "projects": [dict(item) if isinstance(item, dict) else item for item in (source.get("projects") or [])],
    }
    matched_skills = [skill for score, skill in skill_results if score > 0]

    try:
        gaps = job_data.get("skill_gaps") or "{}"
        if isinstance(gaps, str):
            import json
            gaps = json.loads(gaps)
        missing_skills = gaps.get("missing_skills", []) if isinstance(gaps, dict) else []
    except (TypeError, ValueError):
        missing_skills = []

    return {
        "profile": tailored,
        "tailoring": {
            "role": job_data.get("title", ""),
            "matched_skills": matched_skills,
            "skills_to_highlight": matched_skills[:8],
            "gaps_to_address_honestly": missing_skills[:8] if isinstance(missing_skills, list) else [],
            "source": job_data.get("platform", ""),
            "method": "fact-preserving keyword prioritization",
            "facts_rewritten": False,
        },
    }
