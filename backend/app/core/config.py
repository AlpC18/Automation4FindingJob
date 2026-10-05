import os
from pathlib import Path
from typing import Any, Dict, List
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True, parents=True)


def _env_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _csv(value: str) -> List[str]:
    return [item.strip() for item in value.split(",") if item.strip()]

class Settings(BaseSettings):
    PROJECT_NAME: str = "Autonomous Career Agent Engine"
    VERSION: str = "1.0.0"
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    API_V1_PREFIX: str = "/api"
    API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
    API_PORT: int = _env_int("API_PORT", 8000)
    BACKEND_PUBLIC_URL: str = os.getenv("BACKEND_PUBLIC_URL", f"http://localhost:{_env_int('API_PORT', 8000)}")
    FRONTEND_PUBLIC_URL: str = os.getenv("FRONTEND_PUBLIC_URL", "http://localhost:3000")
    PUBLIC_API_URL: str = os.getenv("PUBLIC_API_URL", "http://localhost:8000/api")

    # Security: leave API_AUTH_TOKEN empty only for trusted local development.
    API_AUTH_TOKEN: str = os.getenv("API_AUTH_TOKEN", "")
    AUTH_SECRET_KEY: str = os.getenv("AUTH_SECRET_KEY", "")
    MULTI_TENANT_ENABLED: bool = _env_bool(
        "MULTI_TENANT_ENABLED", os.getenv("ENVIRONMENT", "development").lower() == "production"
    )
    APP_ENCRYPTION_KEY: str = os.getenv("APP_ENCRYPTION_KEY", "")
    CLAMAV_HOST: str = os.getenv("CLAMAV_HOST", "")
    CLAMAV_PORT: int = _env_int("CLAMAV_PORT", 3310)
    CLAMAV_TIMEOUT_SECONDS: int = _env_int("CLAMAV_TIMEOUT_SECONDS", 20)
    SENTRY_DSN: str = os.getenv("SENTRY_DSN", "")
    SENTRY_TRACES_SAMPLE_RATE: float = _env_float("SENTRY_TRACES_SAMPLE_RATE", 0.05)
    CORS_ORIGINS: str = os.getenv(
        "CORS_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000",
    )
    STARTUP_SEED_ENABLED: bool = _env_bool("STARTUP_SEED_ENABLED", False)
    AUTO_START_DAEMON: bool = _env_bool("AUTO_START_DAEMON", False)
    # Demo fixtures are opt-in; ordinary development reads persisted application data.
    DEMO_DATA_ENABLED: bool = _env_bool("DEMO_DATA_ENABLED", False)
    
    # Storage & DB
    DATA_PATH: Path = DATA_DIR
    BACKUP_DIR: Path | None = Path(os.getenv("BACKUP_DIR")) if os.getenv("BACKUP_DIR") else None
    BACKUP_INTERVAL_SECONDS: int = _env_int("BACKUP_INTERVAL_SECONDS", 86400)
    BACKUP_RETENTION_DAYS: int = _env_int("BACKUP_RETENTION_DAYS", 14)
    BACKUP_MAX_SIZE_MB: int = _env_int("BACKUP_MAX_SIZE_MB", 512)
    DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite:///{DATA_DIR}/career_engine.db")
    CHROMA_PERSIST_DIR: str = str(DATA_DIR / "chroma_db")
    VECTOR_BACKEND: str = os.getenv("VECTOR_BACKEND", "auto")
    VECTOR_DIMENSIONS: int = _env_int("VECTOR_DIMENSIONS", 384)
    
    # LLM & AI Keys (Optional, fallback to smart rule-based engine if empty)
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o")
    VOICE_STT_MODEL: str = os.getenv("VOICE_STT_MODEL", "whisper-1")
    VOICE_TTS_MODEL: str = os.getenv("VOICE_TTS_MODEL", "tts-1")
    VOICE_TTS_VOICE: str = os.getenv("VOICE_TTS_VOICE", "alloy")
    VOICE_TTS_PROVIDER: str = os.getenv("VOICE_TTS_PROVIDER", "openai")
    VOICE_EDGE_TTS_VOICE: str = os.getenv("VOICE_EDGE_TTS_VOICE", "en-US-AriaNeural")
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    ANTHROPIC_MODEL: str = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5-5")
    # Daily cap on Anthropic tokens (input + output); past it the template engine answers. 0 disables the cap.
    LLM_DAILY_TOKEN_BUDGET: int = _env_int("LLM_DAILY_TOKEN_BUDGET", 200000)
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
    DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")
    DEEPSEEK_MODEL: str = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama3")
    ACTIVE_LLM_PROVIDER: str = os.getenv("ACTIVE_LLM_PROVIDER", "auto")
    
    # Platform / Sourcing APIs
    APIFY_API_TOKEN: str = os.getenv("APIFY_API_TOKEN", "")
    APIFY_ACTOR_LINKEDIN: str = os.getenv("APIFY_ACTOR_LINKEDIN", "valig/linkedin-jobs-scraper")
    APIFY_ACTOR_UPWORK: str = os.getenv("APIFY_ACTOR_UPWORK", "")
    APIFY_ACTOR_KOSOVAJOB: str = os.getenv("APIFY_ACTOR_KOSOVAJOB", "")
    APIFY_INPUT_LINKEDIN: str = os.getenv("APIFY_INPUT_LINKEDIN", '{"keywords":"","location":"","limit":100}')
    APIFY_INPUT_UPWORK: str = os.getenv("APIFY_INPUT_UPWORK", "{}")
    APIFY_INPUT_KOSOVAJOB: str = os.getenv("APIFY_INPUT_KOSOVAJOB", "{}")
    APIFY_TIMEOUT_SECONDS: int = _env_int("APIFY_TIMEOUT_SECONDS", 90)
    # Bounds the size returned to the app for each billable Actor invocation.
    APIFY_MAX_ITEMS_PER_RUN: int = _env_int("APIFY_MAX_ITEMS_PER_RUN", 100)
    APIFY_MAX_ACTOR_RUNS_PER_DAY: int = _env_int("APIFY_MAX_ACTOR_RUNS_PER_DAY", 20)
    APIFY_MAX_TOTAL_CHARGE_USD: float = _env_float("APIFY_MAX_TOTAL_CHARGE_USD", 1.0)
    JOB_SOURCE_TIMEOUT_SECONDS: int = _env_int("JOB_SOURCE_TIMEOUT_SECONDS", 20)
    JOB_SOURCE_USER_AGENT: str = os.getenv("JOB_SOURCE_USER_AGENT", "AutonomousCareerAgent/1.0 (job aggregator)")
    REMOTEOK_API_URL: str = os.getenv("REMOTEOK_API_URL", "https://remoteok.com/api")
    ARBEITNOW_API_URL: str = os.getenv("ARBEITNOW_API_URL", "https://www.arbeitnow.com/api/job-board-api")
    # Company career boards to scan, e.g. "greenhouse:stripe,lever:spotify,ashby:ramp".
    COMPANY_BOARDS: str = os.getenv("COMPANY_BOARDS", "")
    APOLLO_API_KEY: str = os.getenv("APOLLO_API_KEY", "")
    
    # Proxy & Scraping
    RESIDENTIAL_PROXY_URL: str = os.getenv("RESIDENTIAL_PROXY_URL", "")
    STEALTH_BROWSER_HEADLESS: bool = _env_bool("STEALTH_BROWSER_HEADLESS", True)

    # Dynamic sourcing and scheduler controls
    SCRAPER_MODE: str = os.getenv("SCRAPER_MODE", "auto")
    SCRAPER_PLATFORMS: str = os.getenv("SCRAPER_PLATFORMS", "linkedin,upwork,kosovajob,techcareer,remote")
    DEFAULT_SCRAPE_QUERY: str = os.getenv("DEFAULT_SCRAPE_QUERY", "Developer")
    SCHEDULER_TIMEZONE: str = os.getenv("SCHEDULER_TIMEZONE", "Europe/Belgrade")
    SCHEDULER_NIGHTLY_TIME: str = os.getenv("SCHEDULER_NIGHTLY_TIME", "03:30")
    SCHEDULER_MORNING_TIME: str = os.getenv("SCHEDULER_MORNING_TIME", "08:00")
    DAEMON_POLL_SECONDS: int = _env_int("DAEMON_POLL_SECONDS", 45)
    MORNING_MIN_MATCH_SCORE: int = _env_int("MORNING_MIN_MATCH_SCORE", 75)
    MORNING_DRAFT_LIMIT: int = _env_int("MORNING_DRAFT_LIMIT", 3)
    
    # Account Safety & Daily Rate Limits
    DAILY_LIMIT_LINKEDIN: int = 25
    DAILY_LIMIT_UPWORK: int = 20
    DAILY_LIMIT_KOSOVAJOB: int = 35
    DAILY_LIMIT_GLOBAL_REMOTE: int = 30
    
    # Telegram Bot & Mobile Dispatch
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")

    # Inbox & Email Listener
    IMAP_HOST: str = os.getenv("IMAP_HOST", "")
    IMAP_USER: str = os.getenv("IMAP_USER", "")
    IMAP_PASSWORD: str = os.getenv("IMAP_PASSWORD", "")
    SMTP_HOST: str = os.getenv("SMTP_HOST", "")
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASS: str = os.getenv("SMTP_PASS", "")
    SMTP_PORT: int = _env_int("SMTP_PORT", 587)
    SMTP_FROM_EMAIL: str = os.getenv("SMTP_FROM_EMAIL", "")
    SMTP_USE_TLS: bool = _env_bool("SMTP_USE_TLS", True)
    
    # Official OAuth2 Integration (Google & Microsoft)
    GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET: str = os.getenv("GOOGLE_CLIENT_SECRET", "")
    GOOGLE_REDIRECT_URI: str = os.getenv("GOOGLE_REDIRECT_URI", f"{BACKEND_PUBLIC_URL}/api/inbox/oauth/google/callback")
    MICROSOFT_CLIENT_ID: str = os.getenv("MICROSOFT_CLIENT_ID", "")
    MICROSOFT_CLIENT_SECRET: str = os.getenv("MICROSOFT_CLIENT_SECRET", "")
    MICROSOFT_REDIRECT_URI: str = os.getenv("MICROSOFT_REDIRECT_URI", f"{BACKEND_PUBLIC_URL}/api/inbox/oauth/microsoft/callback")

    # Distributed Task Queue (Celery + Redis)
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    USE_CELERY: bool = _env_bool("USE_CELERY", False)

    # Ghost Job & Red Flag Thresholds
    GHOST_JOB_DAYS_THRESHOLD: int = _env_int("GHOST_JOB_DAYS_THRESHOLD", 45)
    MIN_ATS_MATCH_SCORE: int = _env_int("MIN_ATS_MATCH_SCORE", 70)

    # Company Research Cache
    COMPANY_CACHE_TTL_DAYS: int = _env_int("COMPANY_CACHE_TTL_DAYS", 7)

    # Notion Integration
    NOTION_API_KEY: str = os.getenv("NOTION_API_KEY", "")
    NOTION_DATABASE_ID: str = os.getenv("NOTION_DATABASE_ID", "")

    # Portal Health Check
    PORTAL_HEALTH_MIN_SCORE: int = 50  # below this, portal is flagged as degraded

    @property
    def scraper_platforms(self) -> List[str]:
        return _csv(self.SCRAPER_PLATFORMS)

    def public_runtime_config(self) -> Dict[str, Any]:
        """Return browser-safe configuration without exposing credentials."""
        return {
            "environment": self.ENVIRONMENT,
            "project": {"name": self.PROJECT_NAME, "version": self.VERSION},
            "api": {"prefix": self.API_V1_PREFIX, "public_url": self.PUBLIC_API_URL},
            "frontend": {"public_url": self.FRONTEND_PUBLIC_URL},
            "features": {
                "demo_data": self.DEMO_DATA_ENABLED,
                "startup_seed": self.STARTUP_SEED_ENABLED,
                "daemon": self.AUTO_START_DAEMON,
                "celery": self.USE_CELERY,
                "multi_tenant": self.MULTI_TENANT_ENABLED,
            },
            "providers": {
                "llm": self.ACTIVE_LLM_PROVIDER,
                "tts": self.VOICE_TTS_PROVIDER,
                "vector": self.VECTOR_BACKEND,
            },
            "scraping": {
                "mode": self.SCRAPER_MODE,
                "platforms": self.scraper_platforms,
                "default_query": self.DEFAULT_SCRAPE_QUERY,
            },
            "scheduler": {
                "timezone": self.SCHEDULER_TIMEZONE,
                "nightly_time": self.SCHEDULER_NIGHTLY_TIME,
                "morning_time": self.SCHEDULER_MORNING_TIME,
                "morning_draft_limit": self.MORNING_DRAFT_LIMIT,
            },
        }

    model_config = SettingsConfigDict(env_file=".env", extra="allow")


def production_config_issues() -> list[str]:
    """Return actionable fail-fast configuration errors for production boots."""
    if settings.ENVIRONMENT.lower() != "production":
        return []
    issues: list[str] = []
    if len(settings.API_AUTH_TOKEN.strip()) < 32:
        issues.append("API_AUTH_TOKEN en az 32 karakter olmalı.")
    if len(settings.AUTH_SECRET_KEY.strip()) < 32:
        issues.append("AUTH_SECRET_KEY en az 32 karakter olmalı.")
    if not settings.MULTI_TENANT_ENABLED:
        issues.append("MULTI_TENANT_ENABLED=true olmalı.")
    if settings.DEMO_DATA_ENABLED:
        issues.append("DEMO_DATA_ENABLED=false olmalı.")
    if not settings.APP_ENCRYPTION_KEY.strip():
        issues.append("APP_ENCRYPTION_KEY tanımlanmalı.")
    else:
        try:
            from cryptography.fernet import Fernet
            Fernet(settings.APP_ENCRYPTION_KEY.encode())
        except Exception:
            issues.append("APP_ENCRYPTION_KEY geçerli bir Fernet anahtarı olmalı.")
    if not settings.CLAMAV_HOST.strip():
        issues.append("CLAMAV_HOST tanımlanmalı; dosyalar antivirüs taramasından geçmeli.")
    if "*" in {origin.strip() for origin in settings.CORS_ORIGINS.split(",") if origin.strip()}:
        issues.append("CORS_ORIGINS üretimde '*' olamaz.")
    return issues

settings = Settings()
