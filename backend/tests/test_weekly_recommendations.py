"""Weekly digest advice must come from recorded activity, not canned text."""

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.modules.outcome.weekly_digest import build_recommendations

QUIET_WEEK = {"new_jobs_found": 3, "applications_submitted": 1, "closing_soon_count": 0}


def test_pending_work_and_deadlines_become_advice_with_real_counts():
    advice = build_recommendations(
        {"new_jobs_found": 12, "applications_submitted": 0, "closing_soon_count": 2},
        {},
        {"follow_up_due": 3, "approve_draft": 1, "new_matches": 4},
    )
    assert len(advice) == 4
    assert advice[0].startswith("3 başvurunun takip zamanı geldi")
    assert advice[1].startswith("1 taslak onayını bekliyor")
    assert advice[2].startswith("2 ilanın son başvuru tarihi")
    assert "4 yüksek uyumlu ilan" in advice[3]


def test_observed_results_drive_source_and_role_advice():
    analytics = {
        "applied_count": 6, "interview_count": 2,
        "observed_insights": {
            "best_observed_source": {"platform": "Linkedin", "conversion_rate": 33.3},
            "best_observed_role": {"target_role": "Backend Engineer", "interview_rate": 40.0},
        },
    }
    advice = build_recommendations(QUIET_WEEK, analytics, {})
    assert any("Linkedin" in line and "%33.3" in line for line in advice)
    assert any("Backend Engineer" in line and "%40.0" in line for line in advice)
    assert not any("CV'ni" in line for line in advice)


def test_many_applications_without_interviews_points_at_the_cv():
    advice = build_recommendations(QUIET_WEEK, {"applied_count": 5, "interview_count": 0, "observed_insights": {}}, {})
    assert advice == ["5 doğrulanmış başvurudan mülakat dönüşü yok; CV'ni CV analizi ekranında gözden geçir ve hedef rolünü daralt."]


def test_empty_week_never_invents_a_trend():
    assert build_recommendations(QUIET_WEEK, {}, {}) == ["Bekleyen iş yok; başvuru hattını dolu tutmak için yeni bir tarama başlat."]
    idle = build_recommendations({"new_jobs_found": 0}, {}, {})
    assert idle == ["Bu hafta yeni ilan taranmadı; tarama başlat veya otomasyon servisini aç."]


def test_digest_endpoint_returns_data_driven_advice():
    digest = TestClient(app).get("/api/outcome/digest").json()
    assert digest["strategic_recommendations"]
    assert not any("%24" in line for line in digest["strategic_recommendations"])
