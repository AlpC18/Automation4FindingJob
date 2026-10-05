"""
Canonical Job Dedup Key Generator & Audit Tool
Adapted from MadsLorentzen/ai-job-search job_key.py

Generates deterministic, collision-free dedup keys for job postings.
Solves two real-world problems:
1. Keys with characters that break downstream (/, commas in company names)
2. Same job stored twice because of inconsistent title truncation

Algorithm:
- Slugify company + title to ASCII lowercase
- Length-cap with SHA1 hash suffix for deterministic truncation
- Fall back to portal numeric ID for non-Latin scripts

Usage:
    from backend.app.tools.job_key import make_job_key, audit_keys
    key = make_job_key(company="Acme Corp", title="Senior Engineer (L2)")
"""

import hashlib
import re
import unicodedata
from typing import Optional, List, Dict, Any

COMPANY_MAX = 30
TITLE_MAX = 50
HASH_LEN = 8

_NON_SLUG = re.compile(r"[^a-z0-9]+")
_JOB_ID = re.compile(r"(\d{6,})")


def slugify(text: str) -> str:
    """Lowercase ASCII slug. Non-Latin scripts legitimately reduce to ''."""
    if not text:
        return ""
    decomposed = unicodedata.normalize("NFKD", str(text))
    ascii_only = decomposed.encode("ascii", "ignore").decode("ascii")
    return _NON_SLUG.sub("-", ascii_only.lower()).strip("-")


def _cap(slug: str, limit: int) -> str:
    """Cap length without making truncation lossy across runs.

    Appending a hash of the full slug makes the result deterministic
    for a given title and distinct for any other.
    """
    if len(slug) <= limit:
        return slug
    digest = hashlib.sha1(slug.encode("utf-8")).hexdigest()[:HASH_LEN]
    return f"{slug[:limit].rstrip('-')}-{digest}"


def make_job_key(company: str, title: str, url: str = "") -> str:
    """
    The canonical dedup key for one job posting.

    Returns a deterministic string like 'acme-corp_senior-engineer-l2'.
    """
    company_slug = _cap(slugify(company), COMPANY_MAX)
    if not company_slug:
        name = unicodedata.normalize("NFC", str(company or "").strip().casefold())
        digest = hashlib.sha1(name.encode("utf-8")).hexdigest()[:HASH_LEN]
        company_slug = f"company-{digest}" if name else "unknown-company"

    title_slug = _cap(slugify(title), TITLE_MAX)
    if not title_slug:
        # No Latin characters in the title — use portal's numeric ID
        match = _JOB_ID.search(url or "")
        if match:
            title_slug = match.group(1)
        else:
            name = unicodedata.normalize("NFC", str(title or "").strip().casefold())
            digest = hashlib.sha1(name.encode("utf-8")).hexdigest()[:HASH_LEN]
            title_slug = f"title-{digest}" if name else "unknown-title"

    return f"{company_slug}_{title_slug}"


def audit_keys(jobs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Audit a list of jobs for key collisions and problematic characters.

    Args:
        jobs: list of dicts with 'company', 'title', and optionally 'url', 'id' fields.

    Returns:
        Dict with 'collisions', 'bad_chars', 'stats'.
    """
    key_map: Dict[str, List[Dict]] = {}
    bad_chars = []

    for job in jobs:
        company = job.get("company", "")
        title = job.get("title", "")
        url = job.get("url", "")
        job_id = job.get("id", "")

        # Check for problematic characters
        for char in ['/', ',', '\\', ':', '*', '?', '"', '<', '>', '|']:
            if char in company or char in title:
                bad_chars.append({
                    "job_id": job_id,
                    "company": company,
                    "title": title,
                    "bad_char": char,
                })

        key = make_job_key(company, title, url)
        if key not in key_map:
            key_map[key] = []
        key_map[key].append({
            "id": job_id,
            "company": company,
            "title": title,
        })

    # Find collisions (same key, different jobs)
    collisions = {
        k: v for k, v in key_map.items() if len(v) > 1
    }

    return {
        "total_jobs": len(jobs),
        "unique_keys": len(key_map),
        "collisions": collisions,
        "collision_count": len(collisions),
        "bad_char_entries": bad_chars,
        "bad_char_count": len(bad_chars),
    }


if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 3:
        company_arg = sys.argv[1]
        title_arg = sys.argv[2]
        url_arg = sys.argv[3] if len(sys.argv) > 3 else ""
        key = make_job_key(company_arg, title_arg, url_arg)
        print(f"Key: {key}")
    else:
        print("Usage: python job_key.py <company> <title> [url]", file=sys.stderr)
        sys.exit(2)
