"""Persistence and export regressions for the career workspace."""

from zipfile import ZipFile

from backend.app.core.config import settings
from backend.app.core.database import use_tenant
from backend.app.modules.upskill import UpskillEngine


def test_learning_plan_survives_restart_with_notes_and_custom_skill_progress(tmp_path):
    engine = UpskillEngine(tmp_path / "progress.json")
    plan = engine.generate_learning_path([" Docker ", "docker", "Data storytelling"], [], 5)
    assert len(plan["path"]) == 2
    engine.mark_progress("Data storytelling", "completed", "Finished the presentation")

    restarted = UpskillEngine(tmp_path / "progress.json")
    restored = restarted.get_saved_plan()
    assert restored["hours_per_week"] == 5
    assert restored["path"][1]["status"] == "completed"
    assert restarted.get_progress()["details"]["data storytelling"]["notes"] == "Finished the presentation"
    regenerated = restarted.generate_learning_path(["Data storytelling"], [], 3)
    assert regenerated["path"][0]["status"] == "completed"


def test_learning_plans_stay_with_their_tenant(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "DATA_PATH", tmp_path)
    engine = UpskillEngine(tmp_path / "progress.json")
    with use_tenant("learner-one"):
        engine.generate_learning_path(["Docker"], [], 5)
        engine.mark_progress("Docker", "in_progress", "First lab")
    with use_tenant("learner-two"):
        assert engine.get_saved_plan() is None
        assert engine.get_progress()["total_tracked"] == 0
        engine.generate_learning_path(["Rust"], [], 10)
    with use_tenant("learner-one"):
        restored = engine.get_saved_plan()
        assert restored["path"][0]["skill"] == "Docker"
        assert restored["path"][0]["status"] == "in_progress"


def test_portfolio_projects_are_escaped_and_included_in_zip(monkeypatch, tmp_path):
    from backend.app.modules.setup import portfolio_generator as module

    monkeypatch.setattr(module, "_portfolio_output_path", lambda: tmp_path / "index.html")
    monkeypatch.setattr(module, "_portfolio_archive_path", lambda: tmp_path / "portfolio.zip")
    profile = {
        "full_name": "Test Candidate",
        "target_role": "Engineer",
        "projects": [{"title": "<script>alert(1)</script>", "content": "API & dashboard", "metrics": "20% faster", "tech_stack": ["Python"]}],
    }
    result = module.portfolio_generator.generate_static_package(profile, "My work")
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in result["html_content"]
    assert "<script>alert(1)</script>" not in result["html_content"]
    assert "API &amp; dashboard" in result["html_content"]
    with ZipFile(result["archive_path"]) as archive:
        html = archive.read("index.html").decode()
        assert 'id="projects"' in html
        assert "20% faster" in html
        assert "Python" in html
