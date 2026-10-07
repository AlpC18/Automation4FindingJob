"""The API: one router per domain, combined here."""

from fastapi import APIRouter

from backend.app.api.profile import fetch_candidate_profile  # noqa: F401  (imported from here by main)
from backend.app.api.routers.application import router as application_router
from backend.app.api.routers.auto_apply import router as auto_apply_router
from backend.app.api.routers.inbox import router as inbox_router
from backend.app.api.routers.intelligence import router as intelligence_router
from backend.app.api.routers.operations import router as operations_router
from backend.app.api.routers.orchestration import router as orchestration_router
from backend.app.api.routers.outcome import router as outcome_router
from backend.app.api.routers.profile_features import router as profile_features_router
from backend.app.api.routers.scrape import AnalyzeOnTheFlyRequest, analyze_job_on_the_fly, router as scrape_router  # noqa: F401
from backend.app.api.routers.setup import router as setup_router
from backend.app.api.routers.system import router as system_router

router = APIRouter()
for domain_router in (
    outcome_router, setup_router, scrape_router, inbox_router, profile_features_router,
    application_router, intelligence_router, operations_router, orchestration_router, auto_apply_router, system_router,
):
    router.include_router(domain_router)
