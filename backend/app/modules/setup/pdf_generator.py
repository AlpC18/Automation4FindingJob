"""
ATS-Compliant PDF Generator Engine
Uses ReportLab to build 100% ATS-scannable, single-column, cleanly structured PDFs
with standardized headers, right-aligned dates, and selectable text.
Supports XML-safe sanitization and color accents.
"""

import io
from datetime import datetime
from xml.sax.saxutils import escape as xml_escape
from typing import Dict, Any, List, Optional
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY

THEME_PALETTES = {
    "navy": {"heading": "#1e3a8a", "line": "#2563eb", "subtext": "#475569"},
    "charcoal": {"heading": "#0f172a", "line": "#334155", "subtext": "#475569"},
    "slate": {"heading": "#334155", "line": "#64748b", "subtext": "#475569"},
    "emerald": {"heading": "#065f46", "line": "#059669", "subtext": "#475569"}
}

def clean_xml(text: Any) -> str:
    """Safely escapes text for ReportLab's mini-XML parser."""
    if text is None:
        return ""
    s = str(text)
    return xml_escape(s).replace("'", "&apos;").replace('"', "&quot;")

class ATSPdfGenerator:
    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._init_custom_styles()

    def _init_custom_styles(self):
        self.styles.add(ParagraphStyle(
            name='CandidateName',
            fontName='Helvetica-Bold',
            fontSize=16,
            leading=20,
            alignment=TA_CENTER,
            textColor=colors.HexColor('#0f172a')
        ))
        self.styles.add(ParagraphStyle(
            name='ContactInfo',
            fontName='Helvetica',
            fontSize=9,
            leading=12,
            alignment=TA_CENTER,
            textColor=colors.HexColor('#475569')
        ))
        self.styles.add(ParagraphStyle(
            name='SectionHeading',
            fontName='Helvetica-Bold',
            fontSize=11,
            leading=14,
            textColor=colors.HexColor('#1e3a8a'),
            spaceBefore=8,
            spaceAfter=4
        ))
        self.styles.add(ParagraphStyle(
            name='ItemTitle',
            fontName='Helvetica-Bold',
            fontSize=10,
            leading=13,
            textColor=colors.HexColor('#1e293b')
        ))
        self.styles.add(ParagraphStyle(
            name='ItemDate',
            fontName='Helvetica-Oblique',
            fontSize=9,
            leading=13,
            alignment=TA_RIGHT,
            textColor=colors.HexColor('#64748b')
        ))
        self.styles.add(ParagraphStyle(
            name='BodyClean',
            fontName='Helvetica',
            fontSize=9.5,
            leading=13.5,
            textColor=colors.HexColor('#334155')
        ))
        self.styles.add(ParagraphStyle(
            name='BulletClean',
            fontName='Helvetica',
            fontSize=9,
            leading=13,
            leftIndent=12,
            textColor=colors.HexColor('#334155')
        ))
        self.styles.add(ParagraphStyle(
            name='CoverDate',
            fontName='Helvetica',
            fontSize=9.5,
            leading=13,
            alignment=TA_LEFT,
            textColor=colors.HexColor('#64748b'),
            spaceAfter=8
        ))

    def generate_cv_pdf(self, profile: Dict[str, Any], theme: str = "navy") -> io.BytesIO:
        palette = THEME_PALETTES.get(theme.lower(), THEME_PALETTES["navy"])
        heading_color = colors.HexColor(palette["heading"])
        line_color = colors.HexColor(palette["line"])

        # Dynamically adapt heading style color
        self.styles['SectionHeading'].textColor = heading_color

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=36,
            leftMargin=36,
            topMargin=36,
            bottomMargin=36
        )
        story = []

        # 1. Header (Candidate Name & Contact Details)
        name = clean_xml(profile.get("full_name") or "CANDIDATE").upper()
        story.append(Paragraph(name, self.styles['CandidateName']))
        story.append(Spacer(1, 3))

        contact_parts = [
            clean_xml(profile.get("email")),
            clean_xml(profile.get("phone")),
            clean_xml(profile.get("location")),
            clean_xml(profile.get("github_url"))
        ]
        contact_line = " | ".join([p for p in contact_parts if p])
        story.append(Paragraph(contact_line, self.styles['ContactInfo']))
        story.append(Spacer(1, 6))
        story.append(HRFlowable(width="100%", thickness=1, color=line_color, spaceBefore=2, spaceAfter=8))

        # 2. Professional Summary
        story.append(Paragraph("PROFESSIONAL SUMMARY", self.styles['SectionHeading']))
        summary = profile.get("summary") or profile.get("raw_cv_text") or "Add a professional summary in the profile setup screen."
        story.append(Paragraph(clean_xml(summary), self.styles['BodyClean']))
        story.append(Spacer(1, 6))

        # 3. Core Technical Skills
        story.append(Paragraph("CORE SKILLS & TECHNOLOGIES", self.styles['SectionHeading']))
        skills = profile.get("skills", [])
        # Plain separators: the bullet glyph comes out of the PDF text layer as a control character.
        skill_text = ", ".join(clean_xml(s) for s in skills)
        story.append(Paragraph(skill_text, self.styles['BodyClean']))
        story.append(Spacer(1, 6))

        # 4. Professional Experience
        story.append(Paragraph("PROFESSIONAL EXPERIENCE", self.styles['SectionHeading']))
        experiences = profile.get("experience", [])

        for exp in experiences:
            title_text = f"<b>{clean_xml(exp.get('title', 'Engineer'))}</b> — {clean_xml(exp.get('company', 'Company'))}"
            period_text = clean_xml(exp.get('period', '2022 - Present'))
            data = [
                [Paragraph(title_text, self.styles['ItemTitle']),
                 Paragraph(period_text, self.styles['ItemDate'])]
            ]
            t = Table(data, colWidths=[410, 130])
            t.setStyle(TableStyle([
                ('VALIGN', (0,0), (-1,-1), 'TOP'),
                ('BOTTOMPADDING', (0,0), (-1,-1), 2),
                ('TOPPADDING', (0,0), (-1,-1), 0),
                ('LEFTPADDING', (0,0), (-1,-1), 0),
                ('RIGHTPADDING', (0,0), (-1,-1), 0),
            ]))
            story.append(t)

            for bullet in exp.get("bullets", []):
                story.append(Paragraph(f"- {clean_xml(bullet)}", self.styles['BulletClean']))
            story.append(Spacer(1, 5))

        # 5. Key Engineering Projects / RAG Highlights
        projects = profile.get("projects", [])
        if projects:
            story.append(Paragraph("KEY ENGINEERING PROJECTS", self.styles['SectionHeading']))
            for proj in projects:
                proj_title = f"<b>{clean_xml(proj.get('title'))}</b> ({', '.join(clean_xml(s) for s in proj.get('tech_stack', []))})"
                proj_metric = clean_xml(proj.get('metric', ''))
                data = [
                    [Paragraph(proj_title, self.styles['ItemTitle']),
                     Paragraph(proj_metric, self.styles['ItemDate'])]
                ]
                t = Table(data, colWidths=[380, 160])
                t.setStyle(TableStyle([
                    ('VALIGN', (0,0), (-1,-1), 'TOP'),
                    ('BOTTOMPADDING', (0,0), (-1,-1), 2),
                    ('TOPPADDING', (0,0), (-1,-1), 0),
                    ('LEFTPADDING', (0,0), (-1,-1), 0),
                    ('RIGHTPADDING', (0,0), (-1,-1), 0),
                ]))
                story.append(t)
                story.append(Spacer(1, 4))

        # 6. Education & Certifications
        edu_list = profile.get("education", [])
        if edu_list:
            story.append(Paragraph("EDUCATION & CERTIFICATIONS", self.styles['SectionHeading']))
        for edu in edu_list:
            edu_title = f"<b>{clean_xml(edu.get('degree'))}</b> — {clean_xml(edu.get('school'))}"
            edu_year = clean_xml(str(edu.get('year', '2021')))
            data = [
                [Paragraph(edu_title, self.styles['ItemTitle']),
                 Paragraph(edu_year, self.styles['ItemDate'])]
            ]
            t = Table(data, colWidths=[410, 130])
            t.setStyle(TableStyle([
                ('VALIGN', (0,0), (-1,-1), 'TOP'),
                ('BOTTOMPADDING', (0,0), (-1,-1), 2),
                ('TOPPADDING', (0,0), (-1,-1), 0),
                ('LEFTPADDING', (0,0), (-1,-1), 0),
                ('RIGHTPADDING', (0,0), (-1,-1), 0),
            ]))
            story.append(t)

        doc.build(story)
        buffer.seek(0)
        return buffer

    def generate_cover_letter_pdf(
        self,
        job_title: str,
        company: str,
        cover_letter_text: str,
        candidate_name: str,
        theme: str = "navy"
    ) -> io.BytesIO:
        palette = THEME_PALETTES.get(theme.lower(), THEME_PALETTES["navy"])
        line_color = colors.HexColor(palette["line"])

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=45,
            leftMargin=45,
            topMargin=45,
            bottomMargin=45
        )
        story = []

        # 1. Candidate Header
        c_name = clean_xml(candidate_name).upper()
        story.append(Paragraph(c_name, self.styles['CandidateName']))
        story.append(Spacer(1, 3))
        story.append(Paragraph(f"Application for {clean_xml(job_title)} @ {clean_xml(company)}", self.styles['ContactInfo']))
        story.append(Spacer(1, 4))
        story.append(HRFlowable(width="100%", thickness=1, color=line_color, spaceBefore=4, spaceAfter=14))

        # 2. Date
        today_str = datetime.now().strftime("%B %d, %Y")
        story.append(Paragraph(today_str, self.styles['CoverDate']))
        story.append(Spacer(1, 8))

        # 3. Addressee Block
        addressee_text = f"<b>Hiring Team</b><br/>{clean_xml(company)}"
        story.append(Paragraph(addressee_text, self.styles['BodyClean']))
        story.append(Spacer(1, 14))

        # 4. Body Paragraphs
        paragraphs = cover_letter_text.split("\n\n")
        for p in paragraphs:
            clean_p = p.replace("\n", " ").strip()
            if clean_p:
                story.append(Paragraph(clean_xml(clean_p), self.styles['BodyClean']))
                story.append(Spacer(1, 9))

        # 5. Signoff
        story.append(Spacer(1, 10))
        signoff = f"Sincerely,<br/><br/><b>{clean_xml(candidate_name)}</b>"
        story.append(Paragraph(signoff, self.styles['BodyClean']))

        doc.build(story)
        buffer.seek(0)
        return buffer

ats_pdf_generator = ATSPdfGenerator()
