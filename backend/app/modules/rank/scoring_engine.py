"""
Algorithmic Job Scoring & Ranking Engine
Computes ATS Match Scores (0-100), Tiers (High, Medium, Low), Pass/Fail outcomes,
Red Flags, Skill Gaps, and Salary Benchmarks.
"""

import json
import re
from typing import Dict, Any, Optional, Tuple
from backend.app.core.config import settings
from backend.app.core.database import get_db_connection
from backend.app.modules.rank.red_flag_detector import detect_red_flags
from backend.app.modules.rank.skill_gap_analyzer import COMMON_TECH_LEXICON, analyze_skill_gaps
from backend.app.modules.rank.salary_benchmark import calculate_salary_benchmark

SKILL_POINTS = 50.0
ROLE_POINTS = 30.0
EXPERIENCE_POINTS = 20.0
# Fewer recognised skills than this is thin evidence, so the skill score stays near neutral.
MIN_SKILLS_FOR_FULL_CONFIDENCE = 3
# A senior-titled job is out of reach below this much experience, whatever the keywords say.
SENIOR_ROLE_MIN_YEARS = 3.0
SENIORITY_MISMATCH_DEDUCTION = 25.0
_SENIOR_TITLE = re.compile(r"\b(senior|sr\.?|lead|staff|principal|head of|director|architect|kıdemli)\b", re.IGNORECASE)

_SENIORITY_WORDS = {"senior", "junior", "lead", "staff", "principal", "mid", "sr", "jr", "intern", "ii", "iii", "remote"}
_ROLE_SYNONYMS = {
    "engineer": "developer", "programmer": "developer", "dev": "developer", "coder": "developer",
    "geliştirici": "developer", "mühendis": "developer", "mühendisi": "developer", "yazılımcı": "developer",
    "zhvillues": "developer", "inxhinier": "developer",
}


def _role_tokens(text: str) -> set:
    words = re.findall(r"[a-zçğıöşüë+#.]+", str(text or "").casefold().replace("back-end", "backend").replace("front-end", "frontend").replace("full-stack", "fullstack"))
    return {_ROLE_SYNONYMS.get(word, word) for word in words if len(word) > 1 and word not in _SENIORITY_WORDS}


def role_relevance(job_title: str, target_roles: list) -> Optional[float]:
    """Share of a target role's words found in the job title (best role wins); None without a target role."""
    title_tokens = _role_tokens(job_title)
    shares = [len(tokens & title_tokens) / len(tokens) for tokens in map(_role_tokens, target_roles) if tokens]
    return max(shares) if shares else None


JOB_TEXT_FIELDS = ("title", "company", "description", "location", "remote_type", "posted_date", "salary_range")


def score_job_against_profile(job_data: Dict[str, Any], candidate_profile: Dict[str, Any]) -> Dict[str, Any]:
    cand_skills = candidate_profile.get("skills") or []
    cand_exp = candidate_profile.get("years_of_experience")
    try:
        cand_exp = max(0.0, float(cand_exp)) if cand_exp not in (None, "") else None
    except (TypeError, ValueError):
        cand_exp = None
    if cand_exp == 0 and not (candidate_profile.get("experience") or candidate_profile.get("raw_cv_text")):
        cand_exp = None
    # A saved job can hold NULL in any text column; every check below expects text.
    job_data = {**job_data, **{field: job_data.get(field) or "" for field in JOB_TEXT_FIELDS}}
    desc = job_data["description"]
    title = job_data["title"]
    
    # Treat an explicit skill phrase in the saved CV as evidence, but never
    # infer skills from the job description itself.
    profile_skills = [str(skill).strip() for skill in cand_skills if str(skill).strip()]
    cv_text = str(candidate_profile.get("raw_cv_text") or "")
    cv_evidenced_skills = [
        skill for skill in COMMON_TECH_LEXICON
        if re.search(r"(?<![\w])" + re.escape(skill) + r"(?![\w])", cv_text, flags=re.IGNORECASE)
    ]
    candidate_skill_evidence = list(dict.fromkeys(profile_skills + cv_evidenced_skills))

    # 1. Skill Gap Analysis
    skill_gap_result = analyze_skill_gaps(f"{title} {desc}", candidate_skill_evidence)
    matched = skill_gap_result["matched_skills"]
    missing = skill_gap_result["missing_skills"]
    
    # Base match calculation
    total_relevant = len(matched) + len(missing)
    neutral_skill_score = SKILL_POINTS / 2
    if total_relevant > 0:
        # One matching keyword must not look like a perfect fit: thin evidence stays near neutral.
        evidence_weight = min(1.0, total_relevant / MIN_SKILLS_FOR_FULL_CONFIDENCE)
        overlap_score = (len(matched) / total_relevant) * SKILL_POINTS
        skill_score = neutral_skill_score + (overlap_score - neutral_skill_score) * evidence_weight
    else:
        skill_score = neutral_skill_score

    # Role factor: does the job title resemble a role the candidate is actually targeting?
    target_roles = [candidate_profile.get("target_role"), *(candidate_profile.get("target_roles") or [])]
    relevance = role_relevance(title, [role for role in target_roles if role])
    role_score = relevance * ROLE_POINTS if relevance is not None else ROLE_POINTS / 2

    # Experience factor
    # Missing experience is unknown, not an invented three-year background.
    exp_score = min(EXPERIENCE_POINTS, (cand_exp / 4.0) * EXPERIENCE_POINTS) if cand_exp is not None else 0.0

    seniority_deduction = (
        SENIORITY_MISMATCH_DEDUCTION
        if cand_exp is not None and cand_exp < SENIOR_ROLE_MIN_YEARS and _SENIOR_TITLE.search(title or "")
        else 0.0
    )
    final_score = round(skill_score + role_score + exp_score - seniority_deduction, 1)
    final_score = max(10.0, min(99.0, final_score))
    
    # 2. Red Flags
    red_flags = detect_red_flags(job_data, candidate_profile)
    
    score_before_risk = final_score
    # Deduct score if red flags exist
    if red_flags:
        final_score = max(10.0, round(final_score - (len(red_flags) * 15.0), 1))
        
    # 3. Match Tier & Pass/Fail status
    if final_score >= settings.MIN_ATS_MATCH_SCORE and len(red_flags) == 0:
        tier = "High"
        status = "Pass"
    elif final_score >= 50 and len(red_flags) <= 1:
        tier = "Medium"
        status = "Pass"
    else:
        tier = "Low"
        status = "Fail"
        
    # 4. Salary Benchmark
    salary_bench = calculate_salary_benchmark(title, job_data.get("location", "Remote"), cand_exp)
    
    matched_evidence = []
    for required_skill in matched:
        evidence = next((skill for skill in profile_skills if skill.lower() == required_skill.lower()), None)
        if evidence:
            matched_evidence.append({"required_skill": required_skill, "profile_evidence": evidence, "evidence_source": "profile_skill"})
        elif required_skill in cv_evidenced_skills:
            matched_evidence.append({"required_skill": required_skill, "profile_evidence": required_skill, "evidence_source": "saved_cv_text"})
    skill_gaps_result = dict(skill_gap_result)
    skill_gaps_result["matched_evidence"] = matched_evidence
    skill_gaps_result["score_explanation"] = {
        "label": "heuristic_profile_match_estimate",
        "method": "Skill overlap contributes up to 50 points, similarity between the job title and the target role up to 30, documented experience up to 20; detected risk flags reduce the estimate.",
        "skill_points": round(skill_score, 1),
        "skill_points_max": SKILL_POINTS,
        "role_points": round(role_score, 1),
        "role_points_max": ROLE_POINTS,
        "target_role_missing": relevance is None,
        "experience_points": round(exp_score, 1),
        "experience_points_max": EXPERIENCE_POINTS,
        "seniority_deduction": seniority_deduction,
        "experience_years_used": cand_exp,
        "experience_missing": cand_exp is None,
        "risk_deduction": round(score_before_risk - final_score, 1),
        "confidence": "low" if total_relevant == 0 or cand_exp is None or relevance is None or not candidate_skill_evidence else "heuristic",
        "caveat": "This is a rule-based estimate from the saved profile and job text, not an employer ATS score or probability of getting hired.",
    }

    return {
        "job_id": job_data.get("id"),
        "match_score": final_score,
        "match_tier": tier,
        "match_status": status,
        "red_flags": red_flags,
        "skill_gaps": skill_gaps_result,
        "salary_benchmark": salary_bench
    }

def rank_and_save_all_jobs(candidate_profile: Dict[str, Any]):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM scraped_jobs WHERE stale_at IS NULL OR submission_confirmed = 1")
    rows = cursor.fetchall()
    
    ranked_jobs = []
    for row in rows:
        job_data = dict(row)
        score_res = score_job_against_profile(job_data, candidate_profile)
        
        cursor.execute("""
            UPDATE scraped_jobs
            SET match_score = ?,
                match_tier = ?,
                match_status = ?,
                red_flags = ?,
                skill_gaps = ?,
                salary_benchmark_json = ?
            WHERE id = ?
        """, (
            score_res["match_score"],
            score_res["match_tier"],
            score_res["match_status"],
            json.dumps(score_res["red_flags"]),
            json.dumps(score_res["skill_gaps"]),
            json.dumps(score_res["salary_benchmark"]),
            job_data["id"]
        ))
        
        job_data.update(score_res)
        ranked_jobs.append(job_data)
        
    conn.commit()
    conn.close()
    
    # Sort descending by match_score
    ranked_jobs.sort(key=lambda x: x["match_score"], reverse=True)

    # Dispatch Telegram notifications for high-matching fresh jobs
    try:
        from backend.app.modules.outcome.telegram_bot import send_job_alert
        for item in ranked_jobs:
            if item.get("match_score", 0) >= 75 and item.get("status") in ("Draft", "New", ""):
                send_job_alert(item, item.get("match_score"))
    except Exception:
        pass

    return ranked_jobs
