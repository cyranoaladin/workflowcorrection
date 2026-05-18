"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  BookOpen, FileStack, Plus, ArrowRight, Loader2, AlertCircle,
  Sparkles, Clock, TrendingUp, Zap, ChevronRight
} from "lucide-react";
import { apiGet, apiPostJson } from "@/lib/api";
import type { Exam, StudentCopy } from "@/lib/types";
import { formatRelative } from "@/lib/utils";

export default function Dashboard() {
  const [exams, setExams] = useState<Exam[]>([]);
  const [copies, setCopies] = useState<StudentCopy[]>([]);
  const [title, setTitle] = useState("");
  const [level, setLevel] = useState("");
  const [session, setSession] = useState("");
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);

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
      setShowCreate(false);
      await refresh();
    } catch (e: any) {
      setError(e?.message ?? "Erreur lors de la création");
    } finally {
      setCreating(false);
    }
  }

  const correctedCount = copies.filter((c) => c.status === "corrected").length;
  const processingCount = copies.filter((c) => ["processing", "ocr_pending"].includes(c.status)).length;
  const avgScore = copies.filter(c => c.total_score).length > 0
    ? (copies.filter(c => c.total_score).reduce((acc, c) => acc + parseFloat(c.total_score || "0"), 0) / copies.filter(c => c.total_score).length).toFixed(1)
    : null;

  return (
    <div className="space-y-8">

      {/* Welcome header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 tracking-tight">Tableau de bord</h1>
          <p className="mt-1 text-sm text-gray-500">
            Vue d&apos;ensemble de votre activité de correction
          </p>
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="btn-primary"
        >
          <Plus className="h-4 w-4" /> Nouvel examen
        </button>
      </div>

      {error && (
        <div className="flex items-start gap-3 rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
          <div>
            <p className="font-medium">Erreur de chargement</p>
            <p className="mt-0.5 text-rose-600">{error}</p>
          </div>
        </div>
      )}

      {/* Stats grid */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="stat-card group">
          <div className="flex items-center justify-between">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-50 text-indigo-600 group-hover:bg-indigo-100 transition-colors">
              <BookOpen className="h-5 w-5" />
            </div>
            <span className="badge bg-indigo-50 text-indigo-600">{exams.length > 0 ? "+1 ce mois" : "—"}</span>
          </div>
          <div>
            <div className="text-3xl font-bold text-gray-900 animate-number-up">{exams.length}</div>
            <div className="text-sm text-gray-500">Examens créés</div>
          </div>
        </div>

        <div className="stat-card group">
          <div className="flex items-center justify-between">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-violet-50 text-violet-600 group-hover:bg-violet-100 transition-colors">
              <FileStack className="h-5 w-5" />
            </div>
            {processingCount > 0 && (
              <span className="badge bg-amber-50 text-amber-600">
                <Loader2 className="h-3 w-3 animate-spin" /> {processingCount} en cours
              </span>
            )}
          </div>
          <div>
            <div className="text-3xl font-bold text-gray-900 animate-number-up">{copies.length}</div>
            <div className="text-sm text-gray-500">Copies importées</div>
          </div>
        </div>

        <div className="stat-card group">
          <div className="flex items-center justify-between">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-50 text-emerald-600 group-hover:bg-emerald-100 transition-colors">
              <Sparkles className="h-5 w-5" />
            </div>
            <span className="badge bg-emerald-50 text-emerald-600">
              {copies.length > 0 ? `${Math.round(correctedCount / copies.length * 100)}%` : "—"}
            </span>
          </div>
          <div>
            <div className="text-3xl font-bold text-gray-900 animate-number-up">{correctedCount}</div>
            <div className="text-sm text-gray-500">Copies corrigées</div>
          </div>
        </div>

        <div className="stat-card group">
          <div className="flex items-center justify-between">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-sky-50 text-sky-600 group-hover:bg-sky-100 transition-colors">
              <TrendingUp className="h-5 w-5" />
            </div>
          </div>
          <div>
            <div className="text-3xl font-bold text-gray-900 animate-number-up">
              {avgScore ? `${avgScore}` : "—"}
            </div>
            <div className="text-sm text-gray-500">Score moyen</div>
          </div>
        </div>
      </div>

      {/* Time saved banner */}
      {correctedCount > 0 && (
        <div className="relative overflow-hidden rounded-2xl bg-gradient-to-r from-indigo-600 via-violet-600 to-purple-600 p-6 text-white">
          <div className="absolute -right-8 -top-8 h-40 w-40 rounded-full bg-white/5" />
          <div className="absolute -bottom-4 -left-4 h-24 w-24 rounded-full bg-white/5" />
          <div className="relative flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-white/10 backdrop-blur-sm">
                <Clock className="h-7 w-7" />
              </div>
              <div>
                <div className="text-sm font-medium text-white/80">Temps économisé estimé</div>
                <div className="text-3xl font-bold">{Math.round(correctedCount * 0.5)}h</div>
                <div className="text-sm text-white/70">~30 min par copie corrigée par IA</div>
              </div>
            </div>
            <div className="hidden sm:flex items-center gap-2 rounded-xl bg-white/10 backdrop-blur-sm px-4 py-2">
              <Zap className="h-5 w-5 text-yellow-300" />
              <div className="text-sm">
                <div className="font-semibold">{correctedCount} corrections IA</div>
                <div className="text-white/70 text-xs">complétées avec succès</div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Quick create modal */}
      {showCreate && (
        <div className="card p-6 border-indigo-200 shadow-glow-sm animate-scale-in">
          <div className="mb-4 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500 to-violet-600 text-white shadow-sm">
                <Plus className="h-5 w-5" />
              </div>
              <div>
                <h2 className="text-base font-semibold text-gray-900">Créer un nouvel examen</h2>
                <p className="text-xs text-gray-500">Renseignez les informations de base</p>
              </div>
            </div>
            <button
              onClick={() => setShowCreate(false)}
              className="rounded-lg p-2 text-gray-400 hover:bg-gray-100 hover:text-gray-600 transition-colors"
            >
              ✕
            </button>
          </div>
          <form onSubmit={createExam} className="space-y-4">
            <div className="grid gap-3 sm:grid-cols-3">
              <input
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Titre de l'examen *"
                required
                className="input sm:col-span-1"
                autoFocus
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
            <div className="flex items-center gap-3">
              <button type="submit" disabled={creating || !title.trim()} className="btn-primary">
                {creating ? <><Loader2 className="h-4 w-4 animate-spin" /> Création…</> : <><Plus className="h-4 w-4" /> Créer l&apos;examen</>}
              </button>
              <button type="button" onClick={() => setShowCreate(false)} className="btn-ghost">
                Annuler
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Recent exams table */}
      {exams.length > 0 && (
        <div className="card overflow-hidden">
          <div className="flex items-center justify-between border-b border-gray-100 px-6 py-4">
            <div>
              <h2 className="text-base font-semibold text-gray-900">Examens récents</h2>
              <p className="text-xs text-gray-500 mt-0.5">{exams.length} examen{exams.length !== 1 ? "s" : ""} au total</p>
            </div>
            <Link href="/exams" className="btn-ghost btn-sm">
              Tout voir <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </div>
          <div className="divide-y divide-gray-50">
            {exams.slice(0, 6).map((exam, i) => {
              const examCopies = copies.filter(c => c.exam_id === exam.id);
              const examCorrected = examCopies.filter(c => c.status === "corrected").length;
              return (
                <Link
                  key={exam.id}
                  href={`/exams/${exam.id}`}
                  className="flex items-center gap-4 px-6 py-4 hover:bg-gray-50/80 transition-colors group"
                  style={{ animationDelay: `${i * 50}ms` }}
                >
                  <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gray-100 text-gray-500 group-hover:bg-indigo-50 group-hover:text-indigo-600 transition-colors">
                    <BookOpen className="h-4 w-4" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-gray-900 truncate">{exam.title}</span>
                      {exam.level && (
                        <span className="badge bg-indigo-50 text-indigo-600 shrink-0">{exam.level}</span>
                      )}
                    </div>
                    <div className="mt-0.5 flex items-center gap-3 text-xs text-gray-500">
                      <span>{formatRelative(exam.created_at)}</span>
                      <span>·</span>
                      <span>{examCopies.length} copie{examCopies.length !== 1 ? "s" : ""}</span>
                      {examCorrected > 0 && (
                        <>
                          <span>·</span>
                          <span className="text-emerald-600 font-medium">{examCorrected} corrigée{examCorrected !== 1 ? "s" : ""}</span>
                        </>
                      )}
                    </div>
                  </div>
                  {examCopies.length > 0 && (
                    <div className="hidden sm:flex items-center gap-2">
                      <div className="w-24 h-2 rounded-full bg-gray-100 overflow-hidden">
                        <div
                          className="h-full rounded-full bg-emerald-500 transition-all"
                          style={{ width: `${examCopies.length > 0 ? (examCorrected / examCopies.length * 100) : 0}%` }}
                        />
                      </div>
                      <span className="text-xs text-gray-500 w-8">{examCopies.length > 0 ? Math.round(examCorrected / examCopies.length * 100) : 0}%</span>
                    </div>
                  )}
                  <ChevronRight className="h-4 w-4 text-gray-300 group-hover:text-indigo-400 transition-colors" />
                </Link>
              );
            })}
          </div>
        </div>
      )}

      {/* Empty state */}
      {exams.length === 0 && !error && (
        <div className="card p-12 text-center">
          <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-indigo-50">
            <BookOpen className="h-8 w-8 text-indigo-500" />
          </div>
          <h3 className="mt-4 text-lg font-semibold text-gray-900">Aucun examen créé</h3>
          <p className="mt-2 text-sm text-gray-500 max-w-md mx-auto">
            Commencez par créer votre premier examen, importez le sujet et les copies, puis lancez la correction IA.
          </p>
          <button
            onClick={() => setShowCreate(true)}
            className="btn-primary mt-6"
          >
            <Plus className="h-4 w-4" /> Créer mon premier examen
          </button>
        </div>
      )}
    </div>
  );
}

