"""
Upskill / Learning Path Engine
Adapted from MadsLorentzen/ai-job-search upskill concept.

Generates personalized learning paths based on skill gap analysis:
- Maps missing skills to concrete learning resources
- Prioritizes by job market demand and candidate's existing foundation
- Tracks progress through self-reported completions
- Suggests portfolio-ready mini-projects for each skill

Storage: data/upskill_progress.json
"""

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

from backend.app.core.config import settings
from backend.app.core.tenant import get_tenant_id, tenant_data_path
from backend.app.core.event_logger import agent_logger

UPSKILL_DATA_PATH = settings.DATA_PATH / "upskill_progress.json"

# Curated learning resources by technology
LEARNING_RESOURCES = {
    "docker": {
        "name": "Docker & Containerization",
        "difficulty": "beginner",
        "estimated_hours": 15,
        "resources": [
            {"type": "course", "title": "Docker Mastery", "url": "https://www.udemy.com/course/docker-mastery/", "hours": 10},
            {"type": "docs", "title": "Docker Official Docs", "url": "https://docs.docker.com/get-started/"},
            {"type": "practice", "title": "Play with Docker", "url": "https://labs.play-with-docker.com/"},
        ],
        "portfolio_project": "Containerize your existing project with multi-stage builds, docker-compose, and health checks",
    },
    "kubernetes": {
        "name": "Kubernetes",
        "difficulty": "intermediate",
        "estimated_hours": 30,
        "resources": [
            {"type": "course", "title": "Kubernetes for Developers", "url": "https://kubernetes.io/docs/tutorials/"},
            {"type": "practice", "title": "Killercoda K8s Labs", "url": "https://killercoda.com/playgrounds/scenario/kubernetes"},
        ],
        "portfolio_project": "Deploy a microservice app with K8s manifests, HPA, and service mesh",
    },
    "aws": {
        "name": "AWS Cloud",
        "difficulty": "intermediate",
        "estimated_hours": 40,
        "resources": [
            {"type": "course", "title": "AWS Solutions Architect", "url": "https://aws.amazon.com/training/"},
            {"type": "practice", "title": "AWS Free Tier", "url": "https://aws.amazon.com/free/"},
        ],
        "portfolio_project": "Build a serverless API with Lambda, API Gateway, DynamoDB, and CloudWatch",
    },
    "graphql": {
        "name": "GraphQL",
        "difficulty": "beginner",
        "estimated_hours": 12,
        "resources": [
            {"type": "docs", "title": "GraphQL Official Guide", "url": "https://graphql.org/learn/"},
            {"type": "course", "title": "How to GraphQL", "url": "https://www.howtographql.com/"},
        ],
        "portfolio_project": "Add a GraphQL layer to your existing REST API with schema stitching",
    },
    "rust": {
        "name": "Rust Programming",
        "difficulty": "advanced",
        "estimated_hours": 50,
        "resources": [
            {"type": "book", "title": "The Rust Book", "url": "https://doc.rust-lang.org/book/"},
            {"type": "practice", "title": "Rustlings", "url": "https://github.com/rust-lang/rustlings"},
        ],
        "portfolio_project": "Build a high-performance CLI tool or web scraper in Rust",
    },
    "langchain": {
        "name": "LangChain & LLM Apps",
        "difficulty": "intermediate",
        "estimated_hours": 20,
        "resources": [
            {"type": "docs", "title": "LangChain Docs", "url": "https://python.langchain.com/docs/"},
            {"type": "course", "title": "DeepLearning.AI LangChain Course", "url": "https://www.deeplearning.ai/short-courses/langchain/"},
        ],
        "portfolio_project": "Build a RAG chatbot with document ingestion, vector search, and structured output",
    },
    "terraform": {
        "name": "Terraform / IaC",
        "difficulty": "intermediate",
        "estimated_hours": 20,
        "resources": [
            {"type": "docs", "title": "Terraform Tutorials", "url": "https://developer.hashicorp.com/terraform/tutorials"},
        ],
        "portfolio_project": "Provision a full staging environment with Terraform modules and state management",
    },
}


class UpskillEngine:
    """Generates and tracks personalized learning paths."""

    def __init__(self, data_path: Path = UPSKILL_DATA_PATH):
        self.data_path = data_path
        self._progress_by_scope: Dict[str, Dict[str, Any]] = {}
        self._loaded_scopes = set()

    def _scope(self):
        return get_tenant_id() or "__shared__"

    def _scoped_data_path(self):
        return tenant_data_path(self.data_path.name) if get_tenant_id() else self.data_path

    @property
    def _progress(self):
        scope = self._scope()
        if scope not in self._loaded_scopes:
            path = self._scoped_data_path()
            try:
                value = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
            except (json.JSONDecodeError, OSError):
                value = {}
            self._progress_by_scope[scope] = value
            self._loaded_scopes.add(scope)
        return self._progress_by_scope[scope]

    @_progress.setter
    def _progress(self, value):
        scope = self._scope()
        self._progress_by_scope[scope] = value
        self._loaded_scopes.add(scope)

    def _load(self):
        if self.data_path.is_file():
            try:
                self._progress = json.loads(self.data_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                self._progress = {}

    def _save(self):
        path = self._scoped_data_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self._progress, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

    def generate_learning_path(
        self,
        missing_skills: List[str],
        candidate_skills: List[str],
        max_hours_per_week: int = 10,
    ) -> Dict[str, Any]:
        """
        Generate a prioritized learning path for missing skills.
        """
        path_items = []
        total_hours = 0
        cand_lower = {s.lower() for s in candidate_skills}

        seen = set()
        for raw_skill in missing_skills:
            skill = raw_skill.strip()
            skill_lower = skill.lower()
            if not skill or skill_lower in seen:
                continue
            seen.add(skill_lower)
            resource = LEARNING_RESOURCES.get(skill_lower)

            if resource:
                # Adjust difficulty based on related skills
                has_related = any(
                    related in cand_lower
                    for related in self._get_related_skills(skill_lower)
                )
                adjusted_hours = resource["estimated_hours"]
                if has_related:
                    adjusted_hours = int(adjusted_hours * 0.7)

                path_items.append({
                    "skill": skill,
                    "name": resource["name"],
                    "difficulty": resource["difficulty"],
                    "estimated_hours": adjusted_hours,
                    "resources": resource["resources"],
                    "portfolio_project": resource["portfolio_project"],
                    "has_related_foundation": has_related,
                    "status": self._progress.get(skill_lower, {}).get("status", "not_started"),
                })
                total_hours += adjusted_hours
            else:
                path_items.append({
                    "skill": skill,
                    "name": skill,
                    "difficulty": "unknown",
                    "estimated_hours": 15,
                    "resources": [{"type": "search", "title": f"Search for {skill} tutorials", "url": f"https://www.google.com/search?q={skill}+tutorial"}],
                    "portfolio_project": f"Build a demo project showcasing {skill}",
                    "has_related_foundation": False,
                    "status": self._progress.get(skill_lower, {}).get("status", "not_started"),
                })
                total_hours += 15

        weeks_needed = total_hours / max(max_hours_per_week, 1)

        agent_logger.log_event(
            "UPSKILL",
            f"Generated learning path: {len(path_items)} skills, ~{total_hours}h total"
        )

        plan = {
            "path": path_items,
            "total_skills": len(path_items),
            "total_estimated_hours": total_hours,
            "weeks_at_current_pace": round(weeks_needed, 1),
            "hours_per_week": max_hours_per_week,
        }
        plan_path = self._scoped_data_path().with_name("upskill_plan.json")
        plan_path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=plan_path.parent, delete=False) as temporary:
            json.dump(plan, temporary, ensure_ascii=False)
        os.replace(temporary.name, plan_path)
        return plan

    def get_saved_plan(self) -> Optional[Dict[str, Any]]:
        path = self._scoped_data_path().with_name("upskill_plan.json")
        if not path.is_file():
            return None
        plan = json.loads(path.read_text(encoding="utf-8"))
        for item in plan.get("path", []):
            item["status"] = self._progress.get(item["skill"].lower(), {}).get("status", "not_started")
        return plan

    def _get_related_skills(self, skill: str) -> List[str]:
        """Get skills that provide a foundation for learning the target skill."""
        relations = {
            "kubernetes": ["docker", "linux", "aws", "gcp"],
            "aws": ["linux", "docker", "terraform"],
            "graphql": ["rest api", "javascript", "typescript"],
            "langchain": ["python", "ai", "ml", "llm"],
            "terraform": ["aws", "gcp", "azure", "docker"],
            "rust": ["c", "c++", "go", "python"],
        }
        return relations.get(skill, [])

    def mark_progress(
        self,
        skill: str,
        status: str,
        notes: str = "",
    ) -> Dict[str, Any]:
        """
        Update progress for a skill.
        Status: not_started, in_progress, completed, skipped
        """
        skill_lower = skill.lower()
        self._progress[skill_lower] = {
            "status": status,
            "updated_at": datetime.now().isoformat(),
            "notes": notes,
        }
        self._save()
        return {"skill": skill, "status": status}

    def get_progress(self) -> Dict[str, Any]:
        """Get all upskill progress."""
        completed = sum(1 for v in self._progress.values() if v.get("status") == "completed")
        in_progress = sum(1 for v in self._progress.values() if v.get("status") == "in_progress")
        return {
            "total_tracked": len(self._progress),
            "completed": completed,
            "in_progress": in_progress,
            "details": self._progress,
        }


# Module-level singleton
upskill_engine = UpskillEngine()
