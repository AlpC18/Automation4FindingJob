# @career-agent/braces (3.0.3-career.1)

Bu paket, `braces` 3.0.3 sürümünün proje içi güvenlik yamalı (`vendor/braces`) çatalıdır.

## Güvenlik Arka Planı (GHSA-vfj7-8cjw-p6xm / CVE-2024-4068)
ESLint ve Tailwind gibi geliştirme bağımlılıklarının alt bağımlılık ağacında yer alan `braces` paketinde, aşırı derin iç içe geçmiş küme parantezleri veya parantez ifadeleri (`{a,{b,{c...}}}`) ayrıştırılırken yığın taşmasına (call stack exhaustion) veya kontrolsüz kaynak tüketimine (ReDoS/DoS) yol açan bir zafiyet bulunmaktadır. Henüz resmi bir üst sürüm yayımlanmadığı için yerel bir yama uygulanmıştır.

## Uygulanan Düzeltmeler
1. **Derinlik Sınırı (`lib/depth.js`):**
   - Ayrıştırma (`parse`) ve AST gezintileri için sabit bir üst sınır (`MAX_DEPTH = 100`) tanımlandı.
   - Parantez (`(`) ve süslü parantez (`{`) açıldığında yığın derinliği kontrol edilerek sınır aşılırsa kontrollü bir `SyntaxError` fırlatılır.
2. **Yinelemeli AST Doğrulaması (`assertSafeAst`):**
   - `compile()`, `expand()` ve `stringify()` doğrudan dışarıdan sağlanan AST düğümlerini kabul edebildiği için, özyinelemeli değil yığın tabanlı/yinelemeli (iterative) bir AST derinlik kontrolü eklendi (böylece doğrulayıcının kendisi yığın taşmasına neden olmaz).
3. **npm Overrides Entegrasyonu:**
   - Projenin `package.json` dosyasında `devDependencies` ve `overrides` alanlarına `"braces": "file:vendor/braces"` ve `"braces": "$braces"` tanımlanarak tüm bağımlılık ağacında bu güvenli sürümün kullanılması sağlandı.

## Testler
Yerel güvenlik düzeltmesi `frontend/tests/braces-security.test.cjs` altında otomatik testlerle doğrulanmaktadır:
- Normal sözdizimi ve izin verilen derinlikteki meşru kullanımların çalıştığı,
- Derin iç içe parantez ve süslü parantezlerin güvenle reddedildiği,
- Kapatılmamış derin parantezlerin hatasız yakalandığı,
- Dışarıdan sağlanan derin AST yapılarının yığın taşması yaratmadan reddedildiği doğrulanır.
