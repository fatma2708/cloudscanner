"use client";

import { useState, type ReactNode } from "react";
import { useAnalysis } from "@/lib/analysis-context";
import { ErrorPanel } from "@/components/dashboard/states";
import { CrimInlineChip } from "@/components/dashboard/crim";
import { EvidenceCoverageBadge, unexpandedModuleCount } from "@/components/dashboard/evidence-coverage-badge";
import { formatCurrency } from "@/lib/format";
import { MaterialIcon } from "@/components/ui/material-icon";

function GitHubInput({
  onSubmit,
  onDemo,
  busy,
}: {
  onSubmit: (url: string) => void;
  onDemo: () => void;
  busy: boolean;
}) {
  const [url, setUrl] = useState("");
  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] gap-6">
      <MaterialIcon name="cloud_queue" className="text-primary text-5xl" />
      <div className="text-center">
        <h2 className="text-2xl font-bold text-md-on-surface mb-2">Analyze a repository</h2>
        <p className="text-sm text-md-on-surface-variant max-w-md">
          Paste a public GitHub repo URL containing Terraform or OpenTofu files.
        </p>
      </div>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          const trimmed = url.trim();
          if (trimmed) onSubmit(trimmed);
        }}
        className="flex gap-3 w-full max-w-lg"
      >
        <input
          type="url"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://github.com/owner/repo"
          required
          aria-label="GitHub repository URL"
          className="flex-1 px-5 py-3 rounded-full bg-md-surface-container-lowest border border-md-outline-variant text-md-on-surface placeholder:text-md-on-surface-variant/60 focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary transition-colors text-sm"
        />
        <button
          type="submit"
          disabled={busy}
          className="px-6 py-3 rounded-full bg-primary text-md-on-primary font-bold text-sm hover:opacity-90 transition-opacity inline-flex items-center gap-2 shrink-0 disabled:opacity-50"
        >
          {busy ? (
            <div className="h-4 w-4 animate-spin rounded-full border-2 border-md-on-primary/30 border-t-md-on-primary" />
          ) : (
            <MaterialIcon name="arrow_forward" className="text-[18px]" />
          )}
          Analyze
        </button>
      </form>
      <button
        type="button"
        onClick={onDemo}
        disabled={busy}
        className="text-sm font-medium text-primary hover:underline disabled:opacity-50"
      >
        Or explore the demo project
      </button>
    </div>
  );
}

function LoadingState({ url }: { url: string }) {
  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] gap-6">
      <div className="h-12 w-12 animate-spin rounded-full border-3 border-md-primary-container/30 border-t-primary" />
      <div className="text-center">
        <h2 className="text-xl font-bold text-md-on-surface mb-1">Analyzing repository</h2>
        <p className="text-sm text-md-on-surface-variant font-mono truncate max-w-md">
          {url.replace(/^https?:\/\/(www\.)?github\.com\//, "")}
        </p>
        <p className="text-xs text-md-on-surface-variant/60 mt-2">Parsing Terraform, estimating costs, scoring reliability…</p>
      </div>
    </div>
  );
}

function ScoreRing({ score, size = 48 }: { score: number | null; size?: number }) {
  const r = (size - 8) / 2;
  const c = 2 * Math.PI * r;
  const color = score === null ? "#9e9e9e" : score >= 80 ? "#10b981" : score >= 60 ? "#f59e0b" : "#ef4444";
  return (
    <div className="relative" style={{ width: size, height: size }}>
      <svg viewBox={`0 0 ${size} ${size}`} className="h-full w-full -rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#e8e0f0" strokeWidth="4" />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke={color}
          strokeWidth="4"
          strokeLinecap="round"
          strokeDasharray={c}
          strokeDashoffset={score !== null ? c * (1 - score / 100) : c}
        />
      </svg>
      <div className="absolute inset-0 flex items-center justify-center">
        <span className="font-bold text-md-on-surface" style={{ fontSize: size * 0.3 }}>
          {score !== null ? Math.round(score) : "N/A"}
        </span>
      </div>
    </div>
  );
}

function EvidenceDimensions({ dimensions }: { dimensions: Array<{ name: string; status: string; detail: string }> }) {
  const statusIcon = (s: string) => {
    if (s === "available") return <MaterialIcon name="check_circle" className="text-[14px] text-emerald-600" />;
    if (s === "partial") return <MaterialIcon name="info" className="text-[14px] text-amber-600" />;
    return <MaterialIcon name="cancel" className="text-[14px] text-red-500" />;
  };
  const statusLabel = (s: string) => {
    if (s === "available") return <span className="text-emerald-700 font-medium">Available</span>;
    if (s === "partial") return <span className="text-amber-700 font-medium">Partial</span>;
    return <span className="text-red-600 font-medium">Not available</span>;
  };

  return (
    <div className="space-y-2">
      {dimensions.map((d) => (
        <div key={d.name} className="flex items-start gap-2 text-[11px]">
          {statusIcon(d.status)}
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <span className="font-medium text-md-on-surface">{d.name}</span>
              {statusLabel(d.status)}
            </div>
            <p className="text-md-on-surface-variant mt-0.5">{d.detail}</p>
          </div>
        </div>
      ))}
    </div>
  );
}

function AnalysisLimitations() {
  return (
    <div className="bg-md-surface-container-low rounded-xl border border-md-outline-variant p-4">
      <div className="flex items-center gap-2 mb-2">
        <MaterialIcon name="info_outline" className="text-[16px] text-md-on-surface-variant" />
        <h3 className="text-xs font-bold text-md-on-surface-variant uppercase tracking-wider">Analysis Limitations</h3>
      </div>
      <p className="text-[11px] text-md-on-surface-variant leading-relaxed">
        CloudPilot analyzes Terraform configuration. Runtime telemetry, request volume, actual traffic,
        and workload utilization are not available unless explicitly provided. Cost estimates use
        published catalog pricing and may not reflect negotiated discounts, reserved capacity, or
        spot pricing. Scores and recommendations are based on configuration patterns, not runtime behavior.
      </p>
    </div>
  );
}

export default function OverviewPage() {
  const { data, error, refreshing, refresh, repoUrl, analyzeGithub, analyzeDemo, mode } = useAnalysis();

  if (error && !data) return <ErrorPanel message={error} />;
  if (refreshing && !data) return <LoadingState url={repoUrl ?? ""} />;
  if (!repoUrl || !data) {
    return <GitHubInput onSubmit={analyzeGithub} onDemo={analyzeDemo} busy={refreshing} />;
  }

  const { summary, recommendations, scores, costs } = data;
  const unexpandedModules = unexpandedModuleCount(scores, summary);
  const criticalCount = recommendations.filter((r) => r.severity === "critical" || r.severity === "high").length;
  const topFixes = recommendations.slice(0, 3);
  const evidenceDimensions = scores.evidence_dimensions ?? [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-md-on-surface">Overview</h1>
          <p className="text-xs text-md-on-surface-variant">
            {summary.resource_count} resources · {summary.data_source_count} data sources · {summary.providers.join(", ")} · {summary.regions[0]}
          </p>
        </div>
        <button
          onClick={refresh}
          disabled={refreshing}
          className="flex items-center gap-1.5 px-4 py-2 rounded-full text-sm font-medium border border-md-outline-variant text-md-on-surface-variant hover:bg-md-surface-container-highest transition-colors disabled:opacity-50"
        >
          <MaterialIcon name="refresh" className={`text-[16px] ${refreshing ? "animate-spin" : ""}`} />
          {refreshing ? "Analyzing…" : "Re-analyze"}
        </button>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatCard label="Assessed Score" value={scores.overall !== null ? `${scores.overall} / 100` : "N/A"} icon="grade" />
        <StatCard label="Monthly Cost" value={formatCurrency(summary.current_monthly)} icon="payments"
          sub={costs.confidence.level === "low" ? "Runtime usage data unavailable" : undefined}
          badge={<EvidenceCoverageBadge coveragePct={scores.evidence_coverage_pct} unexpandedModules={unexpandedModules} />} />
        <StatCard
          label="Savings"
          value={summary.monthly_savings > 0 ? formatCurrency(summary.monthly_savings) : "—"}
          sub={summary.monthly_savings > 0 ? "/mo potential" : "Not quantified"}
          icon="savings"
          accent={summary.monthly_savings > 0}
        />
        <StatCard label="Issues" value={criticalCount.toString()} sub="critical + high" icon="warning" alert={criticalCount > 0} />
      </div>

      {mode !== "balanced" && (
        <div className="bg-md-primary-container/20 rounded-lg px-4 py-2 text-xs text-md-on-surface-variant flex items-center gap-2">
          <MaterialIcon name="tune" className="text-[14px] text-primary" />
          Mode: <span className="font-medium text-primary">{mode}</span>
          — <button onClick={refresh} className="underline hover:text-primary">Re-analyze with this mode</button>
        </div>
      )}

      <div className="flex items-center gap-3 p-4 bg-md-surface-container-low rounded-xl border border-md-outline-variant">
        <ScoreRing score={scores.overall} />
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-md-on-surface">
            Assessed Score
          </p>
          <div className="flex items-center gap-2 mt-1 flex-wrap">
            <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${
              scores.evidence_coverage === "high" ? "bg-emerald-100 text-emerald-700" :
              scores.evidence_coverage === "medium" ? "bg-amber-100 text-amber-700" :
              "bg-red-100 text-red-700"
            }`}>
              Evidence Coverage: {scores.evidence_coverage_pct.toFixed(0)}%
            </span>
            <EvidenceCoverageBadge coveragePct={scores.evidence_coverage_pct} unexpandedModules={unexpandedModules} />
            <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${
              costs.confidence.level === "high" ? "bg-emerald-100 text-emerald-700" :
              costs.confidence.level === "medium" ? "bg-amber-100 text-amber-700" :
              "bg-red-100 text-red-700"
            }`}>
              Cost Confidence: {costs.confidence.level}
            </span>
          </div>
          <p className="text-xs text-md-on-surface-variant mt-1">
            {scores.overall !== null ? `${scores.overall.toFixed(0)} / 100` : "Insufficient evidence"}
          </p>
          <div className="text-[10px] text-md-on-surface-variant mt-1">
            {summary.dimensions_assessed} / {summary.dimensions_total} dimensions assessed
          </div>
          {scores.overall === null && (
            <div className="mt-2 p-2 rounded-lg bg-amber-50 border border-amber-200">
              <p className="text-[10px] font-medium text-amber-800">Production Readiness — Insufficient evidence</p>
              <p className="text-[10px] text-amber-700 mt-0.5">Not enough dimensions assessed to determine production readiness</p>
            </div>
          )}
          <div className="mt-2 space-y-1.5">
            {scores.categories.slice(0, 4).map((cat) => (
              <div key={cat.key} className="flex items-center gap-2 text-xs">
                <span className="w-20 text-md-on-surface-variant truncate">{cat.label}</span>
                <div className="flex-1 h-1.5 bg-md-surface-variant rounded-full overflow-hidden">
                  <div
                    className="h-full rounded-full"
                    style={{
                      width: cat.score !== null ? `${(cat.score / cat.max) * 100}%` : "0%",
                      backgroundColor: cat.score === null ? "#9e9e9e" : cat.score >= 80 ? "#10b981" : cat.score >= 60 ? "#f59e0b" : "#ef4444",
                    }}
                  />
                </div>
                <span className="w-8 text-right font-medium text-md-on-surface-variant">
                  {cat.score !== null ? cat.score : <span className="text-[9px] opacity-50">N/A</span>}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div className="p-4 bg-md-surface-container-low rounded-xl border border-md-outline-variant">
          <p className="text-xs text-md-on-surface-variant uppercase tracking-wider mb-1">Known Baseline</p>
          <p className="text-xl font-bold text-md-on-surface">{formatCurrency(costs.known_monthly)}<span className="text-sm font-normal text-md-on-surface-variant">/mo</span></p>
          <p className="text-[10px] text-md-on-surface-variant mt-1">Determined from Terraform configuration</p>
          {costs.usage_monthly > 0 && !costs.usage_available && (
            <div className="mt-2 pt-2 border-t border-md-outline-variant">
              <p className="text-[10px] text-md-on-surface-variant opacity-70">Usage-dependent charges — not quantified</p>
              <p className="text-[10px] text-md-on-surface-variant/60 mt-0.5">Excluded from the known baseline above</p>
            </div>
          )}
        </div>
        <div className="p-4 bg-md-surface-container-low rounded-xl border border-md-outline-variant">
          <p className="text-xs text-md-on-surface-variant uppercase tracking-wider mb-1">Optimized</p>
          <p className="text-xl font-bold text-primary">{formatCurrency(summary.optimized_monthly)}<span className="text-sm font-normal text-md-on-surface-variant">/mo</span></p>
          {summary.monthly_savings > 0 && (
            <p className="text-[10px] text-primary mt-1">
              {formatCurrency(summary.monthly_savings)}/mo potential savings
            </p>
          )}
        </div>
      </div>

      {evidenceDimensions.length > 0 && (
        <div className="bg-md-surface-container-low rounded-xl border border-md-outline-variant p-4">
          <h3 className="text-xs font-bold text-md-on-surface-variant uppercase tracking-wider mb-3">Evidence Dimensions</h3>
          <EvidenceDimensions dimensions={evidenceDimensions} />
        </div>
      )}

      {costs.confidence.reasons && costs.confidence.reasons.length > 0 && (
        <div className="bg-md-surface-container-low rounded-xl border border-md-outline-variant p-4">
          <h3 className="text-xs font-bold text-md-on-surface-variant uppercase tracking-wider mb-2">Cost Confidence: {costs.confidence.level}</h3>
          <ul className="space-y-1">
            {costs.confidence.reasons.map((reason, i) => (
              <li key={i} className="text-[11px] text-md-on-surface-variant flex items-start gap-2">
                <MaterialIcon name="arrow_right" className="text-[12px] text-md-on-surface-variant mt-0.5 shrink-0" />
                {reason}
              </li>
            ))}
          </ul>
        </div>
      )}

      {topFixes.length > 0 && (
        <div>
          <h2 className="text-sm font-bold text-md-on-surface mb-3">Top Issues</h2>
          <div className="space-y-2">
            {topFixes.map((rec, i) => (
              <div
                key={rec.key + i}
                className={`p-3 rounded-lg border border-md-outline-variant ${
                  rec.severity === "critical" ? "border-l-3 border-l-md-error" : rec.severity === "high" ? "border-l-3 border-l-md-tertiary" : "border-l-3 border-l-md-outline-variant"
                }`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <h3 className="text-sm font-medium text-md-on-surface">{rec.title}</h3>
                    <p className="text-xs text-md-on-surface-variant line-clamp-1 mt-0.5">{rec.description}</p>
                    <div className="flex flex-wrap items-center gap-2 mt-1.5">
                      <span className="text-[10px] text-md-on-surface-variant/80">Detected by CloudPilot rules</span>
                      <CrimInlineChip
                        classification={rec.ml_classification}
                        unavailable={data.crim?.ml_unavailable}
                        alwaysShowUncertain
                        showModel
                      />
                    </div>
                  </div>
                  {rec.savings_monthly > 0 && (
                    <span className="text-xs font-medium text-primary whitespace-nowrap">
                      {formatCurrency(rec.savings_monthly)}/mo
                    </span>
                  )}
                  {rec.savings_monthly === 0 && rec.severity === "critical" && (
                    <span className="text-xs font-medium text-md-error whitespace-nowrap">
                      Required
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <AnalysisLimitations />
    </div>
  );
}

function StatCard({ label, value, sub, icon, accent, alert, badge }: {
  label: string;
  value: string;
  sub?: string;
  icon: string;
  accent?: boolean;
  alert?: boolean;
  badge?: ReactNode;
}) {
  return (
    <div className={`p-4 rounded-xl border border-md-outline-variant ${alert ? "bg-md-error-container/10 border-md-error/20" : "bg-md-surface-container-low"}`}>
      <div className="flex items-center gap-1.5 mb-2">
        <MaterialIcon name={icon} className={`text-[16px] ${accent ? "text-primary" : alert ? "text-md-error" : "text-md-on-surface-variant"}`} />
        <span className="text-[11px] text-md-on-surface-variant uppercase tracking-wider">{label}</span>
      </div>
      <div className="flex items-baseline gap-1.5">
        <span className={`text-xl font-bold ${accent ? "text-primary" : alert ? "text-md-error" : "text-md-on-surface"}`}>{value}</span>
      </div>
      {sub && <p className="text-[10px] text-md-on-surface-variant mt-0.5">{sub}</p>}
      {badge && <div className="mt-2">{badge}</div>}
    </div>
  );
}
