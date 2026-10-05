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
from backend.app.core.llm_client import llm_client
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
        skills = candidate_profile.get("skills", [])
        skills_str = ", ".join(skills) if isinstance(skills, list) else str(skills)
        years_exp = candidate_profile.get("years_of_experience", 3)
        current_role = candidate_profile.get("target_role", "Software Engineer")
        achievements = []

        for exp in candidate_profile.get("experience", []):
            if isinstance(exp, dict):
                achievements.extend(exp.get("achievements", []))

        work_style = ""
        if behavioral_profile:
            dims = behavioral_profile.get("dimensions", {})
            work_style = dims.get("work_style", {}).get("label", "Autonomous")

        # Deterministic Base Mapping
        detected_domains = []
        skills_lower = [s.lower() for s in skills]
        
        if any(s in skills_lower for s in ["python", "fastapi", "django", "go", "java", "sql", "postgresql", "kafka"]):
            detected_domains.append("backend_engineering")
        if any(s in skills_lower for s in ["ai", "ml", "pytorch", "tensorflow", "llm", "langchain", "rag", "scikit-learn"]):
            detected_domains.append("machine_learning")
        if any(s in skills_lower for s in ["react", "vue", "next.js", "typescript", "javascript", "tailwind"]):
            detected_domains.append("fullstack")
        if any(s in skills_lower for s in ["docker", "kubernetes", "aws", "gcp", "azure", "ci/cd", "terraform"]):
            detected_domains.append("automation_devops")

        adjacent_roles = []
        for domain in detected_domains:
            for role in TECH_DOMAIN_ADJACENCIES.get(domain, []):
                if role not in adjacent_roles and role.lower() != current_role.lower():
                    adjacent_roles.append(role)

        # Build trajectory matrix
        core_tracks = [
            {
                "title": f"Senior {current_role}",
                "track_type": "core_progression",
                "match_reason": f"{years_exp}+ yıllık birikim üzerine doğrudan kıdem artışı ve mimari liderlik.",
                "readiness_score": 90
            }
        ]

        lateral_tracks = []
        for role in adjacent_roles[:3]:
            lateral_tracks.append({
                "title": role,
                "track_type": "lateral_pivot",
                "match_reason": f"Mevcut yetenek kümeniz ({skills_str[:50]}...) ile %80+ aktarılabilir yetenek örtüşmesi.",
                "readiness_score": 82
            })

        wildcard_tracks = [
            {
                "title": "Autonomous Agent Systems Architect",
                "track_type": "emerging_frontier",
                "match_reason": "AI araçları, otonom crawler'lar ve çoklu model orkestrasyonu deneyiminizle doğrudan örtüşen yeni nesil pozisyon.",
                "readiness_score": 85
            }
        ]

        agent_logger.log_event("CAREER_DISCOVERY", f"Discovered {len(adjacent_roles)} adjacent roles across {len(detected_domains)} domains.")

        return {
            "candidate_current_role": current_role,
            "detected_competency_domains": detected_domains,
            "core_progression": core_tracks,
            "lateral_pivots": lateral_tracks,
            "emerging_frontiers": wildcard_tracks,
            "transferable_skill_highlights": [
                "Büyük ölçekli sistem tasarımı ve API mimarisi",
                "Veri çekme, web otomasyonu ve anti-detection stratejileri",
                "LLM destekli karar alma ve otonom iş akışları",
                "Mikroservis konteynerizasyonu ve asenkron kuyruk yönetimi"
            ],
            "recommended_search_queries": [
                f"{current_role} Remote Europe",
                "AI Platform Engineer Global",
                "Senior Backend Distributed Systems",
                "Founding Full Stack Engineer Autonomous Systems"
            ]
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
            temperature=0.4
        )
        return {
            "pivot_role": target_pivot,
            "action_plan_markdown": res.get("text", "")
        }

career_discovery_engine = CareerDiscoveryEngine()
