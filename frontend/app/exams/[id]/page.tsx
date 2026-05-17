"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { apiGet, apiPostForm, apiPostJson } from "@/lib/api";
import type { Exam, StudentCopy } from "@/lib/types";
import { CopyCard } from "@/components/CopyCard";
import { FileUpload } from "@/components/FileUpload";
import { StudentCsvUpload } from "@/components/StudentCsvUpload";

export default function ExamDetailPage() {
  const params = useParams();
  const id = params.id as string;
  const [exam, setExam] = useState<Exam | null>(null);
  const [copies, setCopies] = useState<StudentCopy[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [rubricText, setRubricText] = useState<string>("");
  const [rubricSaving, setRubricSaving] = useState(false);
  const [rubricError, setRubricError] = useState<string | null>(null);

  const examId = useMemo(() => id, [id]);

  async function refresh() {
    const [e, c] = await Promise.all([apiGet<Exam>(`/exams/${examId}`), apiGet<StudentCopy[]>(`/copies?exam_id=${examId}`)]);
    setExam(e);
    setCopies(c);
  }

  useEffect(() => {
    refresh().catch((e) => setError(e?.message ?? "Failed to load"));
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
    try {
      const parsed = JSON.parse(rubricText);
      await apiPostJson(`/exams/${examId}/rubric-json`, parsed);
      await refresh();
    } catch (e: any) {
      setRubricError(e?.message ?? "JSON invalide ou erreur serveur");
    } finally {
      setRubricSaving(false);
    }
  }

  if (!exam) {
    return <div className="text-sm text-slate-600">Chargement...</div>;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">{exam.title}</h1>
          <div className="text-sm text-slate-600">
            {exam.level ?? "—"} · {exam.session ?? "—"}
          </div>
        </div>
        <div className="flex gap-3">
          <Link href={`/exams/${examId}/bilan`} className="rounded border border-indigo-300 px-3 py-1.5 text-sm text-indigo-700 hover:bg-indigo-50">
            Bilan classe
          </Link>
          <Link href="/exams" className="text-sm text-slate-700 hover:text-slate-900 self-center">
            ← Back
          </Link>
        </div>
      </div>

      {error ? <div className="rounded border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">{error}</div> : null}

      <div className="grid gap-4 md:grid-cols-3">
        <FileUpload label="Upload sujet (PDF)" accept="application/pdf" onUpload={(f) => uploadExamFile("subject_pdf", f)} />
        <FileUpload label="Upload corrigé (PDF)" accept="application/pdf" onUpload={(f) => uploadExamFile("correction_pdf", f)} />
        <FileUpload label="Upload barème (PDF)" accept="application/pdf" onUpload={(f) => uploadExamFile("rubric_pdf", f)} />
      </div>

      <FileUpload label="Upload copie élève (PDF)" accept="application/pdf" onUpload={uploadCopy} />

      <StudentCsvUpload examId={examId} onImported={() => refresh()} />

      {/* Rubric JSON */}
      <div className="rounded border bg-white p-4">
        <div className="mb-2 flex items-center justify-between">
          <div className="text-sm font-medium">Barème structuré (JSON) — requis pour la correction IA</div>
          {exam.rubric_json && (exam.rubric_json as any).questions && (
            <span className="text-xs text-emerald-600">✓ {((exam.rubric_json as any).questions as any[]).length} question(s) configurée(s)</span>
          )}
        </div>
        <p className="mb-2 text-xs text-slate-500">
          Format : <code className="rounded bg-slate-100 px-1">{`{"questions":[{"id":"Q1","label":"...","points_max":4,"criteria":["..."],"expected_answer":"..."}]}`}</code>
        </p>
        <textarea
          className="w-full rounded border px-3 py-2 font-mono text-xs"
          rows={5}
          placeholder='{"questions": [{"id": "Q1", "label": "...", "points_max": 4, "criteria": ["..."]}]}'
          value={rubricText || (exam.rubric_json ? JSON.stringify(exam.rubric_json, null, 2) : "")}
          onChange={(e) => setRubricText(e.target.value)}
        />
        {rubricError && <div className="mt-1 text-xs text-rose-600">{rubricError}</div>}
        <button
          onClick={saveRubricJson}
          disabled={rubricSaving || !rubricText}
          className="mt-2 rounded bg-indigo-600 px-3 py-1.5 text-xs text-white hover:bg-indigo-700 disabled:opacity-50"
        >
          {rubricSaving ? "Enregistrement..." : "Enregistrer le barème"}
        </button>
      </div>

      <div className="space-y-3">
        <div className="text-sm font-medium">Copies</div>
        {copies.length === 0 ? <div className="text-sm text-slate-600">Aucune copie pour le moment.</div> : null}
        <div className="grid gap-3">
          {copies.map((c) => (
            <CopyCard key={c.id} copy={c} />
          ))}
        </div>
      </div>
    </div>
  );
}

