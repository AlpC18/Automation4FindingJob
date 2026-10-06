"""
Autonomous Career Agent Engine - FastAPI Main Server
Connects all 7 core modules with CORS support for Next.js Web UI.
"""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from backend.app.core.config import production_config_issues, settings
from backend.app.core.database import init_auth_db, init_db, is_postgres_database
from backend.app.core.backup_manager import run_periodic_sqlite_backups
from backend.app.api.router import router as api_router, fetch_candidate_profile
from backend.app.api.routers.voice import router as voice_router
from backend.app.api.routers.interview import router as interview_router
from backend.app.api.routers.integrations import router as integrations_router
from backend.app.api.routers.portfolio import router as portfolio_router
from backend.app.api.routers.daemon import router as daemon_router
from backend.app.api.routers.search import router as search_router
from backend.app.api.routers.tracking import router as tracking_router
from backend.app.api.routers.auth import router as auth_router
from backend.app.api.routers.trust import router as trust_router
from backend.app.modules.scrape.unified_scraper import unified_scraper
from backend.app.modules.rank.scoring_engine import rank_and_save_all_jobs
from backend.app.tasks.scheduler_daemon import scheduler_daemon
from backend.app.core.llm_client import LLMUnavailable
from backend.app.core.security import APIKeyMiddleware
from backend.app.core.monitoring import RequestMetricsMiddleware, initialize_error_monitoring

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

initialize_error_monitoring()

def _seed_initial_data():
    """Optional first-run seed; external portal scraping is never implicit."""
    try:
        scrape_res = unified_scraper.run_multi_platform_scrape(query=settings.DEFAULT_SCRAPE_QUERY)
        profile = fetch_candidate_profile()
        rank_and_save_all_jobs(profile)
        print(f"[*] Engine initialized: Scraped {scrape_res['total_scraped']} jobs and computed ATS scores.")
    except Exception as exc:
        print(f"[!] Startup seed exception: {exc}")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    config_issues = production_config_issues()
    if config_issues:
        raise RuntimeError("Production yapılandırması geçersiz: " + " ".join(config_issues))
    init_db()
    init_auth_db()
    if settings.STARTUP_SEED_ENABLED:
        seed_task = asyncio.create_task(asyncio.to_thread(_seed_initial_data))
    else:
        seed_task = None
        print("[*] Startup scrape disabled. Use /api/scrape/run when a scan is requested.")
    if settings.AUTO_START_DAEMON:
        await scheduler_daemon.start_daemon()
        print("[*] Autonomous scheduler daemon started.")
    reminder_task = asyncio.create_task(scheduler_daemon.run_follow_up_reminder_loop())
    backup_task = None if is_postgres_database() else asyncio.create_task(run_periodic_sqlite_backups())
    try:
        yield
    finally:
        if backup_task:
            backup_task.cancel()
            try:
                await backup_task
            except asyncio.CancelledError:
                pass
        reminder_task.cancel()
        try:
            await reminder_task
        except asyncio.CancelledError:
            pass
        if seed_task and not seed_task.done():
            seed_task.cancel()
        if settings.AUTO_START_DAEMON:
            await scheduler_daemon.stop_daemon()


# Keep imports and lightweight TestClient usage safe on a fresh checkout.
init_db()
init_auth_db()

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Full-stack Autonomous Career Agent Engine with Anti-AI Humanizer, Multi-Agent RAG, and Decision Maker Sourcing.",
    lifespan=lifespan,
)

# Enable CORS for Next.js frontend
@app.exception_handler(LLMUnavailable)
async def llm_unavailable_handler(request: Request, exc: LLMUnavailable) -> JSONResponse:
    return JSONResponse(status_code=503, content={"detail": str(exc)})


app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.CORS_ORIGINS.split(",") if origin.strip()],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-API-Key", "Authorization", "X-CSRF-Token"],
)
app.add_middleware(APIKeyMiddleware)
app.add_middleware(RequestMetricsMiddleware)

# Mount API routes
app.include_router(api_router, prefix=settings.API_V1_PREFIX)
app.include_router(auth_router, prefix=settings.API_V1_PREFIX)
app.include_router(voice_router, prefix=settings.API_V1_PREFIX)
app.include_router(interview_router, prefix=settings.API_V1_PREFIX)
app.include_router(integrations_router, prefix=settings.API_V1_PREFIX)
app.include_router(portfolio_router, prefix=settings.API_V1_PREFIX)
app.include_router(daemon_router, prefix=settings.API_V1_PREFIX)
app.include_router(search_router, prefix=settings.API_V1_PREFIX)
app.include_router(tracking_router, prefix=settings.API_V1_PREFIX)
app.include_router(trust_router, prefix=settings.API_V1_PREFIX)

@app.get("/")
def health_check():
    return {
        "status": "ONLINE",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "runtime_config": settings.public_runtime_config(),
        "docs_url": "/docs"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.app.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        log_level=settings.LOG_LEVEL.lower(),
        reload=settings.ENVIRONMENT == "development",
    )
