"""
Decision Maker Sourcing & Cold Outreach Engine
Implements Google X-Ray Dorking, Apollo Search helpers, and 3-sentence outreach generation
strictly adhering to PRD Section 3.3.
"""

import re
from typing import Dict, Any, List, Optional

import httpx

from backend.app.core.config import settings
from backend.app.prompts.outreach_prompts import DECISION_MAKER_OUTREACH_PROMPT

class DecisionMakerEngine:
    def generate_xray_dork(self, company_name: str, location: str) -> str:
        """
        Builds Google X-Ray search query:
        site:linkedin.com/in/ "{location}" AND "{company_name}" AND ("Manager" OR "Director" OR "Lead")
        """
        clean_company = company_name.replace('"', '').strip()
        clean_loc = location.split('/')[0].split(',')[0].strip() or "Remote"
        return f'site:linkedin.com/in/ "{clean_loc}" AND "{clean_company}" AND ("Manager" OR "Director" OR "Lead" OR "Head")'

    def draft_three_sentence_outreach(
        self,
        company_name: str,
        job_title: str,
        candidate_profile: Dict[str, Any],
        rag_project: Dict[str, Any] = None
    ) -> str:
        """
        Strictly follows PRD 3.3:
        S1: Relevant observation about their regional operations/projects.
        S2: Direct value proposition based on user's core skillset.
        S3: Low-friction call to action.
        """
        # Built only from what is saved: no assumed skills, no claims about the company or about results.
        skills = [str(skill) for skill in (candidate_profile.get("skills") or [])[:2]]
        project = (rag_project or {}).get("title")
        result = (rag_project or {}).get("metrics")

        s1 = f"I saw your open {job_title} role at {company_name}."
        if skills and project:
            s2 = f"I work with {' and '.join(skills)}, most recently on {project}" + (f" ({result})." if result else ".")
        elif skills:
            s2 = f"I work with {' and '.join(skills)} and would like to hear what the team needs."
        else:
            s2 = "I would like to hear what the team needs."
        s3 = "Would you be open to a brief 5-minute chat this week?"

        return f"{s1} {s2} {s3}"

    def synthesize_micro_portfolio(self, job_title: str, company: str, rag_projects: list) -> str:
        """
        PRD 1.4 Micro-Project Synthesizer:
        Generates a 1-page structured micro-case study addressing company's specific needs.
        """
        if not rag_projects:
            # No saved project means no case study; an invented one would be sent to a real employer.
            return ""
        proj = rag_projects[0]
        
        return f"""# MICRO-CASE STUDY: TECHNICAL ARCHITECTURE
**Target Role:** {job_title} @ {company}

### Problem Statement
Modern platforms require high reliability, zero data leakage, and low-latency interaction across complex distributed services.

### Implemented Solution ({proj.get('title')})
- **Core Stack:** {', '.join(proj.get('tech_stack', []))}
- **Architectural Highlights:** Built clean, modular microservices designed for fault tolerance and automated retries.
- **Measurable Result:** {proj.get('metrics', 'Production-tested high availability')}.

### Value Add for {company}
Immediate ability to integrate into ongoing roadmap, clean codebase delivery, and zero onboarding friction.
"""

decision_maker_engine = DecisionMakerEngine()
