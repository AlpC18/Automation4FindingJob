"""Interview simulation and compensation negotiation API."""

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.app.core.database import get_db_connection
from backend.app.modules.interview.interview_simulator import interview_simulator
from backend.app.modules.interview.offer_negotiator import offer_negotiator_engine

router = APIRouter()


class InterviewStartRequest(BaseModel):
    job_id: str


@router.post("/interview/start")
def start_interview_simulation(req: InterviewStartRequest):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM scraped_jobs WHERE id = ?", (req.job_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Job not found")
    job = dict(row)
    questions = interview_simulator.generate_interview_session(
        job["title"], job["company"], job["description"]
    )
    return {"job": job, "questions": questions}


class InterviewEvaluateRequest(BaseModel):
    question: str
    answer: str


@router.post("/interview/evaluate")
def evaluate_interview_response(req: InterviewEvaluateRequest):
    return interview_simulator.evaluate_candidate_answer(req.question, req.answer)


class CounterOfferRequest(BaseModel):
    company_name: str
    role_title: str
    initial_offer: str
    market_benchmark: str
    target_amount: str
    special_requests: Optional[str] = "Flexible remote schedule and annual learning budget"


@router.post("/interview/counter_offer")
def generate_counter_offer(req: CounterOfferRequest):
    """Backward-compatible adapter for the original counter-offer contract."""
    try:
        initial_offer = float(req.initial_offer.replace(",", "").replace("$", "").strip())
        target_amount = float(req.target_amount.replace(",", "").replace("$", "").strip())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Teklif tutarları sayısal olmalı.") from exc

    return {
        "company": req.company_name,
        "title": req.role_title,
        "initial_offer": req.initial_offer,
        "market_benchmark": req.market_benchmark,
        "target_amount": req.target_amount,
        "special_requests": req.special_requests,
        "recommendation": offer_negotiator_engine.evaluate_offer(
            company=req.company_name,
            title=req.role_title,
            base_salary=initial_offer,
        ),
        "counter_letter": {
            "status": "use_counter_letter_endpoint",
            "target_base": target_amount,
            "message": "Detaylı mektup için /api/interview/offer/counter_letter endpoint'ini kullanın.",
        },
    }


class EvaluateOfferRequest(BaseModel):
    company: str
    title: str
    base_salary: float
    currency: Optional[str] = "USD"
    annual_bonus_pct: Optional[float] = 0.0
    equity_annual_value: Optional[float] = 0.0
    signing_bonus: Optional[float] = 0.0
    is_remote: Optional[bool] = True


@router.post("/interview/offer/evaluate")
def evaluate_job_offer(req: EvaluateOfferRequest):
    return offer_negotiator_engine.evaluate_offer(
        company=req.company,
        title=req.title,
        base_salary=req.base_salary,
        currency=req.currency or "USD",
        annual_bonus_pct=req.annual_bonus_pct or 0.0,
        equity_annual_value=req.equity_annual_value or 0.0,
        signing_bonus=req.signing_bonus or 0.0,
        is_remote=req.is_remote if req.is_remote is not None else True,
    )


class CounterLetterRequest(BaseModel):
    company: str
    title: str
    offered_base: float
    target_base: float
    currency: Optional[str] = "USD"
    primary_leverage: Optional[str] = "skill_alignment"
    competing_offer_details: Optional[str] = None


@router.post("/interview/offer/counter_letter")
async def generate_counter_offer_letter(req: CounterLetterRequest):
    return await offer_negotiator_engine.generate_counter_offer_letter(
        company=req.company,
        title=req.title,
        offered_base=req.offered_base,
        target_base=req.target_base,
        currency=req.currency or "USD",
        primary_leverage=req.primary_leverage or "skill_alignment",
        competing_offer_details=req.competing_offer_details,
    )


@router.get("/interview/offer/objection_playbook")
def get_negotiation_objection_playbook(objection_type: str = "no_budget"):
    return offer_negotiator_engine.simulate_objection(objection_type)
