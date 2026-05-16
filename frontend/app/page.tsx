"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ApiHealthBadge } from "@/components/ApiHealthBadge";
import { apiGet, apiPostJson } from "@/lib/api";
import type { Exam, StudentCopy } from "@/lib/types";

export default function Dashboard() {
  const [exams, setExams] = useState<Exam[]>([]);
  const [copies, setCopies] = useState<StudentCopy[]>([]);
  const [title, setTitle] = useState("");
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    const [e, c] = await Promise.all([apiGet<Exam[]>("/exams"), apiGet<StudentCopy[]>("/copies")]);
    setExams(e);
    setCopies(c);
  }

  useEffect(() => {
    refresh().catch((e) => setError(e?.message ?? "Failed to load"));
  }, []);

  async function createExam() {
    if (!title.trim()) return;
    setCreating(true);
    setError(null);
    try {
      await apiPostJson<Exam>("/exams", { title });
      setTitle("");
      await refresh();
    } catch (e: any) {
      setError(e?.message ?? "Failed to create exam");
    } finally {
      setCreating(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Dashboard</h1>
        <ApiHealthBadge />
      </div>

      {error ? <div className="rounded border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">{error}</div> : null}

      <div className="grid gap-4 md:grid-cols-2">
        <div className="rounded border bg-white p-4">
          <div className="text-sm text-slate-600">Exams</div>
          <div className="mt-1 text-3xl font-semibold">{exams.length}</div>
          <div className="mt-3 flex gap-2">
            <Link href="/exams" className="rounded bg-slate-100 px-3 py-1.5 text-sm">
              Voir
            </Link>
          </div>
        </div>
        <div className="rounded border bg-white p-4">
          <div className="text-sm text-slate-600">Copies</div>
          <div className="mt-1 text-3xl font-semibold">{copies.length}</div>
        </div>
      </div>

      <div className="rounded border bg-white p-4">
        <div className="mb-2 text-sm font-medium">Créer un examen</div>
        <div className="flex flex-wrap gap-2">
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Titre"
            className="w-full rounded border px-3 py-2 text-sm md:w-80"
          />
          <button
            onClick={createExam}
            disabled={creating}
            className="rounded bg-slate-900 px-4 py-2 text-sm text-white disabled:opacity-50"
          >
            {creating ? "Création..." : "Créer"}
          </button>
        </div>
        <div className="mt-2 text-xs text-slate-500">Pour niveau/session, utilise la page de création avancée (phase 2).</div>
      </div>
    </div>
  );
}

