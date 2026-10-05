"use client";
import { useLanguage } from "@/lib/i18n";
import { useState, useEffect, useRef } from "react";
import { Mic, MicOff, Volume2, Sparkles, RefreshCw, CheckCircle2, AlertTriangle, Shield } from "lucide-react";
import { API_BASE, API_AUTH_TOKEN, fetchFromApi } from "@/lib/api";

export default function VoiceInterviewPage() {
  const { translate: t } = useLanguage();
  const [jobTitle, setJobTitle] = useState("Senior Backend & AI Systems Engineer");
  const [questionData, setQuestionData] = useState<any>(null);
  const [loadingQuestion, setLoadingQuestion] = useState(false);

  // Recording State
  const [isRecording, setIsRecording] = useState(false);
  const [transcript, setTranscript] = useState("");
  const [speaking, setSpeaking] = useState(false);
  const [analysisResult, setAnalysisResult] = useState<any>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [recordedAudio, setRecordedAudio] = useState<Blob | null>(null);
  const [transcribing, setTranscribing] = useState(false);

  const recognitionRef = useRef<any>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const startTimeRef = useRef<number>(0);

  async function handleGetQuestion() {
    try {
      setLoadingQuestion(true);
      const res = await fetchFromApi("/interview/voice/question", {
        method: "POST",
        body: JSON.stringify({ job_title: jobTitle, question_category: "behavioral" })
      });
      setQuestionData(res);
      setTranscript("");
      setAnalysisResult(null);
    } catch (e) {
      alert(t("Soru üretilemedi."));
    } finally {
      setLoadingQuestion(false);
    }
  }

  useEffect(() => {
    handleGetQuestion();
  }, []);

  // Text-To-Speech (AI Interviewer Speaks)
  async function handleSpeakQuestion() {
    if (!questionData?.spoken_question) return;

    // Prefer server-side TTS when an OpenAI key is configured on the backend.
    // The browser speech engine remains a zero-configuration fallback.
    try {
      const response = await fetch(`${API_BASE}/interview/voice/synthesize/stream`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(API_AUTH_TOKEN ? { "X-API-Key": API_AUTH_TOKEN } : {}),
        },
        body: JSON.stringify({ text: questionData.spoken_question, response_format: "mp3" }),
      });
      if (response.ok) {
        const audio = new Audio(URL.createObjectURL(await response.blob()));
        audioRef.current?.pause();
        audioRef.current = audio;
        audio.onplay = () => setSpeaking(true);
        audio.onended = () => setSpeaking(false);
        audio.onerror = () => setSpeaking(false);
        await audio.play();
        return;
      }
    } catch {
      // Fall through to browser TTS when the optional provider is unavailable.
    }

    if ("speechSynthesis" in window) {
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(questionData.spoken_question);
      utterance.lang = "en-US";
      utterance.rate = 0.95;
      utterance.onstart = () => setSpeaking(true);
      utterance.onend = () => setSpeaking(false);
      window.speechSynthesis.speak(utterance);
    } else {
      alert(t("Tarayıcınız ses sentezini (TTS) desteklemiyor."));
    }
  }

  // Speech-To-Text (Microphone Recording via Web Speech API)
  async function toggleRecording() {
    if (isRecording) {
      // Stop recording
      if (recognitionRef.current) {
        recognitionRef.current.stop();
      }
      if (mediaRecorderRef.current?.state === "recording") {
        mediaRecorderRef.current.stop();
      }
      setIsRecording(false);
      const durationSec = Math.max(5, (Date.now() - startTimeRef.current) / 1000);
      handleAnalyzeAnswer(transcript, durationSec);
    } else {
      // Start recording
      setRecordedAudio(null);
      audioChunksRef.current = [];
      try {
        if (navigator.mediaDevices?.getUserMedia && typeof MediaRecorder !== "undefined") {
          const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
          const recorder = new MediaRecorder(stream);
          mediaStreamRef.current = stream;
          mediaRecorderRef.current = recorder;
          recorder.ondataavailable = (event) => {
            if (event.data.size > 0) audioChunksRef.current.push(event.data);
          };
          recorder.onstop = () => {
            setRecordedAudio(new Blob(audioChunksRef.current, { type: recorder.mimeType || "audio/webm" }));
            mediaStreamRef.current?.getTracks().forEach((track) => track.stop());
            mediaStreamRef.current = null;
          };
          recorder.start();
        }
      } catch {
        // Browser STT can still work when microphone recording is unavailable.
      }

      const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
      if (!SpeechRecognition) {
        if (!mediaRecorderRef.current) {
          alert(t("Tarayıcınız ses kaydını desteklemiyor. Lütfen Chrome veya Safari kullanın."));
          return;
        }
        startTimeRef.current = Date.now();
        setIsRecording(true);
        return;
      }

      setTranscript("");
      setAnalysisResult(null);
      startTimeRef.current = Date.now();

      const recognition = new SpeechRecognition();
      recognition.continuous = true;
      recognition.interimResults = true;
      recognition.lang = "tr-TR";

      recognition.onresult = (event: any) => {
        let currentTranscript = "";
        for (let i = 0; i < event.results.length; i++) {
          currentTranscript += event.results[i][0].transcript + " ";
        }
        setTranscript(currentTranscript);
      };

      recognition.onerror = () => {
        setIsRecording(false);
      };

      recognition.onend = () => {
        setIsRecording(false);
      };

      recognitionRef.current = recognition;
      recognition.start();
      setIsRecording(true);
    }
  }

  async function handleWhisperTranscription() {
    if (!recordedAudio) return;
    try {
      setTranscribing(true);
      const formData = new FormData();
      formData.append("audio", recordedAudio, "voice-answer.webm");
      formData.append("language", "tr");
      const response = await fetch(`${API_BASE}/interview/voice/transcribe`, {
        method: "POST",
        headers: API_AUTH_TOKEN ? { "X-API-Key": API_AUTH_TOKEN } : undefined,
        body: formData,
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || "Whisper transkripsiyonu başarısız.");
      setTranscript(payload.text || "");
      await handleAnalyzeAnswer(payload.text || "", Math.max(5, (Date.now() - startTimeRef.current) / 1000));
    } catch (error: any) {
      alert(error?.message || "Whisper transkripsiyonu başarısız.");
    } finally {
      setTranscribing(false);
    }
  }

  async function handleAnalyzeAnswer(text: string, durationSec: number) {
    if (!text.trim()) return;
    try {
      setAnalyzing(true);
      const res = await fetchFromApi("/interview/voice/analyze", {
        method: "POST",
        body: JSON.stringify({
          transcript_text: text,
          duration_seconds: durationSec
        })
      });
      setAnalysisResult(res);
    } catch (e) {
      console.error(e);
    } finally {
      setAnalyzing(false);
    }
  }

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-white flex items-center gap-3">
          <Volume2 className="w-7 h-7 text-indigo-400" /> {t("İnteraktif Sesli Mülakat Koçu (Voice AI)")}</h1>
        <p className="text-slate-400 mt-1">
          {t("Yapay zeka mülakatçı soruyu seslendirir; cevabınızı mikrofonla konuşarak verirsiniz. Sistem konuşma hızı ve dolgu kelimelerinizi ölçer.")}</p>
      </div>

      {/* Spoken Question Box */}
      <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 space-y-4 shadow-xl">
        <div className="flex items-center justify-between">
          <div className="text-xs font-bold text-indigo-400 uppercase tracking-wider flex items-center gap-2">
            <Sparkles className="w-4 h-4" />
            <span>{t("Yapay Zeka Mülakatçı Sorusu")}</span>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={handleSpeakQuestion}
              disabled={speaking || !questionData}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-colors ${
                speaking ? "bg-amber-500/20 text-amber-300 animate-pulse" : "bg-indigo-600/30 text-indigo-300 hover:bg-indigo-600/50"
              }`}
            >
              <Volume2 className="w-3.5 h-3.5" />
              {speaking ? "Seslendiriliyor..." : "Soruyu Dinle (TTS)"}
            </button>
            <button
              onClick={handleGetQuestion}
              disabled={loadingQuestion}
              className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 transition-colors"
              title={t("Yeni Soru Üret")}
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loadingQuestion ? "animate-spin" : ""}`} />
            </button>
          </div>
        </div>

        <div className="text-base text-white font-medium leading-relaxed bg-slate-950/80 p-4 rounded-xl border border-slate-800">
          "{questionData?.spoken_question || t("Soru hazırlanıyor...")}"
        </div>

        {questionData?.listen_for && (
          <div className="text-xs text-slate-400 space-y-1">
            <span className="font-semibold text-slate-300">{t("Mülakatçının Duymak İstediği Anahtar Noktalar:")}</span>
            <div className="flex flex-wrap gap-2 pt-1">
              {questionData.listen_for.map((point: string, i: number) => (
                <span key={i} className="px-2.5 py-0.5 rounded-full bg-slate-800 text-slate-300 text-[11px]">
                  {t("•")}{point}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Answer & Microphone Recording Box */}
      <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 space-y-4 text-center">
        <div className="text-xs font-bold text-slate-400 uppercase tracking-wider">
          {t("Sesli Yanıt Alanı (Mikrofon Dinlemede)")}</div>

        {/* Big Mic Button */}
        <div className="py-2">
          <button
            onClick={toggleRecording}
            className={`w-20 h-20 rounded-full flex items-center justify-center mx-auto transition-all shadow-2xl ${
              isRecording
                ? "bg-rose-600 text-white animate-pulse ring-8 ring-rose-600/30 scale-105"
                : "bg-indigo-600 hover:bg-indigo-500 text-white"
            }`}
          >
            {isRecording ? <MicOff className="w-8 h-8" /> : <Mic className="w-8 h-8" />}
          </button>
          <div className="text-xs font-semibold mt-3 text-slate-300">
            {isRecording ? t("Dinleniyor... Konuşmanız bittiğinde tekrar basın") : t("Konuşmaya Başlamak İçin Basın")}
          </div>
        </div>

        {/* Live Transcript Display */}
        <div className="bg-slate-950/80 border border-slate-800 rounded-xl p-4 min-h-[90px] text-left text-xs text-slate-300 leading-relaxed font-sans">
          {transcript || (
            <span className="text-slate-600 italic">
              {t("Mikrofon butonuna basıp konuştuğunuzda metin anlık olarak burada belirecektir...")}</span>
          )}
        </div>
        {recordedAudio && (
          <button
            onClick={handleWhisperTranscription}
            disabled={transcribing}
            className="mx-auto px-3 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 disabled:opacity-50 text-xs text-indigo-300 transition-colors"
          >
            {transcribing ? t("Whisper çözümlüyor...") : t("Whisper ile yeniden çözümle")}
          </button>
        )}
      </div>

      {/* Audio Analytics & Fluency Score */}
      {analysisResult && (
        <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 space-y-4 animate-in fade-in">
          <div className="text-xs font-bold text-emerald-400 uppercase tracking-wider flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4" />
            <span>{t("Ses ve Akıcılık Analiz Raporu")}</span>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div className="bg-slate-950/80 border border-slate-800 p-3 rounded-xl text-center">
              <div className="text-[10px] text-slate-400 uppercase font-mono">{t("Akıcılık Puanı")}</div>
              <div className="text-2xl font-bold text-emerald-400 font-mono mt-0.5">
                %{analysisResult.fluency_score}
              </div>
            </div>
            <div className="bg-slate-950/80 border border-slate-800 p-3 rounded-xl text-center">
              <div className="text-[10px] text-slate-400 uppercase font-mono">{t("Konuşma Hızı (WPM)")}</div>
              <div className="text-2xl font-bold text-white font-mono mt-0.5">
                {analysisResult.words_per_minute}
              </div>
            </div>
            <div className="bg-slate-950/80 border border-slate-800 p-3 rounded-xl text-center">
              <div className="text-[10px] text-slate-400 uppercase font-mono">{t("Dolgu Kelimeler")}</div>
              <div className="text-2xl font-bold text-amber-400 font-mono mt-0.5">
                {analysisResult.total_fillers_used}
              </div>
            </div>
            <div className="bg-slate-950/80 border border-slate-800 p-3 rounded-xl text-center">
              <div className="text-[10px] text-slate-400 uppercase font-mono">{t("Kelime Sayısı")}</div>
              <div className="text-2xl font-bold text-blue-400 font-mono mt-0.5">
                {analysisResult.total_words}
              </div>
            </div>
          </div>

          <div className="bg-slate-950/60 p-3 rounded-xl border border-slate-800 text-xs text-slate-300">
            🎯 <strong>{t("Ritim Değerlendirmesi:")}</strong> {analysisResult.pace_verdict}
          </div>
        </div>
      )}
    </div>
  );
}
