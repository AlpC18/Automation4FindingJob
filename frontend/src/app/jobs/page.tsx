"use client";

import { notify } from "@/lib/notify";
import { useDeferredValue, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import {
  Search,
  Filter,
  Briefcase,
  Sparkles,
  RefreshCw,
  Clock,
  ExternalLink,
  MapPin,
  Compass,
  CheckSquare,
  Square,
  Heart,
  Plus,
  Check,
  Code2,
  Palette,
  TrendingUp,
  Building2,
  GraduationCap,
} from "lucide-react";
import AiProviderSelect from "@/components/AiProviderSelect";
import JobCard from "@/components/JobCard";
import { buildApiUrl, fetchFromApi, waitForBackgroundJob } from "@/lib/api";
import { getExternalJobUrl } from "@/lib/job-links";
import { useLanguage } from "@/lib/i18n";
import { isInternshipJob } from "@/lib/job-categories.cjs";
import { formatTimestamp, jobFreshness, linkStatus } from "@/lib/scan-status.cjs";
import ScanStatusPanel, { type ScanStatus } from "@/components/ScanStatusPanel";
import EmptyFeedGuide from "@/components/EmptyFeedGuide";

export default function JobsPage() {
  const { locale, translate: t } = useLanguage();
  const [jobs, setJobs] = useState<any[]>([]);
  const [, setLoading] = useState(true);
  const [scraping, setScraping] = useState(false);
  const [selectedPlatform, setSelectedPlatform] = useState("all");
  const [selectedTier, setSelectedTier] = useState("all");
  const [textFilter, setTextFilter] = useState("");
  const [locationFilter, setLocationFilter] = useState("");
  const [remoteFilter, setRemoteFilter] = useState("all");
  const [internshipOnly, setInternshipOnly] = useState(false);
  const [minimumMatch, setMinimumMatch] = useState("0");
  const [ghostOnly, setGhostOnly] = useState(false);
  const [currentOnly, setCurrentOnly] = useState(false);
  const [includeStale, setIncludeStale] = useState(false);
  const [favoriteOnly, setFavoriteOnly] = useState(false);
  const [sortOrder, setSortOrder] = useState("match");
  const [selectedJobIds, setSelectedJobIds] = useState<string[]>([]);
  const [batchBusy, setBatchBusy] = useState(false);

  // CV Role Discovery & Work Style Wizard State
  const [discoveredRoles, setDiscoveredRoles] = useState<any[]>([]);
  const [selectedRoleIds, setSelectedRoleIds] = useState<string[]>([]);
  const [customRoleInput, setCustomRoleInput] = useState("");
  const [customRoles, setCustomRoles] = useState<string[]>([]);
  const [wizardWorkMode, setWizardWorkMode] = useState<string>("Remote");
  const [wizardLocationPreset, setWizardLocationPreset] = useState<string>("all");
  const [selectedDisciplineId, setSelectedDisciplineId] = useState<string>("tech");

  const [locationPresets, setLocationPresets] = useState<any[]>([]);
  const [selectedLocationId, setSelectedLocationId] = useState<string>("");
  const [customLocationInput, setCustomLocationInput] = useState("");
  const [searchAi, setSearchAi] = useState("");

  const [showWizard, setShowWizard] = useState(true);
  const [scrapeFeedback, setScrapeFeedback] = useState<string | null>(null);
  const [savedSearches, setSavedSearches] = useState<any[]>([]);
  const [savedSearchBusy, setSavedSearchBusy] = useState<string | null>(null);
  const [packagePreview, setPackagePreview] = useState<any>(null);
  const [preparingJob, setPreparingJob] = useState<string | null>(null);
  const [detailJob, setDetailJob] = useState<any>(null);
  const [scanRuns, setScanRuns] = useState<any[]>([]);
  const [jobFeedbackTypes, setJobFeedbackTypes] = useState<string[]>([]);
  const [jobFeedbackNote, setJobFeedbackNote] = useState("");
  const [jobFeedbackBusy, setJobFeedbackBusy] = useState<string | null>(null);
  const [jobFeedbackNotice, setJobFeedbackNotice] = useState("");
  const [linkCheckBusy, setLinkCheckBusy] = useState<string | null>(null);
  const [scanStatus, setScanStatus] = useState<ScanStatus | null>(null);
  const [scanStatusUnavailable, setScanStatusUnavailable] = useState(false);

  useEffect(() => {
    if (!detailJob?.id) {
      setJobFeedbackTypes([]);
      setJobFeedbackNote("");
      setJobFeedbackNotice("");
      return;
    }
    fetchFromApi(`/trust/feedback?job_id=${encodeURIComponent(detailJob.id)}`)
      .then((result) => setJobFeedbackTypes(result.feedback_types || []))
      .catch(() => setJobFeedbackTypes([]));
  }, [detailJob?.id]);

  async function toggleJobFeedback(feedbackType: string) {
    if (!detailJob) return;
    setJobFeedbackBusy(feedbackType);
    setJobFeedbackNotice("");
    try {
      const existing = jobFeedbackTypes.includes(feedbackType);
      const endpoint = existing
        ? `/trust/feedback/${feedbackType}?job_id=${encodeURIComponent(detailJob.id)}`
        : "/trust/feedback";
      await fetchFromApi(endpoint, existing
        ? { method: "DELETE" }
        : { method: "POST", body: JSON.stringify({ job_id: detailJob.id, company: detailJob.company, source_url: detailJob.url || "", feedback_type: feedbackType, note: jobFeedbackNote }) });
      const result = await fetchFromApi(`/trust/feedback?job_id=${encodeURIComponent(detailJob.id)}`);
      setJobFeedbackTypes(result.feedback_types || []);
      setJobFeedbackNotice(t(existing ? "Geri bildirimin kaldırıldı." : "Geri bildirimin bu hesabına kaydedildi."));
      setJobFeedbackNote("");
    } catch {
      setJobFeedbackNotice(t("Geri bildirim kaydedilemedi. Tekrar deneyin."));
    } finally {
      setJobFeedbackBusy(null);
    }
  }

  const jobsRequest = useRef(0);

  async function loadSavedSearches() {
    const result = await fetchFromApi("/scrape/saved-searches");
    setSavedSearches(result.searches || []);
  }

  async function loadJobs() {
    const requestId = ++jobsRequest.current;
    try {
      setLoading(true);
      const params = new URLSearchParams();
      if (favoriteOnly) params.set("flag", "favorite");
      if (includeStale) params.set("include_stale", "true");
      const suffix = params.toString();
      const res = await fetchFromApi(`/scrape/jobs${suffix ? `?${suffix}` : ""}`);
      if (requestId !== jobsRequest.current) return; // a newer request has started
      setJobs(res.jobs || []);
    } catch (cause: any) {
      notify(cause?.message || t("İlanlar yüklenemedi."));
    } finally {
      setLoading(false);
    }
  }

  async function toggleJobFlag(job: any, flag: "favorite" | "hidden") {
    const enabled = !Boolean(job[flag]);
    await fetchFromApi(`/scrape/jobs/${encodeURIComponent(job.id)}/flags`, {
      method: "POST",
      body: JSON.stringify({ flag, enabled }),
    });
    if (flag === "hidden" || favoriteOnly) {
      await loadJobs();
    } else {
      setJobs((current) => current.map((item) => item.id === job.id ? { ...item, [flag]: enabled } : item));
    }
  }

  async function checkJobLink(job: any) {
    setLinkCheckBusy(job.id);
    try {
      const result = await fetchFromApi(`/scrape/jobs/${encodeURIComponent(job.id)}/link-check`, { method: "POST" });
      const check = result.check;
      setJobs((current) => current.map((item) => item.id === job.id ? { ...item, source_link_check: check } : item));
      setDetailJob((current: any) => current?.id === job.id ? { ...current, source_link_check: check } : current);
    } catch (error: any) {
      setScrapeFeedback(error.message || t("İlan linki kontrol edilemedi."));
    } finally {
      setLinkCheckBusy(null);
    }
  }

  async function loadScanRuns() {
    try {
      const result = await fetchFromApi("/scrape/runs?limit=5");
      setScanRuns(result.runs || []);
    } catch {
      setScanRuns([]);
    }
  }

  async function loadScanStatus() {
    try {
      setScanStatus(await fetchFromApi<ScanStatus>("/scrape/status"));
      setScanStatusUnavailable(false);
    } catch {
      setScanStatus(null);
      setScanStatusUnavailable(true);
    }
  }

  async function loadDiscoveredRoles() {
    try {
      const res = await fetchFromApi("/setup/discovered_roles");
      if (res && res.roles) {
        setDiscoveredRoles(res.roles);
        setLocationPresets(res.location_presets || []);
        setSelectedLocationId((current) => current || res.location_presets?.[0]?.id || "");
        // Pre-select default checked roles
        const defaults = res.roles.filter((r: any) => r.default_checked).map((r: any) => r.id);
        setSelectedRoleIds(defaults);
      }
    } catch (e) {
      console.error("Could not fetch discovered roles", e);
    }
  }

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("minMatch")) setMinimumMatch(params.get("minMatch") || "0");
    if (params.get("ghost") === "1") setGhostOnly(true);
    if (params.get("scope") === "current") setCurrentOnly(true);
    loadDiscoveredRoles();
    loadSavedSearches().catch(() => {});
    loadScanRuns();
    loadScanStatus();
  }, []);

  // Only the list depends on these two filters; reloading the rest would reset the roles picked above.
  useEffect(() => {
    loadJobs();
  }, [favoriteOnly, includeStale]);

  async function scheduleCurrentSearch() {
    const terms = internshipOnly
      ? ["intern"]
      : discoveredRoles.filter((role) => selectedRoleIds.includes(role.id)).map((role) => role.title).concat(customRoles);
    if (!terms.length) { setScrapeFeedback(t("Zamanlamak için önce en az bir rol seç.")); return; }
    const savedPreset = locationPresets.find((item) => item.id === selectedLocationId);
    const location = customLocationInput.trim()
      || (wizardLocationPreset !== "all" ? wizardLocationPreset : "")
      || (savedPreset ? savedPreset.location_filter : "");
    const effectiveRemote = wizardWorkMode === "all" ? "" : wizardWorkMode;
    try {
      await fetchFromApi("/scrape/saved-searches", {
        method: "POST",
        body: JSON.stringify({
          name: internshipOnly ? t("Staj ilanları") : terms.slice(0, 2).join(" + "),
          queries: terms,
          location,
          min_match_score: 65,
          enabled: true,
          llm_provider: searchAi === "local_fallback" ? "" : searchAi,
          remote_type: effectiveRemote || "Remote"
        })
      });
      await loadSavedSearches();
      await loadScanStatus();
      setScrapeFeedback(t("Arama otomatik zamanlamaya eklendi; şimdi tarama başlatılmadı. Durumu aşağıdaki Otomatik zamanlama bölümünden yönetebilirsin."));
    } catch (error: any) {
      setScrapeFeedback(error.message || t("Zamanlama ayarı kaydedilemedi."));
    }
  }

  async function runSavedSearch(id: string) {
    setSavedSearchBusy(id);
    try {
      const result = await fetchFromApi(`/scrape/saved-searches/${id}/run`, { method: "POST", body: "{}" });
      setScrapeFeedback(`${t("Arama tamamlandı")}: ${result.new_matches} ${t("yeni uygun ilan")}.`);
      await loadJobs();
      await loadScanRuns();
      await loadScanStatus();
    } catch (error: any) { setScrapeFeedback(error.message || t("Arama başarısız.")); }
    finally { setSavedSearchBusy(null); }
  }

  async function setSavedSearchSchedule(search: any, enabled: boolean) {
    try {
      await fetchFromApi(`/scrape/saved-searches/${search.id}`, {
        method: "PATCH",
        body: JSON.stringify({ enabled }),
      });
      setSavedSearches((current) => current.map((item) => item.id === search.id ? { ...item, enabled } : item));
      await loadScanStatus();
    } catch (error: any) {
      setScrapeFeedback(error.message || t("Zamanlama ayarı kaydedilemedi."));
    }
  }

  async function prepareApplication(job: any) {
    setPreparingJob(job.id);
    try {
      const result = await fetchFromApi("/apply/generate_package", { method: "POST", body: JSON.stringify({ job_id: job.id, provider: "auto" }) });
      setPackagePreview({ ...result, job });
      await loadJobs();
    } catch (error: any) { setScrapeFeedback(error.message || t("Başvuru taslağı hazırlanamadı.")); }
    finally { setPreparingJob(null); }
  }

  function toggleRole(id: string) {
    if (selectedRoleIds.includes(id)) {
      setSelectedRoleIds(selectedRoleIds.filter((r) => r !== id));
    } else {
      setSelectedRoleIds([...selectedRoleIds, id]);
    }
  }

  function togglePopularRole(roleName: string) {
    if (customRoles.includes(roleName)) {
      setCustomRoles(customRoles.filter((r) => r !== roleName));
    } else {
      setCustomRoles([...customRoles, roleName]);
    }
  }

  function handleSelectAllDisciplineRoles(roles: string[]) {
    const combined = Array.from(new Set([...customRoles, ...roles]));
    setCustomRoles(combined);
  }

  function handleClearDisciplineRoles(roles: string[]) {
    setCustomRoles(customRoles.filter((r) => !roles.includes(r)));
  }

  function handleAddCustomRole() {
    if (!customRoleInput.trim()) return;
    if (!customRoles.includes(customRoleInput.trim())) {
      setCustomRoles([...customRoles, customRoleInput.trim()]);
    }
    setCustomRoleInput("");
  }

  function handleRemoveCustomRole(role: string) {
    setCustomRoles(customRoles.filter((r) => r !== role));
  }

  // Multi-Role & Work Style Scrape Dispatcher
  async function handleExecuteCustomSearch() {
    const chosenTitles: string[] = internshipOnly ? ["intern"] : [];
    if (!internshipOnly) {
      discoveredRoles.forEach((r) => {
        if (selectedRoleIds.includes(r.id)) chosenTitles.push(r.title);
      });
      customRoles.forEach((r) => chosenTitles.push(r));
    }

    if (chosenTitles.length === 0) {
      notify(t("Lütfen taranacak en az bir rol veya ünvan seçiniz."));
      return;
    }

    const locPreset = locationPresets.find((p) => p.id === selectedLocationId);
    const locFilter = customLocationInput.trim()
      || (wizardLocationPreset !== "all" ? wizardLocationPreset : "")
      || (locPreset ? locPreset.location_filter : "");
    const remoteFilter = wizardWorkMode === "all" ? "" : wizardWorkMode;

    try {
      setScraping(true);
      setScrapeFeedback(null);
      let res = await fetchFromApi<any>("/scrape/run", {
        method: "POST",
        body: JSON.stringify({
          queries: chosenTitles,
          location_preference: locFilter,
          remote_type: remoteFilter
        })
      });
      if (res.status === "QUEUED" && res.job_id) {
        setScrapeFeedback(t("Tarama kuyruğa alındı; sonuçlar bekleniyor…"));
        const completed = await waitForBackgroundJob(res.job_id);
        if (!completed) {
          await loadJobs();
          await loadScanStatus();
          setScrapeFeedback(t("Tarama arka planda sürüyor. Durumunu Gelen Kutusu sayfasındaki Arka Plan İşleri bölümünden izleyebilirsin."));
          return;
        }
        res = completed;
      }
      // Recalculate the explainable profile-match estimates for current jobs.
      await fetchFromApi("/rank/evaluate_all", { method: "POST" });
      const summary = `${res.raw_fetched_count ?? res.total_scraped ?? 0} ${t("bulundu")} · ${res.newly_saved_count ?? 0} ${t("yeni")} · ${res.filtered_count ?? 0} ${t("elendi")} · ${res.current_total ?? 0} ${t("güncel ilan")}`;
      setScrapeFeedback(res.errors?.length
        ? `${t("Tarama kısmen tamamlandı")}: ${summary}. ${res.errors.join(" ")}`
        : `${t("Tarama tamamlandı")}: ${summary}. ${t("Uyum tahminleri yeniden hesaplandı.")}`);
      await loadJobs();
      await loadScanRuns();
      await loadScanStatus();
    } catch (e: any) {
      setScrapeFeedback(e?.message || t("Arama sırasında hata oluştu."));
    } finally {
      setScraping(false);
    }
  }

  // Typing stays responsive: the list is refiltered after the keystroke, and only when a filter changed.
  const deferredText = useDeferredValue(textFilter);
  const filteredJobs = useMemo(() => jobs.filter((j) => {
    if (currentOnly && !["Draft", "New", ""].includes(j.status || "Draft")) return false;
    if (ghostOnly && (j.ghost_score || 0) < 35) return false;
    const text = deferredText.trim().toLowerCase();
    if (text && !`${j.title} ${j.company} ${j.description}`.toLowerCase().includes(text)) return false;
    if (internshipOnly && !isInternshipJob(j)) return false;
    if (selectedPlatform !== "all" && String(j.platform || "").toLowerCase() !== selectedPlatform.toLowerCase()) return false;
    if (selectedTier !== "all" && (j.match_tier || "").toLowerCase() !== selectedTier.toLowerCase()) return false;
    if (locationFilter.trim() && !(j.location || "").toLowerCase().includes(locationFilter.trim().toLowerCase())) return false;
    if (remoteFilter !== "all" && !(j.remote_type || "").toLowerCase().includes(remoteFilter.toLowerCase())) return false;
    if ((j.match_score || 0) < Number(minimumMatch)) return false;
    return true;
  }).sort((a, b) => sortOrder === "salary"
    // Listings that state their pay first, highest first; the rest keep their match order below them.
    ? (b.salary_yearly_usd?.max ?? -1) - (a.salary_yearly_usd?.max ?? -1) || (b.match_score || 0) - (a.match_score || 0)
    : sortOrder === "recent"
    ? String(b.created_at || "").localeCompare(String(a.created_at || ""))
    : sortOrder === "company"
      ? String(a.company || "").localeCompare(String(b.company || ""))
      : (b.match_score || 0) - (a.match_score || 0)),
  [jobs, currentOnly, ghostOnly, deferredText, internshipOnly, selectedPlatform, selectedTier, locationFilter, remoteFilter, minimumMatch, sortOrder]);

  const platformOptions = useMemo(() => {
    const knownPlatforms = [
      { id: "all", label: t("Tümü"), activeClass: "bg-blue-600 text-white border-blue-500 font-semibold shadow-sm" },
      { id: "linkedin", label: "LinkedIn", activeClass: "bg-[#0a66c2] text-white border-[#0a66c2] font-semibold shadow-md shadow-[#0a66c2]/30" },
      { id: "arbeitnow", label: "Arbeitnow", activeClass: "bg-amber-600 text-white border-amber-500 font-semibold shadow-sm" },
      { id: "himalayas", label: "Himalayas", activeClass: "bg-purple-600 text-white border-purple-500 font-semibold shadow-sm" },
      { id: "techcareer", label: "Techcareer", activeClass: "bg-indigo-600 text-white border-indigo-500 font-semibold shadow-sm" },
      { id: "jobicy", label: "Jobicy", activeClass: "bg-cyan-600 text-white border-cyan-500 font-semibold shadow-sm" },
      { id: "remoteok", label: "RemoteOK", activeClass: "bg-rose-600 text-white border-rose-500 font-semibold shadow-sm" },
      { id: "remotive", label: "Remotive", activeClass: "bg-orange-600 text-white border-orange-500 font-semibold shadow-sm" },
      { id: "upwork", label: "Upwork", activeClass: "bg-emerald-600 text-white border-emerald-500 font-semibold shadow-sm" },
      { id: "kosovajob", label: "Kosovajob", activeClass: "bg-teal-600 text-white border-teal-500 font-semibold shadow-sm" },
    ];

    const counts: Record<string, number> = { all: jobs.length };
    jobs.forEach((j) => {
      const p = String(j.platform || "").toLowerCase();
      if (p) counts[p] = (counts[p] || 0) + 1;
    });

    const activeList = knownPlatforms
      .filter((kp) => kp.id === "all" || counts[kp.id] !== undefined || ["linkedin", "upwork"].includes(kp.id))
      .map((kp) => ({
        ...kp,
        count: counts[kp.id] || 0,
      }));

    Object.keys(counts).forEach((p) => {
      if (p !== "all" && !activeList.some((o) => o.id === p)) {
        activeList.push({
          id: p,
          label: p.charAt(0).toUpperCase() + p.slice(1),
          activeClass: "bg-blue-600 text-white border-blue-500 font-semibold shadow-sm",
          count: counts[p],
        });
      }
    });

    return activeList;
  }, [jobs, t]);

  const careerDisciplines = useMemo(() => [
    {
      id: "tech",
      label: t("Bilgisayar & Yazılım"),
      badge: t("Mühendislik & IT"),
      icon: Code2,
      activeColor: "border-sky-500/70 bg-sky-950/40 text-sky-200",
      description: t("Bilgisayar mühendisliği öğrencileri ve mezunları için yazılım geliştirme, yapay zeka, sistem, siber güvenlik ve veri rolleri."),
      roles: [
        "Software Engineer",
        "Frontend Developer",
        "Backend Developer",
        "Full Stack Developer",
        "AI / ML Engineer",
        "DevOps Engineer",
        "Data Scientist",
        "Cybersecurity Analyst",
        "Mobile Developer",
        "QA Automation Engineer",
      ],
    },
    {
      id: "design",
      label: t("Grafik Tasarım & Yaratıcı"),
      badge: t("Tasarım & Sanat"),
      icon: Palette,
      activeColor: "border-purple-500/70 bg-purple-950/40 text-purple-200",
      description: t("Grafik tasarımı ve görsel sanatlar alanında UI/UX, marka kimliği, hareketli grafik, illüstrasyon ve 3D tasarım rolleri."),
      roles: [
        "Graphic Designer",
        "UI/UX Designer",
        "Visual Designer",
        "Brand Identity Designer",
        "Motion Designer",
        "Digital Illustrator",
        "Product Designer",
        "3D Artist",
        "Art Director",
      ],
    },
    {
      id: "economics",
      label: t("Ekonomi & Finans"),
      badge: t("İş Dünyası & Analiz"),
      icon: TrendingUp,
      activeColor: "border-emerald-500/70 bg-emerald-950/40 text-emerald-200",
      description: t("Ekonomi mezunları finansal analiz, pazar araştırması, veri analitiği, risk yönetimi ve yatırım bankacılığı alanlarında ilerleyebilir."),
      roles: [
        "Financial Analyst",
        "Business Analyst",
        "Market Research Analyst",
        "Risk Analyst",
        "Investment Banking Analyst",
        "Economist",
        "Accounting Specialist",
        "Budget & Reporting Specialist",
        "Portfolio Analyst",
      ],
    },
    {
      id: "architecture",
      label: t("Mimarlık & Yapı Tasarımı"),
      badge: t("Mimarlık & Tasarım"),
      icon: Building2,
      activeColor: "border-amber-500/70 bg-amber-950/40 text-amber-200",
      description: t("Mimarlık ve iç mimarlık mezunları mimari proje tasarımı, BIM/Revit uzmanlığı, 3D görselleştirme ve kentsel planlama pozisyonlarına yönelebilir."),
      roles: [
        "Architect",
        "Interior Architect",
        "BIM Specialist",
        "3D Architectural Visualizer",
        "Project Architect",
        "Landscape Architect",
        "Urban Planner",
        "Site Architect",
        "Architectural Designer",
      ],
    },
  ], [t]);

  function toggleJobSelection(id: string) {
    setSelectedJobIds((current) => current.includes(id) ? current.filter((item) => item !== id) : [...current, id]);
  }

  function toggleAllVisible() {
    const visibleIds = filteredJobs.map((job) => job.id);
    const allSelected = visibleIds.length > 0 && visibleIds.every((id) => selectedJobIds.includes(id));
    setSelectedJobIds((current) => allSelected
      ? current.filter((id) => !visibleIds.includes(id))
      : Array.from(new Set([...current, ...visibleIds])));
  }

  async function runBatchAction(action: "reject" | "prepare") {
    if (!selectedJobIds.length) return;
    try {
      setBatchBusy(true);
      const [path, body] = action === "reject"
        ? ["/outcome/update_status", (job_id: string) => ({ job_id, new_status: "Rejected" })] as const
        : ["/apply/generate_package", (job_id: string) => ({ job_id, provider: "auto" })] as const;
      const results = await Promise.allSettled(selectedJobIds.map((job_id) => fetchFromApi(path, { method: "POST", body: JSON.stringify(body(job_id)) })));
      const failed = results.filter((result) => result.status === "rejected").length;
      if (failed) notify(`${failed} / ${results.length} ${t("işlem tamamlanamadı.")}`);
      setSelectedJobIds([]);
      await loadJobs();
    } finally {
      setBatchBusy(false);
    }
  }

  function clearFilters() {
    setTextFilter(""); setLocationFilter(""); setRemoteFilter("all"); setSelectedPlatform("all"); setSelectedTier("all");
    setMinimumMatch("0"); setGhostOnly(false); setCurrentOnly(false); setInternshipOnly(false);
  }

  const linkLabels: Record<string, string> = {
    reachable: t("Link doğrulandı"), broken: t("Link bozuk"), unreachable: t("Linke ulaşılamadı"), queued: t("Link kontrolü sırada"),
    invalid: t("Link geçersiz"), blocked: t("Link güvenlik nedeniyle kontrol edilemedi"), unchecked: t("Link kontrol edilmedi"),
  };
  const scheduler = scanStatus?.scheduler;
  const selectedCount = selectedRoleIds.length + customRoles.length;
  const activeSearchCount = internshipOnly ? 1 : selectedCount;
  const currentLoc = locationPresets.find((p) => p.id === selectedLocationId);

  const cardContext = { selectedJobIds, toggleJobSelection, toggleJobFlag, checkJobLink, linkCheckBusy, linkLabels, prepareApplication, preparingJob, setDetailJob };

  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      {/* Top Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <Search className="w-6 h-6 text-blue-500" />
            {t("İş ilanları")}
          </h1>
          <p className="text-xs text-slate-400 mt-1">
            {t("CV'niz doğrultusunda kabul görme ihtimali yüksek rolleri keşfedin, çalışma şekli ve konumu her aramada siz belirleyin.")}
          </p>
        </div>

        {/* Quick Search toggle */}
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowWizard(!showWizard)}
            className="flex items-center gap-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold px-3 py-2 rounded-xl transition border border-slate-700"
          >
            <Compass className="w-3.5 h-3.5 text-sky-400" />
            {showWizard ? t("Arama ayarlarını gizle") : t("Arama ayarlarını aç")}
          </button>
        </div>
      </div>

      {/* ========================================================================= */}
      {/* CV-DRIVEN ROLE DISCOVERY & LOCATION SELECTION WIZARD */}
      {/* ========================================================================= */}
      {showWizard && (
        <div className="p-6 rounded-2xl bg-[#0e1524] border border-blue-900/60 shadow-xl space-y-6">
          <div className="flex items-center justify-between border-b border-slate-800/80 pb-3">
            <div className="flex items-center gap-2.5">
              <Sparkles className="w-5 h-5 text-amber-400" />
              <div>
                <h2 className="text-sm font-bold text-white">{t("Arama ayarları")}</h2>
                <p className="text-xs text-slate-400">
                  {t("Aday profiliniz ve yetkinliklerinize göre mülakat alma şansınızın en yüksek olduğu pozisyonlar")}</p>
              </div>
            </div>
            <span className="text-xs bg-blue-500/10 text-blue-400 border border-blue-500/20 px-2.5 py-0.5 rounded-full font-mono">
              {t("Yapay zekâ önerileri açık")}
            </span>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* 1. ROLE & TITLE SELECTION */}
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-slate-200 flex items-center gap-1.5">
                  <Briefcase className="w-4 h-4 text-sky-400" />
                  {t("Bir sonraki rolde ne tür iş yapmak istiyorsun? Hangi ünvanları arayalım?")}
                </span>
                <span className="text-xs text-slate-400 font-mono">
                  {activeSearchCount} {t(internshipOnly ? "Staj araması" : "rol seçildi")}
                </span>
              </div>

              <div className="space-y-2">
                <button
                  type="button"
                  aria-pressed={internshipOnly}
                  onClick={() => setInternshipOnly((current) => !current)}
                  className={`flex w-full items-center justify-between rounded-xl border px-3 py-2.5 text-left text-xs font-semibold transition ${internshipOnly ? "border-emerald-500/50 bg-emerald-950/35 text-emerald-300" : "border-slate-800 bg-slate-900/40 text-slate-300 hover:border-emerald-700/60"}`}
                >
                  <span>{t("Staj / internship ilanları")}</span>
                  <span className="text-xs font-normal">{internshipOnly ? t("Etkin · yalnızca staj") : t("Aramayı staj ilanlarına çevir")}</span>
                </button>
                {discoveredRoles.map((role) => {
                  const isChecked = selectedRoleIds.includes(role.id);
                  return (
                    <div
                      key={role.id}
                      onClick={() => toggleRole(role.id)}
                      className={`p-3 rounded-xl border transition cursor-pointer select-none space-y-1 ${
                        isChecked
                          ? "bg-blue-950/30 border-blue-500/50 shadow-sm"
                          : "bg-slate-900/40 border-slate-800/80 hover:border-slate-700"
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2.5">
                          <div
                            className={`w-4 h-4 rounded border flex items-center justify-center transition ${
                              isChecked
                                ? "bg-blue-600 border-blue-500 text-white"
                                : "border-slate-600 bg-slate-950"
                            }`}
                          >
                            {isChecked && <Check className="w-3 h-3 stroke-[3]" />}
                          </div>
                          <span className="text-xs font-bold text-white">{role.title}</span>
                        </div>

                      <span className="text-xs font-bold font-mono px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                          {t("CV becerileriyle önerildi")}
                        </span>
                      </div>
                      <div className="text-xs text-slate-400 pl-6 leading-relaxed">
                        {role.subtext}
                      </div>
                    </div>
                  );
                })}

                {/* CAREER FIELD / DISCIPLINE SELECTOR */}
                <div className="pt-2 space-y-3 rounded-xl bg-slate-950/60 p-3.5 border border-slate-800">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1">
                    <span className="text-xs font-bold text-slate-200 flex items-center gap-1.5">
                      <GraduationCap className="w-4 h-4 text-sky-400" />
                      {t("Meslek & Kariyer Alanı Seçimi")}
                    </span>
                    <span className="text-[11px] text-slate-400">
                      {t("Kendiniz, aileniz veya arkadaşlarınız için hedef sektörü seçin")}
                    </span>
                  </div>

                  {/* 4 Discipline Category Buttons */}
                  <div className="grid grid-cols-2 gap-2">
                    {careerDisciplines.map((disc) => {
                      const isSelected = selectedDisciplineId === disc.id;
                      const IconComp = disc.icon;
                      return (
                        <button
                          key={disc.id}
                          type="button"
                          onClick={() => setSelectedDisciplineId(disc.id)}
                          className={`p-2.5 rounded-xl border text-left transition flex items-center gap-2.5 ${
                            isSelected
                              ? disc.activeColor
                              : "border-slate-800 bg-slate-900/40 text-slate-400 hover:border-slate-700 hover:text-slate-200"
                          }`}
                        >
                          <div className={`w-7 h-7 rounded-lg flex items-center justify-center shrink-0 ${
                            isSelected ? "bg-white/10" : "bg-slate-800"
                          }`}>
                            <IconComp className="w-4 h-4" />
                          </div>
                          <div className="min-w-0">
                            <div className="text-xs font-semibold truncate text-white">{disc.label}</div>
                            <div className="text-[10px] text-slate-400 truncate">{disc.badge}</div>
                          </div>
                        </button>
                      );
                    })}
                  </div>

                  {/* Active Discipline Guidance Note & Roles */}
                  {(() => {
                    const activeDisc = careerDisciplines.find((d) => d.id === selectedDisciplineId) || careerDisciplines[0];
                    const allSelected = activeDisc.roles.every((r) => customRoles.includes(r));
                    return (
                      <div className="space-y-2 pt-1 border-t border-slate-800/80">
                        <p className="text-[11px] text-slate-300 leading-relaxed bg-slate-900/60 p-2.5 rounded-lg border border-slate-800/80">
                          {activeDisc.description}
                        </p>

                        <div className="flex items-center justify-between text-xs pt-1">
                          <span className="text-[11px] font-semibold text-slate-300">
                            {t("Bu Alandaki Popüler Pozisyonlar:")}
                          </span>
                          <div className="flex items-center gap-2">
                            <button
                              type="button"
                              onClick={() => handleSelectAllDisciplineRoles(activeDisc.roles)}
                              className="text-[11px] text-sky-400 hover:text-sky-300 font-medium"
                            >
                              {allSelected ? t("Tümü Eklendi ✓") : `+ ${t("Tüm Bu Rolleri Ekle")}`}
                            </button>
                            <button
                              type="button"
                              onClick={() => handleClearDisciplineRoles(activeDisc.roles)}
                              className="text-[11px] text-slate-400 hover:text-rose-400"
                            >
                              {t("Temizle")}
                            </button>
                          </div>
                        </div>

                        <div className="flex flex-wrap gap-1.5">
                          {activeDisc.roles.map((r) => {
                            const isAdded = customRoles.includes(r);
                            return (
                              <button
                                key={r}
                                type="button"
                                onClick={() => togglePopularRole(r)}
                                className={`text-[11px] px-2.5 py-1 rounded-lg border transition ${
                                  isAdded
                                    ? "bg-blue-600/30 text-blue-300 border-blue-500/60 font-semibold shadow-sm"
                                    : "bg-slate-950/60 text-slate-400 border-slate-800 hover:text-slate-200 hover:border-slate-700"
                                }`}
                              >
                                {isAdded ? `✓ ${r}` : `+ ${r}`}
                              </button>
                            );
                          })}
                        </div>
                      </div>
                    );
                  })()}
                </div>

                {/* Custom Added Roles */}
                {customRoles.map((cr) => (
                  <div
                    key={cr}
                    className="p-3 rounded-xl border bg-blue-950/20 border-blue-500/40 flex items-center justify-between text-xs"
                  >
                    <div className="flex items-center gap-2">
                      <Check className="w-3.5 h-3.5 text-blue-400" />
                      <span className="font-semibold text-white">{cr}</span>
                      <span className="text-xs bg-slate-800 text-slate-400 px-1.5 py-0.5 rounded">{t("Özel")}</span>
                    </div>
                    <button
                      onClick={() => handleRemoveCustomRole(cr)}
                      className="text-xs text-rose-400 hover:text-rose-300"
                    >
                      {t("Kaldır")}
                    </button>
                  </div>
                ))}

                {/* Type something (Add custom title) */}
                <div className="flex gap-2 pt-1">
                  <input
                    type="text"
                    value={customRoleInput}
                    onChange={(e) => setCustomRoleInput(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && handleAddCustomRole()}
                    placeholder={t("Örn: Platform Architect, Lead ML")}
                    className="flex-1 bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-white placeholder:text-slate-500 focus:outline-none focus:border-blue-500"
                  />
                  <button
                    onClick={handleAddCustomRole}
                    disabled={!customRoleInput.trim()}
                    className="bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold px-3 py-2 rounded-xl transition border border-slate-700 disabled:opacity-40"
                  >
                    <Plus className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            </div>

            {/* 2. WORK STYLE & LOCATION PREFERENCE */}
            <div className="space-y-4">
              {/* 2A. Independent Work Mode */}
              <div className="space-y-2">
                <span className="text-xs font-bold text-slate-200 flex items-center gap-1.5">
                  <Compass className="w-4 h-4 text-sky-400" />
                  {t("Çalışma Şekli")}
                </span>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                  {[
                    { id: "all", label: t("Tümü") },
                    { id: "Remote", label: t("Uzaktan (Remote)") },
                    { id: "Hybrid", label: t("Hibrit (Hybrid)") },
                    { id: "On-site", label: t("Ofiste (On-site)") },
                  ].map((mode) => {
                    const isSelected = wizardWorkMode === mode.id;
                    return (
                      <button
                        key={mode.id}
                        type="button"
                        aria-pressed={isSelected}
                        onClick={() => setWizardWorkMode(mode.id)}
                        className={`rounded-xl border px-3 py-2 text-xs font-semibold text-center transition ${
                          isSelected
                            ? "border-sky-500/60 bg-sky-950/40 text-sky-200 shadow-sm"
                            : "border-slate-800 bg-slate-900/40 text-slate-400 hover:border-slate-700 hover:text-slate-200"
                        }`}
                      >
                        {mode.label}
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* 2B. Location Preference */}
              <div className="space-y-2">
                <span className="text-xs font-bold text-slate-200 flex items-center gap-1.5">
                  <MapPin className="w-4 h-4 text-emerald-400" />
                  {t("Konum Tercihi")}
                </span>

                <div className="flex flex-wrap gap-2">
                  {[
                    { id: "all", label: t("Dünya Geneli (Global)") },
                    { id: "Turkey", label: t("Türkiye") },
                    { id: "Kosovo", label: t("Kosova") },
                    { id: "Germany", label: t("Almanya") },
                    { id: "United Kingdom", label: t("Birleşik Krallık") },
                    { id: "United States", label: t("ABD") },
                    { id: "Europe", label: t("Avrupa") },
                  ].map((loc) => {
                    const isSelected = wizardLocationPreset === loc.id && !customLocationInput;
                    return (
                      <button
                        key={loc.id}
                        type="button"
                        aria-pressed={isSelected}
                        onClick={() => {
                          setWizardLocationPreset(loc.id);
                          setCustomLocationInput("");
                        }}
                        className={`rounded-full border px-3 py-1.5 text-xs font-semibold transition ${
                          isSelected
                            ? "border-emerald-500/60 bg-emerald-950/40 text-emerald-200"
                            : "border-slate-800 bg-slate-900/40 text-slate-300 hover:border-slate-600"
                        }`}
                      >
                        {loc.label}
                      </button>
                    );
                  })}
                </div>

                {/* Custom Location input */}
                <div className="pt-1">
                  <input
                    type="text"
                    value={customLocationInput}
                    onChange={(e) => {
                      setCustomLocationInput(e.target.value);
                      setWizardLocationPreset("custom");
                    }}
                    placeholder={t("Veya özel şehir / ülke gir (Örn: Berlin, Remote US, İzmir hibrit)")}
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-white placeholder:text-slate-500 focus:outline-none focus:border-blue-500"
                  />
                </div>
              </div>
            </div>
          </div>

          {/* Action Footer */}
          <div className="pt-4 border-t border-slate-800/80 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div className="text-xs text-slate-300">
              {t("Arama Kapsamı")}{t(":")} <strong className="text-sky-400">{activeSearchCount} {t(internshipOnly ? "Staj araması" : "Ünvan")}</strong> {t("•")} {t("Çalışma")}{t(":")} <strong className="text-blue-300">{wizardWorkMode === "all" ? t("Tümü") : wizardWorkMode}</strong> {t("•")} {t("Konum")}{t(":")}{" "}
              <strong className="text-emerald-400">
                {customLocationInput.trim() || (wizardLocationPreset === "all" ? t("Global") : wizardLocationPreset)}
              </strong>
            </div>

            <div className="flex flex-wrap items-center justify-end gap-2">
              <AiProviderSelect onChange={setSearchAi} />
              <button
                onClick={() => void scheduleCurrentSearch()}
                disabled={scraping || activeSearchCount === 0}
                title={t("Bu rol ve konumu kaydeder; tarama zamanlayıcı çalıştığında otomatik yapılır. Şimdi tarama başlatmaz.")}
                className="flex items-center justify-center gap-2 rounded-xl border border-blue-500/30 px-4 py-3 text-xs font-semibold text-blue-300 transition hover:bg-blue-500/10 disabled:opacity-50"
              >
                <Clock className="h-4 w-4" />
                {t("Otomatik zamanla")}
              </button>
              <button
                onClick={handleExecuteCustomSearch}
                disabled={scraping || activeSearchCount === 0}
                title={t("Seçili rol ve konumla şimdi bir kez tarar.")}
                className="flex items-center justify-center gap-2 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white text-xs font-bold px-6 py-3 rounded-xl transition shadow-lg shadow-blue-600/30 disabled:opacity-50"
              >
                <RefreshCw className={`w-4 h-4 ${scraping ? "animate-spin" : ""}`} />
                {scraping ? t("Kaynaklar taranıyor ve uyum tahmini hesaplanıyor...") : `${t("Tarama başlat")} · ${t("şimdi, bir kez")}`}
              </button>
            </div>
          </div>

              {scrapeFeedback && (
            <div className="text-xs text-emerald-400 font-medium bg-emerald-950/30 p-3 rounded-xl border border-emerald-900/50">
              {scrapeFeedback}
            </div>
              )}
        </div>
      )}

      {/* Secondary information: open until there are results, then tucked away. */}
      <details className="jobs-secondary space-y-4" open={jobs.length === 0 ? true : undefined}>
        <summary className="cursor-pointer rounded-xl border border-slate-800 px-4 py-3 text-sm font-semibold text-slate-200">{t("Zamanlama ve tarama durumu")}</summary>
        <div className="mt-4 space-y-6">
      <section className="rounded-xl border border-slate-800 bg-[#0e1524] p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-sm font-semibold text-white">{t("Otomatik zamanlama")}</h2>
            <p className="mt-1 text-xs text-slate-400">{t("“Tarama başlat” yalnızca şimdi bir kez tarar. Burada zamanlanan aramalar ise zamanlayıcı çalışırken her gece kendiliğinden taranır.")}</p>
          </div>
          {scheduler && <span className={`rounded-full border px-2.5 py-1 text-xs font-semibold ${scheduler.is_running ? "border-emerald-500/30 text-emerald-300" : "border-amber-500/30 text-amber-300"}`}>{scheduler.is_running ? `${t("Zamanlayıcı çalışıyor")} · ${scheduler.nightly_time} (${scheduler.timezone})` : t("Zamanlayıcı kapalı")}</span>}
        </div>
        {scheduler && !scheduler.is_running && scheduler.scheduled_searches > 0 && <p className="mt-2 text-xs text-amber-200">{scheduler.scheduled_searches} {t("arama zamanlanmış ama zamanlayıcı kapalı olduğu için otomatik çalışmayacak.")} <Link href="/daemon-settings" className="font-semibold underline">{t("Zamanlayıcıyı aç")}</Link></p>}
        {scheduler?.last_nightly_run && <p className="mt-2 text-xs text-slate-400">{t("Son otomatik tarama")}: {formatTimestamp(scheduler.last_nightly_run, locale)}</p>}
        {savedSearches.length === 0 ? <p className="mt-3 text-xs text-slate-400">{t("Zamanlanmış arama yok. Yukarıdan rol ve konum seçip “Otomatik zamanla”ya bas.")}</p> : <div className="mt-3 flex flex-wrap gap-2">{savedSearches.map((item) => <div key={item.id} className="flex flex-wrap items-center gap-2 rounded-lg bg-slate-950 px-3 py-2 text-xs text-slate-200">
          <span>{item.name} · {item.location || "Remote"} · %{item.min_match_score}+{item.llm_provider ? ` · ${t("Yapay zekâ incelemesi")}: ${item.llm_provider}` : ""}</span>
          <button onClick={() => void setSavedSearchSchedule(item, !item.enabled)} aria-pressed={Boolean(item.enabled)} className={item.enabled ? "text-emerald-300" : "text-slate-400"}>{item.enabled ? t("Otomatik zamanlama açık") : t("Otomatik zamanlama kapalı")}</button>
          <button onClick={() => void runSavedSearch(item.id)} disabled={savedSearchBusy === item.id} className="text-blue-300 hover:text-white">{savedSearchBusy === item.id ? t("Taranıyor…") : t("Şimdi tara")}</button>
          <button onClick={async () => { await fetchFromApi(`/scrape/saved-searches/${item.id}`, { method: "DELETE" }); await loadSavedSearches(); await loadScanStatus(); }} className="text-rose-300 hover:text-rose-200">{t("Sil")}</button>
        </div>)}</div>}
      </section>

      <ScanStatusPanel status={scanStatus} unavailable={scanStatusUnavailable} runs={scanRuns} />
        </div>
      </details>

      {/* Filters Bar */}
      <div className="p-4 rounded-xl bg-[#0e1524] border border-slate-800 flex flex-wrap items-center justify-between gap-4 text-xs">
        <div className="flex w-full flex-wrap items-center gap-2">
          <div className="relative min-w-[220px] flex-1">
            <Search className="pointer-events-none absolute left-3 top-2.5 h-3.5 w-3.5 text-slate-400" />
            <input value={textFilter} onChange={(e) => setTextFilter(e.target.value)} placeholder={t("İlan, şirket veya yetenek ara")} className="w-full rounded-lg border border-slate-800 bg-slate-950 py-2 pl-9 pr-3 text-xs text-white placeholder:text-slate-500 focus:border-blue-500 focus:outline-none" />
          </div>
          <button type="button" aria-pressed={internshipOnly} onClick={() => setInternshipOnly((current) => !current)} className={`rounded-lg border px-3 py-2 text-xs font-semibold transition ${internshipOnly ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-300" : "border-slate-800 bg-slate-950 text-slate-300 hover:border-emerald-700/60"}`}>{internshipOnly ? t("Yalnızca staj") : t("Staj ilanlarını ara / filtrele")}</button>
          <button type="button" aria-pressed={includeStale} onClick={() => setIncludeStale((value) => !value)} className={`rounded-lg border px-3 py-2 text-xs font-semibold transition ${includeStale ? "border-amber-500/40 bg-amber-500/10 text-amber-200" : "border-slate-800 bg-slate-950 text-slate-300 hover:border-amber-700/60"}`}>{includeStale ? t("Eski ilanlar dahil") : t("Eski ilanları göster")}</button>
          <input value={locationFilter} onChange={(e) => setLocationFilter(e.target.value)} placeholder={t("Konum")} className="w-32 rounded-lg border border-slate-800 bg-slate-950 px-3 py-2 text-xs text-white placeholder:text-slate-500 focus:border-blue-500 focus:outline-none" />
          <select value={remoteFilter} onChange={(e) => setRemoteFilter(e.target.value)} className="rounded-lg border border-slate-800 bg-slate-950 px-3 py-2 text-xs text-slate-200 focus:border-blue-500 focus:outline-none">
            <option value="all">{t("Tüm çalışma şekilleri")}</option><option value="remote">{t("Remote")}</option><option value="hybrid">{t("Hybrid")}</option><option value="on-site">{t("On-site")}</option>
          </select>
          <select value={minimumMatch} onChange={(e) => setMinimumMatch(e.target.value)} className="rounded-lg border border-slate-800 bg-slate-950 px-3 py-2 text-xs text-slate-200 focus:border-blue-500 focus:outline-none">
            <option value="0">{t("Tahmini uyum: tümü")}</option><option value="50">{t("Tahmini uyum: 50+")}</option><option value="70">{t("Tahmini uyum: 70+")}</option><option value="85">{t("Tahmini uyum: 85+")}</option>
          </select>
          <select value={sortOrder} onChange={(e) => setSortOrder(e.target.value)} className="rounded-lg border border-slate-800 bg-slate-950 px-3 py-2 text-xs text-slate-200 focus:border-blue-500 focus:outline-none">
            <option value="match">{t("En yüksek eşleşme")}</option><option value="recent">{t("En yeni")}</option><option value="company">{t("Şirkete göre")}</option><option value="salary">{t("En yüksek ücret (belirtilmişse)")}</option>
          </select>
        </div>
        <div className="flex w-full flex-wrap items-center gap-2 pt-2 border-t border-slate-800/80">
          <div className="flex items-center gap-1.5 text-slate-400 font-semibold text-xs mr-1">
            <Filter className="w-3.5 h-3.5 text-blue-400" />
            <span>{t("Platform:")}</span>
          </div>
          <div className="flex flex-wrap items-center gap-1.5">
            {platformOptions.map(({ id, label, count, activeClass }) => {
              const isSelected = selectedPlatform === id;
              const isLinkedIn = id === "linkedin";
              return (
                <button
                  key={id}
                  type="button"
                  onClick={() => setSelectedPlatform(id)}
                  className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs transition border ${
                    isSelected
                      ? activeClass
                      : isLinkedIn
                      ? "border-[#0a66c2]/40 bg-[#0a66c2]/10 text-[#4ca2ff] hover:bg-[#0a66c2]/20 font-medium"
                      : "border-slate-800 bg-slate-950/70 text-slate-300 hover:border-slate-700 hover:text-white"
                  }`}
                >
                  <span className="capitalize">{label}</span>
                  <span
                    className={`text-[10px] px-1.5 py-0.2 rounded-full font-mono ${
                      isSelected
                        ? "bg-white/20 text-white font-bold"
                        : isLinkedIn
                        ? "bg-[#0a66c2]/30 text-[#4ca2ff]"
                        : "bg-slate-800 text-slate-400"
                    }`}
                  >
                    {count}
                  </span>
                </button>
              );
            })}
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-slate-400">{t("Eşleşme katmanı:")}</span>
          {["all", "High", "Medium", "Low"].map((tier) => (
            <button
              key={tier}
              onClick={() => setSelectedTier(tier)}
              className={`px-2 py-0.5 rounded text-xs ${
                selectedTier === tier ? "bg-slate-700 text-white" : "text-slate-400 hover:text-white"
              }`}
            >
              {t({ all: "Tümü", High: "Yüksek", Medium: "Orta", Low: "Düşük" }[tier] || tier)}
            </button>
          ))}
        </div>
        <button type="button" onClick={() => setFavoriteOnly((value) => !value)} className={`inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-xs font-semibold ${favoriteOnly ? "border-rose-500/40 bg-rose-500/10 text-rose-300" : "border-slate-800 text-slate-400 hover:text-white"}`}>
          <Heart className={`h-3.5 w-3.5 ${favoriteOnly ? "fill-current" : ""}`} /> {t("Favoriler")}
        </button>
      </div>

      {/* Batch command bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-800 bg-slate-950/60 px-4 py-3">
        <button
          onClick={toggleAllVisible}
          className="flex items-center gap-2 text-xs font-semibold text-slate-300 hover:text-white"
        >
          {filteredJobs.length > 0 && filteredJobs.every((job) => selectedJobIds.includes(job.id))
            ? <CheckSquare className="w-4 h-4 text-blue-400" />
            : <Square className="w-4 h-4 text-slate-400" />}
          {t("Görünen ilanların tümünü seç")} ({filteredJobs.length})
        </button>
        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-400">{selectedJobIds.length} {t("seçili")}</span>
          {selectedJobIds.length > 0 && (
            <>
              <button
                disabled={batchBusy}
                onClick={() => void runBatchAction("prepare")}
                className="rounded-lg border border-blue-500/30 bg-blue-500/10 px-3 py-1.5 text-xs font-semibold text-blue-300 hover:bg-blue-500/20 disabled:opacity-50"
              >
                {batchBusy ? t("İşleniyor...") : t("Toplu taslak hazırla")}
              </button>
              <button
                disabled={batchBusy}
                onClick={() => void runBatchAction("reject")}
                className="rounded-lg border border-rose-500/30 bg-rose-500/10 px-3 py-1.5 text-xs font-semibold text-rose-300 hover:bg-rose-500/20 disabled:opacity-50"
              >
                {t("Seçilenleri ele")}
              </button>
            </>
          )}
        </div>
      </div>

      {/* Jobs Feed List */}
      <div className="space-y-4">
        {filteredJobs.length === 0 ? (
          <EmptyFeedGuide hiddenByPageFilters={jobs.length > 0} emptyState={scanStatus?.empty_state || null} unavailable={scanStatusUnavailable} onClearFilters={clearFilters} />
        ) : (
          filteredJobs.map((job) => <JobCard key={job.id} job={job} ctx={cardContext} />)
        )}
      </div>
      {packagePreview && <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4" role="dialog" aria-modal="true" aria-labelledby="package-title">
        <div className="max-h-[90vh] w-full max-w-3xl overflow-y-auto rounded-2xl border border-slate-700 bg-slate-950 p-6 shadow-2xl">
          <div className="flex items-start justify-between gap-4"><div><p className="text-xs uppercase tracking-widest text-blue-400">{t("Kullanıcı incelemesi gerekli · Profil sürümü")} {packagePreview.profile_version}</p><h2 id="package-title" className="mt-1 text-xl font-bold text-white">{packagePreview.job.title} · {packagePreview.job.company}</h2></div><button onClick={() => setPackagePreview(null)} className="text-slate-400 hover:text-white">{t("Kapat")}</button></div>
          <div className="mt-4 rounded-xl border border-slate-800 bg-slate-900 p-4"><h3 className="text-sm font-semibold text-white">{t("Doğru deneyimle öne çıkar")}</h3><p className="mt-2 text-xs text-slate-300">{t("Eşleşen yetkinlikler:")} {(packagePreview.tailoring?.skills_to_highlight || []).join(", ") || t("İlan açıklamasına göre CV’ni gözden geçir.")}</p>{packagePreview.tailoring?.gaps_to_address_honestly?.length > 0 && <p className="mt-2 text-xs text-amber-300">{t("CV’de doğrulamadan ekleme:")} {packagePreview.tailoring.gaps_to_address_honestly.join(", ")}</p>}</div>
          <section className="mt-4 rounded-xl border border-slate-800 bg-slate-900 p-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div><h3 className="text-sm font-semibold text-white">{t("Bu ilana göre düzenlenmiş CV")}</h3><p className="mt-1 text-xs text-slate-400">{t("Bilgiler değiştirilmedi; yalnızca ilgili beceriler ve deneyim maddeleri öne alındı.")}</p></div>
              <div className="flex gap-2">
                <a href={buildApiUrl(`/apply/preview_tailored_cv?package_id=${packagePreview.package_id}`)} target="_blank" rel="noreferrer" className="rounded-lg border border-slate-700 px-3 py-2 text-xs font-medium text-slate-200 hover:bg-slate-800">{t("CV önizle")}</a>
                <a href={buildApiUrl(`/apply/download_tailored_cv?package_id=${packagePreview.package_id}`)} className="rounded-lg bg-emerald-700 px-3 py-2 text-xs font-semibold text-white hover:bg-emerald-600">{t("CV PDF indir")}</a>
              </div>
            </div>
            {packagePreview.tailored_cv?.summary && <p className="mt-3 text-xs leading-5 text-slate-300">{packagePreview.tailored_cv.summary}</p>}
            {packagePreview.tailored_cv?.skills?.length > 0 && <div className="mt-3 flex flex-wrap gap-1.5">{packagePreview.tailored_cv.skills.slice(0, 8).map((skill: string, index: number) => <span key={`${skill}-${index}`} className={`rounded-full border px-2.5 py-1 text-xs ${index < (packagePreview.tailoring?.skills_to_highlight?.length || 0) ? "border-emerald-700/60 bg-emerald-950/50 text-emerald-200" : "border-slate-700 text-slate-300"}`}>{skill}</span>)}</div>}
            {packagePreview.tailored_cv?.experience?.length > 0 && <div className="mt-3 space-y-2">{packagePreview.tailored_cv.experience.slice(0, 3).map((experience: any, index: number) => <p key={`${experience.title}-${experience.company}-${index}`} className="text-xs text-slate-300"><strong className="text-slate-100">{experience.title}</strong> · {experience.company}{experience.bullets?.[0] ? ` — ${experience.bullets[0]}` : ""}</p>)}</div>}
          </section>
          <textarea readOnly value={packagePreview.cover_letter} rows={12} className="mt-4 w-full rounded-xl border border-slate-800 bg-slate-900 p-4 text-sm leading-relaxed text-slate-200" />
          <p className="mt-3 text-xs text-slate-400">{t("Taslak oluşturuldu; hiçbir yere gönderilmedi. Gerçek başvuruyu yalnızca sen gözden geçirip gönderirsin.")}</p>
          <div className="mt-4 flex justify-end"><Link href="/kanban" onClick={() => setPackagePreview(null)} className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white">{t("Başvuruları takip et")}</Link></div>
        </div>
      </div>}
      {detailJob && <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4" role="dialog" aria-modal="true" aria-labelledby="job-detail-title">
        <div className="max-h-[90vh] w-full max-w-3xl overflow-y-auto rounded-2xl border border-slate-700 bg-slate-950 p-6 shadow-2xl">
          <div className="flex items-start justify-between gap-4"><div><p className="text-xs uppercase tracking-widest text-blue-400">{t("Canlı kaynak ilanı ·")} {detailJob.platform}</p><h2 id="job-detail-title" className="mt-1 text-xl font-bold text-white">{detailJob.title}</h2><p className="mt-1 text-sm text-slate-400">{detailJob.company} · {detailJob.location}</p></div><button onClick={() => setDetailJob(null)} className="text-slate-400 hover:text-white">{t("Kapat")}</button></div>
          <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4"><div className="rounded-xl border border-slate-800 bg-slate-900 p-3"><div className="text-xs text-slate-400">{t("Tahmini profil uyumu")}</div><div className="mt-1 text-lg font-bold text-emerald-400">≈ %{detailJob.match_score ?? "—"}</div></div><div className="rounded-xl border border-slate-800 bg-slate-900 p-3"><div className="text-xs text-slate-400">{t("Ghost riski")}</div><div className="mt-1 text-lg font-bold text-rose-300">%{detailJob.ghost_score ?? 0}</div></div><div className="rounded-xl border border-slate-800 bg-slate-900 p-3"><div className="text-xs text-slate-400">{t("Yayın tarihi")}</div><div className="mt-1 text-sm font-semibold text-white">{detailJob.posted_date || "Bilinmiyor"}</div></div><div className="rounded-xl border border-slate-800 bg-slate-900 p-3"><div className="text-xs text-slate-400">{t("Link durumu")}</div><div className="mt-1 text-sm font-semibold text-white">{linkLabels[linkStatus(detailJob.source_link_check)]}</div>{detailJob.source_link_check?.checked_at && <div className="mt-1 text-xs text-slate-400">{t("Son kontrol")}: {formatTimestamp(detailJob.source_link_check.checked_at, locale)}</div>}</div></div>
          <p className="mt-2 text-xs text-slate-400">{t("Bu eşleşme bir kural tabanlı tahmindir; işverenin kullandığı ATS skoru veya işe alınma olasılığı değildir.")}</p>
          {(detailJob.skill_gaps?.matched_evidence?.length > 0 || detailJob.skill_gaps?.missing_skills?.length > 0) && <section className="mt-4 rounded-xl border border-emerald-500/15 bg-emerald-500/[0.03] p-4"><h3 className="text-sm font-semibold text-white">{t("Eşleşme kanıtı ve beceri boşlukları")}</h3>{detailJob.skill_gaps?.matched_evidence?.length > 0 && <div className="mt-3"><div className="text-xs font-semibold uppercase tracking-wide text-emerald-300">{t("Profilden eşleşen beceriler")}</div><div className="mt-1 flex flex-wrap gap-1.5">{detailJob.skill_gaps.matched_evidence.map((item: any) => <span key={item.required_skill} className="rounded-full border border-emerald-500/20 px-2.5 py-1 text-xs text-emerald-200">{item.profile_evidence}</span>)}</div></div>}{detailJob.skill_gaps?.missing_skills?.length > 0 && <div className="mt-3"><div className="text-xs font-semibold uppercase tracking-wide text-amber-300">{t("İlan metninde aranıp profilde bulunmayan beceriler")}</div><div className="mt-1 flex flex-wrap gap-1.5">{detailJob.skill_gaps.missing_skills.map((item: string) => <span key={item} className="rounded-full border border-amber-500/20 px-2.5 py-1 text-xs text-amber-200">{item}</span>)}</div></div>}</section>}
          <div className="mt-3 rounded-xl border border-slate-800 bg-slate-900/60 p-3 text-xs text-slate-400">{t("Veri kaynağı")}: {detailJob.platform}{(detailJob.source_aliases || []).length > 0 ? ` · ${t("Aynı ilan şu kaynaklarda da bulundu")}: ${detailJob.source_aliases.map((alias: any) => alias.platform).join(", ")}` : ""} · {t("İlk görüldü")} {formatTimestamp(detailJob.first_seen_at, locale)} · {t("Kaynakta son görüldü")} {formatTimestamp(detailJob.last_seen_at, locale)}{detailJob.stale_at ? ` · ${t("Eskimiş olabilir: son taramada kaynak bu ilanı döndürmedi")}` : jobFreshness(detailJob).level === "aging" ? ` · ${jobFreshness(detailJob).days} ${t("gündür kaynakta yeniden doğrulanmadı")}` : ""}</div>
          <div className="mt-5 rounded-xl border border-slate-800 bg-slate-900 p-4"><h3 className="text-sm font-semibold text-white">{t("İlan açıklaması")}</h3><p className="mt-3 whitespace-pre-wrap text-sm leading-7 text-slate-300">{detailJob.description}</p></div>
          {detailJob.ghost_reasons?.length > 0 && <div className="mt-3 rounded-xl border border-rose-500/20 bg-rose-500/5 p-4"><h3 className="text-sm font-semibold text-rose-300">{t("Risk nedenleri")}</h3><ul className="mt-2 list-disc space-y-1 pl-5 text-xs text-rose-200">{detailJob.ghost_reasons.map((reason: string) => <li key={reason}>{reason}</li>)}</ul></div>}
          <div className="mt-5 flex flex-wrap items-center justify-between gap-3"><span className="text-xs text-slate-400">{t("İlanda belirtilen maaş:")}<strong className="text-white">{detailJob.salary_range || t("Belirtilmemiş")}</strong></span>{getExternalJobUrl(detailJob.url) && <a href={getExternalJobUrl(detailJob.url)!} target="_self" className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-xs font-semibold text-white hover:bg-blue-500">{t("Kaynak ilanda aç")}<ExternalLink className="h-3.5 w-3.5" /></a>}</div>
          {detailJob.salary_benchmark?.formatted_display && <div className="mt-3 rounded-xl border border-amber-500/20 bg-amber-500/5 p-3"><div className="text-xs font-semibold text-amber-200">{t("Piyasa tahmini")}: {detailJob.salary_benchmark.formatted_display}</div><p className="mt-1 text-xs text-slate-400">{t("Bu kural tabanlı bir tahmindir; işveren tarafından bildirilmemiş veya doğrulanmamıştır.")}</p></div>}
          <section className="mt-5 rounded-xl border border-slate-800 bg-slate-900 p-4">
            <h3 className="text-sm font-semibold text-white">{t("Şirket ve ilan güvenilirliği")}</h3>
            <p className="mt-1 text-xs text-slate-400">{t("Bildirimin yalnızca bu hesabında saklanır; topluluk doğrulaması veya bağımsız teyit anlamına gelmez.")}</p>
            <textarea value={jobFeedbackNote} onChange={(event) => setJobFeedbackNote(event.target.value)} maxLength={2000} rows={2} placeholder={t("İstersen kısa bir not ekle (kişisel bilgi paylaşma)")} className="mt-3 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-white" />
            <div className="mt-3 flex flex-wrap gap-2">
              {[
                ["company_suspicious", "Şirket/ilan şüpheli"],
                ["company_positive", "Şirket bilgisi tutarlı"],
                ["salary_mismatch", "Maaş bilgisi uyuşmuyor"],
                ["salary_consistent", "Maaş bilgisi tutarlı"],
                ["salary_outdated", "Maaş bilgisi güncel değil"],
                ["listing_closed", "İlan kapanmış/dolmuş"],
              ].map(([feedbackType, label]) => {
                const selected = jobFeedbackTypes.includes(feedbackType);
                return <button key={feedbackType} type="button" disabled={jobFeedbackBusy !== null} onClick={() => void toggleJobFeedback(feedbackType)} className={`rounded-lg border px-3 py-2 text-xs disabled:opacity-50 ${selected ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-200" : "border-slate-700 text-slate-300 hover:bg-slate-800"}`}>
                  {jobFeedbackBusy === feedbackType ? t("Kaydediliyor…") : selected ? `${t(label)} · ${t("Geri al")}` : t(label)}
                </button>;
              })}
            </div>
            {jobFeedbackNotice && <p role="status" className="mt-3 text-xs text-slate-300">{jobFeedbackNotice}</p>}
            {jobFeedbackTypes.length > 0 && <p className="mt-2 text-xs text-slate-400">{t("Bu ilan için kayıtlı kişisel bildirimin sayısı")}: {jobFeedbackTypes.length}</p>}
          </section>
        </div>
      </div>}
    </div>
  );
}
