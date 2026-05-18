"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { BookOpen, Plus, Search, Loader2, AlertCircle, ChevronRight } from "lucide-react";
import { apiGet, apiPostJson } from "@/lib/api";
import type { Exam } from "@/lib/types";
import { formatRelative } from "@/lib/utils";

export default function ExamsPage() {
  const [exams, setExams] = useState<Exam[]>([]);
  const [title, setTitle] = useState("");
  const [level, setLevel] = useState("");
  const [session, setSession] = useState("");
  const [search, setSearch] = useState("");
  const [creating, setCreating] = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<"all" | string>("all");

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
      setShowCreate(false);
      await refresh();
    } catch (e: any) {
      setError(e?.message ?? "Erreur lors de la création");
    } finally {
      setCreating(false);
    }
  }

  const levels = [...new Set(exams.map(e => e.level).filter(Boolean))] as string[];

  const filtered = exams.filter((e) => {
    const matchSearch = !search.trim() ||
      e.title.toLowerCase().includes(search.toLowerCase()) ||
      (e.level ?? "").toLowerCase().includes(search.toLowerCase()) ||
      (e.session ?? "").toLowerCase().includes(search.toLowerCase());
    const matchFilter = filter === "all" || e.level === filter;
    return matchSearch && matchFilter;
  });

  return (
    <div className="space-y-6">

      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 tracking-tight">Examens</h1>
          <p className="mt-1 text-sm text-gray-500">{exams.length} examen{exams.length !== 1 ? "s" : ""} au total</p>
        </div>
        <button onClick={() => setShowCreate(true)} className="btn-primary">
          <Plus className="h-4 w-4" /> Nouvel examen
        </button>
      </div>

      {error && (
        <div className="flex items-start gap-3 rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
          <div>
            <p className="font-medium">Erreur</p>
            <p className="mt-0.5 text-rose-600">{error}</p>
          </div>
        </div>
      )}

      {/* Create form */}
      {showCreate && (
        <div className="card p-6 border-indigo-200 shadow-glow-sm animate-scale-in">
          <div className="mb-4 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500 to-violet-600 text-white shadow-sm">
                <Plus className="h-5 w-5" />
              </div>
              <div>
                <h2 className="text-base font-semibold text-gray-900">Nouvel examen</h2>
                <p className="text-xs text-gray-500">Renseignez les informations de base</p>
              </div>
            </div>
            <button onClick={() => setShowCreate(false)} className="rounded-lg p-2 text-gray-400 hover:bg-gray-100 hover:text-gray-600 transition-colors">
              ✕
            </button>
          </div>
          <form onSubmit={create} className="space-y-4">
            <div className="grid gap-3 sm:grid-cols-3">
              <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Titre de l'examen *" required className="input" autoFocus />
              <input value={level} onChange={(e) => setLevel(e.target.value)} placeholder="Niveau (ex. Terminale S)" className="input" />
              <input value={session} onChange={(e) => setSession(e.target.value)} placeholder="Session (ex. Juin 2025)" className="input" />
            </div>
            <div className="flex items-center gap-3">
              <button type="submit" disabled={creating || !title.trim()} className="btn-primary">
                {creating ? <><Loader2 className="h-4 w-4 animate-spin" /> Création…</> : <><Plus className="h-4 w-4" /> Créer</>}
              </button>
              <button type="button" onClick={() => setShowCreate(false)} className="btn-ghost">Annuler</button>
            </div>
          </form>
        </div>
      )}

      {/* Filters + Search */}
      {exams.length > 0 && (
        <div className="flex flex-wrap items-center gap-3">
          <div className="relative flex-1 min-w-[200px] max-w-md">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Rechercher un examen…"
              className="input pl-10"
            />
          </div>
          <div className="flex items-center gap-1.5 rounded-lg border border-gray-200 bg-white p-1">
            <button
              onClick={() => setFilter("all")}
              className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${filter === "all" ? "bg-indigo-50 text-indigo-700" : "text-gray-600 hover:bg-gray-50"}`}
            >
              Tous
            </button>
            {levels.slice(0, 4).map(lvl => (
              <button
                key={lvl}
                onClick={() => setFilter(lvl)}
                className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${filter === lvl ? "bg-indigo-50 text-indigo-700" : "text-gray-600 hover:bg-gray-50"}`}
              >
                {lvl}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Table */}
      {filtered.length === 0 ? (
        <div className="card p-12 text-center">
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-gray-100">
            <BookOpen className="h-7 w-7 text-gray-400" />
          </div>
          <h3 className="mt-4 text-base font-semibold text-gray-900">
            {search ? "Aucun résultat" : "Aucun examen"}
          </h3>
          <p className="mt-1 text-sm text-gray-500">
            {search ? "Essayez avec d'autres mots-clés" : "Créez votre premier examen pour commencer"}
          </p>
          {!search && (
            <button onClick={() => setShowCreate(true)} className="btn-primary mt-4">
              <Plus className="h-4 w-4" /> Créer un examen
            </button>
          )}
        </div>
      ) : (
        <div className="card overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="table-header">
                <th className="px-6 py-3 text-left">Examen</th>
                <th className="px-4 py-3 text-left">Niveau</th>
                <th className="px-4 py-3 text-left">Session</th>
                <th className="px-4 py-3 text-right">Points max</th>
                <th className="px-4 py-3 text-left">Créé</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((exam) => (
                <tr key={exam.id} className="table-row group">
                  <td className="px-6 py-4">
                    <Link href={`/exams/${exam.id}`} className="font-semibold text-gray-900 hover:text-indigo-600 transition-colors">
                      {exam.title}
                    </Link>
                  </td>
                  <td className="px-4 py-4">
                    {exam.level ? (
                      <span className="badge bg-indigo-50 text-indigo-600">{exam.level}</span>
                    ) : (
                      <span className="text-gray-400 text-sm">—</span>
                    )}
                  </td>
                  <td className="px-4 py-4 text-sm text-gray-600">{exam.session ?? "—"}</td>
                  <td className="px-4 py-4 text-right text-sm font-medium text-gray-700">{exam.total_points}</td>
                  <td className="px-4 py-4 text-sm text-gray-500">{formatRelative(exam.created_at)}</td>
                  <td className="px-4 py-4 text-right">
                    <Link href={`/exams/${exam.id}`} className="rounded-lg p-2 text-gray-400 hover:bg-indigo-50 hover:text-indigo-600 transition-colors inline-flex">
                      <ChevronRight className="h-4 w-4" />
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

