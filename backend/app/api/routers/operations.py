"""Operational controls: SMTP settings, logs and LLM providers."""

from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, SecretStr

from backend.app.core.event_logger import agent_logger
from backend.app.core.llm_client import llm_client
from backend.app.core.provider_credentials import (
    delete_provider_api_key,
    get_provider_credential_status,
    save_provider_api_key,
)
from backend.app.core.smtp_credentials import (
    delete_smtp_configuration,
    save_smtp_configuration,
    smtp_configuration_status,
    test_smtp_connection,
)


router = APIRouter()


@router.get("/notifications/smtp")
def get_smtp_settings():
    return smtp_configuration_status()


class SaveSmtpConfigurationRequest(BaseModel):
    host: str = Field(min_length=1, max_length=255)
    port: int = Field(default=587, ge=1, le=65535)
    username: str = Field(default="", max_length=254)
    password: SecretStr = Field(default=SecretStr(""), max_length=1024)
    from_email: str = Field(min_length=3, max_length=254)
    use_tls: bool = True


@router.put("/notifications/smtp")
def put_smtp_settings(req: SaveSmtpConfigurationRequest):
    try:
        save_smtp_configuration(
            host=req.host, port=req.port, username=req.username,
            password=req.password.get_secret_value(), from_email=req.from_email, use_tls=req.use_tls,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail="SMTP ayarları güvenli biçimde kaydedilemedi; uygulama şifreleme anahtarını kontrol edin.") from exc
    return {"status": "saved", **smtp_configuration_status()}


@router.delete("/notifications/smtp")
def remove_smtp_settings():
    delete_smtp_configuration()
    return {"status": "deleted", **smtp_configuration_status()}


@router.post("/notifications/smtp/test")
def test_smtp_settings():
    return test_smtp_connection()


@router.get("/stream/agent_logs")
def get_agent_logs():
    return {"logs": agent_logger.get_recent_logs()}


@router.get("/llm/providers")
def get_llm_providers():
    return llm_client.get_providers_status()


@router.get("/llm/usage")
def get_llm_usage():
    return llm_client.get_usage_today()


@router.get("/llm/credentials")
def get_llm_credentials():
    return {"providers": get_provider_credential_status()}


class SaveProviderCredentialRequest(BaseModel):
    provider: str
    api_key: str


@router.put("/llm/credentials")
def put_llm_credential(req: SaveProviderCredentialRequest):
    try:
        save_provider_api_key(req.provider, req.api_key)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"status": "SUCCESS", "provider": req.provider.lower(), "message": "API anahtarı şifreli olarak kaydedildi."}


@router.delete("/llm/credentials/{provider}")
def remove_llm_credential(provider: str):
    try:
        delete_provider_api_key(provider)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "SUCCESS", "provider": provider.lower()}


class SetProviderRequest(BaseModel):
    provider: str
    model: Optional[str] = None


@router.post("/llm/set_provider")
def set_active_llm_provider(req: SetProviderRequest):
    known = {item["id"] for item in llm_client.get_providers_status()["providers"]} | {"auto"}
    if req.provider.lower() not in known:
        raise HTTPException(status_code=422, detail="Bilinmeyen yapay zekâ sağlayıcısı.")
    llm_client.set_active_provider(req.provider, req.model)
    agent_logger.log_event(
        "LLM_HUB",
        f"Active LLM provider switched to {req.provider} (Model: {req.model or 'default'}).",
    )
    return {"status": "SUCCESS", "active_provider": req.provider, "model": req.model}


class TestConnectionRequest(BaseModel):
    provider: str


@router.post("/llm/test_connection")
async def test_llm_connection(req: TestConnectionRequest):
    agent_logger.log_event("LLM_HUB", f"Pinging provider {req.provider}...")
    return await llm_client.test_provider_connection(req.provider)


class LLMGenerateRequest(BaseModel):
    system_prompt: str
    user_prompt: str
    provider: Optional[str] = "auto"
    temperature: Optional[float] = 0.7


@router.post("/llm/generate")
async def call_llm_provider(req: LLMGenerateRequest):
    agent_logger.log_event("LLM_CORE", f"Executing generation with provider: {req.provider}...")
    result = await llm_client.generate_text(
        system_prompt=req.system_prompt,
        user_prompt=req.user_prompt,
        preferred_provider=req.provider,
        temperature=req.temperature or 0.7,
    )
    agent_logger.log_event(
        "LLM_CORE",
        f"Completed generation via {result['provider_used']} (Texture Score: {result['human_texture_score']}%).",
    )
    return result


class VoiceEvaluateRequest(BaseModel):
    question: str
    transcript: str
    duration_seconds: Optional[float] = 30.0
