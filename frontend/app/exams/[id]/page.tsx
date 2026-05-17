"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { apiGet, apiPostForm } from "@/lib/api";
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
        <Link href="/exams" className="text-sm text-slate-700 hover:text-slate-900">
          ← Back
        </Link>
      </div>

      {error ? <div className="rounded border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">{error}</div> : null}

      <div className="grid gap-4 md:grid-cols-3">
        <FileUpload label="Upload sujet (PDF)" accept="application/pdf" onUpload={(f) => uploadExamFile("subject_pdf", f)} />
        <FileUpload label="Upload corrigé (PDF)" accept="application/pdf" onUpload={(f) => uploadExamFile("correction_pdf", f)} />
        <FileUpload label="Upload barème (PDF)" accept="application/pdf" onUpload={(f) => uploadExamFile("rubric_pdf", f)} />
      </div>

      <FileUpload label="Upload copie élève (PDF)" accept="application/pdf" onUpload={uploadCopy} />

      <StudentCsvUpload examId={examId} onImported={() => refresh()} />

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

