"use client";

/**
 * Thin typed fetch wrapper (ADR 0003). All computed values (scores, bands)
 * come from the API — this layer never recomputes anything, it only shapes
 * requests/responses.
 */

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

import type { MockLoginResponse } from "@/lib/types";

const SESSION_STORAGE_KEY = "risk_platform_session";

export type Session = MockLoginResponse;

export function getSession(): Session | null {
  if (typeof window === "undefined") return null;
  const raw = window.localStorage.getItem(SESSION_STORAGE_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as Session;
  } catch {
    return null;
  }
}

export function setSession(session: Session): void {
  window.localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(session));
}

export function clearSession(): void {
  window.localStorage.removeItem(SESSION_STORAGE_KEY);
}

function getToken(): string | null {
  return getSession()?.access_token ?? null;
}

export class ApiError extends Error {
  status: number;
  detail: unknown;

  constructor(status: number, detail: unknown) {
    super(typeof detail === "string" ? detail : JSON.stringify(detail));
    this.status = status;
    this.detail = detail;
  }
}

interface RequestOptions {
  method?: string;
  body?: unknown;
  isForm?: boolean;
  query?: Record<string, string | number | boolean | undefined>;
}

export async function apiFetch<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;
  if (!options.isForm) headers["Content-Type"] = "application/json";

  let url = `${API_BASE_URL}${path}`;
  if (options.query) {
    const params = new URLSearchParams();
    for (const [key, value] of Object.entries(options.query)) {
      if (value !== undefined) params.set(key, String(value));
    }
    const qs = params.toString();
    if (qs) url += `?${qs}`;
  }

  const response = await fetch(url, {
    method: options.method ?? "GET",
    headers,
    body: options.isForm
      ? (options.body as FormData)
      : options.body !== undefined
        ? JSON.stringify(options.body)
        : undefined,
  });

  if (!response.ok) {
    let detail: unknown;
    try {
      detail = await response.json();
    } catch {
      detail = await response.text();
    }
    throw new ApiError(response.status, (detail as { detail?: unknown })?.detail ?? detail);
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

/**
 * Downloads a bearer-authenticated file (a plain `<a href>` can't carry the
 * auth header) as a Blob, reading the server-supplied filename off
 * Content-Disposition so the browser save prompt matches the report type.
 */
export async function apiDownload(path: string): Promise<{ blob: Blob; filename: string }> {
  const token = getToken();
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const response = await fetch(`${API_BASE_URL}${path}`, { headers });
  if (!response.ok) {
    let detail: unknown;
    try {
      detail = await response.json();
    } catch {
      detail = await response.text();
    }
    throw new ApiError(response.status, (detail as { detail?: unknown })?.detail ?? detail);
  }

  const disposition = response.headers.get("content-disposition") ?? "";
  const match = disposition.match(/filename="?([^"]+)"?/);
  const filename = match ? match[1] : "report";
  const blob = await response.blob();
  return { blob, filename };
}

export function apiFetchWithHeaders<T>(
  path: string,
  options: RequestOptions = {},
): Promise<{ data: T; headers: Headers }> {
  const token = getToken();
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;

  let url = `${API_BASE_URL}${path}`;
  if (options.query) {
    const params = new URLSearchParams();
    for (const [key, value] of Object.entries(options.query)) {
      if (value !== undefined) params.set(key, String(value));
    }
    const qs = params.toString();
    if (qs) url += `?${qs}`;
  }

  return fetch(url, { headers }).then(async (response) => {
    if (!response.ok) {
      const detail = await response.json().catch(() => undefined);
      throw new ApiError(response.status, detail?.detail ?? detail);
    }
    const data = (await response.json()) as T;
    return { data, headers: response.headers };
  });
}
