"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  ChevronLeft, Cpu, Brain, CheckCircle2, AlertTriangle,
  RefreshCw, Loader2, AlertCircle, Shield, ChevronDown, ChevronUp
} from "lucide-react";
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

  if (!copy) {
    return (
      <div className="flex items-center justify-center py-24 text-gray-400">
        <Loader2 className="mr-2 h-5 w-5 animate-spin" /> Chargement…
      </div>
    );
  }

  const isProcessed = ["processed_pages", "ocr_pending", "corrected"].includes(copy.status);
  const isCorrected = copy.status === "corrected";

  return (
    <div className="space-y-6">

      {/* Breadcrumb */}
      <div>
        <Link
          href={`/exams/${copy.exam_id}`}
          className="mb-3 inline-flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-800 transition-colors"
        >
          <ChevronLeft className="h-4 w-4" /> Retour à l&apos;examen
        </Link>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-xl font-bold text-gray-900 tracking-tight">
              {copy.student_name ?? <span className="italic text-gray-400">Élève non renseigné</span>}
            </h1>
            <div className="mt-1 flex flex-wrap items-center gap-2">
              {copy.copy_code && (
                <span className="rounded bg-gray-100 px-1.5 py-0.5 font-mono text-xs text-gray-500">{copy.copy_code}</span>
              )}
              <StatusBadge status={copy.status} />
            </div>
          </div>
        </div>
      </div>

      {error && (
        <div className="flex items-start gap-2 rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700 whitespace-pre-wrap">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" /> {error}
        </div>
      )}

      {/* Actions card */}
      <div className="card p-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="space-y-2">
            <div className="text-sm font-semibold text-gray-700">Traitement &amp; correction</div>
            <div className="text-xs text-gray-500">
              {status ? (
                <span>Statut&nbsp;: <span className="font-medium text-gray-700">{status.status}</span> · Tâche&nbsp;: <span className="font-mono">{status.task_state ?? "n/a"}</span></span>
              ) : "—"}
            </div>
            {copy.error_message && (
              <div className="flex items-center gap-1.5 text-xs text-rose-600">
                <AlertCircle className="h-3.5 w-3.5" /> {copy.error_message}
              </div>
            )}
            {integrations && (
              <div className="flex flex-wrap gap-2">
                {[
                  { label: "Mathpix", ok: integrations.mathpix.configured },
                  { label: "Azure",   ok: integrations.azure_document_intelligence.configured },
                  { label: "OpenAI",  ok: integrations.openai.configured },
                ].map((int) => (
                  <span key={int.label} className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${int.ok ? "bg-emerald-100 text-emerald-700" : "bg-slate-100 text-slate-500"}`}>
                    <span className={`h-1.5 w-1.5 rounded-full ${int.ok ? "bg-emerald-500" : "bg-slate-400"}`} />
                    {int.label}
                  </span>
                ))}
              </div>
            )}
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              onClick={launch}
              disabled={processing}
              className="inline-flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 shadow-sm hover:bg-slate-50 disabled:opacity-50 transition-colors"
            >
              {processing ? <><Loader2 className="h-3.5 w-3.5 animate-spin" /> Traitement…</> : <><Cpu className="h-3.5 w-3.5" /> Traiter PDF</>}
            </button>
            {isProcessed && (
              <button
                onClick={() => launchGrade(isCorrected)}
                disabled={grading}
                className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-indigo-700 disabled:opacity-50 transition-colors"
              >
                {grading
                  ? <><Loader2 className="h-3.5 w-3.5 animate-spin" /> Correction…</>
                  : isCorrected
                  ? <><RefreshCw className="h-3.5 w-3.5" /> Re-corriger</>
                  : <><Brain className="h-3.5 w-3.5" /> Corriger avec IA</>}
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Report */}
      {report && (
        <div className="space-y-4">

          {/* Score hero */}
          <div className="card p-6">
            <div className="flex flex-wrap items-start justify-between gap-6">
              <div>
                <div className="text-sm text-gray-500">{report.exam.title}</div>
                <div className="mt-2 flex items-end gap-3">
                  <span className="text-5xl font-extrabold text-gray-900">{report.score.grade_over_20}</span>
                  <span className="mb-1 text-xl text-gray-400">/ 20</span>
                </div>
                <div className="mt-1 text-sm text-gray-500">
                  {report.score.total_awarded} / {report.score.total_max} pts ({report.score.percentage}%)
                </div>
              </div>
              <div className="flex flex-col items-end gap-2">
                <span className={`rounded-xl px-4 py-1.5 text-sm font-bold ${mentionColor(report.score.mention)}`}>
                  {report.score.mention}
                </span>
                {report.needs_human_review && (
                  <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-100 px-3 py-1 text-xs font-medium text-amber-700">
                    <AlertTriangle className="h-3.5 w-3.5" /> Révision recommandée
                  </span>
                )}
              </div>
            </div>

            {/* Score bar */}
            <div className="mt-4">
              <div className="h-2 w-full rounded-full bg-slate-100 overflow-hidden">
                <div
                  className="h-full rounded-full bg-indigo-500 transition-all"
                  style={{ width: `${Math.min(report.score.percentage, 100)}%` }}
                />
              </div>
            </div>

            {/* Audit flags */}
            {report.audit.flags.length > 0 && (
              <div className="mt-4 rounded-lg border border-amber-200 bg-amber-50 p-3">
                <div className="mb-1.5 flex items-center gap-1.5 text-xs font-semibold text-amber-800">
                  <Shield className="h-3.5 w-3.5" /> Signalements audit
                </div>
                <ul className="space-y-0.5 text-xs text-amber-700">
                  {report.audit.flags.map((f, i) => (
                    <li key={i} className="flex items-start gap-1.5">
                      <span className="mt-0.5 h-1.5 w-1.5 shrink-0 rounded-full bg-amber-400" />{f}
                    </li>
                  ))}
                </ul>
                {report.audit.summary && (
                  <div className="mt-2 text-xs italic text-amber-600">{report.audit.summary}</div>
                )}
              </div>
            )}
          </div>

          {/* Questions */}
          <div className="card overflow-hidden">
            <div className="border-b border-gray-100 px-5 py-4">
              <h2 className="text-base font-semibold text-gray-900">Détail par question</h2>
            </div>
            <div className="divide-y divide-gray-100">
              {report.questions.map((q) => (
                <QuestionCard
                  key={q.question_id}
                  q={q}
                  validatingId={validatingId}
                  overrideValues={overrideValues}
                  setOverrideValues={setOverrideValues}
                  onValidate={validateQuestion}
                />
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Pages */}
      <PageViewer pages={pages} />
    </div>
  );
}

type Q = GradeReport["questions"][number];

function QuestionCard({
  q,
  validatingId,
  overrideValues,
  setOverrideValues,
  onValidate,
}: {
  q: Q;
  validatingId: string | null;
  overrideValues: Record<string, string>;
  setOverrideValues: React.Dispatch<React.SetStateAction<Record<string, string>>>;
  onValidate: (id: string) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const isError = q.status === "error";
  const confPct = q.confidence != null ? Math.round(q.confidence * 100) : null;

  return (
    <div className={`px-5 py-4 ${isError ? "bg-rose-50/40" : ""}`}>
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-2">
          <span className="rounded-md bg-indigo-50 px-2 py-0.5 text-xs font-bold text-indigo-700">Q{q.question_id}</span>
          {q.needs_human_review && !q.validated_by_human && !isError && (
            <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700">
              <AlertTriangle className="h-3 w-3" /> À vérifier
            </span>
          )}
          {q.validated_by_human && (
            <span className="inline-flex items-center gap-1 rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-700">
              <CheckCircle2 className="h-3 w-3" /> Validée
            </span>
          )}
        </div>
        <div className="flex items-center gap-3">
          {confPct != null && (
            <div className="flex items-center gap-1.5">
              <div className="h-1.5 w-16 rounded-full bg-slate-100 overflow-hidden">
                <div
                  className={`h-full rounded-full ${confPct >= 80 ? "bg-emerald-500" : confPct >= 50 ? "bg-amber-400" : "bg-rose-400"}`}
                  style={{ width: `${confPct}%` }}
                />
              </div>
              <span className="text-xs text-slate-500">{confPct}%</span>
            </div>
          )}
          <span className={`text-sm font-bold ${isError ? "text-rose-600" : "text-slate-900"}`}>
            {q.points_awarded !== null ? `${q.points_awarded}` : "—"}<span className="text-slate-400 font-normal"> / {q.points_max} pts</span>
          </span>
          <button
            onClick={() => setExpanded((v) => !v)}
            className="rounded-md p-1 text-slate-400 hover:bg-slate-100 transition-colors"
            aria-label={expanded ? "Réduire" : "Voir détails"}
          >
            {expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
          </button>
        </div>
      </div>

      {expanded && (
        <div className="mt-3 space-y-3">
          {q.justification && (
            <div className="rounded-lg bg-slate-50 border border-slate-200 px-3 py-2.5 text-sm text-slate-700 leading-relaxed">
              {q.justification}
            </div>
          )}
          {q.criteria_details.length > 0 && (
            <div className="space-y-1.5">
              {q.criteria_details.map((c, i) => (
                <div key={i} className="flex items-start gap-2 text-xs text-slate-600">
                  <span className={`mt-0.5 shrink-0 rounded px-1.5 py-0.5 font-semibold ${c.awarded > 0 ? "bg-emerald-100 text-emerald-700" : "bg-slate-100 text-slate-500"}`}>
                    {c.awarded}pt
                  </span>
                  <span className="text-slate-700 font-medium">{c.criterion}</span>
                  {c.comment && <span className="text-slate-500">— {c.comment}</span>}
                </div>
              ))}
            </div>
          )}
          {q.error_message && (
            <div className="flex items-center gap-1.5 text-xs text-rose-600">
              <AlertCircle className="h-3.5 w-3.5" /> {q.error_message}
            </div>
          )}
          {q.needs_human_review && !q.validated_by_human && (
            <div className="rounded-lg border border-amber-200 bg-amber-50 p-3">
              <div className="mb-2 text-xs font-semibold text-amber-800">Validation manuelle requise</div>
              <div className="flex items-center gap-2">
                <input
                  type="number"
                  min={0}
                  max={q.points_max}
                  step={0.5}
                  placeholder={`Score (0 – ${q.points_max})`}
                  value={overrideValues[q.id] ?? ""}
                  onChange={(e) => setOverrideValues((prev) => ({ ...prev, [q.id]: e.target.value }))}
                  className="w-32 rounded-lg border border-amber-300 bg-white px-2.5 py-1.5 text-xs focus:border-amber-500 focus:outline-none"
                />
                <button
                  onClick={() => onValidate(q.id)}
                  disabled={validatingId === q.id}
                  className="inline-flex items-center gap-1.5 rounded-lg bg-amber-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-amber-700 disabled:opacity-50 transition-colors"
                >
                  {validatingId === q.id ? <><Loader2 className="h-3 w-3 animate-spin" /> …</> : <><CheckCircle2 className="h-3 w-3" /> Valider</>}
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
