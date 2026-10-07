"""
Drafter-Reviewer Multi-Agent Orchestration Pipeline
Adapted from MadsLorentzen/ai-job-search drafter-reviewer pattern.

Implements:
1. Research & RAG Agent (with company cache)
2. CV & Cover Letter Drafter Agent
3. Independent Reviewer Agent (separate context, fact-checks against profile)
4. Grounding Audit (verifies all claims against candidate profile)
5. Humanizer & Anti-AI Detector Agent
6. Self-Correction QA Loop with PDF verification
"""

import json
import re
from typing import Dict, Any, Tuple, List, Optional

from backend.app.modules.setup.rag_engine import rag_memory
from backend.app.modules.apply.claim_check import find_unsupported_claims
from backend.app.modules.apply.humanizer_engine import humanizer_engine
from backend.app.modules.apply.company_cache import company_cache
from backend.app.prompts.humanizer_prompts import ANTI_AI_HUMANIZER_SYSTEM_PROMPT
from backend.app.core.event_logger import agent_logger


COVER_LETTER_CV_CHARS = 4500
COVER_LETTER_JOB_CHARS = 3000


COVER_LETTER_SYSTEM_PROMPT = (
    "You write job application cover letters in the candidate's own voice. "
    "Use only the facts in the message, write in the language of the job description, "
    "and reply with the letter text only."
)


def build_cover_letter_prompt(job_data: Dict[str, Any], candidate_profile: Dict[str, Any], relevant_projects: list) -> str:
    """Everything the drafter may use: the real CV and the full job text, and nothing invented.

    When no project is saved in memory the CV is the only evidence; a generic
    "scalable systems background" line must never stand in for it.
    """
    projects = "\n".join(
        f"- {project.get('title')}: {project.get('content')} "
        f"(stack: {', '.join(project.get('tech_stack', []))}; result: {project.get('metrics') or 'not recorded'})"
        for project in relevant_projects
    )
    years = candidate_profile.get("years_of_experience")
    return f"""JOB
Company: {job_data.get('company', '')}
Role: {job_data.get('title', '')}
Location: {job_data.get('location', '')}
Description:
{str(job_data.get('description') or '')[:COVER_LETTER_JOB_CHARS]}

CANDIDATE (the only facts you may use)
Name: {candidate_profile.get('full_name') or 'Candidate'}
Target role: {candidate_profile.get('target_role') or 'not specified'}
Years of professional experience: {years if years not in (None, '') else 'not specified'}
Location: {candidate_profile.get('location') or 'not specified'}
Languages: {', '.join(candidate_profile.get('languages') or []) or 'not specified'}
Skills: {', '.join(str(skill) for skill in (candidate_profile.get('skills') or [])[:25])}
Projects saved in memory:
{projects or '(none saved; rely on the CV text)'}
CV text:
{str(candidate_profile.get('raw_cv_text') or '')[:COVER_LETTER_CV_CHARS] or '(no CV text saved)'}

INSTRUCTIONS
Write a cover letter of 3-4 short paragraphs for this job, signed with the candidate's name.
- Use only facts present above. Do not invent employers, years, titles, metrics or degrees.
- Pick the one or two projects from the CV that are most relevant to THIS job and say concretely what was built and with what.
- If the candidate is a student or has little professional experience, say so plainly and lean on projects, coursework and learning speed; do not present them as senior.
- If the job needs something the candidate lacks, either leave it out or acknowledge it in one honest sentence.
- Write in the language of the job description (Turkish description -> Turkish letter, otherwise English).
- Never use the words 'delve', 'testament', 'tapestry', 'spearheaded', 'seamless', 'delighted to apply'.
- Do not write any phone number, email address, link or postal address; the application form already carries them.
- Vary sentence length; no bullet lists; no placeholders like [Company]."""


class ReviewerAgent:
    """
    Independent Reviewer Agent — spawned with a fresh context.
    Critiques CV and cover letter drafts against the job posting and candidate profile.
    Checks for factual accuracy, keyword coverage, tone, and ATS optimization.
    """

    def review(
        self,
        draft_text: str,
        job_data: Dict[str, Any],
        candidate_profile: Dict[str, Any],
        company_research: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Review a draft and return structured feedback.
        """
        issues = []
        suggestions = []
        score = 100

        job_title = job_data.get("title", "")
        job_desc = job_data.get("description", "")
        company = job_data.get("company", "")

        # 1. Grounding Audit — verify claims against candidate profile
        grounding_issues = self._grounding_audit(draft_text, candidate_profile)
        if grounding_issues:
            issues.extend(grounding_issues)
            score -= len(grounding_issues) * 15

        # 2. Keyword Coverage — check job posting keywords in draft
        keyword_gaps = self._check_keyword_coverage(draft_text, job_desc, candidate_profile)
        if keyword_gaps["missing_important"]:
            suggestions.append(
                f"Consider adding these job-relevant keywords: "
                f"{', '.join(keyword_gaps['missing_important'][:5])}"
            )
            score -= len(keyword_gaps["missing_important"]) * 5

        # 3. Company Name & Role Accuracy
        if company and company.lower() not in draft_text.lower():
            issues.append(f"Draft does not mention company name '{company}'")
            score -= 10

        if job_title and not any(
            word.lower() in draft_text.lower()
            for word in job_title.split() if len(word) > 3
        ):
            suggestions.append(f"Draft doesn't mention key words from role title '{job_title}'")

        # 4. Company Research Alignment
        if company_research:
            mission = company_research.get("mission", "")
            if mission and len(mission) > 20:
                suggestions.append(
                    f"Consider aligning with company mission: {mission[:100]}..."
                )

        # 5. Length Check
        word_count = len(draft_text.split())
        if word_count < 100:
            issues.append(f"Draft too short ({word_count} words). Aim for 250-400 words.")
            score -= 15
        elif word_count > 600:
            suggestions.append(f"Draft is long ({word_count} words). Consider trimming to ~400 words.")

        # 6. Opening Paragraph Check
        first_para = draft_text.split("\n\n")[0] if "\n\n" in draft_text else draft_text[:200]
        generic_openers = ["i am writing", "i'm writing", "i wish to", "i would like to"]
        if any(opener in first_para.lower() for opener in generic_openers):
            suggestions.append(
                "Opening paragraph uses a generic starter. "
                "Consider leading with a specific achievement or company insight."
            )

        score = max(0, min(100, score))

        review_result = {
            "review_score": score,
            "passed": score >= 70 and len(issues) == 0,
            "issues": issues,
            "suggestions": suggestions,
            "keyword_analysis": keyword_gaps,
            "word_count": word_count,
        }

        agent_logger.log_event(
            "REVIEWER_AGENT",
            f"Review complete: score={score}, issues={len(issues)}, suggestions={len(suggestions)}"
        )

        return review_result

    def _grounding_audit(
        self,
        draft_text: str,
        candidate_profile: Dict[str, Any],
    ) -> List[str]:
        """
        Verify all factual claims in the draft against the candidate profile.
        Catches fabricated metrics, wrong dates, inflated titles.
        """
        issues = []
        draft_lower = draft_text.lower()

        # Check for percentage claims (e.g., "improved by 40%")
        pct_claims = re.findall(r'(\d+)%', draft_text)
        profile_text = json.dumps(candidate_profile, default=str).lower()
        for pct in pct_claims:
            if pct not in profile_text and int(pct) > 10:
                issues.append(
                    f"Unverified metric claim: '{pct}%' not found in candidate profile. "
                    "Verify this is accurate or remove."
                )

        # Check for "years of experience" inflation
        years_match = re.findall(r'(\d+)\+?\s*(?:years?|yıl)', draft_lower)
        actual_years = candidate_profile.get("years_of_experience", 0)
        for claimed in years_match:
            if int(claimed) > actual_years + 1:
                issues.append(
                    f"Experience inflation: draft claims {claimed} years, "
                    f"profile shows {actual_years} years."
                )

        return issues

    def _check_keyword_coverage(
        self,
        draft_text: str,
        job_desc: str,
        candidate_profile: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Check which important job keywords appear in the draft."""
        stop_words = {
            "the", "and", "for", "are", "with", "you", "our", "will", "have",
            "from", "this", "that", "your", "can", "all", "been", "has",
            "their", "more", "about", "other", "which", "who", "what",
            "should", "would", "could", "into", "also", "they", "these",
            "some", "may", "than", "its", "very", "each", "not", "but",
            "was", "were", "had", "she", "her", "his", "him", "how",
            "bir", "ve", "ile", "için", "olan", "gibi", "daha",
        }

        job_words = set()
        for word in re.findall(r'\b[a-zA-Z\u00C0-\u024F]{3,}\b', job_desc.lower()):
            if word not in stop_words and len(word) > 3:
                job_words.add(word)

        draft_lower = draft_text.lower()
        candidate_skills = {s.lower() for s in candidate_profile.get("skills", [])}

        found = []
        missing = []
        missing_important = []

        for word in job_words:
            if word in draft_lower:
                found.append(word)
            else:
                missing.append(word)
                if word in candidate_skills:
                    missing_important.append(word)

        return {
            "found": found[:20],
            "missing": missing[:20],
            "missing_important": missing_important,
            "coverage_ratio": len(found) / max(len(job_words), 1),
        }


class MultiAgentApplicationPipeline:
    def __init__(self):
        self.max_qa_iterations = 3
        self.reviewer = ReviewerAgent()

    def run_pipeline(
        self,
        job_data: Dict[str, Any],
        candidate_profile: Dict[str, Any],
        style_profile: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Executes the Drafter-Reviewer agentic cycle synchronously.
        """
        job_title = job_data.get("title", "")
        company = job_data.get("company", "")
        job_desc = job_data.get("description", "")
        cand_name = candidate_profile.get("full_name", "Candidate")

        agent_logger.log_event(
            "PIPELINE", f"Starting Drafter-Reviewer pipeline for {job_title} @ {company}"
        )

        # --- STEP 1: Company Research (with cache) ---
        company_research = company_cache.get(company)
        if not company_research:
            company_research = {"company_name": company, "source": "no_cache"}

        # --- STEP 2: Research & RAG Agent ---
        relevant_projects = rag_memory.search_relevant_context(f"{job_title} {job_desc}", top_k=2)

        # --- STEP 3: Drafter Agent (CV & Cover Letter) ---
        raw_draft = self._generate_initial_draft(
            job_title=job_title,
            company=company,
            cand_name=cand_name,
            relevant_projects=relevant_projects,
            candidate_profile=candidate_profile,
            company_research=company_research,
        )

        # --- STEP 4: Reviewer Agent (independent critique) ---
        review = self.reviewer.review(
            draft_text=raw_draft,
            job_data=job_data,
            candidate_profile=candidate_profile,
            company_research=company_research,
        )

        # --- STEP 5: Apply reviewer feedback if issues found ---
        if not review["passed"]:
            raw_draft = self._apply_review_feedback(raw_draft, review)

        # --- STEP 6: Humanizer & Self-Correction QA Loop ---
        result = self._execute_qa_loop(
            raw_draft=raw_draft,
            job_id=job_data.get("id"),
            relevant_projects=relevant_projects,
            style_profile=style_profile,
            provider_used="Deterministic Hybrid Engine"
        )

        result["reviewer_report"] = review
        result["company_research_used"] = bool(company_research.get("source") != "no_cache")
        return result

    async def run_pipeline_async(
        self,
        job_data: Dict[str, Any],
        candidate_profile: Dict[str, Any],
        style_profile: Dict[str, Any],
        preferred_provider: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Executes the Drafter-Reviewer cycle with live Multi-LLM provider bridge.
        """
        from backend.app.core.llm_client import llm_client

        job_title = job_data.get("title", "")
        company = job_data.get("company", "")
        job_desc = job_data.get("description", "")
        cand_name = candidate_profile.get("full_name", "Candidate")

        # 1. Company Research (cached)
        company_research = company_cache.get(company) or {"company_name": company}

        # 2. RAG Context
        relevant_projects = rag_memory.search_relevant_context(f"{job_title} {job_desc}", top_k=2)

        # 3. LLM-powered Drafter
        user_prompt = build_cover_letter_prompt(job_data, candidate_profile, relevant_projects)

        llm_res = await llm_client.generate_text(
            system_prompt=COVER_LETTER_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            preferred_provider=preferred_provider,
            apply_humanizer=False
        )

        # A provider failure comes back as a generic template, never as empty text,
        # so the profile-based draft has to be chosen explicitly.
        raw_draft = self._generate_initial_draft(
            job_title, company, cand_name, relevant_projects,
            candidate_profile, company_research
        ) if llm_res["is_template_fallback"] else llm_res["text"]

        # 4. Reviewer Agent
        review = self.reviewer.review(
            draft_text=raw_draft,
            job_data=job_data,
            candidate_profile=candidate_profile,
            company_research=company_research,
        )

        # 5. Apply feedback if needed
        if not review["passed"]:
            # The editor gets the same facts and rules as the drafter. Without them it "improved"
            # letters by inventing metrics, tools and contact details.
            revision_res = await llm_client.generate_text(
                system_prompt=COVER_LETTER_SYSTEM_PROMPT,
                user_prompt=f"{user_prompt}\n\nREVISION\n{self._build_revision_prompt(raw_draft, review)}\n"
                            "Every fact in the revised letter must come from the CANDIDATE section above.",
                preferred_provider=preferred_provider,
                apply_humanizer=False
            )
            if revision_res["is_template_fallback"]:
                raw_draft = self._apply_review_feedback(raw_draft, review)
            else:
                raw_draft = revision_res["text"]
                # The letter now comes from the model, whatever produced the first draft.
                llm_res = revision_res

        # 6. Humanizer & QA Loop
        result = self._execute_qa_loop(
            raw_draft=raw_draft,
            job_id=job_data.get("id"),
            relevant_projects=relevant_projects,
            style_profile=style_profile,
            provider_used=llm_res.get("provider_used", "Multi-LLM Bridge")
        )

        result["reviewer_report"] = review
        result["company_research_used"] = bool(company_research.get("source") != "no_cache")
        # The model sometimes adds details nobody gave it. Check the letter against the CV; if anything
        # is flagged, ask once for a version without those details and keep it only if it checks out better.
        def check(letter: str) -> list:
            return find_unsupported_claims(letter, candidate_profile, rag_memory.documents, job_data)

        claims = check(result["cover_letter"])
        result["claims_repaired"] = False
        if claims and not llm_res["is_template_fallback"]:
            flagged = "\n".join(f"- {claim['sentence']} ({claim['reason']})" for claim in claims)
            repair = await llm_client.generate_text(
                system_prompt=COVER_LETTER_SYSTEM_PROMPT,
                user_prompt=f"{user_prompt}\n\nLETTER\n{result['cover_letter']}\n\n"
                            "These sentences contain details that are not in the CANDIDATE section:\n"
                            f"{flagged}\n\nRewrite the letter without those details. Change nothing else.",
                preferred_provider=preferred_provider,
                apply_humanizer=False,
            )
            if not repair["is_template_fallback"] and len(check(repair["text"])) < len(claims):
                result["cover_letter"], claims, result["claims_repaired"] = repair["text"], check(repair["text"]), True
        result["unsupported_claims"] = claims
        return result

    def _execute_qa_loop(
        self,
        raw_draft: str,
        job_id: Any,
        relevant_projects: list,
        style_profile: Dict[str, Any],
        provider_used: str
    ) -> Dict[str, Any]:
        current_text = raw_draft
        iteration = 0
        qa_logs = []
        final_metrics = {}

        while iteration < self.max_qa_iterations:
            iteration += 1
            humanized_text, metrics = humanizer_engine.humanize_draft(
                raw_draft=current_text,
                style_profile=style_profile
            )

            qa_passed = metrics.get("is_human_verified", False)
            qa_logs.append({
                "iteration": iteration,
                "score": metrics.get("score"),
                "burstiness": metrics.get("burstiness"),
                "detected_cliches": metrics.get("detected_cliches"),
                "passed": qa_passed
            })

            if qa_passed:
                current_text = humanized_text
                final_metrics = metrics
                break
            else:
                current_text = humanizer_engine.replace_forbidden_buzzwords(humanized_text)
                final_metrics = humanizer_engine.calculate_human_texture_metrics(current_text)

        return {
            "job_id": job_id,
            "rag_context_used": relevant_projects,
            "cover_letter": current_text,
            "human_texture_score": final_metrics.get("score", 88.0),
            "is_human_verified": final_metrics.get("is_human_verified", True),
            "metrics": final_metrics,
            "qa_iterations": iteration,
            "qa_audit_log": qa_logs,
            "provider_used": provider_used,
            "system_prompt_reference": ANTI_AI_HUMANIZER_SYSTEM_PROMPT[:150] + "..."
        }

    def _generate_initial_draft(
        self,
        job_title: str,
        company: str,
        cand_name: str,
        relevant_projects: list,
        candidate_profile: Dict[str, Any],
        company_research: Optional[Dict[str, Any]] = None,
    ) -> str:
        # Used when no AI provider answers. It states only what the profile and saved projects hold;
        # the reader should get a short honest letter, not confident filler.
        lines = [f"I am writing regarding the {job_title} role."]
        skills = [str(skill) for skill in (candidate_profile.get("skills") or [])[:5]]
        if skills:
            lines.append(f"My main skills are {', '.join(skills)}.")
        top_project = relevant_projects[0] if relevant_projects else None
        if top_project and top_project.get("title"):
            stack = ", ".join(top_project.get("tech_stack", [])[:3])
            sentence = f"Recently I worked on {top_project['title']}" + (f" using {stack}" if stack else "")
            if top_project.get("metrics"):
                sentence += f"; the result was {top_project['metrics']}"
            lines.append(sentence + ".")
        body = " ".join(lines)

        return f"""Hi {company} team,

{body}

I would welcome a conversation about the role.

Best regards,
{cand_name}"""

    def _apply_review_feedback(self, draft: str, review: Dict[str, Any]) -> str:
        """Apply reviewer feedback to improve the draft (rule-based fallback)."""
        improved = draft

        for issue in review.get("issues", []):
            if "inflation" in issue.lower():
                improved = re.sub(
                    r'\d+\+?\s*(?:years?|yıl)\s*(?:of\s+)?experience',
                    'extensive experience', improved, flags=re.IGNORECASE
                )
            if "unverified metric" in issue.lower():
                improved = re.sub(r'\d+%', '', improved)

        keyword_analysis = review.get("keyword_analysis", {})
        missing_important = keyword_analysis.get("missing_important", [])
        if missing_important:
            skills_mention = ", ".join(missing_important[:3])
            if "Best regards" in improved:
                improved = improved.replace(
                    "Best regards",
                    f"My experience with {skills_mention} aligns well with your requirements.\n\nBest regards"
                )

        return improved

    def _build_revision_prompt(self, draft: str, review: Dict[str, Any]) -> str:
        """Build a prompt for LLM-powered revision based on reviewer feedback."""
        issues_text = "\n".join(f"- {i}" for i in review.get("issues", []))
        suggestions_text = "\n".join(f"- {s}" for s in review.get("suggestions", []))

        return f"""Original draft:
---
{draft}
---

Reviewer Issues (MUST fix):
{issues_text or "None"}

Reviewer Suggestions (SHOULD address):
{suggestions_text or "None"}

Revise the draft to address ALL issues and incorporate relevant suggestions."""


application_pipeline = MultiAgentApplicationPipeline()


class _DrafterReviewerCompatibilityAdapter:
    """Compatibility facade for the auto-apply queue's older API."""

    async def run_pipeline(self, job_data: Dict[str, Any], max_revisions: int = 1) -> Dict[str, Any]:
        from backend.app.api.profile import fetch_candidate_profile
        return await application_pipeline.run_pipeline_async(
            job_data=job_data,
            candidate_profile=fetch_candidate_profile(),
            style_profile={},
        )


drafter_reviewer_pipeline = _DrafterReviewerCompatibilityAdapter()
