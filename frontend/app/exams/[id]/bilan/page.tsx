"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
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

export default function BilanPage() {
  const params = useParams();
  const examId = useMemo(() => params.id as string, [params.id]);
  const [bilan, setBilan] = useState<BilanData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiGet<BilanData>(`/exams/${examId}/bilan`)
      .then(setBilan)
      .catch((e) => setError(e?.message ?? "Failed to load"));
  }, [examId]);

  if (!bilan) return <div className="p-6 text-sm text-slate-600">Chargement...</div>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">{bilan.exam_title}</h1>
          <div className="text-sm text-slate-500">Bilan classe · {bilan.total_points} pts max</div>
        </div>
        <Link href={`/exams/${examId}`} className="text-sm text-slate-700 hover:text-slate-900">
          ← Retour examen
        </Link>
      </div>

      {error && <div className="rounded border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">{error}</div>}

      {bilan.message && !bilan.stats && (
        <div className="rounded border bg-white p-4 text-sm text-slate-600">{bilan.message}</div>
      )}

      {/* Stats */}
      {bilan.stats && (
        <div className="grid gap-4 md:grid-cols-5">
          {[
            { label: "Moyenne /20", value: bilan.stats.average_over_20 },
            { label: "Min /20", value: (bilan.stats.min / bilan.total_points * 20).toFixed(2) },
            { label: "Max /20", value: (bilan.stats.max / bilan.total_points * 20).toFixed(2) },
            { label: "Médiane /20", value: (bilan.stats.median / bilan.total_points * 20).toFixed(2) },
            { label: "Corrigées", value: `${bilan.corrected_copies} / ${bilan.total_copies}` },
          ].map((s) => (
            <div key={s.label} className="rounded border bg-white p-4 text-center">
              <div className="text-2xl font-bold text-slate-800">{s.value}</div>
              <div className="mt-1 text-xs text-slate-500">{s.label}</div>
            </div>
          ))}
        </div>
      )}

      {/* Distribution */}
      {bilan.distribution_over_20 && (
        <div className="rounded border bg-white p-4">
          <div className="mb-3 text-sm font-medium">Distribution des notes /20</div>
          <div className="flex items-end gap-2 h-24">
            {Object.entries(bilan.distribution_over_20).map(([range, count]) => {
              const max = Math.max(...Object.values(bilan.distribution_over_20!));
              const height = max > 0 ? Math.round((count / max) * 80) : 0;
              return (
                <div key={range} className="flex flex-col items-center gap-1 flex-1">
                  <span className="text-xs font-medium text-slate-700">{count}</span>
                  <div
                    className="w-full rounded-t bg-indigo-400"
                    style={{ height: `${height}px` }}
                  />
                  <span className="text-xs text-slate-500">{range}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Students table */}
      {bilan.students && bilan.students.length > 0 && (
        <div className="rounded border bg-white overflow-hidden">
          <div className="px-4 py-3 text-sm font-medium border-b">Classement des élèves</div>
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-xs text-slate-500">
              <tr>
                <th className="px-4 py-2 text-left">#</th>
                <th className="px-4 py-2 text-left">Élève</th>
                <th className="px-4 py-2 text-left">Code</th>
                <th className="px-4 py-2 text-right">Note /20</th>
                <th className="px-4 py-2 text-right">Points</th>
                <th className="px-4 py-2 text-center">Statut</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {bilan.students.map((s, i) => (
                <tr key={s.copy_id} className="hover:bg-slate-50">
                  <td className="px-4 py-2 text-slate-400">{i + 1}</td>
                  <td className="px-4 py-2">
                    <Link href={`/copies/${s.copy_id}`} className="hover:underline text-indigo-700">
                      {s.student_name ?? "—"}
                    </Link>
                  </td>
                  <td className="px-4 py-2 text-slate-500">{s.copy_code ?? "—"}</td>
                  <td className="px-4 py-2 text-right font-semibold">{s.score_over_20}</td>
                  <td className="px-4 py-2 text-right text-slate-600">{s.score}</td>
                  <td className="px-4 py-2 text-center">
                    {s.needs_human_review ? (
                      <span className="text-xs text-amber-600">⚠ À vérifier</span>
                    ) : (
                      <span className="text-xs text-emerald-600">✓</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
