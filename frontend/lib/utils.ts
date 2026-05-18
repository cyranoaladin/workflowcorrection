import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatDate(dateStr: string) {
  return new Date(dateStr).toLocaleDateString("fr-FR", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

export function formatRelative(dateStr: string) {
  const diff = Date.now() - new Date(dateStr).getTime();
  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) return "à l'instant";
  if (minutes < 60) return `il y a ${minutes}min`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `il y a ${hours}h`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `il y a ${days}j`;
  return formatDate(dateStr);
}

export function gradeColor(note: number): string {
  if (note >= 16) return "text-emerald-700 bg-emerald-50 border-emerald-200";
  if (note >= 12) return "text-blue-700 bg-blue-50 border-blue-200";
  if (note >= 10) return "text-amber-700 bg-amber-50 border-amber-200";
  return "text-rose-700 bg-rose-50 border-rose-200";
}

export function gradeColorSolid(note: number): string {
  if (note >= 16) return "bg-emerald-500";
  if (note >= 12) return "bg-blue-500";
  if (note >= 10) return "bg-amber-500";
  return "bg-rose-500";
}

export function statusLabel(status: string): string {
  const map: Record<string, string> = {
    uploaded: "Uploadée",
    processing: "En traitement",
    processed_pages: "Traitée",
    ocr_pending: "OCR en cours",
    corrected: "Corrigée",
    error: "Erreur",
  };
  return map[status] ?? status;
}

export function statusColor(status: string): string {
  const map: Record<string, string> = {
    uploaded: "bg-slate-100 text-slate-600",
    processing: "bg-sky-100 text-sky-700",
    processed_pages: "bg-violet-100 text-violet-700",
    ocr_pending: "bg-amber-100 text-amber-700",
    corrected: "bg-emerald-100 text-emerald-700",
    error: "bg-rose-100 text-rose-700",
  };
  return map[status] ?? "bg-slate-100 text-slate-600";
}
