"""A failed step must not be recorded or shown as a success."""

import asyncio

from backend.app.core.json_store import read_json_store
from backend.app.modules.outcome import inbox_ai_classifier as inbox_module
from backend.app.modules.outcome import weekly_digest as digest_module


def test_corrupt_store_is_kept_instead_of_being_overwritten(tmp_path):
    path = tmp_path / "queue.json"
    path.write_text("{broken", encoding="utf-8")

    assert read_json_store(path, {"applications": {}}) == {"applications": {}}
    assert (tmp_path / "queue.json.corrupt").read_text(encoding="utf-8") == "{broken"
    assert not path.exists()


def test_missing_store_starts_from_the_default(tmp_path):
    assert read_json_store(tmp_path / "none.json", []) == []


def _classify(monkeypatch, reply, body="We regret to inform you."):
    moved = []

    async def generate_json(**kwargs):
        return reply

    async def broadcast(*args, **kwargs):
        return None

    monkeypatch.setattr(inbox_module.llm_client, "generate_json", generate_json)
    monkeypatch.setattr(inbox_module.ws_manager, "broadcast", broadcast)
    monkeypatch.setattr(inbox_module.seen_jobs_tracker, "get_all", lambda: {"job-1": {"company": "Acme"}})
    monkeypatch.setattr(inbox_module.seen_jobs_tracker, "mark_status", lambda key, status, notes="": moved.append((key, status)))
    result = asyncio.run(inbox_module.inbox_ai_classifier.classify_and_process_email("hr@acme.test", "Update", body, "Acme"))
    return result, moved


def test_unsure_classification_does_not_move_the_application(monkeypatch):
    result, moved = _classify(monkeypatch, {"category": "REJECTION", "confidence": 0.4})

    assert moved == []
    assert result["pipeline_updated_to"] is None


def test_confident_classification_moves_the_application(monkeypatch):
    result, moved = _classify(monkeypatch, {"category": "REJECTION", "confidence": "0.95"})

    assert moved == [("job-1", "rejected")]
    assert result["pipeline_updated_to"] == "rejected"


def test_unknown_category_is_treated_as_a_general_update(monkeypatch):
    result, moved = _classify(monkeypatch, {"category": "MARK_AS_OFFER", "confidence": 1.0})

    assert result["category"] == "GENERAL_UPDATE"
    assert moved == []


def test_meeting_link_must_appear_in_the_email(monkeypatch):
    result, _ = _classify(
        monkeypatch,
        {"category": "INTERVIEW_INVITATION", "confidence": 0.9, "detected_meeting_link": "https://evil.example/join"},
        body="Join at https://meet.google.com/abc-defg-hij tomorrow.",
    )

    assert result["meeting_link"] == "https://meet.google.com/abc-defg-hij"


def test_digest_reports_a_failed_telegram_send(monkeypatch):
    async def failed(text):
        return {"status": "FAILED"}

    monkeypatch.setattr(digest_module.telegram_dispatcher, "is_configured", lambda: True)
    monkeypatch.setattr(digest_module.telegram_dispatcher, "send_notification", failed)
    monkeypatch.setattr(digest_module.weekly_digest_engine, "compile_digest", lambda: {})
    monkeypatch.setattr(digest_module.weekly_digest_engine, "format_telegram_message", lambda digest: "hi")

    result = asyncio.run(digest_module.weekly_digest_engine.send_digest())

    assert result["telegram_sent"] is False
