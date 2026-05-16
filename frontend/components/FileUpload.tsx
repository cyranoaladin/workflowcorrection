"use client";

import { useRef, useState } from "react";

export function FileUpload({
  label,
  accept,
  onUpload
}: {
  label: string;
  accept?: string;
  onUpload: (file: File) => Promise<void>;
}) {
  const ref = useRef<HTMLInputElement>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handle() {
    setError(null);
    const file = ref.current?.files?.[0];
    if (!file) return;
    setLoading(true);
    try {
      await onUpload(file);
    } catch (e: any) {
      setError(e?.message ?? "Upload failed");
    } finally {
      setLoading(false);
      if (ref.current) ref.current.value = "";
    }
  }

  return (
    <div className="rounded border bg-white p-4">
      <div className="mb-2 text-sm font-medium">{label}</div>
      <div className="flex flex-wrap items-center gap-2">
        <input ref={ref} type="file" accept={accept} className="text-sm" />
        <button
          onClick={handle}
          disabled={loading}
          className="rounded bg-slate-900 px-3 py-1.5 text-sm text-white disabled:opacity-50"
        >
          {loading ? "Upload..." : "Upload"}
        </button>
      </div>
      {error ? <div className="mt-2 text-sm text-rose-700">{error}</div> : null}
    </div>
  );
}

