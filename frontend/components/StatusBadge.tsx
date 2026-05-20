"use client";

const STATUS_CONFIG: Record<string, { label: string; cls: string; dot: string }> = {
  uploaded:        { label: "Uploadée",      cls: "bg-slate-100 text-slate-600",   dot: "bg-slate-400" },
  processing:      { label: "Traitement…",   cls: "bg-amber-100 text-amber-700",   dot: "bg-amber-400 animate-pulse" },
  processed_pages: { label: "Traitée",       cls: "bg-emerald-100 text-emerald-700", dot: "bg-emerald-500" },
  ocr_pending:     { label: "OCR en attente",cls: "bg-sky-100 text-sky-700",       dot: "bg-sky-400" },
  corrected:       { label: "Corrigée IA",   cls: "bg-indigo-100 text-indigo-700", dot: "bg-indigo-500" },
  failed:          { label: "Échec",          cls: "bg-rose-100 text-rose-700",     dot: "bg-rose-500" },
  grading_queued:  { label: "En queue",       cls: "bg-violet-100 text-violet-700", dot: "bg-violet-400 animate-pulse" },
  idle:            { label: "Non indexé",     cls: "bg-slate-100 text-slate-600",   dot: "bg-slate-400" },
  queued:          { label: "Indexation…",    cls: "bg-amber-100 text-amber-700",   dot: "bg-amber-400 animate-pulse" },
  embedded:        { label: "Indexé",         cls: "bg-emerald-100 text-emerald-700", dot: "bg-emerald-500" },
};

export function StatusBadge({ status }: { status: string }) {
  const cfg = STATUS_CONFIG[status] ?? { label: status, cls: "bg-slate-100 text-slate-600", dot: "bg-slate-400" };
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold ${cfg.cls}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${cfg.dot}`} />
      {cfg.label}
    </span>
  );
}
