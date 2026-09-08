import { MaterialIcon } from "@/components/ui/material-icon";
import type { Scores, Summary } from "@/lib/types";

export const EVIDENCE_COVERAGE_INCOMPLETE_THRESHOLD = 50;

export function unexpandedModuleCount(scores: Scores, summary?: Summary | null): number {
  if (scores.modules_unexpanded && scores.modules_unexpanded.length > 0) {
    return scores.modules_unexpanded.length;
  }
  if (summary?.unexpanded_module_count && summary.unexpanded_module_count > 0) {
    return summary.unexpanded_module_count;
  }
  const moduleContents = (scores.evidence_dimensions ?? []).find((d) =>
    d.name.toLowerCase().includes("module content")
  );
  if (moduleContents) {
    const matches = moduleContents.detail.match(/\bmodule\.[\w.-]+/g);
    if (matches && matches.length > 0) return matches.length;
  }
  return 0;
}

export function EvidenceCoverageBadge({
  coveragePct,
  unexpandedModules,
  threshold = EVIDENCE_COVERAGE_INCOMPLETE_THRESHOLD,
}: {
  coveragePct: number;
  unexpandedModules: number;
  threshold?: number;
}) {
  const pct = Number.isFinite(coveragePct) ? coveragePct : 100;
  if (pct >= threshold || unexpandedModules <= 0) return null;
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-medium text-amber-800">
      <MaterialIcon name="priority_high" className="text-[12px]" />
      Incomplete — {unexpandedModules} module{unexpandedModules === 1 ? "" : "s"} not inspected
    </span>
  );
}