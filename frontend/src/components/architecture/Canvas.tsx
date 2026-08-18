import { useMemo, useState, useCallback, useRef } from "react";
import type { Graph } from "@/lib/types";
import { computeLayout } from "./layout";
import { ArchitectureNode } from "./Node";
import { ArchitectureEdge } from "./Edge";
import { GroupRect } from "./GroupRect";
import { DetailsDrawer } from "./DetailsDrawer";
import { Toolbar } from "./Toolbar";

interface Props {
  graph: Graph;
  showSupporting: boolean;
  onToggleSupporting: (v: boolean) => void;
  summary: {
    total_block_count?: number;
    resource_count: number;
    data_source_count?: number;
  };
}

export function ArchitectureCanvas({ graph, showSupporting, onToggleSupporting, summary }: Props) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);
  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [searchQuery, setSearchQuery] = useState("");

  const visibleGraph = useMemo(() => {
    if (showSupporting) return graph;
    const filtered = graph.nodes.filter(
      (n) => n.layer === "primary" || n.layer === "supporting"
    );
    const ids = new Set(filtered.map((n) => n.id));
    return {
      ...graph,
      nodes: filtered,
      edges: graph.edges.filter((e) => ids.has(e.source) && ids.has(e.target)),
    };
  }, [graph, showSupporting]);

  const searchLower = searchQuery.toLowerCase();
  const matchingIds = useMemo(() => {
    if (!searchLower) return new Set<string>();
    return new Set(
      visibleGraph.nodes
        .filter(
          (n) =>
            n.displayName.toLowerCase().includes(searchLower) ||
            n.name.toLowerCase().includes(searchLower) ||
            n.type.toLowerCase().includes(searchLower) ||
            n.kind.toLowerCase().includes(searchLower) ||
            n.category.toLowerCase().includes(searchLower) ||
            n.label.toLowerCase().includes(searchLower)
        )
        .map((n) => n.id)
    );
  }, [visibleGraph.nodes, searchLower]);

  const { positions, groupBounds, viewBox } = useMemo(
    () => computeLayout(visibleGraph),
    [visibleGraph]
  );

  const connectedEdges = useMemo(() => {
    if (!hoveredNode) return new Set<number>();
    const set = new Set<number>();
    visibleGraph.edges.forEach((e, i) => {
      if (e.source === hoveredNode || e.target === hoveredNode) set.add(i);
    });
    return set;
  }, [hoveredNode, visibleGraph.edges]);

  const connectedNodes = useMemo(() => {
    if (!hoveredNode) return new Set<string>();
    const set = new Set<string>([hoveredNode]);
    visibleGraph.edges.forEach((e) => {
      if (e.source === hoveredNode) set.add(e.target);
      if (e.target === hoveredNode) set.add(e.source);
    });
    return set;
  }, [hoveredNode, visibleGraph.edges]);

  const handleHover = useCallback((id: string | null) => setHoveredNode(id), []);
  const handleClick = useCallback(
    (id: string) => setSelectedNode((prev) => (prev === id ? null : id)),
    []
  );
  const handleFit = useCallback(() => {
    setZoom(1);
    setPan({ x: 0, y: 0 });
  }, []);

  const dimmed = hoveredNode !== null;
  const focusedData = selectedNode
    ? visibleGraph.nodes.find((n) => n.id === selectedNode)
    : null;

  const vbParts = viewBox.split(" ").map(Number);

  const implementationCount = graph.nodes.filter((n) => n.layer === "implementation").length;
  const topologyCount = graph.topology_count ?? graph.nodes.length;
  const visibleCount = topologyCount - implementationCount;
  const groupCount = graph.groups.length;

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl font-bold text-gray-900">Architecture</h1>
          <p className="text-xs text-gray-500">
            {summary.total_block_count ?? summary.resource_count} Terraform blocks
            ({summary.resource_count} resources
            {summary.data_source_count ? ` \u00b7 ${summary.data_source_count} data sources` : ""})
            {" \u00b7 "}
            {groupCount} groups
          </p>
          <p className="text-[10px] text-gray-400 mt-0.5">
            {showSupporting
              ? `Showing all ${topologyCount} nodes including ${implementationCount} implementation resources.`
              : `${visibleCount} of ${topologyCount} nodes visible (${implementationCount} implementation resources hidden)`}
          </p>
        </div>
      </div>

      {/* Toolbar */}
      <div className="bg-white rounded-xl border border-gray-200 px-3 py-2">
        <Toolbar
          visibleCount={visibleGraph.nodes.length}
          edgeCount={visibleGraph.edges.length}
          searchQuery={searchQuery}
          onSearchChange={setSearchQuery}
          showSupporting={showSupporting}
          onToggleSupporting={onToggleSupporting}
          onZoomIn={() => setZoom((z) => Math.min(z * 1.25, 4))}
          onZoomOut={() => setZoom((z) => Math.max(z / 1.25, 0.25))}
          onFit={handleFit}
        />
      </div>

      {/* Canvas */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden relative">
        <svg
          ref={svgRef}
          viewBox={viewBox}
          className="w-full rounded-xl"
          style={{ height: "640px" }}
          preserveAspectRatio="xMidYMid meet"
        >
          <defs>
            <marker id="arrow" markerWidth="6" markerHeight="5" refX="12" refY="2.5" orient="auto">
              <path d="M0,0 L6,2.5 L0,5 L1.5,2.5 z" fill="rgba(100,116,139,0.3)" />
            </marker>
            <marker id="arrow-active" markerWidth="6" markerHeight="5" refX="12" refY="2.5" orient="auto">
              <path d="M0,0 L6,2.5 L0,5 L1.5,2.5 z" fill="rgba(100,116,139,0.8)" />
            </marker>
          </defs>

          <g transform={`translate(${pan.x},${pan.y}) scale(${zoom})`}>
            {/* Grid */}
            <g opacity={0.06}>
              {Array.from({ length: Math.ceil(vbParts[3] / 40) + 1 }, (_, i) => (
                <line
                  key={`gh${i}`}
                  x1={vbParts[0]}
                  y1={vbParts[1] + i * 40}
                  x2={vbParts[0] + vbParts[2]}
                  y2={vbParts[1] + i * 40}
                  stroke="#94a3b8"
                  strokeWidth={0.5}
                />
              ))}
              {Array.from({ length: Math.ceil(vbParts[2] / 40) + 1 }, (_, i) => (
                <line
                  key={`gv${i}`}
                  x1={vbParts[0] + i * 40}
                  y1={vbParts[1]}
                  x2={vbParts[0] + i * 40}
                  y2={vbParts[1] + vbParts[3]}
                  stroke="#94a3b8"
                  strokeWidth={0.5}
                />
              ))}
            </g>

            {/* Groups */}
            {[...groupBounds.entries()].map(([gId, bounds]) => {
              const group = visibleGraph.groups.find((g) => g.id === gId);
              if (!group) return null;
              return <GroupRect key={`g-${gId}`} group={group} bounds={bounds} />;
            })}

            {/* Edges */}
            {visibleGraph.edges.map((e, i) => {
              const a = positions.get(e.source);
              const b = positions.get(e.target);
              if (!a || !b) return null;
              return (
                <ArchitectureEdge
                  key={`e-${i}`}
                  edge={e}
                  a={a}
                  b={b}
                  isActive={connectedEdges.has(i)}
                  isDimmed={dimmed && !connectedEdges.has(i)}
                />
              );
            })}

            {/* Nodes */}
            {visibleGraph.nodes.map((n) => {
              const p = positions.get(n.id);
              if (!p) return null;
              const isHovered = hoveredNode === n.id;
              const isConnected = connectedNodes.has(n.id);
              const isSearchHit = matchingIds.has(n.id);

              return (
                <g key={n.id} filter={isSearchHit ? "url(#search-glow)" : undefined}>
                  <ArchitectureNode
                    node={n}
                    x={p.x}
                    y={p.y}
                    isHovered={isHovered}
                    isConnected={isConnected}
                    isDimmed={dimmed && !isConnected && !isSearchHit}
                    isSelected={selectedNode === n.id}
                    onMouseEnter={() => handleHover(n.id)}
                    onMouseLeave={() => handleHover(null)}
                    onClick={() => handleClick(n.id)}
                  />
                </g>
              );
            })}
          </g>
        </svg>

        {/* Details drawer */}
        {focusedData && (
          <DetailsDrawer node={focusedData} onClose={() => setSelectedNode(null)} />
        )}
      </div>

      {/* Legend */}
      <div className="flex flex-wrap items-center gap-2">
        {[
          { key: "network", label: "Network", color: "#3b82f6" },
          { key: "compute", label: "Compute", color: "#06b6d4" },
          { key: "storage", label: "Storage", color: "#10b981" },
          { key: "database", label: "Database", color: "#8b5cf6" },
          { key: "security", label: "Security", color: "#f59e0b" },
          { key: "observability", label: "Observability", color: "#ec4899" },
          { key: "serverless", label: "Serverless", color: "#eab308" },
          { key: "container", label: "Container", color: "#94a3b8" },
        ].map((item) => (
          <span
            key={item.key}
            className="inline-flex items-center gap-1.5 rounded-full border border-gray-200 bg-gray-50 px-2.5 py-1 text-[10px] text-gray-600"
          >
            <span
              className="h-1.5 w-1.5 rounded-full"
              style={{ backgroundColor: item.color }}
            />
            {item.label}
          </span>
        ))}
      </div>
    </div>
  );
}
