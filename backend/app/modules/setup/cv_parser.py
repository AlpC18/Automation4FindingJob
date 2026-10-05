"""Private, in-memory CV text and profile-field extraction helpers."""

from __future__ import annotations

import io
import re
import zipfile
from typing import Any
from xml.etree import ElementTree

from pypdf import PdfReader


MAX_CV_BYTES = 10 * 1024 * 1024
MAX_CV_PAGES = 50
MAX_DOCX_XML_BYTES = 20 * 1024 * 1024


class CVParseError(ValueError):
    def __init__(self, message: str, status_code: int = 422):
        super().__init__(message)
        self.status_code = status_code


def extract_cv_text(filename: str, content: bytes) -> tuple[str, int | None]:
    """Extract selectable text from PDF or DOCX bytes without persisting the file."""
    extension = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    if extension not in {"pdf", "docx"}:
        raise CVParseError("CV dosyası PDF veya DOCX biçiminde olmalıdır.", 415)
    if len(content) > MAX_CV_BYTES:
        raise CVParseError("CV dosyası 10 MB sınırını aşamaz.", 413)
    if not content:
        raise CVParseError("CV dosyası boş.")

    if extension == "pdf":
        try:
            reader = PdfReader(io.BytesIO(content), strict=False)
            if reader.is_encrypted:
                raise CVParseError("Şifreli PDF dosyaları açılamıyor.")
            if len(reader.pages) > MAX_CV_PAGES:
                raise CVParseError("CV PDF'i en fazla 50 sayfa olabilir.")
            text = "\n\n".join(page.extract_text() or "" for page in reader.pages).strip()
            page_count = len(reader.pages)
        except CVParseError:
            raise
        except Exception as exc:
            raise CVParseError("PDF okunamadı; dosyanın sağlam ve metin içeren bir PDF olduğunu kontrol edin.") from exc
        if len(text) < 30:
            raise CVParseError("PDF'ten seçilebilir metin çıkarılamadı. Taranmış CV'ler için OCR henüz desteklenmiyor.")
        return text, page_count

    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            info = archive.getinfo("word/document.xml")
            if info.file_size > MAX_DOCX_XML_BYTES:
                raise CVParseError("DOCX içeriği izin verilen boyutu aşıyor.", 413)
            root = ElementTree.fromstring(archive.read(info))
        ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        paragraphs: list[str] = []
        for paragraph in root.findall(".//w:p", ns):
            words = [node.text or "" for node in paragraph.findall(".//w:t", ns)]
            value = "".join(words).strip()
            if value:
                paragraphs.append(value)
        text = "\n".join(paragraphs).strip()
    except CVParseError:
        raise
    except (zipfile.BadZipFile, KeyError, ElementTree.ParseError, OSError) as exc:
        raise CVParseError("DOCX okunamadı; dosyanın sağlam bir Word belgesi olduğunu kontrol edin.") from exc
    if len(text) < 30:
        raise CVParseError("DOCX dosyasından yeterli metin çıkarılamadı.")
    return text, None


_EMAIL = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_PHONE = re.compile(r"(?<!\w)(?:\+?\d[\d\s()./-]{7,}\d)(?!\w)")
_URL = re.compile(r"(?:https?://)?(?:www\.)?(?:github\.com|linkedin\.com)/[A-Za-z0-9._%/-]+", re.IGNORECASE)
_SECTION = re.compile(r"^(summary|profile|about(?: me)?|experience|work experience|employment|education|skills|technical skills|languages|projects)\s*:?[\s]*$", re.IGNORECASE)
_DATE = re.compile(r"\b(?:(?:19|20)\d{2})(?:\s*[-–—]\s*(?:(?:19|20)\d{2}|present|current|now))?\b|\b(?:present|current|now)\b", re.IGNORECASE)


def extract_profile_fields(text: str) -> dict[str, Any]:
    """Conservative local extraction: return only values directly found in the CV."""
    lines = [re.sub(r"\s+", " ", line).strip(" \t•●▪-") for line in text.splitlines()]
    lines = [line for line in lines if line]
    result: dict[str, Any] = {
        "full_name": "", "email": "", "phone": "", "location": "", "target_role": "",
        "years_of_experience": 0, "skills": [], "languages": [], "github_url": "", "summary": "",
        "experience": [], "education": [],
    }
    confidence: dict[str, float] = {}

    email = _EMAIL.search(text)
    if email:
        result["email"] = email.group(0)
        confidence["email"] = 0.99
    phone = _PHONE.search(text)
    if phone:
        normalized = re.sub(r"\s+", " ", phone.group(0)).strip()
        if sum(char.isdigit() for char in normalized) >= 8:
            result["phone"] = normalized
            confidence["phone"] = 0.78
    for match in _URL.finditer(text):
        url = match.group(0).rstrip(".,;)")
        if "github.com" in url.lower():
            result["github_url"] = url if url.lower().startswith("http") else f"https://{url}"
            confidence["github_url"] = 0.98
            break

    ignored = {"resume", "curriculum vitae", "cv", "curriculum vitae (cv)"}
    for line in lines[:8]:
        if _EMAIL.search(line) or _PHONE.search(line) or _SECTION.match(line) or line.lower() in ignored:
            continue
        if len(line.split()) in range(2, 5) and len(line) < 70 and not re.search(r"\d{3,}", line):
            result["full_name"] = line
            confidence["full_name"] = 0.55
            break

    section = ""
    section_lines: dict[str, list[str]] = {key: [] for key in ("summary", "experience", "education", "skills", "languages")}
    section_aliases = {
        "summary": {"summary", "profile", "about", "about me", "professional summary", "professional profile"},
        "experience": {"experience", "work experience", "employment", "professional experience", "work history"},
        "education": {"education", "academic background", "qualifications"},
        "skills": {"skills", "technical skills", "core skills", "competencies", "technologies"},
        "languages": {"languages", "language skills"},
    }
    for line in lines:
        normalized = line.strip(": ").lower()
        matched = next((key for key, aliases in section_aliases.items() if normalized in aliases), None)
        if matched:
            section = matched
            continue
        if _SECTION.match(line) and normalized not in {alias for aliases in section_aliases.values() for alias in aliases}:
            section = ""
            continue
        if section:
            section_lines[section].append(line)

    summary_lines = section_lines["summary"]
    if summary_lines:
        result["summary"] = " ".join(summary_lines)[:1200]
        confidence["summary"] = 0.62

    skill_lines = section_lines["skills"]
    if skill_lines:
        skills = [part.strip(" •●▪-") for line in skill_lines for part in re.split(r"[,;|•]", line)]
        result["skills"] = list(dict.fromkeys(skill for skill in skills if 1 < len(skill) < 60))[:40]
        if result["skills"]:
            confidence["skills"] = 0.62

    language_lines = section_lines["languages"]
    if language_lines:
        result["languages"] = list(dict.fromkeys(part.strip(" •●▪-") for line in language_lines for part in re.split(r"[,;|•]", line) if part.strip(" •●▪-")))[:20]
        if result["languages"]:
            confidence["languages"] = 0.58

    experience: list[dict[str, Any]] = []
    for line in section_lines["experience"]:
        bullet = line.lstrip(" •●▪-").strip()
        if (line[:1] in {"•", "●", "▪", "-"}) and experience:
            experience[-1]["bullets"].append(bullet[:500])
            continue
        date_match = _DATE.search(line)
        parts = [part.strip() for part in re.split(r"\s*(?:\||•|—|–)\s*", line) if part.strip()]
        if len(parts) >= 2:
            record: dict[str, Any] = {"title": parts[0], "company": parts[1], "period": "", "bullets": []}
            if date_match:
                record["period"] = date_match.group(0)
            experience.append(record)
        elif date_match and experience and not experience[-1]["period"]:
            experience[-1]["period"] = date_match.group(0)
        elif re.search(r"\s+at\s+", line, re.IGNORECASE):
            title, company = re.split(r"\s+at\s+", line, maxsplit=1, flags=re.IGNORECASE)
            experience.append({"title": title.strip(), "company": company.strip(), "period": date_match.group(0) if date_match else "", "bullets": []})
    if experience:
        result["experience"] = experience[:20]
        confidence["experience"] = 0.55

    education: list[dict[str, Any]] = []
    for line in section_lines["education"]:
        parts = [part.strip() for part in re.split(r"\s*(?:\||•|—|–|,)\s*", line) if part.strip()]
        if len(parts) >= 2:
            year = next((part for part in parts if re.search(r"\b(?:19|20)\d{2}\b", part)), "")
            degree = parts[0] if parts[0] != year else ""
            school = next((part for part in parts[1:] if part != year), "")
            if degree or school:
                education.append({"degree": degree, "school": school, "year": year})
    if education:
        result["education"] = education[:20]
        confidence["education"] = 0.55

    # Suggest a role only when a labeled title exists; avoid guessing from arbitrary lines.
    for line in lines[:14]:
        labeled = re.match(r"(?:target role|role|position|title|hedef pozisyon)\s*:\s*(.+)", line, re.IGNORECASE)
        if labeled:
            result["target_role"] = labeled.group(1).strip()
            confidence["target_role"] = 0.82
            break

    for line in lines[:12]:
        labeled = re.match(r"(?:location|based in|konum|ikamet)\s*:\s*(.+)", line, re.IGNORECASE)
        if labeled:
            result["location"] = labeled.group(1).strip()
            confidence["location"] = 0.8
            break

    years = re.search(r"(?:over|more than|\+)?\s*(\d{1,2})\s*\+?\s*(?:years?|yrs?)\s+(?:of\s+)?(?:experience|exp)", text, re.IGNORECASE)
    if years:
        result["years_of_experience"] = int(years.group(1))
        confidence["years_of_experience"] = 0.76

    # The local parser deliberately leaves complex timelines empty rather than inventing records.
    result["confidence"] = confidence
    return result


def validate_ai_profile_fields(candidate: Any) -> dict[str, Any]:
    """Keep only supported, bounded profile fields from an explicitly requested AI parse."""
    if not isinstance(candidate, dict):
        return {}
    scalar_limits = {
        "full_name": 120, "email": 254, "phone": 60, "location": 120, "target_role": 160,
        "summary": 2000, "github_url": 500,
    }
    cleaned: dict[str, Any] = {}
    for key, limit in scalar_limits.items():
        value = candidate.get(key)
        if isinstance(value, str) and value.strip():
            cleaned[key] = value.strip()[:limit]
    experience = candidate.get("experience")
    if isinstance(experience, list):
        cleaned["experience"] = []
        for item in experience[:20]:
            if not isinstance(item, dict):
                continue
            record = {key: str(item.get(key, ""))[:1200] for key in ("title", "company", "period") if isinstance(item.get(key, ""), str)}
            bullets = item.get("bullets")
            if isinstance(bullets, list):
                record["bullets"] = [str(value)[:500] for value in bullets[:12]]
            elif isinstance(bullets, str):
                record["bullets"] = [line[:500] for line in bullets.splitlines()[:12] if line.strip()]
            cleaned["experience"].append(record)
    education = candidate.get("education")
    if isinstance(education, list):
        cleaned["education"] = [
            {key: str(item.get(key, ""))[:200] for key in ("degree", "school", "year") if isinstance(item.get(key, ""), str)}
            for item in education[:20] if isinstance(item, dict)
        ]
    skills = candidate.get("skills")
    if isinstance(skills, list):
        cleaned["skills"] = list(dict.fromkeys(str(value).strip()[:80] for value in skills[:60] if str(value).strip()))
    languages = candidate.get("languages")
    if isinstance(languages, list):
        cleaned["languages"] = list(dict.fromkeys(str(value).strip()[:80] for value in languages[:30] if str(value).strip()))
    years = candidate.get("years_of_experience")
    if isinstance(years, int) and 0 <= years <= 60:
        cleaned["years_of_experience"] = years
    return cleaned


def validate_ai_cv_analysis(candidate: Any) -> dict[str, Any]:
    """Validate concise, evidence-based CV feedback returned by an opted-in AI provider."""
    if not isinstance(candidate, dict):
        return {}
    result: dict[str, Any] = {}
    for key in ("strengths", "gaps", "improvements"):
        values = candidate.get(key)
        if isinstance(values, list):
            result[key] = [value.strip()[:500] for value in values[:8] if isinstance(value, str) and value.strip()]
    issues = candidate.get("potential_issues")
    if isinstance(issues, list):
        result["potential_issues"] = []
        for issue in issues[:8]:
            if not isinstance(issue, dict):
                continue
            finding = issue.get("finding")
            if not isinstance(finding, str) or not finding.strip():
                continue
            severity = issue.get("severity")
            result["potential_issues"].append({
                "severity": severity if severity in {"low", "medium", "high"} else "medium",
                "finding": finding.strip()[:500],
                "evidence": issue.get("evidence", "")[:300] if isinstance(issue.get("evidence", ""), str) else "",
                "recommendation": issue.get("recommendation", "")[:500] if isinstance(issue.get("recommendation", ""), str) else "",
            })
    return result


def validate_optimized_cv(candidate: Any) -> str:
    """Accept a bounded plain-text rewrite only; never overwrite the uploaded source file."""
    if not isinstance(candidate, str):
        return ""
    cleaned = candidate.strip()
    if len(cleaned) < 100:
        return ""
    return cleaned[:30000]


def build_local_optimized_cv(text: str, fields: dict[str, Any]) -> str:
    """Create an ATS-friendly draft from facts found locally, without inventing content."""
    lines: list[str] = []
    name = str(fields.get("full_name") or "").strip()
    if name:
        lines.append(name.upper())
    contact = [str(fields.get(key) or "").strip() for key in ("email", "phone", "location", "github_url")]
    contact = [value for value in contact if value]
    if contact:
        lines.append(" | ".join(contact))
    if lines:
        lines.extend(["", "=" * 58, ""])

    def add_section(title: str, values: list[str]) -> None:
        if values:
            lines.extend([title, "-" * len(title), *values, ""])

    target_role = str(fields.get("target_role") or "").strip()
    summary = str(fields.get("summary") or "").strip()
    if target_role:
        add_section("TARGET ROLE", [target_role])
    if summary:
        add_section("PROFESSIONAL SUMMARY", [summary])

    skills = fields.get("skills") if isinstance(fields.get("skills"), list) else []
    skills = [str(skill).strip() for skill in skills if str(skill).strip()]
    add_section("CORE SKILLS & TECHNOLOGIES", [", ".join(skills)] if skills else [])

    experiences = fields.get("experience") if isinstance(fields.get("experience"), list) else []
    experience_lines: list[str] = []
    for item in experiences:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        company = str(item.get("company") or "").strip()
        period = str(item.get("period") or "").strip()
        heading = " - ".join(value for value in (title, company) if value)
        if period:
            heading = f"{heading} [{period}]" if heading else period
        if heading:
            experience_lines.append(heading)
        bullets = item.get("bullets") if isinstance(item.get("bullets"), list) else []
        experience_lines.extend(f"- {str(bullet).strip()}" for bullet in bullets if str(bullet).strip())
        if heading or bullets:
            experience_lines.append("")
    add_section("PROFESSIONAL EXPERIENCE", experience_lines)

    education = fields.get("education") if isinstance(fields.get("education"), list) else []
    education_lines: list[str] = []
    for item in education:
        if not isinstance(item, dict):
            continue
        values = [str(item.get(key) or "").strip() for key in ("degree", "school", "year")]
        values = [value for value in values if value]
        if values:
            education_lines.append(" - ".join(values))
    add_section("EDUCATION", education_lines)

    languages = fields.get("languages") if isinstance(fields.get("languages"), list) else []
    languages = [str(language).strip() for language in languages if str(language).strip()]
    add_section("LANGUAGES", [", ".join(languages)] if languages else [])

    draft = "\n".join(lines).strip()
    if len(draft) >= 100:
        return draft[:30000]
    # A short or poorly structured CV still gets a safe formatting pass; its facts are untouched.
    cleaned = re.sub(r"[\u2022\u2023\u25E6\u2043\u2219\u25AA\u25AB\u25CF\u2713\u2714\u25CB\u25C6]", "-", text)
    cleaned = "\n".join(line.strip() for line in cleaned.splitlines() if line.strip())
    return cleaned[:30000] if len(cleaned) >= 30 else ""


def analyze_cv_quality(text: str, fields: dict[str, Any], page_count: int | None = None) -> dict[str, Any]:
    """Explainable, deterministic CV-readiness rubric; it evaluates the document, not the person."""
    sections = {
        "summary": ("summary", "profile", "professional summary", "professional profile", "about me"),
        "experience": ("experience", "work experience", "professional experience", "employment", "work history"),
        "education": ("education", "academic background", "qualifications"),
        "skills": ("skills", "technical skills", "core skills", "competencies", "technologies"),
        "languages": ("languages", "language skills"),
    }
    normalized_lines = [line.strip().strip(":").lower() for line in text.splitlines() if line.strip()]
    detected_sections = {
        section for section, aliases in sections.items()
        if any(line in aliases for line in normalized_lines)
    }
    email_present = bool(_EMAIL.search(text))
    phone_present = bool(_PHONE.search(text))
    skills = fields.get("skills") if isinstance(fields.get("skills"), list) else []
    experience = fields.get("experience") if isinstance(fields.get("experience"), list) else []
    experience_bullets = [
        bullet
        for record in experience if isinstance(record, dict)
        for bullet in (record.get("bullets") if isinstance(record.get("bullets"), list) else [])
        if isinstance(bullet, str)
    ]
    quantified_bullets = sum(bool(re.search(r"\d|%|\$|€|£", bullet)) for bullet in experience_bullets)
    has_bullets = bool(re.search(r"(?m)^\s*[•●▪*-]\s+", text)) or bool(experience_bullets)

    contact_score = (6 if email_present else 0) + (4 if phone_present else 0)
    section_score = (
        (6 if fields.get("summary") else 0)
        + (8 if skills else 0)
        + (8 if experience else 0)
        + (4 if fields.get("education") else 0)
        + (4 if fields.get("location") else 0)
    )
    impact_score = 0 if not experience else min(25, 5 + quantified_bullets * 7)
    focus_score = (8 if fields.get("target_role") else 0) + (4 if fields.get("summary") else 0) + (3 if skills else 0)
    readability_score = (
        6
        + (5 if len(text) >= 800 else 3 if len(text) >= 200 else 0)
        + min(6, len(detected_sections) * 2)
        + (3 if has_bullets else 0)
    )
    score = contact_score + section_score + impact_score + focus_score + readability_score

    recommendations: list[str] = []
    if not fields.get("target_role"):
        recommendations.append("add_target_role")
    if not fields.get("summary"):
        recommendations.append("add_summary")
    if not experience:
        recommendations.append("add_experience")
    elif quantified_bullets == 0:
        recommendations.append("quantify_achievements")
    if not fields.get("education"):
        recommendations.append("add_education_if_relevant")
    if not skills:
        recommendations.append("add_relevant_skills")
    elif len(skills) > 25:
        recommendations.append("prioritize_skills")
    if not email_present:
        recommendations.append("add_email")
    if not phone_present:
        recommendations.append("add_phone")
    if not detected_sections.intersection({"experience", "education", "skills", "summary"}):
        recommendations.append("use_clear_sections")
    if page_count and page_count > 2:
        recommendations.append("review_length")

    if score >= 80:
        grade = "strong"
    elif score >= 65:
        grade = "good"
    elif score >= 45:
        grade = "needs_improvement"
    else:
        grade = "weak"

    return {
        "score": max(0, min(100, score)),
        "grade": grade,
        "criteria": [
            {"id": "contact", "score": contact_score, "max_score": 10},
            {"id": "profile_sections", "score": section_score, "max_score": 30},
            {"id": "measurable_impact", "score": impact_score, "max_score": 25},
            {"id": "targeting", "score": focus_score, "max_score": 15},
            {"id": "readability", "score": readability_score, "max_score": 20},
        ],
        "recommendation_ids": recommendations,
        "signals": {
            "detected_sections": sorted(detected_sections),
            "experience_records": len(experience),
            "quantified_achievement_bullets": quantified_bullets,
            "skill_count": len(skills),
            "page_count": page_count,
        },
    }
