import type { GraphEdge } from "@/lib/types";
import type { Point } from "./layout";

interface Props {
  edge: GraphEdge;
  a: Point;
  b: Point;
  isActive: boolean;
  isDimmed: boolean;
}

function edgePath(a: Point, b: Point): string {
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  const len = Math.sqrt(dx * dx + dy * dy) || 1;
  const curvature = Math.min(len * 0.1, 28);
  const nx = -dy / len;
  const ny = dx / len;
  const mx = (a.x + b.x) / 2;
  const my = (a.y + b.y) / 2;
  return `M ${a.x} ${a.y} Q ${mx + nx * curvature} ${my + ny * curvature} ${b.x} ${b.y}`;
}

export function ArchitectureEdge({ a, b, isActive, isDimmed }: Props) {
  return (
    <path
      d={edgePath(a, b)}
      fill="none"
      stroke="rgba(71,85,105,0.55)"
      strokeWidth={isActive ? 2.4 : 1.2}
      strokeOpacity={isDimmed ? 0.12 : isActive ? 1 : 0.7}
      strokeLinecap="round"
      markerEnd={isActive ? "url(#arrow-active)" : "url(#arrow)"}
      style={{ transition: "stroke-opacity 0.15s, stroke-width 0.15s" }}
    />
  );
}
