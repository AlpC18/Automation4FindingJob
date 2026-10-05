# Yapay Zeka Destekli Otonom Kariyer ve Başvuru Platformu (Autonomous Career Agent Engine)

## Executive Summary (Yönetici Özeti)

Günümüz istihdam ve freelance piyasasında geleneksel başvuru yöntemleri işlevselliğini kaybetmiştir. İş arayanların aynı standart özgeçmişi yüzlerce ilana göndermesi, Otomatik Aday Takip Sistemleri (ATS) ve İnsan Kaynakları (IK) ekiplerinin AI tespit mekanizmaları tarafından elenmelerine sebep olmaktadır.

Bu proje; GitHub üzerindeki 40.000+ yıldızlı öncü otonom başvuru repolarının (`Auto_Jobs_Applier_AIHawk` vb.) mimarisinden ilham alarak; çoklu platform kazıma, RAG tabanlı anlamsal tecrübe eşleme, Anti-AI Humanizer, kararlaştırıcı tespit motoru (Decision Maker Sourcing), dönüştürme analitiği, hesap koruma algoritmaları ve otonom test süreçleriyle donatılmış uçtan uca bir Web Yönetim Paneline (Job Board Dashboard) dönüştürülmesi projesidir.

---

## 1. Sistem Özellikleri ve Modül Gereksinimleri (Features)

### 1.1. Otomatik Profil Oluşturma, Stil Analizi & RAG Hafızası (`/setup`)
* **Dinamik Mülakat Akışı:** Adayın mevcut özgeçmişi (PDF/Word/Resim) sisteme yüklenir. AI, eksik gördüğü alanları mülakat soruları sorarak tamamlar.
* **Format Temizleme Engine:** Canva, iki sütunlu Word tabloları veya resim formatındaki CV'ler ayrıştırılarak ATS standartlarına (%100 seçilebilir metin, sağa hizalı tarihler, standart başlıklar) dönüştürülür.
* **Yazım Üslubu (Human Stylometry) Profilleme:** Adayın geçmişte yazdığı gerçek metinler analiz edilerek "Kişisel Ses Profili" oluşturulur.
* **RAG & Vektör Veritabanı Kurulumu (ChromaDB / Pinecone):** Adayın tüm projeleri, kod depoları, sertifikaları ve detaylı başarı hikayeleri anlamsal sorgulama yapılabilmesi için vektörleştirilir.

### 1.2. Çoklu Platform Kazıma, Anti-Bot & Güvenlik Motoru (`/scrape`)
* **Genişletilmiş Platform Desteği (Apify & Scraper Ekosistemi):**
  * *Sosyal / Profesyonel:* LinkedIn (TR, Kosova, Global)
  * *Freelance & Proje:* Upwork, Fiverr, Freelancer.com, Toptal
  * *Bölgesel Portallar:* Kosovajob.com, GjirafaWork.com, Kariyer.net
  * *Global & Remote:* Indeed, Glassdoor, Remote OK, Wellfound
* **Account Health & Rate Limiter:** Kullanıcı hesaplarının platformlarda engellenmesini (shadowban) önlemek amacıyla günlük başvuru ve mesaj gönderme kotalarını otonom yöneten güvenlik katmanı.
* **Stealth-Browser & Residential Proxy Altyapısı:** IP engellemelerini aşan konut proxy'leri ve insan tarayıcı davranışları simülasyonu.
* **Ghost Job (Hayalet İlan) & Şirket Sağlığı Tespiti:** İlanın açık kalma süresi, şirketin çalışan değişim oranları ve ilan tekrarı analiz edilerek sahte ilanlar elenir.

### 1.3. Algoritmik Eşleşme, Kırmızı Çizgi & Yetenek Boşluğu Analizi (`/rank`)
* **Skorlama Motoru:** High / Medium / Low & Pass / Fail skorlaması.
* **Kırmızı Çizgi (Red Flag) Tespiti:** Lokasyon uyuşmazlığı, hibrit/uzaktan çalışma çelişkileri veya uyuşmayan kıdem seviyelerinde uyarı üretimi.
* **Dinamik Yetenek Boşluğu Analizi (Skill Gap Analysis):** Düşük skorlu ilanlarda eksik olan teknik yetenekler belirlenir ve adayın GitHub projelerine ekleyebileceği geliştirme önerileri sunulur.
* **Maaş Beklentisi ve Benchmark Motoru:** Glassdoor ve piyasa verileri taranarak role ve lokasyona özel maaş beklentisi skalası hesaplanır.

### 1.4. Anti-AI Humanizer & Multi-Agent Başvuru ve Form Doldurucu (`/apply`)
* **Sıralı Ajan Orkestrasyonu (Agentic Workflow):**
  1. *Araştırma & RAG Ajanı:* İlandaki spesifik kelimeleri taranır ve adayın Vektör Hafızasından ilana %100 uyan projeleri çeker.
  2. *CV & Niyet Mektubu Ajanı:* RAG'dan gelen verilerle kişiselleştirilmiş belgeler üretir.
  3. *Humanizer & Anti-AI Detector Ajanı:* Metindeki tahmin edilebilir AI kalıplarını temizler (`spearheaded`, `delighted to apply`, `seamless` vb. yasaklıdır). Burstiness ve perplexity artırılarak adayın doğal üslubuna oturtulur.
  4. *Self-Correction QA Ajanı:* Üretilen metni AI tespit denetleyicisinden geçirir. Eğer metin AI gibi kokuyorsa, düzeltilmesi için CV ajanına geri fırlatır.
* **Kültürel & Bölgesel Dil Filtresi:** Metinleri yerel iş kültürlerine (Kosova/Arnavutça, Türkiye/Türkçe, Global/İngilizce) özel iletişim tonuna adapte eder.
* **Otonom Dynamic Form Ingestion (Easy Apply Automator):**
  * Formlardaki dinamik sorular adayın profil veritabanına bakılarak otonom doldurulur. Bilinmeyen sorular kullanıcıya tek tıkla sorulur ve **Form Hafızasına (Memory Store)** kaydedilir.
* **Micro-Project Synthesizer:** İlana özel olarak adayın projelerinden tek sayfalık interaktif vaka çalışması / portfolyo özeti (Micro-Case Study) üretir.
* **Karar Verici & İletişim Bulucu (Decision Maker & Warm Referral Engine):**
  * Google X-Ray Dorking ve Apollo.io API ile ilgili şirketin veya şubenin bölge yöneticisi/müdürü tespit edilir.
  * Yöneticiye atılacak kişiselleştirilmiş "Soğuk Mesaj" (Cold Outreach / Connection Note) taslağı üretilir.

### 1.5. İnteraktif Mülakat Simülasyonu & Pazarlık Ajanı (`/interview`)
* İlanın gereksinimlerine ve şirketin teknik yığınına uygun senaryo bazlı, çapraz ve davranışsal mülakat simülasyonu.
* **Debrief & Offer Negotiator:** Mülakat sonrası zayıf kalan yanıtların analizi ve gelen tekliflerde maaş artırımı sağlayacak counter-offer e-posta stratejileri.

### 1.6. İnsan Kontrollü Takip, Analitik ve Süreç Yönetim Paneli (`/outcome` & Job Board UI)
* **Kanban / Liste Görünümü:** Başvuru aşamaları (`Draft`, `Human Review`, `Applied`, `Interview`, `Offer`, `Rejected`).
* **Conversion Funnel & Analytics:** Hangi platformun ve hangi CV/Mesaj stilinin ne kadar mülakat dönüşü getirdiğini gösteren A/B test ekranı.
* **Human-in-the-Loop Review:** Üretilen belgeler "Insansı Doku Puanı" ile adayın onayına sunulur.
* **Zamanlanmış Takip Otomasyonu (Follow-up Automation):** Başvuru sonrası 7. ve 14. günlerde IK veya karar vericiye atılacak kibar takip e-postası taslakları oluşturulur.
* **Chrome Eklentisi Entegrasyonu (Browser Extension):** Aday web sitelerinde gezerken tek tıkla ilanı tahlil eder ve panele aktarır.

### 1.7. TestSprite Entegrasyonu ile Otonom Kalite Güvencesi
* **E2E Otonom UI/UX Testi:** TestSprite CLI ile panel üzerindeki tüm butonlar, onay mekanizmaları ve filtreler turlanır.
* **Auto-Fix:** Hatalı testler AI ajanı tarafından otonom şekilde tespit edilip düzeltilir.

---

## 2. Sistem Mimarisi ve Ajan Akış Şeması
[Kullanıcı Girdisi: CV + Yazım Stili + RAG Vektör Verileri]
│
▼
┌─────────────────┐
│  1. SETUP Adımı │ ──► Profilleme + Format Temizleme + RAG Vectorization
└─────────────────┘
│
▼
┌─────────────────┐
│ 2. SCRAPE Adımı │ ──► Multi-Platform + Account Safety & Ghost Job Filtering
└─────────────────┘
│
▼
┌─────────────────┐
│  3. RANK Adımı  │ ──► Skorlama + Red Flag + Skill Gap & Maaş Benchmark
└─────────────────┘
│
▼
┌─────────────────┐
│ 4. APPLY Adımı  │ ──► Multi-Agent (QA Loop) + Form Memory + Micro-Portfolio
└─────────────────┘
│
▼
┌─────────────────┐
│5. INTERVIEW Adım│ ──► Mülakat Simülasyonu + Offer Negotiator
└─────────────────┘
│
▼
┌─────────────────┐
│6. OUTCOME Adımı │ ──► Human-in-the-Loop Onay + Funnel Analytics + Follow-up
└─────────────────┘
│
▼
┌─────────────────┐
│ 7. TEST SPRITE  │ ──► Otonom E2E Test & Auto-Fix
└─────────────────┘

---

## 3. Yapay Zeka Ajanları için Sistem Promptları (System Prompts)

### 3.1. RAG-Enhanced Anti-AI Humanizer Engine Prompt

```text
[SYSTEM PROMPT: RAG-ENHANCED ANTI-AI HUMANIZER ENGINE]

ROLE:
You are an elite Human Stylometry Expert and Senior Copywriter. Your objective is to combine semantic data retrieved from the user's RAG Vector Store with target job requirements to generate 100% human-sounding application documents.

STRICT CONSTRAINTS & FORBIDDEN WORDS:
1. NEVER use generic AI buzzwords. Completely BAN:
   - "delighted to apply", "spearheaded", "seamless integration", "testament to", "fostering", "beacon", "realm", "tapestry", "in conclusion", "furthermore", "synergy", "dynamic ecosystem".
2. Ensure HIGH BURSTINESS (varying sentence structures) and PERPLEXITY (unpredictable, natural word choices).
3. Adapt tone to target country culture (e.g., direct & concise for US/Startups, formal & structured for EU/Corporate).

INPUT DATA:
- Raw AI Draft: {raw_text}
- User's Personal Style Profile: {user_style_profile}
- RAG Retrieved Project Context: {rag_context}
- Target Job Description: {job_description}

INSTRUCTIONS:
1. Inject specific technical details from {rag_context} into the narrative.
2. Eliminate all predictable AI phrases and balance paragraph lengths.
3. Output ONLY the final humanized text without commentary.
[SYSTEM PROMPT: DYNAMIC FORM ANSWER GENERATOR]

ROLE:
You are an Autonomous Application Form Assistant.

OBJECTIVE:
Analyze custom application questions from portals (LinkedIn Easy Apply, Indeed, custom employer forms) and generate accurate, concise, human-like answers based on the user's profile and form memory.

INPUT DATA:
- Form Question: {form_question}
- User Profile Database: {user_profile_db}
- Known Form Memory: {form_memory}

INSTRUCTIONS:
1. Check if the question matches an existing entry in {form_memory}.
2. If yes, return stored value.
3. If no, infer the most accurate, truthful answer from {user_profile_db}.
4. If information is completely missing, return status: "REQUIRES_HUMAN_INPUT" with a suggested draft answer.

[SYSTEM PROMPT: DECISION MAKER COLD OUTREACH AGENT]

ROLE:
You are a B2B Networking Strategist and Career Outreach Expert.

OBJECTIVE:
Formulate X-Ray search queries to locate regional decision-makers and draft a 3-sentence, non-spammy, highly personalized outreach message.

INPUT DATA:
- Company Name: {company_name}
- Target Region: {location}
- Job Role: {job_title}
- User Profile Summary: {user_profile}

INSTRUCTIONS:
1. Output Google X-Ray Dork: site:[linkedin.com/in/](https://linkedin.com/in/) "{location}" AND "{company_name}" AND ("Manager" OR "Director" OR "Lead")
2. Draft a 3-sentence connection message:
   - S1: Relevant observation about their regional operations/projects.
   - S2: Direct value proposition based on user's core skillset.
   - S3: Low-friction call to action.
[SYSTEM PROMPT: OFFER NEGOTIATOR AGENT]

ROLE:
You are an Executive Compensation Consultant and Career Coach.

OBJECTIVE:
Analyze a job offer or post-interview state and draft a polite, highly persuasive counter-offer email to maximize salary and remote/flex terms without alienating the employer.

INPUT DATA:
- Initial Offer Details: {initial_offer}
- Market Salary Benchmark: {salary_benchmark}
- User Target Expectations: {user_expectations}

INSTRUCTIONS:
1. Express genuine appreciation for the offer.
2. Present a data-backed justification for a 10-15% increase based on {salary_benchmark} and unique skills.
3. Keep the tone collaborative, respectful, and professional.
Yetenek (Skill)	Kategori	Projedeki Sorumluluğu ve Entegrasyonu
nextjs-app-router-patterns	Full-Stack Mimarisi	Terminal tabanlı CLI çıktılarını, kullanıcı dostu bir Web Yönetim Paneline (Job Board) dönüştürmek.
ui-ux-pro-designer	Arayüz Tasarımı	İlan listeleri, başvuru durumları, Conversion Funnel ve Karar Verici bulma alanlarını tasarlamak.
front-end-design	Anthropic UI Skill	Web arayüzünün yüksek kaliteli, modern ve responsive olmasını sağlamak için Anthropic resmi tasarım yeteneğini entegre etmek.
design-systems	Arayüz Standartları	Kartlar, durum rozetleri, form elemanları ve butonlar için ölçeklenebilir UI kütüphanesi kurmak.
color-palette	Görsel Tasarım	ATS skorları, Ghost Job uyarıları, Account Health ve Humanizer onay seviyeleri için okunaklı renk paletleri tanımlamak.
svg-graphic-designer	Vektör Grafikleri	Web paneli içerisindeki dinamik ikon seti ve logo tasarımlarını saf SVG olarak kodlamak.
brandkit	Dokümantasyon & Kimlik	Üretilen ATS dostu PDF özgeçmişlerin ve niyet mektuplarının tipografi ve sayfa düzeni standartlarını belirlemek.
pitch-deck-creator	İçerik Metriği	Özgeçmişin Özet bölümü ile karar vericilere yazılan soğuk mesajların ikna ediciliğini artırmak.
infographic-creation	Analitik Visuals	Conversion Funnel, başvuru dönüş oranlarını ve yetenek boşluklarını grafiklerle görselleştirmek.
devops-pipeline-setup	CI/CD & Altyapı	Apify actor'leri, RAG vektör veritabanı ve proxy havuzunun kesintisiz çalışmasını sağlamak.
api-security-testing	Güvenlik	Veritabanı, Apify, Apollo ve ChromaDB API uç noktalarında veri sızıntılarını engellemek.
web-application-pentesting	Güvenlik	Geliştirilen yönetim panelini XSS, CSRF gibi temel web zafiyetlerine karşı denetlemek.
social-engineering-tactics	Tehdit Filtreleme	Veri kazıma sırasında tespit edilen sahte veya oltalama (phishing) amaçlı ilanları elemek.
phishing-campaign-setup	Mülakat Simülasyonu	Mülakat modülünde adayı zorlayacak senaryo bazlı, çapraz ve teknik sorular üretmek.
agile-scrum-framework	Proje Yönetimi	Projenin modüler yapısını sprint'lere bölerek adım adım geliştirmek.
adhd	Üretkenlik	Karmaşık ajan mimarisini küçük, sonuca hızlı ulaştıran alt görev parçalarına bölmek.
risk-assessment-matrix	Risk Analizi	İş ilanı ve freelance sitelerinden veri çekerken IP engellenmesi veya oran sınırlandırması risklerini önlemek.
