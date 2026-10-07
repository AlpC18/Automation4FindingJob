"""The per-job fit report states only what the CV, saved projects and posting contain."""

from backend.app.modules.apply.fit_report import build_fit_report

PROFILE = {"skills": ["Python", "FastAPI", "React", "PHP"], "target_roles": ["Backend Developer"], "years_of_experience": 1,
           "raw_cv_text": "Freelance developer. Python, FastAPI, React, PHP."}
PROJECTS = [
    {"title": "ClearMark / Watermark Engine", "tech_stack": ["Python", "FastAPI", "Celery"], "content": "Image inpainting web application."},
    {"title": "ShopFront", "tech_stack": ["React", "TypeScript"], "content": "Storefront."},
]
JOB = {"id": "j1", "title": "Senior Backend Developer", "company": "Acme", "match_score": 61.5,
       "description": "We use Python, FastAPI, Kubernetes and Kafka. Celery experience is a plus."}


def test_report_separates_what_the_cv_shows_from_what_it_lacks():
    report = build_fit_report(PROFILE, PROJECTS, JOB)

    assert report["match_percent"] == 61.5
    assert set(report["keywords_you_have"]) == {"Python", "FastAPI", "Celery"}
    assert set(report["keywords_missing"]) == {"Kubernetes", "Kafka"}
    assert report["breakdown"]["skill_coverage_percent"] == 60 and report["breakdown"]["senior_title"] is True
    assert "not a chance of being hired" in report["note"]


def test_tailored_version_reorders_and_selects_without_inventing():
    tailored = build_fit_report(PROFILE, PROJECTS, JOB)["tailored"]

    assert tailored["skills_order"][:2] == ["Python", "FastAPI"] and set(tailored["skills_order"]) == set(PROFILE["skills"])
    assert [project["title"] for project in tailored["projects_to_show"]] == ["ClearMark / Watermark Engine"]
    assert "Kubernetes" not in tailored["summary_line"] and "1 year of experience" in tailored["summary_line"]


def test_edits_are_concrete_and_warn_about_seniority_and_missing_skills():
    edits = " ".join(build_fit_report(PROFILE, PROJECTS, JOB)["edits"])

    assert "Python" in edits and "Add one only if you have really used it" in edits and "senior title" in edits


def test_an_empty_posting_or_profile_does_not_break():
    report = build_fit_report({}, [], {"id": "x", "title": "", "description": ""})

    assert report["keywords_you_have"] == [] and report["breakdown"]["skill_coverage_percent"] is None
