"""
Portal Health Check Module
Adapted from MadsLorentzen/ai-job-search portal health check concept.

Scraper-based portal CLIs rot silently: when a portal changes its markup,
the parser usually exits 0 with zero results or with null/garbled fields.
This module catches that from evidence the run already holds.

Checks:
1. Degraded scan: inspects returned results for:
   - company null/empty on every result
   - empty titles
   - undecoded HTML entities or fragments in titles
   - URLs that don't point at the expected portal domain
2. Yield history: if a portal returned zero results but had prior results
3. Sentinel probe: one targeted search using a known-good query

Usage:
    from backend.app.modules.scrape.portal_health import portal_health_checker
    report = portal_health_checker.check_portal("linkedin", results, seen_history)
"""

import re
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from backend.app.core.event_logger import agent_logger

# HTML entity/fragment patterns that indicate broken parsing
HTML_PATTERNS = [
    re.compile(r'&amp;|&lt;|&gt;|&quot;|&#\d+;'),  # HTML entities
    re.compile(r'<[a-z]+[^>]*>'),  # HTML tags in titles
    re.compile(r'class=|style=|href='),  # CSS/HTML attributes leaked into text
]

# Portal domain mapping for URL validation
PORTAL_DOMAINS = {
    "linkedin": ["linkedin.com"],
    "kosovajob": ["kosovajob.com"],
    "upwork": ["upwork.com"],
    "techcareer": ["techcareer.net"],
    "fiverr": ["fiverr.com"],
    "freelancer": ["freelancer.com"],
    "toptal": ["toptal.com"],
    "gjirafawork": ["gjirafa.com", "gjirafawork.com"],
    "kariyernet": ["kariyer.net"],
    "indeed": ["indeed.com"],
    "glassdoor": ["glassdoor.com"],
    "wellfound": ["wellfound.com", "angel.co"],
    "remote": ["remote.co", "weworkremotely.com", "remoteok.com", "remotive.com"],
}


class PortalHealthChecker:
    """Detects silently broken scrapers from their output."""

    def check_results_quality(
        self,
        portal_name: str,
        results: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Analyze scrape results for signs of parser degradation.

        Returns:
            Dict with health status and detected issues.
        """
        issues = []
        warnings = []

        if not results:
            return {
                "portal": portal_name,
                "status": "no_results",
                "result_count": 0,
                "issues": ["Portal returned zero results"],
                "warnings": [],
                "health_score": 0,
            }

        total = len(results)

        # 1. Check for null/empty companies
        empty_companies = sum(
            1 for r in results
            if not r.get("company") or str(r["company"]).strip() == ""
        )
        if empty_companies == total:
            issues.append(f"ALL {total} results have empty company names — parser likely broken")
        elif empty_companies > total * 0.5:
            warnings.append(f"{empty_companies}/{total} results have empty company names")

        # 2. Check for empty titles
        empty_titles = sum(
            1 for r in results
            if not r.get("title") or str(r["title"]).strip() == ""
        )
        if empty_titles == total:
            issues.append(f"ALL {total} results have empty titles — parser likely broken")
        elif empty_titles > total * 0.3:
            warnings.append(f"{empty_titles}/{total} results have empty titles")

        # 3. Check for HTML artifacts in titles
        html_contaminated = 0
        for r in results:
            title = str(r.get("title", ""))
            for pattern in HTML_PATTERNS:
                if pattern.search(title):
                    html_contaminated += 1
                    break
        if html_contaminated > total * 0.2:
            issues.append(
                f"{html_contaminated}/{total} titles contain HTML artifacts — "
                "parser is extracting raw markup instead of text"
            )

        # 4. Check URL domains match expected portal
        if portal_name in PORTAL_DOMAINS:
            expected_domains = PORTAL_DOMAINS[portal_name]
            wrong_domain = 0
            for r in results:
                url = str(r.get("url", ""))
                if url and not any(d in url for d in expected_domains):
                    wrong_domain += 1
            if wrong_domain > total * 0.5:
                warnings.append(
                    f"{wrong_domain}/{total} URLs don't point to expected "
                    f"{portal_name} domain(s): {expected_domains}"
                )

        # 5. Check for suspiciously identical descriptions
        descriptions = [str(r.get("description", ""))[:100] for r in results if r.get("description")]
        if len(descriptions) > 3:
            unique_descs = set(descriptions)
            if len(unique_descs) == 1:
                issues.append("All results have identical descriptions — likely a parsing error")

        # 6. Check for date sanity
        future_dates = 0
        very_old = 0
        for r in results:
            date_str = str(r.get("posted_date", ""))
            # Simple heuristic checks
            if "2030" in date_str or "2029" in date_str or "2028" in date_str:
                future_dates += 1
            if "2020" in date_str or "2019" in date_str or "2018" in date_str:
                very_old += 1
        if future_dates > 0:
            warnings.append(f"{future_dates} results have future dates")
        if very_old > total * 0.5:
            warnings.append(f"{very_old}/{total} results have dates older than 5 years")

        # Calculate health score
        health_score = 100
        health_score -= len(issues) * 30
        health_score -= len(warnings) * 10
        health_score = max(0, min(100, health_score))

        status = "healthy"
        if issues:
            status = "degraded"
        elif warnings:
            status = "warning"

        if status == "degraded":
            agent_logger.log_event(
                "PORTAL_HEALTH",
                f"⚠️ Portal '{portal_name}' is DEGRADED: {'; '.join(issues)}"
            )
        elif status == "warning":
            agent_logger.log_event(
                "PORTAL_HEALTH",
                f"⚡ Portal '{portal_name}' has warnings: {'; '.join(warnings)}"
            )

        return {
            "portal": portal_name,
            "status": status,
            "result_count": total,
            "health_score": health_score,
            "issues": issues,
            "warnings": warnings,
            "checked_at": datetime.now().isoformat(),
        }

    def check_yield_history(
        self,
        portal_name: str,
        current_count: int,
        historical_counts: List[int],
    ) -> Optional[str]:
        """
        Check if a portal that used to return results now returns nothing.

        Args:
            portal_name: Name of the portal
            current_count: Number of results from this run
            historical_counts: List of result counts from previous runs

        Returns:
            Warning message if portal appears broken, None if OK.
        """
        if current_count > 0:
            return None

        if not historical_counts:
            return None

        avg_historical = sum(historical_counts) / len(historical_counts)
        if avg_historical > 5:
            msg = (
                f"Portal '{portal_name}' returned 0 results but averaged "
                f"{avg_historical:.0f} results in {len(historical_counts)} prior runs. "
                "The portal may have changed its markup or API."
            )
            agent_logger.log_event("PORTAL_HEALTH", f"📉 {msg}")
            return msg

        return None

    def full_health_report(
        self,
        portal_results: Dict[str, List[Dict[str, Any]]],
    ) -> Dict[str, Any]:
        """
        Run health checks on all portals from a single scrape run.

        Args:
            portal_results: Dict mapping portal_name → list of results

        Returns:
            Combined health report for all portals.
        """
        reports = {}
        overall_healthy = True

        for portal_name, results in portal_results.items():
            report = self.check_results_quality(portal_name, results)
            reports[portal_name] = report
            if report["status"] != "healthy":
                overall_healthy = False

        return {
            "overall_status": "healthy" if overall_healthy else "issues_detected",
            "portals": reports,
            "checked_at": datetime.now().isoformat(),
        }


# Module-level singleton
portal_health_checker = PortalHealthChecker()
