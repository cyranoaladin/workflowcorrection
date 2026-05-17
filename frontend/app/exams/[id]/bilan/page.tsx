"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ChevronLeft, BarChart2, TrendingUp, Award, AlertTriangle, Loader2, AlertCircle } from "lucide-react";
import { apiGet } from "@/lib/api";

type BilanData = {
  exam_id: string;
  exam_title: string;
  total_points: number;
  total_copies: number;
  corrected_copies: number;
  pending_copies: number;
  message?: string;
  stats?: {
    average: number;
    average_over_20: number;
    min: number;
    max: number;
    median: number;
  };
  distribution_over_20?: Record<string, number>;
  students?: {
    copy_id: string;
    student_name: string | null;
    copy_code: string | null;
    score: number;
    score_over_20: number;
    needs_human_review: boolean;
  }[];
};

function gradeColor(note: number) {
  if (note >= 16) return "text-emerald-700 bg-emerald-50";
  if (note >= 12) return "text-blue-700 bg-blue-50";
  if (note >= 10) return "text-amber-700 bg-amber-50";
  return "text-rose-700 bg-rose-50";
}

export default function BilanPage() {
  const params = useParams();
  const examId = useMemo(() => params.id as string, [params.id]);
  const [bilan, setBilan] = useState<BilanData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiGet<BilanData>(`/exams/${examId}/bilan`)
      .then(setBilan)
      .catch((e) => setError(e?.message ?? "Erreur de chargement"));
  }, [examId]);

  if (!bilan) {
    return (
      <div className="flex items-center justify-center py-24 text-slate-400">
        <Loader2 className="mr-2 h-5 w-5 animate-spin" /> Chargement…
      </div>
    );
  }

  const statItems = bilan.stats ? [
    { icon: TrendingUp, label: "Moyenne /20",  value: bilan.stats.average_over_20,                                          color: "bg-indigo-50 text-indigo-600" },
    { icon: BarChart2,  label: "Médiane /20",  value: (bilan.stats.median / bilan.total_points * 20).toFixed(2),            color: "bg-sky-50 text-sky-600" },
    { icon: Award,      label: "Max /20",      value: (bilan.stats.max / bilan.total_points * 20).toFixed(2),               color: "bg-emerald-50 text-emerald-600" },
    { icon: AlertTriangle, label: "Min /20",   value: (bilan.stats.min / bilan.total_points * 20).toFixed(2),               color: "bg-rose-50 text-rose-600" },
    { icon: BarChart2,  label: "Corrigées",    value: `${bilan.corrected_copies}/${bilan.total_copies}`,                    color: "bg-violet-50 text-violet-600" },
  ] : [];

  return (
    <div className="space-y-6 animate-slide-up">

      {/* Breadcrumb + header */}
      <div>
        <Link href={`/exams/${examId}`} className="mb-3 inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-800 transition-colors">
          <ChevronLeft className="h-4 w-4" /> Retour à l&apos;examen
        </Link>
        <div>
          <div className="flex items-center gap-2">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-600 text-white shadow-sm">
              <BarChart2 className="h-5 w-5" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-slate-900">{bilan.exam_title}</h1>
              <p className="text-sm text-slate-500">Bilan classe · {bilan.total_points} pts max</p>
            </div>
          </div>
        </div>
      </div>

      {error && (
        <div className="flex items-start gap-2 rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" /> {error}
        </div>
      )}

      {bilan.message && !bilan.stats && (
        <div className="rounded-xl border border-slate-200 bg-white p-6 text-center text-sm text-slate-500 shadow-card">
          <BarChart2 className="mx-auto mb-3 h-8 w-8 text-slate-300" />
          {bilan.message}
        </div>
      )}

      {/* Stats grid */}
      {bilan.stats && (
        <div className="grid gap-4 sm:grid-cols-5">
          {statItems.map((s) => (
            <div key={s.label} className="rounded-xl border border-slate-200 bg-white p-4 text-center shadow-card">
              <div className={`mx-auto mb-2 flex h-10 w-10 items-center justify-center rounded-xl ${s.color}`}>
                <s.icon className="h-5 w-5" />
              </div>
              <div className="text-2xl font-bold text-slate-900">{s.value}</div>
              <div className="mt-1 text-xs text-slate-500">{s.label}</div>
            </div>
          ))}
        </div>
      )}

      {/* Distribution bar chart */}
      {bilan.distribution_over_20 && (
        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-card">
          <h2 className="mb-4 text-sm font-semibold text-slate-700">Distribution des notes /20</h2>
          <div className="flex items-end gap-1.5 h-32">
            {Object.entries(bilan.distribution_over_20).map(([range, count]) => {
              const maxVal = Math.max(...Object.values(bilan.distribution_over_20!), 1);
              const pct = Math.round((count / maxVal) * 100);
              return (
                <div key={range} className="flex flex-col items-center gap-1 flex-1 min-w-0">
                  {count > 0 && <span className="text-xs font-semibold text-slate-700">{count}</span>}
                  <div className="w-full rounded-t-md bg-indigo-500 transition-all" style={{ height: `${pct}%`, minHeight: count > 0 ? "4px" : "0" }} />
                  <span className="text-xs text-slate-500 truncate w-full text-center">{range}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Ranking table */}
      {bilan.students && bilan.students.length > 0 && (
        <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-card">
          <div className="px-5 py-4 border-b border-slate-100">
            <h2 className="text-sm font-semibold text-slate-700">Classement des élèves</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-xs font-medium text-slate-500">
                <tr>
                  <th className="px-4 py-3 text-left w-10">#</th>
                  <th className="px-4 py-3 text-left">Élève</th>
                  <th className="px-4 py-3 text-left">Code</th>
                  <th className="px-4 py-3 text-right">Note /20</th>
                  <th className="px-4 py-3 text-right">Points</th>
                  <th className="px-4 py-3 text-center">Statut</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {bilan.students.map((s, i) => (
                  <tr key={s.copy_id} className="hover:bg-slate-50 transition-colors">
                    <td className="px-4 py-3 text-slate-400 font-medium">{i + 1}</td>
                    <td className="px-4 py-3">
                      <Link href={`/copies/${s.copy_id}`} className="font-medium text-indigo-700 hover:underline underline-offset-2">
                        {s.student_name ?? <span className="italic text-slate-400">—</span>}
                      </Link>
                    </td>
                    <td className="px-4 py-3 font-mono text-xs text-slate-500">{s.copy_code ?? "—"}</td>
                    <td className="px-4 py-3 text-right">
                      <span className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-bold ${gradeColor(s.score_over_20)}`}>
                        {s.score_over_20}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right text-slate-600">{s.score}</td>
                    <td className="px-4 py-3 text-center">
                      {s.needs_human_review ? (
                        <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700">
                          <AlertTriangle className="h-3 w-3" /> À vérifier
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-700">
                          ✓ OK
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

    </div>
  );
}
