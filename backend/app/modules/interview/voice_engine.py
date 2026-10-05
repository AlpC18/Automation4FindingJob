"""
Voice AI Speech & Interactive Interview Engine
Handles speech evaluation, audio analytics, and conversational interview flow:
- Audio speech analysis (Filler word count, speaking pace WPM, confidence score)
- TTS conversational prompt generator with realistic interviewer tone
- Real-time STAR verbal response diagnostic
"""

import re
from typing import Dict, Any, List, Optional
from backend.app.core.llm_client import llm_client
from backend.app.core.event_logger import agent_logger


class VoiceInterviewEngine:
    """Evaluates verbal interview answers and generates natural speech prompts."""

    FILLER_WORDS = [
        "şey", "yani", "ııı", "eee", "falan", "filan", "mesela",
        "um", "uh", "like", "you know", "basically", "actually", "literally"
    ]

    def analyze_spoken_transcript(
        self,
        transcript_text: str,
        duration_seconds: float = 60.0
    ) -> Dict[str, Any]:
        """Analyzes speech pace (WPM), filler word usage, and verbal clarity."""
        words = transcript_text.split()
        word_count = len(words)
        minutes = max(0.1, duration_seconds / 60.0)
        wpm = round(word_count / minutes)

        # Detect fillers
        text_lower = transcript_text.lower()
        filler_counts = {}
        total_fillers = 0

        for filler in self.FILLER_WORDS:
            count = len(re.findall(rf"\b{filler}\b", text_lower))
            if count > 0:
                filler_counts[filler] = count
                total_fillers += count

        # Pace diagnosis (Ideal conversational pace: 130-160 WPM)
        if wpm < 110:
            pace_verdict = "Biraz yavaş — Konuşmanızı hafif hızlandırabilirsiniz."
        elif wpm > 175:
            pace_verdict = "Çok hızlı — Anlaşılırlığı artırmak için duraklamalara özen gösterin."
        else:
            pace_verdict = "Mükemmel konuşma ritmi (Doğal ve anlaşılır)."

        # Fluency score calculation
        fluency_score = max(30, 100 - (total_fillers * 6))

        return {
            "total_words": word_count,
            "duration_seconds": duration_seconds,
            "words_per_minute": wpm,
            "pace_verdict": pace_verdict,
            "total_fillers_used": total_fillers,
            "filler_breakdown": filler_counts,
            "fluency_score": fluency_score
        }

    async def generate_interviewer_speech_prompt(
        self,
        job_title: str,
        question_category: str = "behavioral"
    ) -> Dict[str, Any]:
        """Generates natural, spoken-style interview question with follow-up triggers."""
        prompt = f"""
Role: {job_title}
Category: {question_category}

Write a natural, conversational interview question that an engineering director would speak aloud over a Zoom call.
Include:
1. "spoken_question": Natural question text (conversational tone, e.g. 'Hey, thanks for joining today... I'd love to hear about a time when...').
2. "interviewer_persona": Brief description of tone (e.g. 'Friendly but technically rigorous').
3. "listen_for": 3 specific points the candidate must touch upon to score well.
"""
        res = await llm_client.generate_json(
            system_prompt="You are a Principal Engineering Director conducting a warm, senior-level conversational interview.",
            user_prompt=prompt
        )

        return res if res else {
            "spoken_question": f"Thanks for taking the time to chat today. For this {job_title} role, could you walk me through a high-stakes technical challenge you solved recently where things didn't go as planned?",
            "interviewer_persona": "Collaborative, curious, and engineering-depth focused",
            "listen_for": ["Root cause debugging", "Team communication under pressure", "Measurable post-mortem resolution"]
        }


voice_interview_engine = VoiceInterviewEngine()
