"use client";

import { useEffect, useState } from "react";
import { apiGet, apiPostJson } from "@/lib/api";
import type { Exam } from "@/lib/types";
import { ExamCard } from "@/components/ExamCard";

export default function ExamsPage() {
  const [exams, setExams] = useState<Exam[]>([]);
  const [title, setTitle] = useState("");
  const [level, setLevel] = useState("");
  const [session, setSession] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    setExams(await apiGet<Exam[]>("/exams"));
  }

  useEffect(() => {
    refresh().catch((e) => setError(e?.message ?? "Failed to load exams"));
  }, []);

  async function create() {
    setError(null);
    const payload: any = { title: title.trim() };
    if (!payload.title) return;
    if (level.trim()) payload.level = level.trim();
    if (session.trim()) payload.session = session.trim();
    await apiPostJson<Exam>("/exams", payload);
    setTitle("");
    setLevel("");
    setSession("");
    await refresh();
  }

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold">Exams</h1>

      {error ? <div className="rounded border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">{error}</div> : null}

      <div className="rounded border bg-white p-4">
        <div className="mb-2 text-sm font-medium">Créer un examen</div>
        <div className="grid gap-2 md:grid-cols-3">
          <input className="rounded border px-3 py-2 text-sm" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Titre" />
          <input className="rounded border px-3 py-2 text-sm" value={level} onChange={(e) => setLevel(e.target.value)} placeholder="Niveau (optionnel)" />
          <input className="rounded border px-3 py-2 text-sm" value={session} onChange={(e) => setSession(e.target.value)} placeholder="Session (optionnel)" />
        </div>
        <button onClick={create} className="mt-3 rounded bg-slate-900 px-4 py-2 text-sm text-white">
          Créer
        </button>
      </div>

      <div className="grid gap-3">
        {exams.map((e) => (
          <ExamCard key={e.id} exam={e} />
        ))}
      </div>
    </div>
  );
}

