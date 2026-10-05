"""CV extraction and explicit AI-consent contract tests."""

import io
import zipfile

import pytest
from pypdf import PdfWriter
from reportlab.pdfgen import canvas
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.modules.setup.cv_parser import (
    CVParseError,
    analyze_cv_quality,
    build_local_optimized_cv,
    extract_cv_text,
    extract_profile_fields,
    validate_ai_profile_fields,
)
from backend.app.api.routers import setup as setup_router


client = TestClient(app)


def make_pdf(text: str = "Ada Lovelace\nada@example.com\nPython, SQL\nProfessional experience") -> bytes:
    buffer = io.BytesIO()
    document = canvas.Canvas(buffer)
    for index, line in enumerate(text.splitlines()):
        document.drawString(72, 720 - index * 18, line)
    document.save()
    return buffer.getvalue()


def make_docx(text: str = "Ada Lovelace\nada@example.com\nSkills\nPython, SQL") -> bytes:
    xml_text = "".join(f"<w:p><w:r><w:t>{line}</w:t></w:r></w:p>" for line in text.splitlines())
    document_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{xml_text}</w:body></w:document>"
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("word/document.xml", document_xml)
    return buffer.getvalue()


def test_extracts_selectable_pdf_text_and_profile_fields():
    text, page_count = extract_cv_text("resume.pdf", make_pdf())
    fields = extract_profile_fields(text)
    assert page_count == 1
    assert fields["email"] == "ada@example.com"
    assert fields["full_name"] == "Ada Lovelace"


def test_extracts_docx_text_and_profile_fields():
    text, page_count = extract_cv_text(
        "resume.docx",
        make_docx("Ada Lovelace\nada@example.com\nSkills\nPython, SQL\nExperience\nSoftware Engineer | Analytical Engines | 2020 - 2024\nEducation\nBSc Mathematics, University of London, 1843"),
    )
    fields = extract_profile_fields(text)
    assert page_count is None
    assert "Python, SQL" in text
    assert fields["email"] == "ada@example.com"
    assert fields["skills"] == ["Python", "SQL"]
    assert fields["experience"][0]["company"] == "Analytical Engines"
    assert fields["education"][0]["school"] == "University of London"


def test_ai_profile_fields_are_bounded_and_keep_experience_bullets_structured():
    parsed = validate_ai_profile_fields({
        "years_of_experience": 5,
        "experience": [{"title": "Engineer", "bullets": ["Built APIs", "Improved reliability"]}],
        "email": "x" * 300,
        "extra_private_field": "discard me",
    })
    assert parsed["experience"][0]["bullets"] == ["Built APIs", "Improved reliability"]
    assert len(parsed["email"]) == 254
    assert "extra_private_field" not in parsed


def test_quality_report_is_explainable_and_recommends_missing_sections():
    text = "Ada Lovelace\nada@example.com\nSkills\nPython, SQL\nExperience\nSoftware Engineer | Analytical Engines | 2020 - 2024"
    fields = extract_profile_fields(text)
    report = analyze_cv_quality(text, fields, 1)
    assert report["score"] < 80
    assert report["grade"] in {"good", "needs_improvement", "weak"}
    assert "add_target_role" in report["recommendation_ids"]
    assert {item["id"] for item in report["criteria"]} == {"contact", "profile_sections", "measurable_impact", "targeting", "readability"}


def test_local_optimized_cv_preserves_only_extracted_facts():
    text = "Ada Lovelace\nada@example.com\nSkills\nPython, SQL\nExperience\nSoftware Engineer | Analytical Engines | 2020 - 2024"
    fields = extract_profile_fields(text)
    draft = build_local_optimized_cv(text, fields)
    assert "ADA LOVELACE" in draft
    assert "ada@example.com" in draft
    assert "Python, SQL" in draft
    assert "Analytical Engines" in draft
    assert "CANDIDATE" not in draft
    assert "Company" not in draft


@pytest.mark.parametrize(
    ("filename", "content", "message"),
    [
        ("resume.docx", b"not a zip file", "DOCX okunamadı"),
        ("resume.pdf", b"", "boş"),
        ("resume.txt", b"plain text", "PDF veya DOCX"),
    ],
)
def test_rejects_invalid_or_unsupported_files(filename, content, message):
    with pytest.raises(CVParseError, match=message):
        extract_cv_text(filename, content)


def test_rejects_oversized_cv():
    with pytest.raises(CVParseError, match="10 MB") as error:
        extract_cv_text("resume.pdf", b"x" * (10 * 1024 * 1024 + 1))
    assert error.value.status_code == 413


def test_rejects_encrypted_pdf():
    writer = PdfWriter()
    writer.add_blank_page(width=300, height=300)
    writer.encrypt("secret")
    encrypted = io.BytesIO()
    writer.write(encrypted)
    with pytest.raises(CVParseError, match="Şifreli"):
        extract_cv_text("resume.pdf", encrypted.getvalue())


def test_parse_cv_does_not_call_ai_without_explicit_opt_in(monkeypatch):
    class ForbiddenAI:
        def get_effective_provider(self):
            raise AssertionError("AI provider must not be selected without explicit opt-in")

    monkeypatch.setattr(setup_router, "llm_client", ForbiddenAI())
    response = client.post(
        "/api/setup/parse_cv",
        files={"file": ("resume.pdf", make_pdf(), "application/pdf")},
    )
    assert response.status_code == 200
    assert response.json()["ai_requested"] is False
    assert response.json()["ai_used"] is False
    assert response.headers["cache-control"] == "no-store"


def test_parse_cv_uses_ai_only_after_explicit_opt_in(monkeypatch):
    class OptInAI:
        def __init__(self):
            self.called = False

        def get_effective_provider(self):
            return "openai"

        async def generate_json(self, **_kwargs):
            self.called = True
            return {"target_role": "Backend Engineer", "skills": ["Python", "APIs"]}

    ai = OptInAI()
    monkeypatch.setattr(setup_router, "llm_client", ai)
    response = client.post(
        "/api/setup/parse_cv",
        data={"use_ai": "true"},
        files={"file": ("resume.pdf", make_pdf(), "application/pdf")},
    )
    assert response.status_code == 200
    assert ai.called
    assert response.json()["ai_requested"] is True
    assert response.json()["ai_used"] is True
    assert response.json()["fields"]["target_role"] == "Backend Engineer"
