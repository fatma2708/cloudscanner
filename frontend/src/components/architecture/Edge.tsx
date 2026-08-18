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

export function ArchitectureEdge({ edge: _edge, a, b, isActive, isDimmed }: Props) {
  return (
    <path
      d={edgePath(a, b)}
      fill="none"
      stroke="rgba(100,116,139,0.3)"
      strokeWidth={isActive ? 1.8 : 0.8}
      strokeOpacity={isDimmed ? 0.06 : isActive ? 1 : 0.3}
      markerEnd={isActive ? "url(#arrow-active)" : "url(#arrow)"}
      style={{ transition: "stroke-opacity 0.15s, stroke-width 0.15s" }}
    />
  );
}
