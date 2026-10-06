"use client";
import { notify } from "@/lib/notify";
import { useLanguage } from "@/lib/i18n";

import { useEffect, useState } from "react";
import { DragDropContext, Droppable, Draggable, type DropResult } from "@hello-pangea/dnd";
import {
  KanbanSquare,
  Sparkles,
  CheckCircle2,
  Clock,
  ShieldCheck,
  HelpCircle,
  Eye,
  ExternalLink,
  X,
  Cpu
} from "lucide-react";
import Link from "next/link";
import { buildApiUrl, fetchFromApi } from "@/lib/api";
import { getExternalJobUrl } from "@/lib/job-links";

const STAGES = ["Draft", "Human Review", "Applied", "Interview", "Offer", "Rejected"];

export default function KanbanPage() {
  const { translate: t } = useLanguage();
  const [board, setBoard] = useState<Record<string, any[]>>({});
  const [, setLoading] = useState(true);
  const [selectedJob, setSelectedJob] = useState<any>(null);
  const [pendingSubmission, setPendingSubmission] = useState<any>(null);
  const [generating, setGenerating] = useState<string | null>(null);
  const [approving, setApproving] = useState(false);
  const [confirmingSubmission, setConfirmingSubmission] = useState(false);
  const [statusHistory, setStatusHistory] = useState<any[]>([]);

  // Form Question Modal Test
  const [testQuestion, setTestQuestion] = useState("How many years of work experience do you have with Python?");
  const [questionResult, setQuestionResult] = useState<any>(null);
  const [testingQuestion, setTestingQuestion] = useState(false);
  const [selectedLlmProvider, setSelectedLlmProvider] = useState("auto");
  const [clPdfTheme, setClPdfTheme] = useState("navy");

  async function loadBoard() {
    try {
      setLoading(true);
      const res = await fetchFromApi("/outcome/kanban");
      setBoard(res || {});
    } catch (cause: any) {
      notify(cause?.message || t("Başvurular yüklenemedi."));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadBoard();
  }, []);

  useEffect(() => {
    const jobId = selectedJob?.job_id || selectedJob?.id;
    if (!jobId) {
      setStatusHistory([]);
      return;
    }
    fetchFromApi(`/outcome/status-history/${encodeURIComponent(jobId)}`)
      .then((result) => setStatusHistory(result.history || []))
      .catch(() => setStatusHistory([]));
  }, [selectedJob?.job_id, selectedJob?.id]);

  async function handleGeneratePackage(jobId: string) {
    try {
      setGenerating(jobId);
      const res = await fetchFromApi("/apply/generate_package", {
        method: "POST",
        body: JSON.stringify({ job_id: jobId, provider: selectedLlmProvider })
      });
      await loadBoard();
      // Open modal to review
      setSelectedJob({ ...res, id: jobId });
    } finally {
      setGenerating(null);
    }
  }

  async function handleApprove(jobId: string) {
    try {
      setApproving(true);
      const approvedJob = selectedJob;
      await fetchFromApi("/outcome/update_status", {
        method: "POST",
        body: JSON.stringify({
          job_id: jobId,
          new_status: "Applied",
          final_cover_letter: selectedJob?.cover_letter
        })
      });
      setSelectedJob(null);
      setPendingSubmission({
        id: jobId,
        title: approvedJob?.title || "İlan",
        company: approvedJob?.company || "Şirket",
      });
      await loadBoard();
    } finally {
      setApproving(false);
    }
  }

  async function handleMoveStage(jobId: string, nextStage: string) {
    try {
      await fetchFromApi("/outcome/update_status", {
        method: "POST",
        body: JSON.stringify({ job_id: jobId, new_status: nextStage })
      });
      await loadBoard();
      if (nextStage === "Applied") {
        const movedJob = Object.values(board)
          .flat()
          .find((job: any) => String(job.id) === String(jobId));
        setPendingSubmission({
          id: jobId,
          title: movedJob?.title || "İlan",
          company: movedJob?.company || "Şirket",
        });
      }
    } catch (error) {
      console.error("Kanban stage update failed", error);
      notify(t("Aşama güncellenemedi."));
    }
  }

  async function handleDragEnd(result: DropResult) {
    const destination = result.destination;
    if (!destination || result.source.droppableId === destination.droppableId) return;
    await handleMoveStage(result.draggableId, destination.droppableId);
  }

  async function handleConfirmSubmission() {
    if (!pendingSubmission) return;
    try {
      setConfirmingSubmission(true);
      await fetchFromApi("/outcome/confirm_submission", {
        method: "POST",
        body: JSON.stringify({
          job_id: pendingSubmission.id,
          execution_mode: "live",
          message: "Portal gönderimi kullanıcı tarafından doğrulandı.",
        }),
      });
      setPendingSubmission(null);
      await loadBoard();
    } finally {
      setConfirmingSubmission(false);
    }
  }

  async function handleTestFormQuestion() {
    if (!testQuestion.trim()) return;
    try {
      setTestingQuestion(true);
      const res = await fetchFromApi("/apply/form_answer", {
        method: "POST",
        body: JSON.stringify({ question: testQuestion })
      });
      setQuestionResult(res);
    } catch {
      notify(t("Form sorusu test edilemedi."));
    } finally {
      setTestingQuestion(false);
    }
  }

  function nextStepLabel(kind: string): string {
    switch (kind) {
      case "follow_up": return t("Takip mesajı hazırla");
      case "decision_maker": return t("Karar vericiyi bul");
      case "interview_sim": return t("Mülakat provası yap");
      case "star_prep": return t("STAR yanıtlarını hazırla");
      case "salary_intel": return t("Maaş aralığına bak");
      case "offer_review": return t("Teklifi değerlendir");
      case "upskill": return t("Eksik becerileri kapat");
      default: return kind;
    }
  }

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <KanbanSquare className="w-6 h-6 text-blue-500" />
            {t("Başvurular")}</h1>
          <p className="text-xs text-slate-400 mt-1">
            {t("Başvurularını aşamalara göre takip et.")}</p>
        </div>

        {/* Tools row: LLM Model selector & Dynamic Form Memory Quick Tool */}
        <div className="flex flex-wrap items-center gap-3">
          <div className="p-2.5 bg-[#0e1524] border border-slate-800 rounded-xl flex items-center gap-2 text-xs">
            <Cpu className="w-4 h-4 text-blue-400 shrink-0" />
            <span className="text-slate-400 font-medium">{t("Model:")}</span>
            <select
              value={selectedLlmProvider}
              onChange={(e) => setSelectedLlmProvider(e.target.value)}
              className="bg-slate-900 border border-slate-800 rounded-lg px-2.5 py-1 text-white text-xs focus:outline-none focus:border-blue-500"
            >
              <option value="auto">{t("Auto (Otomatik Tespit)")}</option>
              <option value="openai">{t("OpenAI (GPT-4o)")}</option>
              <option value="gemini">{t("Google Gemini (1.5 Flash)")}</option>
              <option value="anthropic">{t("Claude 3.5 Sonnet")}</option>
              <option value="deepseek">{t("DeepSeek Chat")}</option>
              <option value="ollama">{t("Yerel Ollama (Llama 3)")}</option>
              <option value="local_fallback">{t("Fallback Hibrit Motor")}</option>
            </select>
          </div>

          <div className="p-2.5 bg-[#0e1524] border border-slate-800 rounded-xl flex items-center gap-2 text-xs">
            <HelpCircle className="w-4 h-4 text-amber-400 shrink-0" />
            <input
              type="text"
              value={testQuestion}
              onChange={(e) => setTestQuestion(e.target.value)}
              placeholder={t("Dinamik Easy Apply sorusu...")}
              className="bg-slate-900 border border-slate-800 rounded-lg px-2.5 py-1 text-white text-xs w-56"
            />
            <button
              onClick={handleTestFormQuestion}
              disabled={testingQuestion}
              className="bg-slate-800 hover:bg-slate-700 text-slate-200 px-3 py-1 rounded-lg font-medium"
            >
              {testingQuestion ? t("Sorgulanıyor...") : t("Form Hafızasından Çöz")}
            </button>
          </div>
        </div>
      </div>

      {questionResult && (
        <div className="p-3 rounded-xl bg-amber-500/10 border border-amber-500/20 text-xs flex items-center justify-between">
          <div>
            <span className="font-semibold text-amber-300">{t("Form Hafıza Yanıtı:")}</span>{" "}
            {questionResult.status === "REQUIRES_HUMAN_INPUT" ? (
              <span className="text-white">{t("Kayıtlı yanıt yok; bu soruyu kendin yanıtlamalısın.")}</span>
            ) : (
              <>
                <span className="text-white font-mono">{questionResult.answer}</span>{" "}
                <span className="text-slate-400 text-xs">({questionResult.source} {t("• Güven: %")} {Math.round(questionResult.confidence * 100)})</span>
              </>
            )}
          </div>
          <button onClick={() => setQuestionResult(null)} className="text-slate-400 hover:text-white">✕</button>
        </div>
      )}

      {/* Kanban Board Columns */}
      <DragDropContext onDragEnd={handleDragEnd}>
        <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-6 gap-4 overflow-x-auto pb-4">
          {STAGES.map((stage) => {
          const items = board[stage] || [];
          return (
            <Droppable droppableId={stage} key={stage}>
              {(provided, snapshot) => <div
                key={stage}
                ref={provided.innerRef}
                {...provided.droppableProps}
                className={`bg-[#0b101a] border rounded-2xl p-3 flex flex-col min-w-[210px] transition-all duration-200 ${
                  snapshot.isDraggingOver
                    ? "border-blue-400 bg-blue-500/10 shadow-lg shadow-blue-500/10 -translate-y-0.5"
                    : "border-slate-800/80"
                }`}
              >
              {/* Column Header */}
              <div className="flex items-center justify-between pb-3 mb-3 border-b border-slate-800/80">
                <span className="text-xs font-bold text-slate-200">{stage}</span>
                <span className="text-xs bg-slate-800 text-slate-400 px-2 py-0.5 rounded-full font-mono">
                  {items.length}
                </span>
              </div>
              <div className="text-xs text-slate-400 mb-2 uppercase tracking-wider">
                {t("Kartları sürükleyip bırakın")}</div>

              {/* Cards List */}
              <div className="space-y-3 flex-1 overflow-y-auto max-h-[680px]">
                {items.length === 0 ? (
                  <div className="text-xs text-slate-400 text-center py-8">{t("İlan yok")}</div>
                ) : (
                  items.map((job, index) => (
                    <Draggable draggableId={String(job.id)} index={index} key={job.id}>
                      {(dragProvided, dragSnapshot) => <div
                      key={job.id}
                      ref={dragProvided.innerRef}
                      {...dragProvided.draggableProps}
                      {...dragProvided.dragHandleProps}
                      className={`p-3.5 rounded-xl bg-slate-900/80 border border-slate-800 hover:border-blue-500/60 hover:shadow-lg hover:shadow-blue-500/5 transition space-y-2.5 shadow-sm cursor-grab active:cursor-grabbing ${dragSnapshot.isDragging ? "rotate-1 shadow-2xl shadow-blue-500/20" : ""}`}
                    >
                      <div className="flex justify-between items-start gap-1">
                        <span className="text-xs font-bold text-white line-clamp-1">{job.title}</span>
                      </div>
                      <div className="text-xs text-slate-400 font-medium">{job.company}</div>
                      {getExternalJobUrl(job.url) && <a href={getExternalJobUrl(job.url)!} target="_self" onClick={(event) => event.stopPropagation()} draggable={false} className="inline-flex items-center gap-1 text-xs font-semibold text-emerald-300 hover:text-emerald-200">
                        {t("Kaynak ilanda aç")}<ExternalLink className="h-3 w-3" />
                      </a>}

                      <div className="flex items-center justify-between text-xs pt-1">
                        <span className="text-blue-400 uppercase font-mono">{job.platform}</span>
                        <span className="text-emerald-400 font-bold font-mono">≈ %{job.match_score ?? "—"} {t("Tahmini uyum")}</span>
                      </div>

                      {/* Actions according to Stage */}
                      {stage === "Draft" && (
                        <button
                          onClick={() => handleGeneratePackage(job.id)}
                          disabled={generating === job.id}
                          className="w-full mt-2 bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold py-1.5 rounded-lg transition flex items-center justify-center gap-1 shadow-md shadow-blue-600/20 disabled:opacity-50"
                        >
                          <Sparkles className="w-3 h-3" />
                          {generating === job.id ? t("Üretiliyor...") : t("Apply Paketi Üret")}
                        </button>
                      )}

                      {stage === "Human Review" && (
                        <div className="space-y-1.5 pt-1">
                          <div className="text-xs text-emerald-400 bg-emerald-500/10 px-1.5 py-0.5 rounded flex items-center justify-between">
                            <span>{t("İnsansı Doku:")}</span>
                            <strong>{job.human_texture_score == null ? "—" : `%${job.human_texture_score}`}</strong>
                          </div>
                          <button
                            onClick={() => setSelectedJob(job)}
                            className="w-full bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold py-1.5 rounded-lg transition flex items-center justify-center gap-1"
                          >
                            <Eye className="w-3 h-3" /> {t("İncele & Onayla")}</button>
                        </div>
                      )}

                      {stage === "Applied" && (
                        <div className="pt-1 flex gap-1">
                          <button
                            onClick={() => handleMoveStage(job.id, "Interview")}
                            className="flex-1 bg-emerald-600 hover:bg-emerald-500 text-white text-xs py-1 rounded transition text-center font-medium"
                          >
                            {t("Mülakata Geç →")}</button>
                        </div>
                      )}

                      {stage === "Interview" && (
                        <div className="pt-1 flex gap-1">
                          <button
                            onClick={() => handleMoveStage(job.id, "Offer")}
                            className="flex-1 bg-amber-600 hover:bg-amber-500 text-white text-xs py-1 rounded transition text-center font-medium"
                          >
                            {t("Teklif Alındı")}</button>
                        </div>
                      )}

                      {stage === "Offer" && (
                        <div className="text-xs text-amber-400 text-center font-semibold bg-amber-500/10 py-1 rounded">
                          {t("Pazarlık Ajanı Bekliyor")}</div>
                      )}

                      {job.is_template_fallback && (
                        <div className="rounded bg-red-500/10 px-1.5 py-0.5 text-xs font-semibold text-red-300">{t("Şablon metin · yapay zekâ yazmadı")}</div>
                      )}

                      {(job.next_steps || []).length > 0 && (
                        <div className="border-t border-slate-800 pt-2">
                          <div className="text-xs font-semibold uppercase tracking-wide text-slate-400">{t("Sıradaki adım")}</div>
                          <div className="mt-1 flex flex-wrap gap-1">
                            {job.next_steps.map((step: { kind: string; href: string }) => (
                              <Link
                                key={step.kind}
                                href={step.href}
                                onClick={(event) => event.stopPropagation()}
                                draggable={false}
                                className="rounded bg-slate-800 px-1.5 py-0.5 text-xs font-medium text-blue-300 hover:bg-slate-700"
                              >
                                {nextStepLabel(step.kind)}
                              </Link>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>}
                    </Draggable>
                  ))
                )}
                {provided.placeholder}
              </div>
              </div>}
            </Droppable>
          );
          })}
        </div>
      </DragDropContext>

      {/* Human-in-the-Loop Review Modal */}
      {selectedJob && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-[#0e1524] border border-slate-800 rounded-2xl w-full max-w-3xl max-h-[90vh] flex flex-col shadow-2xl">
            {/* Header */}
            <div className="p-5 border-b border-slate-800 flex justify-between items-center">
              <div>
                <h2 className="text-base font-bold text-white flex items-center gap-2">
                  <ShieldCheck className="w-5 h-5 text-emerald-400" />
                  {t("Onayını bekleyenler")}</h2>
                <p className="text-xs text-slate-400 mt-0.5">
                  {t("Anti-AI Humanizer Engine tarafından arındırılmış metin adayın kontrolüne sunulur.")}</p>
              </div>
              <button
                onClick={() => setSelectedJob(null)}
                className="text-slate-400 hover:text-white p-1"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Modal Body */}
            <div className="p-6 space-y-4 overflow-y-auto flex-1 text-xs">
              <section className="rounded-xl border border-slate-800 bg-slate-900/60 p-3">
                <div className="mb-2 flex items-center gap-2 text-xs font-semibold text-slate-200"><Clock className="h-3.5 w-3.5 text-sky-300" />{t("Başvuru geçmişi")}</div>
                {statusHistory.length === 0 ? <p className="text-xs text-slate-400">{t("Henüz durum geçmişi yok")}</p> : <div className="space-y-1.5">{statusHistory.slice(0, 6).map((item) => <div key={item.id} className="flex flex-wrap items-center justify-between gap-2 text-xs"><span className="text-slate-300">{item.from_status} → <strong className="text-white">{item.to_status}</strong></span><span className="text-slate-400">{item.created_at}</span></div>)}</div>}
              </section>

              {/* Cultural Tone & Multilingual Switcher */}
              <div className="space-y-1.5 p-3 rounded-xl bg-slate-900/60 border border-slate-800">
                <div className="flex justify-between items-center text-xs">
                  <span className="font-semibold text-slate-300">{t("Bölgesel / Kültürel Dil Adaptasyonu:")}</span>
                  <div className="flex gap-1.5">
                    <button
                      type="button"
                      onClick={async () => {
                        const res = await fetchFromApi("/apply/multilingual", {
                          method: "POST",
                          body: JSON.stringify({ culture_code: "kosovo_sq", job_id: selectedJob.job_id || selectedJob.id })
                        });
                        setSelectedJob({ ...selectedJob, cover_letter: res.cover_letter });
                      }}
                      className="px-2 py-0.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium"
                    >
                      {t("Kosova (Shqip)")}</button>
                    <button
                      type="button"
                      onClick={async () => {
                        const res = await fetchFromApi("/apply/multilingual", {
                          method: "POST",
                          body: JSON.stringify({ culture_code: "turkey_tr", job_id: selectedJob.job_id || selectedJob.id })
                        });
                        setSelectedJob({ ...selectedJob, cover_letter: res.cover_letter });
                      }}
                      className="px-2 py-0.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium"
                    >
                      {t("Türkiye (Türkçe)")}</button>
                    <button
                      type="button"
                      onClick={async () => {
                        const res = await fetchFromApi("/apply/multilingual", {
                          method: "POST",
                          body: JSON.stringify({ culture_code: "global_en", job_id: selectedJob.job_id || selectedJob.id })
                        });
                        setSelectedJob({ ...selectedJob, cover_letter: res.cover_letter });
                      }}
                      className="px-2 py-0.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium"
                    >
                      {t("Global (English)")}</button>
                  </div>
                </div>
              </div>

              {/* Model Provider Info Badge */}
              {selectedJob.provider_used && (
                <div className="flex items-center justify-between text-xs text-slate-400 bg-slate-900/80 px-3.5 py-2 rounded-xl border border-slate-800">
                  <div className="flex items-center gap-2">
                    <Cpu className="w-3.5 h-3.5 text-blue-400" />
                    <span>{t("Üreten AI Motoru:")}</span>
                    <strong className="text-white font-mono">{selectedJob.provider_used}</strong>
                  </div>
                  <span className="text-xs text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded font-mono">
                    {t("Human-Verified")}</span>
                </div>
              )}

              {/* Cover Letter Edit Area & PDF Tools */}
              <div className="space-y-2">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                  <label className="text-xs font-semibold text-slate-300">
                    {t("Özelleştirilmiş Niyet Mektubu (Cover Letter):")}</label>

                  {/* PDF Theme & Action Buttons */}
                  <div className="flex items-center gap-2 text-xs">
                    <div className="flex items-center gap-1 bg-slate-900 px-2 py-1 rounded-lg border border-slate-800">
                      <span className="text-xs text-slate-400">{t("Tema:")}</span>
                      {["navy", "charcoal", "slate", "emerald"].map((t) => (
                        <button
                          key={t}
                          type="button"
                          onClick={() => setClPdfTheme(t)}
                          className={`px-1.5 py-0.5 rounded capitalize text-xs transition ${
                            clPdfTheme === t ? "bg-blue-600 text-white font-semibold" : "text-slate-400 hover:text-white"
                          }`}
                        >
                          {t}
                        </button>
                      ))}
                    </div>

                    <a
                      href={buildApiUrl(`/apply/preview_cover_letter_pdf?job_id=${selectedJob.job_id || selectedJob.id}&theme=${clPdfTheme}`)}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="bg-slate-800 hover:bg-slate-700 text-slate-200 px-2.5 py-1 rounded-lg transition flex items-center gap-1 border border-slate-700"
                    >
                      <Eye className="w-3 h-3 text-blue-400" /> {t("Önizle")}</a>

                    <a
                      href={buildApiUrl(`/apply/download_cover_letter_pdf?job_id=${selectedJob.job_id || selectedJob.id}&theme=${clPdfTheme}`)}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="bg-blue-600 hover:bg-blue-500 text-white font-semibold px-2.5 py-1 rounded-lg transition flex items-center gap-1 shadow-md shadow-blue-600/20"
                    >
                      {t("PDF İndir")}</a>
                  </div>
                </div>

                {selectedJob.is_template_fallback && (
                  <div role="alert" className="rounded-xl border border-red-500/40 bg-red-500/10 px-4 py-3 text-xs text-red-200">
                    <strong>{t("Bu metni yapay zekâ yazmadı.")}</strong>{" "}
                    {t("Yapay zekâ sağlayıcısı yanıt vermediği için genel bir şablon kullanıldı; ilana ve sana özel değil. Göndermeden önce yeniden üret ya da kendin yaz.")}
                  </div>
                )}
                <textarea
                  value={selectedJob.cover_letter || ""}
                  onChange={(e) => setSelectedJob({ ...selectedJob, cover_letter: e.target.value })}
                  className="w-full h-44 bg-slate-950 border border-slate-800 rounded-xl p-3 text-xs text-slate-200 leading-relaxed font-sans focus:outline-none focus:border-blue-500"
                ></textarea>
              </div>

              {/* Micro-Portfolio Case Study Preview */}
              {selectedJob.micro_portfolio && (
                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-slate-300">
                    {t("İlana Özel Micro-Case Study (Micro-Project Synthesizer):")}</label>
                  <pre className="p-3 bg-slate-950 border border-slate-800 rounded-xl text-xs text-slate-300 font-mono whitespace-pre-wrap max-h-36 overflow-y-auto">
                    {selectedJob.micro_portfolio}
                  </pre>
                </div>
              )}
            </div>

            {/* Modal Footer */}
            <div className="p-4 border-t border-slate-800 flex items-center justify-between">
              <span className="text-xs text-slate-400">
                {t("Onay verildiğinde 7. ve 14. gün kibar takip otomasyonu devreye girer.")}</span>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={async () => {
                    try {
                      const result = await fetchFromApi("/scrape/playwright_apply", {
                        method: "POST",
                        body: JSON.stringify({ job_id: selectedJob.job_id || selectedJob.id })
                      });
                      notify(result.message || result.status);
                      // Only a session that really opened the posting counts as a step forward.
                      if (!["INSPECTED", "SUBMIT_ATTEMPTED"].includes(result.status)) return;
                      await handleApprove(selectedJob.job_id || selectedJob.id);
                    } catch {
                      notify(t("Tarayıcı oturumu başlatılamadı."));
                    }
                  }}
                  className="bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-xs px-4 py-2.5 rounded-xl transition flex items-center gap-1.5"
                >
                  <Sparkles className="w-3.5 h-3.5" /> {t("Playwright ile Otonom Başvur")}</button>
                <button
                  onClick={() => handleApprove(selectedJob.job_id || selectedJob.id)}
                  disabled={approving}
                  className="bg-emerald-600 hover:bg-emerald-500 text-white font-semibold text-xs px-5 py-2.5 rounded-xl transition flex items-center gap-1.5 shadow-lg shadow-emerald-600/20"
                >
                  <CheckCircle2 className="w-4 h-4" />
                  {approving ? t("Başvuruluyor...") : t("İnsansı Doku Onaylandı & Başvur")}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* External submission confirmation after an Applied drag-and-drop */}
      {pendingSubmission && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-[#0e1524] border border-amber-500/30 rounded-2xl w-full max-w-lg p-6 space-y-5 shadow-2xl shadow-amber-950/20">
            <div className="flex items-start gap-3">
              <div className="w-10 h-10 rounded-xl bg-amber-500/10 border border-amber-500/20 flex items-center justify-center">
                <Clock className="w-5 h-5 text-amber-400" />
              </div>
              <div>
                <h2 className="text-base font-bold text-white">{t("Portal gönderimi doğrulansın mı?")}</h2>
                <p className="text-xs text-slate-400 mt-1">
                  {pendingSubmission.company} — {pendingSubmission.title}
                </p>
              </div>
            </div>
            <div className="rounded-xl border border-slate-800 bg-slate-950/70 p-3 text-xs leading-relaxed text-slate-300">
              {t("Kart Kanban’da")}<strong className="text-amber-300">{t("Applied")}</strong> {t("aşamasına taşındı; bu işlem tek başına portalda gerçek başvuru yapıldığını göstermez. Yalnızca portal gönderimini gerçekten gördüyseniz doğrulayın.")}</div>
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setPendingSubmission(null)}
                className="px-3 py-2 rounded-lg border border-slate-700 text-slate-300 text-xs hover:bg-slate-800"
              >
                {t("Henüz değil")}</button>
              <button
                onClick={handleConfirmSubmission}
                disabled={confirmingSubmission}
                className="px-3 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold disabled:opacity-50"
              >
                {confirmingSubmission ? "Kaydediliyor..." : t("Portal gönderimini doğrula")}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
