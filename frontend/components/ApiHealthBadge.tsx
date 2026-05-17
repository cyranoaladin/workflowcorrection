"use client";

import { useEffect, useState } from "react";
import { getApiBaseUrl } from "@/lib/api";

const CFG = {
  loading:   { label: "API", dot: "bg-slate-300 animate-pulse", text: "text-slate-500" },
  ready:     { label: "API opérationnelle", dot: "bg-emerald-500", text: "text-emerald-700" },
  not_ready: { label: "API dégradée", dot: "bg-amber-400 animate-pulse", text: "text-amber-700" },
  down:      { label: "API hors ligne", dot: "bg-rose-500", text: "text-rose-700" },
};

export function ApiHealthBadge() {
  const [status, setStatus] = useState<keyof typeof CFG>("loading");
  const baseUrl = getApiBaseUrl();

  useEffect(() => {
    let cancelled = false;
    if (!baseUrl) { setStatus("down"); return; }
    fetch(`${baseUrl}/health/ready`, { cache: "no-store" })
      .then(async (res) => {
        if (cancelled) return;
        if (!res.ok) { setStatus(res.status === 503 ? "not_ready" : "down"); return; }
        const json = (await res.json()) as any;
        setStatus(json?.status === "ready" ? "ready" : "not_ready");
      })
      .catch(() => { if (!cancelled) setStatus("down"); });
    return () => { cancelled = true; };
  }, [baseUrl]);

  const cfg = CFG[status];
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border border-current/10 px-2.5 py-1 text-xs font-medium ${cfg.text} bg-white shadow-sm`}
      title={baseUrl || "NEXT_PUBLIC_API_BASE_URL non défini"}
    >
      <span className={`h-2 w-2 rounded-full ${cfg.dot}`} />
      {cfg.label}
    </span>
  );
}
