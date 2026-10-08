"""
Interactive Interview Simulation Engine
Generates scenario-based technical, behavioral (STAR method), and cross-examination questions
based on the job description and evaluates candidate answers.
"""

import re
from typing import Dict, Any, List, Optional

from backend.app.modules.interview.star_framework import star_framework

STAR_POINTS = ["Situation", "Task", "Action", "Result"]
# The technical and gap questions built below name their technology this way.
_ASKS_FOR = re.compile(r"asks for (.+?)(?:\.\s|,\s|$)", re.IGNORECASE)
_OWN_ACTION = re.compile(
    r"\bI (?:\w+ly )?(?:built|wrote|designed|implemented|created|developed|fixed|led|set up|added|migrated|refactored|tested|"
    r"deployed|automated|reduced|improved|optimized|solved|debugged|changed|measured)\b|"
    r"\b(?:geliştirdim|tasarladım|uyguladım|yazdım|yönettim|ekledim|kurdum|çözdüm|ölçtüm|test ettim)\b",
    re.IGNORECASE,
)
_CONTEXT_CUES = ("when ", "while ", "during ", "project", "client", "team", "company", "freelance", "task was",
                 "projede", "müşteri", "ekip", "şirket", "sırasında", "görevim")
_RESULT_CUES = ("as a result", "result", "which meant", "led to", "so that", "dropped", "fell", "reduced", "increased", "improved",
                "now ", "sonuç", "sayesinde", "azal", "arttı", "düştü")
_EVIDENCE_CUES = ("test", "tests", "log", "logs", "dashboard", "ticket", "tickets", "release", "deployment", "metric",
                  "kanıt", "test", "ölçüm", "yayın")
_REASONING_CUES = ("because", "therefore", "in order to", "trade-off", "tradeoff", "decided", "chose", "without", "so that",
                   "bu nedenle", "karar verdim", "seçtim", "yaklaşım", "için", "amaçla")
TECH_QUESTIONS_FROM_CV = 2


def _mentions(text: str, phrase: str) -> bool:
    """Match a named cue, not substrings such as 'log' inside 'catalog'."""
    return bool(re.search(r"(?<!\w)" + re.escape(phrase.strip()) + r"(?!\w)", text, re.IGNORECASE))


class InterviewSimulator:
    def generate_interview_session(
        self, job_title: str, company: str, job_description: str, fit_report: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Questions for this posting: the technologies it names, then one behavioural question per theme it signals."""
        report = fit_report or {}
        drafts = [{
            "type": "Role fit",
            "question": f"Why do you want the {job_title} role at {company}, and which part of your past work is closest to it?",
            "key_points": ["What the role does", "Your closest project", "Why this company"],
        }]
        for tech in list(report.get("keywords_you_have") or [])[:TECH_QUESTIONS_FROM_CV]:
            drafts.append({
                "type": "Technical",
                "question": f"This role asks for {tech}. Walk me through a piece of work where you used {tech}: the problem, what you did, and how it turned out.",
                "key_points": ["The problem", f"Your own work with {tech}", "A trade-off you made", "The outcome"],
            })
        for tech in list(report.get("keywords_missing") or [])[:1]:
            drafts.append({
                "type": "Gap",
                "question": f"The posting asks for {tech}, which is not on your CV. What is the closest thing you have used, and how would you get productive with {tech}?",
                "key_points": ["Say plainly what you have not used", "The closest thing you know", "How you would learn it"],
            })
        asked = set()
        for item in star_framework.generate_role_questions(job_title, job_description or ""):
            if item["category"] not in asked:
                asked.add(item["category"])
                drafts.append({"type": item["category_name"], "question": item["question"], "key_points": STAR_POINTS})
        return [{"id": f"q{number}", **draft} for number, draft in enumerate(drafts, start=1)]

    def evaluate_candidate_answer(self, question: str, answer: str) -> Dict[str, Any]:
        """Check the answer's structure against the question; each check is listed with what it found.

        This reads how the answer is built, not whether its content is technically right.
        """
        text = (answer or "").strip()
        lowered = text.lower()
        asked_for = [tech.strip() for tech in _ASKS_FOR.findall(question or "")]
        checks: List[Dict[str, Any]] = []

        def check(check_id: str, points: int, passed: bool, found: str, missing: str) -> None:
            checks.append({"id": check_id, "points": points, "passed": passed, "note": found if passed else missing})

        if asked_for:
            named = [tech for tech in asked_for if _mentions(text, tech)]
            check("on_topic", 20, bool(named), f"Sorulan teknolojiden söz ediyorsun: {', '.join(named)}.",
                  f"Soru {', '.join(asked_for)} hakkında; cevabında adı geçmiyor.")
        check("own_action", 20, bool(_OWN_ACTION.search(text)), "Kendi yaptığın işi birinci tekil şahısla anlatıyorsun.",
              "Senin ne yaptığın belli değil. 'I built / I wrote / geliştirdim' gibi kendi eylemini söyle.")
        check("context", 15, any(cue in lowered for cue in _CONTEXT_CUES), "Durumu ve bağlamı veriyorsun.",
              "Bağlam yok: hangi proje, hangi müşteri ya da ekip, sorun neydi?")
        check("result", 15, any(cue in lowered for cue in _RESULT_CUES), "Sonucu söylüyorsun.",
              "Sonuç yok: yaptığın iş neyi değiştirdi?")
        # A year or a technology version is not evidence of an outcome.
        has_measurement = bool(re.search(
            r"\d+(?:[.,]\d+)?\s*(?:%|percent\b|ms\b|seconds?\b|minutes?\b|hours?\b|users?\b|tickets?\b|kullanıcı\b|saniye\b)"
            r"|%\s*\d+|\bfrom\s+\d+\s+(?:\w+\s+){0,3}to\s+\d+",
            text, re.IGNORECASE,
        ))
        has_evidence = has_measurement or any(_mentions(text, cue) for cue in _EVIDENCE_CUES)
        check("evidence", 15, has_evidence, "Sonucu ölçüm, artefakt veya gözlenebilir bir kanıtla destekliyorsun.",
              "Sonuç için gözlenebilir kanıt yok. Bir ölçüm, test, yayın, kullanıcı etkisi veya somut artefakt ekle; sayı uydurma.")
        check("reasoning", 15, any(cue in lowered for cue in _REASONING_CUES), "Seçimini veya yaklaşımını gerekçelendiriyorsun.",
              "Yaklaşımının nedenini açıklamıyorsun. Bir tercih, trade-off veya karar gerekçesi ekle.")

        possible = sum(item["points"] for item in checks)
        earned = sum(item["points"] for item in checks if item["passed"])
        score = round(100 * earned / possible) if text else 0
        gaps = sorted((item for item in checks if not item["passed"]), key=lambda item: -item["points"])
        return {
            "scoring_method": "local_rubric_v2",
            "technical_correctness_verified": False,
            "score": score,
            "grade": "EXCELLENT" if score >= 85 else ("GOOD" if score >= 70 else "NEEDS_IMPROVEMENT"),
            "feedback": [("✓ " if item["passed"] else "✗ ") + item["note"] for item in checks],
            "checks": checks,
            "coaching_tip": gaps[0]["note"] if gaps else "Yapı tam. İçeriğin doğruluğunu bu kontrol ölçmez; cevabı bir de sesli prova et.",
        }


interview_simulator = InterviewSimulator()
