"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { apiGet, apiPatch, apiPostJson } from "@/lib/api";
import type { CopyPage, IntegrationsStatus, StudentCopy } from "@/lib/types";
import { StatusBadge } from "@/components/StatusBadge";
import { PageViewer } from "@/components/PageViewer";

type GradeReport = {
  copy_id: string;
  student: { name: string | null; code: string | null };
  exam: { title: string; total_points: number };
  score: {
    total_awarded: number;
    total_max: number;
    percentage: number;
    grade_over_20: number;
    mention: string;
  };
  questions: {
    id: string;
    question_id: string;
    points_max: number;
    points_awarded: number | null;
    percentage: number | null;
    confidence: number | null;
    needs_human_review: boolean;
    validated_by_human: boolean;
    justification: string;
    criteria_details: { criterion: string; awarded: number; comment: string }[];
    status: string;
    error_message: string | null;
  }[];
  audit: {
    audit_passed: boolean;
    flags: string[];
    summary: string;
    recommendation?: string;
    needs_human_review: boolean;
  };
  needs_human_review: boolean;
};

function mentionColor(mention: string) {
  if (mention === "Très bien") return "text-emerald-700 bg-emerald-50";
  if (mention === "Bien") return "text-blue-700 bg-blue-50";
  if (mention === "Assez bien") return "text-sky-700 bg-sky-50";
  if (mention === "Passable") return "text-amber-700 bg-amber-50";
  return "text-rose-700 bg-rose-50";
}

function confidenceLabel(c: number | null) {
  if (c === null) return "—";
  if (c >= 0.8) return `✓ ${Math.round(c * 100)}%`;
  if (c >= 0.5) return `~ ${Math.round(c * 100)}%`;
  return `⚠ ${Math.round(c * 100)}%`;
}

export default function CopyDetailPage() {
  const params = useParams();
  const id = params.id as string;
  const copyId = useMemo(() => id, [id]);

  const [copy, setCopy] = useState<StudentCopy | null>(null);
  const [pages, setPages] = useState<CopyPage[]>([]);
  const [status, setStatus] = useState<any>(null);
  const [integrations, setIntegrations] = useState<IntegrationsStatus | null>(null);
  const [report, setReport] = useState<GradeReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [processing, setProcessing] = useState(false);
  const [grading, setGrading] = useState(false);
  const [validatingId, setValidatingId] = useState<string | null>(null);
  const [overrideValues, setOverrideValues] = useState<Record<string, string>>({});

  async function refreshAll() {
    const [c, p, s] = await Promise.all([
      apiGet<StudentCopy>(`/copies/${copyId}`),
      apiGet<CopyPage[]>(`/copies/${copyId}/pages`),
      apiGet<any>(`/copies/${copyId}/status`),
    ]);
    setCopy(c);
    setPages(p);
    setStatus(s);
  }

  async function loadReport() {
    try {
      const r = await apiGet<GradeReport>(`/copies/${copyId}/report`);
      setReport(r);
    } catch {
      setReport(null);
    }
  }

  useEffect(() => {
    refreshAll().catch((e) => setError(e?.message ?? "Failed to load"));
    const t = setInterval(() => refreshAll().catch(() => {}), 3000);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [copyId]);

  useEffect(() => {
    if (copy?.status === "corrected") loadReport().catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [copy?.status]);

  useEffect(() => {
    apiGet<IntegrationsStatus>("/integrations/status")
      .then(setIntegrations)
      .catch(() => setIntegrations(null));
  }, []);

  async function launch() {
    setProcessing(true);
    setError(null);
    try {
      await apiPostJson(`/copies/${copyId}/process`, {});
      await refreshAll();
    } catch (e: any) {
      setError(e?.message ?? "Failed to launch processing");
    } finally {
      setProcessing(false);
    }
  }

  async function launchGrade(force = false) {
    setGrading(true);
    setError(null);
    try {
      await apiPostJson(`/copies/${copyId}/grade${force ? "?force=true" : ""}`, {});
      await refreshAll();
      await loadReport();
    } catch (e: any) {
      const details = typeof e?.details === "string" ? e.details : JSON.stringify(e?.details ?? "");
      setError(`Correction échouée: ${details || e?.message}`);
    } finally {
      setGrading(false);
    }
  }

  async function validateQuestion(correctionId: string) {
    setValidatingId(correctionId);
    try {
      const override = overrideValues[correctionId];
      const params: Record<string, number> | undefined =
        override !== undefined && override !== "" ? { points_awarded: parseFloat(override) } : undefined;
      await apiPatch(`/corrections/${correctionId}/validate`, params);
      await loadReport();
    } catch (e: any) {
      setError(`Validation échouée: ${e?.message}`);
    } finally {
      setValidatingId(null);
    }
  }

  if (!copy) return <div className="p-6 text-sm text-slate-600">Chargement...</div>;

  const isProcessed = ["processed_pages", "ocr_pending", "corrected"].includes(copy.status);
  const isCorrected = copy.status === "corrected";

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">Copie élève</h1>
          <div className="mt-1 flex items-center gap-2 text-sm text-slate-600">
            <span>{copy.student_name ?? "Élève (non renseigné)"}</span>
            {copy.copy_code && <span className="text-slate-400">· {copy.copy_code}</span>}
            <StatusBadge status={copy.status} />
          </div>
        </div>
        <Link href={`/exams/${copy.exam_id}`} className="text-sm text-slate-700 hover:text-slate-900">
          ← Retour examen
        </Link>
      </div>

      {error && (
        <div className="rounded border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800 whitespace-pre-wrap">
          {error}
        </div>
      )}

      {/* Actions */}
      <div className="rounded border bg-white p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="text-sm">
            <div className="font-medium">Statut traitement</div>
            <div className="text-slate-600">
              {status ? `${status.status} · tâche: ${status.task_state ?? "n/a"}` : "—"}
            </div>
            {copy.error_message && <div className="mt-1 text-rose-700">{copy.error_message}</div>}
            {integrations && (
              <div className="mt-2 text-xs text-slate-500">
                Mathpix: {integrations.mathpix.configured ? "✓" : "✗"} · Azure:{" "}
                {integrations.azure_document_intelligence.configured ? "✓" : "✗"} · OpenAI:{" "}
                {integrations.openai.configured ? "✓" : "✗"}
              </div>
            )}
          </div>
          <div className="flex gap-2">
            <button
              onClick={launch}
              disabled={processing}
              className="rounded border border-slate-300 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50 disabled:opacity-50"
            >
              {processing ? "Traitement..." : "Traiter PDF"}
            </button>
            {isProcessed && (
              <button
                onClick={() => launchGrade(isCorrected)}
                disabled={grading}
                className="rounded bg-indigo-600 px-4 py-2 text-sm text-white hover:bg-indigo-700 disabled:opacity-50"
              >
                {grading ? "Correction en cours..." : isCorrected ? "Re-corriger" : "Corriger avec IA"}
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Report */}
      {report && (
        <div className="space-y-4">
          {/* Score global */}
          <div className="rounded border bg-white p-5">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <div className="text-sm text-slate-500">{report.exam.title}</div>
                <div className="mt-1 text-3xl font-bold">
                  {report.score.total_awarded}
                  <span className="text-lg text-slate-400"> / {report.score.total_max}</span>
                </div>
                <div className="mt-1 text-xl font-semibold text-slate-700">
                  {report.score.grade_over_20} / 20
                </div>
              </div>
              <div className="text-right">
                <span
                  className={`inline-block rounded-full px-3 py-1 text-sm font-semibold ${mentionColor(report.score.mention)}`}
                >
                  {report.score.mention}
                </span>
                <div className="mt-2 text-sm text-slate-500">{report.score.percentage}%</div>
                {report.needs_human_review && (
                  <div className="mt-1 text-xs text-amber-600">⚠ Révision humaine recommandée</div>
                )}
              </div>
            </div>

            {/* Audit */}
            {report.audit.flags.length > 0 && (
              <div className="mt-4 rounded bg-amber-50 p-3 text-xs text-amber-800">
                <div className="mb-1 font-semibold">Signalements audit :</div>
                <ul className="list-disc pl-4 space-y-0.5">
                  {report.audit.flags.map((f, i) => <li key={i}>{f}</li>)}
                </ul>
                {report.audit.summary && <div className="mt-2 italic">{report.audit.summary}</div>}
              </div>
            )}
          </div>

          {/* Questions */}
          <div className="rounded border bg-white divide-y">
            <div className="px-4 py-3 font-medium text-sm">Détail par question</div>
            {report.questions.map((q) => (
              <div key={q.question_id} className="px-4 py-4 space-y-2">
                <div className="flex items-center justify-between gap-3 flex-wrap">
                  <div className="font-medium text-sm">Question {q.question_id}</div>
                  <div className="flex items-center gap-3 text-sm">
                    <span className="text-slate-500 text-xs">
                      Confiance : {confidenceLabel(q.confidence)}
                    </span>
                    {q.needs_human_review && !q.status.includes("error") && (
                      <span className="text-xs text-amber-600">⚠ à vérifier</span>
                    )}
                    <span className={`font-semibold ${q.status === "error" ? "text-rose-600" : "text-slate-900"}`}>
                      {q.points_awarded !== null ? `${q.points_awarded} / ${q.points_max} pts` : `— / ${q.points_max} pts`}
                    </span>
                  </div>
                </div>

                {q.justification && (
                  <div className="text-sm text-slate-600 rounded bg-slate-50 px-3 py-2">{q.justification}</div>
                )}

                {q.criteria_details.length > 0 && (
                  <div className="space-y-1">
                    {q.criteria_details.map((c, i) => (
                      <div key={i} className="flex items-start gap-2 text-xs text-slate-600">
                        <span className="font-medium shrink-0">{c.awarded}pt</span>
                        <span className="text-slate-400">·</span>
                        <span>{c.criterion} — {c.comment}</span>
                      </div>
                    ))}
                  </div>
                )}

                {q.error_message && (
                  <div className="text-xs text-rose-600">Erreur: {q.error_message}</div>
                )}

                {q.needs_human_review && !q.validated_by_human && (
                  <div className="flex items-center gap-2 pt-1">
                    <input
                      type="number"
                      min={0}
                      max={q.points_max}
                      step={0.5}
                      placeholder={`Score (0–${q.points_max})`}
                      value={overrideValues[q.id] ?? ""}
                      onChange={(e) =>
                        setOverrideValues((prev) => ({ ...prev, [q.id]: e.target.value }))
                      }
                      className="w-28 rounded border px-2 py-1 text-xs"
                    />
                    <button
                      onClick={() => validateQuestion(q.id)}
                      disabled={validatingId === q.id}
                      className="rounded bg-slate-800 px-3 py-1 text-xs text-white disabled:opacity-50"
                    >
                      {validatingId === q.id ? "..." : "Valider"}
                    </button>
                  </div>
                )}
                {q.validated_by_human && (
                  <div className="text-xs text-emerald-600">✓ Validée manuellement</div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Pages */}
      <PageViewer pages={pages} />
    </div>
  );
}
