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
  const token = process.env.NEXT_PUBLIC_ADMIN_API_TOKEN;
  return {
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
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
