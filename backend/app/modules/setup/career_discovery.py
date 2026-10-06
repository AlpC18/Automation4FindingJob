"""
Latent Career Path & Transferable Skills Discovery Engine
Adapted from MadsLorentzen/ai-job-search career path discovery concept.

Discovers non-obvious career trajectories, adjacent industry transitions,
and latent opportunities by analyzing candidate's deep project achievements,
transferable skills, and motivational drivers (energizers vs drainers).
"""

from typing import Dict, Any, List, Optional
import json
import re
from backend.app.core.llm_client import LLMUnavailable, llm_client
from backend.app.core.event_logger import agent_logger

# Domain mapping for transferable technical competencies
TECH_DOMAIN_ADJACENCIES = {
    "backend_engineering": [
        "Distributed Systems Engineer",
        "Platform / SRE Engineer",
        "Data Infrastructure Engineer",
        "Fintech Backend Specialist",
        "AI Agent Backend Architect"
    ],
    "machine_learning": [
        "Applied AI Engineer",
        "MLOps Engineer",
        "LLM Application Architect",
        "Quantitative Research Developer",
        "Data Science Strategist"
    ],
    "fullstack": [
        "Technical Product Specialist / Solutions Engineer",
        "Developer Advocate / DevRel",
        "Engineering Team Lead",
        "Founding Engineer / Head of MVP"
    ],
    "automation_devops": [
        "Cloud Architect",
        "Autonomous Systems Engineer",
        "Security & Compliance DevOps Specialist",
        "Infrastructure Security Engineer"
    ]
}

DOMAIN_SKILL_KEYWORDS = {
    "backend_engineering": {"python", "fastapi", "django", "go", "java", "sql", "postgresql", "kafka"},
    "machine_learning": {"ai", "ml", "pytorch", "tensorflow", "llm", "langchain", "rag", "scikit-learn"},
    "fullstack": {"react", "vue", "next.js", "typescript", "javascript", "tailwind"},
    "automation_devops": {"docker", "kubernetes", "aws", "gcp", "azure", "ci/cd", "terraform"},
}
MAX_LATERAL_TRACKS = 3


class CareerDiscoveryEngine:
    """Discovers high-potential career moves and hidden industry verticals."""

    def __init__(self):
        pass

    def discover_latent_opportunities(
        self,
        candidate_profile: Dict[str, Any],
        behavioral_profile: Optional[Dict[str, Any]] = None,
        preferences: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Synthesizes candidate background, hard achievements, and work style
        to map out 3 strategic tracks:
        1. Core Expansion (Immediate natural progression)
        2. Lateral Pivot (High transferable skill overlap)
        3. Emerging / Wildcard (AI & High-impact tech frontier)
        """
        skills = candidate_profile.get("skills") or []
        skills = [str(skill) for skill in skills] if isinstance(skills, list) else [str(skills)]
        years_exp = candidate_profile.get("years_of_experience")
        current_role = candidate_profile.get("target_role") or "Software Engineer"

        # Every suggestion below is tied to skills the candidate saved; nothing is assumed.
        matched: Dict[str, List[str]] = {}
        for domain, keywords in DOMAIN_SKILL_KEYWORDS.items():
            found = [skill for skill in skills if skill.lower() in keywords]
            if found:
                matched[domain] = found
        detected_domains = list(matched)

        lateral_tracks = []
        for domain, found in matched.items():
            for role in TECH_DOMAIN_ADJACENCIES[domain]:
                if role.lower() == current_role.lower() or any(track["title"] == role for track in lateral_tracks):
                    continue
                lateral_tracks.append({
                    "title": role,
                    "track_type": "lateral_pivot",
                    "match_reason": f"Kayıtlı becerilerin ({', '.join(found[:4])}) bu role aktarılabilir.",
                    "readiness_score": 80,
                })
        lateral_tracks = lateral_tracks[:MAX_LATERAL_TRACKS]

        experience = f"{years_exp} yıllık deneyimin üzerine " if years_exp not in (None, "") else ""
        core_tracks = [{
            "title": f"Senior {current_role}",
            "track_type": "core_progression",
            "match_reason": f"{experience}aynı alanda kıdem ve sorumluluk artışı.".capitalize(),
            "readiness_score": 90,
        }]

        ai_skills = matched.get("machine_learning", [])
        wildcard_tracks = [{
            "title": "LLM Application Engineer",
            "track_type": "emerging_frontier",
            "match_reason": f"Yapay zekâ becerilerin ({', '.join(ai_skills[:4])}) yeni açılan bu role doğrudan uyuyor.",
            "readiness_score": 70,
        }] if ai_skills else []

        agent_logger.log_event("CAREER_DISCOVERY", f"Discovered {len(lateral_tracks)} adjacent roles across {len(detected_domains)} domains.")

        return {
            "candidate_current_role": current_role,
            "detected_competency_domains": detected_domains,
            "core_progression": core_tracks,
            "lateral_pivots": lateral_tracks,
            "emerging_frontiers": wildcard_tracks,
            "recommended_search_queries": [f"{current_role} Remote", *(track["title"] for track in lateral_tracks)],
        }

    async def generate_ai_career_roadmaps(
        self,
        candidate_profile: Dict[str, Any],
        target_pivot: str
    ) -> Dict[str, Any]:
        """Uses LLM client to design a concrete 60-day action plan to pivot into an adjacent role."""
        prompt = f"""Target Pivot Role: {target_pivot}
Candidate Current Profile:
Target Role: {candidate_profile.get('target_role')}
Experience: {candidate_profile.get('years_of_experience')} years
Skills: {candidate_profile.get('skills')}

Please outline:
1. Key Transferable Strengths (What candidate already has)
2. Bridgeable Skill Gaps (What must be learned in 60 days)
3. High-Value Portfolio Project Blueprint (To prove capability without formal tenure)
4. Recommended Resume Re-framing Hook
Return in crisp, structured markdown."""

        res = await llm_client.generate_text(
            system_prompt="You are an elite Tech Career Strategist and Principal Engineering Manager.",
            user_prompt=prompt,
            temperature=0.4,
            apply_humanizer=False
        )
        if res["is_template_fallback"]:
            raise LLMUnavailable("Yapay zekâ sağlayıcısı yanıt vermedi; geçiş planı üretilemedi.")
        return {
            "pivot_role": target_pivot,
            "action_plan_markdown": res.get("text", "")
        }

career_discovery_engine = CareerDiscoveryEngine()
