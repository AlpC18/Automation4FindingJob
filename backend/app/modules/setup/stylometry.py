"""
Human Stylometry Profiling Engine
Analyzes authentic human writing samples to produce a mathematical "Personal Style Profile",
measuring Burstiness, Lexical Diversity (TTR), Formality, and Syntactic patterns.
"""

import re
import math
from typing import Dict, Any, List

def calculate_burstiness(sentence_lengths: List[int]) -> float:
    """
    Burstiness measures variation in sentence lengths.
    Human writing has high burstiness (mix of very short punchy sentences and complex ones).
    Standard AI writing has very low variance (monotonous 15-20 words per sentence).
    Returns standard deviation / mean (coefficient of variation).
    """
    if not sentence_lengths or len(sentence_lengths) < 2:
        return 0.5
    mean = sum(sentence_lengths) / len(sentence_lengths)
    variance = sum((x - mean) ** 2 for x in sentence_lengths) / (len(sentence_lengths) - 1)
    std_dev = math.sqrt(variance)
    return round(std_dev / (mean + 1e-6), 3)

def analyze_stylometry(text_samples: List[str]) -> Dict[str, Any]:
    """
    Extracts deep stylometric markers from genuine human writing samples.
    """
    combined_text = "\n".join(text_samples).strip()
    if not combined_text:
        return {
            "style_tone": "Balanced & Direct",
            "avg_sentence_length": 14.0,
            "burstiness_index": 0.65,
            "lexical_diversity": 0.72,
            "formality_score": 75,
            "punctuation_preferences": {"dashes": True, "semicolons": False, "exclamations": False},
            "voice_directives": [
                "Keep sentences punchy and varied in length.",
                "Favor active voice and direct outcomes over corporate jargon.",
                "Use natural transitions rather than robotic signposts."
            ]
        }
        
    # Split into sentences
    sentences = re.split(r'[.!?]+', combined_text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 3]
    
    # Tokenize words
    words = re.findall(r'\b[a-zA-Z\u00C0-\u024F\u1E00-\u1EFF]+\b', combined_text.lower())
    
    sentence_lengths = [len(s.split()) for s in sentences if len(s.split()) > 0]
    avg_sentence_len = round(sum(sentence_lengths) / max(len(sentence_lengths), 1), 2)
    burstiness = calculate_burstiness(sentence_lengths)
    
    # Type-Token Ratio (Vocabulary richness)
    unique_words = set(words)
    lexical_diversity = round(len(unique_words) / max(len(words), 1), 3)
    
    # Punctuation markers
    has_dashes = ("-" in combined_text or "—" in combined_text)
    has_semicolons = (";" in combined_text)
    exclamation_count = combined_text.count("!")
    
    # Formality estimation based on contractions and complex words
    contractions = len(re.findall(r"\b(i'm|don't|can't|it's|we've|you'll|they're)\b", combined_text.lower()))
    formality = max(10, min(95, int(85 - (contractions * 5) + (lexical_diversity * 20))))
    
    # Tone label
    if formality > 75 and avg_sentence_len > 16:
        tone = "Formal & Analytical"
    elif burstiness > 0.6 and formality < 65:
        tone = "Dynamic & Direct (Founder/Tech Lead tone)"
    else:
        tone = "Modern Professional & Concise"
        
    voice_directives = [
        f"Target average sentence length around {int(avg_sentence_len)} words.",
        f"Maintain a burstiness coefficient >= {burstiness} (mix short clauses with longer explanations).",
        "Strictly avoid robotic qualifiers and passive AI fluff.",
        "Highlight pragmatic achievements and concrete engineering decisions."
    ]
    
    return {
        "style_tone": tone,
        "avg_sentence_length": avg_sentence_len,
        "burstiness_index": burstiness,
        "lexical_diversity": lexical_diversity,
        "formality_score": formality,
        "punctuation_preferences": {
            "dashes": has_dashes,
            "semicolons": has_semicolons,
            "exclamations": exclamation_count > 0
        },
        "voice_directives": voice_directives
    }
