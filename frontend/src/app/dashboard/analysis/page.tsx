"use client";

import { useMemo, useState } from "react";
import { useAnalysis } from "@/lib/analysis-context";
import { ErrorPanel } from "@/components/dashboard/states";
import { MaterialIcon } from "@/components/ui/material-icon";
import { serviceColor, serviceMeta } from "@/components/dashboard/service-meta";
import { formatCurrency } from "@/lib/format";

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4">
      <MaterialIcon name="dns" className="text-primary text-5xl" />
      <h2 className="text-xl font-bold text-md-on-surface">No resources yet</h2>
      <p className="text-sm text-md-on-surface-variant">Analyze a repo first to see resource details.</p>
    </div>
  );
}

function resourceCostDisplay(r: { monthly_cost?: number; attributes?: Record<string, unknown> }) {
  const cost = r.monthly_cost ?? 0;
  if (cost > 0) return formatCurrency(cost);
  const classification = (r.attributes as Record<string, unknown>)?._cost_classification;
  if (classification === "usage_based") return "Usage-based";
  if (classification === "unknown") return "—";
  return "—";
}

export default function AnalysisPage() {
  const { data, loading, error, repoUrl } = useAnalysis();
  const [query, setQuery] = useState("");
  const [service, setService] = useState("all");

  const services = useMemo(() => {
    if (!data) return [];
    return Array.from(new Set(data.resources.map((r) => r.service))).sort();
  }, [data]);

  const filtered = useMemo(() => {
    if (!data) return [];
    const q = query.trim().toLowerCase();
    return data.resources.filter((r) => {
      if (service !== "all" && r.service !== service) return false;
      if (q && ![r.resource_type, r.name, r.id, r.module].some((s) => s.toLowerCase().includes(q))) return false;
      return true;
    });
  }, [data, query, service]);

  if (error && !data) return <ErrorPanel message={error} />;
  if (!repoUrl || (!data && !loading)) return <EmptyState />;
  if (loading && !data) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-md-primary-container/30 border-t-md-primary" />
      </div>
    );
  }
  if (!data) return null;

  const meta = data.analysis_metadata;

  // Compute pricing stats
  const priced = filtered.filter((r) => (r.monthly_cost ?? 0) > 0);
  const knownTotal = priced.reduce((acc, r) => acc + (r.monthly_cost ?? 0), 0);
  const fixedCost = filtered.filter((r) => {
    const c = (r.attributes as Record<string, unknown>)?._cost_classification;
    return c === "fixed" && (r.monthly_cost ?? 0) > 0;
  }).length;
  const estimatedCost = filtered.filter((r) => {
    const c = (r.attributes as Record<string, unknown>)?._cost_classification;
    return c === "estimated" && (r.monthly_cost ?? 0) > 0;
  }).length;
  const usageBased = filtered.filter((r) => {
    const c = (r.attributes as Record<string, unknown>)?._cost_classification;
    return c === "usage_based" || c === "unknown";
  }).length;

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-bold text-md-on-surface">Resources</h1>
        <p className="text-xs text-md-on-surface-variant">{data.summary.total_block_count ?? data.summary.resource_count} Terraform blocks · {data.summary.resource_count} resources · {data.summary.data_source_count ?? 0} data sources</p>
      </div>

      {meta && (
        <div className="bg-md-surface-container-low rounded-lg p-3 border border-md-outline-variant flex flex-wrap items-center gap-2 text-[10px]">
          <span className="px-2 py-0.5 rounded-full bg-violet-100 text-violet-700 font-medium">
            AI Review: {meta.llm_model || meta.llm_provider}
          </span>
          {meta.llm_provider_label && (
            <span className="px-2 py-0.5 rounded-full bg-violet-50 text-violet-600 font-medium">
              Provider: {meta.llm_provider_label}
            </span>
          )}
          <span className="px-2 py-0.5 rounded-full bg-blue-100 text-blue-700 font-medium">
            {meta.rules_evaluated} rules evaluated
          </span>
          <span
            className="px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-700 font-medium relative group cursor-help"
            title="Evidence coverage measures how much of the analysis can be established from Terraform/configuration alone. Runtime telemetry and workload usage data are not available."
          >
            Evidence Coverage: {meta.evidence_coverage_pct.toFixed(0)}%
            <span className="hidden group-hover:block absolute left-0 top-full mt-1 w-64 p-2 rounded-lg bg-gray-900 text-white text-[10px] leading-relaxed z-50 shadow-lg">
              Evidence coverage measures how much of the analysis can be established from Terraform/configuration alone.
              Runtime telemetry and workload usage data are not available.
            </span>
          </span>
          <span className="px-2 py-0.5 rounded-full bg-amber-100 text-amber-700 font-medium">
            Cost Confidence: {meta.cost_estimates_confident}
          </span>
        </div>
      )}

      <div className="bg-md-surface-container-low rounded-lg p-3 border border-md-outline-variant flex flex-col gap-2 sm:flex-row sm:items-center">
        <div className="relative flex-1">
          <MaterialIcon name="search" className="absolute left-2.5 top-1/2 -translate-y-1/2 text-md-on-surface-variant text-[16px]" />
          <input
            placeholder="Search resources..."
            className="w-full pl-8 pr-3 py-2 rounded-full bg-md-surface-container-lowest border border-md-outline-variant text-sm text-md-on-surface placeholder:text-md-on-surface-variant/60 focus:outline-none focus:border-primary"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>
        <select
          value={service}
          onChange={(e) => setService(e.target.value)}
          className="px-3 py-2 rounded-full bg-md-surface-container-lowest border border-md-outline-variant text-sm text-md-on-surface focus:outline-none focus:border-primary"
        >
          <option value="all">All services</option>
          {services.map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
      </div>

      <div className="bg-md-surface-container-low rounded-lg p-3 border border-md-outline-variant space-y-2">
        <div className="flex items-center gap-2 text-xs text-md-on-surface-variant flex-wrap">
          <span className="bg-md-secondary-container text-md-on-secondary-container font-bold px-2 py-0.5 rounded">
            {filtered.length} resources
          </span>
          {knownTotal > 0 && (
            <span className="bg-md-surface-container text-md-on-surface font-bold px-2 py-0.5 rounded">
              Known baseline: {formatCurrency(knownTotal)}/mo
            </span>
          )}
          {fixedCost > 0 && (
            <span className="bg-md-surface-container text-md-on-surface-variant px-2 py-0.5 rounded">
              {fixedCost} fixed-price
            </span>
          )}
          {estimatedCost > 0 && (
            <span className="bg-md-surface-container text-md-on-surface-variant px-2 py-0.5 rounded">
              {estimatedCost} estimated
            </span>
          )}
          {usageBased > 0 && (
            <span className="bg-md-surface-container text-md-on-surface-variant px-2 py-0.5 rounded">
              {usageBased} usage-dependent (not quantified)
            </span>
          )}
          {knownTotal === 0 && (
            <span className="bg-md-surface-container text-md-on-surface-variant px-2 py-0.5 rounded">
              Not enough pricing data
            </span>
          )}
        </div>
      </div>

      <div className="bg-md-surface-container-low rounded-xl border border-md-outline-variant overflow-hidden divide-y divide-md-outline-variant">
        {filtered.map((r) => {
          const meta = serviceMeta[r.service];
          const color = serviceColor(r.service);
          const costText = resourceCostDisplay(r);
          return (
            <div key={r.id} className="flex items-center gap-3 px-4 py-3">
              <div
                className="grid h-7 w-7 shrink-0 place-items-center rounded-full"
                style={{ backgroundColor: `${color}1f` }}
              >
                <MaterialIcon name={meta?.icon ?? "dns"} className="text-[14px]" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="font-mono text-xs font-medium text-md-on-surface truncate">{r.resource_type}.{r.name}</p>
                <p className="text-[10px] text-md-on-surface-variant">{r.region}</p>
              </div>
              <span className="bg-md-surface-variant text-md-on-surface-variant text-[10px] font-bold px-1.5 py-0.5 rounded capitalize hidden sm:inline">
                {r.kind}
              </span>
              <span className={`text-xs font-medium w-16 text-right ${(r.monthly_cost ?? 0) > 0 ? "text-md-on-surface" : "text-md-on-surface-variant"}`}>
                {costText}
              </span>
            </div>
          );
        })}
        {filtered.length === 0 && (
          <div className="py-10 text-center text-sm text-md-on-surface-variant">No resources match your search.</div>
        )}
      </div>
    </div>
  );
}
