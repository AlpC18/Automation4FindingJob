"""Behavioral, writing-style, career discovery, and STAR interview APIs."""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from backend.app.api.profile import fetch_candidate_profile
from backend.app.modules.interview.star_framework import star_framework
from backend.app.modules.setup.behavioral_profile import behavioral_profiler
from backend.app.modules.setup.career_discovery import career_discovery_engine
from backend.app.modules.setup.writing_style import writing_style_guide

router = APIRouter()


@router.get("/setup/behavioral/questions")
@router.get("/api/setup/behavioral/questions")
def get_behavioral_questions():
    return behavioral_profiler.get_assessment_questions()


class BehavioralAnswersRequest(BaseModel):
    answers: Dict[str, str]


@router.post("/setup/behavioral/build")
@router.post("/api/setup/behavioral/build")
def build_behavioral_profile(req: BehavioralAnswersRequest):
    return behavioral_profiler.build_profile(req.answers)


class CulturalFitRequest(BaseModel):
    behavioral_profile: Dict[str, Any]
    job_data: Dict[str, Any]


@router.post("/setup/behavioral/cultural_fit")
@router.post("/api/setup/behavioral/cultural_fit")
def check_cultural_fit(req: CulturalFitRequest):
    return behavioral_profiler.calculate_cultural_fit(req.behavioral_profile, req.job_data)


@router.get("/setup/writing_style/presets")
@router.get("/api/setup/writing_style/presets")
def get_writing_style_presets():
    return writing_style_guide.get_tone_presets()


class BuildStyleGuideRequest(BaseModel):
    tone: Optional[str] = "professional_conversational"
    custom_dos: Optional[List[str]] = None
    custom_donts: Optional[List[str]] = None
    preferred_phrases: Optional[List[str]] = None
    avoided_phrases: Optional[List[str]] = None


@router.post("/setup/writing_style/build")
@router.post("/api/setup/writing_style/build")
def build_writing_style(req: BuildStyleGuideRequest):
    return writing_style_guide.build_style_guide(
        tone=req.tone or "professional_conversational",
        custom_dos=req.custom_dos,
        custom_donts=req.custom_donts,
        preferred_phrases=req.preferred_phrases,
        avoided_phrases=req.avoided_phrases,
    )


class StyleComplianceRequest(BaseModel):
    text: str
    style_guide: Dict[str, Any]


@router.post("/setup/writing_style/check")
@router.post("/api/setup/writing_style/check")
def check_style_compliance(req: StyleComplianceRequest):
    return writing_style_guide.check_compliance(req.text, req.style_guide)


@router.post("/setup/writing_style/auto_fix")
@router.post("/api/setup/writing_style/auto_fix")
def auto_fix_style(req: StyleComplianceRequest):
    fixed = writing_style_guide.auto_fix(req.text, req.style_guide)
    return {"fixed_text": fixed, "compliance": writing_style_guide.check_compliance(fixed, req.style_guide)}


@router.post("/setup/career_discovery")
@router.post("/api/setup/career_discovery")
def discover_career_paths():
    return career_discovery_engine.discover_latent_opportunities(fetch_candidate_profile())


class CareerPivotRequest(BaseModel):
    target_pivot: str


@router.post("/setup/career_discovery/roadmap")
@router.post("/api/setup/career_discovery/roadmap")
async def generate_career_roadmap(req: CareerPivotRequest):
    return await career_discovery_engine.generate_ai_career_roadmaps(fetch_candidate_profile(), req.target_pivot)


@router.get("/interview/star/categories")
@router.get("/api/interview/star/categories")
def get_star_categories():
    return star_framework.get_question_categories()


class STARQuestionsRequest(BaseModel):
    job_title: str
    job_description: str


@router.post("/interview/star/questions")
@router.post("/api/interview/star/questions")
def get_star_questions(req: STARQuestionsRequest):
    questions = star_framework.generate_role_questions(req.job_title, req.job_description)
    return {"questions": questions, "count": len(questions)}


@router.post("/interview/star/extract")
@router.post("/api/interview/star/extract")
def extract_star_candidates():
    stubs = star_framework.extract_star_candidates(fetch_candidate_profile())
    return {"stubs": stubs, "count": len(stubs)}


class STARAnswerRequest(BaseModel):
    situation: str
    task: str
    action: str
    result: str


@router.post("/interview/star/score")
@router.post("/api/interview/star/score")
def score_star_answer(req: STARAnswerRequest):
    return star_framework.score_star_answer(req.model_dump())
