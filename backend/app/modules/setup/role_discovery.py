"""
AI Role & Career Title Discovery Engine
Analyzes documented candidate CV skills and projects to suggest related target roles,
lateral pivot opportunities, and tailored work style / location configurations.
"""

import asyncio
import json
import re
from typing import Dict, Any, List, Optional
from backend.app.core.llm_client import is_template_engine, llm_client
from backend.app.core.event_logger import agent_logger

# One-tap search areas. An empty location_filter searches everywhere; an empty remote_filter accepts any work mode.
LOCATION_WORK_STYLE_PRESETS = [
    {"id": "remote_global", "title": "Remote · Worldwide", "location_filter": "", "remote_filter": "Remote"},
    {"id": "remote_germany", "title": "Germany · Remote", "location_filter": "Germany", "remote_filter": "Remote"},
    {"id": "remote_uk", "title": "UK · Remote", "location_filter": "United Kingdom", "remote_filter": "Remote"},
    {"id": "remote_usa", "title": "USA · Remote", "location_filter": "United States", "remote_filter": "Remote"},
    {"id": "remote_turkey", "title": "Turkey · Remote", "location_filter": "Turkey", "remote_filter": "Remote"},
    {"id": "germany_any", "title": "Germany · Any", "location_filter": "Germany", "remote_filter": ""},
    {"id": "kosovo_any", "title": "Kosovo · Any", "location_filter": "Kosovo", "remote_filter": ""},
]

class RoleDiscoveryEngine:
    def get_work_style_presets(self) -> List[Dict[str, Any]]:
        return LOCATION_WORK_STYLE_PRESETS

    def discover_eligible_roles(self, profile: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Analyzes profile skills, experiences, and current target role
        to return role title suggestions; this does not estimate hiring probability.
        """
        skills = profile.get("skills", [])
        skills_str = ", ".join(skills) if isinstance(skills, list) else str(skills)
        exp_years = profile.get("years_of_experience")
        target_role = profile.get("target_role", "Software Engineer")
        raw_cv = profile.get("raw_cv_text", "")

        # Try LLM-driven personalized role mapping
        prompt = f"""You are a Silicon Valley Senior Tech Recruiter and Career Architect.
Analyze the following candidate profile and suggest 4 to 5 job titles that are plausibly related to the documented skills and target role. Do not estimate hiring, interview, or acceptance probability. Do not invent experience, expertise, or achievements.

Candidate Target Role: {target_role}
Years of Experience: {exp_years}
Skills: {skills_str}
CV Summary: {raw_cv[:400]}

For each role, provide:
- title: Industry standard job title (e.g. Full-Stack Developer, Senior Frontend Developer, Backend / API Developer, Product Engineer / Founding Engineer, AI Systems Engineer)
- subtext: A 1-line tactical explanation in Turkish (e.g. 'Mevcut çizgide devam: React + Node.js uçtan uca' or 'Node.js, PostgreSQL, sistem tasarımı ağırlıklı')
- reasons: 2-3 short rationale points grounded only in profile fields

Return ONLY valid JSON array with schema:
[
  {{
    "title": "string",
    "subtext": "string",
    "reasons": ["reason 1", "reason 2"]
  }}
]
"""
        try:
            # This runs in a worker thread (sync endpoint), so it owns its event loop.
            result = asyncio.run(llm_client.generate_text(
                system_prompt="You are an expert career architect. Return only JSON array.",
                user_prompt=prompt,
                temperature=0.3,
                apply_humanizer=False,
            ))
            if is_template_engine(result["provider_used"]):
                raise RuntimeError("no language model answered")
            raw_response = result["text"]
            # Clean markdown codeblocks
            cleaned = re.sub(r"^```(?:json)?\s*", "", raw_response.strip(), flags=re.MULTILINE)
            cleaned = re.sub(r"```$", "", cleaned.strip(), flags=re.MULTILINE)
            
            parsed = json.loads(cleaned)
            if isinstance(parsed, list) and len(parsed) >= 3:
                roles = []
                for idx, r in enumerate(parsed):
                    roles.append({
                        "id": f"role_{idx+1}",
                        "title": r.get("title", f"Role {idx+1}"),
                        "subtext": r.get("subtext", "CV yetkinliklerinizle doğrudan örtüşen pozisyon"),
                        "reasons": r.get("reasons", ["Profil ve ilan başlığıyla ilişkilendirilen rol önerisi"]),
                        "default_checked": idx < 3
                    })
                agent_logger.log_event("ROLE_DISCOVERY", f"Discovered {len(roles)} candidate roles via LLM.")
                return roles
        except Exception as e:
            agent_logger.log_event("ROLE_DISCOVERY", f"Fallback to heuristic role discovery: {str(e)[:50]}")

        # High-Fidelity Heuristic Rule-based Discovery
        return self._heuristic_role_discovery(profile)

    def _heuristic_role_discovery(self, profile: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Intelligent taxonomy engine matching CV stack to market titles."""
        skills_lower = [str(s).lower() for s in profile.get("skills", [])]
        exp_years = profile.get("years_of_experience")
        try:
            exp_years = max(0, int(exp_years)) if exp_years not in (None, "") else None
        except (TypeError, ValueError):
            exp_years = None
        prefix = "Senior " if exp_years is not None and exp_years >= 4 else ("Mid-Level " if exp_years is not None and exp_years >= 2 else "")

        has_react = any("react" in s or "next" in s or "vue" in s for s in skills_lower)
        has_node = any("node" in s or "express" in s or "nest" in s for s in skills_lower)
        has_python = any("python" in s or "fastapi" in s or "django" in s for s in skills_lower)
        has_ai = any("ai" in s or "llm" in s or "rag" in s or "langchain" in s for s in skills_lower)

        roles = []

        # 1. Full-Stack Developer
        if (has_react or "frontend" in skills_lower) and (has_node or has_python or "backend" in skills_lower):
            roles.append({
                "id": "fullstack_dev",
                "title": f"{prefix}Full-Stack Developer",
                "subtext": "Mevcut çizgide devam: React + Python/Node.js uçtan uca mimari",
                "reasons": [
                    "Profilde eşleşen frontend ve backend becerileri",
                    "İlan taraması öncesi öneri; deneyim ve ilan uygunluğunu ayrıca kontrol edin"
                ],
                "default_checked": True
            })

        # 2. Senior Frontend Developer
        if has_react:
            roles.append({
                "id": "frontend_dev",
                "title": f"{prefix}Frontend Developer",
                "subtext": "Frontend ağırlıklı, React/Next.js/TypeScript derinliği ve UI mimarisi",
                "reasons": [
                    "Profilde React/Next.js ile eşleşme bulundu",
                    "Öneri; ilan gereksinimlerini ayrıca inceleyin"
                ],
                "default_checked": True
            })

        # 3. Backend / API Developer
        if has_python or has_node:
            backend_lang = "FastAPI & Python" if has_python else "Node.js & Express"
            roles.append({
                "id": "backend_dev",
                "title": f"{prefix}Backend / API Developer",
                "subtext": f"{backend_lang}, veri tabanı modelleme ve mikroservis tasarımı",
                "reasons": [
                    f"Profilde {backend_lang} ile eşleşme bulundu",
                    "Öneri; veri tabanı ve API deneyimini ayrıca doğrulayın"
                ],
                "default_checked": True
            })

        # 4. Product Engineer / Founding Engineer
        roles.append({
            "id": "product_eng",
            "title": "Product Engineer / Founding Engineer",
            "subtext": "Erken aşama girişim veya ölçeklenen ürünlerde yüksek etki ve ürün sahipliği",
            "reasons": [
                "Rol, ürün mühendisliği kategorisinden önerildi",
                "Profildeki proje ve deneyim kayıtlarını bu rolle karşılaştırın"
            ],
            "default_checked": False
        })

        # 5. AI Systems / Automation Engineer
        if has_ai or has_python:
            roles.append({
                "id": "ai_systems_eng",
                "title": "AI Systems & Automation Engineer",
                "subtext": "Otonom ajanlar, RAG mimarileri ve akıllı iş akışı otomasyonu",
                "reasons": [
                    "Profilde AI/Python ile eşleşme bulundu",
                    "Öneri; ilgili proje ve deneyim kanıtlarını kontrol edin"
                ],
                "default_checked": True
            })

        return roles

role_discovery_engine = RoleDiscoveryEngine()
