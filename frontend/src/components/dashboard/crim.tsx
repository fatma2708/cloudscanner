import { MaterialIcon } from "@/components/ui/material-icon";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { formatConfidence } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { CrimCategory, CrimClassification, CrimSummary } from "@/lib/types";

export const CRIM_MODEL_LABEL = "CRIM-v4.2";

export const CRIM_CATEGORY_LABELS: Record<CrimCategory, string> = {
  NETWORK_SECURITY: "Network Security",
  DATA_SECURITY: "Data Security",
  OBSERVABILITY: "Observability",
};

export const CRIM_CATEGORY_STYLES: Record<CrimCategory, string> = {
  NETWORK_SECURITY: "bg-blue-100 text-blue-700 border-blue-500/30",
  DATA_SECURITY: "bg-emerald-100 text-emerald-700 border-emerald-500/30",
  OBSERVABILITY: "bg-amber-100 text-amber-700 border-amber-500/30",
};

const UNCERTAIN_LABEL = "ML classification uncertain";
const UNAVAILABLE_LABEL = "ML classification unavailable";

export function crimCategoryLabel(category: string | null | undefined): string | null {
  if (!category) return null;
  return CRIM_CATEGORY_LABELS[category as CrimCategory] ?? null;
}

export const CRIM_TOOLTIP_TEXT =
  "CRIM-v4.2 is a supervised ML model that classifies the security domain of the Terraform configuration. It is advisory and does not determine whether a finding exists.";

export function CrimInfoButton({ className }: { className?: string }) {
  return (
    <TooltipProvider delay={100}>
      <Tooltip>
        <TooltipTrigger
          aria-label="What is ML classification?"
          className={cn(
            "grid h-4 w-4 cursor-help place-items-center rounded-full text-violet-500 transition-colors hover:text-violet-700 focus-visible:outline-2 focus-visible:outline-violet-500",
            className,
          )}
        >
          <MaterialIcon name="info" className="text-[14px]" />
        </TooltipTrigger>
        <TooltipContent side="top">{CRIM_TOOLTIP_TEXT}</TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}

function modelLabel(model: string | undefined | null): string {
  return model || CRIM_MODEL_LABEL;
}

function categoryStyle(category: string | null | undefined): string {
  if (!category || !(category in CRIM_CATEGORY_STYLES)) return "bg-md-surface-variant text-md-on-surface-variant border-md-outline-variant";
  return CRIM_CATEGORY_STYLES[category as CrimCategory];
}

export function CrimInlineChip({
  classification,
  unavailable = false,
  alwaysShowUncertain = false,
  showModel = false,
}: {
  classification?: CrimClassification | null;
  unavailable?: boolean;
  alwaysShowUncertain?: boolean;
  showModel?: boolean;
}) {
  if (classification === undefined) return null;
  if (classification === null) {
    if (unavailable) {
      return (
        <span className="inline-flex items-center gap-1 rounded-[4px] border border-md-outline-variant bg-md-surface-variant/60 px-1.5 py-0.5 text-[10px] font-medium text-md-on-surface-variant/80">
          <span className="text-[8px] font-bold uppercase tracking-wider text-md-on-surface-variant/70">ML</span>
          unavailable
        </span>
      );
    }
    if (!alwaysShowUncertain) return null;
    return (
      <span className="inline-flex items-center gap-1 rounded-[4px] border border-md-outline-variant bg-md-surface-variant/60 px-1.5 py-0.5 text-[10px] font-medium text-md-on-surface-variant/80">
        <span className="text-[8px] font-bold uppercase tracking-wider text-md-on-surface-variant/70">ML</span>
        uncertain
      </span>
    );
  }

  if (classification.abstained || !classification.category) {
    return (
      <TooltipProvider delay={100}>
        <Tooltip>
          <TooltipTrigger
            aria-label={UNCERTAIN_LABEL}
            className="inline-flex items-center gap-1 rounded-[4px] border border-md-outline-variant bg-md-surface-variant/60 px-1.5 py-0.5 text-[10px] font-medium text-md-on-surface-variant/80 cursor-help"
          >
            <span className="text-[8px] font-bold uppercase tracking-wider text-md-on-surface-variant/70">ML</span>
            <span>uncertain · {formatConfidence(classification.confidence)}</span>
          </TooltipTrigger>
          <TooltipContent side="top">
            {UNCERTAIN_LABEL} — below the confidence threshold, CRIM does not assign a category.
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>
    );
  }

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-[4px] border px-1.5 py-0.5 text-[10px] font-bold",
        categoryStyle(classification.category),
      )}
    >
      <span className="text-[8px] font-bold uppercase tracking-wider text-violet-500">ML</span>
      {crimCategoryLabel(classification.category)}
      <span className="font-medium">· {formatConfidence(classification.confidence)}</span>
      {showModel && (
        <span className="font-medium text-md-on-surface-variant/80">· {modelLabel(classification.model)}</span>
      )}
    </span>
  );
}

export function CrimFindingBlock({
  classification,
  unavailable = false,
}: {
  classification?: CrimClassification | null;
  unavailable?: boolean;
}) {
  return (
    <div className="rounded-[4px] border border-violet-200/60 bg-violet-50/40 p-3">
      <div className="flex items-center gap-1.5">
        <p className="text-[11px] font-bold uppercase tracking-wider text-violet-700">ML classification</p>
        <CrimInfoButton />
      </div>

      {!classification ? (
        <p className="mt-1 text-[12px] font-medium text-md-on-surface-variant italic">
          {unavailable ? UNAVAILABLE_LABEL : UNCERTAIN_LABEL}
        </p>
      ) : classification.abstained || !classification.category ? (
        <div className="mt-1 space-y-0.5">
          <p className="text-[13px] font-medium text-md-on-surface-variant italic">{UNCERTAIN_LABEL}</p>
          <p className="text-[11px] text-md-on-surface-variant">
            Confidence {formatConfidence(classification.confidence)} · {modelLabel(classification.model)}
          </p>
        </div>
      ) : (
        <div className="mt-1 space-y-0.5">
          <p className="text-[13px] font-bold text-md-on-surface">{crimCategoryLabel(classification.category)}</p>
          <p className="text-[11px] text-md-on-surface-variant">
            Confidence {formatConfidence(classification.confidence)} · {modelLabel(classification.model)}
          </p>
        </div>
      )}
    </div>
  );
}

export function CrimSummaryChips({ summary }: { summary?: CrimSummary | null }) {
  if (!summary) return null;

  if (summary.ml_unavailable) {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-amber-50 px-2 py-0.5 text-[10px] font-medium text-amber-600">
        <MaterialIcon name="info_outline" className="text-[12px]" />
        ML classification unavailable
      </span>
    );
  }

  const classified = summary.classified ?? 0;
  const abstained = summary.abstained ?? 0;
  const unclassifiedCount = summary.unclassified ?? 0;

  return (
    <>
      <span className="inline-flex items-center gap-1 rounded-full bg-violet-100 px-2 py-0.5 text-[10px] font-bold text-violet-700">
        ML classification · {summary.name ?? CRIM_MODEL_LABEL}
      </span>
      <span className="inline-flex items-center gap-1 rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-medium text-emerald-700">
        Classified {classified}
      </span>
      <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-medium text-amber-700">
        Abstained {abstained}
      </span>
      {unclassifiedCount > 0 && (
        <span className="inline-flex items-center gap-1 rounded-full bg-md-surface-variant px-2 py-0.5 text-[10px] font-medium text-md-on-surface-variant">
          Not classified {unclassifiedCount}
        </span>
      )}
    </>
  );
}