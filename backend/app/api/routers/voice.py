"""Voice interview APIs backed by OpenAI Whisper and text-to-speech."""

from typing import Optional

import httpx
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel

from backend.app.core.config import settings
from backend.app.core.file_scanner import enforce_upload_scan
from backend.app.core.provider_credentials import get_provider_api_key
from backend.app.modules.interview.voice_engine import voice_interview_engine

router = APIRouter()


def _tts_provider() -> str:
    """Resolve the configured TTS adapter without importing optional providers."""
    configured = (settings.VOICE_TTS_PROVIDER or "openai").strip().lower()
    if configured in {"edge", "edge-tts", "edge_tts"}:
        return "edge"
    if configured == "auto" and not get_provider_api_key("openai"):
        return "edge"
    return "openai"


def _audio_media_type(response_format: str) -> str:
    return {
        "mp3": "audio/mpeg",
        "opus": "audio/opus",
        "aac": "audio/aac",
        "flac": "audio/flac",
        "wav": "audio/wav",
        "pcm": "audio/L16",
    }[response_format]


async def _synthesize_edge_audio(text: str, voice: str) -> bytes:
    """Collect Edge TTS audio while keeping the optional dependency lazy."""
    try:
        import edge_tts
    except ImportError as exc:
        raise HTTPException(
            status_code=503,
            detail="Edge TTS için edge-tts bağımlılığı kurulmalıdır.",
        ) from exc

    try:
        communicator = edge_tts.Communicate(text, voice)
        chunks = []
        async for chunk in communicator.stream():
            if chunk.get("type") == "audio" and chunk.get("data"):
                chunks.append(chunk["data"])
        audio = b"".join(chunks)
    except Exception as exc:  # pragma: no cover - provider/network-specific errors
        raise HTTPException(status_code=502, detail="Edge TTS üretimi başarısız oldu.") from exc

    if not audio:
        raise HTTPException(status_code=502, detail="Edge TTS boş ses döndürdü.")
    return audio


def _validate_synthesis_request(req: "VoiceSynthesisRequest") -> str:
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="TTS metni boş olamaz.")
    if req.response_format not in {"mp3", "opus", "aac", "flac", "wav", "pcm"}:
        raise HTTPException(status_code=400, detail="Desteklenmeyen ses formatı.")
    provider = _tts_provider()
    if provider == "edge" and req.response_format != "mp3":
        raise HTTPException(
            status_code=400,
            detail="Edge TTS yalnızca mp3 çıktı formatını destekler.",
        )
    return provider


class VoiceAnalyzeRequest(BaseModel):
    transcript_text: str
    duration_seconds: Optional[float] = 60.0


@router.post("/interview/voice/analyze")
@router.post("/api/interview/voice/analyze")
def analyze_voice_interview_transcript(req: VoiceAnalyzeRequest):
    """Analyze a transcript for pace, fluency, and filler words."""
    return voice_interview_engine.analyze_spoken_transcript(
        transcript_text=req.transcript_text,
        duration_seconds=req.duration_seconds or 60.0,
    )


class VoiceQuestionRequest(BaseModel):
    job_title: str
    question_category: Optional[str] = "behavioral"


@router.post("/interview/voice/question")
@router.post("/api/interview/voice/question")
async def generate_interviewer_spoken_question(req: VoiceQuestionRequest):
    """Generate a conversational question for a live mock interview."""
    return await voice_interview_engine.generate_interviewer_speech_prompt(
        job_title=req.job_title,
        question_category=req.question_category or "behavioral",
    )


@router.post("/interview/voice/transcribe")
@router.post("/api/interview/voice/transcribe")
async def transcribe_voice_answer(
    audio: UploadFile = File(...),
    language: Optional[str] = Form(default=None),
):
    """Transcribe a browser-recorded answer with OpenAI Whisper."""
    api_key = get_provider_api_key("openai")
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="Whisper kullanımı için OPENAI_API_KEY yapılandırılmalıdır.",
        )

    audio_bytes = await audio.read(25 * 1024 * 1024 + 1)
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Ses dosyası boş.")
    if len(audio_bytes) > 25 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Ses dosyası en fazla 25 MB olabilir.")
    try:
        enforce_upload_scan(audio_bytes)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    data = {"model": settings.VOICE_STT_MODEL}
    if language:
        data["language"] = language

    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            response = await client.post(
                "https://api.openai.com/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {api_key}"},
                data=data,
                files={
                    "file": (
                        audio.filename or "voice-answer.webm",
                        audio_bytes,
                        audio.content_type or "application/octet-stream",
                    )
                },
            )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        detail = "Whisper transkripsiyonu başarısız oldu."
        try:
            detail = exc.response.json().get("error", {}).get("message", detail)
        except ValueError:
            pass
        raise HTTPException(status_code=502, detail=detail) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="Whisper servisine erişilemedi.") from exc

    payload = response.json()
    return {
        "text": payload.get("text", "").strip(),
        "provider": "openai-whisper",
        "model": settings.VOICE_STT_MODEL,
    }


class VoiceSynthesisRequest(BaseModel):
    text: str
    voice: Optional[str] = None
    response_format: str = "mp3"


@router.post("/interview/voice/synthesize")
@router.post("/api/interview/voice/synthesize")
async def synthesize_interviewer_voice(req: VoiceSynthesisRequest):
    """Synthesize an interviewer question as audio."""
    provider = _validate_synthesis_request(req)
    if provider == "edge":
        audio = await _synthesize_edge_audio(
            req.text.strip(), req.voice or settings.VOICE_EDGE_TTS_VOICE
        )
        return Response(
            content=audio,
            media_type="audio/mpeg",
            headers={
                "X-Voice-Provider": "edge-tts",
                "X-Voice-Voice": req.voice or settings.VOICE_EDGE_TTS_VOICE,
            },
        )

    api_key = get_provider_api_key("openai")
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="TTS kullanımı için OPENAI_API_KEY yapılandırılmalıdır.",
        )

    payload = {
        "model": settings.VOICE_TTS_MODEL,
        "input": req.text,
        "voice": req.voice or settings.VOICE_TTS_VOICE,
        "response_format": req.response_format,
    }
    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            response = await client.post(
                "https://api.openai.com/v1/audio/speech",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        detail = "TTS üretimi başarısız oldu."
        try:
            detail = exc.response.json().get("error", {}).get("message", detail)
        except ValueError:
            pass
        raise HTTPException(status_code=502, detail=detail) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="TTS servisine erişilemedi.") from exc

    media_type = _audio_media_type(req.response_format)
    return Response(
        content=response.content,
        media_type=media_type,
        headers={
            "X-Voice-Provider": "openai-tts",
            "X-Voice-Model": settings.VOICE_TTS_MODEL,
        },
    )


@router.post("/interview/voice/synthesize/stream")
@router.post("/api/interview/voice/synthesize/stream")
async def stream_interviewer_voice(req: VoiceSynthesisRequest):
    """Stream TTS bytes as they arrive for low-latency interview playback."""
    provider = _validate_synthesis_request(req)
    if provider == "edge":
        audio = await _synthesize_edge_audio(
            req.text.strip(), req.voice or settings.VOICE_EDGE_TTS_VOICE
        )
        return StreamingResponse(
            iter([audio]),
            media_type="audio/mpeg",
            headers={
                "X-Voice-Provider": "edge-tts",
                "X-Voice-Voice": req.voice or settings.VOICE_EDGE_TTS_VOICE,
                "Cache-Control": "no-store",
            },
        )

    api_key = get_provider_api_key("openai")
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="TTS kullanımı için OPENAI_API_KEY yapılandırılmalıdır.",
        )

    payload = {
        "model": settings.VOICE_TTS_MODEL,
        "input": req.text,
        "voice": req.voice or settings.VOICE_TTS_VOICE,
        "response_format": req.response_format,
    }
    media_type = _audio_media_type(req.response_format)

    async def audio_chunks():
        async with httpx.AsyncClient(timeout=90.0) as client:
            async with client.stream(
                "POST",
                "https://api.openai.com/v1/audio/speech",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            ) as response:
                if response.status_code >= 400:
                    detail = "TTS streaming üretimi başarısız oldu."
                    try:
                        error_payload = response.json()
                        detail = error_payload.get("error", {}).get("message", detail)
                    except (TypeError, ValueError):
                        pass
                    raise HTTPException(status_code=502, detail=detail)
                async for chunk in response.aiter_bytes():
                    if chunk:
                        yield chunk

    return StreamingResponse(
        audio_chunks(),
        media_type=media_type,
        headers={
            "X-Voice-Provider": "openai-tts",
            "X-Voice-Model": settings.VOICE_TTS_MODEL,
            "Cache-Control": "no-store",
        },
    )
