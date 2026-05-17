"use client";

import { useEffect, useState } from "react";
import { BookOpen, Plus, Search, Loader2, AlertCircle } from "lucide-react";
import { apiGet, apiPostJson } from "@/lib/api";
import type { Exam } from "@/lib/types";
import { ExamCard } from "@/components/ExamCard";

export default function ExamsPage() {
  const [exams, setExams] = useState<Exam[]>([]);
  const [title, setTitle] = useState("");
  const [level, setLevel] = useState("");
  const [session, setSession] = useState("");
  const [search, setSearch] = useState("");
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    setExams(await apiGet<Exam[]>("/exams"));
  }

  useEffect(() => {
    refresh().catch((e) => setError(e?.message ?? "Erreur de chargement"));
  }, []);

  async function create(e: React.FormEvent) {
    e.preventDefault();
    if (!title.trim()) return;
    setCreating(true);
    setError(null);
    try {
      const payload: Record<string, string> = { title: title.trim() };
      if (level.trim()) payload.level = level.trim();
      if (session.trim()) payload.session = session.trim();
      await apiPostJson<Exam>("/exams", payload);
      setTitle(""); setLevel(""); setSession("");
      await refresh();
    } catch (e: any) {
      setError(e?.message ?? "Erreur lors de la création");
    } finally {
      setCreating(false);
    }
  }

  const filtered = exams.filter((e) =>
    !search.trim() ||
    e.title.toLowerCase().includes(search.toLowerCase()) ||
    (e.level ?? "").toLowerCase().includes(search.toLowerCase()) ||
    (e.session ?? "").toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="space-y-6 animate-slide-up">

      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-600 text-white shadow-sm">
            <BookOpen className="h-5 w-5" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-slate-900">Examens</h1>
            <p className="text-sm text-slate-500">{exams.length} examen{exams.length !== 1 ? "s" : ""}</p>
          </div>
        </div>
      </div>

      {error && (
        <div className="flex items-start gap-2 rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" /> {error}
        </div>
      )}

      {/* Create form */}
      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-card">
        <div className="mb-4 flex items-center gap-2">
          <Plus className="h-4 w-4 text-indigo-600" />
          <h2 className="text-sm font-semibold text-slate-800">Nouvel examen</h2>
        </div>
        <form onSubmit={create} className="space-y-3">
          <div className="grid gap-3 sm:grid-cols-3">
            <input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Titre *"
              required
              className="input"
            />
            <input
              value={level}
              onChange={(e) => setLevel(e.target.value)}
              placeholder="Niveau (ex. Terminale S)"
              className="input"
            />
            <input
              value={session}
              onChange={(e) => setSession(e.target.value)}
              placeholder="Session (ex. Juin 2025)"
              className="input"
            />
          </div>
          <button
            type="submit"
            disabled={creating || !title.trim()}
            className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-5 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {creating
              ? <><Loader2 className="h-3.5 w-3.5 animate-spin" /> Création…</>
              : <><Plus className="h-3.5 w-3.5" /> Créer l&apos;examen</>}
          </button>
        </form>
      </div>

      {/* Search */}
      {exams.length > 0 && (
        <div className="relative">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Rechercher un examen…"
            className="input pl-9"
          />
        </div>
      )}

      {/* List */}
      {filtered.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-xl border-2 border-dashed border-slate-200 bg-white py-16 text-center">
          <BookOpen className="mb-3 h-10 w-10 text-slate-300" />
          <p className="font-medium text-slate-500">
            {search ? "Aucun examen ne correspond à votre recherche" : "Aucun examen créé pour le moment"}
          </p>
          {!search && (
            <p className="mt-1 text-sm text-slate-400">Utilisez le formulaire ci-dessus pour créer votre premier examen.</p>
          )}
        </div>
      ) : (
        <div className="grid gap-3">
          {filtered.map((e) => (
            <ExamCard key={e.id} exam={e} />
          ))}
        </div>
      )}
    </div>
  );
}

