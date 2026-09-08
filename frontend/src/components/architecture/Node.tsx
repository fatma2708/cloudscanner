import type { FC, SVGProps } from "react";
import { serviceColor } from "@/components/dashboard/service-meta";
import { NODE_RADIUS } from "./layout";
import type { GraphNode } from "@/lib/types";

interface Props {
  node: GraphNode;
  x: number;
  y: number;
  isHovered: boolean;
  isDimmed: boolean;
  isSelected: boolean;
  onMouseEnter: () => void;
  onMouseLeave: () => void;
  onClick: () => void;
}

const KIND_ICONS: Record<string, FC<SVGProps<SVGSVGElement>>> = {
  vpc: VpcIcon,
  subnet: SubnetIcon,
  igw: IgwIcon,
  nat: NatIcon,
  eip: EipIcon,
  route_table: RouteIcon,
  route: RouteIcon,
  instance: InstanceIcon,
  rds: DbIcon,
  security_group: SgIcon,
  alb: AlbIcon,
  s3: S3Icon,
  ecs: EcsIcon,
  lambda: LambdaIcon,
  dynamodb: DbIcon,
  elasticache: DbIcon,
};

function truncate(label: string, max = 20): string {
  return label.length > max ? label.slice(0, max - 2) + "\u2026" : label;
}

export function ArchitectureNode({
  node,
  x,
  y,
  isHovered,
  isDimmed,
  isSelected,
  onMouseEnter,
  onMouseLeave,
  onClick,
}: Props) {
  const color = serviceColor(node.service, "#64748b");
  const Icon = KIND_ICONS[node.kind] ?? GenericIcon;
  const opacity = isDimmed ? 0.12 : 1;

  if (node.is_module) {
    return <ModuleNode
      node={node}
      x={x}
      y={y}
      color={color}
      isHovered={isHovered}
      isDimmed={isDimmed}
      isSelected={isSelected}
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
      onClick={onClick}
    />;
  }

  return (
    <g
      style={{ opacity, transition: "opacity 0.15s", cursor: "pointer" }}
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
      onClick={onClick}
    >
      {isHovered && (
        <circle
          cx={x}
          cy={y}
          r={NODE_RADIUS + 8}
          fill="none"
          stroke={color}
          strokeWidth={2}
          strokeOpacity={0.45}
        />
      )}

      <circle
        cx={x}
        cy={y}
        r={NODE_RADIUS}
        fill={`${color}26`}
        stroke={isSelected ? color : `${color}b3`}
        strokeWidth={isHovered || isSelected ? 2.5 : 1.6}
      />

      <Icon
        x={x - 8}
        y={y - 8}
        width={16}
        height={16}
        style={{ color, opacity: isDimmed ? 0.3 : 1 }}
        className="pointer-events-none"
      />

      <text
        x={x}
        y={y + NODE_RADIUS + 18}
        textAnchor="middle"
        className="select-none"
        style={{
          fontSize: "10px",
          fontWeight: 600,
          fill: "#1e293b",
          paintOrder: "stroke",
          stroke: "rgba(255,255,255,0.95)",
          strokeWidth: 3,
          strokeLinejoin: "round",
        }}
      >
        {truncate(node.displayName || node.label)}
      </text>
    </g>
  );
}

interface ModuleProps extends Props {
  color: string;
}

function ModuleNode({
  node,
  x,
  y,
  color,
  isHovered,
  isDimmed,
  isSelected,
  onMouseEnter,
  onMouseLeave,
  onClick,
}: ModuleProps) {
  const opacity = isDimmed ? 0.12 : 1;
  const unexpanded = node.expansion === "unexpanded";
  // Unexpanded modules are drawn dashed + hollow: they are declarations whose
  // contents were never inspected, not concrete resources.
  const strokeColor = unexpanded ? "#a855f7" : color;
  const badgeText =
    node.expansion === "unexpanded"
      ? "not expanded"
      : node.expansion === "partially_expanded"
        ? "partial"
        : `${node.resource_count ?? 0} res`;

  return (
    <g
      style={{ opacity, transition: "opacity 0.15s", cursor: "pointer" }}
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
      onClick={onClick}
    >
      {isHovered && (
        <rect
          x={x - NODE_RADIUS - 8}
          y={y - NODE_RADIUS - 8}
          width={(NODE_RADIUS + 8) * 2}
          height={(NODE_RADIUS + 8) * 2}
          rx={10}
          fill="none"
          stroke="#a855f7"
          strokeWidth={2}
          strokeOpacity={0.45}
        />
      )}

      <rect
        x={x - NODE_RADIUS}
        y={y - NODE_RADIUS}
        width={NODE_RADIUS * 2}
        height={NODE_RADIUS * 2}
        rx={10}
        fill={unexpanded ? "#faf5ff" : `${color}26`}
        stroke={isSelected ? strokeColor : `${strokeColor}b3`}
        strokeWidth={isHovered || isSelected ? 2.5 : 1.6}
        strokeDasharray={unexpanded ? "4 3" : undefined}
      />

      <PackageIcon
        x={x - 8}
        y={y - 8}
        width={16}
        height={16}
        style={{ color: strokeColor }}
        className="pointer-events-none"
      />

      <text
        x={x}
        y={y + NODE_RADIUS + 12}
        textAnchor="middle"
        className="select-none"
        style={{
          fontSize: "10px",
          fontWeight: 600,
          fill: "#1e293b",
          paintOrder: "stroke",
          stroke: "rgba(255,255,255,0.95)",
          strokeWidth: 3,
          strokeLinejoin: "round",
        }}
      >
        {truncate(node.displayName || node.label)}
      </text>
      <text
        x={x}
        y={y + NODE_RADIUS + 23}
        textAnchor="middle"
        className="select-none"
        style={{
          fontSize: "8.5px",
          fontWeight: 700,
          fill: unexpanded ? "#9333ea" : "#475569",
          paintOrder: "stroke",
          stroke: "rgba(255,255,255,0.95)",
          strokeWidth: 3,
          strokeLinejoin: "round",
        }}
      >
        {badgeText}
      </text>
    </g>
  );
}

function PackageIcon(p: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" {...p}>
      <path d="M21 8l-9-5-9 5v8l9 5 9-5V8z" />
      <path d="M3 8l9 5 9-5M12 13v9" />
    </svg>
  );
}

function VpcIcon(p: SVGProps<SVGSVGElement>) {
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" {...p}><rect x="3" y="4" width="18" height="12" rx="2" /><path d="M12 4v12M8 9h8M8 13h6" /></svg>;
}
function SubnetIcon(p: SVGProps<SVGSVGElement>) {
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" {...p}><rect x="3" y="7" width="18" height="10" rx="2" /><path d="M9 7v10M15 7v10" /></svg>;
}
function IgwIcon(p: SVGProps<SVGSVGElement>) {
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" {...p}><path d="M12 3v18M5 21h14M7 17l5-4 5 4M7 7l5 4 5-4" /></svg>;
}
function NatIcon(p: SVGProps<SVGSVGElement>) {
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" {...p}><path d="M4 12h10M18 12l-3-3M18 12l-3 3" /><circle cx="18" cy="12" r="2.5" /><path d="M4 5v14" /></svg>;
}
function EipIcon(p: SVGProps<SVGSVGElement>) {
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" {...p}><circle cx="12" cy="12" r="5" /><path d="M12 2v3M12 19v3M2 12h3M19 12h3" /></svg>;
}
function RouteIcon(p: SVGProps<SVGSVGElement>) {
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" {...p}><path d="M4 7h14a3 3 0 0 1 0 6H10" /><circle cx="7" cy="7" r="3" /><circle cx="10" cy="13" r="3" /></svg>;
}
function InstanceIcon(p: SVGProps<SVGSVGElement>) {
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" {...p}><rect x="4" y="4" width="16" height="16" rx="2" /><rect x="9" y="9" width="6" height="6" /></svg>;
}
function DbIcon(p: SVGProps<SVGSVGElement>) {
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" {...p}><ellipse cx="12" cy="5" rx="7" ry="3" /><path d="M5 5v14c0 1.66 3.13 3 7 3s7-1.34 7-3V5M5 12c0 1.66 3.13 3 7 3s7-1.34 7-3" /></svg>;
}
function SgIcon(p: SVGProps<SVGSVGElement>) {
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" {...p}><path d="M12 2 4 5.5v5C4 15 7.3 19 12 21c4.7-2 8-6 8-10.5v-5L12 2Z" /></svg>;
}
function AlbIcon(p: SVGProps<SVGSVGElement>) {
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" {...p}><rect x="9" y="3" width="6" height="6" rx="1" /><path d="M9 9v4a3 3 0 0 0 3 3h1M15 9v3" /><path d="M4 15h4v6H4zM16 15h4v6h-4z" /></svg>;
}
function S3Icon(p: SVGProps<SVGSVGElement>) {
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" {...p}><rect x="3" y="4" width="18" height="16" rx="2" /><path d="M3 9h18M3 15h18M9 9v6M15 9v6" /></svg>;
}
function EcsIcon(p: SVGProps<SVGSVGElement>) {
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" {...p}><rect x="2" y="6" width="20" height="12" rx="2" /><path d="M6 6V4a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v2M12 10v4M9 12h6" /></svg>;
}
function LambdaIcon(p: SVGProps<SVGSVGElement>) {
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" {...p}><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" /></svg>;
}
function GenericIcon(p: SVGProps<SVGSVGElement>) {
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" {...p}><rect x="3" y="3" width="18" height="18" rx="3" /><circle cx="12" cy="12" r="3" /></svg>;
}
