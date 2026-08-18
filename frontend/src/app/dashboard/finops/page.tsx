"use client";

import { useAnalysis } from "@/lib/analysis-context";
import { ErrorPanel } from "@/components/dashboard/states";
import { formatCurrency } from "@/lib/format";
import { MaterialIcon } from "@/components/ui/material-icon";
import { serviceColor } from "@/components/dashboard/service-meta";

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4">
      <MaterialIcon name="payments" className="text-primary text-5xl" />
      <h2 className="text-xl font-bold text-md-on-surface">No cost data yet</h2>
      <p className="text-sm text-md-on-surface-variant">Analyze a repo first to see FinOps breakdown.</p>
    </div>
  );
}

export default function FinopsPage() {
  const { data, loading, error, repoUrl } = useAnalysis();

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

  const { finops, carbon, costs } = data;
  const maxService = Math.max(...finops.by_service.map((s) => s.monthly), 1);

  const costConfidenceColor = (level: string) => {
    if (level === "high") return "bg-emerald-100 text-emerald-700";
    if (level === "medium") return "bg-amber-100 text-amber-700";
    return "bg-red-100 text-red-700";
  };

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-bold text-md-on-surface">FinOps</h1>
        <p className="text-xs text-md-on-surface-variant">Cost breakdown, savings, and sustainability.</p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="p-3 bg-md-surface-container-low rounded-xl border border-md-outline-variant">
          <p className="text-[11px] text-md-on-surface-variant uppercase tracking-wider mb-1">Known baseline</p>
          <p className="text-lg font-bold text-md-on-surface">{formatCurrency(finops.current_monthly)}<span className="text-[10px] font-normal text-md-on-surface-variant">/mo</span></p>
          <div className="mt-2 text-xs text-md-on-surface-variant">
            {finops.usage_available ? (
              <span>Includes {formatCurrency(finops.usage_monthly)} estimated usage-dependent charges</span>
            ) : (
              <span className="opacity-70">Usage-dependent charges not quantified</span>
            )}
          </div>
        </div>
        <Card label="Optimized" value={formatCurrency(finops.optimized_monthly)} sub="/mo" accent />
        <Card label="Annual Savings" value={formatCurrency(finops.annual_savings)} accent />
        <div className="p-3 bg-md-surface-container-low rounded-xl border border-md-outline-variant">
          <p className="text-[11px] text-md-on-surface-variant uppercase tracking-wider mb-1">Carbon</p>
          <p className={`text-lg font-bold ${
            carbon.rating === "low" ? "text-emerald-600" :
            carbon.rating === "moderate" ? "text-amber-600" : "text-red-600"
          }`}>{carbon.rating}</p>
          <p className="text-[10px] text-md-on-surface-variant">{carbon.potential} reduction potential</p>
        </div>
      </div>

      <div className="flex items-center gap-2 flex-wrap">
        <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${costConfidenceColor(costs.confidence.level)}`}>
          Cost Confidence: {costs.confidence.level}
        </span>
        <span className="text-[10px] text-md-on-surface-variant">
          {costs.confidence.breakdown.high} high · {costs.confidence.breakdown.medium} medium · {costs.confidence.breakdown.low} low · {costs.confidence.breakdown.unknown} unknown
        </span>
      </div>

      {costs.confidence.reasons && costs.confidence.reasons.length > 0 && (
        <div className="bg-md-surface-container-low rounded-xl p-3 border border-md-outline-variant">
          <p className="text-[10px] font-bold text-md-on-surface-variant uppercase tracking-wider mb-1.5">Why this confidence level</p>
          <ul className="space-y-1">
            {costs.confidence.reasons.map((reason, i) => (
              <li key={i} className="text-[11px] text-md-on-surface-variant flex items-start gap-1.5">
                <MaterialIcon name="arrow_right" className="text-[11px] text-md-on-surface-variant mt-0.5 shrink-0" />
                {reason}
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="bg-md-surface-container-low rounded-xl p-4 border border-md-outline-variant">
        <h2 className="text-sm font-semibold text-md-on-surface mb-3 flex items-center gap-1.5">
          <MaterialIcon name="payments" className="text-primary text-[16px]" />
          Cost by Service {!finops.usage_available && <span className="text-[10px] font-normal text-md-on-surface-variant ml-1">(baseline only)</span>}
        </h2>
        <div className="space-y-3">
          {finops.by_service.filter((s) => s.monthly > 0).map((s) => (
            <div key={s.service}>
              <div className="mb-1 flex items-center justify-between text-xs">
                <span className="font-medium text-md-on-surface">{s.service_label}</span>
                <span className="text-md-on-surface-variant">{formatCurrency(s.monthly)} baseline/mo · {s.pct.toFixed(0)}%</span>
              </div>
              <div className="h-2 w-full overflow-hidden rounded-full bg-md-surface-variant">
                <div className="h-full rounded-full" style={{ width: `${(s.monthly / maxService) * 100}%`, backgroundColor: serviceColor(s.service) }} />
              </div>
            </div>
          ))}
        </div>
      </div>

      {(finops.rightsizing || finops.spot_recommendation) && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {finops.rightsizing && (
            <div className="bg-md-surface-container-low rounded-xl p-4 border border-md-outline-variant">
              <h3 className="text-xs font-semibold text-md-on-surface mb-2 flex items-center gap-1.5">
                <MaterialIcon name="speed" className="text-primary text-[14px]" />
                Rightsizing
              </h3>
              <div className="flex items-end justify-between">
                <div>
                  <p className="text-2xl font-bold text-md-on-surface">{finops.rightsizing.instances}</p>
                  <p className="text-[11px] text-md-on-surface-variant">over-provisioned</p>
                </div>
                <p className="text-sm font-medium text-primary">{formatCurrency(finops.rightsizing.potential_savings)}/mo</p>
              </div>
            </div>
          )}
          {finops.spot_recommendation && (
            <div className="bg-md-surface-container-low rounded-xl p-4 border border-md-outline-variant">
              <h3 className="text-xs font-semibold text-md-on-surface mb-2 flex items-center gap-1.5">
                <MaterialIcon name="bolt" className="text-md-tertiary text-[14px]" />
                Spot Capacity
              </h3>
              <div className="flex items-end justify-between">
                <div>
                  <p className="text-2xl font-bold text-md-on-surface">{finops.spot_recommendation.eligible}</p>
                  <p className="text-[11px] text-md-on-surface-variant">eligible workloads</p>
                </div>
                <p className="text-sm font-medium text-primary">{formatCurrency(finops.spot_recommendation.potential_savings)}/mo</p>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function Card({ label, value, sub, accent }: { label: string; value: string; sub?: string; accent?: boolean }) {
  return (
    <div className="p-3 bg-md-surface-container-low rounded-xl border border-md-outline-variant">
      <p className="text-[11px] text-md-on-surface-variant uppercase tracking-wider mb-1">{label}</p>
      <p className={`text-lg font-bold ${accent ? "text-primary" : "text-md-on-surface"}`}>{value}</p>
      {sub && <p className="text-[10px] text-md-on-surface-variant">{sub}</p>}
    </div>
  );
}
