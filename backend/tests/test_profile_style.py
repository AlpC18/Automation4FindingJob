"""Behavioural profile, cultural fit and the writing-style checker."""

from backend.app.modules.setup.behavioral_profile import behavioral_profiler
from backend.app.modules.setup.writing_style import writing_style_guide

ANSWERS = {"communication": "direct", "work_style": "autonomous", "motivation": "leadership",
           "energy_source": "ambivert", "team_size": "startup_small", "unknown": "ignored"}


def test_the_questionnaire_lists_every_dimension():
    questions = behavioral_profiler.get_assessment_questions()

    assert [dimension["id"] for dimension in questions["dimensions"]] == [
        "communication", "work_style", "motivation", "conflict_resolution", "energy_source"]
    assert len(questions["environment_preferences"]) == 3


def test_a_profile_keeps_only_answered_dimensions():
    profile = behavioral_profiler.build_profile(ANSWERS)

    assert set(profile["dimensions"]) == {"communication", "work_style", "motivation", "energy_source"}
    assert profile["dimensions"]["work_style"]["label_en"] == "Autonomous, minimal oversight"
    assert profile["environment_preferences"] == {"team_size": "startup_small"}
    assert profile["summary"].startswith("İletişim: Doğrudan ve açık")
    assert behavioral_profiler.build_profile({})["summary"] == "Profil henüz tamamlanmadı"
    assert behavioral_profiler.build_profile({"communication": "made-up"})["dimensions"]["communication"]["label"] == "made-up"


def test_cultural_fit_rises_and_falls_with_the_posting():
    autonomous = behavioral_profiler.build_profile(ANSWERS)
    methodical = behavioral_profiler.build_profile({"work_style": "methodical"})
    posting = {"description": "Fast-paced startup. Independent work in a cross-functional team; you will mentor juniors."}

    strong = behavioral_profiler.calculate_cultural_fit(autonomous, posting)
    weak = behavioral_profiler.calculate_cultural_fit(methodical, posting)
    neutral = behavioral_profiler.calculate_cultural_fit(autonomous, {"description": "Write reports."})

    assert (strong["cultural_fit_score"], strong["recommendation"], len(strong["signals"])) == (100, "Yüksek uyum", 4)
    assert (weak["cultural_fit_score"], weak["recommendation"]) == (40, "Düşük uyum — dikkatli değerlendirin")
    assert (neutral["cultural_fit_score"], neutral["signals"]) == (50, [])


def test_style_guide_merges_the_tone_with_personal_rules():
    guide = writing_style_guide.build_style_guide(tone="technical", avoided_phrases=["rockstar"], custom_dos=["Name the project"])
    fallback = writing_style_guide.build_style_guide(tone="no-such-tone")

    assert guide["tone_description"] == "Teknik, özlü, metrik odaklı"
    assert "rockstar" in guide["forbidden_phrases"] and guide["custom_dos"] == ["Name the project"]
    assert fallback["tone_rules"] == writing_style_guide.get_tone_presets()["professional_conversational"]["rules"]


def test_compliance_flags_stock_phrases_flat_rhythm_and_long_paragraphs():
    guide = writing_style_guide.build_style_guide()
    stock = "I am excited to apply. I have a proven track record. I am a team player here."
    varied = "I built the billing service. It handles forty thousand invoices a day without a single manual step, which is why I applied."
    long_paragraph = ". ".join(["This is one more sentence in a very long paragraph"] * 9) + "."

    flagged = writing_style_guide.check_compliance(stock, guide)
    clean = writing_style_guide.check_compliance(varied, guide)

    assert {item["phrase"] for item in flagged["violations"]} == {"I am excited to", "proven track record", "team player"}
    assert flagged["violations"][0]["suggestion"].startswith("Replace with:")
    assert any("tekdüze" in tip for tip in flagged["suggestions"])
    assert (clean["compliance_score"], clean["is_compliant"], clean["violation_count"]) == (100, True, 0)
    assert any("çok uzun" in tip for tip in writing_style_guide.check_compliance(long_paragraph, guide)["suggestions"])


def test_auto_fix_replaces_known_stock_phrases_only():
    guide = writing_style_guide.build_style_guide()

    fixed = writing_style_guide.auto_fix("I am excited to LEVERAGE Python. Plain sentence.", guide)

    assert "excited" not in fixed and "leverage" not in fixed.lower()
    assert fixed.endswith("Python. Plain sentence.")
