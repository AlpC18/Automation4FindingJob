"""
Format Cleaning Engine (ATS Standardizer)
Converts messy CVs (multi-column tables, Canva layouts, plain text)
into 100% selectable, standard ATS-compliant text with standardized headers and dates.
"""

import re
from typing import Dict, Any, List

STANDARD_SECTIONS = [
    "PROFESSIONAL SUMMARY",
    "CORE SKILLS & TECHNOLOGIES",
    "PROFESSIONAL EXPERIENCE",
    "KEY PROJECTS",
    "EDUCATION & CERTIFICATIONS"
]

def clean_raw_cv_text(raw_text: str) -> str:
    """
    Cleans unstructured CV text by removing unwanted glyphs, extra whitespace,
    and standardizing line breaks.
    """
    if not raw_text:
        return ""
    
    # Remove unicode bullets, icons and weird non-ascii artifacts
    text = re.sub(r'[\u2022\u2023\u25E6\u2043\u2219\u25AA\u25AB\u25CF\u2713\u2714\u25CB\u25C6]', '-', raw_text)
    text = re.sub(r'[^\x00-\x7F\u00C0-\u024F\u1E00-\u1EFF]', ' ', text)  # Keep Latin extended (Turkish/Albanian etc.)
    
    # Normalize multiple whitespace
    lines = [line.strip() for line in text.splitlines()]
    clean_lines = []
    prev_blank = False
    
    for line in lines:
        if not line:
            if not prev_blank:
                clean_lines.append("")
                prev_blank = True
        else:
            clean_lines.append(line)
            prev_blank = False
            
    return "\n".join(clean_lines)

def convert_to_ats_standard(cv_data: Dict[str, Any]) -> str:
    """
    Renders structured profile data into a 100% ATS-friendly clean format.
    Standard sections, clean dates, right-aligned formats and bullet points.
    """
    lines = []
    
    # Header
    name = cv_data.get("full_name", "CANDIDATE").upper()
    email = cv_data.get("email", "")
    phone = cv_data.get("phone", "")
    location = cv_data.get("location", "")
    contact_parts = [p for p in [email, phone, location] if p]
    
    lines.append(name)
    lines.append(" | ".join(contact_parts))
    lines.append("=" * 60)
    lines.append("")
    
    # Professional Summary
    summary = cv_data.get("summary") or cv_data.get("raw_cv_text", "")[:300]
    if summary:
        lines.append("PROFESSIONAL SUMMARY")
        lines.append("-" * 30)
        lines.append(summary.strip())
        lines.append("")
        
    # Skills
    skills = cv_data.get("skills", [])
    if skills:
        lines.append("CORE SKILLS & TECHNOLOGIES")
        lines.append("-" * 30)
        if isinstance(skills, list):
            lines.append(" • " + ", ".join(str(s) for s in skills))
        else:
            lines.append(str(skills))
        lines.append("")
        
    # Experience
    experiences = cv_data.get("experience", [])
    if experiences:
        lines.append("PROFESSIONAL EXPERIENCE")
        lines.append("-" * 30)
        for exp in experiences:
            title = exp.get("title", "Software Engineer")
            company = exp.get("company", "Company")
            period = exp.get("period", "2022 - Present")
            lines.append(f"{title.upper()} - {company.upper()}   [{period}]")
            for bullet in exp.get("bullets", []):
                lines.append(f"  - {bullet}")
            lines.append("")
            
    # Education
    education = cv_data.get("education", [])
    if education:
        lines.append("EDUCATION & CERTIFICATIONS")
        lines.append("-" * 30)
        for edu in education:
            degree = edu.get("degree", "Bachelor's Degree")
            school = edu.get("school", "University")
            year = edu.get("year", "2023")
            lines.append(f"{degree} - {school} ({year})")
        lines.append("")
        
    return "\n".join(lines)
