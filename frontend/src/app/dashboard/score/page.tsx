"use client";

import { useMemo } from "react";
import { useAnalysis } from "@/lib/analysis-context";
import { ErrorPanel } from "@/components/dashboard/states";
import { MaterialIcon } from "@/components/ui/material-icon";
import type { ScoreCategory } from "@/lib/types";

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4">
      <MaterialIcon name="grade" className="text-primary text-5xl" />
      <h2 className="text-xl font-bold text-md-on-surface">No score yet</h2>
      <p className="text-sm text-md-on-surface-variant">Analyze a repo first to see production readiness.</p>
    </div>
  );
}

function gradeColor(score: number | null): string {
  if (score === null) return "#9e9e9e";
  if (score >= 90) return "#10b981";
  if (score >= 75) return "#84cc16";
  if (score >= 60) return "#f59e0b";
  return "#ef4444";
}

function ScoreRing({ score }: { score: number | null }) {
  const r = 56;
  const c = 2 * Math.PI * r;
  const color = gradeColor(score);
  return (
    <div className="relative h-36 w-36 mx-auto">
      <svg viewBox="0 0 140 140" className="h-full w-full -rotate-90">
        <circle cx="70" cy="70" r={r} fill="none" stroke="#e8e0f0" strokeWidth="10" />
        <circle
          cx="70" cy="70" r={r} fill="none" stroke={color} strokeWidth="10"
          strokeLinecap="round" strokeDasharray={c} strokeDashoffset={score !== null ? c * (1 - score / 100) : c}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-2xl font-bold" style={{ color }}>{score !== null ? score.toFixed(1) : "N/A"}</span>
        <span className="text-[11px] text-md-on-surface-variant">/ 100</span>
      </div>
    </div>
  );
}

export default function ScorePage() {
  const { data, loading, error, repoUrl } = useAnalysis();

  const categories = useMemo(() => {
    if (!data) return [] as ScoreCategory[];
    return [...data.scores.categories].sort((a, b) => {
      if (a.score === null && b.score === null) return 0;
      if (a.score === null) return 1;
      if (b.score === null) return -1;
      return a.score - b.score;
    });
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

  const { scores } = data;
  const evidenceDimensions = scores.evidence_dimensions ?? [];
  const assessed = categories.filter((c) => c.score !== null);
  const unassessed = categories.filter((c) => c.score === null);
  const unassessedLabels = scores.unassessed_categories ?? unassessed.map((c) => c.label);
  const dimensionsAssessed = data.summary?.dimensions_assessed ?? assessed.length;
  const dimensionsTotal = data.summary?.dimensions_total ?? categories.length;

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-bold text-md-on-surface">Score</h1>
        <p className="text-xs text-md-on-surface-variant">
          Weighted readiness across {dimensionsAssessed} / {dimensionsTotal} dimensions assessed.
        </p>
      </div>

      <div className="bg-md-surface-container-low rounded-xl p-5 border border-md-outline-variant">
        <ScoreRing score={scores.overall} />
        <div className="flex items-center justify-center gap-3 mt-3">
          {scores.overall !== null ? (
            <div className="text-center">
              <span className="text-sm font-semibold text-md-on-surface">Assessed Score</span>
            </div>
          ) : (
            <div className="text-center">
              <span className="text-sm font-semibold text-md-on-surface-variant">Insufficient evidence</span>
            </div>
          )}
        </div>
        <div className="text-sm font-medium text-md-on-surface text-center mt-2">
          {dimensionsAssessed} / {dimensionsTotal} dimensions assessed
        </div>
        <div className="text-center mt-3">
          <p className="text-xs font-medium text-md-on-surface-variant uppercase tracking-wider mb-1">Production Readiness</p>
          {scores.overall !== null ? (
            <span className="text-sm font-semibold text-emerald-700 bg-emerald-50 px-3 py-1 rounded-full">Partial assessment — review dimensions below</span>
          ) : (
            <span className="text-sm font-semibold text-amber-700 bg-amber-50 px-3 py-1 rounded-full">Insufficient evidence — {dimensionsAssessed} of {dimensionsTotal} dimensions assessed</span>
          )}
        </div>
        <div className="flex items-center justify-center gap-3 mt-3">
          <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${
            scores.evidence_coverage === "high" ? "bg-emerald-100 text-emerald-700" :
            scores.evidence_coverage === "medium" ? "bg-amber-100 text-amber-700" :
            "bg-red-100 text-red-700"
          }`}>
            Evidence Coverage: {scores.evidence_coverage_pct.toFixed(0)}%
          </span>
          {scores.evidence_coverage === "low" && (
            <span className="text-[10px] text-md-on-surface-variant">
              Score may not reflect true posture — examine more resources
            </span>
          )}
        </div>
      </div>

      {evidenceDimensions.length > 0 && (
        <div className="bg-md-surface-container-low rounded-xl p-4 border border-md-outline-variant">
          <h2 className="text-sm font-semibold text-md-on-surface mb-3">Evidence Dimensions</h2>
          <div className="space-y-2">
            {evidenceDimensions.map((d) => (
              <div key={d.name} className="flex items-start gap-2 text-[11px]">
                {d.status === "available" && <MaterialIcon name="check_circle" className="text-[14px] text-emerald-600 shrink-0 mt-0.5" />}
                {d.status === "partial" && <MaterialIcon name="info" className="text-[14px] text-amber-600 shrink-0 mt-0.5" />}
                {d.status === "unavailable" && <MaterialIcon name="cancel" className="text-[14px] text-red-500 shrink-0 mt-0.5" />}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-md-on-surface">{d.name}</span>
                    {d.status === "available" && <span className="text-emerald-700 font-medium">Available</span>}
                    {d.status === "partial" && <span className="text-amber-700 font-medium">Partial</span>}
                    {d.status === "unavailable" && <span className="text-red-600 font-medium">Not available</span>}
                  </div>
                  <p className="text-md-on-surface-variant mt-0.5">{d.detail}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="bg-md-surface-container-low rounded-xl p-4 border border-md-outline-variant">
        <h2 className="text-sm font-semibold text-md-on-surface mb-3">Assessed Dimensions</h2>
        {assessed.length === 0 ? (
          <p className="text-xs text-md-on-surface-variant">No dimensions were assessed due to insufficient evidence.</p>
        ) : (
          <div className="space-y-4">
            {assessed.map((c) => (
              <div key={c.key}>
                <div className="mb-1 flex items-center justify-between text-xs">
                  <span className="font-medium text-md-on-surface">{c.label}</span>
                  <span className="text-md-on-surface-variant">
                    {c.score !== null ? `${c.score.toFixed(1)}/${c.max.toFixed(0)}` : ""}
                  </span>
                </div>
                <div className="h-2 w-full overflow-hidden rounded-full bg-md-surface-variant">
                  <div
                    className="h-full rounded-full transition-all"
                    style={{ width: c.score !== null ? `${(c.score / c.max) * 100}%` : "0%", backgroundColor: gradeColor(c.score) }}
                  />
                </div>
                {c.signals.length > 0 && (
                  <div className="mt-1 flex flex-wrap gap-1">
                    {c.signals.slice(0, 3).map((s) => (
                      <span key={s} className="text-[10px] text-md-on-surface-variant bg-md-surface-container rounded px-1.5 py-0.5">
                        {s}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {unassessed.length > 0 && (
        <div className="bg-md-surface-container-low rounded-xl p-4 border border-md-outline-variant">
          <h2 className="text-sm font-semibold text-md-on-surface mb-1">Insufficient Evidence</h2>
          <p className="text-[11px] text-md-on-surface-variant mb-3">
            These dimensions could not be scored because insufficient evidence was found.
          </p>
          <div className="space-y-2">
            {unassessed.map((c) => (
              <div key={c.key} className="flex items-center gap-2 text-xs">
                <MaterialIcon name="help_outline" className="text-[14px] text-md-on-surface-variant shrink-0" />
                <span className="text-md-on-surface-variant">{c.label}</span>
              </div>
            ))}
            {unassessedLabels.filter((l) => !unassessed.some((c) => c.label === l)).map((label) => (
              <div key={label} className="flex items-center gap-2 text-xs">
                <MaterialIcon name="help_outline" className="text-[14px] text-md-on-surface-variant shrink-0" />
                <span className="text-md-on-surface-variant">{label}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
