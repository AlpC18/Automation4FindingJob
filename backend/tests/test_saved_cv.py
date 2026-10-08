"""One upload keeps the CV file and saves the profile; nothing has to be re-entered afterwards."""

import pytest
from fastapi.testclient import TestClient

from backend.app.api.profile import fetch_candidate_profile
from backend.app.core.database import get_db_connection
from backend.app.main import app
from backend.app.modules.setup.pdf_generator import ats_pdf_generator

client = TestClient(app)
PROFILE = {
    "full_name": "Ada Example", "email": "ada@example.test", "summary": "Backend developer.",
    "skills": ["Python", "FastAPI", "PostgreSQL"],
    "experience": [{"title": "Developer", "company": "Acme", "period": "2024 - 2025", "bullets": ["Built the billing API"]}],
}


@pytest.fixture
def clean_workspace():
    def wipe():
        conn = get_db_connection()
        conn.cursor().execute("DELETE FROM cv_documents")
        conn.cursor().execute("DELETE FROM candidate_profile")
        conn.cursor().execute("DELETE FROM candidate_profiles")
        conn.commit()
        conn.close()

    wipe()
    yield
    wipe()


def _pdf() -> bytes:
    return ats_pdf_generator.generate_cv_pdf(PROFILE).getvalue()


def _upload(content: bytes, name="ada-cv.pdf"):
    return client.post("/api/setup/cv", files={"file": (name, content, "application/pdf")})


def test_uploading_a_cv_saves_the_file_and_fills_the_profile(clean_workspace):
    pdf = _pdf()

    response = _upload(pdf)
    body = response.json()
    saved = fetch_candidate_profile()

    assert response.status_code == 200
    assert body["cv"]["filename"] == "ada-cv.pdf" and body["cv"]["size_bytes"] == len(pdf)
    assert saved["email"] == "ada@example.test" and "Python" in saved["skills"] and "ADA EXAMPLE" in saved["raw_cv_text"]
    assert "email" in body["filled_fields"] and "skills" in body["filled_fields"]
    assert "target_role" in body["missing_fields"]  # the CV does not say; it is reported, not guessed

    assert client.get("/api/setup/cv").json()["cv"]["filename"] == "ada-cv.pdf"
    download = client.get("/api/setup/cv/download")
    assert download.content == pdf and "ada-cv.pdf" in download.headers["content-disposition"]
    assert download.headers["cache-control"] == "no-store"


def test_the_stored_file_is_encrypted_at_rest(clean_workspace):
    _upload(_pdf())

    conn = get_db_connection()
    row = dict(conn.cursor().execute("SELECT * FROM cv_documents").fetchone())
    conn.close()

    assert row["encrypted_content"].startswith("fernet$") and "%PDF" not in row["encrypted_content"]
    assert "encrypted_content" not in client.get("/api/setup/cv").text


def test_a_new_cv_never_overwrites_what_the_user_already_entered(clean_workspace):
    client.post("/api/setup/update_profile", json={
        "full_name": "Ada E. Example", "email": "work@example.test", "target_role": "Platform Engineer",
        "years_of_experience": 6, "skills": ["Go"],
    })

    body = _upload(_pdf()).json()
    saved = fetch_candidate_profile()

    assert (saved["full_name"], saved["email"], saved["target_role"], saved["years_of_experience"]) == (
        "Ada E. Example", "work@example.test", "Platform Engineer", 6)
    assert saved["skills"][0] == "Go" and "Python" in saved["skills"]  # merged, user's own first
    assert "full_name" not in body["filled_fields"] and body["missing_fields"] == []


def test_replacing_and_deleting_the_cv(clean_workspace):
    _upload(_pdf(), "first.pdf")
    _upload(_pdf(), "second.pdf")

    assert client.get("/api/setup/cv").json()["cv"]["filename"] == "second.pdf"
    assert client.delete("/api/setup/cv").json() == {"deleted": True}
    assert client.get("/api/setup/cv").json() == {"cv": None}
    assert client.get("/api/setup/cv/download").status_code == 404
    assert fetch_candidate_profile()["email"] == "ada@example.test"  # deleting the file keeps the profile


def test_bad_uploads_are_refused_and_save_nothing(clean_workspace):
    assert _upload(b"not a pdf at all").status_code in (400, 415, 422)
    assert _upload(_pdf(), "cv.exe").status_code in (400, 415, 422)
    assert _upload(b"x" * (10 * 1024 * 1024 + 2)).status_code == 413
    assert client.get("/api/setup/cv").json() == {"cv": None}
    assert not fetch_candidate_profile().get("email")


def test_the_target_role_reads_back_as_text_and_keeps_the_role_list(clean_workspace):
    body = {"full_name": "Ada", "email": "a@example.test", "target_role": "Backend Developer", "years_of_experience": 1,
            "skills": ["Python"], "target_roles": ["Backend Developer", "API Engineer"]}
    client.post("/api/setup/update_profile", json=body)
    client.post("/api/setup/update_profile", json={key: value for key, value in body.items() if key != "target_roles"})

    saved = fetch_candidate_profile()

    assert saved["target_role"] == "Backend Developer"
    assert saved["target_roles"] == ["Backend Developer", "API Engineer"]  # an unchanged role must not reset the list


def test_turkish_and_varied_cv_headings_are_understood():
    from backend.app.modules.setup.cv_parser import extract_profile_fields

    fields = extract_profile_fields(
        "Yüksel Örnek\nyuksel@example.test\n\nÖZET\nYazılım öğrencisi.\n\nTEKNİK BECERİLER\nPython, React | SQL\n\n"
        "PROJELER\nKariyer Asistanı\n\nEĞİTİM:\nUBT, Bilgisayar Mühendisliği 2023 - 2027\n\nDİLLER\nTürkçe, İngilizce\n"
    )
    english = extract_profile_fields("Ada Example\n\nSkills & Tools\nGo; Docker\n\nCertifications\nAWS Practitioner\n")

    assert fields["skills"] == ["Python", "React", "SQL"] and fields["languages"] == ["Türkçe", "İngilizce"]
    assert fields["summary"] == "Yazılım öğrencisi." and fields["education"]
    assert english["skills"] == ["Go", "Docker"]  # the certifications heading ends the skills section


TWO_COLUMN_CV = """Ada Example
Software Engineer
Languages: PHP, JavaScript, TypeScript, Python
Frontend: React, Angular, Tailwind CSS
Backend: Node.js,Spring Boot, REST APIs
Tools: Git, Docker, Linux,Postman
AI & Data: Python (Data Engineering), ML workflows
ada@example.test | +383 44 000 000 | github.com/ada | Prishtina, Kosovo
Projects
Education
Technical Skills
Certifications & Courses
University for Business and Technology — UBT
2024 – 2027
• Languages: English (C1 — Fluent), Turkish (C2 — Native), Italian (A2–B1)
• Google AI Professional Certificate — Google (2026)
• Billing API (Python, FastAPI) — Invoicing service handling forty thousand invoices a day for regional clients.
Work Experience
Software Engineer (Freelance) | Independent
2025 – Present
• Delivered custom full-stack web applications for regional clients.
"""


def test_a_two_column_cv_yields_real_skills_not_scrambled_sections():
    from backend.app.modules.setup.cv_parser import extract_profile_fields

    fields = extract_profile_fields(TWO_COLUMN_CV)

    assert fields["skills"][:6] == ["PHP", "JavaScript", "TypeScript", "Python", "React", "Angular"]
    assert {"Spring Boot", "Postman", "ML workflows", "Python (Data Engineering)"} <= set(fields["skills"])
    assert fields["skills"].count("Python") == 1
    assert not any("Certificate" in skill or "University" in skill or "2024" in skill or "Fluent" in skill for skill in fields["skills"])
    assert fields["languages"] == ["English (C1 — Fluent)", "Turkish (C2 — Native)", "Italian (A2–B1)"]
    assert fields["location"] == "Prishtina, Kosovo"
    assert fields["experience"] == [{
        "title": "Software Engineer (Freelance)", "company": "Independent", "period": "2025 – Present",
        "bullets": ["Delivered custom full-stack web applications for regional clients."],
    }]
