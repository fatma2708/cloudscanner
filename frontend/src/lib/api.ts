import type { AnalysisResult } from "@/lib/types";

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    cache: "no-store",
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      /* ignore non-JSON error bodies */
    }
    throw new Error(detail);
  }
  return (await res.json()) as T;
}

export const api = {
  health: () => request<{ status: string; version?: string }>("/api/v1/health"),
  sampleFiles: () => request<{ files: Record<string, string> }>("/api/v1/demo/sample-files"),
  analyze: (mode = "balanced") => request<AnalysisResult>(`/api/v1/demo/analyze/${mode}`),
  analyzeGithub: (url: string, mode = "balanced") =>
    request<AnalysisResult>(
      `/api/v1/demo/analyze-github?url=${encodeURIComponent(url)}&mode=${mode}`,
    ),
};
