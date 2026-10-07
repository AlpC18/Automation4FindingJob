"""
Weekly Intelligence Digest & Smart Strategic Notification Engine
Generates Monday Morning Career Digests:
- Weekly activity recap (new jobs, applications sent, interviews booked)
- Top 3 high-priority expiring opportunities
- Market salary intelligence highlights
- Pending follow-up alerts for dormant applications
- Shown on the weekly digest page
"""

from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from backend.app.core.event_logger import agent_logger
from backend.app.modules.scrape.job_feed import feed_jobs
from backend.app.modules.outcome.analytics_engine import calculate_funnel_metrics
from backend.app.modules.outcome.today import _closing_soon_jobs, get_today_actions

MIN_APPLICATIONS_FOR_CV_ADVICE = 5


def build_recommendations(metrics: Dict[str, Any], analytics: Dict[str, Any], pending: Dict[str, int]) -> List[str]:
    """This week's advice, derived only from recorded activity; never from invented trends."""
    advice: List[str] = []
    if pending.get("follow_up_due"):
        advice.append(f"{pending['follow_up_due']} başvurunun takip zamanı geldi; Takip ekranından mesajlarını gönder.")
    if pending.get("confirm_submission"):
        advice.append(f"{pending['confirm_submission']} başvuru portalda gönderilip teyit edilmeyi bekliyor; teyit edilmeden başvuru sayılmaz.")
    if pending.get("approve_draft"):
        advice.append(f"{pending['approve_draft']} taslak onayını bekliyor; inceleyip onayla.")
    if metrics.get("closing_soon_count"):
        advice.append(f"{metrics['closing_soon_count']} ilanın son başvuru tarihi yakın; önce onları değerlendir.")
    if not metrics.get("applications_submitted") and pending.get("new_matches"):
        advice.append(f"Kayıtlı başvurun yok ama {pending['new_matches']} yüksek uyumlu ilan bekliyor; en az biri için başvuru paketi hazırla.")

    insights = analytics.get("observed_insights") or {}
    best_source = insights.get("best_observed_source")
    if best_source:
        advice.append(f"Şu ana kadar en yüksek mülakat dönüşü {best_source['platform']} kaynağından geldi (%{best_source['conversion_rate']}); taramada ona öncelik ver.")
    best_role = insights.get("best_observed_role")
    if best_role:
        advice.append(f"\"{best_role['target_role']}\" hedef rolüyle yapılan başvurular en çok mülakata dönüyor (%{best_role['interview_rate']}); bu role yakın ilanlara ağırlık ver.")
    applied = int(analytics.get("applied_count") or 0)
    if applied >= MIN_APPLICATIONS_FOR_CV_ADVICE and not analytics.get("interview_count"):
        advice.append(f"{applied} doğrulanmış başvurudan mülakat dönüşü yok; CV'ni CV analizi ekranında gözden geçir ve hedef rolünü daralt.")
    if not metrics.get("new_jobs_found"):
        advice.append("Bu hafta yeni ilan taranmadı; tarama başlat veya otomasyon servisini aç.")
    return advice or ["Bekleyen iş yok; başvuru hattını dolu tutmak için yeni bir tarama başlat."]


class WeeklyDigestEngine:
    """Compiles and distributes executive job search summaries."""

    def compile_digest(self) -> Dict[str, Any]:
        """Synthesizes performance metrics and tactical action items."""
        now = datetime.now()
        one_week_ago = now - timedelta(days=7)
        one_week_iso = one_week_ago.isoformat()

        all_jobs = feed_jobs()

        new_this_week = 0
        ranked_this_week = 0
        applied_this_week = 0
        high_match_candidates = []

        for key, job in all_jobs.items():
            first_seen = job.get("first_seen", "")
            if first_seen >= one_week_iso:
                new_this_week += 1

            status = job.get("status")
            if status == "ranked":
                ranked_this_week += 1
                if job.get("match_score", 0) >= 75:
                    high_match_candidates.append(job)
            elif status == "applied" and str(job.get("applied_at") or "") >= one_week_iso:
                # applied_at is only set for confirmed submissions, so this counts real applications from this week.
                applied_this_week += 1

        high_match_candidates.sort(key=lambda x: x.get("match_score", 0), reverse=True)
        top_opportunities = high_match_candidates[:3]

        closing_soon = _closing_soon_jobs()

        metrics = {
            "new_jobs_found": new_this_week,
            "evaluated_ranked": ranked_this_week,
            "applications_submitted": applied_this_week,
            "closing_soon_count": len(closing_soon),
        }
        digest = {
            "period": f"{one_week_ago.strftime('%d %b')} - {now.strftime('%d %b %Y')}",
            "generated_at": now.isoformat(),
            "metrics": metrics,
            "top_opportunities": top_opportunities,
            "closing_soon_jobs": closing_soon[:3],
            "strategic_recommendations": build_recommendations(
                metrics, calculate_funnel_metrics(), get_today_actions()["counts"],
            ),
        }

        agent_logger.log_event("WEEKLY_DIGEST", f"Compiled digest with {new_this_week} new, {applied_this_week} applied")
        return digest


weekly_digest_engine = WeeklyDigestEngine()
