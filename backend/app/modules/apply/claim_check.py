"""Check a drafted letter against the candidate's own CV and saved projects.

A language model writes fluent letters and now and then adds a detail nobody gave it.
This is a plain text comparison, not a judgement: it reports sentences whose technologies
or figures cannot be found where the letter says they belong, so the candidate reads those
sentences before sending. It cannot see an invented action described in known words.
"""

import re
import unicodedata
from datetime import date
from typing import Any, Dict, List

# A token shaped like a technology or product name: CamelCase (FastAPI), dotted (Node.js),
# C++/C#, an acronym with optional parts (AES-256-GCM), or letters with digits (HTML5).
_TECH_TOKEN = re.compile(
    r"\b[A-Z][a-z0-9]+(?:[A-Z][A-Za-z0-9]*)+\b"
    r"|\b[A-Za-z]+(?:\.[A-Za-z][A-Za-z0-9]*)+\b"
    r"|\b[A-Za-z](?:\+\+|#)"
    r"|\b[A-Z]{2,}[a-z0-9]*(?:[-\u2011][A-Z0-9]+)*\b"
    r"|\b[A-Za-z]+\d+[A-Za-z0-9]*\b"
)
# Common technologies written as ordinary capitalised words, which the shapes above cannot tell from names.
_COMMON_TECH = (
    "Python Java Rust Go Golang Ruby Rails Scala Kotlin Swift Dart Flutter Elixir Perl Haskell Bash Linux Git Docker Kubernetes "
    "Terraform Ansible Jenkins Kafka Redis Celery RabbitMQ Nginx Apache Oracle Cassandra Elasticsearch Grafana Prometheus Splunk "
    "Selenium Cypress Jest Pytest Playwright Webpack Vite Laravel Symfony Spring Hibernate Angular React Vue Svelte Next Nuxt "
    "Express Nest Fastify Prisma Supabase Firebase Heroku Vercel Netlify Azure Snowflake Tableau Spark Hadoop Airflow Pandas "
    "Keras Django Flask Unity Figma Jira Stripe Twilio Claude Gemini Tailwind Bootstrap Redux Electron Remotion Postman"
).split()
_FIGURE = re.compile(r"\b\d+(?:[.,]\d+)?\s?(?:%|x\b|k\b|\+)|\b\d{2,}\b")
_CONTACT = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+|(?:https?://|www\.)\S+|\b[\w-]+\.com/\S*|\+?\d[\d\s()./\u2011-]{7,}\d")
# Other spellings under which a project may list the same technology.
_ALIASES = {"javascript": ("JS",), "typescript": ("TS",), "node.js": ("Node", "NodeJS"), "postgresql": ("Postgres",), "rest apis": ("REST", "API")}
# Words that match the token shape but name no technology.
_ORDINARY = {"I", "CV", "IT", "HR", "API", "APIs", "REST", "AI", "UI", "UX", "B2B", "SaaS", "CRM", "PDF", "USA", "UK", "EU", "CEO", "CTO"}


def _norm(text: str) -> str:
    """Lowercase letters and digits only, so "AES‑256‑GCM", "aes-256-gcm" and "Node.js"/"NodeJS" compare equal."""
    folded = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "", folded.lower())


def _mentions(text: str, term: str) -> bool:
    """Whole-word, case-insensitive: "Java" is not found inside "JavaScript"."""
    return re.search(rf"(?<![A-Za-z0-9]){re.escape(term)}(?![A-Za-z0-9])", text, re.IGNORECASE) is not None


def _project_names(project: Dict[str, Any]) -> List[str]:
    return [name.strip() for name in str(project.get("title") or "").split("/") if len(name.strip()) > 2]


def _project_text(project: Dict[str, Any]) -> str:
    return " ".join([str(project.get("title") or ""), " ".join(project.get("tech_stack") or []),
                     str(project.get("content") or ""), str(project.get("metrics") or "")])


def _education_words(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").lower().replace("ı", "i"))
    return "".join(char for char in text if not unicodedata.combining(char))


def _degree_level(text: str) -> str:
    for level, pattern in (
        ("school", r"high school|secondary school|lise"),
        ("doctorate", r"doctorate|doctoral|ph\.?d|doktora"),
        ("master", r"master|yuksek lisans"),
        ("bachelor", r"bachelor|undergraduate|\blisans\b"),
    ):
        if re.search(pattern, text):
            return level
    return ""


def ongoing_education(profile: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Only explicit ongoing status or a future study end date establishes ongoing study."""
    entries = profile.get("education") or []
    if not isinstance(entries, list):
        return []
    ongoing = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        status = _education_words(entry.get("status"))
        if status in {"completed", "graduated", "mezun", "tamamlandi"}:
            continue
        text = _education_words(" ".join(str(entry.get(key) or "") for key in ("degree", "year", "end_date", "status")))
        years = [int(year) for year in re.findall(r"\b(?:19|20)\d{2}\b", text)]
        if re.search(r"\b(current|present|ongoing|pursuing|enrolled|student|in progress|devam|ogrenci)\b", text) or (years and max(years) > date.today().year):
            ongoing.append(entry)
    return ongoing


def _education_claim_reason(sentence: str, profile: Dict[str, Any]) -> str:
    text = _education_words(sentence)
    # Only completed-degree assertions, not requirements, future plans or negations.
    if re.search(r"\b(not|never|haven't|have not|henuz|degilim)\b|mezun olmad|will graduate|expect(?:ed)? to graduate", text):
        return ""
    graduate = re.search(r"\b(?:i (?:am|have|graduated)|as (?:a|an)|being (?:a|an))\b.{0,90}\bgraduat(?:e|ed)\b|\bi graduated\b|mezunuyum|mezun oldum", text)
    possession = re.search(r"\b(?:with (?:a|an)|i (?:hold|earned|completed|have|obtained|received)(?: (?:a|an))?)\s+(?:[\w’'& -]{0,65})(?:bachelor|master|doctorate|degree)\b|lisans diplomam", text)
    if not graduate and not possession:
        return ""
    ongoing = ongoing_education(profile)
    level = _degree_level(text)
    if ongoing:
        levels = {_degree_level(_education_words(entry.get("degree"))) for entry in ongoing}
        completed_levels = {_degree_level(_education_words(entry.get("degree"))) for entry in profile.get("education", [])
                            if isinstance(entry, dict) and entry not in ongoing}
        # A completed bachelor's degree can coexist with a current master's degree.
        if level and level not in levels:
            return ""
        if level and level in completed_levels:
            return ""
        if not level and completed_levels - {"", "school"}:
            return ""
    else:
        cv = _education_words(profile.get("raw_cv_text"))
        if not re.search(r"(?:currently|current).{0,65}\bstudent\b|\b(?:universite|lisans) ogrencisi", cv):
            return ""
        if level == "school":
            return ""
    return "graduation or a completed degree is claimed, but your profile records ongoing studies; describe yourself as a current student"


def find_unsupported_claims(letter: str, profile: Dict[str, Any], projects: List[Dict[str, Any]], job: Dict[str, Any]) -> List[Dict[str, str]]:
    """Sentences to re-read, each with the reason. An empty list means nothing was found, not that all is true."""
    skills = [str(skill) for skill in profile.get("skills") or []]
    stacks = [str(tech) for project in projects for tech in project.get("tech_stack") or []]
    known_tech = sorted({tech for tech in [*skills, *stacks] if len(tech) > 1}, key=len, reverse=True)
    own_text = " ".join([str(profile.get("raw_cv_text") or ""), " ".join(skills), *(_project_text(project) for project in projects)])
    own, job_text = _norm(own_text), _norm(" ".join(str(job.get(key) or "") for key in ("title", "company", "description")))

    # The posting's own title and company may always be named.
    posting_names = _norm(" ".join(str(job.get(key) or "") for key in ("title", "company")))
    cv_text = str(profile.get("raw_cv_text") or "")

    claims: List[Dict[str, str]] = []
    for paragraph in re.split(r"\n\s*\n", letter or ""):
        subject: List[Dict[str, Any]] = []  # the project(s) the current run of sentences is about
        for sentence in re.split(r"(?<=[.!?])\s+|\n", paragraph.strip()):
            if not sentence.strip():
                continue
            named = [project for project in projects if any(_mentions(sentence, name) for name in _project_names(project))]
            if named:
                subject = named
            elif re.match(r"\s*[-*•]", sentence):
                subject = []  # a new list item is a new topic
            reasons = []
            education_reason = _education_claim_reason(sentence, profile)
            if education_reason:
                reasons.append(education_reason)
            first_person = re.search(r"\b(I|my|we|our)\b", sentence) is not None
            if subject:
                allowed_text = " ".join(_project_text(project) for project in subject)
                project_label = ", ".join(_project_names(project)[0] for project in subject)
                for tech in known_tech:
                    in_project = _norm(tech) in _norm(allowed_text) or any(_mentions(allowed_text, alias) for alias in _ALIASES.get(tech.lower(), ()))
                    if _mentions(sentence, tech) and not in_project:
                        reasons.append(f"{tech} is not part of {project_label} in your saved projects")
            shaped = [match.group(0) for match in _TECH_TOKEN.finditer(sentence)]
            common = [tech for tech in _COMMON_TECH if re.search(rf"(?<![A-Za-z0-9.]){tech}(?![A-Za-z0-9])", sentence)]
            for token in dict.fromkeys([*shaped, *common]):
                key = _norm(token)
                # "RESTful" for REST and "LLMs" for LLM are the same term on the CV.
                variants = {key, key.removesuffix("s"), key.removesuffix("ful")}
                if token in _ORDINARY or len(key) < 2 or key in posting_names or any(len(v) > 1 and v in own for v in variants) \
                        or any(_norm(tech) in variants for tech in known_tech):
                    continue
                if key in job_text and not first_person:
                    continue  # naming something from the posting is fine; claiming it as experience is not
                where = "appears only in the job posting, not in your CV" if key in job_text else "is not in your CV or saved projects"
                reasons.append(f"{token} {where}")
            for contact in dict.fromkeys(match.group(0) for match in _CONTACT.finditer(sentence)):
                if _norm(contact) not in _norm(cv_text):
                    reasons.append(f"the contact detail {contact.strip()} is not on your CV")
            if not any("contact detail" in reason for reason in reasons):
                for figure in dict.fromkeys(match.group(0).strip() for match in _FIGURE.finditer(sentence)):
                    if _norm(figure) and _norm(figure) not in own and _norm(figure) not in job_text:
                        reasons.append(f"the figure {figure} is not in your CV or saved projects")
            if reasons:
                claims.append({"sentence": sentence.strip(), "reason": "; ".join(dict.fromkeys(reasons))})
    return claims
