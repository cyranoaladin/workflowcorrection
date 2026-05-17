"use client";

import Link from "next/link";
import { ArrowRight } from "lucide-react";
import type { StudentCopy } from "@/lib/types";
import { StatusBadge } from "@/components/StatusBadge";

function Initials({ name }: { name: string | null }) {
  const letters = (name ?? "?").split(" ").map((w) => w[0]).slice(0, 2).join("").toUpperCase();
  return (
    <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-indigo-100 text-sm font-semibold text-indigo-700">
      {letters}
    </div>
  );
}

export function CopyCard({ copy }: { copy: StudentCopy }) {
  const score = copy.total_score != null ? Number(copy.total_score) : null;

  return (
    <Link
      href={`/copies/${copy.id}`}
      className="group flex items-center gap-4 rounded-xl border border-slate-200 bg-white px-5 py-4 shadow-card hover:shadow-card-hover hover:border-indigo-200 transition-all duration-200"
    >
      <Initials name={copy.student_name} />

      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="font-semibold text-slate-900 truncate">
            {copy.student_name ?? <span className="italic text-slate-400">Nom non renseigné</span>}
          </span>
          {copy.copy_code && (
            <span className="shrink-0 rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-500 font-mono">{copy.copy_code}</span>
          )}
        </div>
        <div className="mt-1 flex flex-wrap items-center gap-2">
          <StatusBadge status={copy.status} />
          {score !== null && (
            <span className="text-xs font-semibold text-indigo-700">{score} pts</span>
          )}
        </div>
        {copy.error_message && (
          <div className="mt-1.5 flex items-center gap-1 text-xs text-rose-600">
            <span className="h-1.5 w-1.5 rounded-full bg-rose-500" />
            {copy.error_message}
          </div>
        )}
      </div>

      <ArrowRight className="h-4 w-4 shrink-0 text-slate-300 transition-transform group-hover:translate-x-0.5 group-hover:text-indigo-400" />
    </Link>
  );
}
