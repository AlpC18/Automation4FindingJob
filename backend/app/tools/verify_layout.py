"""
PDF Layout Verification Tool — Orphan, Hole, Footer Collision Detector
Adapted from MadsLorentzen/ai-job-search verify_layout.py

Detects common LaTeX layout failures that pass page-count checks:
- Orphaned entries (header on one page, bullets on next)
- Internal holes (large blank spaces mid-page from ejected entries)
- Pages ending too early
- Final page mostly empty
- Footer collisions (body text pushed into page-number band)

Requires poppler-utils (pdftotext -bbox) for word bounding boxes.
"""

import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

# Layout thresholds (points)
FOOTER_BAND_PT = 50.0       # Bottom band reserved for page numbers
GAP_THRESHOLD_PT = 100.0    # Largest acceptable gap between body lines
EARLY_END_PT = 180.0        # Minimum bottom space for a non-final page to flag
THIN_PAGE_RATIO = 0.40      # Final page flagged if body uses less than this fraction
HEADING_HEIGHT_RATIO = 1.3   # A line taller than median × this is a heading
INDENT_PT = 20.0            # Indentation threshold for bullet detection

PAGE_RE = re.compile(r'<page width="[\d.]+" height="([\d.]+)">(.*?)</page>', re.S)
WORD_RE = re.compile(
    r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="[\d.]+" yMax="([\d.]+)">([^<]*)</word>'
)


@dataclass
class Line:
    top: float
    bottom: float
    left: float
    height: float
    text: str


class Page:
    def __init__(self, height: float, lines: list):
        self.height = height
        self.lines = sorted(lines, key=lambda l: l.top)

    @property
    def body(self) -> list:
        cutoff = self.height - FOOTER_BAND_PT
        return [l for l in self.lines if l.top < cutoff]

    @property
    def empty(self) -> bool:
        return not self.body

    @property
    def bottom_space(self) -> float:
        return self.height - max(l.bottom for l in self.body) if self.body else self.height

    @property
    def left_edge(self) -> float:
        return min(l.left for l in self.body) if self.body else 0.0

    @property
    def body_median_height(self) -> float:
        heights = sorted(l.height for l in self.body)
        return heights[len(heights) // 2] if heights else 0.0

    @property
    def footer_crowded(self) -> bool:
        """One line in the bottom band is a page number; two means body text spilled in."""
        band = self.height - FOOTER_BAND_PT
        return len({round(l.top, 1) for l in self.lines if l.top >= band}) > 1

    def is_indented(self, line: Line) -> bool:
        return line.left > self.left_edge + INDENT_PT

    def is_heading(self, line: Line) -> bool:
        median = self.body_median_height
        return bool(median) and line.height > median * HEADING_HEIGHT_RATIO

    def largest_gap(self) -> Tuple[float, float]:
        """Largest top-to-top distance between body lines, and where it starts."""
        body = self.body
        if len(body) < 2:
            return 0.0, 0.0
        max_gap, max_pos = 0.0, 0.0
        for i in range(1, len(body)):
            gap = body[i].top - body[i - 1].top
            if gap > max_gap:
                max_gap = gap
                max_pos = body[i - 1].top
        return max_gap, max_pos


def parse_bbox_xml(xml_text: str) -> List[Page]:
    """Parse pdftotext -bbox XML output into Page objects."""
    pages = []
    for page_match in PAGE_RE.finditer(xml_text):
        height = float(page_match.group(1))
        content = page_match.group(2)

        # Group words into lines by y-coordinate proximity
        words = []
        for word_match in WORD_RE.finditer(content):
            left = float(word_match.group(1))
            top = float(word_match.group(2))
            bottom = float(word_match.group(3))
            text = word_match.group(4)
            words.append((left, top, bottom, text))

        # Cluster words into lines (same y-position ± tolerance)
        lines = []
        if words:
            words.sort(key=lambda w: (w[1], w[0]))
            current_line_words = [words[0]]
            for w in words[1:]:
                if abs(w[1] - current_line_words[0][1]) < 3.0:  # Same line
                    current_line_words.append(w)
                else:
                    top = min(cw[1] for cw in current_line_words)
                    bottom = max(cw[2] for cw in current_line_words)
                    left = min(cw[0] for cw in current_line_words)
                    text = " ".join(cw[3] for cw in current_line_words)
                    lines.append(Line(top=top, bottom=bottom, left=left, height=bottom - top, text=text))
                    current_line_words = [w]
            # Last line
            top = min(cw[1] for cw in current_line_words)
            bottom = max(cw[2] for cw in current_line_words)
            left = min(cw[0] for cw in current_line_words)
            text = " ".join(cw[3] for cw in current_line_words)
            lines.append(Line(top=top, bottom=bottom, left=left, height=bottom - top, text=text))

        pages.append(Page(height, lines))
    return pages


def get_bbox_xml(pdf_path: Path) -> str:
    """Extract bounding box XML from PDF using pdftotext -bbox."""
    try:
        result = subprocess.run(
            ["pdftotext", "-bbox", str(pdf_path), "-"],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        return result.stdout
    except FileNotFoundError:
        raise RuntimeError(
            "pdftotext not found. Install poppler-utils: "
            "macOS: brew install poppler, Ubuntu: apt install poppler-utils"
        )
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"pdftotext failed: {exc.stderr}")


@dataclass
class LayoutIssue:
    page: int
    severity: str  # "error" or "warning"
    issue_type: str
    description: str


def verify_layout(pdf_path: Path) -> List[LayoutIssue]:
    """
    Verify a PDF's page layout for common issues.
    Returns list of LayoutIssue objects (empty = clean layout).
    """
    issues = []

    try:
        xml = get_bbox_xml(pdf_path)
    except RuntimeError as e:
        return [LayoutIssue(
            page=0, severity="warning", issue_type="extractor_missing",
            description=str(e)
        )]

    pages = parse_bbox_xml(xml)
    if not pages:
        return [LayoutIssue(
            page=0, severity="error", issue_type="no_pages",
            description="No pages found in PDF"
        )]

    for i, page in enumerate(pages, 1):
        if page.empty:
            issues.append(LayoutIssue(
                page=i, severity="error", issue_type="empty_page",
                description=f"Page {i} has no body content"
            ))
            continue

        # Check for internal holes (large gaps)
        gap_size, gap_pos = page.largest_gap()
        if gap_size > GAP_THRESHOLD_PT:
            issues.append(LayoutIssue(
                page=i, severity="error", issue_type="internal_hole",
                description=f"Page {i}: {gap_size:.0f}pt gap at y={gap_pos:.0f} "
                           f"(threshold: {GAP_THRESHOLD_PT}pt). Entry may have been ejected."
            ))

        # Check for orphaned headings (heading at bottom with no following content)
        body = page.body
        if body and page.is_heading(body[-1]) and not page.is_indented(body[-1]):
            if i < len(pages):  # Not the last page
                next_body = pages[i].body  # 0-indexed: pages[i] is page i+1
                if next_body and page.is_indented(next_body[0]):
                    issues.append(LayoutIssue(
                        page=i, severity="error", issue_type="orphaned_entry",
                        description=f"Page {i}: Heading '{body[-1].text[:50]}...' at bottom "
                                   f"with bullets continuing on page {i+1}"
                    ))

        # Check for page ending too early (non-final page)
        if i < len(pages) and page.bottom_space > EARLY_END_PT:
            issues.append(LayoutIssue(
                page=i, severity="warning", issue_type="page_ends_early",
                description=f"Page {i}: {page.bottom_space:.0f}pt unused at bottom"
            ))

        # Check for footer collision
        if page.footer_crowded:
            issues.append(LayoutIssue(
                page=i, severity="warning", issue_type="footer_collision",
                description=f"Page {i}: Body text encroaches on footer band"
            ))

    # Check final page thinness
    if len(pages) > 1:
        last = pages[-1]
        if not last.empty:
            used_ratio = (max(l.bottom for l in last.body) - min(l.top for l in last.body)) / last.height
            if used_ratio < THIN_PAGE_RATIO:
                issues.append(LayoutIssue(
                    page=len(pages), severity="warning", issue_type="thin_final_page",
                    description=f"Final page uses only {used_ratio:.0%} of page height"
                ))

    return issues


def verify_layout_dict(pdf_path: str) -> dict:
    """API-friendly wrapper returning a dict."""
    issues = verify_layout(Path(pdf_path))
    return {
        "status": "clean" if not issues else "issues_found",
        "issue_count": len(issues),
        "errors": [
            {"page": i.page, "type": i.issue_type, "description": i.description}
            for i in issues if i.severity == "error"
        ],
        "warnings": [
            {"page": i.page, "type": i.issue_type, "description": i.description}
            for i in issues if i.severity == "warning"
        ],
    }


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python verify_layout.py <pdf_path>", file=sys.stderr)
        sys.exit(2)

    path = Path(sys.argv[1])
    issues = verify_layout(path)
    if not issues:
        print(f"✅ {path}: Layout clean")
    else:
        for issue in issues:
            icon = "❌" if issue.severity == "error" else "⚠️"
            print(f"{icon} {issue.description}")
        sys.exit(1 if any(i.severity == "error" for i in issues) else 0)
