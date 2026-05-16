"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { apiGet, apiPostJson } from "@/lib/api";
import type { CopyPage, IntegrationsStatus, StudentCopy } from "@/lib/types";
import { StatusBadge } from "@/components/StatusBadge";
import { PageViewer } from "@/components/PageViewer";

export default function CopyDetailPage() {
  const params = useParams();
  const id = params.id as string;
  const copyId = useMemo(() => id, [id]);

  const [copy, setCopy] = useState<StudentCopy | null>(null);
  const [pages, setPages] = useState<CopyPage[]>([]);
  const [status, setStatus] = useState<any>(null);
  const [integrations, setIntegrations] = useState<IntegrationsStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [processing, setProcessing] = useState(false);

  async function refreshAll() {
    const [c, p, s] = await Promise.all([
      apiGet<StudentCopy>(`/copies/${copyId}`),
      apiGet<CopyPage[]>(`/copies/${copyId}/pages`),
      apiGet<any>(`/copies/${copyId}/status`)
    ]);
    setCopy(c);
    setPages(p);
    setStatus(s);
  }

  useEffect(() => {
    refreshAll().catch((e) => setError(e?.message ?? "Failed to load"));
    const t = setInterval(() => refreshAll().catch(() => {}), 2000);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [copyId]);

  useEffect(() => {
    apiGet<IntegrationsStatus>("/integrations/status")
      .then(setIntegrations)
      .catch(() => setIntegrations(null));
  }, []);

  async function launch() {
    setProcessing(true);
    setError(null);
    try {
      await apiPostJson(`/copies/${copyId}/process`, {});
      await refreshAll();
    } catch (e: any) {
      setError(e?.message ?? "Failed to launch processing");
    } finally {
      setProcessing(false);
    }
  }

  if (!copy) return <div className="text-sm text-slate-600">Chargement...</div>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">Copie</h1>
          <div className="text-sm text-slate-600">
            {copy.student_name ?? "Élève (non renseigné)"} · <StatusBadge status={copy.status} />
          </div>
        </div>
        <Link href={`/exams/${copy.exam_id}`} className="text-sm text-slate-700 hover:text-slate-900">
          ← Retour examen
        </Link>
      </div>

      {error ? <div className="rounded border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">{error}</div> : null}

      <div className="rounded border bg-white p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="text-sm">
            <div className="font-medium">Statut</div>
            <div className="text-slate-600">{status ? `${status.status} (${status.task_state ?? "n/a"})` : "—"}</div>
            {copy.error_message ? <div className="mt-1 text-rose-700">{copy.error_message}</div> : null}
            {integrations ? (
              <div className="mt-2 text-xs text-slate-600">
                Intégrations · Mathpix: {integrations.mathpix.configured ? "ok" : "off"} · Azure:{" "}
                {integrations.azure_document_intelligence.configured ? "ok" : "off"} · OpenAI: {integrations.openai.configured ? "ok" : "off"}
              </div>
            ) : (
              <div className="mt-2 text-xs text-slate-500">Intégrations: n/a</div>
            )}
          </div>
          <button
            onClick={launch}
            disabled={processing}
            className="rounded bg-slate-900 px-4 py-2 text-sm text-white disabled:opacity-50"
          >
            {processing ? "Lancement..." : "Lancer traitement"}
          </button>
        </div>
      </div>

      <PageViewer pages={pages} />

      <div className="rounded border bg-white p-4">
        <div className="mb-2 text-sm font-medium">Correction JSON (MVP)</div>
        <pre className="overflow-auto rounded bg-slate-950 p-3 text-xs text-slate-100">
          {JSON.stringify({ copy_id: copy.id, corrections: [] }, null, 2)}
        </pre>
        <div className="mt-2 text-xs text-slate-500">La correction IA complète est en phase 2.</div>
      </div>
    </div>
  );
}
