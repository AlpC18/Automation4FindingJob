"use client";

import { createContext, useContext, useEffect, useMemo, useState } from "react";

export type Locale = "tr" | "en";

// Turkish is the source text, so only the English locale needs a dictionary. It is a large
// file and is downloaded the first time English is chosen, not on every page load.
type Dictionary = Record<string, string>;

type LanguageContextValue = {
  locale: Locale;
  setLocale: (locale: Locale) => void;
  translate: (value: string, values?: Record<string, string | number>) => string;
};

const LanguageContext = createContext<LanguageContextValue | null>(null);

export function LanguageProvider({ children }: { children: React.ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>("tr");

  useEffect(() => {
    const saved = localStorage.getItem("career-agent-locale");
    const next = saved === "en" ? "en" : "tr";
    setLocaleState(next);
    document.documentElement.lang = next;
  }, []);

  function setLocale(next: Locale) {
    setLocaleState(next);
    localStorage.setItem("career-agent-locale", next);
    document.documentElement.lang = next;
  }

  const [english, setEnglish] = useState<Dictionary | null>(null);

  useEffect(() => {
    if (locale !== "en" || english) return;
    let cancelled = false;
    import("./i18n-translations")
      .then((module) => { if (!cancelled) setEnglish(module.englishTranslations); })
      .catch((error) => console.error("Could not load the English translations", error));
    return () => { cancelled = true; };
  }, [locale, english]);

  const value = useMemo(() => ({
    locale,
    setLocale,
    translate: (value: string, values?: Record<string, string | number>) => {
      const translated = (locale === "en" && english?.[value]) || value;
      if (!values) return translated;
      return Object.entries(values).reduce((text, [key, replacement]) => text.split(`{${key}}`).join(String(replacement)), translated);
    },
  }), [locale, english]);

  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>;
}

export function useLanguage() {
  const context = useContext(LanguageContext);
  if (!context) throw new Error("useLanguage must be used inside LanguageProvider");
  return context;
}
