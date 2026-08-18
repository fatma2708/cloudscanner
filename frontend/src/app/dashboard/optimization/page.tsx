"use client";

import { useState } from "react";
import { useAnalysis, OPTIMIZATION_MODES } from "@/lib/analysis-context";
import { ErrorPanel } from "@/components/dashboard/states";
import { HclBlock } from "@/components/hcl/hcl-block";
import { formatCurrency } from "@/lib/format";
import { MaterialIcon } from "@/components/ui/material-icon";
import type { Recommendation } from "@/lib/types";

function getSeverityBadge(severity: string) {
  switch (severity) {
    case "critical":
      return "bg-md-error-container text-md-on-error-container";
    case "high":
      return "bg-md-error-container text-md-on-error-container";
    case "medium":
      return "bg-md-tertiary-container text-md-on-tertiary-container";
    default:
      return "bg-md-surface-variant text-md-on-surface-variant";
  }
}

function getSeverityLabel(severity: string) {
  switch (severity) {
    case "critical": return "High Impact";
    case "high": return "High Impact";
    case "medium": return "Medium";
    default: return "Low";
  }
}

export default function OptimizationPage() {
  const { data, loading, error, mode, setMode, repoUrl } = useAnalysis();
  const [selected, setSelected] = useState<Recommendation | null>(null);
  const [copied, setCopied] = useState(false);

  if (error && !data) return <ErrorPanel message={error} />;
  if (!repoUrl || (!data && !loading)) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4">
        <MaterialIcon name="auto_fix_high" className="text-primary text-5xl" />
        <h2 className="text-xl font-bold text-md-on-surface">No analysis yet</h2>
        <p className="text-sm text-md-on-surface-variant">Go to Overview and paste a GitHub repo URL to get started.</p>
      </div>
    );
  }
  if (loading && !data) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-md-primary-container/30 border-t-md-primary" />
      </div>
    );
  }
  if (!data) return null;

  const { recommendations, optimization } = data;
  const activeRec = selected ?? recommendations[0];

  const handleCopy = () => {
    const code = optimization.code;
    navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const modeIcons: Record<string, string> = {
    balanced: "balance",
    "lowest-cost": "trending_down",
    reliability: "shield",
    "lowest-latency": "bolt",
    "startup-budget": "rocket_launch",
    "lowest-carbon": "eco",
    security: "lock",
  };

  return (
    <div className="flex flex-col h-[calc(100vh-56px)] -mt-4 -mx-4 md:-mx-6">
      <div className="bg-md-surface border-b border-md-outline-variant py-2.5 px-4 z-10 shrink-0">
        <div className="flex items-center gap-2 overflow-x-auto hide-scrollbar pb-1">
          {Object.entries(OPTIMIZATION_MODES).map(([key, m]) => (
            <button
              key={key}
              onClick={() => setMode(key)}
              className={`whitespace-nowrap px-3 py-1.5 rounded-full border font-medium text-xs flex items-center gap-1.5 transition-colors ${
                mode === key
                  ? "border-primary bg-md-primary-container text-md-on-primary-container"
                  : "border-md-outline-variant text-md-on-surface-variant hover:bg-md-surface-container-high"
              }`}
            >
              <MaterialIcon name={modeIcons[key] || "settings"} className="text-[16px]" />
              {m.label}
            </button>
          ))}
        </div>
      </div>

      <div className="flex flex-col md:flex-row flex-1 overflow-hidden">
        <div className="h-[35%] md:h-full md:w-1/3 border-b md:border-b-0 md:border-r border-md-outline-variant overflow-y-auto bg-md-surface-container-lowest">
          {recommendations.map((rec) => (
            <div
              key={rec.key + (rec.target[0] || "")}
              onClick={() => setSelected(rec)}
              className={`p-3 border-l-3 cursor-pointer transition-colors border-b border-md-outline-variant ${
                activeRec?.key === rec.key && activeRec?.target[0] === rec.target[0]
                  ? "border-l-primary bg-md-secondary-container/20"
                  : "border-l-transparent hover:bg-md-surface-container-high"
              }`}
            >
              <div className="flex justify-between items-start mb-1">
                <span className={`${getSeverityBadge(rec.severity)} text-[9px] font-bold px-1.5 py-0.5 rounded uppercase tracking-wider`}>
                  {getSeverityLabel(rec.severity)}
                </span>
                {rec.savings_monthly > 0 && (
                  <span className="text-primary font-bold text-xs">
                    {formatCurrency(rec.savings_monthly)}/mo
                  </span>
                )}
              </div>
              <h3 className="font-semibold text-md-on-surface text-sm">{rec.title}</h3>
              {rec.target[0] && (
                <p className="text-[11px] font-mono text-md-on-surface-variant truncate mt-1">{rec.target[0]}</p>
              )}
            </div>
          ))}
        </div>

        <div className="h-[65%] md:h-full md:w-2/3 overflow-y-auto bg-md-background">
          {activeRec && (
            <div className="p-5 md:p-6 max-w-3xl mx-auto">
              <div className="mb-5">
                <div className="flex items-center gap-2 mb-2">
                  <span className={`${getSeverityBadge(activeRec.severity)} text-[10px] font-bold px-2 py-0.5 rounded uppercase tracking-wider`}>
                    {getSeverityLabel(activeRec.severity)}
                  </span>
                  {activeRec.savings_monthly > 0 && (
                    <span className="text-primary text-[11px] font-medium flex items-center gap-1">
                      <MaterialIcon name="savings" className="text-[13px]" />
                      Save {formatCurrency(activeRec.savings_monthly)}/mo
                    </span>
                  )}
                </div>
                <h2 className="font-bold text-lg text-md-on-surface">{activeRec.title}</h2>
                <div className="flex items-center gap-3 text-xs text-md-on-surface-variant mt-1.5">
                  {activeRec.target[0] && (
                    <span className="flex items-center gap-1">
                      <MaterialIcon name="tag" className="text-[14px]" />
                      {activeRec.target[0]}
                    </span>
                  )}
                  {activeRec.source_file && (
                    <span className="flex items-center gap-1">
                      <MaterialIcon name="description" className="text-[14px]" />
                      {activeRec.source_file}{activeRec.source_line ? `:${activeRec.source_line}` : ""}
                    </span>
                  )}
                </div>
              </div>

              {activeRec.explanation.why && (
                <div className="bg-md-surface-container-low rounded-lg p-4 mb-5 border border-md-outline-variant">
                  <p className="text-xs text-md-on-surface-variant leading-relaxed">
                    {activeRec.explanation.why}
                  </p>
                </div>
              )}

              <div>
                <div className="flex items-center justify-between mb-2">
                  <h3 className="text-sm font-semibold text-md-on-surface flex items-center gap-1.5">
                    <MaterialIcon name="code" className="text-primary text-[16px]" />
                    Suggested Fix
                  </h3>
                  {optimization.code_validated === false && (
                    <span className="text-[10px] px-2 py-0.5 rounded bg-amber-100 text-amber-700 font-medium">
                      Requires review
                    </span>
                  )}
                  <button
                    onClick={handleCopy}
                    className="text-xs text-md-on-surface-variant hover:text-primary transition-colors flex items-center gap-1"
                  >
                    <MaterialIcon name={copied ? "check" : "content_copy"} className="text-[14px]" />
                    {copied ? "Copied" : "Copy"}
                  </button>
                </div>
                <div className="bg-md-inverse-surface rounded-lg overflow-hidden text-sm">
                  <div className="px-3 py-1.5 border-b border-md-outline-variant/20 flex items-center gap-1.5 text-md-inverse-on-surface/60 text-[11px]">
                    <MaterialIcon name="description" className="text-[13px]" />
                    {activeRec.source_file || "main.tf"}
                  </div>
                  <div className="p-3 overflow-x-auto">
                    <HclBlock code={optimization.code} maxHeight={400} />
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
