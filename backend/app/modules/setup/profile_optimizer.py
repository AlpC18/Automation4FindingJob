"""
LinkedIn & GitHub Profile Optimization Agent (Reverse Recruitment)
Transforms candidate web presence to attract inbound recruiter discovery:
- LinkedIn Headline, About Section, and Skills Re-writer
- GitHub Public Repository Auditor & Showcase Project Generator
- ATS Keyword Alignment for Inbound Search Rank
"""

from typing import Dict, Any, List, Optional
from backend.app.core.llm_client import llm_client
from backend.app.core.event_logger import agent_logger

class ProfileOptimizerAgent:
    """Optimizes LinkedIn & GitHub assets for high inbound recruiter conversion."""

    async def optimize_linkedin_profile(
        self,
        candidate_profile: Dict[str, Any],
        target_role: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generates high-conversion LinkedIn headline, about section, and strategic keywords."""
        role = target_role or candidate_profile.get("target_role", "Software Engineer")
        skills = ", ".join(candidate_profile.get("skills", [])[:10])
        exp_years = candidate_profile.get("years_of_experience", 3)
        
        prompt = f"""
Candidate Info:
Target Role: {role}
Years of Experience: {exp_years}
Core Skills: {skills}

Please provide an optimized LinkedIn profile upgrade in JSON format with keys:
1. "headlines": Array of 3 distinct, high-impact headlines (e.g. Formula: [Role] | [Specialization/Stack] | [Impact/Value Proposition], max 120 chars each, NO cheesy buzzwords like 'rockstar' or 'ninja').
2. "about_section": A 3-paragraph compelling first-person 'About' narrative that hooks technical recruiters. First paragraph hook, second paragraph engineering achievements & tech stack, third paragraph what problems you love solving + contact CTA.
3. "featured_skills": Top 10 skill keywords to pin in the LinkedIn skills section to maximize recruiter search SEO.
4. "profile_tips": 3 actionable tips to increase search appearances (e.g. Creator mode, recommendation asks).
"""
        res = await llm_client.generate_json(
            system_prompt="You are a Principal Tech Recruiter and Personal Branding Strategist for elite software engineers.",
            user_prompt=prompt
        )

        agent_logger.log_event("PROFILE_OPTIMIZER", f"Generated LinkedIn optimization for role: {role}")
        return res if res else {
            "headlines": [
                f"{role} | Distributed Systems & AI Systems | Python, FastAPI, Docker",
                f"Senior {role} • Building Scalable Autonomous Agents & Web Architectures",
                f"{role} @ High-Growth Tech | Cloud & Modern Backend Infrastructure"
            ],
            "about_section": f"I am a {role} with {exp_years}+ years of experience building resilient backend architectures, AI agents, and data systems...",
            "featured_skills": candidate_profile.get("skills", [])[:10],
            "profile_tips": [
                "Başlığınızda şirket adı yerine çözdüğünüz ana problemleri ve temel teknolojileri öne çıkarın.",
                "Hakkımda kısmının ilk 3 satırını mobil ekranda 'Devamını Gör'e basmadan okunacak şekilde güçlü bir kanca ile başlatın.",
                "Projeler kısmına canlı demo linklerini ve GitHub repolarını doğrudan ekleyin."
            ]
        }

    async def audit_github_profile(
        self,
        github_username: str,
        sample_projects: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Evaluates public GitHub presence and suggests portfolio upgrades."""
        projects = sample_projects or [
            {"name": "Autonomous-Career-Agent", "desc": "End-to-end multi-agent AI system with FastAPI and Next.js"},
            {"name": "Distributed-Crawler", "desc": "High-throughput stealth web scraper with Celery and proxy rotation"}
        ]

        prompt = f"""
GitHub Username: {github_username}
Key Repositories: {projects}

Provide GitHub profile optimization recommendations in JSON with keys:
1. "pinned_repos_advice": Best strategies for which repos to pin and how to name them.
2. "readme_template": A crisp Markdown template for the user's main GitHub profile README (github.com/{github_username}/{github_username}).
3. "repository_health_checklist": 4 must-have repository hygiene checks (e.g., badges, architecture diagrams, test coverage, quickstart instructions).
"""
        res = await llm_client.generate_json(
            system_prompt="You are an Open Source Maintainer and Senior Engineering Director reviewing developer GitHub portfolios.",
            user_prompt=prompt
        )

        return res if res else {
            "pinned_repos_advice": "En fazla 4-6 aktif repo sabitleyin. Toy/tutorial projeleri yerine mimari tasarımını kendiniz kurguladığınız production-grade repoları öne çıkarın.",
            "readme_template": f"# Hi, I'm @{github_username} 👋\n\n```python\nclass Engineer:\n    skills = ['Python', 'FastAPI', 'AI Agents', 'Docker']\n    focus = 'Scalable distributed systems'\n```",
            "repository_health_checklist": [
                "Her repoda çalışan bir Quickstart / docker-compose talimatı",
                "Mimariyi özetleyen en az bir Mermaid.js veya görsel diyagram",
                "CI/CD GitHub Actions badge'leri ve test kapsamı",
                "Lisans ve temiz .gitignore dosyası"
            ]
        }

profile_optimizer_agent = ProfileOptimizerAgent()
