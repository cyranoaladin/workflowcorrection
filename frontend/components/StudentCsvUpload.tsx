"use client";

import { useRef, useState } from "react";
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

  return (
    <div className="rounded border border-dashed border-slate-300 bg-slate-50 p-4">
      <p className="mb-2 text-sm font-medium text-slate-700">
        Importer une liste d&apos;élèves (CSV)
      </p>
      <p className="mb-3 text-xs text-slate-500">
        Colonnes attendues :{" "}
        <code className="rounded bg-slate-200 px-1">student_name</code> (ou{" "}
        <code className="rounded bg-slate-200 px-1">nom</code>) et optionnellement{" "}
        <code className="rounded bg-slate-200 px-1">copy_code</code> (ou{" "}
        <code className="rounded bg-slate-200 px-1">code</code>).
        Encodage UTF-8 ou Latin-1.
      </p>

      <label className="inline-block cursor-pointer rounded bg-slate-800 px-3 py-1.5 text-xs font-medium text-white hover:bg-slate-700 disabled:opacity-50">
        {loading ? "Import en cours..." : "Choisir un fichier CSV"}
        <input
          ref={inputRef}
          type="file"
          accept=".csv,text/csv,text/plain"
          className="hidden"
          disabled={loading}
          onChange={handleFile}
        />
      </label>

      {error && (
        <p className="mt-3 rounded bg-rose-50 px-3 py-2 text-xs text-rose-700">
          {error}
        </p>
      )}

      {result && (
        <div className="mt-3 rounded bg-emerald-50 px-3 py-2 text-xs text-emerald-800">
          <p className="font-semibold">Import terminé</p>
          <p>✓ {result.created} élève(s) créé(s)</p>
          {result.skipped > 0 && <p>⊘ {result.skipped} ligne(s) ignorée(s) (vides)</p>}
          {result.errors.length > 0 && (
            <ul className="mt-1 list-disc pl-4 text-rose-700">
              {result.errors.map((e, i) => (
                <li key={i}>Ligne {e.row} : {e.message}</li>
              ))}
            </ul>
          )}
        </div>
      )}

      <p className="mt-3 text-xs text-slate-400">
        Exemple de fichier :{" "}
        <button
          type="button"
          onClick={() => {
            const csv = "student_name,copy_code\nDupont Marie,A01\nMartin Paul,A02\n";
            const a = document.createElement("a");
            a.href = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
            a.download = "eleves_exemple.csv";
            a.click();
          }}
          className="underline hover:text-slate-600"
        >
          télécharger le modèle
        </button>
      </p>
    </div>
  );
}
