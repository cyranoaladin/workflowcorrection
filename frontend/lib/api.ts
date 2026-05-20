export type ApiError = {
  status: number;
  message: string;
  details?: unknown;
};

export function getApiBaseUrl(): string {
  const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;
  if (!baseUrl) return "";
  return baseUrl.replace(/\/$/, "");
}

function getApiHeaders(extra?: HeadersInit): HeadersInit {
  // NEXT_PUBLIC_DEV_ADMIN_TOKEN is a development-only escape hatch for calling
  // the backend directly (without Caddy). It is intentionally ignored in
  // production builds: Caddy injects Authorization server-side via header_up.
  // Never set this variable in a production environment file.
  const devToken =
    process.env.NODE_ENV !== "production"
      ? process.env.NEXT_PUBLIC_DEV_ADMIN_TOKEN
      : undefined;
  return {
    ...(devToken ? { Authorization: `Bearer ${devToken}` } : {}),
    ...(extra ?? {})
  };
}

export async function apiGet<T>(path: string): Promise<T> {
  const base = getApiBaseUrl();
  if (!base) throw new Error("NEXT_PUBLIC_API_BASE_URL is not set");
  const url = `${base}${path}`;
  const res = await fetch(url, { cache: "no-store", headers: getApiHeaders() });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw { status: res.status, message: `GET ${path} failed`, details: text } satisfies ApiError;
  }
  return (await res.json()) as T;
}

export async function apiPostJson<T>(path: string, body: unknown): Promise<T> {
  const base = getApiBaseUrl();
  if (!base) throw new Error("NEXT_PUBLIC_API_BASE_URL is not set");
  const url = `${base}${path}`;
  const res = await fetch(url, {
    method: "POST",
    headers: getApiHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify(body)
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw { status: res.status, message: `POST ${path} failed`, details: text } satisfies ApiError;
  }
  return (await res.json()) as T;
}

export async function apiPost<T>(path: string): Promise<T> {
  const base = getApiBaseUrl();
  if (!base) throw new Error("NEXT_PUBLIC_API_BASE_URL is not set");
  const url = `${base}${path}`;
  const res = await fetch(url, { method: "POST", headers: getApiHeaders() });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw { status: res.status, message: `POST ${path} failed`, details: text } satisfies ApiError;
  }
  return (await res.json()) as T;
}

export async function apiPostForm<T>(path: string, form: FormData): Promise<T> {
  const base = getApiBaseUrl();
  if (!base) throw new Error("NEXT_PUBLIC_API_BASE_URL is not set");
  const url = `${base}${path}`;
  const res = await fetch(url, { method: "POST", headers: getApiHeaders(), body: form });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw { status: res.status, message: `POST ${path} failed`, details: text } satisfies ApiError;
  }
  return (await res.json()) as T;
}

export async function apiPatch<T>(path: string, params?: Record<string, string | number>): Promise<T> {
  const base = getApiBaseUrl();
  if (!base) throw new Error("NEXT_PUBLIC_API_BASE_URL is not set");
  const url = new URL(`${base}${path}`);
  if (params) Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, String(v)));
  const res = await fetch(url.toString(), { method: "PATCH", headers: getApiHeaders() });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw { status: res.status, message: `PATCH ${path} failed`, details: text } satisfies ApiError;
  }
  return (await res.json()) as T;
}

export async function apiFetchBlob(path: string): Promise<Blob> {
  const base = getApiBaseUrl();
  if (!base) throw new Error("NEXT_PUBLIC_API_BASE_URL is not set");
  const url = `${base}${path}`;
  const res = await fetch(url, { cache: "no-store", headers: getApiHeaders() });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw { status: res.status, message: `GET ${path} failed`, details: text } satisfies ApiError;
  }
  return res.blob();
}
