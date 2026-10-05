"use client";

import { useState, type ComponentType } from "react";
import { useLanguage } from "@/lib/i18n";

type Tab = { label: string; Component: ComponentType };

/** Shows several related screens on one page; the first tab is the page's own content. */
export default function PageTabs({ tabs }: { tabs: Tab[] }) {
  const { translate: t } = useLanguage();
  const [active, setActive] = useState(0);
  const Active = tabs[active].Component;

  return (
    <div className="space-y-5">
      <div role="tablist" className="flex flex-wrap gap-2 border-b pb-3" style={{ borderColor: "var(--border)" }}>
        {tabs.map((tab, index) => (
          <button
            key={tab.label}
            type="button"
            role="tab"
            aria-selected={index === active}
            onClick={() => setActive(index)}
            className="rounded-full border px-3.5 py-1.5 text-xs font-semibold transition-colors"
            style={index === active
              ? { color: "var(--text)", borderColor: "var(--accent-strong)", background: "var(--surface-muted)" }
              : { color: "var(--muted)", borderColor: "var(--border)", background: "transparent" }}
          >
            {t(tab.label)}
          </button>
        ))}
      </div>
      <Active />
    </div>
  );
}
