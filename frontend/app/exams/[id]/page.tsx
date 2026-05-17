"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  ChevronLeft, BarChart2, FileText, Users, Brain,
  CheckCircle2, AlertCircle, Loader2, Save, Code2
} from "lucide-react";
import { apiGet, apiPostForm, apiPostJson } from "@/lib/api";
import type { Exam, StudentCopy } from "@/lib/types";
import { CopyCard } from "@/components/CopyCard";
import { FileUpload } from "@/components/FileUpload";
import { StudentCsvUpload } from "@/components/StudentCsvUpload";

export default function ExamDetailPage() {
  const params = useParams();
  const id = params.id as string;
  const examId = useMemo(() => id, [id]);

  const [exam, setExam] = useState<Exam | null>(null);
  const [copies, setCopies] = useState<StudentCopy[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [rubricText, setRubricText] = useState("");
  const [rubricSaving, setRubricSaving] = useState(false);
  const [rubricError, setRubricError] = useState<string | null>(null);
  const [rubricSaved, setRubricSaved] = useState(false);

  async function refresh() {
    const [e, c] = await Promise.all([
      apiGet<Exam>(`/exams/${examId}`),
      apiGet<StudentCopy[]>(`/copies?exam_id=${examId}`),
    ]);
    setExam(e);
    setCopies(c);
  }

  useEffect(() => {
    refresh().catch((e) => setError(e?.message ?? "Erreur de chargement"));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [examId]);

  async function uploadExamFile(kind: "subject_pdf" | "correction_pdf" | "rubric_pdf", file: File) {
    const form = new FormData();
    form.set(kind, file);
    await apiPostForm<Exam>(`/exams/${examId}/files`, form);
    await refresh();
  }

  async function uploadCopy(file: File) {
    const form = new FormData();
    form.set("exam_id", examId);
    form.set("file", file);
    await apiPostForm<StudentCopy>("/copies", form);
    await refresh();
  }

  async function saveRubricJson() {
    setRubricSaving(true);
    setRubricError(null);
    setRubricSaved(false);
    try {
      const parsed = JSON.parse(rubricText);
      await apiPostJson(`/exams/${examId}/rubric-json`, parsed);
      setRubricSaved(true);
      setRubricText("");
      setTimeout(() => setRubricSaved(false), 3000);
      await refresh();
    } catch (e: any) {
      setRubricError(e?.message ?? "JSON invalide ou erreur serveur");
    } finally {
      setRubricSaving(false);
    }
  }

  if (!exam) {
    return (
      <div className="flex items-center justify-center py-24 text-slate-400">
        <Loader2 className="mr-2 h-5 w-5 animate-spin" /> Chargement…
      </div>
    );
  }

  const rubricQuestions = (exam.rubric_json as any)?.questions ?? [];
  const correctedCount = copies.filter((c) => c.status === "corrected").length;

  return (
    <div className="space-y-6 animate-slide-up">

      {/* Breadcrumb + header */}
      <div>
        <Link href="/exams" className="mb-3 inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-800 transition-colors">
          <ChevronLeft className="h-4 w-4" /> Retour aux examens
        </Link>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-slate-900">{exam.title}</h1>
            <div className="mt-1 flex flex-wrap items-center gap-2">
              {exam.level && (
                <span className="rounded-md bg-indigo-50 px-2 py-0.5 text-xs font-medium text-indigo-700">{exam.level}</span>
              )}
              {exam.session && (
                <span className="text-sm text-slate-500">{exam.session}</span>
              )}
              <span className="text-xs text-slate-400">{exam.total_points} pts max</span>
            </div>
          </div>
          <Link
            href={`/exams/${examId}/bilan`}
            className="inline-flex items-center gap-2 rounded-lg border border-indigo-200 bg-indigo-50 px-4 py-2 text-sm font-medium text-indigo-700 hover:bg-indigo-100 transition-colors shadow-sm"
          >
            <BarChart2 className="h-4 w-4" /> Bilan classe
          </Link>
        </div>
      </div>

      {error && (
        <div className="flex items-start gap-2 rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" /> {error}
        </div>
      )}

      {/* Progress pills */}
      <div className="flex flex-wrap gap-3">
        {[
          { icon: FileText,     label: "Sujet",    done: !!exam.subject_pdf_path },
          { icon: FileText,     label: "Corrigé",  done: !!exam.correction_pdf_path },
          { icon: FileText,     label: "Barème PDF",done: !!exam.rubric_pdf_path },
          { icon: Brain,        label: "Barème IA", done: rubricQuestions.length > 0 },
          { icon: Users,        label: `${copies.length} copie${copies.length !== 1 ? "s" : ""}`, done: copies.length > 0 },
          { icon: CheckCircle2, label: `${correctedCount} corrigée${correctedCount !== 1 ? "s" : ""}`, done: correctedCount > 0 },
        ].map((step) => (
          <div
            key={step.label}
            className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium transition-colors ${
              step.done
                ? "bg-emerald-100 text-emerald-700"
                : "bg-slate-100 text-slate-500"
            }`}
          >
            <step.icon className="h-3 w-3" />
            {step.label}
            {step.done && <span className="ml-0.5">✓</span>}
          </div>
        ))}
      </div>

      {/* Section: Documents */}
      <div>
        <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-700">
          <FileText className="h-4 w-4 text-slate-400" /> Documents de l&apos;examen
        </h2>
        <div className="grid gap-3 sm:grid-cols-3">
          <FileUpload label="Sujet (PDF)" accept="application/pdf" onUpload={(f) => uploadExamFile("subject_pdf", f)} />
          <FileUpload label="Corrigé (PDF)" accept="application/pdf" onUpload={(f) => uploadExamFile("correction_pdf", f)} />
          <FileUpload label="Barème (PDF)" accept="application/pdf" onUpload={(f) => uploadExamFile("rubric_pdf", f)} />
        </div>
      </div>

      {/* Section: Copies */}
      <div>
        <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-700">
          <Users className="h-4 w-4 text-slate-400" /> Copies élèves
        </h2>
        <div className="space-y-3">
          <FileUpload label="Uploader une copie (PDF)" accept="application/pdf" onUpload={uploadCopy} />
          <StudentCsvUpload examId={examId} onImported={() => refresh()} />
        </div>
      </div>

      {/* Section: Rubric JSON */}
      <div>
        <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-700">
          <Brain className="h-4 w-4 text-slate-400" /> Barème structuré (JSON) — requis pour la correction IA
        </h2>
        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-card">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2 text-xs text-slate-500">
              <Code2 className="h-3.5 w-3.5" />
              Format&nbsp;: <code className="rounded bg-slate-100 px-1.5 py-0.5 text-slate-600">{`{"questions":[{"id":"Q1","label":"…","points_max":4,"criteria":["…"]}]}`}</code>
            </div>
            {rubricQuestions.length > 0 && (
              <span className="inline-flex items-center gap-1 rounded-full bg-emerald-100 px-2.5 py-0.5 text-xs font-semibold text-emerald-700">
                <CheckCircle2 className="h-3 w-3" /> {rubricQuestions.length} question(s)
              </span>
            )}
          </div>
          <textarea
            className="w-full rounded-lg border border-slate-300 bg-slate-50 px-3 py-2.5 font-mono text-xs leading-relaxed focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100 focus:outline-none transition-colors"
            rows={6}
            placeholder={`{"questions": [{"id": "Q1", "label": "Calculer f(x)", "points_max": 4, "criteria": ["Règle de dérivation", "Simplification"]}]}`}
            value={rubricText || (exam.rubric_json ? JSON.stringify(exam.rubric_json, null, 2) : "")}
            onChange={(e) => setRubricText(e.target.value)}
          />
          {rubricError && (
            <div className="mt-2 flex items-center gap-1.5 text-xs text-rose-600">
              <AlertCircle className="h-3.5 w-3.5" /> {rubricError}
            </div>
          )}
          <div className="mt-3 flex items-center gap-3">
            <button
              onClick={saveRubricJson}
              disabled={rubricSaving || !rubricText.trim()}
              className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {rubricSaving
                ? <><Loader2 className="h-3.5 w-3.5 animate-spin" /> Enregistrement…</>
                : rubricSaved
                ? <><CheckCircle2 className="h-3.5 w-3.5" /> Enregistré !</>
                : <><Save className="h-3.5 w-3.5" /> Enregistrer le barème</>}
            </button>
          </div>
        </div>
      </div>

      {/* Section: Copies list */}
      <div>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="flex items-center gap-2 text-sm font-semibold text-slate-700">
            <Users className="h-4 w-4 text-slate-400" />
            {copies.length} copie{copies.length !== 1 ? "s" : ""}
            {correctedCount > 0 && (
              <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-700">
                {correctedCount} corrigée{correctedCount !== 1 ? "s" : ""}
              </span>
            )}
          </h2>
        </div>
        {copies.length === 0 ? (
          <div className="flex flex-col items-center justify-center rounded-xl border-2 border-dashed border-slate-200 bg-white py-12 text-center">
            <Users className="mb-2 h-8 w-8 text-slate-300" />
            <p className="text-sm font-medium text-slate-500">Aucune copie pour le moment</p>
            <p className="mt-1 text-xs text-slate-400">Uploadez un PDF ou importez une liste CSV ci-dessus.</p>
          </div>
        ) : (
          <div className="grid gap-2">
            {copies.map((c) => (
              <CopyCard key={c.id} copy={c} />
            ))}
          </div>
        )}
      </div>

    </div>
  );
}

