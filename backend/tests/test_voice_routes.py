"""Voice interview routes refuse bad input before any paid speech service is called."""

from fastapi.testclient import TestClient

from backend.app.api.routers import voice as routes
from backend.app.main import app

client = TestClient(app)


def test_a_transcript_is_analysed_for_pace_and_fillers():
    response = client.post("/api/interview/voice/analyze", json={
        "transcript_text": "Um, so I, like, built the billing service and, um, it handled forty thousand invoices a day.",
        "duration_seconds": 20,
    })

    assert response.status_code == 200 and response.json()


def test_a_practice_question_is_available_without_an_ai_provider(monkeypatch):
    async def no_answer(**kwargs):
        return {}

    monkeypatch.setattr(routes.voice_interview_engine.__class__.generate_interviewer_speech_prompt.__globals__["llm_client"], "generate_json", no_answer)

    question = client.post("/api/interview/voice/question", json={"job_title": "Backend Developer"}).json()

    assert "Backend Developer" in question["spoken_question"] and len(question["listen_for"]) == 3


def test_speech_requests_are_validated(monkeypatch):
    monkeypatch.setattr(routes, "_tts_provider", lambda: "edge")

    assert client.post("/api/interview/voice/synthesize", json={"text": "   "}).status_code == 400
    assert client.post("/api/interview/voice/synthesize", json={"text": "Hello", "response_format": "midi"}).status_code == 400
    assert client.post("/api/interview/voice/synthesize", json={"text": "Hello", "response_format": "wav"}).status_code == 400
    assert client.post("/api/interview/voice/synthesize/stream", json={"text": ""}).status_code == 400

    monkeypatch.setattr(routes, "_tts_provider", lambda: "openai")
    monkeypatch.setattr(routes, "get_provider_api_key", lambda provider: "")
    assert client.post("/api/interview/voice/synthesize", json={"text": "Hello"}).status_code == 503


def test_transcription_needs_a_key_and_a_non_empty_recording(monkeypatch):
    audio = {"audio": ("answer.webm", b"", "audio/webm")}

    monkeypatch.setattr(routes, "get_provider_api_key", lambda provider: "")
    assert client.post("/api/interview/voice/transcribe", files=audio).status_code == 503

    monkeypatch.setattr(routes, "get_provider_api_key", lambda provider: "key")
    assert client.post("/api/interview/voice/transcribe", files=audio).status_code == 400
