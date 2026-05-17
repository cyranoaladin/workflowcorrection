"use client";

import { useRef, useState } from "react";
import { UploadCloud, CheckCircle2, Loader2 } from "lucide-react";

export function FileUpload({
  label,
  accept,
  onUpload,
}: {
  label: string;
  accept?: string;
  onUpload: (file: File) => Promise<void>;
}) {
  const ref = useRef<HTMLInputElement>(null);
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filename, setFilename] = useState<string | null>(null);

  async function handle() {
    setError(null);
    setDone(false);
    const file = ref.current?.files?.[0];
    if (!file) return;
    setFilename(file.name);
    setLoading(true);
    try {
      await onUpload(file);
      setDone(true);
      setTimeout(() => setDone(false), 3000);
    } catch (e: any) {
      setError(e?.message ?? "Upload échoué");
    } finally {
      setLoading(false);
      if (ref.current) ref.current.value = "";
    }
  }

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-card">
      <div className="mb-3 flex items-center gap-2">
        <UploadCloud className="h-4 w-4 text-slate-400" />
        <span className="text-sm font-medium text-slate-700">{label}</span>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <label className="flex-1 cursor-pointer rounded-lg border border-dashed border-slate-300 bg-slate-50 px-3 py-2 text-xs text-slate-500 hover:bg-slate-100 hover:border-slate-400 transition-colors">
          <input ref={ref} type="file" accept={accept} className="sr-only" onChange={handle} />
          {loading
            ? <span className="flex items-center gap-1.5"><Loader2 className="h-3 w-3 animate-spin" /> Upload en cours…</span>
            : done
            ? <span className="flex items-center gap-1.5 text-emerald-600"><CheckCircle2 className="h-3 w-3" /> {filename} uploadé</span>
            : <span>Choisir un fichier…</span>}
        </label>
      </div>
      {error && (
        <div className="mt-2 flex items-center gap-1.5 text-xs text-rose-600">
          <span className="h-1.5 w-1.5 rounded-full bg-rose-500" />
          {error}
        </div>
      )}
    </div>
  );
}

