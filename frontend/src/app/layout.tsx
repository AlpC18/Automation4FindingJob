import "./globals.css";
import Script from "next/script";
import AppShell from "@/components/AppShell";
import PWARegister from "@/components/PWARegister";
import SessionGate from "@/components/SessionGate";
import { LanguageProvider } from "@/lib/i18n";

export const metadata = {
  title: "Career Agent | Kariyer çalışma alanı",
  description: "İş arama ve başvuru süreciniz için kişisel kariyer çalışma alanı.",
  manifest: "/manifest.json",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="tr" data-theme="dark" suppressHydrationWarning>
      <body className="app-root min-h-screen">
        <Script src="/runtime-config.js" strategy="beforeInteractive" />
        <Script id="theme-init" strategy="beforeInteractive">
          {`try { document.documentElement.dataset.theme = localStorage.getItem("career-agent-theme") || "dark"; } catch {}`}
        </Script>
        <LanguageProvider>
          <SessionGate>
            <PWARegister />
            <AppShell>{children}</AppShell>
          </SessionGate>
        </LanguageProvider>
      </body>
    </html>
  );
}
