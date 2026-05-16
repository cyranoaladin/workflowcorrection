"use client";

import { useEffect, useState } from "react";
import { getApiBaseUrl } from "@/lib/api";

export function ApiHealthBadge() {
  const [status, setStatus] = useState<"loading" | "ready" | "not_ready" | "down">("loading");
  const baseUrl = getApiBaseUrl();

  useEffect(() => {
    let cancelled = false;
    if (!baseUrl) {
      setStatus("down");
      return () => {
        cancelled = true;
      };
    }
    fetch(`${baseUrl}/health/ready`, { cache: "no-store" })
      .then(async (res) => {
        if (cancelled) return;
        if (!res.ok) {
          setStatus(res.status === 503 ? "not_ready" : "down");
          return;
        }
        const json = (await res.json()) as any;
        setStatus(json?.status === "ready" ? "ready" : "not_ready");
      })
      .catch(() => {
        if (cancelled) return;
        setStatus("down");
      });
    return () => {
      cancelled = true;
    };
  }, [baseUrl]);

  const cls =
    status === "ready"
      ? "bg-emerald-100 text-emerald-800"
      : status === "not_ready"
        ? "bg-amber-100 text-amber-800"
        : status === "down"
        ? "bg-rose-100 text-rose-800"
        : "bg-slate-100 text-slate-700";

  return (
    <span className={`rounded px-2 py-1 text-xs font-medium ${cls}`} title={baseUrl || "NEXT_PUBLIC_API_BASE_URL is not set"}>
      API: {status}
    </span>
  );
}
