"""
Semantic Vector Search & Market Trend Clustering Engine
Integrates ChromaDB & Vector Embeddings:
- Natural language semantic search across all indexed jobs
- "Find Similar Opportunities" (cosine similarity nearest neighbors)
- Market competency trend analytics & skill co-occurrence clustering
"""

import json
import hashlib
import os
import re
from typing import Dict, Any, List, Optional
from datetime import datetime
from backend.app.core.config import settings
from backend.app.core.database import is_postgres_database
from backend.app.core.event_logger import agent_logger
from backend.app.core.llm_client import llm_client
from backend.app.modules.scrape.seen_jobs_tracker import seen_jobs_tracker

try:
    import chromadb
    from chromadb.config import Settings as ChromaSettings
    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False


class SemanticSearchEngine:
    """Manages vector embeddings and semantic job querying via ChromaDB."""

    def __init__(self):
        self.persist_dir = settings.CHROMA_PERSIST_DIR
        self.client = None
        self.collection = None
        self.pg_connection = None
        self.backend = "fallback"
        self._init_chroma()

    def _embedding(self, text: str) -> List[float]:
        """Create a deterministic local vector for pgvector deployments.

        This keeps the migration self-contained and repeatable. A future
        embedding provider can replace this method without changing storage or
        query contracts.
        """
        dimensions = settings.VECTOR_DIMENSIONS
        vector = [0.0] * dimensions
        tokens = re.findall(r"[\w+#.-]+", text.lower())
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % dimensions
            vector[index] += 1.0
        norm = sum(value * value for value in vector) ** 0.5
        return [value / norm for value in vector] if norm else vector

    def _init_postgres(self) -> bool:
        if not is_postgres_database() or settings.VECTOR_BACKEND.lower() == "chroma":
            return False
        try:
            import psycopg
            from pgvector.psycopg import register_vector
            from psycopg.rows import dict_row

            dsn = settings.DATABASE_URL.replace("postgresql+psycopg://", "postgresql://", 1)
            self.pg_connection = psycopg.connect(dsn, row_factory=dict_row)
            register_vector(self.pg_connection)
            with self.pg_connection.cursor() as cursor:
                cursor.execute("CREATE EXTENSION IF NOT EXISTS vector")
                cursor.execute(f"""
                    CREATE TABLE IF NOT EXISTS career_job_vectors (
                        job_key TEXT PRIMARY KEY,
                        title TEXT NOT NULL,
                        company TEXT NOT NULL,
                        location TEXT,
                        match_score DOUBLE PRECISION DEFAULT 0,
                        status TEXT,
                        content TEXT NOT NULL,
                        embedding vector({settings.VECTOR_DIMENSIONS}) NOT NULL,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
            self.pg_connection.commit()
            self.backend = "pgvector"
            agent_logger.log_event("SEMANTIC_SEARCH", "PostgreSQL/pgvector backend initialized.")
            return True
        except Exception as exc:
            if self.pg_connection:
                self.pg_connection.close()
                self.pg_connection = None
            agent_logger.log_event("SEMANTIC_SEARCH", f"pgvector unavailable, fallback enabled: {exc}")
            return False

    def _init_chroma(self):
        if self._init_postgres():
            return
        if not CHROMA_AVAILABLE:
            agent_logger.log_event("SEMANTIC_SEARCH", "ChromaDB library not available, fallback enabled.")
            return

        try:
            os.makedirs(self.persist_dir, exist_ok=True)
            self.client = chromadb.PersistentClient(path=self.persist_dir)
            self.collection = self.client.get_or_create_collection(
                name="career_job_postings",
                metadata={"hnsw:space": "cosine"}
            )
            self.backend = "chroma"
            agent_logger.log_event("SEMANTIC_SEARCH", "ChromaDB job collection initialized.")
        except Exception as e:
            agent_logger.log_event("SEMANTIC_SEARCH", f"ChromaDB initialization failed: {e}")

    def index_all_seen_jobs(self) -> Dict[str, Any]:
        """Indexes all jobs currently tracked in seen_jobs_tracker into ChromaDB."""
        if self.backend == "pgvector" and self.pg_connection:
            return self._index_pgvector_jobs()
        if not self.collection:
            return {"status": "error", "message": "ChromaDB collection not available."}

        all_jobs = seen_jobs_tracker.get_all()
        indexed_count = 0

        documents = []
        metadatas = []
        ids = []

        for key, job in all_jobs.items():
            title = job.get("title", "")
            company = job.get("company", "")
            location = job.get("location", "")
            desc = job.get("description", "") or f"{title} at {company} located in {location}"

            text_repr = f"Title: {title}\nCompany: {company}\nLocation: {location}\nDetails: {desc[:2000]}"
            
            documents.append(text_repr)
            metadatas.append({
                "job_key": key,
                "company": company,
                "title": title,
                "location": location,
                "match_score": float(job.get("match_score") or 0.0),
                "status": job.get("status", "new")
            })
            ids.append(key)

        if ids:
            self.collection.upsert(
                documents=documents,
                metadatas=metadatas,
                ids=ids
            )
            indexed_count = len(ids)

        agent_logger.log_event("SEMANTIC_SEARCH", f"Upserted {indexed_count} jobs to vector space.")
        return {
            "status": "success",
            "indexed_count": indexed_count,
            "total_tracked": len(all_jobs)
        }

    def _index_pgvector_jobs(self) -> Dict[str, Any]:
        all_jobs = seen_jobs_tracker.get_all()
        with self.pg_connection.cursor() as cursor:
            for key, job in all_jobs.items():
                title = job.get("title", "")
                company = job.get("company", "")
                location = job.get("location", "")
                content = f"Title: {title}\nCompany: {company}\nLocation: {location}\nDetails: {(job.get('description') or '')[:2000]}"
                cursor.execute("""
                    INSERT INTO career_job_vectors
                        (job_key, title, company, location, match_score, status, content, embedding, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (job_key) DO UPDATE SET
                        title = EXCLUDED.title, company = EXCLUDED.company,
                        location = EXCLUDED.location, match_score = EXCLUDED.match_score,
                        status = EXCLUDED.status, content = EXCLUDED.content,
                        embedding = EXCLUDED.embedding, updated_at = CURRENT_TIMESTAMP
                """, (
                    key, title, company, location, float(job.get("match_score") or 0.0),
                    job.get("status", "new"), content, self._embedding(content),
                ))
        self.pg_connection.commit()
        count = len(all_jobs)
        agent_logger.log_event("SEMANTIC_SEARCH", f"Upserted {count} jobs to pgvector.")
        return {"status": "success", "backend": "pgvector", "indexed_count": count, "total_tracked": count}

    def semantic_search(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Searches jobs based on semantic conceptual similarity rather than exact keywords."""
        if self.backend == "pgvector" and self.pg_connection:
            embedding = self._embedding(query)
            with self.pg_connection.cursor() as cursor:
                cursor.execute("""
                    SELECT job_key, title, company, location, match_score, status,
                           GREATEST(0, 1 - (embedding <=> %s)) AS semantic_similarity
                    FROM career_job_vectors
                    ORDER BY embedding <=> %s
                    LIMIT %s
                """, (embedding, embedding, limit))
                rows = cursor.fetchall()
            return [
                {
                    "job_key": row["job_key"], "title": row["title"],
                    "company": row["company"], "location": row["location"],
                    "match_score": row["match_score"], "status": row["status"],
                    "semantic_similarity": round(float(row["semantic_similarity"]) * 100, 1),
                }
                for row in rows
            ]

        if not self.collection:
            # Fallback to smart keyword filtering if ChromaDB is offline
            all_jobs = seen_jobs_tracker.get_all()
            q_words = query.lower().split()
            scored = []
            for k, j in all_jobs.items():
                match = sum(1 for w in q_words if w in j.get("title", "").lower() or w in j.get("company", "").lower())
                if match > 0:
                    scored.append((match, j))
            scored.sort(key=lambda x: -x[0])
            return [x[1] for x in scored[:limit]]

        results = self.collection.query(
            query_texts=[query],
            n_results=min(limit, max(1, self.collection.count()))
        )

        matches = []
        if results and results.get("ids") and results["ids"][0]:
            for i, job_key in enumerate(results["ids"][0]):
                meta = results["metadatas"][0][i]
                dist = results["distances"][0][i] if "distances" in results and results["distances"] else 0.5
                similarity = round((1.0 - dist) * 100, 1)

                matches.append({
                    "job_key": job_key,
                    "title": meta.get("title"),
                    "company": meta.get("company"),
                    "location": meta.get("location"),
                    "match_score": meta.get("match_score"),
                    "status": meta.get("status"),
                    "semantic_similarity": max(0.0, similarity)
                })

        return matches

    def find_similar_jobs(self, job_key: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Finds job postings semantically closest to a specific job key."""
        all_jobs = seen_jobs_tracker.get_all()
        target = all_jobs.get(job_key)
        if not target:
            return []

        search_text = f"{target.get('title')} {target.get('company')} {target.get('location')}"
        results = self.semantic_search(search_text, limit=limit + 1)
        # Exclude self
        return [r for r in results if r.get("job_key") != job_key][:limit]

    def analyze_market_skill_trends(self) -> Dict[str, Any]:
        """Analyzes skill frequencies and high-velocity demand patterns."""
        all_jobs = seen_jobs_tracker.get_all()
        
        tech_keywords = [
            "Python", "FastAPI", "Docker", "Kubernetes", "AWS", "LangChain", 
            "TypeScript", "React", "Next.js", "PostgreSQL", "Kafka", "Agent",
            "LLM", "RAG", "Microservices", "GraphQL", "Go", "Rust"
        ]
        
        frequency: Dict[str, int] = {k: 0 for k in tech_keywords}
        total = len(all_jobs)

        for job in all_jobs.values():
            blob = f"{job.get('title', '')} {job.get('description', '')}".lower()
            for tech in tech_keywords:
                if tech.lower() in blob:
                    frequency[tech] += 1

        sorted_trends = sorted(frequency.items(), key=lambda x: -x[1])
        top_skills = [
            {"skill": k, "count": v, "percentage": round((v / max(total, 1)) * 100, 1)}
            for k, v in sorted_trends if v > 0
        ]

        return {
            "total_analyzed_jobs": total,
            "top_in_demand_skills": top_skills[:10],
            "market_summary": f"Son taranan {total} ilanda en yüksek talep gören ilk 3 teknoloji: " + 
                              ", ".join([s['skill'] for s in top_skills[:3]]) if top_skills else "Veri yetersiz."
        }

semantic_search_engine = SemanticSearchEngine()
