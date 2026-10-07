"""robots.txt check for the scrapers that read a site's web pages."""

from functools import lru_cache
from typing import Optional
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import httpx

from backend.app.core.config import settings


# ponytail: one read per site for the life of the process; add an expiry if the app starts running for weeks.
@lru_cache(maxsize=64)
def _rules(origin: str) -> Optional[RobotFileParser]:
    """The site's rules, or None when they could not be read."""
    try:
        response = httpx.get(
            f"{origin}/robots.txt", headers={"User-Agent": settings.JOB_SOURCE_USER_AGENT},
            timeout=settings.JOB_SOURCE_TIMEOUT_SECONDS, follow_redirects=True,
        )
    except httpx.HTTPError:
        return None
    parser = RobotFileParser()
    if 400 <= response.status_code < 500:
        parser.parse([])  # no published rules: nothing is disallowed
    elif response.status_code == 200:
        parser.parse(response.text.splitlines())
    else:
        return None
    return parser


def robots_allows(url: str) -> bool:
    """Whether the site lets our agent fetch this URL. An unreadable robots.txt counts as no."""
    parts = urlsplit(url)
    rules = _rules(f"{parts.scheme}://{parts.netloc}")
    return rules is not None and rules.can_fetch(settings.JOB_SOURCE_USER_AGENT, url)
