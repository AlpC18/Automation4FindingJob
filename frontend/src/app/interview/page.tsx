"use client";
import { notify } from "@/lib/notify";
import dynamic from "next/dynamic";
import PageTabs from "@/components/PageTabs";
import { useLanguage } from "@/lib/i18n";

import { useEffect, useState, useRef } from "react";
import {
  MessageSquare,
  Sparkles,
  DollarSign,
  Send,
  Copy,
  Check,
  Volume2,
  Mic,
  MicOff,
  Zap
} from "lucide-react";
import { fetchFromApi } from "@/lib/api";

function InterviewPage() {
  const { translate: t } = useLanguage();
  const [jobs, setJobs] = useState<any[]>([]);
  const [selectedJobId, setSelectedJobId] = useState("");
  const [questions, setQuestions] = useState<any[]>([]);
  const [currentQIndex, setCurrentQIndex] = useState(0);
  const [candidateAnswer, setCandidateAnswer] = useState("");
  const [evaluation, setEvaluation] = useState<any>(null);
  const [evaluating, setEvaluating] = useState(false);

  // Voice AI Coach State
  const [selectedPersona, setSelectedPersona] = useState("alex_vp");
  const [isRecording, setIsRecording] = useState(false);
  const [recordingSeconds, setRecordingSeconds] = useState(0);
  const [vocalEvaluation, setVocalEvaluation] = useState<any>(null);
  const [evaluatingVoice, setEvaluatingVoice] = useState(false);
  const [recognitionInstance, setRecognitionInstance] = useState<any>(null);

  // Counter Offer State
  const [initialOffer, setInitialOffer] = useState("");
  const [marketBench, setMarketBench] = useState("");
  const [targetAmount, setTargetAmount] = useState("");
  const [counterOfferDraft, setCounterOfferDraft] = useState<any>(null);
  const [generatingOffer, setGeneratingOffer] = useState(false);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    // Deep link from Kanban / today's tasks: /interview?job=<id> opens that job's rehearsal.
    // An application outlives its listing, so a linked job is looked up among archived ones too.
    const requested = new URLSearchParams(window.location.search).get("job");
    fetchFromApi(requested ? "/scrape/jobs?include_stale=true" : "/scrape/jobs").then((res) => {
      const jList = res.jobs || [];
      setJobs(jList);
      if (jList.length > 0) {
        const initial = jList.find((job: any) => String(job.id) === requested) || jList[0];
        setSelectedJobId(initial.id);
        startSession(initial.id);
      }
    });
  }, []);

  async function startSession(jobId: string) {
    const res = await fetchFromApi("/interview/start", {
      method: "POST",
      body: JSON.stringify({ job_id: jobId })
    });
    setQuestions(res.questions || []);
    setCurrentQIndex(0);
    setEvaluation(null);
    setCandidateAnswer("");
  }

  async function handleEvaluate() {
    if (!candidateAnswer.trim() || !questions[currentQIndex]) return;
    try {
      setEvaluating(true);
      const res = await fetchFromApi("/interview/evaluate", {
        method: "POST",
        body: JSON.stringify({
          question: questions[currentQIndex].question,
          answer: candidateAnswer
        })
      });
      setEvaluation(res);
    } finally {
      setEvaluating(false);
    }
  }

  // Voice AI Coach Handlers
  const timerRef = useRef<any>(null);

  function handleSpeakQuestion() {
    if (typeof window === "undefined" || !window.speechSynthesis) return;
    window.speechSynthesis.cancel();
    const textToSpeak = questions[currentQIndex]?.question || "";
    const utterance = new SpeechSynthesisUtterance(textToSpeak);
    utterance.rate = selectedPersona === "alex_vp" ? 1.05 : 0.95;
    utterance.lang = "en-US";
    window.speechSynthesis.speak(utterance);
  }

  function handleToggleSpeechRecognition() {
    if (typeof window === "undefined") return;
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SpeechRecognition) {
      notify(t("Tarayıcınız Web Speech API'yi desteklemiyor. Lütfen Chrome veya Brave kullanın veya yanıtınızı metin olarak girin."));
      return;
    }

    if (isRecording) {
      if (recognitionInstance) recognitionInstance.stop();
      setIsRecording(false);
      clearInterval(timerRef.current);
    } else {
      const rec = new SpeechRecognition();
      rec.continuous = true;
      rec.interimResults = true;
      rec.lang = "en-US";

      rec.onresult = (e: any) => {
        let transcript = "";
        for (let i = 0; i < e.results.length; i++) {
          transcript += e.results[i][0].transcript + " ";
        }
        setCandidateAnswer(transcript.trim());
      };

      rec.onerror = (err: any) => {
        console.error("Speech Recognition Error:", err);
        setIsRecording(false);
        clearInterval(timerRef.current);
      };

      rec.start();
      setRecognitionInstance(rec);
      setIsRecording(true);
      setRecordingSeconds(0);
      timerRef.current = setInterval(() => {
        setRecordingSeconds((prev) => prev + 1);
      }, 1000);
    }
  }

  async function handleVoiceEvaluate() {
    if (!candidateAnswer.trim() || !questions[currentQIndex]) return;
    try {
      setEvaluatingVoice(true);
      const res = await fetchFromApi("/interview/voice_evaluate", {
        method: "POST",
        body: JSON.stringify({
          question: questions[currentQIndex].question,
          transcript: candidateAnswer,
          duration_seconds: Math.max(recordingSeconds, 15)
        })
      });
      setVocalEvaluation(res);
    } finally {
      setEvaluatingVoice(false);
    }
  }

  async function handleGenerateCounterOffer() {
    try {
      setGeneratingOffer(true);
      const selectedJob = jobs.find((job) => job.id === selectedJobId);
      if (!selectedJob || !initialOffer.trim() || !marketBench.trim() || !targetAmount.trim()) return;
      const res = await fetchFromApi("/interview/counter_offer", {
        method: "POST",
        body: JSON.stringify({
          company_name: selectedJob.company,
          role_title: selectedJob.title,
          initial_offer: initialOffer,
          market_benchmark: marketBench,
          target_amount: targetAmount,
          special_requests: ""
        })
      });
      setCounterOfferDraft(res);
    } finally {
      setGeneratingOffer(false);
    }
  }

  const currentQ = questions[currentQIndex];

  return (
    <div className="space-y-8 max-w-6xl mx-auto">
      <div>
        <h1 className="text-2xl font-bold text-white flex items-center gap-2">
          <MessageSquare className="w-6 h-6 text-blue-500" />
          {t("Mülakat hazırlığı")}</h1>
        <p className="text-xs text-slate-400 mt-1">
          {t("Yapay zekanın soruyu sesli sorduğu, mikrofonunuzla yanıtladığınız, WPM ve dolgu kelime analizli Sesli Koçluk Sistemi.")}</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        
        {/* Left: Interactive & Voice Interview Simulator */}
        <div className="p-6 rounded-2xl bg-[#0e1524] border border-slate-800/80 space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
            <h2 className="text-sm font-semibold text-white flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-indigo-400" /> {t("Sesli Mülakat Simülatörü")}</h2>

            {/* Persona Selector */}
            <div className="flex items-center gap-1.5 text-xs bg-slate-900 p-1 rounded-xl border border-slate-800">
              <span className="text-xs text-slate-400 px-1">{t("Mülakatçı:")}</span>
              {[
                { id: "alex_vp", label: "Alex (VP Eng)" },
                { id: "elena_hr", label: "Elena (HR)" },
                { id: "marcus_principal", label: "Marcus (Architect)" }
              ].map((p) => (
                <button
                  key={p.id}
                  onClick={() => setSelectedPersona(p.id)}
                  className={`px-2 py-0.5 rounded text-xs font-medium transition ${
                    selectedPersona === p.id
                      ? "bg-indigo-600 text-white"
                      : "text-slate-400 hover:text-white"
                  }`}
                >
                  {p.label}
                </button>
              ))}
            </div>
          </div>

          {currentQ && (
            <div className="space-y-3">
              {/* Question Card with Audio Speak Button */}
              <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800 space-y-2">
                <div className="flex justify-between items-center">
                  <span className="text-xs bg-blue-500/10 text-blue-400 px-2 py-0.5 rounded uppercase font-mono">
                    {currentQ.type} {t("• Soru")}{currentQIndex + 1}/{questions.length}
                  </span>
                  <button
                    onClick={handleSpeakQuestion}
                    className="text-indigo-400 hover:text-indigo-300 text-xs flex items-center gap-1 bg-indigo-500/10 hover:bg-indigo-500/20 px-2.5 py-1 rounded-lg border border-indigo-500/20 transition"
                  >
                    <Volume2 className="w-3.5 h-3.5" /> {t("Soruyu Sesli Oku")}</button>
                </div>

                <p className="text-xs font-semibold text-slate-200 leading-relaxed">
                  {currentQ.question}
                </p>
                <div className="text-xs text-slate-400 pt-1">
                  <strong>{t("Beklenen Odaklar:")}</strong> {currentQ.key_points?.join(" • ")}
                </div>
              </div>

              {/* Answer Input Area & Voice Controls */}
              <div className="space-y-2">
                <div className="flex items-center justify-between text-xs">
                  <label className="text-slate-300 font-semibold">{t("Cevabınız (Yazarak veya Konuşarak):")}</label>
                  <button
                    onClick={handleToggleSpeechRecognition}
                    className={`flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-semibold transition ${
                      isRecording
                        ? "bg-rose-600 text-white animate-pulse"
                        : "bg-emerald-600 hover:bg-emerald-500 text-white"
                    }`}
                  >
                    {isRecording ? (
                      <>
                        <MicOff className="w-3.5 h-3.5" /> {t("Dinleniyor (")}{recordingSeconds}{t("s)...")}</>
                    ) : (
                      <>
                        <Mic className="w-3.5 h-3.5" /> {t("Sesle Konuş (Mikrofon)")}</>
                    )}
                  </button>
                </div>

                <textarea
                  value={candidateAnswer}
                  onChange={(e) => setCandidateAnswer(e.target.value)}
                  placeholder={t("Yanıtınızı buraya yazın veya mikrofon butonuna basarak sesli konuşun (STAR metodu)...")}
                  className="w-full h-32 bg-slate-950 border border-slate-800 rounded-xl p-3 text-xs text-white focus:outline-none focus:border-indigo-500 leading-relaxed"
                ></textarea>
              </div>

              {/* Action Buttons: Evaluate Content vs Evaluate Vocal Performance */}
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <button
                    onClick={handleEvaluate}
                    disabled={evaluating || !candidateAnswer.trim()}
                    className="bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-xs px-3.5 py-2 rounded-xl transition flex items-center gap-1.5 disabled:opacity-50"
                  >
                    <Send className="w-3.5 h-3.5" />
                    {evaluating ? t("Değerlendiriliyor...") : t("İçeriği Puanla")}
                  </button>

                  <button
                    onClick={handleVoiceEvaluate}
                    disabled={evaluatingVoice || !candidateAnswer.trim()}
                    className="bg-sky-600 hover:bg-sky-500 text-white font-semibold text-xs px-3.5 py-2 rounded-xl transition flex items-center gap-1.5 disabled:opacity-50 shadow-md shadow-sky-600/20"
                  >
                    <Zap className="w-3.5 h-3.5" />
                    {evaluatingVoice ? t("Ölçülüyor...") : "Vokal Performans & WPM"}
                  </button>
                </div>

                {currentQIndex < questions.length - 1 && (
                  <button
                    onClick={() => {
                      setCurrentQIndex(currentQIndex + 1);
                      setCandidateAnswer("");
                      setEvaluation(null);
                      setVocalEvaluation(null);
                    }}
                    className="text-xs text-slate-400 hover:text-white"
                  >
                    {t("Sonraki Soru →")}</button>
                )}
              </div>

              {/* Vocal Performance Metrics Card */}
              {vocalEvaluation && (
                <div className="p-4 rounded-xl bg-slate-950 border border-sky-500/30 space-y-3">
                  <div className="flex justify-between items-center text-xs">
                    <span className="font-bold text-sky-300">{t("Vokal & Akıcılık Karnesi:")}</span>
                    <span className="font-mono font-bold text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20">
                      {vocalEvaluation.overall_score} {t("/ 100")}</span>
                  </div>

                  <div className="grid grid-cols-3 gap-2 text-center text-xs">
                    <div className="p-2 rounded bg-slate-900 border border-slate-800">
                      <div className="text-xs text-slate-400">{t("Konuşma Hızı")}</div>
                      <div className="text-xs font-bold text-white font-mono mt-0.5">{vocalEvaluation.wpm} {t("WPM")}</div>
                      <div className="text-xs text-sky-400">{vocalEvaluation.pace_label}</div>
                    </div>
                    <div className="p-2 rounded bg-slate-900 border border-slate-800">
                      <div className="text-xs text-slate-400">{t("Dolgu Kelimeler")}</div>
                      <div className="text-xs font-bold text-amber-400 font-mono mt-0.5">{vocalEvaluation.total_fillers} {t("adet")}</div>
                      <div className="text-xs text-slate-400">{t("um, uh, like")}</div>
                    </div>
                    <div className="p-2 rounded bg-slate-900 border border-slate-800">
                      <div className="text-xs text-slate-400">{t("STAR Uyumu")}</div>
                      <div className="text-xs font-bold text-emerald-400 font-mono mt-0.5">%{vocalEvaluation.star_adherence_percent}</div>
                      <div className="text-xs text-emerald-400">{t("Durum/Görev/Aksiyon")}</div>
                    </div>
                  </div>

                  <div className="text-xs text-slate-300 bg-slate-900/60 p-2.5 rounded-lg border border-slate-800">
                    <strong>{t("Koçluk Tavsiyesi:")}</strong> {vocalEvaluation.actionable_suggestions?.[0] || vocalEvaluation.pace_feedback}
                  </div>
                </div>
              )}

              {/* Content Evaluation Output */}
              {evaluation && (
                <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 space-y-2.5">
                  <div className="flex justify-between items-center">
                    <span className="text-xs font-bold text-white">{t("İçerik Değerlendirme Sonucu:")}</span>
                    <span className="text-xs font-bold text-emerald-400 font-mono">
                      {evaluation.grade} (%{evaluation.score}{t("/100)")}</span>
                  </div>
                  <ul className="text-xs text-slate-300 space-y-1 list-disc pl-4">
                    {evaluation.feedback?.map((fb: string, i: number) => (
                      <li key={i}>{fb}</li>
                    ))}
                  </ul>
                  <div className="p-2.5 bg-indigo-950/30 rounded-lg border border-indigo-500/20 text-xs text-indigo-300">
                    <strong>{t("Koçluk İpucu:")}</strong> {evaluation.coaching_tip}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Right: Offer Negotiator (PRD 3.4) */}
        <div className="p-6 rounded-2xl bg-[#0e1524] border border-slate-800/80 space-y-4 flex flex-col justify-between">
          <div className="space-y-4">
            <div className="flex justify-between items-center">
              <h2 className="text-sm font-semibold text-white flex items-center gap-2">
                <DollarSign className="w-4 h-4 text-emerald-400" /> {t("Pazarlık Ajanı (Offer Negotiator)")}</h2>
              <span className="text-xs bg-emerald-500/10 text-emerald-400 px-2 py-0.5 rounded font-mono">
                {t("PRD 3.4 Standardı")}</span>
            </div>
            <p className="text-xs text-slate-400">
              {t("Gelen teklifi piyasa karşılaştırma verileriyle analiz eder, işvereni küstürmeden %10-15 artış ve remote esneklik sağlayan diplomatik karşı teklif e-postası üretir.")}</p>

            <div className="space-y-2">
              <div>
                <label className="text-xs font-semibold text-slate-400 uppercase">{t("Gelen Teklif (Initial Offer)")}</label>
                <input
                  type="text"
                  value={initialOffer}
                  onChange={(e) => setInitialOffer(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-white"
                />
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-400 uppercase">{t("Piyasa Skalası (Benchmark Data)")}</label>
                <input
                  type="text"
                  value={marketBench}
                  onChange={(e) => setMarketBench(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-white"
                />
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-400 uppercase">{t("Talep Edilen Hedef Maaş")}</label>
                <input
                  type="text"
                  value={targetAmount}
                  onChange={(e) => setTargetAmount(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-white"
                />
              </div>
            </div>

            <button
              onClick={handleGenerateCounterOffer}
              disabled={generatingOffer}
              className="w-full bg-emerald-600 hover:bg-emerald-500 text-white font-semibold text-xs py-2.5 rounded-xl transition flex items-center justify-center gap-1.5 shadow-lg shadow-emerald-600/20"
            >
              <Sparkles className="w-3.5 h-3.5" />
              {generatingOffer ? t("Hazırlanıyor...") : t("Karşı Teklif (Counter-Offer) E-postası Üret")}
            </button>

            {counterOfferDraft && (
              <div className="space-y-2 pt-2">
                <div className="flex justify-between items-center text-xs">
                  <span className="font-semibold text-slate-300">{t("Konu:")}{counterOfferDraft.subject}</span>
                </div>
                <pre className="p-3 bg-slate-950 border border-slate-800 rounded-xl text-xs text-slate-200 font-sans whitespace-pre-wrap max-h-48 overflow-y-auto leading-relaxed">
                  {counterOfferDraft.email_body}
                </pre>
              </div>
            )}
          </div>

          {counterOfferDraft && (
            <button
              onClick={() => {
                navigator.clipboard.writeText(counterOfferDraft.email_body);
                setCopied(true);
                setTimeout(() => setCopied(false), 2000);
              }}
              className="w-full mt-3 bg-slate-800 hover:bg-slate-700 text-white text-xs font-semibold py-2 rounded-xl transition flex items-center justify-center gap-1.5"
            >
              {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
              {copied ? t("Metin Panoya Kopyalandı!") : t("E-postayı Kopyala")}
            </button>
          )}
        </div>

      </div>
    </div>
  );
}

// Loaded only when their tab is opened, so this page stays as light as before.
const STARPrepPage = dynamic(() => import("../star-prep/page"));
const VoiceInterviewPage = dynamic(() => import("../voice-interview/page"));

// Related screens live here as tabs so the menu stays short; each still has its own route.
const TABS = [
    { label: "Mülakat hazırlığı", Component: InterviewPage },
    { label: "STAR hazırlığı", Component: STARPrepPage },
    { label: "Sesli mülakat", Component: VoiceInterviewPage },
];

export default function InterviewPageWithTabs() {
  return <PageTabs tabs={TABS} />;
}
