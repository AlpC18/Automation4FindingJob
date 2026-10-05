"""
Automated Personal Developer Portfolio Website Generator
Generates a standalone, single-page modern personal portfolio website:
- Styled with Tailwind CSS CDN & responsive dark mode
- Showcases Bio, Core Tech Stack, Key Projects, and Work Experience Timeline
- Exportable as a standalone HTML file ready for GitHub Pages or Vercel deployment
"""

from typing import Dict, Any, List, Optional
from pathlib import Path
from html import escape
from zipfile import ZipFile, ZIP_DEFLATED
from backend.app.core.config import settings
from backend.app.core.event_logger import agent_logger
from backend.app.core.tenant import tenant_data_path

def _portfolio_output_path():
    path = tenant_data_path("generated_portfolio.html")
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _portfolio_archive_path():
    path = tenant_data_path("portfolio-site.zip")
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


class PortfolioWebsiteGenerator:
    """Compiles candidate background into a responsive personal portfolio website."""

    def generate_html_portfolio(
        self,
        candidate_profile: Dict[str, Any],
        custom_headline: Optional[str] = None
    ) -> Dict[str, Any]:
        """Creates responsive single-page developer portfolio HTML string."""
        name = escape(str(candidate_profile.get("full_name") or "Candidate"))
        role = escape(str(candidate_profile.get("target_role") or "Target role"))
        headline = escape(custom_headline or candidate_profile.get("summary") or candidate_profile.get("raw_cv_text") or "Add a professional summary from the profile setup screen.")
        skills = [escape(str(skill)) for skill in candidate_profile.get("skills", [])]
        experience = candidate_profile.get("experience", [])
        
        # Build skills tags
        skills_html = "".join([
            f'<span class="px-3 py-1.5 bg-slate-800 text-slate-200 border border-slate-700 rounded-lg text-xs font-mono font-medium">{s}</span>'
            for s in skills
        ])

        # Build experience list
        exp_html = ""
        for exp in experience[:4]:
            if isinstance(exp, dict):
                title = escape(str(exp.get("title", "")))
                company = escape(str(exp.get("company", "")))
                period = escape(str(exp.get("period", "Past Experience")))
                achievements = "".join([
                    f'<li class="text-xs text-slate-400 mt-1">• {escape(str(a))}</li>'
                    for a in (exp.get("achievements") or exp.get("bullets", []))[:4]
                ])
                
                exp_html += f"""
                <div class="relative pl-6 pb-6 border-l border-slate-800 last:border-none">
                    <div class="absolute -left-1.5 top-0 w-3 h-3 rounded-full bg-blue-500"></div>
                    <div class="text-sm font-bold text-white">{title} <span class="text-blue-400">@ {company}</span></div>
                    <div class="text-[11px] text-slate-500 font-mono mb-2">{period}</div>
                    <ul class="space-y-1">{achievements}</ul>
                </div>
                """

        education_html = "".join(
            f'<div class="text-xs text-slate-300">{escape(str(item.get("degree", "")))} · {escape(str(item.get("school", "")))} · {escape(str(item.get("year", "")))}</div>'
            for item in candidate_profile.get("education", [])
            if isinstance(item, dict)
        )

        projects_html = ""
        for project in candidate_profile.get("projects", []):
            if not isinstance(project, dict):
                continue
            title = escape(str(project.get("title", "")))
            content = escape(str(project.get("content", "")))
            metrics = escape(str(project.get("metrics", "")))
            stack = escape(", ".join(str(item) for item in project.get("tech_stack", [])))
            projects_html += f'<article class="rounded-xl border border-slate-700 bg-slate-800 p-5 space-y-3"><h4 class="font-semibold">{title}</h4><p class="text-sm text-slate-300">{content}</p><p class="text-xs text-blue-400">{metrics}</p><p class="text-xs text-slate-400">{stack}</p></article>'

        html_template = f"""<!DOCTYPE html>
<html lang="en" class="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{name} | {role}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script>
        tailwind.config = {{
            darkMode: 'class',
            theme: {{
                extend: {{
                    colors: {{
                        slate: {{ 950: '#111111', 900: '#181818', 800: '#232323', 700: '#353535' }},
                        blue: {{ 400: '#c0d6a4', 500: '#8faa76', 600: '#526940' }}
                    }}
                }}
            }}
        }}
    </script>
</head>
<body class="bg-slate-950 text-slate-100 font-sans min-h-screen antialiased selection:bg-blue-500 selection:text-white">
    <div class="max-w-4xl mx-auto px-6 py-16 space-y-16">
        <!-- Hero Header -->
        <header class="space-y-4">
            <div class="inline-block px-3 py-1 bg-blue-500/10 border border-blue-500/20 text-blue-400 text-xs font-mono rounded-full">
                Open to opportunities
            </div>
            <h1 class="text-4xl md:text-5xl font-extrabold text-white tracking-tight">{name}</h1>
            <h2 class="text-xl md:text-2xl font-semibold text-slate-300">{role}</h2>
            <p class="text-slate-400 max-w-2xl text-base leading-relaxed">{headline}</p>
            <div class="flex gap-4 pt-2">
                <a href="#contact" class="px-5 py-2.5 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-xs font-bold transition-all shadow-lg shadow-blue-500/20">
                    Get in Touch
                </a>
                <a href="#experience" class="px-5 py-2.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-xl text-xs font-bold transition-all">
                    View Experience
                </a>
            </div>
        </header>

        <!-- Tech Stack -->
        <section class="space-y-4">
            <h3 class="text-sm font-bold uppercase tracking-wider text-slate-400">Core Technologies</h3>
            <div class="flex flex-wrap gap-2">
                {skills_html}
            </div>
        </section>

        <!-- Experience Timeline -->
        {f'<section id="projects" class="space-y-4"><h3 class="text-sm font-bold uppercase tracking-wider text-slate-400">Selected Projects</h3><div class="grid gap-4 sm:grid-cols-2">{projects_html}</div></section>' if projects_html else ''}

        <section id="experience" class="space-y-6">
            <h3 class="text-sm font-bold uppercase tracking-wider text-slate-400">Work Experience</h3>
            <div class="mt-4">
                {exp_html}
            </div>
        </section>

        {f'<section class="space-y-3"><h3 class="text-sm font-bold uppercase tracking-wider text-slate-400">Education</h3>{education_html}</section>' if education_html else ''}

        <!-- Contact CTA -->
        <footer id="contact" class="pt-8 border-t border-slate-900 text-center space-y-3">
            <div class="text-sm text-slate-300 font-semibold">Interested in working together?</div>
            <div class="text-xs text-slate-500">Contact: {escape(str(candidate_profile.get('email') or 'Add contact information'))}</div>
            <div class="text-[10px] text-slate-600">Generated automatically with Autonomous Career Agent Engine</div>
        </footer>
    </div>
</body>
</html>"""

        # Save to disk
        output_path = _portfolio_output_path()
        output_path.write_text(html_template, encoding="utf-8")
        agent_logger.log_event("PORTFOLIO_GEN", f"Generated personal portfolio site ({len(html_template)} bytes)")

        return {
            "file_path": str(output_path),
            "html_content": html_template,
            "size_bytes": len(html_template)
        }

    def generate_static_package(
        self,
        candidate_profile: Dict[str, Any],
        custom_headline: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a deployable archive for GitHub Pages or Vercel."""
        generated = self.generate_html_portfolio(candidate_profile, custom_headline)
        readme = (
            "# Portfolio site\n\n"
            "Upload `index.html` to GitHub Pages, or deploy this archive to Vercel.\n"
            "The page uses Tailwind's CDN runtime and needs no build step.\n"
        )
        vercel_config = '{"cleanUrls": true, "trailingSlash": false}\n'
        archive_path = _portfolio_archive_path()
        with ZipFile(archive_path, "w", compression=ZIP_DEFLATED) as archive:
            archive.writestr("index.html", generated["html_content"])
            archive.writestr("README.md", readme)
            archive.writestr("vercel.json", vercel_config)

        return {
            **generated,
            "archive_path": str(archive_path),
            "archive_size_bytes": archive_path.stat().st_size,
            "files": ["index.html", "README.md", "vercel.json"],
        }


portfolio_generator = PortfolioWebsiteGenerator()
