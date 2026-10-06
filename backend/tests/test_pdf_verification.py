"""The generated CV must have a text layer an applicant-tracking system can read."""

import pytest

from backend.app.modules.setup.pdf_generator import ats_pdf_generator
from backend.app.tools import verify_pdf as checker

PROFILE = {"full_name": "Ada Example", "email": "ada@example.test", "skills": ["Python", "FastAPI"], "summary": "Backend developer."}


@pytest.fixture
def cv_pdf(tmp_path):
    path = tmp_path / "cv.pdf"
    path.write_bytes(ats_pdf_generator.generate_cv_pdf(PROFILE).getvalue())
    return path


def test_the_generated_cv_is_machine_readable(cv_pdf, tmp_path):
    dump = tmp_path / "text.txt"

    extractor, text, pages = checker.verify_pdf(cv_pdf, min_chars=20, contains=["Ada Example", "python"], dump_text=dump)
    summary = checker.verify_pdf_dict(str(cv_pdf), expected_pages=pages)

    assert extractor == "pypdf" and pages >= 1 and "ADA EXAMPLE" in dump.read_text(encoding="utf-8")
    assert summary["status"] == "verified" and summary["non_whitespace_chars"] > 20
    assert "Python, FastAPI" in text and not any(ord(char) == 0x7F for char in text)


def test_each_failed_check_is_explained(cv_pdf, tmp_path):
    def error(**checks):
        return checker.verify_pdf_dict(str(cv_pdf), **checks)["error"]

    assert "Expected 99 page(s)" in error(expected_pages=99)
    assert "minimum: 1000000" in error(min_chars=1_000_000)
    assert "Required keywords missing" in error(contains=["Kubernetes"])
    assert "File not found" in checker.verify_pdf_dict(str(tmp_path / "none.pdf"))["error"]


def test_broken_fonts_and_encoding_are_caught(cv_pdf, monkeypatch):
    monkeypatch.setattr(checker, "extract_text_pypdf", lambda path: ("Name (cid:12)(cid:13)", 1))
    assert "corrupted glyph" in checker.verify_pdf_dict(str(cv_pdf))["error"]

    monkeypatch.setattr(checker, "extract_text_pypdf", lambda path: ("text " + "�" * 6, 1))
    assert "replacement characters" in checker.verify_pdf_dict(str(cv_pdf))["error"]


def test_the_second_extractor_is_used_when_the_first_fails(cv_pdf, monkeypatch):
    def unavailable(path):
        raise checker.VerificationError("pypdf is not installed")

    monkeypatch.setattr(checker, "extract_text_pypdf", unavailable)
    monkeypatch.setattr(checker, "run_tool", lambda command: "Pages:          2\n" if command[0] == "pdfinfo" else "Ada’s CV — Python")

    extractor, text, pages = checker.verify_pdf(cv_pdf, expected_pages=2, contains=["Ada's CV -- python"])
    assert (extractor, pages) == ("pdftotext", 2)

    def missing(command):
        raise checker.VerificationError("not found")

    monkeypatch.setattr(checker, "run_tool", missing)
    assert "Neither pypdf nor pdftotext" in checker.verify_pdf_dict(str(cv_pdf))["error"]


def test_external_tool_problems_become_readable_errors():
    with pytest.raises(checker.VerificationError, match="was not found"):
        checker.run_tool(["definitely-not-a-real-command-xyz"])
    with pytest.raises(checker.VerificationError, match="could not read the PDF"):
        checker.run_tool(["python3", "-c", "import sys; sys.stderr.write('bad file'); sys.exit(2)"])
    assert checker.run_tool(["python3", "-c", "print('ok')"]).strip() == "ok"
    with pytest.raises(checker.VerificationError, match="page count"):
        checker.parse_page_count("Title: none")
