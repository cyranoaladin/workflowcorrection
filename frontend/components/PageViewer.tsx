"use client";

import { useEffect, useRef, useMemo, useState, useCallback } from "react";
import type { CopyPage, PageFull, Transcription } from "@/lib/types";
import { apiGet, apiPostJson, getApiBaseUrl, apiFetchBlob } from "@/lib/api";

export function PageViewer({ pages }: { pages: CopyPage[] }) {
  const [mode, setMode] = useState<"original" | "processed">("processed");
  const base = useMemo(() => getApiBaseUrl(), []);
  const [pagesFull, setPagesFull] = useState<PageFull[]>([]);
  const [transcriptions, setTranscriptions] = useState<Record<string, Transcription[]>>({});
  const [busy, setBusy] = useState<Record<string, string | null>>({});
  const [error, setError] = useState<Record<string, string | null>>({});
  const [blobUrls, setBlobUrls] = useState<Record<string, string>>({});

  const copyId = pages[0]?.copy_id;

  function formatErr(e: any): string {
    if (!e) return "Unknown error";
    if (typeof e === "string") return e;
    const details = typeof e.details === "string" ? e.details : JSON.stringify(e.details ?? "");
    return `${e.message ?? "Request failed"}${details ? `: ${details}` : ""}`;
  }

  // Batch load: 1 request for all pages + transcriptions
  useEffect(() => {
    if (!base || !copyId) return;
    apiGet<PageFull[]>(`/copies/${copyId}/pages-full`)
      .then((full) => {
        setPagesFull(full);
        const txMap: Record<string, Transcription[]> = {};
        for (const p of full) {
          txMap[p.id] = p.transcriptions;
        }
        setTranscriptions(txMap);
      })
      .catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [copyId, base]);

  // Refresh a single page's transcriptions (after OCR action)
  async function refreshPage(pageId: string) {
    const list = await apiGet<Transcription[]>(`/pages/${pageId}/transcriptions`);
    setTranscriptions((prev) => ({ ...prev, [pageId]: list }));
  }

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

  // Determine effective image type per page (use has_processed from batch)
  const effectiveType = (p: CopyPage) => {
    if (mode === "original") return "original";
    const full = pagesFull.find((pf) => pf.id === p.id);
    return full?.has_processed ? "processed" : "original";
  };

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
          <PageCard
            key={p.id}
            page={p}
            imageType={effectiveType(p)}
            transcriptions={transcriptions[p.id] ?? []}
            busy={busy[p.id]}
            error={error[p.id]}
            onAction={(action) => run(p.id, action)}
          />
        ))}
      </div>
    </div>
  );
}

/** Lazy-loaded page card — only loads image when visible in viewport */
function PageCard({
  page,
  imageType,
  transcriptions,
  busy,
  error,
  onAction,
}: {
  page: CopyPage;
  imageType: string;
  transcriptions: Transcription[];
  busy: string | null | undefined;
  error: string | null | undefined;
  onAction: (action: "mathpix" | "azure" | "openai-vision" | "fuse") => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(false);
  const [blobUrl, setBlobUrl] = useState<string | null>(null);

  // Intersection Observer for lazy loading
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      ([entry]) => { if (entry.isIntersecting) { setVisible(true); observer.disconnect(); } },
      { rootMargin: "200px" }
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  // Load image only when visible
  useEffect(() => {
    if (!visible) return;
    let cancelled = false;
    apiFetchBlob(`/pages/${page.id}/image?type=${imageType}`)
      .then((blob) => {
        if (!cancelled) setBlobUrl(URL.createObjectURL(blob));
      })
      .catch(() => {});
    return () => {
      cancelled = true;
      if (blobUrl) URL.revokeObjectURL(blobUrl);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [visible, page.id, imageType]);

  return (
    <div ref={ref} className="rounded border p-3">
      <div className="mb-2 text-xs text-slate-600">Page {page.page_number}</div>
      {blobUrl ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={blobUrl} alt={`Page ${page.page_number}`} className="w-full rounded" />
      ) : (
        <div className="flex h-32 items-center justify-center rounded bg-slate-100 text-xs text-slate-500">
          {visible ? "Chargement image..." : ""}
        </div>
      )}

      <div className="mt-3 flex flex-wrap gap-2">
        <button onClick={() => onAction("mathpix")} disabled={!!busy} className="rounded bg-slate-900 px-3 py-1 text-xs text-white disabled:opacity-50">
          {busy === "mathpix" ? "OCR Mathpix..." : "OCR Mathpix page"}
        </button>
        <button onClick={() => onAction("azure")} disabled={!!busy} className="rounded bg-slate-900 px-3 py-1 text-xs text-white disabled:opacity-50">
          {busy === "azure" ? "OCR Azure..." : "OCR Azure page"}
        </button>
        <button onClick={() => onAction("openai-vision")} disabled={!!busy} className="rounded bg-slate-900 px-3 py-1 text-xs text-white disabled:opacity-50">
          {busy === "openai-vision" ? "OCR OpenAI..." : "OCR OpenAI Vision page"}
        </button>
        <button onClick={() => onAction("fuse")} disabled={!!busy} className="rounded bg-slate-100 px-3 py-1 text-xs text-slate-900 disabled:opacity-50">
          {busy === "fuse" ? "Fusion..." : "Fusion OCR page"}
        </button>
      </div>

      {error ? (
        <div className="mt-2 rounded border border-rose-200 bg-rose-50 p-2 text-xs text-rose-800">{error}</div>
      ) : null}

      <div className="mt-3 space-y-2">
        {transcriptions.length === 0 ? (
          <div className="text-xs text-slate-500">Aucune transcription OCR pour cette page.</div>
        ) : (
          transcriptions.slice(0, 6).map((t) => (
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
  );
}
