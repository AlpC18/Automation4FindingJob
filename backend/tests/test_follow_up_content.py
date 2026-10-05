from backend.app.modules.outcome.follow_up_cadence import FollowUpCadenceEngine
from backend.app.modules.outcome.follow_up_scheduler import generate_follow_up_email


def test_follow_up_templates_do_not_invent_candidate_achievements():
    sequence = FollowUpCadenceEngine().generate_cadence_messages("Example Company", "Backend Engineer")
    all_text = "\n".join(item["body"] for item in sequence["cadence"])

    assert "Example Company" in all_text
    assert "Backend Engineer" in all_text
    assert "35%" not in all_text
    assert "autonomous pipeline" not in all_text
    assert "modern backend systems" not in all_text

    day_nine_draft = generate_follow_up_email("Example Company", "Backend Engineer", 9)
    assert "35%" not in day_nine_draft
    assert "scalable architectures" not in day_nine_draft
    assert "Candidate" not in day_nine_draft
