"""
Robots.txt Compliance Checker
Adapted from MadsLorentzen/ai-job-search robots_check.py

Before retrying a scrape with browser-like headers after a 403,
this tool checks the target site's robots.txt to confirm access is permitted.

Rules (RFC 9309, cautious side):
- Longest-match wins; on equal specificity, Disallow wins
- Disallow for either "*" or our user-agent blocks the retry
- 404 means no published policy = permission granted
- Any other failure = do not retry

Usage:
    from backend.app.tools.robots_check import check_robots_permission
    allowed, reason = check_robots_permission("https://example.com/jobs/123")
"""

import re
import subprocess
import sys
from urllib.parse import urlsplit, unquote
from typing import Tuple, Optional

BROWSER_UA = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
    '(KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36'
)

SCRAPER_UA = 'CareerAgent-Bot/1.0'


def _fetch(url: str, ua: str) -> Tuple[str, int]:
    """Fetch URL content using curl with specified user-agent."""
    result = subprocess.run(
        ['curl', '-sS', '-L', '--max-redirs', '5', '--max-time', '12',
         '-A', ua, '-H', 'Accept: text/plain, text/html',
         '-o', '-', '-w', '\n%{http_code}', '--', url],
        capture_output=True, text=True, encoding='utf-8', errors='replace'
    )
    output = result.stdout
    lines = output.rsplit('\n', 1)
    if len(lines) == 2:
        body, code_str = lines
        try:
            return body, int(code_str.strip())
        except ValueError:
            pass
    if result.returncode != 0:
        raise ConnectionError(f"curl failed: {result.stderr.strip()}")
    return output, 0


def is_robots_body(text: str) -> bool:
    """Quick check if the response body looks like a robots.txt file."""
    lower = text.lower()
    return 'user-agent' in lower or 'disallow' in lower or 'allow' in lower


def _groups(text: str) -> dict:
    """Parse robots.txt into {agent: [(is_allow, pattern), ...]}."""
    groups = {}
    current_agents = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if ':' not in line:
            continue
        key, _, value = line.partition(':')
        key = key.strip().lower()
        value = value.strip().split('#')[0].strip()

        if key == 'user-agent':
            agent = value.lower()
            current_agents = [agent]
            if agent not in groups:
                groups[agent] = []
        elif key in ('allow', 'disallow') and current_agents:
            is_allow = key == 'allow'
            for agent in current_agents:
                groups.setdefault(agent, []).append((is_allow, value))

    return groups


def _match(pattern: str, path: str) -> int:
    """Return match specificity (pattern length) or -1 if no match."""
    if pattern == '':
        return -1
    pattern = unquote(pattern)
    rx = '^' + ''.join(
        '.*' if c == '*' else ('$' if c == '$' else re.escape(c))
        for c in pattern
    )
    return len(pattern) if re.match(rx, path) else -1


def allowed(text: str, agent: str, path: str) -> bool:
    """Check if a path is allowed for the given agent based on robots.txt content."""
    g = _groups(text)
    rules = g.get(agent.lower()) or g.get('*') or []
    best_len, best_allow = -1, True
    for is_allow, pat in rules:
        n = _match(pat, path)
        if n > best_len or (n == best_len and n >= 0 and not is_allow):
            best_len, best_allow = n, is_allow  # Ties → Disallow wins (cautious)
    return True if best_len < 0 else best_allow


def check_robots_permission(url: str) -> Tuple[bool, str]:
    """
    Check if scraping a URL is permitted by robots.txt.

    Returns:
        (is_allowed: bool, reason: str)
    """
    parts = urlsplit(url)
    path = unquote(parts.path) or '/'
    if parts.query:
        path += '?' + parts.query

    robots_url = f'{parts.scheme}://{parts.netloc}/robots.txt'
    body, last = None, 'no attempt'

    for ua in (SCRAPER_UA, BROWSER_UA):
        try:
            text, code = _fetch(robots_url, ua)
        except Exception as e:
            last = type(e).__name__
            continue

        if code == 404:
            return True, 'ALLOWED — no robots.txt published'

        if code == 200:
            if not is_robots_body(text):
                last = 'HTTP 200 but the body is not a robots.txt'
                continue
            body = text
            break

        last = f'HTTP {code}'

    if body is None:
        return False, f'UNCONFIRMED ({last}) — do not retry, use fallback'

    for agent_name in (SCRAPER_UA, '*'):
        if not allowed(body, agent_name, path):
            return False, f'DISALLOWED for {agent_name} — do not retry, use fallback'

    return True, 'ALLOWED — robots.txt permits this path'


def check_robots_dict(url: str) -> dict:
    """API-friendly wrapper."""
    is_allowed, reason = check_robots_permission(url)
    return {
        "url": url,
        "allowed": is_allowed,
        "reason": reason,
    }


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print('Usage: python robots_check.py <url>', file=sys.stderr)
        sys.exit(2)
    ok, msg = check_robots_permission(sys.argv[1])
    print(msg)
    sys.exit(0 if ok else 1)
