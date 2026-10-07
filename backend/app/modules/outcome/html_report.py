"""
HTML Report Generator
Adapted from MadsLorentzen/ai-job-search html-report command.

Generates standalone, self-contained HTML reports for:
- Job search summary (all tracked jobs, scores, statuses)
- Application pipeline progress
- Skill gap analysis overview
- Interview preparation status

Reports are fully offline-viewable single HTML files with embedded CSS.
"""

import json
from html import escape
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

from backend.app.core.config import settings
from backend.app.core.event_logger import agent_logger
from backend.app.core.tenant import tenant_data_path

def _text(value: Any) -> str:
    """Scraped and typed-in text is shown as text, never as markup."""
    return escape(str(value)) if value not in (None, "") else "—"


def _link(url: Any) -> str:
    """Only web links are clickable; a `javascript:` URL from a listing must not be."""
    url = str(url or "")
    return escape(url, quote=True) if url.lower().startswith(("http://", "https://")) else "#"


def _reports_dir():
    path = tenant_data_path("reports")
    path.mkdir(exist_ok=True, parents=True)
    return path


class HTMLReportGenerator:
    """Generates self-contained HTML reports."""

    def generate_job_search_report(
        self,
        jobs: List[Dict[str, Any]],
        stats: Dict[str, Any],
        title: str = "İş Arama Raporu",
    ) -> Dict[str, Any]:
        """
        Generate a comprehensive job search HTML report.
        """
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
        filename = f"job_search_report_{timestamp}.html"
        filepath = _reports_dir() / filename

        # Sort jobs by score
        sorted_jobs = sorted(jobs, key=lambda j: j.get("match_score", j.get("score", 0)), reverse=True)

        # Count by status
        status_counts = {}
        for j in jobs:
            s = j.get("status", "unknown")
            status_counts[s] = status_counts.get(s, 0) + 1

        html = self._build_html(
            title=title,
            timestamp=datetime.now().strftime("%d %B %Y, %H:%M"),
            sections=[
                self._stats_section(stats, status_counts, len(jobs)),
                self._jobs_table_section(sorted_jobs),
            ]
        )

        filepath.write_text(html, encoding="utf-8")
        agent_logger.log_event("HTML_REPORT", f"Report generated: {filepath}")

        return {
            "report_path": str(filepath),
            "filename": filename,
            "total_jobs": len(jobs),
            "generated_at": datetime.now().isoformat(),
        }

    def generate_pipeline_report(
        self,
        applications: List[Dict[str, Any]],
        title: str = "Başvuru Pipeline Raporu",
    ) -> Dict[str, Any]:
        """Generate an application pipeline progress report."""
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
        filename = f"pipeline_report_{timestamp}.html"
        filepath = _reports_dir() / filename

        stages = {"drafted": 0, "applied": 0, "interview": 0, "offer": 0, "hired": 0, "rejected": 0, "no_response": 0}
        for app in applications:
            status = app.get("status", "unknown")
            if status in stages:
                stages[status] += 1

        html = self._build_html(
            title=title,
            timestamp=datetime.now().strftime("%d %B %Y, %H:%M"),
            sections=[
                self._pipeline_funnel_section(stages),
                self._applications_table_section(applications),
            ]
        )

        filepath.write_text(html, encoding="utf-8")
        return {"report_path": str(filepath), "filename": filename}

    def _build_html(self, title: str, timestamp: str, sections: List[str]) -> str:
        """Build a complete HTML document."""
        sections_html = "\n".join(sections)
        return f"""<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<style>
:root {{ --primary: #2563eb; --success: #16a34a; --warning: #f59e0b; --danger: #dc2626; --bg: #f8fafc; --card: #ffffff; --text: #1e293b; --muted: #64748b; }}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif; background: var(--bg); color: var(--text); line-height: 1.6; padding: 2rem; }}
.container {{ max-width: 1200px; margin: 0 auto; }}
h1 {{ font-size: 1.8rem; margin-bottom: 0.5rem; color: var(--primary); }}
.timestamp {{ color: var(--muted); margin-bottom: 2rem; font-size: 0.9rem; }}
.card {{ background: var(--card); border-radius: 12px; padding: 1.5rem; margin-bottom: 1.5rem; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
.card h2 {{ font-size: 1.2rem; margin-bottom: 1rem; color: var(--text); }}
.stat-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 1rem; }}
.stat {{ text-align: center; padding: 1rem; border-radius: 8px; background: var(--bg); }}
.stat .value {{ font-size: 2rem; font-weight: 700; color: var(--primary); }}
.stat .label {{ font-size: 0.85rem; color: var(--muted); }}
table {{ width: 100%; border-collapse: collapse; font-size: 0.9rem; }}
th {{ background: var(--bg); padding: 0.75rem; text-align: left; font-weight: 600; border-bottom: 2px solid #e2e8f0; }}
td {{ padding: 0.75rem; border-bottom: 1px solid #e2e8f0; }}
tr:hover {{ background: #f1f5f9; }}
.badge {{ display: inline-block; padding: 0.2rem 0.6rem; border-radius: 9999px; font-size: 0.75rem; font-weight: 600; }}
.badge-high {{ background: #dcfce7; color: #166534; }}
.badge-mid {{ background: #fef3c7; color: #92400e; }}
.badge-low {{ background: #fecaca; color: #991b1b; }}
.badge-new {{ background: #dbeafe; color: #1e40af; }}
.funnel {{ display: flex; justify-content: center; gap: 0.5rem; align-items: end; margin: 1rem 0; }}
.funnel-bar {{ background: var(--primary); border-radius: 4px 4px 0 0; min-width: 60px; text-align: center; color: white; font-weight: 700; padding: 0.5rem 0.3rem; font-size: 0.85rem; }}
.funnel-label {{ font-size: 0.75rem; color: var(--muted); text-align: center; }}
a {{ color: var(--primary); text-decoration: none; }}
a:hover {{ text-decoration: underline; }}
@media (max-width: 768px) {{ body {{ padding: 1rem; }} .stat-grid {{ grid-template-columns: 1fr 1fr; }} }}
</style>
</head>
<body>
<div class="container">
<h1>📊 {title}</h1>
<p class="timestamp">Oluşturulma: {timestamp} | Otonom İş Bulma Sistemi</p>
{sections_html}
</div>
</body>
</html>"""

    def _stats_section(self, stats: Dict, status_counts: Dict, total: int) -> str:
        stats_cards = ""
        for label, value in [("Toplam İlan", total), ("Yeni", status_counts.get("new", 0)),
                              ("Değerlendirilen", status_counts.get("ranked", 0)),
                              ("Başvurulan", status_counts.get("applied", 0)),
                              ("Süresi Geçen", status_counts.get("expired", 0))]:
            stats_cards += f'<div class="stat"><div class="value">{value}</div><div class="label">{label}</div></div>'
        return f'<div class="card"><h2>Özet İstatistikler</h2><div class="stat-grid">{stats_cards}</div></div>'

    def _jobs_table_section(self, jobs: List[Dict]) -> str:
        rows = ""
        for j in jobs[:100]:
            score = j.get("match_score", j.get("score", 0))
            badge_class = "badge-high" if score >= 75 else "badge-mid" if score >= 50 else "badge-low"
            status = j.get("status", "new")
            rows += f"""<tr>
<td><a href="{_link(j.get("url"))}" target="_blank" rel="noopener noreferrer">{_text(j.get("title"))}</a></td>
<td>{_text(j.get("company"))}</td>
<td>{_text(j.get("location"))}</td>
<td><span class="badge {badge_class}">{score:.0f}</span></td>
<td><span class="badge badge-new">{_text(status)}</span></td>
<td>{_text(j.get("deadline"))}</td>
</tr>"""

        return f"""<div class="card"><h2>İş İlanları ({len(jobs)})</h2>
<table><thead><tr><th>Pozisyon</th><th>Şirket</th><th>Lokasyon</th><th>Skor</th><th>Durum</th><th>Son Tarih</th></tr></thead>
<tbody>{rows}</tbody></table></div>"""

    def _pipeline_funnel_section(self, stages: Dict) -> str:
        max_val = max(stages.values()) if stages.values() else 1
        bars = ""
        for label, count in stages.items():
            height = max(20, int(count / max(max_val, 1) * 150))
            bars += f'<div><div class="funnel-bar" style="height:{height}px">{count}</div><div class="funnel-label">{label}</div></div>'
        return f'<div class="card"><h2>Başvuru Hunisi</h2><div class="funnel">{bars}</div></div>'

    def _applications_table_section(self, apps: List[Dict]) -> str:
        rows = ""
        for a in apps[:50]:
            rows += f"""<tr><td>{_text(a.get("company"))}</td><td>{_text(a.get("role", a.get("title")))}</td>
<td>{_text(a.get("status"))}</td><td>{_text(a.get("date"))}</td><td>{_text(a.get("notes"))}</td></tr>"""
        return f"""<div class="card"><h2>Başvurular</h2>
<table><thead><tr><th>Şirket</th><th>Pozisyon</th><th>Durum</th><th>Tarih</th><th>Not</th></tr></thead>
<tbody>{rows}</tbody></table></div>"""


# Module-level singleton
html_report_generator = HTMLReportGenerator()
