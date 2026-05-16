"use client";

import { useEffect, useMemo, useState } from "react";
import type { CopyPage, Transcription } from "@/lib/types";
import { apiGet, apiPostJson, getApiBaseUrl, apiFetchBlob } from "@/lib/api";

export function PageViewer({ pages }: { pages: CopyPage[] }) {
  const [mode, setMode] = useState<"original" | "processed">("processed");
  const base = useMemo(() => getApiBaseUrl(), []);
  const [transcriptions, setTranscriptions] = useState<Record<string, Transcription[]>>({});
  const [busy, setBusy] = useState<Record<string, string | null>>({});
  const [error, setError] = useState<Record<string, string | null>>({});
  const [blobUrls, setBlobUrls] = useState<Record<string, string>>({});

  function formatErr(e: any): string {
    if (!e) return "Unknown error";
    if (typeof e === "string") return e;
    const details = typeof e.details === "string" ? e.details : JSON.stringify(e.details ?? "");
    return `${e.message ?? "Request failed"}${details ? `: ${details}` : ""}`;
  }

  async function refreshPage(pageId: string) {
    const list = await apiGet<Transcription[]>(`/pages/${pageId}/transcriptions`);
    setTranscriptions((prev) => ({ ...prev, [pageId]: list }));
  }

  useEffect(() => {
    if (!base || pages.length === 0) return;
    Promise.all(pages.map((p) => refreshPage(p.id))).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pages.map((p) => p.id).join(",")]);

  const pageIds = pages.map((p) => p.id).join(",");
  useEffect(() => {
    if (!base || pages.length === 0) return;
    setBlobUrls({});
    const prev: Record<string, string> = {};
    let cancelled = false;
    Promise.all(
      pages.map(async (p) => {
        try {
          const blob = await apiFetchBlob(`/pages/${p.id}/image?type=${mode}`);
          if (!cancelled) {
            const url = URL.createObjectURL(blob);
            prev[p.id] = url;
          }
        } catch {
          // silently ignore — image will show placeholder
        }
      })
    ).then(() => {
      if (!cancelled) setBlobUrls({ ...prev });
    });
    return () => {
      cancelled = true;
      Object.values(prev).forEach((u) => URL.revokeObjectURL(u));
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pageIds, mode, base]);

  if (!base) {
    return (
      <div className="rounded border bg-white p-4 text-sm text-rose-700">
        NEXT_PUBLIC_API_BASE_URL is not set. Configure `frontend/.env.local` before using the viewer.
      </div>
    );
  }

  if (pages.length === 0) {
    return <div className="rounded border bg-white p-4 text-sm text-slate-600">Aucune page générée.</div>;
  }

  async function run(pageId: string, action: "mathpix" | "azure" | "openai-vision" | "fuse") {
    setBusy((prev) => ({ ...prev, [pageId]: action }));
    setError((prev) => ({ ...prev, [pageId]: null }));
    try {
      const qs = action === "fuse" ? "" : `?image_type=${mode}&confirm_paid_call=true`;
      const path =
        action === "mathpix"
          ? `/pages/${pageId}/ocr/mathpix${qs}`
          : action === "azure"
            ? `/pages/${pageId}/ocr/azure${qs}`
            : action === "openai-vision"
              ? `/pages/${pageId}/ocr/openai-vision${qs}`
              : `/pages/${pageId}/ocr/fuse`;
      await apiPostJson(path, {});
      await refreshPage(pageId);
    } catch (e: any) {
      setError((prev) => ({ ...prev, [pageId]: formatErr(e) }));
    } finally {
      setBusy((prev) => ({ ...prev, [pageId]: null }));
    }
  }

  return (
    <div className="rounded border bg-white p-4">
      <div className="mb-3 flex items-center justify-between">
        <div className="text-sm font-medium">Pages</div>
        <div className="flex gap-2">
          <button
            className={`rounded px-3 py-1 text-sm ${mode === "original" ? "bg-slate-900 text-white" : "bg-slate-100"}`}
            onClick={() => setMode("original")}
          >
            Original
          </button>
          <button
            className={`rounded px-3 py-1 text-sm ${mode === "processed" ? "bg-slate-900 text-white" : "bg-slate-100"}`}
            onClick={() => setMode("processed")}
          >
            Processed
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4">
        {pages.map((p) => (
          <div key={p.id} className="rounded border p-3">
            <div className="mb-2 text-xs text-slate-600">Page {p.page_number}</div>
            {blobUrls[p.id] ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={blobUrls[p.id]}
                alt={`Page ${p.page_number} (${mode})`}
                className="w-full rounded"
              />
            ) : (
              <div className="flex h-32 items-center justify-center rounded bg-slate-100 text-xs text-slate-500">
                Chargement image...
              </div>
            )}

            <div className="mt-3 flex flex-wrap gap-2">
              <button
                onClick={() => run(p.id, "mathpix")}
                disabled={busy[p.id] !== null && busy[p.id] !== undefined}
                className="rounded bg-slate-900 px-3 py-1 text-xs text-white disabled:opacity-50"
              >
                {busy[p.id] === "mathpix" ? "OCR Mathpix..." : "OCR Mathpix page"}
              </button>
              <button
                onClick={() => run(p.id, "azure")}
                disabled={busy[p.id] !== null && busy[p.id] !== undefined}
                className="rounded bg-slate-900 px-3 py-1 text-xs text-white disabled:opacity-50"
              >
                {busy[p.id] === "azure" ? "OCR Azure..." : "OCR Azure page"}
              </button>
              <button
                onClick={() => run(p.id, "openai-vision")}
                disabled={busy[p.id] !== null && busy[p.id] !== undefined}
                className="rounded bg-slate-900 px-3 py-1 text-xs text-white disabled:opacity-50"
              >
                {busy[p.id] === "openai-vision" ? "OCR OpenAI..." : "OCR OpenAI Vision page"}
              </button>
              <button
                onClick={() => run(p.id, "fuse")}
                disabled={busy[p.id] !== null && busy[p.id] !== undefined}
                className="rounded bg-slate-100 px-3 py-1 text-xs text-slate-900 disabled:opacity-50"
              >
                {busy[p.id] === "fuse" ? "Fusion..." : "Fusion OCR page"}
              </button>
            </div>

            {error[p.id] ? (
              <div className="mt-2 rounded border border-rose-200 bg-rose-50 p-2 text-xs text-rose-800">{error[p.id]}</div>
            ) : null}

            <div className="mt-3 space-y-2">
              {(transcriptions[p.id] ?? []).length === 0 ? (
                <div className="text-xs text-slate-500">Aucune transcription OCR pour cette page.</div>
              ) : (
                (transcriptions[p.id] ?? []).slice(0, 6).map((t) => (
                  <div key={t.id} className="rounded border bg-slate-50 p-2">
                    <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
                      <div className="font-medium">
                        {t.source ?? "unknown"} · conf: {t.confidence ?? "n/a"} · review: {t.needs_human_review ? "yes" : "no"}
                      </div>
                      <div className="text-slate-500">{new Date(t.created_at).toLocaleString()}</div>
                    </div>
                    {t.error_message ? <div className="mt-1 text-xs text-rose-700">{t.error_message}</div> : null}
                    {t.final_text ? (
                      <pre className="mt-2 max-h-40 overflow-auto whitespace-pre-wrap rounded bg-white p-2 text-xs text-slate-900">
                        {t.final_text}
                      </pre>
                    ) : null}
                    {t.final_latex ? (
                      <pre className="mt-2 max-h-32 overflow-auto whitespace-pre-wrap rounded bg-white p-2 text-xs text-slate-900">
                        {t.final_latex}
                      </pre>
                    ) : null}
                  </div>
                ))
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
