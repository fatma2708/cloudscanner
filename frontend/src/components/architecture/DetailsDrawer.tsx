import type { GraphNode } from "@/lib/types";
import { serviceColor } from "@/components/dashboard/service-meta";

interface Props {
  node: GraphNode;
  onClose: () => void;
}

export function DetailsDrawer({ node, onClose }: Props) {
  const cost = node.metrics.monthly_cost;
  const color = serviceColor(node.service, "#64748b");

  const costDisplay =
    node.is_module && node.expansion === "unexpanded"
      ? "Not quantified (module not expanded)"
      : cost > 0
        ? `$${cost.toFixed(2)}`
        : node.metrics.cost_classification === "usage_based"
          ? "Usage-based"
          : "Not estimated";

  return (
    <div className="absolute right-4 top-14 w-72 rounded-xl border border-gray-200 bg-white shadow-xl overflow-hidden z-10">
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100">
        <div className="flex items-center gap-2 min-w-0">
          <span
            className="h-3 w-3 rounded-full shrink-0"
            style={{ backgroundColor: color }}
          />
          <span className="font-semibold text-gray-900 text-sm truncate">
            {node.displayName || node.label}
          </span>
        </div>
        <button
          onClick={onClose}
          className="text-gray-400 hover:text-gray-600 ml-2 shrink-0"
          aria-label="Close details"
        >
          <svg viewBox="0 0 16 16" className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="1.5">
            <path d="M4 4l8 8M12 4l-8 8" />
          </svg>
        </button>
      </div>

      <div className="p-4 space-y-2.5 text-[11px]">
        {node.is_module ? (
          <>
            <Row label="Terraform address" value={node.resourceAddress} />
            <Row label="Source" value={node.module_source || "unavailable"} />
            {node.module_version && <Row label="Version" value={node.module_version} />}
            <Row label="Source type" value={node.source_type ?? "unknown"} />
            <Row
              label="Expansion"
              value={
                node.expansion === "unexpanded"
                  ? "Not expanded"
                  : node.expansion === "partially_expanded"
                    ? "Partially expanded"
                    : "Expanded"
              }
            />
            {typeof node.resource_count === "number" && (
              <Row label="Resources found" value={String(node.resource_count)} />
            )}
            <Row label="Monthly cost" value={costDisplay} />
            {node.note && (
              <p className="text-[10px] text-gray-500 italic leading-relaxed pt-1 border-t border-gray-100">
                {node.note}
              </p>
            )}
          </>
        ) : (
          <>
            <Row label="Name" value={node.name} />
            <Row label="Type" value={node.type} />
            <Row label="Category" value={node.category} />
            <Row label="Service" value={node.service} />
            <Row label="Monthly cost" value={costDisplay} />
            {node.metrics.cost_confidence && node.metrics.cost_confidence !== "unknown" && (
              <Row label="Confidence" value={node.metrics.cost_confidence} />
            )}
            {node.resourceAddress && (
              <Row label="Terraform address" value={node.resourceAddress} />
            )}
            {node.region && <Row label="Region" value={node.region} />}
            <Row label="Layer" value={node.layer} />
          </>
        )}
      </div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-2">
      <span className="text-gray-500 shrink-0">{label}</span>
      <span className="font-medium text-gray-900 text-right truncate">{value}</span>
    </div>
  );
}
