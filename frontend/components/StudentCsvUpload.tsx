"use client";

import { useRef, useState } from "react";
import { Users, Loader2, CheckCircle2, Download, AlertCircle } from "lucide-react";
import { apiPostForm } from "@/lib/api";

interface ImportResult {
  created: number;
  skipped: number;
  errors: { row: number; message: string }[];
}

interface Props {
  examId: string;
  onImported?: (result: ImportResult) => void;
}

export function StudentCsvUpload({ examId, onImported }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ImportResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setLoading(true);
    setResult(null);
    setError(null);
    try {
      const form = new FormData();
      form.append("file", file);
      const res = await apiPostForm<ImportResult>(`/exams/${examId}/students/csv`, form);
      setResult(res);
      onImported?.(res);
    } catch (err: any) {
      setError(err?.message ?? "Erreur lors de l'import CSV");
    } finally {
      setLoading(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  function downloadTemplate() {
    const csv = "student_name,copy_code\nDupont Marie,A01\nMartin Paul,A02\n";
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
    a.download = "eleves_exemple.csv";
    a.click();
  }

  return (
    <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 p-5">
      <div className="mb-3 flex items-center gap-2">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-50 text-indigo-600">
          <Users className="h-4 w-4" />
        </div>
        <div>
          <div className="text-sm font-medium text-slate-800">Importer une liste d&apos;élèves (CSV)</div>
          <div className="text-xs text-slate-500">
            Colonnes&nbsp;:{" "}
            <code className="rounded bg-slate-200 px-1 text-slate-600">student_name</code>{" "}
            ou <code className="rounded bg-slate-200 px-1 text-slate-600">nom</code>,
            optionnel&nbsp;: <code className="rounded bg-slate-200 px-1 text-slate-600">copy_code</code>.
            UTF-8 ou Latin-1.
          </div>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <label className={`inline-flex cursor-pointer items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-colors ${
          loading
            ? "bg-slate-200 text-slate-500 cursor-not-allowed"
            : "bg-indigo-600 text-white hover:bg-indigo-700 shadow-sm"
        }`}>
          {loading
            ? <><Loader2 className="h-3.5 w-3.5 animate-spin" /> Import en cours…</>
            : <><Users className="h-3.5 w-3.5" /> Choisir un fichier CSV</>}
          <input
            ref={inputRef}
            type="file"
            accept=".csv,text/csv,text/plain"
            className="sr-only"
            disabled={loading}
            onChange={handleFile}
          />
        </label>

        <button
          type="button"
          onClick={downloadTemplate}
          className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs text-slate-600 hover:bg-slate-50 transition-colors shadow-sm"
        >
          <Download className="h-3 w-3" /> Modèle CSV
        </button>
      </div>

      {error && (
        <div className="mt-3 flex items-start gap-2 rounded-lg bg-rose-50 border border-rose-200 px-3 py-2 text-xs text-rose-700">
          <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          {error}
        </div>
      )}

      {result && (
        <div className="mt-3 rounded-lg bg-emerald-50 border border-emerald-200 px-4 py-3 text-xs">
          <div className="flex items-center gap-2 font-semibold text-emerald-800">
            <CheckCircle2 className="h-3.5 w-3.5" /> Import terminé
          </div>
          <div className="mt-1 space-y-0.5 text-emerald-700">
            <div>{result.created} élève(s) créé(s)</div>
            {result.skipped > 0 && <div className="text-slate-500">{result.skipped} ligne(s) ignorée(s)</div>}
          </div>
          {result.errors.length > 0 && (
            <ul className="mt-2 space-y-0.5 text-rose-700">
              {result.errors.map((e, i) => (
                <li key={i} className="flex items-start gap-1">
                  <span className="shrink-0">Ligne {e.row} :</span> {e.message}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
