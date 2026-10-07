"""
Interactive Interview Simulation Engine
Generates scenario-based technical, behavioral (STAR method), and cross-examination questions
based on the job description and evaluates candidate answers.
"""

from typing import Dict, Any, List, Optional

from backend.app.modules.interview.star_framework import star_framework

STAR_POINTS = ["Situation", "Task", "Action", "Result"]
TECH_QUESTIONS_FROM_CV = 2


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
        """
        Grades candidate response, detects strengths, and offers constructive improvement advice.
        """
        word_count = len(answer.split())
        score = 70
        feedback = []
        
        if word_count < 25:
            score -= 20
            feedback.append("Yanıtınız çok kısa. Somut adımlar, teknik araçlar ve metrikler ekleyerek zenginleştirin.")
        elif word_count > 180:
            score -= 10
            feedback.append("Yanıtınız biraz uzun ve dağılmış. Mülakatçının dikkatini canlı tutmak için STAR formatında daha öz (concise) ifade edin.")
        else:
            score += 15
            feedback.append("Cümle uzunluğu ve odak dengeli.")

        # Check for technical specifics
        if any(tech in answer.lower() for tech in ["log", "metric", "cache", "redis", "test", "docker", "veri", "hata"]):
            score += 15
            feedback.append("Teknik terimler ve pratik problem çözme adımları başarılı bir şekilde aktarılmış.")
            
        final_score = max(30, min(98, score))
        
        return {
            "score": final_score,
            "grade": "EXCELLENT" if final_score >= 85 else ("GOOD" if final_score >= 70 else "NEEDS_IMPROVEMENT"),
            "feedback": feedback,
            "coaching_tip": "Bir sonraki soruda sonucu (Result) sayısal bir veriyle (% artış, ms düşüş) bağlamaya özen gösterin."
        }

interview_simulator = InterviewSimulator()
