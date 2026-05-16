"use client";

import Link from "next/link";
import type { StudentCopy } from "@/lib/types";
import { StatusBadge } from "@/components/StatusBadge";

export function CopyCard({ copy }: { copy: StudentCopy }) {
  return (
    <Link href={`/copies/${copy.id}`} className="block rounded border bg-white p-4 hover:border-slate-300">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="font-semibold">{copy.student_name ?? "Élève (non renseigné)"}</div>
          <div className="text-sm text-slate-600">{copy.copy_code ?? "—"}</div>
        </div>
        <StatusBadge status={copy.status} />
      </div>
      {copy.error_message ? <div className="mt-2 text-sm text-rose-700">{copy.error_message}</div> : null}
    </Link>
  );
}

