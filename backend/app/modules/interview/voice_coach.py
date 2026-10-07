"""
Voice AI Interview Coach & Vocal Performance Engine
Analyzes spoken interview answers: Words Per Minute (WPM),
filler words ratio (um, uh, like, yani), STAR framework alignment, and technical depth.
"""

import re
from typing import Dict, Any, List

FILLER_WORDS = [
    "um", "uh", "like", "you know", "actually", "basically", "literally",
    "yani", "şey", "ııı", "eee", "mesela", "falan", "filan", "açıkçası"
]

class VoiceInterviewCoach:
    def __init__(self):
        self.ideal_wpm_min = 120
        self.ideal_wpm_max = 160

    def get_personas(self) -> List[Dict[str, Any]]:
        return [
            {
                "id": "alex_vp",
                "name": "Alex Vance (VP of Engineering)",
                "accent": "US Corporate",
                "tone": "Direct, fast-paced, pragmatic",
                "focus": "Scalability, architectural tradeoffs, leadership"
            },
            {
                "id": "elena_hr",
                "name": "Elena Rostova (Head of Talent)",
                "accent": "UK Professional",
                "tone": "Empathetic, structured, conversational",
                "focus": "Team dynamics, conflict resolution, cultural fit"
            },
            {
                "id": "marcus_principal",
                "name": "Marcus Chen (Principal Architect)",
                "accent": "Global Tech",
                "tone": "Deeply analytical, rigorous",
                "focus": "Distributed systems, concurrency, low-level optimization"
            }
        ]

    def evaluate_vocal_performance(
        self,
        question: str,
        transcript: str,
        duration_seconds: float = 30.0
    ) -> Dict[str, Any]:
        """
        Computes detailed vocal performance metrics and actionable recommendations.
        """
        clean_text = transcript.strip()
        words = clean_text.split()
        word_count = len(words)

        # 1. Speaking Pace (WPM)
        duration = max(duration_seconds, 1.0)
        wpm = round((word_count / duration) * 60)

        if wpm < self.ideal_wpm_min:
            pace_label = "Slow (Düşük Hız)"
            pace_feedback = f"Konuşma temponuz dakikada {wpm} kelime ile biraz yavaş. Hedef: 130-150 WPM."
        elif wpm > self.ideal_wpm_max:
            pace_label = "Fast (Çok Hızlı)"
            pace_feedback = f"Konuşma temponuz dakikada {wpm} kelime ile biraz hızlı. Nefes alarak cümleleri netleştirin."
        else:
            pace_label = "Ideal (Mükemmel Ritim)"
            pace_feedback = f"Dakikada {wpm} kelime ile uluslararası mülakat standardında ideal tempoda konuştunuz."

        # 2. Filler Words (Dolgu Kelimeler)
        text_lower = clean_text.lower()
        detected_fillers = {}
        total_fillers = 0

        for filler in FILLER_WORDS:
            count = len(re.findall(rf"\b{re.escape(filler)}\b", text_lower))
            if count > 0:
                detected_fillers[filler] = count
                total_fillers += count

        filler_ratio = round((total_fillers / max(word_count, 1)) * 100, 1)
        fluency_score = max(0, min(100, round(100 - (filler_ratio * 4))))

        # 3. STAR Framework Scoring
        star_markers = {
            "situation": ["when", "at my previous", "in my project", "zaman", "şirketimde", "projemde"],
            "task": ["my goal", "we needed", "the challenge", "hedefimiz", "gerekiyordu", "problem"],
            "action": ["i built", "i engineered", "i optimized", "geliştirdim", "tasarladım", "çözdüm"],
            "result": ["resulted in", "improved by", "achieved", "sonucunda", "oranında", "sağlandı"]
        }
        
        star_found = {}
        for stage, keywords in star_markers.items():
            star_found[stage] = any(kw in text_lower for kw in keywords)

        star_adherence = round((sum(star_found.values()) / 4) * 100)

        # 4. Technical Depth & Overall Score
        tech_keywords = [
            "latency", "database", "api", "cache", "async", "docker", "pipeline",
            "microservice", "testing", "scale", "throughput", "memory", "redis", "fastapi"
        ]
        tech_count = sum(1 for kw in tech_keywords if kw in text_lower)
        tech_score = min(100, tech_count * 20 + 40)

        overall_score = round((fluency_score * 0.35) + (star_adherence * 0.35) + (tech_score * 0.30))

        # Actionable Suggestions
        suggestions = []
        if total_fillers > 2:
            suggestions.append(f"Dolgu kelimeleri ({', '.join(detected_fillers.keys())}) azaltmak için düşünürken 1 saniyelik sessiz duraklamalar yapın.")
        if not star_found["result"]:
            suggestions.append("Cevabınızın sonuna ölçülebilir bir metrik veya sonuç ekleyin (Örn: '%30 hızlanma sağlandı').")
        if wpm < 110:
            suggestions.append("Ses tonunuza biraz daha dinamizm ve enerji katarak konuşma temponuzu artırın.")

        if not suggestions:
            suggestions.append("Cevabınız STAR metoduna uygun, net ve teknik olarak güçlü bir yapıya sahip.")

        return {
            "question": question,
            "transcript": clean_text,
            "duration_seconds": round(duration, 1),
            "word_count": word_count,
            "wpm": wpm,
            "pace_label": pace_label,
            "pace_feedback": pace_feedback,
            "filler_words_detected": detected_fillers,
            "total_fillers": total_fillers,
            "filler_ratio_percent": filler_ratio,
            "fluency_score": fluency_score,
            "star_adherence_percent": star_adherence,
            "star_breakdown": star_found,
            "overall_score": overall_score,
            "actionable_suggestions": suggestions
        }

voice_coach = VoiceInterviewCoach()
