"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ChevronLeft, BarChart2, TrendingUp, Award, AlertTriangle, Loader2, AlertCircle, Users, Target } from "lucide-react";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from "recharts";
import { apiGet } from "@/lib/api";
import { cn } from "@/lib/utils";

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
  if (note >= 16) return "text-emerald-700 bg-emerald-50 border-emerald-200";
  if (note >= 12) return "text-blue-700 bg-blue-50 border-blue-200";
  if (note >= 10) return "text-amber-700 bg-amber-50 border-amber-200";
  return "text-rose-700 bg-rose-50 border-rose-200";
}

function barColor(range: string) {
  const num = parseInt(range);
  if (num >= 16) return "#10b981";
  if (num >= 12) return "#3b82f6";
  if (num >= 10) return "#f59e0b";
  return "#f43f5e";
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
      <div className="flex items-center justify-center py-24 text-gray-400">
        <Loader2 className="mr-2 h-5 w-5 animate-spin" /> Chargement du bilan…
      </div>
    );
  }

  const chartData = bilan.distribution_over_20
    ? Object.entries(bilan.distribution_over_20).map(([range, count]) => ({ range, count }))
    : [];

  return (
    <div className="space-y-6">

      {/* Breadcrumb + header */}
      <div>
        <Link href={`/exams/${examId}`} className="mb-3 inline-flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-800 transition-colors">
          <ChevronLeft className="h-4 w-4" /> Retour à l&apos;examen
        </Link>
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900 tracking-tight">{bilan.exam_title}</h1>
            <p className="mt-1 text-sm text-gray-500">Bilan de classe · {bilan.total_points} pts max · {bilan.total_copies} copies</p>
          </div>
          <div className="flex items-center gap-2">
            <span className="badge bg-emerald-50 text-emerald-700 border border-emerald-200">
              {bilan.corrected_copies} corrigées
            </span>
            {bilan.pending_copies > 0 && (
              <span className="badge bg-amber-50 text-amber-700 border border-amber-200">
                {bilan.pending_copies} en attente
              </span>
            )}
          </div>
        </div>
      </div>

      {error && (
        <div className="flex items-start gap-3 rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" /> {error}
        </div>
      )}

      {bilan.message && !bilan.stats && (
        <div className="card p-8 text-center">
          <BarChart2 className="mx-auto mb-3 h-10 w-10 text-gray-300" />
          <p className="text-sm text-gray-500">{bilan.message}</p>
        </div>
      )}

      {/* Stats grid */}
      {bilan.stats && (
        <>
          {/* Hero average */}
          <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-indigo-600 to-violet-700 p-8 text-white">
            <div className="absolute -right-10 -top-10 h-48 w-48 rounded-full bg-white/5" />
            <div className="absolute -bottom-6 -left-6 h-32 w-32 rounded-full bg-white/5" />
            <div className="relative flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-white/70">Note moyenne de la classe</p>
                <div className="mt-2 flex items-end gap-2">
                  <span className="text-5xl font-extrabold">{bilan.stats.average_over_20}</span>
                  <span className="mb-1.5 text-xl text-white/60">/ 20</span>
                </div>
                <p className="mt-2 text-sm text-white/60">
                  Médiane : {(bilan.stats.median / bilan.total_points * 20).toFixed(1)} /20
                </p>
              </div>
              <div className="hidden sm:grid grid-cols-2 gap-4">
                <div className="rounded-xl bg-white/10 backdrop-blur-sm px-5 py-3 text-center">
                  <div className="text-2xl font-bold">{(bilan.stats.max / bilan.total_points * 20).toFixed(1)}</div>
                  <div className="text-xs text-white/70">Meilleure</div>
                </div>
                <div className="rounded-xl bg-white/10 backdrop-blur-sm px-5 py-3 text-center">
                  <div className="text-2xl font-bold">{(bilan.stats.min / bilan.total_points * 20).toFixed(1)}</div>
                  <div className="text-xs text-white/70">Plus basse</div>
                </div>
              </div>
            </div>
            {/* Progress bar */}
            <div className="relative mt-6">
              <div className="h-2 w-full rounded-full bg-white/20 overflow-hidden">
                <div
                  className="h-full rounded-full bg-white/80 transition-all"
                  style={{ width: `${(bilan.stats.average_over_20 / 20) * 100}%` }}
                />
              </div>
              <div className="mt-1.5 flex justify-between text-xs text-white/50">
                <span>0</span>
                <span>10</span>
                <span>20</span>
              </div>
            </div>
          </div>

          {/* Stat pills */}
          <div className="grid gap-4 sm:grid-cols-4">
            <div className="stat-card">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-50 text-indigo-600">
                <TrendingUp className="h-5 w-5" />
              </div>
              <div>
                <div className="text-2xl font-bold text-gray-900">{bilan.stats.average_over_20}</div>
                <div className="text-xs text-gray-500">Moyenne /20</div>
              </div>
            </div>
            <div className="stat-card">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-50 text-emerald-600">
                <Award className="h-5 w-5" />
              </div>
              <div>
                <div className="text-2xl font-bold text-gray-900">{(bilan.stats.max / bilan.total_points * 20).toFixed(1)}</div>
                <div className="text-xs text-gray-500">Meilleure note</div>
              </div>
            </div>
            <div className="stat-card">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-rose-50 text-rose-600">
                <AlertTriangle className="h-5 w-5" />
              </div>
              <div>
                <div className="text-2xl font-bold text-gray-900">{(bilan.stats.min / bilan.total_points * 20).toFixed(1)}</div>
                <div className="text-xs text-gray-500">Note la plus basse</div>
              </div>
            </div>
            <div className="stat-card">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-violet-50 text-violet-600">
                <Users className="h-5 w-5" />
              </div>
              <div>
                <div className="text-2xl font-bold text-gray-900">{bilan.corrected_copies}</div>
                <div className="text-xs text-gray-500">Copies corrigées</div>
              </div>
            </div>
          </div>
        </>
      )}

      {/* Distribution chart with recharts */}
      {chartData.length > 0 && (
        <div className="card p-6">
          <div className="mb-4 flex items-center justify-between">
            <div>
              <h2 className="text-base font-semibold text-gray-900">Répartition des notes</h2>
              <p className="text-xs text-gray-500 mt-0.5">Distribution sur 20 points</p>
            </div>
            {bilan.stats && (
              <span className="badge bg-indigo-50 text-indigo-600 border border-indigo-200">
                <Target className="h-3 w-3" /> Médiane {(bilan.stats.median / bilan.total_points * 20).toFixed(1)}
              </span>
            )}
          </div>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                <XAxis dataKey="range" tick={{ fontSize: 11, fill: "#64748b" }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 11, fill: "#64748b" }} axisLine={false} tickLine={false} allowDecimals={false} />
                <Tooltip
                  contentStyle={{ borderRadius: "12px", border: "1px solid #e2e8f0", boxShadow: "0 4px 12px rgba(0,0,0,.08)" }}
                  labelFormatter={(v) => `Tranche ${v}`}
                  formatter={(v: unknown) => [`${v} copie${v !== 1 ? "s" : ""}`, "Nombre"]}
                />
                <Bar dataKey="count" radius={[6, 6, 0, 0]} maxBarSize={48}>
                  {chartData.map((entry) => (
                    <Cell key={entry.range} fill={barColor(entry.range)} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Ranking table */}
      {bilan.students && bilan.students.length > 0 && (
        <div className="card overflow-hidden">
          <div className="flex items-center justify-between border-b border-gray-100 px-6 py-4">
            <div>
              <h2 className="text-base font-semibold text-gray-900">Classement des élèves</h2>
              <p className="text-xs text-gray-500 mt-0.5">{bilan.students.length} élèves classés par note</p>
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="table-header">
                <tr>
                  <th className="px-6 py-3 text-left w-10">#</th>
                  <th className="px-4 py-3 text-left">Élève</th>
                  <th className="px-4 py-3 text-left">Code</th>
                  <th className="px-4 py-3 text-right">Note /20</th>
                  <th className="px-4 py-3 text-right">Points</th>
                  <th className="px-4 py-3 text-center">Statut</th>
                </tr>
              </thead>
              <tbody>
                {bilan.students.map((s, i) => (
                  <tr key={s.copy_id} className="table-row">
                    <td className="px-6 py-3.5">
                      <span className={cn(
                        "inline-flex h-6 w-6 items-center justify-center rounded-full text-xs font-bold",
                        i === 0 ? "bg-amber-100 text-amber-700" : i === 1 ? "bg-gray-200 text-gray-600" : i === 2 ? "bg-orange-100 text-orange-700" : "text-gray-400"
                      )}>
                        {i + 1}
                      </span>
                    </td>
                    <td className="px-4 py-3.5">
                      <Link href={`/copies/${s.copy_id}`} className="font-semibold text-gray-900 hover:text-indigo-600 transition-colors">
                        {s.student_name ?? <span className="italic text-gray-400">Non renseigné</span>}
                      </Link>
                    </td>
                    <td className="px-4 py-3.5 font-mono text-xs text-gray-500">{s.copy_code ?? "—"}</td>
                    <td className="px-4 py-3.5 text-right">
                      <span className={cn("inline-flex items-center rounded-lg border px-2.5 py-1 text-xs font-bold", gradeColor(s.score_over_20))}>
                        {s.score_over_20}
                      </span>
                    </td>
                    <td className="px-4 py-3.5 text-right text-gray-600">{s.score} / {bilan.total_points}</td>
                    <td className="px-4 py-3.5 text-center">
                      {s.needs_human_review ? (
                        <span className="badge bg-amber-50 text-amber-700 border border-amber-200">
                          <AlertTriangle className="h-3 w-3" /> À vérifier
                        </span>
                      ) : (
                        <span className="badge bg-emerald-50 text-emerald-700 border border-emerald-200">
                          ✓ Validé
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
