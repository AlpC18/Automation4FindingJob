"""
Behavioral Profile System
Adapted from MadsLorentzen/ai-job-search 02-behavioral-profile.md concept.

Structured behavioral assessment for job matching:
- Personality assessment (PI, DISC, Myers-Briggs, or self-assessment)
- Work environment preferences
- Strengths and ideal conditions
- Cultural fit indicators

Used by the ranking engine to score cultural alignment and by
the interview prep module for behavioral question preparation.
"""

from typing import Dict, Any, List, Optional
from backend.app.core.event_logger import agent_logger
from backend.app.core.llm_client import llm_client


class BehavioralProfile:
    """Manages candidate behavioral profile data."""

    # Standard behavioral dimensions
    DIMENSIONS = [
        {
            "id": "communication",
            "name": "İletişim Tarzı",
            "name_en": "Communication Style",
            "options": [
                {"value": "direct", "label": "Doğrudan ve açık", "label_en": "Direct and transparent"},
                {"value": "diplomatic", "label": "Diplomatik ve uzlaşmacı", "label_en": "Diplomatic and consensus-seeking"},
                {"value": "analytical", "label": "Analitik ve veri odaklı", "label_en": "Analytical and data-driven"},
                {"value": "collaborative", "label": "İş birliğine dayalı", "label_en": "Collaborative and inclusive"},
            ],
        },
        {
            "id": "work_style",
            "name": "Çalışma Tarzı",
            "name_en": "Work Style",
            "options": [
                {"value": "autonomous", "label": "Bağımsız, minimal denetimle", "label_en": "Autonomous, minimal oversight"},
                {"value": "structured", "label": "Yapılandırılmış süreçler", "label_en": "Structured processes and clear guidelines"},
                {"value": "agile", "label": "Esnek, hızlı iterasyon", "label_en": "Flexible, fast iterations"},
                {"value": "methodical", "label": "Metodik, detaylı planlama", "label_en": "Methodical, detailed planning"},
            ],
        },
        {
            "id": "motivation",
            "name": "Motivasyon Kaynağı",
            "name_en": "Motivation Driver",
            "options": [
                {"value": "impact", "label": "Somut etki yaratmak", "label_en": "Creating tangible impact"},
                {"value": "learning", "label": "Sürekli öğrenme ve gelişme", "label_en": "Continuous learning and growth"},
                {"value": "mastery", "label": "Teknik ustalık", "label_en": "Technical mastery"},
                {"value": "leadership", "label": "Liderlik ve mentorluk", "label_en": "Leadership and mentoring"},
            ],
        },
        {
            "id": "conflict_resolution",
            "name": "Çatışma Yönetimi",
            "name_en": "Conflict Resolution",
            "options": [
                {"value": "assertive", "label": "Kararlı, pozisyon savunma", "label_en": "Assertive, defending position"},
                {"value": "compromise", "label": "Uzlaşma arayışı", "label_en": "Seeking compromise"},
                {"value": "avoidant", "label": "Kaçınma, zaman tanıma", "label_en": "Avoiding, giving time"},
                {"value": "collaborative", "label": "Ortak çözüm arayışı", "label_en": "Finding collaborative solutions"},
            ],
        },
        {
            "id": "energy_source",
            "name": "Enerji Kaynağı",
            "name_en": "Energy Source",
            "options": [
                {"value": "extrovert", "label": "Takım çalışması ve sosyal etkileşim", "label_en": "Teamwork and social interaction"},
                {"value": "introvert", "label": "Derin odaklanma ve bireysel çalışma", "label_en": "Deep focus and solo work"},
                {"value": "ambivert", "label": "Dengeleyici — duruma göre değişir", "label_en": "Balanced — context-dependent"},
            ],
        },
    ]

    ENVIRONMENT_PREFERENCES = [
        {
            "id": "team_size",
            "name": "Tercih Edilen Takım Boyutu",
            "options": ["startup_small", "mid_team", "large_org"],
        },
        {
            "id": "pace",
            "name": "Çalışma Ritmi",
            "options": ["fast_paced", "steady", "variable"],
        },
        {
            "id": "structure",
            "name": "Organizasyon Yapısı",
            "options": ["flat", "hierarchical", "matrix"],
        },
    ]

    def get_assessment_questions(self) -> Dict[str, Any]:
        """Return the full behavioral assessment questionnaire."""
        return {
            "dimensions": self.DIMENSIONS,
            "environment_preferences": self.ENVIRONMENT_PREFERENCES,
            "instructions": (
                "Her boyut için size en uygun seçeneği işaretleyin. "
                "Bu bilgiler iş eşleştirme skorlamasında ve mülakat hazırlığında kullanılacak."
            ),
        }

    def build_profile(self, answers: Dict[str, str]) -> Dict[str, Any]:
        """
        Build a structured behavioral profile from assessment answers.

        Args:
            answers: Dict mapping dimension_id → selected option value
        """
        profile = {
            "dimensions": {},
            "environment_preferences": {},
            "summary": "",
        }

        for dim in self.DIMENSIONS:
            dim_id = dim["id"]
            selected = answers.get(dim_id)
            if selected:
                option = next((o for o in dim["options"] if o["value"] == selected), None)
                profile["dimensions"][dim_id] = {
                    "value": selected,
                    "label": option["label"] if option else selected,
                    "label_en": option.get("label_en", "") if option else "",
                }

        for pref in self.ENVIRONMENT_PREFERENCES:
            pref_id = pref["id"]
            selected = answers.get(pref_id)
            if selected:
                profile["environment_preferences"][pref_id] = selected

        # Generate summary
        profile["summary"] = self._generate_summary(profile)

        agent_logger.log_event(
            "BEHAVIORAL_PROFILE",
            f"Profile built with {len(profile['dimensions'])} dimensions"
        )

        return profile

    def _generate_summary(self, profile: Dict[str, Any]) -> str:
        """Generate a human-readable summary of the behavioral profile."""
        dims = profile.get("dimensions", {})
        parts = []

        if "communication" in dims:
            parts.append(f"İletişim: {dims['communication']['label']}")
        if "work_style" in dims:
            parts.append(f"Çalışma: {dims['work_style']['label']}")
        if "motivation" in dims:
            parts.append(f"Motivasyon: {dims['motivation']['label']}")
        if "energy_source" in dims:
            parts.append(f"Enerji: {dims['energy_source']['label']}")

        return " | ".join(parts) if parts else "Profil henüz tamamlanmadı"

    def calculate_cultural_fit(
        self,
        behavioral_profile: Dict[str, Any],
        job_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Score cultural fit between candidate behavioral profile and job posting.

        Analyzes job description for culture signals and compares with candidate preferences.
        """
        desc = job_data.get("description", "").lower()
        dims = behavioral_profile.get("dimensions", {})

        fit_score = 50  # Start at neutral
        signals = []

        # Detect culture signals in job description
        if any(w in desc for w in ["startup", "fast-paced", "move fast", "hızlı", "dinamik"]):
            if dims.get("work_style", {}).get("value") in ("agile", "autonomous"):
                fit_score += 15
                signals.append("✅ Hızlı tempo ortamı — çalışma tarzınızla uyumlu")
            elif dims.get("work_style", {}).get("value") == "methodical":
                fit_score -= 10
                signals.append("⚠️ Hızlı tempo ortamı — metodik tarzınızla çatışabilir")

        if any(w in desc for w in ["collaborative", "team", "cross-functional", "ekip", "takım"]):
            if dims.get("energy_source", {}).get("value") in ("extrovert", "ambivert"):
                fit_score += 10
                signals.append("✅ Takım odaklı ortam — sosyal tarzınızla uyumlu")

        if any(w in desc for w in ["autonomous", "independent", "self-driven", "bağımsız"]):
            if dims.get("work_style", {}).get("value") == "autonomous":
                fit_score += 15
                signals.append("✅ Bağımsız çalışma vurgusu — tarzınızla birebir uyumlu")

        if any(w in desc for w in ["mentor", "lead", "coach", "guide", "liderlik"]):
            if dims.get("motivation", {}).get("value") == "leadership":
                fit_score += 10
                signals.append("✅ Liderlik/mentorluk beklentisi — motivasyonunuzla uyumlu")

        fit_score = max(0, min(100, fit_score))

        return {
            "cultural_fit_score": fit_score,
            "signals": signals,
            "recommendation": (
                "Yüksek uyum" if fit_score >= 70 else
                "Orta uyum" if fit_score >= 45 else
                "Düşük uyum — dikkatli değerlendirin"
            ),
        }


# Module-level singleton
behavioral_profiler = BehavioralProfile()
