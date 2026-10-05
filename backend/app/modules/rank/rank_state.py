"""
Rank State Manager
Adapted from MadsLorentzen/ai-job-search rank_state.py concept.

Manages the ranking lifecycle for scored jobs:
- candidates: select eligible entries for ranking
- sweep: expire past-deadline entries
- apply: write scoring results back to seen_jobs

Keeps the scoring model's context small by projecting only needed fields.
"""

import json
from datetime import date, datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from backend.app.modules.scrape.seen_jobs_tracker import seen_jobs_tracker
from backend.app.core.event_logger import agent_logger


class RankStateManager:
    """Orchestrates ranking state transitions for seen jobs."""

    def get_candidates(
        self,
        focus: Optional[str] = None,
        limit: int = 50,
        include_all: bool = False,
    ) -> Dict[str, Any]:
        """
        Select jobs eligible for ranking and project only fields needed for scoring.

        Args:
            focus: Optional text filter (e.g., "AI engineer" to narrow candidates)
            limit: Max number of candidates to return
            include_all: If True, include previously ranked jobs for re-scoring
        """
        all_jobs = seen_jobs_tracker.get_all()
        candidates = []
        skipped = {"already_ranked": 0, "skipped_status": 0, "filtered_out": 0}

        for key, entry in all_jobs.items():
            status = entry.get("status", "new")

            if include_all:
                if status == "skipped":
                    skipped["skipped_status"] += 1
                    continue
            else:
                if status != "new":
                    if status == "ranked":
                        skipped["already_ranked"] += 1
                    else:
                        skipped["skipped_status"] += 1
                    continue

            # Apply focus filter
            if focus:
                focus_lower = focus.lower()
                title = entry.get("title", "").lower()
                company = entry.get("company", "").lower()
                if focus_lower not in title and focus_lower not in company:
                    skipped["filtered_out"] += 1
                    continue

            candidates.append({
                "key": key,
                "company": entry.get("company", ""),
                "title": entry.get("title", ""),
                "url": entry.get("url", ""),
                "location": entry.get("location", ""),
                "portal": entry.get("portal", ""),
                "first_seen": entry.get("first_seen", ""),
                "deadline": entry.get("deadline"),
            })

            if len(candidates) >= limit:
                break

        agent_logger.log_event(
            "RANK_STATE",
            f"Selected {len(candidates)} candidates for ranking "
            f"(skipped: {sum(skipped.values())})"
        )

        return {
            "candidates": candidates,
            "count": len(candidates),
            "skipped": skipped,
            "focus": focus,
            "include_all": include_all,
        }

    def apply_scores(
        self,
        results: List[Dict[str, Any]],
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """
        Write scoring results back to seen_jobs tracker.

        Args:
            results: List of dicts with 'key', 'score', 'strengths', 'gaps', 'deadline'
            dry_run: If True, validate without writing
        """
        applied = []
        errors = []

        for result in results:
            key = result.get("key")
            score = result.get("score", 0)

            if not key:
                errors.append({"error": "Missing key", "result": result})
                continue

            if not dry_run:
                success = seen_jobs_tracker.set_score(
                    key=key,
                    score=score,
                    strengths=result.get("strengths"),
                    gaps=result.get("gaps"),
                    deadline=result.get("deadline"),
                )
                if success:
                    applied.append(key)
                else:
                    errors.append({"error": f"Key not found: {key}", "result": result})
            else:
                applied.append(key)

        agent_logger.log_event(
            "RANK_STATE",
            f"Applied scores to {len(applied)} jobs "
            f"(errors: {len(errors)}, dry_run: {dry_run})"
        )

        return {
            "applied_count": len(applied),
            "applied_keys": applied,
            "error_count": len(errors),
            "errors": errors,
            "dry_run": dry_run,
        }

    def sweep_and_report(
        self,
        dry_run: bool = True,
        exclude_keys: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Run expiry sweep and closing-soon check, then return a combined report.
        """
        # Sweep expired
        expired = seen_jobs_tracker.sweep_expired(dry_run=dry_run)

        # Filter out excluded keys
        if exclude_keys:
            expired = [e for e in expired if e["key"] not in exclude_keys]

        # Get closing soon
        closing_soon = seen_jobs_tracker.get_closing_soon(days=7)
        if exclude_keys:
            closing_soon = [c for c in closing_soon if c["key"] not in exclude_keys]

        return {
            "expired": expired,
            "expired_count": len(expired),
            "closing_soon": closing_soon,
            "closing_soon_count": len(closing_soon),
            "dry_run": dry_run,
        }

    def get_ranking_summary(self) -> Dict[str, Any]:
        """Get a summary of the current ranking state."""
        all_jobs = seen_jobs_tracker.get_all()

        ranked = []
        for key, entry in all_jobs.items():
            if entry.get("status") == "ranked" and entry.get("match_score"):
                ranked.append({
                    "key": key,
                    "company": entry.get("company"),
                    "title": entry.get("title"),
                    "score": entry.get("match_score"),
                    "strengths": entry.get("strengths", []),
                    "gaps": entry.get("gaps", []),
                    "deadline": entry.get("deadline"),
                    "scored_at": entry.get("scored_at"),
                })

        ranked.sort(key=lambda x: x.get("score", 0), reverse=True)

        # Tier breakdown
        high = [j for j in ranked if j["score"] >= 75]
        medium = [j for j in ranked if 50 <= j["score"] < 75]
        low = [j for j in ranked if j["score"] < 50]

        return {
            "total_ranked": len(ranked),
            "high_match": {"count": len(high), "jobs": high[:10]},
            "medium_match": {"count": len(medium), "jobs": medium[:10]},
            "low_match": {"count": len(low), "jobs": low[:5]},
            "stats": seen_jobs_tracker.stats(),
        }


# Module-level singleton
rank_state_manager = RankStateManager()
