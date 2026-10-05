"""The home screen's action list: what the candidate should do next, in priority order."""

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.modules.outcome.today import MAX_ACTIONS_PER_KIND, build_today_actions, next_steps

EMPTY = {"board": {}, "auto_queue": [], "follow_ups": [], "inbox_messages": [], "new_match_count": 0, "closing_soon": []}


def test_nothing_pending_means_an_empty_list():
    assert build_today_actions(**EMPTY) == {"actions": [], "counts": {}, "total": 0}


def test_actions_are_ordered_by_urgency_and_link_to_the_right_screen():
    result = build_today_actions(
        board={
            "Human Review": [{"id": "j1", "title": "Backend", "company": "Acme"}],
            "Applied": [
                {"id": "j2", "title": "Data", "company": "Globex", "submission_confirmed": 0},
                {"id": "j3", "title": "Done", "company": "Initech", "submission_confirmed": 1},
            ],
            "Interview": [{"id": "j4", "title": "Platform", "company": "Umbrella"}],
            "Offer": [{"id": "j5", "title": "Lead", "company": "Hooli"}],
        },
        auto_queue=[
            {"job_key": "a1", "status": "pending_approval", "title": "SRE", "company": "Acme"},
            {"job_key": "a2", "status": "awaiting_user_submission", "title": "QA", "company": "Acme"},
            {"job_key": "a3", "status": "rejected", "title": "Skip", "company": "Acme"},
        ],
        follow_ups=[
            {"job_id": "j3", "title": "Done", "company": "Initech", "due_day": 7},
            {"job_id": "j3", "title": "Done", "company": "Initech", "due_day": 14},
        ],
        inbox_messages=[
            {"id": 1, "status": "UNREAD", "classification": "INTERVIEW_INVITE", "subject": "Interview", "sender_name": "Ada"},
            {"id": 2, "status": "REPLIED", "classification": "INTERVIEW_INVITE", "subject": "Old"},
            {"id": 3, "status": "UNREAD", "classification": "REJECTION", "subject": "Sorry"},
        ],
        new_match_count=4,
        closing_soon=[{"id": "j9", "title": "Python Dev", "company": "IMEE", "deadline": "2026-10-07", "days_left": 2}],
    )

    assert [(a["kind"], a["href"]) for a in result["actions"]] == [
        ("inbox_reply", "/inbox"),
        ("follow_up_due", "/follow-up"),
        ("confirm_submission", "/auto-apply"),
        ("confirm_submission", "/kanban"),
        ("approve_draft", "/auto-apply"),
        ("approve_draft", "/kanban"),
        ("closing_soon", "/jobs?scope=current&minMatch=70"),
        ("interview_prep", "/interview?job=j4"),
        ("offer_review", "/offer-negotiator"),
        ("new_matches", "/jobs?scope=current&minMatch=70"),
    ]
    assert result["total"] == 10
    assert next(a for a in result["actions"] if a["kind"] == "closing_soon")["days"] == 2
    assert result["actions"][-1]["count"] == 4
    assert len({a["id"] for a in result["actions"]}) == 10


def test_long_queues_are_capped_but_still_counted():
    queue = [{"job_key": f"a{i}", "status": "pending_approval"} for i in range(MAX_ACTIONS_PER_KIND + 3)]
    result = build_today_actions(**{**EMPTY, "auto_queue": queue})
    assert len(result["actions"]) == MAX_ACTIONS_PER_KIND
    assert result["counts"] == {"approve_draft": MAX_ACTIONS_PER_KIND + 3}


def test_today_endpoint_serves_the_list():
    response = TestClient(app).get("/api/outcome/today")
    assert response.status_code == 200
    assert set(response.json()) == {"actions", "counts", "total"}


def test_each_stage_unlocks_its_next_steps():
    kinds = lambda job: [step["kind"] for step in next_steps(job)]
    assert kinds({"id": "j", "status": "Draft"}) == []
    assert kinds({"id": "j", "status": "Applied", "submission_confirmed": 0}) == []
    assert kinds({"id": "j", "status": "Applied", "submission_confirmed": 1}) == ["follow_up", "decision_maker"]
    assert kinds({"id": "j", "status": "Interview"}) == ["interview_sim", "star_prep", "salary_intel"]
    assert kinds({"id": "j", "status": "Offer"}) == ["offer_review"]
    assert kinds({"id": "j", "status": "Rejected"}) == ["upskill"]
    assert next_steps({"id": "a b/c", "status": "Interview"})[0]["href"] == "/interview?job=a%20b%2Fc"
