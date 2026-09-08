import type { AnalysisResult, ModuleInfo } from "@/lib/types";

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/**
 * Older backends do not emit `modules` / scope fields. Derive a best-effort
 * module list from summary data so the UI degrades gracefully instead of
 * crashing, and never invents details that are not in the payload.
 */
function normalizeAnalysisResult(raw: AnalysisResult): AnalysisResult {
  const summary = raw.summary ?? {
    resource_count: raw.resources?.length ?? 0,
    data_source_count: 0,
    total_block_count: raw.resources?.length ?? 0,
    providers: [],
    services: [],
    regions: [],
    modules: [],
    variables: [],
    current_monthly: 0,
    known_monthly: 0,
    usage_monthly: 0,
    usage_available: false,
    cost_confidence: { level: "unknown", breakdown: {}, notes: [], reasons: [] },
    optimized_monthly: 0,
    monthly_savings: 0,
    annual_savings: 0,
    score: null,
    grade: "N/A",
    dimensions_assessed: 0,
    dimensions_total: 0,
    evidence_coverage: "unknown",
    evidence_coverage_pct: 0,
  };

  let modules: ModuleInfo[] = Array.isArray(raw.modules) ? raw.modules : [];
  if (modules.length === 0 && Array.isArray(summary.modules) && summary.modules.length > 0) {
    // Legacy payload: only module addresses are known.
    modules = summary.modules.map((addr) => ({
      address: addr,
      name: addr.replace(/^module\./, ""),
      source: "",
      version: null,
      source_type: "unknown",
      configuration: {},
      source_file: "",
      source_line: 0,
      expansion: "unexpanded" as const,
      resource_count: 0,
      data_source_count: 0,
      child_modules: [],
      references: [],
      note: "Module details are unavailable in this analysis payload.",
    }));
  }

  const unexpanded = modules
    .filter((m) => m.expansion === "unexpanded")
    .map((m) => m.address);
  const scores = {
    ...raw.scores,
    modules_unexpanded:
      raw.scores?.modules_unexpanded ?? unexpanded,
    scope:
      raw.scores?.scope ??
      (unexpanded.length > 0 ? "root_configuration_only" : "complete_configuration"),
    scope_label:
      raw.scores?.scope_label ??
      (unexpanded.length > 0 ? "Root configuration only" : "Full configuration"),
  };
  const costs = {
    ...raw.costs,
    modules_unquantified:
      raw.costs?.modules_unquantified ??
      unexpanded.map((address) => ({
        address,
        reason: "Module contents were not part of the analyzed configuration.",
      })),
  };
  const resources = (raw.resources ?? []).map((r) => ({
    ...r,
    module_address: r.module_address ?? r.module ?? "",
  }));

  return {
    ...raw,
    summary,
    modules,
    scores,
    costs,
    resources,
  };
}

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
  analyze: async (mode = "balanced") =>
    normalizeAnalysisResult(
      await request<AnalysisResult>(`/api/v1/demo/analyze/${mode}`),
    ),
  analyzeGithub: async (url: string, mode = "balanced") =>
    normalizeAnalysisResult(
      await request<AnalysisResult>(
        `/api/v1/demo/analyze-github?url=${encodeURIComponent(url)}&mode=${mode}`,
      ),
    ),
};
