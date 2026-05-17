"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { BookOpen, FileStack, Plus, ArrowRight, Loader2, AlertCircle, Sparkles } from "lucide-react";
import { apiGet, apiPostJson } from "@/lib/api";
import { ExamCard } from "@/components/ExamCard";
import type { Exam, StudentCopy } from "@/lib/types";

export default function Dashboard() {
  const [exams, setExams] = useState<Exam[]>([]);
  const [copies, setCopies] = useState<StudentCopy[]>([]);
  const [title, setTitle] = useState("");
  const [level, setLevel] = useState("");
  const [session, setSession] = useState("");
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    const [e, c] = await Promise.all([apiGet<Exam[]>("/exams"), apiGet<StudentCopy[]>("/copies")]);
    setExams(e);
    setCopies(c);
  }

  useEffect(() => {
    refresh().catch((e) => setError(e?.message ?? "Impossible de charger les données"));
  }, []);

  async function createExam(e: React.FormEvent) {
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

  const correctedCount = copies.filter((c) => c.status === "corrected").length;

  return (
    <div className="space-y-8 animate-slide-up">

      {/* Hero */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-indigo-600 to-indigo-700 px-8 py-10 text-white shadow-lg">
        <div className="absolute -right-10 -top-10 h-48 w-48 rounded-full bg-white/5" />
        <div className="absolute -bottom-6 -left-6 h-32 w-32 rounded-full bg-white/5" />
        <div className="relative">
          <div className="mb-1 flex items-center gap-2 text-indigo-200 text-sm font-medium">
            <Sparkles className="h-4 w-4" /> Plateforme de correction IA
          </div>
          <h1 className="text-3xl font-bold tracking-tight">Tableau de bord</h1>
          <p className="mt-2 text-indigo-200 max-w-lg">
            Gérez vos examens, uploadez les copies et lancez la correction automatique par intelligence artificielle.
          </p>
          <Link
            href="/exams"
            className="mt-5 inline-flex items-center gap-2 rounded-lg bg-white px-4 py-2 text-sm font-semibold text-indigo-700 shadow hover:bg-indigo-50 transition-colors"
          >
            Voir tous les examens <ArrowRight className="h-4 w-4" />
          </Link>
        </div>
      </div>

      {error && (
        <div className="flex items-start gap-2 rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
          {error}
        </div>
      )}

      {/* Stats */}
      <div className="grid gap-4 sm:grid-cols-3">
        {[
          { icon: BookOpen,   label: "Examens",           value: exams.length,      href: "/exams",  color: "bg-indigo-50 text-indigo-600" },
          { icon: FileStack,  label: "Copies uploadées",  value: copies.length,     href: "/exams",  color: "bg-sky-50 text-sky-600" },
          { icon: Sparkles,   label: "Copies corrigées",  value: correctedCount,    href: "/exams",  color: "bg-emerald-50 text-emerald-600" },
        ].map((s) => (
          <Link
            key={s.label}
            href={s.href}
            className="group flex items-center gap-4 rounded-xl border border-slate-200 bg-white p-5 shadow-card hover:shadow-card-hover hover:border-indigo-200 transition-all"
          >
            <div className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-xl ${s.color}`}>
              <s.icon className="h-5 w-5" />
            </div>
            <div>
              <div className="text-3xl font-bold text-slate-900">{s.value}</div>
              <div className="text-sm text-slate-500">{s.label}</div>
            </div>
          </Link>
        ))}
      </div>

      {/* Quick create */}
      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-card">
        <div className="mb-4 flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-50 text-indigo-600">
            <Plus className="h-4 w-4" />
          </div>
          <h2 className="text-base font-semibold text-slate-800">Créer un examen</h2>
        </div>
        <form onSubmit={createExam} className="space-y-3">
          <div className="grid gap-3 sm:grid-cols-3">
            <input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Titre de l'examen *"
              required
              className="input sm:col-span-1"
            />
            <input
              value={level}
              onChange={(e) => setLevel(e.target.value)}
              placeholder="Niveau (ex. Terminale)"
              className="input"
            />
            <input
              value={session}
              onChange={(e) => setSession(e.target.value)}
              placeholder="Session (ex. Juin 2025)"
              className="input"
            />
          </div>
          <div className="flex items-center gap-3">
            <button
              type="submit"
              disabled={creating || !title.trim()}
              className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-5 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {creating ? <><Loader2 className="h-3.5 w-3.5 animate-spin" /> Création…</> : <><Plus className="h-3.5 w-3.5" /> Créer</>}
            </button>
            <Link
              href="/exams"
              className="text-sm text-indigo-600 hover:text-indigo-700 hover:underline underline-offset-2"
            >
              Voir tous les examens →
            </Link>
          </div>
        </form>
      </div>

      {/* Recent exams */}
      {exams.length > 0 && (
        <div>
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-base font-semibold text-slate-800">Examens récents</h2>
            <Link href="/exams" className="text-sm text-indigo-600 hover:underline underline-offset-2">
              Tout voir →
            </Link>
          </div>
          <div className="grid gap-3">
            {exams.slice(0, 5).map((e) => (
              <ExamCard key={e.id} exam={e} />
            ))}
          </div>
        </div>
      )}

    </div>
  );
}

