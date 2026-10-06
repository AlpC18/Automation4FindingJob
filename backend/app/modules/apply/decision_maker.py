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

APOLLO_PEOPLE_SEARCH_URL = "https://api.apollo.io/api/v1/mixed_people/api_search"
APOLLO_SENIORITIES = ("owner", "founder", "c_suite", "vp", "head", "director", "manager")
APOLLO_MAX_RESULTS = 10
_DOMAIN_PATTERN = re.compile(r"^(?=.{4,253}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}$")
_APOLLO_ERRORS = {
    401: "Apollo API anahtarı geçersiz.",
    403: "Apollo hesabının bu aramaya erişimi yok; kişi araması için yetkili (master) bir API anahtarı gerekir.",
    422: "Apollo arama parametrelerini kabul etmedi.",
    429: "Apollo saatlik istek sınırına ulaşıldı; daha sonra tekrar dene.",
}


class ApolloError(RuntimeError):
    """Apollo could not be queried; the message is safe to show to the user."""


def normalize_company_domain(value: str) -> str:
    """Accept "https://www.Acme.com/careers" or "acme.com"; return "acme.com" or raise ValueError."""
    domain = re.sub(r"^[a-z]+://", "", (value or "").strip().lower()).split("/")[0].split("@")[-1]
    domain = domain.removeprefix("www.")
    if not _DOMAIN_PATTERN.match(domain):
        raise ValueError("Geçerli bir şirket alan adı gir (ör. acme.com).")
    return domain


class DecisionMakerEngine:
    def search_apollo_people(self, company_domain: str, location: Optional[str] = None, limit: int = 5) -> List[Dict[str, Any]]:
        """Managers and above at a company, from Apollo's People API Search.

        The search itself costs no credits and returns no emails or full surnames;
        Apollo only reveals those through its paid enrichment endpoints.
        """
        if not settings.APOLLO_API_KEY:
            raise ApolloError("Apollo API anahtarı ayarlı değil (APOLLO_API_KEY).")
        params: List[tuple] = [("q_organization_domains_list[]", normalize_company_domain(company_domain))]
        params += [("person_seniorities[]", seniority) for seniority in APOLLO_SENIORITIES]
        if location and location.strip():
            params.append(("person_locations[]", location.strip()[:100]))
        params += [("page", 1), ("per_page", max(1, min(int(limit), APOLLO_MAX_RESULTS)))]
        try:
            response = httpx.post(
                APOLLO_PEOPLE_SEARCH_URL,
                params=params,
                headers={"x-api-key": settings.APOLLO_API_KEY, "Accept": "application/json", "Cache-Control": "no-cache"},
                timeout=20,
            )
        except httpx.HTTPError as exc:
            raise ApolloError("Apollo API'ye ulaşılamadı; ağ bağlantısını kontrol et.") from exc
        if response.status_code >= 400:
            raise ApolloError(_APOLLO_ERRORS.get(response.status_code, f"Apollo HTTP {response.status_code} döndürdü."))
        try:
            people = response.json().get("people") or []
        except (ValueError, AttributeError) as exc:
            raise ApolloError("Apollo beklenmeyen bir yanıt döndürdü.") from exc
        return [
            {
                "first_name": str(person.get("first_name") or ""),
                "last_name_obfuscated": str(person.get("last_name_obfuscated") or ""),
                "title": str(person.get("title") or ""),
                "company": str((person.get("organization") or {}).get("name") or ""),
                "has_email": bool(person.get("has_email")),
            }
            for person in people if isinstance(person, dict)
        ]

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
