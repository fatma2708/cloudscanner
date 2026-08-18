import { AlertTriangle, CheckCircle, Shield, DollarSign } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import type { Recommendation } from "@/lib/types";
import { formatCurrency } from "@/lib/format";

function SeverityBadge({ severity }: { severity: string }) {
  const config: Record<string, { label: string; colors: string; icon: React.ReactNode }> = {
    critical: {
      label: "Must Fix",
      colors: "bg-[#d91536]/10 text-[#d91536] border-[#d91536]/30",
      icon: <AlertTriangle className="h-3 w-3" />,
    },
    high: {
      label: "Should Fix",
      colors: "bg-[#fa6f00]/10 text-[#fa6f00] border-[#fa6f00]/30",
      icon: <AlertTriangle className="h-3 w-3" />,
    },
    medium: {
      label: "Consider",
      colors: "bg-[#e7157b]/10 text-[#e7157b] border-[#e7157b]/30",
      icon: <CheckCircle className="h-3 w-3" />,
    },
    low: {
      label: "Nice to Have",
      colors: "bg-[#545b64]/10 text-[#545b64] border-[#545b64]/30",
      icon: <CheckCircle className="h-3 w-3" />,
    },
  };
  const c = config[severity] || config.low;
  return (
    <span className={`inline-flex items-center gap-1 rounded-[4px] border px-2 py-0.5 text-[11px] font-bold ${c.colors}`}>
      {c.icon}
      {c.label}
    </span>
  );
}

export function RecommendationCard({ rec, onSelect }: { rec: Recommendation; onSelect?: (rec: Recommendation) => void }) {
  return (
    <button
      type="button"
      onClick={() => onSelect?.(rec)}
      className="w-full rounded-[4px] border border-[#eaeded] bg-white p-4 text-left transition-colors hover:border-[#0972d3]/50"
    >
      <div className="flex items-start justify-between gap-3">
        <SeverityBadge severity={rec.severity} />
        {rec.savings_monthly > 0 && (
          <span className="text-[12px] font-bold text-[#146e5a]">
            {formatCurrency(rec.savings_monthly)}/mo
          </span>
        )}
      </div>
      <p className="mt-2 line-clamp-2 text-[13px] font-bold text-[#232f3e]">{rec.title}</p>
      <p className="mt-1 line-clamp-2 text-[12px] text-[#545b64]">{rec.description}</p>
    </button>
  );
}

export function RecommendationDetail({ rec }: { rec: Recommendation }) {
  return (
    <Card>
      <CardContent className="space-y-4 p-5">
        <div className="flex items-center justify-between gap-3">
          <SeverityBadge severity={rec.severity} />
          <span className="text-[12px] text-[#545b64]">
            {rec.category_label} · {rec.difficulty === "easy" ? "Easy to fix" : rec.difficulty === "medium" ? "Takes some work" : "More involved"}
          </span>
        </div>

        <div>
          <h3 className="text-[16px] font-bold text-[#232f3e]">{rec.title}</h3>
          <p className="mt-1 text-[13px] leading-relaxed text-[#545b64]">{rec.description}</p>
        </div>

        {rec.explanation.why && (
          <div className="rounded-[4px] border border-[#eaeded] bg-[#f9f9fb] p-4">
            <p className="text-[13px] font-bold text-[#232f3e]">Why this matters</p>
            <p className="mt-1 text-[13px] leading-relaxed text-[#545b64]">{rec.explanation.why}</p>
          </div>
        )}

        <div className="grid gap-3 sm:grid-cols-2">
          {rec.explanation.impact && (
            <div className="flex items-start gap-2 rounded-[4px] border border-[#eaeded] bg-[#f9f9fb] p-3">
              <CheckCircle className="mt-0.5 h-4 w-4 shrink-0 text-[#146e5a]" />
              <div>
                <p className="text-[12px] font-bold text-[#232f3e]">Impact</p>
                <p className="mt-0.5 text-[12px] text-[#545b64]">{rec.explanation.impact}</p>
              </div>
            </div>
          )}
          {rec.explanation.security && (
            <div className="flex items-start gap-2 rounded-[4px] border border-[#eaeded] bg-[#f9f9fb] p-3">
              <Shield className="mt-0.5 h-4 w-4 shrink-0 text-[#0972d3]" />
              <div>
                <p className="text-[12px] font-bold text-[#232f3e]">Security</p>
                <p className="mt-0.5 text-[12px] text-[#545b64]">{rec.explanation.security}</p>
              </div>
            </div>
          )}
          {rec.savings_monthly > 0 && (
            <div className="flex items-start gap-2 rounded-[4px] border border-[#146e5a]/30 bg-[#146e5a]/5 p-3">
              <DollarSign className="mt-0.5 h-4 w-4 shrink-0 text-[#146e5a]" />
              <div>
                <p className="text-[12px] font-bold text-[#232f3e]">Cost savings</p>
                <p className="mt-0.5 text-[12px] font-bold text-[#146e5a]">
                  Save {formatCurrency(rec.savings_monthly)}/mo ({formatCurrency(rec.savings_monthly * 12)}/year)
                </p>
              </div>
            </div>
          )}
        </div>

        {rec.implementation.length > 0 && (
          <div>
            <p className="text-[13px] font-bold text-[#232f3e]">How to fix this</p>
            <ol className="mt-2 space-y-2">
              {rec.implementation.map((step, i) => (
                <li key={i} className="flex gap-3 text-[13px] leading-relaxed">
                  <span className="grid h-5 w-5 shrink-0 place-items-center rounded-full bg-[#0972d3] text-[11px] font-bold text-white">
                    {i + 1}
                  </span>
                  <span className="text-[#545b64]">{step}</span>
                </li>
              ))}
            </ol>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
