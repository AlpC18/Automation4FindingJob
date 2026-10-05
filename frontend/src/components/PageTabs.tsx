"use client";

import { useId, useState, type ComponentType, type KeyboardEvent } from "react";
import { useLanguage } from "@/lib/i18n";

type Tab = { label: string; Component: ComponentType };

/** Shows several related screens on one page; the first tab is the page's own content. */
export default function PageTabs({ tabs }: { tabs: Tab[] }) {
  const { translate: t } = useLanguage();
  const baseId = useId();
  const [active, setActive] = useState(0);
  // A tab stays mounted once opened, so its filters and input survive a visit to another tab.
  const [visited, setVisited] = useState<number[]>([0]);

  function open(index: number) {
    setActive(index);
    setVisited((current) => (current.includes(index) ? current : [...current, index]));
  }

  function onKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key !== "ArrowRight" && event.key !== "ArrowLeft") return;
    event.preventDefault();
    const next = (active + (event.key === "ArrowRight" ? 1 : tabs.length - 1)) % tabs.length;
    open(next);
    document.getElementById(`${baseId}-tab-${next}`)?.focus();
  }

  return (
    <div className="space-y-5">
      <div role="tablist" onKeyDown={onKeyDown} className="flex flex-wrap gap-2 border-b pb-3" style={{ borderColor: "var(--border)" }}>
        {tabs.map((tab, index) => (
          <button
            key={tab.label}
            id={`${baseId}-tab-${index}`}
            type="button"
            role="tab"
            aria-selected={index === active}
            aria-controls={`${baseId}-panel-${index}`}
            tabIndex={index === active ? 0 : -1}
            onClick={() => open(index)}
            className="rounded-full border px-3.5 py-1.5 text-xs font-semibold transition-colors"
            style={index === active
              ? { color: "var(--text)", borderColor: "var(--accent-strong)", background: "var(--surface-muted)" }
              : { color: "var(--muted)", borderColor: "var(--border)", background: "transparent" }}
          >
            {t(tab.label)}
          </button>
        ))}
      </div>
      {tabs.map((tab, index) => visited.includes(index) && (
        <div key={tab.label} id={`${baseId}-panel-${index}`} role="tabpanel" aria-labelledby={`${baseId}-tab-${index}`} hidden={index !== active}>
          <tab.Component />
        </div>
      ))}
    </div>
  );
}
