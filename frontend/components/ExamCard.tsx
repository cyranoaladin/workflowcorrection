"use client";

import Link from "next/link";
import type { Exam } from "@/lib/types";

export function ExamCard({ exam }: { exam: Exam }) {
  return (
    <Link href={`/exams/${exam.id}`} className="block rounded border bg-white p-4 hover:border-slate-300">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="font-semibold">{exam.title}</div>
          <div className="text-sm text-slate-600">
            {exam.level ?? "—"} · {exam.session ?? "—"}
          </div>
        </div>
        <div className="text-xs text-slate-500">{new Date(exam.created_at).toLocaleString()}</div>
      </div>
    </Link>
  );
}

