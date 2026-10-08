# Dependabot ve mülakat puanlaması kontrolü — 8 Ekim 2026

## Dependabot

Depo: `AlpC18/otonom-is-bulma-sistemi`. GitHub kayıtları, değişiklikler, başarısız CI günlükleri ve mevcut yerel bağımlılıklar kontrol edildi. Üçüncü taraf paketlerin kaynak koduna yönelik kapsamlı güvenlik denetimi değildir.

14 PR'ın tamamı 7 Ekim'de **birleştirilmeden kapatılmış**; açık Dependabot PR'ı yok. Bununla birlikte 12 güncelleme `4dc5ab7` değişikliğinde doğrudan ana dala uygulanmış. Bu çalışma sırasında PR açılmadı, kapatılmadı veya birleştirilmedi.

| PR | Güncelleme | PR kontrolleri | Mevcut durum |
| --- | --- | --- | --- |
| [1](https://github.com/AlpC18/otonom-is-bulma-sistemi/pull/1) | actions/setup-node 7.0.0 | Başarılı | Ana dalda, SHA ile sabitlenmiş |
| [2](https://github.com/AlpC18/otonom-is-bulma-sistemi/pull/2) | actions/setup-python 7.0.0 | Başarılı | Ana dalda, SHA ile sabitlenmiş |
| [3](https://github.com/AlpC18/otonom-is-bulma-sistemi/pull/3) | actions/checkout 7.0.1 | Başarılı | Ana dalda, SHA ile sabitlenmiş |
| [4](https://github.com/AlpC18/otonom-is-bulma-sistemi/pull/4) | pydantic-settings >=2.15.0 | Başarılı | Gereksinim güncellenmiş |
| [5](https://github.com/AlpC18/otonom-is-bulma-sistemi/pull/5) | python-dotenv >=1.2.4 | Başarılı | Gereksinim güncellenmiş |
| [6](https://github.com/AlpC18/otonom-is-bulma-sistemi/pull/6) | beautifulsoup4 >=4.15.0 | Başarılı | Gereksinim güncellenmiş |
| [7](https://github.com/AlpC18/otonom-is-bulma-sistemi/pull/7) | @types/node 26.6.4 | Başarılı | package.json içinde mevcut; CI Node 22 ile tip sürümü aynı ana sürüm değil |
| [8](https://github.com/AlpC18/otonom-is-bulma-sistemi/pull/8) | fastapi >=0.142.2 | Başarılı | Gereksinim güncellenmiş |
| [9](https://github.com/AlpC18/otonom-is-bulma-sistemi/pull/9) | pgvector >=0.5.0 | Başarılı | Gereksinim güncellenmiş |
| [10](https://github.com/AlpC18/otonom-is-bulma-sistemi/pull/10) | chromadb >=1.5.9 | Başarılı | Gereksinim güncellenmiş |
| [11](https://github.com/AlpC18/otonom-is-bulma-sistemi/pull/11) | pdfjs-dist 6.4.299 | Başarılı | Güncellenmiş; paket Node >=22.13 veya >=24 istiyor |
| [12](https://github.com/AlpC18/otonom-is-bulma-sistemi/pull/12) | TypeScript 7.0.2 | Arayüz başarısız | Uygulanmamış; TypeScript 5.x korunmuş |
| [13](https://github.com/AlpC18/otonom-is-bulma-sistemi/pull/13) | lucide-react 1.51.0 | Arayüz başarısız | Sonradan 1.52.0 ana dala alınmış; mevcut uygulama derleniyor |
| [14](https://github.com/AlpC18/otonom-is-bulma-sistemi/pull/14) | eslint-config-next 16.3.8 | Arayüz başarısız | Uygulanmamış; Next ile birlikte 15.1.7 korunmuş |

### Başarısızlıkların nedenleri

- **12:** TypeScript derleyici API'sini kullanan testlerde `ScriptTarget.Latest` ve `ModuleKind.CommonJS` tanımsız. Ayrıca mevcut typescript-eslint sürümünün desteklediği aralığın dışında. [CI günlüğü](https://github.com/AlpC18/otonom-is-bulma-sistemi/actions/runs/37546056085).
- **13:** O zamanki `profile-optimizer` sayfası, yeni Lucide paketinden kaldırılmış `Github` ve `Linkedin` dışa aktarımlarını kullanıyordu. Mevcut checkout'ta bu sayfa yok; güncel derleme başarılı. [CI günlüğü](https://github.com/AlpC18/otonom-is-bulma-sistemi/actions/runs/37546070355).
- **14:** ESLint yapılandırması yüklenirken `Converting circular structure to JSON` hatası. Next 16 yapılandırması eski yapılandırma yaklaşımıyla tek başına yükseltilmemeli. [CI günlüğü](https://github.com/AlpC18/otonom-is-bulma-sistemi/actions/runs/37546082540).

Node tipleri ile çalışma zamanı sürümü gelecekte birlikte hizalanmalı; başarılı tip kontrolü, daha yeni Node API'lerinin eski çalışma zamanında var olduğunu garanti etmez. Mevcut CI dosyasında bu çalışmadan önce başlayan Node 22 değişikliği korundu.

Sonraki sağlık düzeltmesinde Next.js ve eslint-config-next birlikte 15.5.27'ye yükseltildi. Yukarıdaki tablo ilk PR incelemesindeki durumu kaydeder; güncel güvenlik ve test sonuçları `health-fixes-2026-10-08.md` dosyasındadır.

## Mülakat puanlaması

Başlanmış yazılı cevap/STAR değişiklikleri korundu ve tamamlandı:

- Kelime sayısı cevap puanı kazandırmaz veya kaybettirmez.
- Sesli cevap aynı yazılı cevap değerlendirme kurallarını kullanır. Konuşma hızı ve dolgu kelimeleri ayrı ölçümlerdir.
- Boş sesli cevabın eski 47 puanı kaldırıldı; artık 0.
- Teknik terim listesini tekrarlamak teknik derinlik puanı kazandırmaz.
- Teknoloji isimleri noktalama işaretleriyle korunur (`Next.js`, `.NET`, `C++`); büyük/küçük harf farklılığı kişisel eylemi kaçırmaz.
- Tek başına yıl veya `catalog` içindeki `log`, sonuç kanıtı sayılmaz.
- Her ölçüt açıklanır; ekranda yöntemin **yerel, kural tabanlı bir yapı tahmini** olduğu belirtilir. Teknik doğruluk, gerçek başarı veya işe alınma olasılığı doğrulanmaz. AI sağlayıcısına cevap gönderilmez.

## Doğrulama

- İlgili mülakat/araç testleri: **29 geçti**.
- İzole ortamda tüm backend testleri: **409 geçti**, 2 mevcut uyarı (Starlette/httpx kullanımdan kaldırma ve SMTP testinin değer döndürmesi).
- Frontend: **17 test geçti**; lint, TypeScript kontrolü ve üretim derlemesi başarılı.
- `git diff --check`: başarılı.

İlk geniş test çalışmasında yerel `.env` içindeki CORS ve harici yedek dizini ayarları iki testi etkiledi. CORS test kökenleriyle, yedekleme ise geçici veri diziniyle izole edilerek yeniden çalıştırıldı; testleri geçirtmek için ürün davranışı değiştirilmedi. Bu sonuçlar yerel çalışma kopyasına aittir; yeni bir GitHub CI çalışması başlatılmadı.
