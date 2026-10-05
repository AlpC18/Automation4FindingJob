"""Personal portfolio generation API."""

from typing import Optional

from fastapi import APIRouter
from fastapi.responses import FileResponse
from pydantic import BaseModel

from backend.app.api.profile import fetch_candidate_profile
from backend.app.modules.setup.portfolio_generator import portfolio_generator
from backend.app.modules.setup.rag_engine import rag_memory

router = APIRouter()


class PortfolioGenerateRequest(BaseModel):
    custom_headline: Optional[str] = None


@router.post("/setup/portfolio/generate")
def generate_personal_portfolio(req: Optional[PortfolioGenerateRequest] = None):
    profile = fetch_candidate_profile()
    profile["projects"] = rag_memory.documents
    return portfolio_generator.generate_html_portfolio(
        profile,
        custom_headline=req.custom_headline if req else None,
    )


@router.post("/setup/portfolio/package")
def package_personal_portfolio(req: Optional[PortfolioGenerateRequest] = None):
    profile = fetch_candidate_profile()
    profile["projects"] = rag_memory.documents
    result = portfolio_generator.generate_static_package(
        profile,
        custom_headline=req.custom_headline if req else None,
    )
    return FileResponse(
        result["archive_path"],
        media_type="application/zip",
        filename="portfolio-site.zip",
    )
