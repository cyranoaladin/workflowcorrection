"use client";

export function StatusBadge({ status }: { status: string }) {
  const color =
    status === "processed_pages"
      ? "bg-emerald-100 text-emerald-800"
      : status === "failed"
        ? "bg-rose-100 text-rose-800"
        : status === "processing"
          ? "bg-amber-100 text-amber-800"
          : "bg-slate-100 text-slate-700";
  return <span className={`rounded px-2 py-1 text-xs font-medium ${color}`}>{status}</span>;
}

