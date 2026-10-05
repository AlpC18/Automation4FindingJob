"""
Dynamic Skill Gap Analyzer & GitHub Project Suggester
Extracts missing tech stack items and suggests tangible GitHub mini-projects or modules.
"""

from typing import List, Dict, Any

COMMON_TECH_LEXICON = [
    "python", "fastapi", "next.js", "nextjs", "react", "typescript", "javascript",
    "docker", "kubernetes", "aws", "gcp", "azure", "postgresql", "mysql", "redis",
    "chromadb", "langchain", "langgraph", "graphql", "playwright", "selenium",
    "kafka", "rabbitmq", "ci/cd", "github actions", "rest api", "tailwind", "linux"
]

def analyze_skill_gaps(job_description: str, candidate_skills: List[str]) -> Dict[str, Any]:
    desc_lower = job_description.lower()
    cand_skills_lower = {s.lower() for s in candidate_skills}
    
    # Identify required skills from lexicon
    required_in_job = []
    for tech in COMMON_TECH_LEXICON:
        if tech in desc_lower:
            required_in_job.append(tech)
            
    # Gaps are required skills not in candidate skills
    missing_skills = [tech for tech in required_in_job if tech not in cand_skills_lower]
    matched_skills = [tech for tech in required_in_job if tech in cand_skills_lower]
    
    # Generate tailored GitHub mini-project suggestions to bridge the gap
    recommendations = []
    if missing_skills:
        primary_gap = missing_skills[0].upper()
        recommendations.append(
            f"GitHub Proje Eklemesi: Portfolyonuza '{primary_gap}' odaklı bir mikro-servis veya demo modülü ekleyin."
        )
        if len(missing_skills) > 1:
            secondary_gap = missing_skills[1].upper()
            recommendations.append(
                f"Entegrasyon Önerisi: Mevcut projelerinizden birine '{secondary_gap}' entegrasyonu (örn. Docker container veya caching katmanı) ekleyerek CV'nizi güncelleyin."
            )
    else:
        recommendations.append("Harika eşleşme! Tüm temel teknik gereksinimler profilinizde mevcut.")

    return {
        "matched_skills": matched_skills,
        "missing_skills": missing_skills,
        "gap_count": len(missing_skills),
        "actionable_recommendations": recommendations
    }
