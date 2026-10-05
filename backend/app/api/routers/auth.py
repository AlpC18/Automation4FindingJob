"""Account registration and cookie-based session endpoints."""

import re
import secrets
import logging
from typing import Any, Dict, Optional
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from backend.app.core.auth_sessions import (
    allow_security_email_request, consume_security_token, create_account, delete_account_data,
    get_security_email_user, issue_security_token, issue_session_token,
    login_rate_limited, mark_email_verified, record_login_attempt, update_password,
    verify_account,
)
from backend.app.core.config import settings
from backend.app.core.security_email import is_configured as security_email_configured
from backend.app.core.security_email import send_security_email

router = APIRouter()
SESSION_COOKIE = "career_session"
logger = logging.getLogger(__name__)


class CredentialsRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=256)


class PasswordResetRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)


class PasswordResetConfirmRequest(BaseModel):
    token: str = Field(min_length=20, max_length=256)
    new_password: str = Field(min_length=12, max_length=256)


class AccountDeletionRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=256)


def _validate_email(email: str) -> str:
    normalized = email.strip().lower()
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", normalized):
        raise HTTPException(status_code=422, detail="Geçerli bir e-posta adresi girin.")
    return normalized


def _set_session(response: Response, user: Dict[str, Any]) -> str:
    csrf_token = secrets.token_urlsafe(32)
    token = issue_session_token(
        user["id"], user["email"], int(user.get("session_version", 0)), csrf_token
    )
    response.set_cookie(
        SESSION_COOKIE,
        token,
        httponly=True,
        secure=settings.ENVIRONMENT.lower() == "production",
        samesite="none" if settings.ENVIRONMENT.lower() == "production" else "lax",
        max_age=24 * 60 * 60,
        path="/",
    )
    response.headers["Cache-Control"] = "no-store"
    return csrf_token


def _delete_session(response: Response):
    production = settings.ENVIRONMENT.lower() == "production"
    response.delete_cookie(
        SESSION_COOKIE, path="/", secure=production, httponly=True,
        samesite="none" if production else "lax",
    )


def _verification_url(token: str) -> str:
    return f"{settings.BACKEND_PUBLIC_URL.rstrip('/')}{settings.API_V1_PREFIX}/auth/verify-email?token={quote(token)}"


@router.get("/auth/mode")
def get_auth_mode() -> Dict[str, bool]:
    return {"authentication_required": settings.MULTI_TENANT_ENABLED}


@router.post("/auth/register", status_code=status.HTTP_201_CREATED)
def register(credentials: CredentialsRequest, response: Response):
    if not settings.MULTI_TENANT_ENABLED:
        raise HTTPException(status_code=404, detail="Account registration is disabled.")
    if len(credentials.password) < 12:
        raise HTTPException(status_code=422, detail="Parola en az 12 karakter olmalı.")
    email = _validate_email(credentials.email)
    if security_email_configured():
        email_verified = False
    elif settings.ENVIRONMENT.lower() == "production":
        raise HTTPException(status_code=503, detail="Account verification email is not configured.")
    else:
        email_verified = True
    try:
        issue_session_token("configuration-check", email)
        user = create_account(email, credentials.password, email_verified=email_verified)
    except Exception as exc:
        if "unique" in str(exc).lower() or "duplicate" in str(exc).lower():
            raise HTTPException(status_code=409, detail="Bu e-posta adresi zaten kayıtlı.") from exc
        logger.error("Account registration failed")
        raise HTTPException(status_code=503, detail="Hesap oluşturulamadı. Lütfen daha sonra tekrar deneyin.") from exc
    if not email_verified:
        try:
            token = issue_security_token(user["id"], "email_verification", 3600)
            send_security_email(
                user["email"], "Career Agent e-posta doğrulaması",
                f"Hesabınızı doğrulamak için bu bağlantıyı açın (1 saat geçerlidir):\n\n{_verification_url(token)}\n",
            )
        except Exception as exc:
            raise HTTPException(status_code=503, detail="Doğrulama e-postası gönderilemedi; daha sonra tekrar deneyin.") from exc
        return {"user": user, "verification_required": True, "message": "Giriş yapmadan önce e-posta adresinizi doğrulayın."}
    csrf_token = _set_session(response, user)
    return {"user": user, "csrf_token": csrf_token}


@router.post("/auth/login")
def login(credentials: CredentialsRequest, response: Response, request: Request):
    if not settings.MULTI_TENANT_ENABLED:
        raise HTTPException(status_code=404, detail="Account sessions are disabled.")
    email = _validate_email(credentials.email)
    client_ip = request.client.host if request.client else "unknown"
    if login_rate_limited(email, client_ip):
        raise HTTPException(status_code=429, detail="Çok fazla başarısız giriş. 15 dakika sonra tekrar deneyin.", headers={"Retry-After": "900"})
    try:
        user = verify_account(email, credentials.password)
    except RuntimeError as exc:
        logger.error("Account sign-in service is unavailable")
        raise HTTPException(status_code=503, detail="Giriş hizmeti şu anda kullanılamıyor.") from exc
    record_login_attempt(email, client_ip, bool(user and user["email_verified"]))
    if not user:
        raise HTTPException(status_code=401, detail="E-posta veya parola hatalı.")
    if not user["email_verified"]:
        raise HTTPException(status_code=403, detail="Giriş yapmadan önce e-posta adresinizi doğrulayın.")
    csrf_token = _set_session(response, user)
    return {"user": user, "csrf_token": csrf_token}


@router.get("/auth/me")
def current_user(request: Request) -> Dict[str, Any]:
    user = getattr(request.state, "auth_user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Oturum gerekli.")
    return {"user": user, "csrf_token": user.get("csrf_token")}


@router.post("/auth/logout")
def logout(response: Response):
    _delete_session(response)
    return {"status": "signed_out"}


@router.post("/auth/resend-verification", status_code=status.HTTP_202_ACCEPTED)
def resend_verification(payload: PasswordResetRequest, http_request: Request):
    email = _validate_email(payload.email)
    client_ip = http_request.client.host if http_request.client else "unknown"
    allowed = allow_security_email_request(email, client_ip, "email_verification")
    user = get_security_email_user(email)
    if allowed and user and not user["email_verified"] and security_email_configured():
        token = issue_security_token(user["id"], "email_verification", 3600)
        if token:
            try:
                send_security_email(
                    user["email"], "Career Agent e-posta doğrulaması",
                    f"E-posta adresinizi doğrulamak için bağlantıyı açın (1 saat geçerlidir):\n\n{_verification_url(token)}\n",
                )
            except Exception:
                pass
    return {"message": "Adres uygunsa doğrulama talimatları gönderildi."}


@router.get("/auth/verify-email")
def verify_email(token: str):
    user_id = consume_security_token(token, "email_verification")
    if not user_id or not mark_email_verified(user_id):
        raise HTTPException(status_code=400, detail="Doğrulama bağlantısı geçersiz, süresi dolmuş veya daha önce kullanılmış.")
    return RedirectResponse(url=f"{settings.FRONTEND_PUBLIC_URL.rstrip('/')}/?verified=1", status_code=303)


@router.post("/auth/password-reset-request", status_code=status.HTTP_202_ACCEPTED)
def request_password_reset(payload: PasswordResetRequest, http_request: Request):
    email = _validate_email(payload.email)
    client_ip = http_request.client.host if http_request.client else "unknown"
    allowed = allow_security_email_request(email, client_ip, "password_reset")
    user = get_security_email_user(email)
    if allowed and user and user["email_verified"] and security_email_configured():
        token = issue_security_token(user["id"], "password_reset", 1800)
        if token:
            reset_url = f"{settings.FRONTEND_PUBLIC_URL.rstrip('/')}/reset-password?token={quote(token)}"
            try:
                send_security_email(
                    user["email"], "Career Agent parola sıfırlama",
                    f"Parolanızı sıfırlamak için bağlantıyı açın (30 dakika geçerlidir):\n\n{reset_url}\n\nBu talep size ait değilse e-postayı yok sayın.",
                )
            except Exception:
                pass
    return {"message": "Adres kayıtlıysa parola sıfırlama talimatları gönderildi."}


@router.post("/auth/password-reset")
def reset_password(request: PasswordResetConfirmRequest):
    user_id = consume_security_token(request.token, "password_reset")
    if not user_id or not update_password(user_id, request.new_password):
        raise HTTPException(status_code=400, detail="Sıfırlama bağlantısı geçersiz, süresi dolmuş veya daha önce kullanılmış.")
    return {"status": "password_updated", "message": "Parolanız güncellendi. Güvenlik için tekrar giriş yapın."}


@router.delete("/auth/account", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(request: AccountDeletionRequest, http_request: Request, response: Response):
    session_user = getattr(http_request.state, "auth_user", None)
    email = _validate_email(request.email)
    verified_user = verify_account(email, request.password)
    if not session_user or not verified_user or verified_user["id"] != session_user["id"]:
        raise HTTPException(status_code=403, detail="Hesabı silmek için geçerli e-posta ve parolayı onaylayın.")
    delete_account_data(session_user["id"])
    output = Response(status_code=status.HTTP_204_NO_CONTENT)
    _delete_session(output)
    return output
