"""Semantic job search and market trend API."""

from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from backend.app.modules.rank.semantic_search import semantic_search_engine

router = APIRouter()


@router.post("/rank/semantic/index")
def index_jobs_for_vector_search():
    return semantic_search_engine.index_all_seen_jobs()


class SemanticSearchQuery(BaseModel):
    query: str
    limit: Optional[int] = 10


@router.post("/rank/semantic/search")
def search_jobs_semantically(req: SemanticSearchQuery):
    return {"results": semantic_search_engine.semantic_search(req.query, req.limit or 10)}


class SimilarJobsQuery(BaseModel):
    job_key: str
    limit: Optional[int] = 5


@router.post("/rank/semantic/similar")
def find_similar_jobs(req: SimilarJobsQuery):
    return {"results": semantic_search_engine.find_similar_jobs(req.job_key, req.limit or 5)}


@router.get("/rank/semantic/trends")
def get_market_skill_trends():
    return semantic_search_engine.analyze_market_skill_trends()
