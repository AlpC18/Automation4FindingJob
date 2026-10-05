"""
STAR Interview Framework
Adapted from MadsLorentzen/ai-job-search 07-interview-prep.md concept.

Structured STAR (Situation, Task, Action, Result) interview preparation:
- Maps candidate experience to STAR examples
- Generates role-specific behavioral questions
- Provides structured practice framework
- Scores answers for completeness and impact

Extends the existing interview_simulator with deeper behavioral prep.
"""

from typing import Dict, Any, List, Optional
from backend.app.core.event_logger import agent_logger


# Common behavioral question categories
BEHAVIORAL_CATEGORIES = {
    "leadership": {
        "name": "Liderlik & İnisiyatif",
        "questions": [
            "Tell me about a time you led a project or team through a difficult challenge.",
            "Describe a situation where you had to make a decision without all the information.",
            "Give an example of when you mentored someone or helped them grow.",
        ],
    },
    "teamwork": {
        "name": "Takım Çalışması & İşbirliği",
        "questions": [
            "Describe a time you had to work with a difficult team member.",
            "Tell me about a successful cross-functional collaboration.",
            "How did you handle a disagreement with a colleague about a technical approach?",
        ],
    },
    "problem_solving": {
        "name": "Problem Çözme & Analitik Düşünme",
        "questions": [
            "Describe the most complex technical problem you've solved.",
            "Tell me about a time you had to debug a critical production issue.",
            "How did you approach a problem that had no clear solution?",
        ],
    },
    "adaptability": {
        "name": "Uyum Sağlama & Değişim Yönetimi",
        "questions": [
            "Tell me about a time when project requirements changed significantly.",
            "Describe how you learned a new technology or tool quickly for a project.",
            "Give an example of when you had to pivot your approach mid-project.",
        ],
    },
    "impact": {
        "name": "Etki & Sonuç Odaklılık",
        "questions": [
            "What's the project you're most proud of and why?",
            "Tell me about a time you delivered something that exceeded expectations.",
            "Describe a measurable improvement you made to a system or process.",
        ],
    },
    "failure": {
        "name": "Başarısızlık & Öğrenme",
        "questions": [
            "Tell me about a time you failed or made a significant mistake.",
            "Describe a project that didn't go as planned. What did you learn?",
            "How do you handle receiving critical feedback?",
        ],
    },
}


class STARExample:
    """A single STAR-format example from candidate experience."""

    def __init__(
        self,
        title: str,
        category: str,
        situation: str = "",
        task: str = "",
        action: str = "",
        result: str = "",
        source: str = "",
        applicable_questions: Optional[List[str]] = None,
    ):
        self.title = title
        self.category = category
        self.situation = situation
        self.task = task
        self.action = action
        self.result = result
        self.source = source  # e.g., "CV - Senior Engineer @ Acme"
        self.applicable_questions = applicable_questions or []

    def is_complete(self) -> bool:
        return all([self.situation, self.task, self.action, self.result])

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "category": self.category,
            "situation": self.situation,
            "task": self.task,
            "action": self.action,
            "result": self.result,
            "source": self.source,
            "is_complete": self.is_complete(),
            "applicable_questions": self.applicable_questions,
        }


class STARFramework:
    """STAR interview preparation framework."""

    def __init__(self):
        self.examples: List[STARExample] = []

    def get_question_categories(self) -> Dict[str, Any]:
        """Return all behavioral question categories."""
        return BEHAVIORAL_CATEGORIES

    def generate_role_questions(
        self,
        job_title: str,
        job_description: str,
    ) -> List[Dict[str, Any]]:
        """
        Generate role-specific behavioral questions based on the job posting.

        Returns prioritized list of questions with category tags.
        """
        desc_lower = job_description.lower()
        questions = []

        # Determine relevant categories based on job description signals
        category_relevance = {}

        leadership_signals = ["lead", "manage", "mentor", "guide", "lider", "yönet"]
        if any(s in desc_lower for s in leadership_signals):
            category_relevance["leadership"] = 1.0

        team_signals = ["team", "collaborate", "cross-functional", "agile", "takım", "ekip"]
        if any(s in desc_lower for s in team_signals):
            category_relevance["teamwork"] = 1.0

        technical_signals = ["architect", "design", "debug", "optimize", "scale", "system"]
        if any(s in desc_lower for s in technical_signals):
            category_relevance["problem_solving"] = 1.0

        # Always include these
        category_relevance.setdefault("impact", 0.8)
        category_relevance.setdefault("adaptability", 0.7)
        category_relevance.setdefault("failure", 0.5)

        for cat_id, relevance in sorted(category_relevance.items(), key=lambda x: -x[1]):
            cat = BEHAVIORAL_CATEGORIES.get(cat_id)
            if cat:
                for q in cat["questions"]:
                    questions.append({
                        "question": q,
                        "category": cat_id,
                        "category_name": cat["name"],
                        "relevance": relevance,
                    })

        return questions

    def extract_star_candidates(
        self,
        candidate_profile: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        Extract potential STAR examples from candidate profile.
        Returns stubs that need to be completed by the candidate.
        """
        stubs = []

        # From experience
        for exp in candidate_profile.get("experience", []):
            if isinstance(exp, dict):
                title = exp.get("title", "")
                company = exp.get("company", "")
                achievements = exp.get("achievements", [])

                for achievement in achievements:
                    if isinstance(achievement, str) and len(achievement) > 20:
                        stubs.append({
                            "title": f"{achievement[:60]}...",
                            "source": f"CV — {title} @ {company}",
                            "what_happened": achievement,
                            "suggested_categories": self._categorize_achievement(achievement),
                            "star_stub": {
                                "situation": "",
                                "task": "",
                                "action": "",
                                "result": "",
                            },
                        })

        # From skills (for technical questions)
        skills = candidate_profile.get("skills", [])
        if skills:
            stubs.append({
                "title": f"Technical depth: {', '.join(skills[:3])}",
                "source": "Skills section",
                "what_happened": f"Deep experience with {', '.join(skills[:5])}",
                "suggested_categories": ["problem_solving", "impact"],
                "star_stub": {
                    "situation": "",
                    "task": "",
                    "action": "",
                    "result": "",
                },
            })

        agent_logger.log_event(
            "STAR_FRAMEWORK",
            f"Extracted {len(stubs)} STAR candidates from profile"
        )

        return stubs

    def _categorize_achievement(self, text: str) -> List[str]:
        """Suggest behavioral categories for an achievement."""
        text_lower = text.lower()
        categories = []

        if any(w in text_lower for w in ["led", "managed", "built team", "mentored"]):
            categories.append("leadership")
        if any(w in text_lower for w in ["collaborated", "cross-team", "worked with"]):
            categories.append("teamwork")
        if any(w in text_lower for w in ["solved", "debugged", "optimized", "designed"]):
            categories.append("problem_solving")
        if any(w in text_lower for w in ["improved", "increased", "reduced", "achieved"]):
            categories.append("impact")
        if any(w in text_lower for w in ["learned", "adapted", "pivoted", "new"]):
            categories.append("adaptability")

        return categories or ["impact"]

    def score_star_answer(
        self,
        answer: Dict[str, str],
    ) -> Dict[str, Any]:
        """
        Score a STAR answer for completeness and quality.

        Args:
            answer: Dict with 'situation', 'task', 'action', 'result' keys
        """
        scores = {}
        feedback = []

        for component in ["situation", "task", "action", "result"]:
            text = answer.get(component, "")
            word_count = len(text.split())

            if not text:
                scores[component] = 0
                feedback.append(f"❌ {component.upper()} eksik — bu bölümü doldurun")
            elif word_count < 10:
                scores[component] = 30
                feedback.append(f"⚠️ {component.upper()} çok kısa ({word_count} kelime) — daha detay ekleyin")
            elif word_count < 25:
                scores[component] = 60
                feedback.append(f"🔶 {component.upper()} yeterli ama detay eklenebilir")
            else:
                scores[component] = 90
                feedback.append(f"✅ {component.upper()} iyi detaylandırılmış")

        # Check for metrics in Result
        result_text = answer.get("result", "")
        has_metrics = any(c.isdigit() for c in result_text)
        if result_text and not has_metrics:
            feedback.append(
                "💡 RESULT bölümünde sayısal metrik ekleyin "
                "(örn: '%30 iyileşme', '2x hızlanma', '10K kullanıcı')"
            )

        overall = sum(scores.values()) / max(len(scores), 1)

        return {
            "overall_score": round(overall, 1),
            "component_scores": scores,
            "feedback": feedback,
            "is_complete": all(v > 0 for v in scores.values()),
            "has_metrics": has_metrics,
        }


# Module-level singleton
star_framework = STARFramework()
