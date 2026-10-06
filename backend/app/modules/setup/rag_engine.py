"""
RAG & Vector Knowledge Base Engine
Manages semantic vectorization of candidate projects, repository summaries,
certifications, and deep success stories for context injection into applications.
"""

import json
import math
import re
from pathlib import Path
from backend.app.core.json_store import read_json_store
from typing import List, Dict, Any, Optional
from backend.app.core.config import settings
from backend.app.core.tenant import get_tenant_id

class RAGVectorMemory:
    def __init__(self, storage_path: Optional[Path] = None):
        self.storage_path = storage_path or (settings.DATA_PATH / "rag_store.json")
        self._documents: List[Dict[str, Any]] = []
        self._load()

    @property
    def documents(self) -> List[Dict[str, Any]]:
        tenant_id = get_tenant_id()
        if tenant_id:
            from backend.app.core.database import get_db_connection

            conn = get_db_connection()
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT payload FROM candidate_projects ORDER BY created_at, id")
                return [json.loads(row["payload"]) for row in cursor.fetchall()]
            finally:
                conn.close()
        if settings.MULTI_TENANT_ENABLED:
            return []
        return self._documents

    @documents.setter
    def documents(self, documents: List[Dict[str, Any]]):
        self._documents = documents

    def _load(self):
        if settings.MULTI_TENANT_ENABLED:
            self._documents = []
            return
        # A new installation starts empty. Projects must come from the
        # candidate's own portfolio or an explicitly imported repository.
        self._documents = read_json_store(Path(self.storage_path), [])

    def _save(self):
        tenant_id = get_tenant_id()
        if tenant_id:
            from backend.app.core.database import get_db_connection

            conn = get_db_connection()
            try:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM candidate_projects")
                cursor.executemany(
                    "INSERT INTO candidate_projects (id, payload) VALUES (?, ?)",
                    [(document["id"], json.dumps(document, ensure_ascii=False)) for document in self._documents],
                )
                conn.commit()
            finally:
                conn.close()
            return
        if settings.MULTI_TENANT_ENABLED:
            return
        with open(self.storage_path, "w", encoding="utf-8") as f:
            json.dump(self._documents, f, ensure_ascii=False, indent=2)

    def add_project(self, title: str, content: str, tech_stack: List[str], metrics: str = "", category: str = "Engineering"):
        doc_id = f"proj_{len(self.documents) + 1}_{int(len(title))}"
        doc = {
            "id": doc_id,
            "title": title,
            "category": category,
            "tech_stack": tech_stack,
            "content": content,
            "metrics": metrics,
            "tags": [t.lower() for t in tech_stack] + [w.lower() for w in re.findall(r'\b\w+\b', title)]
        }
        documents = self.documents
        documents.append(doc)
        self._documents = documents
        self._save()
        return doc

    def search_relevant_context(self, query: str, top_k: int = 2) -> List[Dict[str, Any]]:
        """
        Hybrid TF-IDF / keyword similarity score for semantic retrieval.
        Finds candidate projects that best align with job requirements.
        """
        if not self.documents:
            return []
            
        query_terms = set(re.findall(r'\b[a-zA-Z0-9+#.-]+\b', query.lower()))
        scored = []
        
        for doc in self.documents:
            doc_text = f"{doc.get('title', '')} {doc.get('content', '')} {' '.join(doc.get('tech_stack', []))}".lower()
            doc_terms = set(re.findall(r'\b[a-zA-Z0-9+#.-]+\b', doc_text))
            
            # Intersection & overlap
            overlap = query_terms.intersection(doc_terms)
            score = len(overlap)
            
            # Boost matches in tech_stack
            for tech in doc.get("tech_stack", []):
                if tech.lower() in query.lower():
                    score += 2.5
                    
            scored.append((score, doc))
            
        scored.sort(key=lambda x: x[0], reverse=True)
        return [item[1] for item in scored[:top_k]]

    def format_rag_context_for_prompt(self, relevant_projects: List[Dict[str, Any]]) -> str:
        """
        Formats retrieved project contexts for injection into system prompts.
        """
        if not relevant_projects:
            return "General software engineering background with scalable systems experience."
            
        parts = []
        for i, proj in enumerate(relevant_projects, 1):
            parts.append(
                f"PROJECT #{i}: {proj.get('title')}\n"
                f"- Tech Stack: {', '.join(proj.get('tech_stack', []))}\n"
                f"- Key Impact: {proj.get('content')}\n"
                f"- Verifiable Metrics: {proj.get('metrics', 'High impact')}"
            )
        return "\n\n".join(parts)

rag_memory = RAGVectorMemory()
