"""
Conversion Funnel Analytics Engine
Calculates stage drop-offs and application outcomes attributed to source, role and profile version.
"""

from typing import Dict, Any, List
from backend.app.core.database import get_db_connection

def calculate_funnel_metrics() -> Dict[str, Any]:
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Moving a card to any Kanban stage is not proof of an external submission.
    # The explicit portal confirmation flag is the single source of truth.
    verified_application = "submission_confirmed = 1"

    # The conversion funnel tracks application work, not every scraped listing.
    # Raw feed items remain visible in platform totals below, but enter the
    # funnel only after a package is prepared or a user moves them to a stage.
    tracked_pipeline = """
        (stale_at IS NULL OR submission_confirmed = 1)
        AND (
            COALESCE(status, 'Draft') NOT IN ('Draft', 'New', '')
            OR COALESCE(cover_letter, '') <> ''
            OR COALESCE(micro_portfolio, '') <> ''
        )
        AND (
            COALESCE(status, 'Draft') NOT IN ('Interview', 'Offer')
            OR COALESCE(submission_confirmed, 0) = 1
        )
    """

    # 1. Stage Counts
    cursor.execute("""
        SELECT COALESCE(status, 'Draft') AS status, COUNT(*) as count
        FROM scraped_jobs
        WHERE """ + tracked_pipeline + " GROUP BY COALESCE(status, 'Draft')")
    rows = cursor.fetchall()
    counts = {r["status"]: r["count"] for r in rows}
    cursor.execute("SELECT COUNT(*) AS count FROM scraped_jobs WHERE " + tracked_pipeline)
    total_jobs = cursor.fetchone()["count"]
    
    cursor.execute(f"SELECT COUNT(*) AS count FROM scraped_jobs WHERE {verified_application}")
    applied_count = cursor.fetchone()["count"]
    counts["Applied"] = applied_count

    stages = ["Draft", "Human Review", "Applied", "Interview", "Offer", "Rejected"]
    funnel = []
    
    interview_count = counts.get("Interview", 0) + counts.get("Offer", 0)
    offer_count = counts.get("Offer", 0)
    
    for s in stages:
        funnel.append({
            "stage": s,
            "count": counts.get(s, 0),
            "percentage_of_total": round((counts.get(s, 0) / max(total_jobs, 1)) * 100, 1)
        })

    # 2. Platform Conversion Breakdown
    cursor.execute(f"""
        SELECT platform,
               SUM(CASE WHEN stale_at IS NULL OR submission_confirmed = 1 THEN 1 ELSE 0 END) as total,
               SUM(CASE WHEN {verified_application} THEN 1 ELSE 0 END) as applied,
               SUM(CASE WHEN submission_confirmed = 1 AND status IN ('Interview', 'Offer') THEN 1 ELSE 0 END) as interviews,
               SUM(CASE WHEN submission_confirmed = 1 AND status = 'Rejected' THEN 1 ELSE 0 END) as rejected,
               AVG(match_score) as avg_match_score,
               AVG(ghost_score) as avg_ghost_score
        FROM scraped_jobs
        WHERE stale_at IS NULL OR submission_confirmed = 1
        GROUP BY platform
    """)
    platform_rows = cursor.fetchall()
    platform_stats = []
    for r in platform_rows:
        tot = r["total"]
        apps = r["applied"] or 0
        ints = r["interviews"] or 0
        rejected = r["rejected"] or 0
        conv_rate = round((ints / max(apps, 1)) * 100, 1) if apps > 0 else 0.0
        
        platform_stats.append({
            "platform": r["platform"].capitalize(),
            "total_scraped": tot,
            "applied": apps,
            "interviews": ints,
            "rejected": rejected,
            "awaiting_response": max(apps - ints - rejected, 0),
            "verified_application_sample": apps,
            "insight_eligible": apps >= 3,
            "conversion_rate": conv_rate,
            "avg_match_score": round(r["avg_match_score"] or 0, 1),
            "avg_ghost_score": round(r["avg_ghost_score"] or 0, 1)
        })

    cursor.execute("""SELECT COALESCE(a.target_role, 'Profil rolü yok') AS target_role,
        COUNT(*) AS applications,
        SUM(CASE WHEN j.status IN ('Interview', 'Offer') THEN 1 ELSE 0 END) AS interviews,
        SUM(CASE WHEN j.status = 'Offer' THEN 1 ELSE 0 END) AS offers,
        SUM(CASE WHEN j.status = 'Rejected' THEN 1 ELSE 0 END) AS rejected,
        COUNT(DISTINCT a.profile_version) AS profile_versions
        FROM application_attribution a JOIN scraped_jobs j ON j.id = a.job_id
        WHERE j.submission_confirmed = 1
        GROUP BY COALESCE(a.target_role, 'Profil rolü yok') ORDER BY applications DESC""")
    role_stats = [{
        "target_role": row["target_role"], "applications": row["applications"],
        "interviews": row["interviews"] or 0, "offers": row["offers"] or 0,
        "rejected": row["rejected"] or 0,
        "awaiting_response": max(row["applications"] - (row["interviews"] or 0) - (row["rejected"] or 0), 0),
        "interview_rate": round((row["interviews"] or 0) * 100 / max(row["applications"], 1), 1),
        "profile_versions": row["profile_versions"],
        "insight_eligible": row["applications"] >= 3,
    } for row in cursor.fetchall()]

    eligible_platforms = [item for item in platform_stats if item["insight_eligible"]]
    eligible_roles = [item for item in role_stats if item["insight_eligible"]]
    observed_insights = {
        "minimum_verified_applications": 3,
        "best_observed_source": max((item for item in eligible_platforms if item["interviews"] > 0), key=lambda item: (item["conversion_rate"], item["verified_application_sample"])) if any(item["interviews"] > 0 for item in eligible_platforms) else None,
        "best_observed_role": max((item for item in eligible_roles if item["interviews"] > 0), key=lambda item: (item["interview_rate"], item["applications"])) if any(item["interviews"] > 0 for item in eligible_roles) else None,
        "eligible_source_groups": len(eligible_platforms),
        "eligible_role_groups": len(eligible_roles),
        "has_verified_interviews": interview_count > 0,
        "note": "Descriptive comparison of explicitly confirmed external submissions only; requires at least 3 confirmed applications per group and is not a prediction of future outcomes.",
    }

    cursor.execute("""SELECT r.version, r.target_role, r.created_at,
        SUM(CASE WHEN j.submission_confirmed = 1 THEN 1 ELSE 0 END) AS applications,
        SUM(CASE WHEN j.submission_confirmed = 1 AND j.status IN ('Interview', 'Offer') THEN 1 ELSE 0 END) AS interviews
        FROM profile_revisions r LEFT JOIN application_attribution a ON a.profile_version = r.version
        LEFT JOIN scraped_jobs j ON j.id = a.job_id GROUP BY r.version, r.target_role, r.created_at
        ORDER BY r.version DESC LIMIT 10""")
    profile_performance = [dict(row) for row in cursor.fetchall()]

    cursor.execute(f"SELECT COUNT(*) AS count FROM scraped_jobs WHERE {verified_application} AND status = 'Rejected'")
    rejected_count = cursor.fetchone()["count"]

    conn.close()

    return {
        "total_jobs": total_jobs,
        "applied_count": applied_count,
        "interview_count": interview_count,
        "offer_count": offer_count,
        "rejected_count": rejected_count,
        "awaiting_response_count": max(applied_count - interview_count - rejected_count, 0),
        "interview_rate": f"{round((interview_count / max(applied_count, 1)) * 100, 1)}%",
        "funnel_stages": funnel,
        "platform_performance": platform_stats,
        "role_performance": role_stats,
        "profile_version_performance": profile_performance,
        "observed_insights": observed_insights,
        "analytics_note": "Başvurular yalnızca portal gönderimi açıkça doğrulandığında sayılır. Mülakat, teklif ve ret metrikleri de yalnızca gönderimi doğrulanmış başvurulardan hesaplanır; taslaklar ve doğrulanmamış Kanban durumları hariçtir.",
    }
