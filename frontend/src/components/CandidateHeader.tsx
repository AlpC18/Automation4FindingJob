"use client";

import { useEffect, useState } from "react";
import { fetchFromApi } from "@/lib/api";
import { useLanguage } from "@/lib/i18n";

export default function CandidateHeader({ compact = false, dense = false }: { compact?: boolean; dense?: boolean }) {
  const { translate: t } = useLanguage();
  const [profile, setProfile] = useState<{ full_name?: string; target_role?: string }>({});

  useEffect(() => {
    fetchFromApi("/setup/profile")
      .then((response) => setProfile(response.profile || {}))
      .catch(() => {});
  }, []);

  const name = profile.full_name?.trim() || t("Aday");
  const role = profile.target_role?.trim() || t("Profil henüz doldurulmadı");
  const initials = name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0])
    .join("")
    .toUpperCase() || "C";

  return (
    <div className={`flex min-w-0 items-center ${compact ? "gap-3" : "gap-3"}`}>
      <div className={`candidate-avatar flex shrink-0 items-center justify-center rounded-full font-bold ${dense ? "h-8 w-8 text-xs" : "h-9 w-9 text-xs"}`}>
        {initials}
      </div>
      <div className={compact ? "min-w-0" : "hidden min-w-0 text-right sm:block"}>
        <div className={`truncate font-semibold ${dense ? "text-xs" : "text-xs"}`}>{name}</div>
        <div className={`muted truncate ${dense ? "text-xs" : "text-xs"}`}>{role}</div>
      </div>
    </div>
  );
}
