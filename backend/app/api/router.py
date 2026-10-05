"""
Unified FastAPI Router
Exposes endpoints for Setup (1.1), Scrape (1.2), Rank (1.3), Apply (1.4),
Interview (1.5), Outcome (1.6), and TestSprite (1.7).
"""

import json
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Query, UploadFile, File, Form, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from backend.app.core.database import get_db_connection
from backend.app.api.profile import fetch_candidate_profile
from backend.app.core.event_logger import agent_logger
# Backward-compatible imports for integrations that imported voice handlers
# from this legacy router before the domain split.
from backend.app.api.routers.voice import (
    VoiceAnalyzeRequest,
    VoiceQuestionRequest,
    analyze_voice_interview_transcript,
    generate_interviewer_spoken_question,
)
from backend.app.api.routers.interview import (
    CounterLetterRequest,
    CounterOfferRequest,
    EvaluateOfferRequest,
    InterviewEvaluateRequest,
    InterviewStartRequest,
    evaluate_interview_response,
    evaluate_job_offer,
    generate_counter_offer,
    generate_counter_offer_letter,
    get_negotiation_objection_playbook,
    start_interview_simulation,
)
from backend.app.api.routers.integrations import (
    ClassifyEmailRequest,
    DiscordAlertRequest,
    SlackAlertRequest,
    classify_incoming_email,
    send_discord_webhook,
    send_slack_webhook,
)
from backend.app.api.routers.portfolio import PortfolioGenerateRequest, generate_personal_portfolio
from backend.app.api.routers.daemon import (
    get_daemon_status,
    start_autonomous_daemon,
    stop_autonomous_daemon,
    trigger_morning_prep_now,
    trigger_nightly_sweep_now,
)
from backend.app.api.routers.search import (
    SemanticSearchQuery,
    SimilarJobsQuery,
    find_similar_jobs,
    get_market_skill_trends,
    index_jobs_for_vector_search,
    search_jobs_semantically,
)
from backend.app.api.routers.tracking import (
    AddSeenJobRequest,
    MarkSeenJobRequest,
    ScoreSeenJobRequest,
    add_seen_job,
    export_seen_jobs,
    get_closing_soon_jobs,
    get_new_seen_jobs,
    get_ranked_seen_jobs,
    get_seen_jobs_stats,
    mark_seen_job_status,
    score_seen_job,
    sweep_expired_jobs,
)
from backend.app.api.routers.outcome import (
    router as outcome_router,
    ConfirmSubmissionRequest,
    get_analytics,
    get_kanban_pipeline,
    update_kanban_status,
    confirm_submission,
)
from backend.app.api.routers.setup import (
    router as setup_router,
    AddProjectRequest,
    ProfileUpdateRequest,
    StylometryRequest,
    add_rag_project,
    generate_stylometry_profile,
    get_discovered_roles,
    get_profile,
    get_rag_projects,
    update_profile,
)
from backend.app.api.routers.scrape import (
    router as scrape_router,
    AnalyzeOnTheFlyRequest,
    ScrapeRequest,
    analyze_job_on_the_fly,
    clear_linkedin_session,
    execute_playwright_apply,
    get_account_health,
    get_all_jobs,
    get_linkedin_session_status,
    rank_jobs,
    sync_linkedin_session,
    trigger_scrape,
)
from backend.app.api.routers.inbox import (
    router as inbox_router,
    ApproveReplyRequest,
    ConnectMockOAuthRequest,
    DispatchScrapeRequest,
    DisconnectOAuthRequest,
    SimulateEmailRequest,
    SyncOAuthEmailsRequest,
    connect_oauth_instant,
    disconnect_oauth_account,
    dispatch_scrape_queue,
    get_google_oauth_url,
    get_inbox_messages,
    get_microsoft_oauth_url,
    get_oauth_status,
    get_task_queue_status,
    handle_google_oauth_callback,
    handle_microsoft_oauth_callback,
    send_inbox_reply,
    simulate_incoming_email,
    sync_oauth_inbox,
)
from backend.app.api.routers.profile_features import (
    router as profile_features_router,
    BehavioralAnswersRequest,
    BuildStyleGuideRequest,
    CareerPivotRequest,
    CulturalFitRequest,
    STARAnswerRequest,
    STARQuestionsRequest,
    StyleComplianceRequest,
    auto_fix_style,
    build_behavioral_profile,
    build_writing_style,
    check_cultural_fit,
    check_style_compliance,
    discover_career_paths,
    extract_star_candidates,
    generate_career_roadmap,
    get_behavioral_questions,
    get_star_categories,
    get_star_questions,
    get_writing_style_presets,
    score_star_answer,
)
from backend.app.api.routers.platform_tools import (
    router as platform_tools_router,
    AuditJobKeysRequest,
    CompanyCacheGetRequest,
    CompanyCacheInvalidateRequest,
    CompanyCachePutRequest,
    CompanyResearchRequest,
    FullHealthReportRequest,
    JobKeyRequest,
    PortalHealthRequest,
    RobotsCheckRequest,
    VerifyLayoutRequest,
    VerifyPDFRequest,
    WebResearchFetchRequest,
    audit_job_keys,
    check_portal_health,
    full_portal_health_report,
    generate_job_key,
    get_company_cache,
    invalidate_company_cache,
    list_company_cache,
    put_company_cache,
    robots_check_endpoint,
    verify_layout_endpoint,
    verify_pdf_endpoint,
    web_research_company,
    web_research_fetch,
)
from backend.app.api.routers.application import (
    router as application_router,
    ApplyPackageRequest,
    EmailFinderRequest,
    FormAnswerRequest,
    MultilingualRequest,
    SaveFormMemoryRequest,
    SmtpOutreachRequest,
    adapt_culture_language,
    answer_form_question,
    download_ats_cv,
    download_cover_letter_pdf,
    find_decision_maker_email,
    generate_application_package,
    preview_ats_cv,
    preview_cover_letter_pdf,
    save_form_memory,
    send_outreach_email,
)
from backend.app.api.routers.intelligence import (
    router as intelligence_router,
    ApplyScoresRequest,
    NotionSyncBatchRequest,
    NotionSyncJobRequest,
    RankCandidatesRequest,
    SalaryAddRequest,
    SalaryImportRequest,
    SalarySearchRequest,
    SweepRequest,
    UpskillPathRequest,
    UpskillProgressRequest,
    add_salary_entry,
    apply_rank_scores,
    generate_job_search_report,
    generate_learning_path,
    generate_pipeline_report,
    get_notion_status,
    get_ranking_summary,
    get_upskill_progress,
    import_salary_data,
    rank_sweep,
    salary_stats,
    search_salary,
    sync_batch_to_notion,
    sync_job_to_notion,
    update_upskill_progress,
    validate_salary_data,
    get_rank_candidates,
)
from backend.app.api.routers.operations import (
    router as operations_router,
    LLMGenerateRequest,
    SetProviderRequest,
    TelegramAlertRequest,
    TelegramCommandRequest,
    TestConnectionRequest,
    VoiceEvaluateRequest,
    call_llm_provider,
    evaluate_voice_answer,
    get_agent_logs,
    get_llm_providers,
    get_voice_personas,
    run_testsprite_suite,
    set_active_llm_provider,
    telegram_dispatch_briefing,
    telegram_handle_command,
    telegram_send_notification,
    telegram_status,
    test_llm_connection,
)
from backend.app.api.routers.orchestration import (
    router as orchestration_router,
    AuditGitHubRequest,
    CalendarEventRequest,
    GenerateCadenceRequest,
    GenerateOutreachRequest,
    OptimizeLinkedInRequest,
    OutreachStatusRequest,
    RouteGenerateRequest,
    create_google_calendar_url,
    dispatch_weekly_digest,
    generate_cold_outreach,
    generate_follow_up_cadence,
    get_llm_cost_metrics,
    get_pending_follow_ups,
    get_weekly_digest,
    list_cold_outreach,
    optimize_linkedin_profile,
    audit_github_presence,
    route_and_generate_llm,
    update_outreach_status,
    websocket_event_channel,
)
from backend.app.api.routers.auto_apply import router as auto_apply_router
from backend.app.api.routers.system import router as system_router
router = APIRouter()
router.include_router(outcome_router)
router.include_router(setup_router)
router.include_router(scrape_router)
router.include_router(inbox_router)
router.include_router(profile_features_router)
router.include_router(platform_tools_router)
router.include_router(application_router)
router.include_router(intelligence_router)
router.include_router(operations_router)
router.include_router(orchestration_router)
router.include_router(auto_apply_router)
router.include_router(system_router)
