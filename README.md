# Yapay Zeka Destekli Otonom Kariyer ve Başvuru Platformu (Autonomous Career Agent Engine)

Bu repo; LinkedIn, Upwork, Kosovajob ve Global Remote iş portallarında otonom iş arama, başvuru yapma, Anti-AI Humanizer süzgeciyle insan elinden çıkmış belgeler üretme, karar verici yöneticileri tespit etme (Google X-Ray Dorking) ve mülakat simülasyonu sağlayan uçtan uca Web Yönetim Paneli (Job Board Dashboard) projesidir.

---

## 🚀 Hızlı Başlangıç

### Tek Komutla Başlatma:
```bash
./start_system.sh
```

Varsayılan geliştirme modu dış portal taramasını backend açılışında otomatik başlatmaz. İsterseniz `.env` içinde `STARTUP_SEED_ENABLED=true` kullanabilirsiniz. Üretim kurulumlarında ayrıca `API_AUTH_TOKEN`, `APP_ENCRYPTION_KEY` ve `CORS_ORIGINS` tanımlanmalıdır.

Mevcut yerel veritabanı bulunan kurulumlarda `scripts/bootstrap_env.py` yeni şifreleme anahtarı üretmek yerine `backend/data/.app_encryption_key` dosyasındaki korunan anahtarı kullanır; veritabanı varsa ama anahtar bulunamıyorsa işlemi durdurur. `.env` yanlışlıkla farklı bir anahtarla oluşturulduysa `backend/.venv/bin/python scripts/restore_local_env_key.py` mevcut Apify kayıtlarını doğrular ve anahtarı `.env` ile güvenli biçimde eşitler. Gizli değerler terminale yazdırılmaz.

`MULTI_TENANT_ENABLED=true` iken panel kayıt/giriş ekranı sunar; her hesabın uygulama verisi ayrı SQLite dosyasında veya PostgreSQL şemasında tutulur. Üretimde `.env` içine güçlü ve sabit bir `AUTH_SECRET_KEY` koyun (ör. `openssl rand -hex 32`); anahtarı deploy'lar arasında değiştirmek mevcut oturumları geçersiz kılar. LinkedIn çerezleri ve görülen ilan dosyaları da tenant klasörüne ayrılır. Eski veritabanı kurulumları açılışta sürümlü şema revizyonlarını uygular.

Üretimde kayıt doğrulaması ve parola kurtarma için `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS` ve `SMTP_FROM_EMAIL` ayarlayın. Oturum-cookie kullanan değiştirici istekler CSRF başlığıyla korunur; hatalı girişler e-posta/IP bazında sınırlandırılır. Kullanıcı oturum menüsünden e-posta ve mevcut parolayı yeniden girerek hesabını ve tenant verisini silebilir. 

AI sağlayıcıları: `/llm` sayfasından Anthropic (Claude), OpenAI, Gemini, DeepSeek, Ollama (yerel) veya herhangi bir OpenAI-uyumlu servis (Groq, OpenRouter, Cerebras vb.) için API anahtarınızı şifreli olarak saklayabilir, bağlantıyı test edebilir veya kaldırabilirsiniz. Anahtarlar API yanıtında tekrar gösterilmez. `CUSTOM_LLM_BASE_URL`, `CUSTOM_LLM_API_KEY` ve `CUSTOM_LLM_MODEL` ile herhangi bir OpenAI-uyumlu hizmet desteklenir (ör. `https://api.groq.com/openai/v1`). `LLM_DAILY_TOKEN_BUDGET` Anthropic Token harcama sınırı olup, aşıldığında şablon motoru devralır; diğer sağlayıcılara uygulanmaz. Seçilen sağlayıcı ve günlük kullanım veri klasöründe kalıcı hale getirilir.

Yerel geliştirmede şifreleme anahtarı `backend/data` altında özel izinle oluşturulur; üretimde sabit `APP_ENCRYPTION_KEY` değerini gizli ortam değişkeni olarak tanımlayın.

Harici hata/trace izlemesi için isteğe bağlı olarak `SENTRY_DSN` ve `SENTRY_TRACES_SAMPLE_RATE` verin. PII otomatik eklenmez. Uygulama ayrıca oturum sayısı ve gecikme histogramını Prometheus formatında `/api/system/metrics` üzerinden verir (uç normal hesap oturumuyla korunur). SQLite yedeği `/api/system/backup` üzerinden indirilebilir. PostgreSQL Docker kurulumunda `postgres-backup` hizmeti her gün doğrulanmış, izinleri kısıtlı bir custom-format yedek üretir; son 14 günlük yedekler `postgres-backups` volume'ünde tutulur. Süre `BACKUP_INTERVAL_SECONDS`, saklama süresi `BACKUP_RETENTION_DAYS` ile ayarlanır. Geri yükleme hedef veritabanını değiştirir; yalnızca doğru yedek dosyasını ve hedefi kontrol ettikten sonra `CONFIRM_RESTORE=YES` ile `scripts/restore-postgres.sh` çalıştırın. Canlıya almadan önce sağlayıcı point-in-time backup'ını da etkin tutun.

### Dinamik Docker kurulumu

Compose dosyası servis adlarını sabitlemez; portlar, image sürümleri, worker sayıları, public URL'ler, veritabanı, Redis, scraper modu ve scheduler saatleri `.env` üzerinden değiştirilebilir. Compose varsayılan olarak PostgreSQL kullanır; veritabanı override'ı gerekiyorsa `COMPOSE_DATABASE_URL`, Redis override'ı için `COMPOSE_REDIS_URL` kullanın (`DATABASE_URL` ve `REDIS_URL` yerel geliştirme sürecine aittir). Docker çalıştırmadan önce `POSTGRES_PASSWORD`, `REDIS_PASSWORD`, `API_AUTH_TOKEN`, `AUTH_SECRET_KEY` ve `APP_ENCRYPTION_KEY` için güçlü ve kalıcı sırlar belirleyin. Gerçek verilerle başlamak için `DEMO_DATA_ENABLED=false` ve sağlayıcı ayarlarını kullanın; yerel fixture görmek için açıkça `DEMO_DATA_ENABLED=true` seçin.

Canlı ilan akışında `remote` kaynağı RemoteOK, Arbeitnow, Remotive, Jobicy ve Himalayas herkese açık feed'lerini sorgulamaktadır. Apify kaynakları için `.env` dosyasında ilgili `APIFY_ACTOR_*` Actor ID'sini ve `APIFY_API_TOKEN`'ı tanımlayın; actor'a özel arama alanları gerekiyorsa `APIFY_INPUT_*` JSON'larıyla ekleyin. Her kaynak aynı normalize ilan alanlarını üretir, hatalar kaynak adıyla raporlanır. Açık API feed'lerini kullanan dağıtımlar ilan kaynağına atıf ve orijinal ilana bağlantı gösterir.

Apify sağlayıcıları `/sources` ekranından tenant bazında ayarlanabilir; çalışma geçmişi ve son hata bu ekranda görünür. Arka plan iş kuyruğu `/inbox` içinden izlenir. SQLite kullanan hesaplar aynı ekrandan tutarlı veritabanı yedeği indirebilir. Yedekten dönmek için uygulamayı durdurun, arşivi ilgili `career_engine.db` (tenant kurulumunda `tenants/<tenant-id>.db`) konumuna geri koyun, sonra uygulamayı başlatın. PostgreSQL compose dağıtımlarında günlük otomatik yedekleme de etkinleşir. Worker heartbeat'i 20 dakika aşan işler kuyruk ekranında başarısız gösterilir ve yeniden denenebilir.


```bash
# Her sırrı kriptografik olarak üretir, .env dosyasını 0600 izinle oluşturur.
# Mevcut yerel geliştirme sunucularını (3000/8000) korumak için alternatif portlar kullanır.
python3 scripts/bootstrap_env.py --isolated-ports
docker compose up -d --build
docker compose up -d --scale celery-worker=2
```

Oluşturulan `.env` git dışında tutulur ve yeniden çalıştırıldığında mevcut dosyanın üzerine yazılmaz. Normal 3000/8000 Docker portlarını kullanmak için `--isolated-ports` seçeneğini kaldırın. İlk hesap kaydı için çok kullanıcılı mod açıktır; e-posta doğrulama ve parola kurtarma için SMTP ayarlarını ekleyin.

Tarayıcı tarafındaki API adresi image yeniden derlenmeden `PUBLIC_API_URL` ile `RUNTIME_API_URL` üzerinden `runtime-config.js` dosyasına yazılır. Sağlık ve güvenli runtime bilgisi `/api/system/health` ile `/api/system/runtime-config` uçlarından izlenebilir. OAuth callback adresleri için `BACKEND_PUBLIC_URL` ve `GOOGLE_REDIRECT_URI` / `MICROSOFT_REDIRECT_URI` değerlerini deploy edilen host adına göre ayarlayın.

Servisler açıldığında:
* **Web Yönetim Paneli (Next.js):** [http://localhost:3000](http://localhost:3000)
* **Backend API Swagger Dokümantasyonu:** [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 🛠️ Mimari ve Modül Kapsamı

| Modül | Bölüm | Fonksiyon ve Görevi |
| :--- | :--- | :--- |
| **1.1 Profil & RAG** | `/setup` | Dinamik Mülakat Soruları, Format Temizleme (%100 ATS Standardı), Yazım Üslubu (Human Stylometry) ve Vektör Hafızası. |
| **1.2 Kazıma & Güvenlik** | `/scrape` | Anahtarsız kaynaklar (KosovaJob, RemoteOK, Arbeitnow, Remotive, Jobicy, Himalayas, şirket kariyer sayfaları) ve Apify üzerinden portallar; Hayalet İlan (Ghost Job) tespiti ve Günlük Güvenlik Kotaları. Ayrıntı aşağıdaki "İlan kaynakları" bölümünde. |
| **1.3 Algoritmik Sıralama** | `/rank` | ATS Eşleşme Skoru (%0-100), Kırmızı Çizgi (Red Flag) tespiti, Yetenek Boşluğu (Skill Gap) ve Bölgesel Maaş Skalası. |
| **1.4 Humanizer & Multi-Agent** | `/apply` | Anti-AI Humanizer Engine, LangGraph sıralı iş akışı, Form Memory Store (Easy Apply), Micro-Case Study ve Karar Verici X-Ray Dorkları. |
| **1.6 Takip & Analitik** | `/outcome` | Kanban başvuru takip paneli, Dönüşüm Hunisi (Conversion Funnel), A/B üslup testleri ve 7./14. gün kibar takip otomasyonu. |

---

## 🛡️ Anti-AI Humanizer Kuralları & Yasaklı Sözcükler

Sistem, yapay zeka tespit algoritmalarını (ZeroGPT, CopyLeaks vb.) ve IK ön eleme sistemlerini aşmak için aşağıdaki buzzword'leri tamamen yasaklamıştır ve otomatik olarak doğal alternatifleriyle değiştirir:
* `delighted to apply`, `spearheaded`, `seamless integration`, `testament to`, `fostering`, `beacon`, `realm`, `tapestry`, `in conclusion`, `furthermore`, `synergy`, `dynamic ecosystem`

Metinler yüksek **Burstiness** (cümle boyu varyasyonu) ve zengin söz dağarcığı (TTR) ile üretilir.

---

## 🧩 Chrome Eklentisi (1-Click Ingestion)

1. Tarayıcınızda `chrome://extensions/` adresini açın.
2. "Geliştirici Modu"nu (Developer Mode) aktif edin.
3. "Paketlenmemiş Öğe Yükle" (Load Unpacked) butonuna basıp projedeki `extension/` klasörünü seçin.
4. LinkedIn, Upwork veya Kosovajob ilanlarında tek tıkla ilanı çekip panele aktarın.

---

## ⚡ Entegrasyonlar ve Altyapı

1. **LinkedIn Session Handshake (`cookies.json`):**
   * Chrome Eklentisi üzerinden tek tıkla kullanıcının aktif `li_at` ve `JSESSIONID` oturum çerezlerini backend'e aktarır.
   * Playwright Stealth Worker oturumla portalı inceler; gerçek gönderim açıkça başlatılmadıkça hiçbir başvuruyu `Applied` olarak işaretlemez ve portal onayı olmadan başarı raporlamaz.
   * `/safety` sayfasından canlı oturum durumu izlenebilir ve manuel çerez yapıştırılabilir.

2. **Kuyruk Mimarisi (Celery + Redis Worker - Dual-Mode):**
   * Ağır kazıma (scraping), Playwright form doldurma ve ATS sıralama işlemlerini Redis mesaj kuyruğu üzerinden Celery worker'larına dağıtır.
   * Docker ortamında (`docker-compose.yml`) otomatik Redis ve Celery Worker ayağa kalkar; yerel hafif geliştirmede ise otomatik Asenkron Yerel Mod'a geçerek sıfır bağımlılıkla çalışır.
   * `/inbox` ve `/safety` üzerinden canlı kuyruk durumu izlenebilir.
   * Tarama ve gerçek portal gönderim işleri tenant DB'sinde kalıcı tutulur: `GET /api/tasks/jobs` listeyi, `GET /api/tasks/jobs/{job_id}` ayrıntıyı verir; başarısız desteklenen işler `POST /api/tasks/jobs/{job_id}/retry` ile yeniden denenebilir. Tarama isteklerinde `Idempotency-Key` kullanmak aynı işin yinelenmesini önler.

   * Auto-apply akışı iki aşamalıdır: taslak onayı ve açık browser gönderim adımı. Tarayıcı veya portal gönderimi doğrulanmadıkça ilan gerçek başvuru olarak raporlanmaz.
   * Kanban `Applied` aşaması ile dış portal gönderimi ayrıdır: `submission_state=pending_confirmation` simülasyon/iş akışını, `/api/outcome/confirm_submission` ise doğrulanmış gönderimi kaydeder; `application_execution_mode` bunun `simulation` veya `live` olduğunu açıkça belirtir.

3. **Resmi E-posta OAuth2 Entegrasyonu (Gmail & Outlook):**
   * Google Cloud Console (Gmail REST API) ve Microsoft Azure AD (Graph API) üzerinden tek tıkla resmi OAuth2 yetkilendirmesi.
   * Uygulama şifresi (App Password) ihtiyacını ortadan kaldırır. Gelen e-postaları otonom olarak çekip Inbox AI sınıflayıcısına ve Kanban durum makinesine aktarır.

   * `OPENAI_API_KEY` yoksa arayüz tarayıcı Speech API fallback'ini kullanır; sunucu uçları açıkça `503` döner.
   * Gmail ve Microsoft OAuth senkronizasyonu unread mesajları çekip Inbox Agent'a aktarır; provider message ID deduplication ile aynı e-posta tekrar işlenmez. OAuth access token'ları süresi dolduğunda refresh token ile yenilenir.

5. **Üretim veri katmanı seçeneği:**
   * Geliştirme varsayılanı SQLite'tır. Docker Compose varsayılan olarak PostgreSQL + pgvector ile başlar; `DATABASE_URL=sqlite:///...` ile yerel fallback korunur.
   * Geçiş geriye dönük qmark SQL uyumluluk katmanıyla kademeli yapılabilir; PostgreSQL modunda seen-job kayıtları ve semantic search aynı veritabanında tutulur. SQLite modunda Chroma fallback'i korunur.
   * Compose ayrıca `daemon-worker` servisini çalıştırır. Bu servis web API'den bağımsız olarak 24/7 scheduler'ı yürütür: 03:30 gece taraması, 08:00 taslak hazırlığı ve Telegram bildirimi. Yerel API sürecinde aynı daemon'ı çalıştırmak isterseniz `AUTO_START_DAEMON=true` kullanabilirsiniz; ikisini aynı anda etkinleştirmeyin.
   * PDF doğrulama katmanı `pypdf` ile text-layer ve ATS keyword kontrollerini container içinde harici Poppler kurulumu olmadan yapabilir.

6. **Yedekleme ve kurtarma:**
   * SQLite modunda çalışma verisi uygulama başlarken ve `BACKUP_INTERVAL_SECONDS` aralığında (varsayılan 1 gün) şifreli arşivlenir; varsayılan saklama süresi 14 gündür.
   * `BACKUP_DIR` tanımlanırsa oraya, yoksa veri klasörüne yedekler kaydedilir. `BACKUP_RETENTION_DAYS` ve `BACKUP_MAX_SIZE_MB` ile saklama ve boyut sınırı ayarlanabilir. Şifreli yedekler mevcut `APP_ENCRYPTION_KEY` ile açılır; bu anahtar yedeğin içine konmaz, ayrı ve güvenli saklanmalıdır.
   * `scripts/backup-data.sh` el ile yedek almayı sağlar. İlan kaynakları ekranındaki geri yükleme önce mevcut verinin güvenlik kopyasını alır ve yalnızca oturum açmış hesabın SQLite çalışma alanını değiştirir. 
   * PostgreSQL Docker kurulumunda `postgres-backup` servisi günlük doğrulanmış özel format yedekler üretir; son 14 günlük yedekler `postgres-backups` volume'ünde tutulur. `scripts/restore-postgres.sh` ile geri yükleme yapılır; `CONFIRM_RESTORE=YES` olmadan hiçbir şey değişmez.

---

## 🌐 İlan kaynakları

| Kaynak | Yöntem | Gerekli |
| :--- | :--- | :--- |
| RemoteOK, Arbeitnow, Remotive, Jobicy, Himalayas | Açık API | Yok |
| KosovaJob, TechCareer | Doğrudan web taraması | Yok |
| Greenhouse, Lever, Ashby kullanan şirketler | Açık kariyer sayfası API'si | `/sources` ekranından şirket ekle ya da `COMPANY_BOARDS=greenhouse:stripe,lever:spotify` |
| LinkedIn, Upwork, Indeed, Glassdoor, Kariyer.net | Apify Actor (hazır Actor tanımlı) | Apify API token |
| Fiverr, Freelancer, Toptal, GjirafaWork, Wellfound | Apify Actor | `/sources` ekranında Actor ID ve Apify API token |

**Platform denetimi:** `SCRAPER_PLATFORMS` (varsayılan: `linkedin,upwork,kosovajob,techcareer,remote`) hangi kaynakların etkin olduğunu belirler. Gece otomatik taraması (`SCHEDULER_NIGHTLY_TIME: 03:30`) yalnızca `NIGHTLY_SCAN_PLATFORMS` (varsayılan: `remote,kosovajob,techcareer`) listesindeki kaynaklardır; Apify ücretli kaynakları gece taramasına dahil edilmez. Apify Token olmayan kaynaklar başında tanımlı token reuse'ı kullanır.

Bot koruması olan portallar (Indeed, Glassdoor, Kariyer.net) doğrudan taranmaz; yalnızca Apify Actor veya Chrome eklentisiyle tek tek aktarılabilir.

## ⚠️ Bilinen sınırlar

* Eşleşme puanı kural tabanlı bir tahmindir (beceri örtüşmesi 50, ilan başlığının hedef role benzerliği 30, deneyim 20); işveren ATS puanı değildir.
* Yapay zekâ sağlayıcısı yanıt vermezse niyet mektubu genel bir şablondan üretilir. Bu durum Kanban'da "Şablon metin" uyarısıyla işaretlenir; böyle bir metin gönderilmeden önce yeniden üretilmelidir.
* "Sistem kontrolü" ekranı bir anahtarın girilmiş olmasına bakar, sağlayıcının gerçekten yanıt verdiğini sınamaz.
* Son başvuru tarihi yalnızca kaynak yayınlıyorsa bilinir (KosovaJob, Himalayas, bazı Greenhouse ilanları).

## 🧪 Testlerin Çalıştırılması

Backend testleri yalıtılmış ortamda çalışmalı; düz `pytest` yerel `.env` dosyasını ve gerçek DB'i kullanır:

```bash
# Yalıtılmış backend testleri (CI ile aynı)
# Sağlayıcı anahtarları boş geçilir; aksi halde yerel .env içindeki gerçek anahtarlar testlere sızar.
T=$(mktemp -d) && PYTHONPATH=. ENVIRONMENT=test MULTI_TENANT_ENABLED=false API_AUTH_TOKEN= \
  CORS_ORIGINS=http://localhost:3000 DATA_PATH="$T" DATABASE_URL="sqlite:///$T/ci.db" \
  ACTIVE_LLM_PROVIDER=auto ANTHROPIC_API_KEY= GEMINI_API_KEY= CUSTOM_LLM_API_KEY= APIFY_API_TOKEN= BACKUP_DIR= \
  ./backend/.venv/bin/python -m pytest -q backend/tests

# Frontend testleri, linting ve build
npm --prefix frontend test
npm --prefix frontend run lint
npm --prefix frontend run build

# E2E testleri (Playwright)
npm --prefix frontend run e2e:install
npm --prefix frontend run e2e
```

GitHub Actions CI aynı backend regresyon testlerini (yalıtılmış ortamda) ve frontend test/lint/build kontrollerini push ve PR'lerde çalıştırır. Chromium kurulumunda başarılıysa CV analiz, iş arama ve analitik ekranları için kritik tarayıcı test akışları da çalışır.

Yerel servisler çalışırken hızlı sağlık kontrolü:

```bash
./scripts/smoke_local.sh
```

Bu komut sistem sağlığı, ilanlar, CV analiz geçmişi, ana sayfa ve analitik ekranlarının erişilebilirliğini doğrular. İlan kaynağı URL'leri ayrıca `/jobs` ekranında on-demand doğrulanır (SSRF koruması nedeniyle yerel/özel ağ adresleri engellenir).
