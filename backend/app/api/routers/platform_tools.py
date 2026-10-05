"""PDF, compliance, cache, portal health, and web research tools."""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from backend.app.core.event_logger import agent_logger
from backend.app.modules.apply.company_cache import company_cache
from backend.app.modules.scrape.portal_health import portal_health_checker
from backend.app.modules.scrape.web_research import web_research_engine
from backend.app.tools.job_key import audit_keys, make_job_key
from backend.app.tools.robots_check import check_robots_dict
from backend.app.tools.verify_layout import verify_layout_dict
from backend.app.tools.verify_pdf import verify_pdf_dict

router = APIRouter()


class VerifyPDFRequest(BaseModel):
    pdf_path: str
    expected_pages: Optional[int] = None
    min_chars: int = 1
    contains: Optional[List[str]] = None


@router.post("/tools/verify_pdf")
@router.post("/api/tools/verify_pdf")
def verify_pdf_endpoint(req: VerifyPDFRequest):
    agent_logger.log_event("PDF_VERIFY", f"Verifying PDF: {req.pdf_path}")
    return verify_pdf_dict(req.pdf_path, req.expected_pages, req.min_chars, req.contains)


class VerifyLayoutRequest(BaseModel):
    pdf_path: str


@router.post("/tools/verify_layout")
@router.post("/api/tools/verify_layout")
def verify_layout_endpoint(req: VerifyLayoutRequest):
    agent_logger.log_event("LAYOUT_VERIFY", f"Checking layout: {req.pdf_path}")
    return verify_layout_dict(req.pdf_path)


class RobotsCheckRequest(BaseModel):
    url: str
    user_agent: str = "CareerAgentBot/1.0"


@router.post("/tools/robots_check")
@router.post("/api/tools/robots_check")
def robots_check_endpoint(req: RobotsCheckRequest):
    return check_robots_dict(req.url, req.user_agent)


class JobKeyRequest(BaseModel):
    company: str
    title: str
    url: Optional[str] = ""


@router.post("/tools/job_key")
@router.post("/api/tools/job_key")
def generate_job_key(req: JobKeyRequest):
    return {"key": make_job_key(req.company, req.title, req.url or ""), "company": req.company, "title": req.title}


class AuditJobKeysRequest(BaseModel):
    jobs: List[Dict[str, Any]]


@router.post("/tools/job_key/audit")
@router.post("/api/tools/job_key/audit")
def audit_job_keys(req: AuditJobKeysRequest):
    return audit_keys(req.jobs)


@router.get("/company_cache/list")
@router.get("/api/company_cache/list")
def list_company_cache():
    return {"entries": company_cache.list_cached(), "stats": company_cache.stats()}


class CompanyCacheGetRequest(BaseModel):
    company_name: str


@router.post("/company_cache/get")
@router.post("/api/company_cache/get")
def get_company_cache(req: CompanyCacheGetRequest):
    cached = company_cache.get(req.company_name)
    return {"found": True, "data": cached} if cached else {"found": False, "message": f"No cache entry for '{req.company_name}'"}


class CompanyCachePutRequest(BaseModel):
    company_name: str
    research_data: Dict[str, Any]


@router.post("/company_cache/put")
@router.post("/api/company_cache/put")
def put_company_cache(req: CompanyCachePutRequest):
    company_cache.put(req.company_name, req.research_data)
    return {"status": "cached", "company": req.company_name}


class CompanyCacheInvalidateRequest(BaseModel):
    company_name: str


@router.post("/company_cache/invalidate")
@router.post("/api/company_cache/invalidate")
def invalidate_company_cache(req: CompanyCacheInvalidateRequest):
    return {"removed": company_cache.invalidate(req.company_name), "company": req.company_name}


class PortalHealthRequest(BaseModel):
    portal_name: str
    results: List[Dict[str, Any]]


@router.post("/scrape/portal_health")
@router.post("/api/scrape/portal_health")
def check_portal_health(req: PortalHealthRequest):
    agent_logger.log_event("PORTAL_HEALTH", f"Health check for portal: {req.portal_name}")
    return portal_health_checker.check_results_quality(req.portal_name, req.results)


class FullHealthReportRequest(BaseModel):
    portal_results: Dict[str, List[Dict[str, Any]]]


@router.post("/scrape/portal_health/full_report")
@router.post("/api/scrape/portal_health/full_report")
def full_portal_health_report(req: FullHealthReportRequest):
    return portal_health_checker.full_health_report(req.portal_results)


class WebResearchFetchRequest(BaseModel):
    url: str
    context: Optional[str] = "job_posting"


@router.post("/scrape/web_research/fetch")
@router.post("/api/scrape/web_research/fetch")
def web_research_fetch(req: WebResearchFetchRequest):
    agent_logger.log_event("WEB_RESEARCH", f"Escalation fetch requested: {req.url}")
    return web_research_engine.fetch_with_escalation(req.url, req.context or "job_posting")


class CompanyResearchRequest(BaseModel):
    company_name: str
    company_url: Optional[str] = None


@router.post("/scrape/web_research/company")
@router.post("/api/scrape/web_research/company")
def web_research_company(req: CompanyResearchRequest):
    cached = company_cache.get(req.company_name)
    if cached:
        return {"source": "cache", "data": cached}
    result = web_research_engine.research_company(req.company_name, req.company_url)
    if result.get("sources"):
        company_cache.put(req.company_name, result)
    return {"source": "fresh", "data": result}
