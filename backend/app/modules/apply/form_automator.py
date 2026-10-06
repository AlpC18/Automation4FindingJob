"""
Dynamic Form Ingestion (Easy Apply Automator) & Form Memory Store
Adheres to PRD 3.2. Analyzes custom application questions, utilizes learned Form Memory,
and falls back to REQUIRES_HUMAN_INPUT with smart drafts when data is missing.
"""

import re
import json
from typing import Dict, Any, List, Optional
from backend.app.core.database import get_db_connection

def normalize_question(q: str) -> str:
    cleaned = re.sub(r'[^\w\s]', '', q.lower()).strip()
    return re.sub(r'\s+', ' ', cleaned)

SEEDED_ANSWERS = [
    ("How many years of work experience do you have with Python?", "4 years"),
    ("Will you now or in the future require visa sponsorship?", "No"),
    ("Are you legally authorized to work in this location?", "Yes"),
    ("What is your current notice period?", "Immediately available / 2 weeks"),
    ("Are you willing to relocate?", "Open to remote, negotiable for exceptional roles"),
]


class FormAutomator:
    def __init__(self):
        self._drop_seeded_answers()

    def _drop_seeded_answers(self):
        """Earlier versions pre-filled these answers for every user; nobody actually gave them."""
        conn = get_db_connection()
        cursor = conn.cursor()
        for orig, ans in SEEDED_ANSWERS:
            cursor.execute(
                "DELETE FROM form_memory WHERE question_normalized = ? AND answer = ?",
                (normalize_question(orig), ans),
            )
        conn.commit()
        conn.close()

    def answer_question(self, question: str, candidate_profile: Dict[str, Any]) -> Dict[str, Any]:
        norm_q = normalize_question(question)
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 1. Check Form Memory: exact or substring match
        cursor.execute("""
            SELECT * FROM form_memory 
            WHERE question_normalized = ? 
               OR ? LIKE '%' || question_normalized || '%'
               OR question_normalized LIKE '%' || ? || '%'
            ORDER BY LENGTH(question_normalized) DESC
            LIMIT 1
        """, (norm_q, norm_q, norm_q))
        row = cursor.fetchone()
        
        if row:
            cursor.execute("UPDATE form_memory SET times_used = times_used + 1 WHERE id = ?", (row["id"],))
            conn.commit()
            conn.close()
            return {
                "question": question,
                "answer": row["answer"],
                "source": "FORM_MEMORY",
                "status": "AUTO_FILLED",
                "confidence": row["confidence"]
            }

        conn.close()

        # 2. Read it from the profile. Visa and work-permit questions are never inferred:
        # the profile has no such field and a wrong answer goes to a real employer.
        years_exp = candidate_profile.get("years_of_experience")
        github_url = candidate_profile.get("github_url")

        if ("years" in norm_q or "deneyim" in norm_q or "experience" in norm_q) and years_exp not in (None, ""):
            return {"question": question, "answer": f"{years_exp} years", "source": "PROFILE_INFERENCE", "status": "AUTO_FILLED", "confidence": 0.9}
        if ("github" in norm_q or "portfolio" in norm_q) and github_url:
            return {"question": question, "answer": github_url, "source": "PROFILE_INFERENCE", "status": "AUTO_FILLED", "confidence": 0.99}

        # 3. Fallback: REQUIRES_HUMAN_INPUT
        return {
            "question": question,
            "answer": "",
            "source": "NO_ANSWER",
            "status": "REQUIRES_HUMAN_INPUT",
            "confidence": 0.0,
        }

    def save_human_answer_to_memory(self, question: str, answer: str):
        norm_q = normalize_question(question)
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO form_memory (question_normalized, original_question, answer, confidence, requires_human_review)
            VALUES (?, ?, ?, 1.0, 0)
            ON CONFLICT(question_normalized) DO UPDATE SET
                answer = excluded.answer,
                times_used = times_used + 1,
                updated_at = CURRENT_TIMESTAMP
        """, (norm_q, question, answer))
        conn.commit()
        conn.close()

form_automator = FormAutomator()
