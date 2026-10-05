"""
Writing Style Guide System
Adapted from MadsLorentzen/ai-job-search 03-writing-style.md concept.

Defines and enforces a candidate's unique writing style for all generated documents:
- Tone preferences (formal, conversational, technical)
- Structural patterns (paragraph length, bullet style, headers)
- Do's and Don'ts (specific words/phrases to use or avoid)
- Cultural adaptations per market

Works alongside the humanizer engine to ensure generated text matches
the candidate's authentic voice, not generic AI output.
"""

from typing import Dict, Any, List, Optional
from backend.app.core.event_logger import agent_logger


class WritingStyleGuide:
    """Manages candidate writing style preferences and enforcement rules."""

    DEFAULT_STYLE = {
        "tone": "professional_conversational",
        "formality": "mid",
        "paragraph_length": "medium",  # short, medium, long
        "sentence_variety": True,
        "use_first_person": True,
        "active_voice_preference": True,
        "bullet_style": "dash",  # dash, dot, number
        "max_paragraph_sentences": 5,
    }

    # Words/phrases that sound generic/AI-generated
    FORBIDDEN_PHRASES = [
        "I am excited to", "I am thrilled", "I am passionate about",
        "proven track record", "results-driven", "detail-oriented",
        "team player", "synergy", "leverage", "utilize",
        "paradigm", "ecosystem", "holistic", "cutting-edge",
        "best-in-class", "world-class", "state-of-the-art",
        "spearheaded", "delve", "tapestry", "testament",
        "landscape", "navigate", "multifaceted", "robust",
        "hemen hemen", "çığır açan", "büyük bir tutkuyla",
    ]

    # Preferred alternatives for common AI phrases
    ALTERNATIVES = {
        "I am excited to": ["I'd welcome the chance to", "I'm drawn to", "What caught my eye is"],
        "I am thrilled": ["I'm genuinely interested in", "This role stands out because"],
        "proven track record": ["consistent results in", "demonstrated by"],
        "leverage": ["use", "apply", "build on"],
        "utilize": ["use", "work with", "apply"],
        "spearheaded": ["led", "built", "designed", "initiated"],
        "delve": ["explore", "dig into", "examine"],
        "ecosystem": ["environment", "stack", "platform"],
        "navigate": ["work through", "handle", "manage"],
        "robust": ["reliable", "solid", "dependable"],
    }

    TONE_PRESETS = {
        "technical": {
            "description": "Teknik, özlü, metrik odaklı",
            "description_en": "Technical, concise, metrics-focused",
            "rules": [
                "Lead with technical specifics, not adjectives",
                "Include quantifiable metrics where possible",
                "Use precise technology names (React 18, not 'modern frameworks')",
                "Short paragraphs, max 3-4 sentences",
            ],
        },
        "professional_conversational": {
            "description": "Profesyonel ama sıcak, doğal akışlı",
            "description_en": "Professional but warm, natural flow",
            "rules": [
                "Write as you'd speak in a professional meeting",
                "Mix short punchy sentences with longer explanations",
                "Use contractions occasionally (I'm, I've, it's)",
                "One personal/genuine touch per document",
            ],
        },
        "formal": {
            "description": "Resmi, geleneksel kurumsal ton",
            "description_en": "Formal, traditional corporate tone",
            "rules": [
                "No contractions",
                "Third-person references where appropriate",
                "Structured paragraphs with topic sentences",
                "Measured, precise language",
            ],
        },
        "startup_casual": {
            "description": "Rahat, direkt, sonuç odaklı",
            "description_en": "Casual, direct, outcome-focused",
            "rules": [
                "Skip the formalities, get to the point",
                "Use 'I built X that did Y' format",
                "Contractions are fine, personality is encouraged",
                "Show energy without buzzwords",
            ],
        },
    }

    def get_tone_presets(self) -> Dict[str, Any]:
        """Return available tone presets."""
        return self.TONE_PRESETS

    def build_style_guide(
        self,
        tone: str = "professional_conversational",
        custom_dos: Optional[List[str]] = None,
        custom_donts: Optional[List[str]] = None,
        preferred_phrases: Optional[List[str]] = None,
        avoided_phrases: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Build a complete writing style guide.

        Args:
            tone: One of the TONE_PRESETS keys
            custom_dos: Custom rules about what TO do
            custom_donts: Custom rules about what NOT to do
            preferred_phrases: Phrases the candidate likes to use
            avoided_phrases: Additional phrases to avoid
        """
        base = dict(self.DEFAULT_STYLE)
        base["tone"] = tone

        tone_preset = self.TONE_PRESETS.get(tone, self.TONE_PRESETS["professional_conversational"])

        guide = {
            **base,
            "tone_description": tone_preset["description"],
            "tone_rules": tone_preset["rules"],
            "forbidden_phrases": self.FORBIDDEN_PHRASES + (avoided_phrases or []),
            "preferred_phrases": preferred_phrases or [],
            "alternatives": self.ALTERNATIVES,
            "custom_dos": custom_dos or [],
            "custom_donts": custom_donts or [],
        }

        agent_logger.log_event(
            "WRITING_STYLE",
            f"Style guide built: tone={tone}, "
            f"forbidden={len(guide['forbidden_phrases'])}, "
            f"preferred={len(guide['preferred_phrases'])}"
        )

        return guide

    def check_compliance(
        self,
        text: str,
        style_guide: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Check if a text complies with the writing style guide.

        Returns compliance score and specific violations.
        """
        violations = []
        suggestions = []
        text_lower = text.lower()

        # Check forbidden phrases
        for phrase in style_guide.get("forbidden_phrases", []):
            if phrase.lower() in text_lower:
                alt = self.ALTERNATIVES.get(phrase)
                if alt:
                    violations.append({
                        "phrase": phrase,
                        "type": "forbidden_phrase",
                        "suggestion": f"Replace with: {' or '.join(alt[:2])}",
                    })
                else:
                    violations.append({
                        "phrase": phrase,
                        "type": "forbidden_phrase",
                        "suggestion": "Remove or rephrase",
                    })

        # Check sentence variety
        import re
        sentences = [s.strip() for s in re.split(r'[.!?]+', text) if len(s.strip()) > 3]
        if sentences:
            lengths = [len(s.split()) for s in sentences]
            avg_len = sum(lengths) / len(lengths)
            variance = sum((l - avg_len) ** 2 for l in lengths) / len(lengths)

            if variance < 5:
                suggestions.append(
                    "Cümle uzunlukları çok tekdüze. "
                    "Kısa ve uzun cümleleri karıştırın (burstiness)."
                )

        # Check paragraph length
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        max_para = style_guide.get("max_paragraph_sentences", 5)
        for i, para in enumerate(paragraphs, 1):
            para_sentences = len(re.split(r'[.!?]+', para))
            if para_sentences > max_para + 2:
                suggestions.append(
                    f"Paragraf {i} çok uzun ({para_sentences} cümle). "
                    f"Maksimum {max_para} cümle önerilir."
                )

        # Calculate compliance score
        score = 100
        score -= len(violations) * 10
        score -= len(suggestions) * 5
        score = max(0, min(100, score))

        return {
            "compliance_score": score,
            "violations": violations,
            "suggestions": suggestions,
            "violation_count": len(violations),
            "is_compliant": score >= 70,
        }

    def auto_fix(
        self,
        text: str,
        style_guide: Dict[str, Any],
    ) -> str:
        """
        Automatically fix simple style violations in text.
        Uses the alternatives mapping for known forbidden phrases.
        """
        import random
        fixed = text

        for phrase, alternatives in self.ALTERNATIVES.items():
            if phrase.lower() in fixed.lower():
                replacement = random.choice(alternatives)
                # Case-insensitive replace
                import re
                pattern = re.compile(re.escape(phrase), re.IGNORECASE)
                fixed = pattern.sub(replacement, fixed, count=1)

        return fixed


# Module-level singleton
writing_style_guide = WritingStyleGuide()
