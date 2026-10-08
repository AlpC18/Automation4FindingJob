# Sağlık kontrolü sonrası düzeltmeler — 8 Ekim 2026

## Uygulanan değişiklikler

- Next.js ve eslint-config-next birlikte 15.5.27 sürümüne yükseltildi.
- PostCSS 8.5.29 alt sınırına çekildi. Next'in sabitlediği eski PostCSS kopyası da `overrides` ile bu sürümü kullanıyor.
- Tailwind ve postcss-nested içindeki selector parser 7.1.6 olarak sabitlendi. Bu ana sürüm geçişinin uygulamadaki uyumluluğu üretim derlemesi ve tarayıcı testleriyle kontrol edildi. Overrides kaldırılmadan önce üst paketlerin kendi bağımlılıkları kontrol edilmeli.
- Kaynaklar sayfasındaki ikinci `html/body` yerleşimi kaldırıldı; kök yerleşim ve uygulama başlığı devralınıyor. Next güncellemesinden sonra bu eski yapı ilk açılışta boş ekran, sayfalar arası geçişte iç içe HTML hatası veriyordu.
- Sunucu kurulumu `uvicorn[standard]` kullanıyor; eksik WebSocket desteği nedeniyle canlı bildirimlerin 404 alması giderildi.
- Devam eden eğitim, gelecekteki eğitim bitiş tarihi ve CV'deki açık öğrenci bilgisi artık mezuniyet iddialarının kontrolüne katılıyor. Tamamlanmış lise ve devam eden yüksek lisans yanında tamamlanmış lisans örnekleri ayrıştırılıyor.
- Yapay zekâya verilen ön yazı bağlamına yapılandırılmış eğitim ve devam eden eğitim listesi eklendi. Konumdan vatandaşlık/çalışma izni veya okul yılı çıkarmaması belirtiliyor. Bu kontrol kural tabanlıdır; tüm olası yanlış iddiaların doğruluğunu garanti etmez.
- Yerel kuyruktaki ve indirilebilir metin dosyalarındaki iki yanlış mezuniyet ifadesi düzeltildi. Önceki dosyalar özel erişimli geçici bir dizine yedeklendi. Başvurular gönderilmiş olarak işaretlenmedi. Mevcut dört CV PDF'inin öğrenci ifadesini koruduğu kontrol edildi.
- Kullanıcının seçtiği Gmail gönderici hesabı yerel ayarlarda hazırlandı. Parola girilmedikçe SMTP hazırlık kontrolü, bağlantı testi ve gönderim yolu hesabı hazır kabul etmiyor. Adres veya parola bu rapora eklenmedi.

## Doğrulama

- Backend: 423 test başarılı; yalnızca mevcut Starlette/httpx kullanımdan kaldırma uyarısı kaldı.
- Frontend: 17 birim testi, lint, TypeScript kontrolü, üretim derlemesi başarılı.
- Tarayıcı: 28 test başarılı. İlk çalışmada kaynaklar sayfasına ait iki test hata verdi; iç içe yerleşim düzeltildikten sonra tümü geçti.
- Gerçek WebSocket bağlantısı açıldı.
- Uygulama 13000, API 18000 portunda mevcut çalışma oturumunda başlatıldı; zamanlayıcı etkin. Oturumdan bağımsız macOS servisi denemesi, Masaüstü klasörü erişimine `Operation not permitted` yanıtı verdi; oluşturulan geçici servis kaydı kaldırıldı. Kalıcı arka plan çalışma/yeniden başlatma kurulmuş değildir.
- Üretim bağımlılıkları için `npm audit --omit=dev`: 0 uyarı.
- Tüm bağımlılıklar için `npm audit`: 0 uyarı. `braces` paketi proje içi güvenli yerel çatal (`vendor/braces`, `@career-agent/braces@3.0.3-career.1`) ile yamanmış ve `package.json` overrides üzerinden sabitlenmiştir.

## Dış hizmetlerde bekleyenler

- 16 farklı Apify tokenının `/v2/users/me` kontrolü: 4 HTTP 200, 12 HTTP 401. Anahtarlar silinmedi, 401 sonuçları geçerli sayılmadı. Bu hesapların sağlayıcıdan yeni anahtar üretmesi gerekiyor.
- Gemini'nin model-listesi kontrolü HTTP 200 döndü. Bu kontrol üretim çağrısı yapmaz; model kotasını veya önce paylaşılmış bir anahtarın iptal edildiğini kanıtlamaz.
- Gmail uygulama parolası henüz kaydedilmedi. Gönderici alanları hazır, e-posta gönderimi tamamlanmış değil.
- Geliştirme araçlarındaki `braces` açığı (GHSA-vfj7-8cjw-p6xm) için resmi yama bulunmadığından yerel çatal (`vendor/braces`) ile derin iç içe girdileri (depth > 100) güvenle reddeden koruma uygulanmış, `tests/braces-security.test.cjs` testleriyle doğrulanmıştır. Tailwind/ESLint gelecekte resmi yama yayımlandığında standart sürüme geri döndürülebilir.

Kaynaklar: [braces güvenlik bildirimi](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm), [Gmail SMTP ayarları](https://support.google.com/mail/answer/7104828), [Google uygulama parolaları](https://support.google.com/mail/answer/185833).
