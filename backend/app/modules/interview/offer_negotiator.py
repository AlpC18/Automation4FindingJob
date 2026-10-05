"""
Offer Negotiation & Compensation Coach Engine
Empowers candidates during the highest-stakes phase of the job search:
- Total Compensation (TC) evaluation (Base, Equity/RSU, Bonus, Benefits)
- Counter-Offer letter generator with strategic leverage hooks
- Live Objection Handling Simulator ("No budget", "Internal equity constraints")
- Multi-offer side-by-side trade-off matrix
"""

from typing import Dict, Any, List, Optional
from backend.app.core.llm_client import llm_client
from backend.app.core.event_logger import agent_logger
from backend.app.modules.rank.salary_lookup import salary_lookup


class OfferNegotiatorEngine:
    """Calculates compensation value and crafts high-leverage counter-offers."""

    def evaluate_offer(
        self,
        company: str,
        title: str,
        base_salary: float,
        currency: str = "USD",
        annual_bonus_pct: float = 0.0,
        equity_annual_value: float = 0.0,
        signing_bonus: float = 0.0,
        is_remote: bool = True
    ) -> Dict[str, Any]:
        """Calculates Total Compensation (TC) and compares against benchmark data."""
        bonus_val = base_salary * (annual_bonus_pct / 100.0)
        total_comp_first_year = base_salary + bonus_val + equity_annual_value + signing_bonus
        ongoing_annual_tc = base_salary + bonus_val + equity_annual_value

        # Lookup benchmark
        benchmarks = salary_lookup.search(company)
        market_median = None
        market_max = None
        if benchmarks:
            market_median = benchmarks[0].get("salary_median")
            market_max = benchmarks[0].get("salary_max")

        comparison_verdict = "Piyasa standardında"
        leverage_score = 70

        if market_median:
            if base_salary < market_median:
                comparison_verdict = f"Piyasa medyanının ({currency} {market_median:,.0f}) altında — Güçlü pazarlık payı var!"
                leverage_score = 85
            elif base_salary >= market_median and (market_max and base_salary < market_max):
                comparison_verdict = "Piyasa medyanı ile üst sınır arasında — Kabul edilebilir veya ufak revizyon istenebilir."
                leverage_score = 65
            else:
                comparison_verdict = "Piyasa tavanında çok rekabetçi bir teklif."
                leverage_score = 50

        return {
            "company": company,
            "title": title,
            "currency": currency,
            "base_salary": base_salary,
            "first_year_tc": total_comp_first_year,
            "ongoing_annual_tc": ongoing_annual_tc,
            "market_median": market_median,
            "market_max": market_max,
            "comparison_verdict": comparison_verdict,
            "negotiation_leverage_score": leverage_score,
            "recommended_counter_target": round(base_salary * 1.12, -2) # Standard 12% target
        }

    async def generate_counter_offer_letter(
        self,
        company: str,
        title: str,
        offered_base: float,
        target_base: float,
        currency: str = "USD",
        primary_leverage: str = "skill_alignment",  # 'competing_offer', 'skill_alignment', 'market_data'
        competing_offer_details: Optional[str] = None
    ) -> Dict[str, Any]:
        """Drafts a gracious, high-leverage counter-offer letter."""
        leverage_prompts = {
            "competing_offer": f"Candidate holds a parallel competing offer offering around {currency} {target_base:,.0f}.",
            "skill_alignment": "Candidate brings rare, direct-fit experience in autonomous agent systems and distributed architecture.",
            "market_data": f"Industry benchmark data for {title} in this market reflects a median compensation of {currency} {target_base:,.0f}."
        }

        context = leverage_prompts.get(primary_leverage, leverage_prompts["skill_alignment"])
        if competing_offer_details:
            context += f" Specific note: {competing_offer_details}"

        prompt = f"""
Company: {company}
Role: {title}
Offered Base: {currency} {offered_base:,.0f}
Requested Counter Target: {currency} {target_base:,.0f}
Strategic Leverage: {context}

Write a professional, collaborative counter-offer letter in JSON with keys:
1. "email_subject": Professional email subject line.
2. "counter_letter_body": 3-paragraph letter:
   - Paragraph 1: Enthusiastic appreciation of the offer and confirmation that {company} is the top choice.
   - Paragraph 2: Direct, polite counter-proposal referencing the leverage point without sounding adversarial or entitled.
   - Paragraph 3: Clear commitment that if they can meet this target, candidate will sign immediately.
3. "alternative_negotiation_points": 3 non-salary items to ask for if salary is strictly non-negotiable (e.g., signing bonus, earlier 6-month performance review, remote stipend, additional PTO).
"""
        res = await llm_client.generate_json(
            system_prompt="You are a Master Executive Compensation Negotiator who has helped hundreds of tech leaders negotiate 15-30% salary increases.",
            user_prompt=prompt
        )

        agent_logger.log_event("OFFER_NEGOTIATOR", f"Generated counter offer letter for {company}")
        return res if res else {
            "email_subject": f"Offer Discussion – {title}",
            "counter_letter_body": (
                f"Thank you so much for extending the offer for the {title} position. "
                f"I am genuinely thrilled about the opportunity to join {company}.\n\n"
                f"Based on the scope of the role and my hands-on background in scalable AI systems, "
                f"I would like to explore if we can bridge the base salary to {currency} {target_base:,.0f}. "
                f"With this adjustment, I am ready to sign and fully commit to the team immediately.\n\n"
                f"Looking forward to finalizing our partnership!"
            ),
            "alternative_negotiation_points": [
                f"{currency} 10,000 tek seferlik İmza Bonusu (Signing Bonus)",
                "6. ayda erken maaş ve performans değerlendirmesi taahhüdü",
                "Yıllık 3,000 USD teknoloji & konferans gelişim bütçesi"
            ]
        }

    def simulate_objection(self, objection_type: str) -> Dict[str, Any]:
        """Provides instant verbal and written responses to common recruiter pushback."""
        playbook = {
            "no_budget": {
                "recruiter_objection": "Bütçemiz kesinlikle maksimum bu seviyede, üzerine çıkmamız mümkün değil.",
                "candidate_response": "Tamamen anlıyorum ve bütçe sınırlarına saygı duyuyorum. Eğer baz maaşta esneklik yoksa, ilk yıl için tek seferlik bir imza primi (signing bonus) veya 6. ayda net hedeflere bağlı bir ara değerlendirme yapmamız mümkün olur mu?",
                "alternative_ask": "İmza primi veya erken performans zammı."
            },
            "internal_equity": {
                "recruiter_objection": "Mevcut ekip içi adalet (internal equity) ve unvan baremleri nedeniyle bu rakamı veremiyoruz.",
                "candidate_response": "Şirket içi ücret dengesini korumanızı takdir ediyorum. Bu barem içinde kalıp unvan seviyesini (örn: Senior -> Staff / Lead) veya hisse opsiyonu / RSU oranını artırarak toplam paketi dengeleyebilir miyiz?",
                "alternative_ask": "Unvan yükseltme veya Hisse / Opsiyon artırımı."
            },
            "take_it_or_leave_it": {
                "recruiter_objection": "Teklifimiz nihai ve son karardır, 48 saat içinde imzalamanız gerekiyor.",
                "candidate_response": "Zaman sınırlamasını ve netliğinizi anlıyorum. Şirketinize olan heyecanım çok yüksek; sadece bu önemli kararı ailemle ve uzun vadeli planlarımla değerlendirmek için Cuma gün sonuna kadar 2 günlük ek süre rica edebilir miyim?",
                "alternative_ask": "Karar süresini 48-72 saat uzatma."
            }
        }
        return playbook.get(objection_type, playbook["no_budget"])


offer_negotiator_engine = OfferNegotiatorEngine()
