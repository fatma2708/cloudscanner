"use client";

import { useMemo } from "react";
import { useAnalysis } from "@/lib/analysis-context";
import { ErrorPanel } from "@/components/dashboard/states";
import { formatCurrency } from "@/lib/format";
import { MaterialIcon } from "@/components/ui/material-icon";
import type { ProviderComparison, ComparisonStatus } from "@/lib/types";

const providerAbbrevs: Record<string, string> = {
  aws: "AWS", azure: "AZ", google: "GCP", digitalocean: "DO",
  hetzner: "HZ", scaleway: "SC", ovh: "OVH", oracle: "OC",
  vultr: "VL", linode: "LN",
};

function statusBadge(status: ComparisonStatus) {
  switch (status) {
    case "comparable":
      return <span className="px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-700 text-[10px] font-medium">Comparable</span>;
    case "partially_comparable":
      return <span className="px-2 py-0.5 rounded-full bg-amber-100 text-amber-700 text-[10px] font-medium">Partial</span>;
    case "not_comparable":
      return <span className="px-2 py-0.5 rounded-full bg-red-100 text-red-700 text-[10px] font-medium">Not Comparable</span>;
  }
}

function confidenceBadge(conf: string) {
  switch (conf) {
    case "high":
      return <span className="px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-700 text-[10px] font-medium">High confidence</span>;
    case "medium":
      return <span className="px-2 py-0.5 rounded-full bg-amber-100 text-amber-700 text-[10px] font-medium">Medium confidence</span>;
    case "low":
      return <span className="px-2 py-0.5 rounded-full bg-orange-100 text-orange-700 text-[10px] font-medium">Low confidence</span>;
    default:
      return <span className="px-2 py-0.5 rounded-full bg-gray-100 text-gray-600 text-[10px] font-medium">Insufficient data</span>;
  }
}

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4">
      <MaterialIcon name="cloud_queue" className="text-primary text-5xl" />
      <h2 className="text-xl font-bold text-md-on-surface">No comparison yet</h2>
      <p className="text-sm text-md-on-surface-variant">Analyze a repo first to see multi-cloud cost comparisons.</p>
    </div>
  );
}

function ComparableProviderCard({ p, isBaseline, baselineMonthly }: { p: ProviderComparison; isBaseline: boolean; baselineMonthly?: number }) {
  return (
    <div className={`bg-md-surface-container-low rounded-xl p-4 border ${
      isBaseline ? "border-2 border-primary" : "border-md-outline-variant"
    }`}>
      {isBaseline && (
        <div className="text-primary text-[10px] font-bold uppercase tracking-wider mb-2">Current provider</div>
      )}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 bg-md-surface-container flex items-center justify-center rounded-lg font-bold text-sm text-md-primary">
            {providerAbbrevs[p.provider] || p.provider.slice(0, 3).toUpperCase()}
          </div>
          <div>
            <h3 className="font-bold text-md-on-surface">{p.label}</h3>
            <p className="text-xs text-md-on-surface-variant">{p.region}</p>
          </div>
        </div>
        <div className="text-right flex flex-col items-end gap-1">
          {statusBadge(p.status)}
          {confidenceBadge(p.comparison_confidence)}
        </div>
      </div>

      <div className="flex items-end justify-between mb-3">
        <div>
          <div className="text-xl font-black text-md-on-surface">
            {isBaseline && baselineMonthly !== undefined
              ? `${formatCurrency(baselineMonthly)}`
              : p.estimated_monthly_cost !== null
                ? `${formatCurrency(p.estimated_monthly_cost)}`
                : "—"}
            {((isBaseline && baselineMonthly !== undefined) || p.estimated_monthly_cost !== null) && (
              <span className="text-xs font-normal text-md-on-surface-variant">/mo</span>
            )}
          </div>
          {p.cost_type === "known_baseline" && (
            <span className="text-[10px] text-md-on-surface-variant opacity-60 block">Known baseline cost</span>
          )}
          {!isBaseline && p.estimated_monthly_cost !== null && (
            <span className="text-[10px] text-md-on-surface-variant block">
              Mapped infrastructure estimate
            </span>
          )}
          {!isBaseline && p.delta_pct !== null && p.delta_pct !== undefined && (
            <span className={`text-[11px] font-medium ${p.delta_pct > 0 ? "text-md-error" : "text-emerald-600"}`}>
              {p.delta_pct > 0 ? "+" : ""}{p.delta_pct.toFixed(0)}% {p.comparison_confidence === "low" ? "mapped-cost delta" : "vs current provider"}
            </span>
          )}
        </div>
        <div className="text-xs text-md-on-surface-variant">
          {p.coverage_pct.toFixed(0)}% service coverage
          {p.mapping_coverage_pct !== undefined && p.mapping_coverage_pct !== p.coverage_pct && (
            <span className="ml-1 opacity-70">({p.mapping_coverage_pct.toFixed(0)}% mapped)</span>
          )}
          {p.architecture_equivalence && (
            <div className="flex items-center gap-1 mt-1">
              <span className="text-[10px] text-md-on-surface-variant">Architecture equivalence:</span>
              <span className={`text-[10px] font-medium ${
                p.architecture_equivalence === "high" ? "text-green-600" :
                p.architecture_equivalence === "medium" ? "text-amber-600" :
                "text-red-600"
              }`}>{p.architecture_equivalence}</span>
            </div>
          )}
        </div>
      </div>

      {p.unsupported_services.length > 0 && (
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-2.5 mb-3">
          <p className="text-[11px] font-medium text-amber-800 mb-1">
            {p.unsupported_services.length} AWS managed {p.unsupported_services.length === 1 ? "service has" : "services have"} no validated equivalent:
          </p>
          <p className="text-[10px] text-amber-700">
            {p.unsupported_services.join(", ")}
          </p>
        </div>
      )}

      {p.comparison_confidence === "low" && (
        <div className="bg-orange-50 border border-orange-200 rounded-lg p-2.5 mb-3">
          <p className="text-[10px] font-medium text-orange-800">
            Not an apples-to-apples migration estimate — this provider has limited service parity with AWS.
          </p>
        </div>
      )}

      {p.breakdown && (
        <div className="grid grid-cols-3 gap-2 text-[11px] border-t border-md-outline-variant pt-3">
          {Object.entries(p.breakdown).map(([cat, cost]) => (
            <div key={cat}>
              <span className="text-md-on-surface-variant">{cat}</span>
              <p className="font-medium text-md-on-surface">{formatCurrency(cost, 2)}</p>
            </div>
          ))}
          <div className="border-t border-md-outline-variant pt-1">
            <span className="text-md-on-surface-variant font-medium">Total</span>
            <p className="font-bold text-md-on-surface">{formatCurrency(
              Object.values(p.breakdown).reduce((a, b) => a + b, 0), 2)}</p>
          </div>
        </div>
      )}

      <div className="mt-3 pt-2 border-t border-md-outline-variant text-[10px] text-md-on-surface-variant">
        <MaterialIcon name="eco" className="text-[12px] mr-1 align-middle" />
        {p.sustainability_note}
      </div>
    </div>
  );
}

function NotComparableCard({ p }: { p: ProviderComparison }) {
  return (
    <div className="bg-md-surface-container-low rounded-xl p-4 border border-md-outline-variant opacity-75">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 bg-md-surface-container flex items-center justify-center rounded-lg font-bold text-sm text-md-on-surface-variant">
            {providerAbbrevs[p.provider] || p.provider.slice(0, 3).toUpperCase()}
          </div>
          <div>
            <h3 className="font-bold text-md-on-surface-variant">{p.label}</h3>
            <p className="text-xs text-md-on-surface-variant/60">{p.region}</p>
          </div>
        </div>
        <div className="flex flex-col items-end gap-1">
          {statusBadge(p.status)}
          {confidenceBadge(p.comparison_confidence)}
        </div>
      </div>

      <div className="bg-md-error-container/20 rounded-lg p-2.5 mt-2">
        <p className="text-[11px] font-medium text-md-on-surface-variant">
          Not directly comparable
        </p>
        <p className="text-[10px] text-md-on-surface-variant/70 mt-1">
          {p.unsupported_services.length} AWS managed {p.unsupported_services.length === 1 ? "service has" : "services have"} no validated equivalent on {p.label}: {p.unsupported_services.join(", ")}.
        </p>
      </div>
    </div>
  );
}

export default function ComparisonPage() {
  const { data, loading, error, repoUrl } = useAnalysis();

  const { comparable, notComparable } = useMemo(() => {
    if (!data) return { comparable: [], notComparable: [] };
    const comp: ProviderComparison[] = [];
    const notComp: ProviderComparison[] = [];
    for (const p of data.comparison.providers) {
      if (p.status === "not_comparable") {
        notComp.push(p);
      } else {
        comp.push(p);
      }
    }
    comp.sort((a, b) => (a.estimated_monthly_cost ?? Infinity) - (b.estimated_monthly_cost ?? Infinity));
    return { comparable: comp, notComparable: notComp };
  }, [data]);

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

  const baseline = comparable.find((p) => p.provider === data.comparison.baseline_provider);

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div>
        <h1 className="text-xl font-bold text-md-on-surface">Cloud Cost Comparison</h1>
        <p className="text-xs text-md-on-surface-variant">
          {data.summary.resource_count}-resource workload across {data.comparison.providers.length} providers
        </p>
      </div>

      <div className="bg-md-surface-container-low rounded-xl p-4 border border-md-outline-variant">
        <p className="text-[11px] text-md-on-surface-variant leading-relaxed">
          Cost estimates are based on translating {data.summary.resource_count} Terraform resources into equivalent provider primitives.
          Providers with incomplete service equivalence are marked &quot;Not Comparable&quot; — no price is shown.
          Actual costs depend on usage, data transfer, and negotiated pricing.
        </p>
      </div>

      {baseline && (
        <div>
          <h2 className="text-sm font-bold text-md-on-surface mb-3">Current Provider</h2>
          <ComparableProviderCard p={baseline} isBaseline={true} baselineMonthly={data.comparison.baseline_monthly} />
        </div>
      )}

      {comparable.filter((p) => p.provider !== data.comparison.baseline_provider).length > 0 && (
        <div>
          <h2 className="text-sm font-bold text-md-on-surface mb-3">Alternative Providers</h2>
          <div className="grid grid-cols-1 gap-3">
            {comparable
              .filter((p) => p.provider !== data.comparison.baseline_provider)
              .map((p) => (
                <ComparableProviderCard key={p.provider} p={p} isBaseline={false} />
              ))}
          </div>
        </div>
      )}

      {notComparable.length > 0 && (
        <div>
          <h2 className="text-sm font-bold text-md-on-surface-variant mb-3">Not Comparable</h2>
          <div className="grid grid-cols-1 gap-3">
            {notComparable.map((p) => (
              <NotComparableCard key={p.provider} p={p} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
