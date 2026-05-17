"use client";

import Link from "next/link";
import { ArrowRight, BookOpen, FileText, CheckCircle2 } from "lucide-react";
import type { Exam } from "@/lib/types";

export function ExamCard({ exam }: { exam: Exam }) {
  const hasRubric = !!(exam.rubric_json as any)?.questions?.length;
  const hasPdfs = !!(exam.subject_pdf_path || exam.correction_pdf_path);

  return (
    <Link
      href={`/exams/${exam.id}`}
      className="group block rounded-xl border border-slate-200 bg-white p-5 shadow-card hover:shadow-card-hover hover:border-indigo-200 transition-all duration-200"
    >
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-3 min-w-0">
          <div className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-indigo-50 text-indigo-600">
            <BookOpen className="h-4 w-4" />
          </div>
          <div className="min-w-0">
            <div className="font-semibold text-slate-900 truncate">{exam.title}</div>
            <div className="mt-0.5 flex items-center gap-2 text-sm text-slate-500">
              {exam.level && <span className="rounded-md bg-slate-100 px-1.5 py-0.5 text-xs font-medium">{exam.level}</span>}
              {exam.session && <span className="text-slate-400">{exam.session}</span>}
              {!exam.level && !exam.session && <span className="italic text-slate-400">Niveau/session non renseigné</span>}
            </div>
          </div>
        </div>

        <div className="flex shrink-0 items-center gap-3">
          <div className="hidden sm:flex items-center gap-2">
            {hasPdfs && (
              <span className="inline-flex items-center gap-1 rounded-md bg-slate-100 px-2 py-0.5 text-xs text-slate-600">
                <FileText className="h-3 w-3" /> PDF
              </span>
            )}
            {hasRubric && (
              <span className="inline-flex items-center gap-1 rounded-md bg-emerald-50 px-2 py-0.5 text-xs text-emerald-700">
                <CheckCircle2 className="h-3 w-3" /> Barème
              </span>
            )}
          </div>
          <ArrowRight className="h-4 w-4 text-slate-400 transition-transform group-hover:translate-x-0.5 group-hover:text-indigo-500" />
        </div>
      </div>

      <div className="mt-3 text-xs text-slate-400">
        Créé le {new Date(exam.created_at).toLocaleDateString("fr-FR", { day: "numeric", month: "long", year: "numeric" })}
      </div>
    </Link>
  );
}

