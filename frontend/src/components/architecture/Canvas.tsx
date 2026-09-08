import { useMemo, useState, useCallback, useRef, useEffect } from "react";
import type { MouseEvent as ReactMouseEvent, PointerEvent as ReactPointerEvent } from "react";
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
    module_count?: number;
    unexpanded_module_count?: number;
  };
}

export function ArchitectureCanvas({ graph, showSupporting, onToggleSupporting, summary }: Props) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);
  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [isPanning, setIsPanning] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const dragState = useRef<{
    startX: number;
    startY: number;
    panX: number;
    panY: number;
    moved: boolean;
  } | null>(null);
  const pointerCache = useRef(new Map<number, { x: number; y: number }>());
  const pinchState = useRef<{
    dist: number;
    zoom: number;
    pan: { x: number; y: number };
  } | null>(null);

  const MIN_ZOOM = 0.25;
  const MAX_ZOOM = 4;

  const clampZoom = useCallback((z: number) => Math.min(Math.max(z, MIN_ZOOM), MAX_ZOOM), []);

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
    setIsPanning(false);
  }, []);

  const cursorToViewBox = useCallback(
    (clientX: number, clientY: number) => {
      const svg = svgRef.current;
      if (!svg) return { x: 0, y: 0 };
      const rect = svg.getBoundingClientRect();
      const [minX, minY, vbW, vbH] = viewBox.split(" ").map(Number);
      return {
        x: minX + ((clientX - rect.left) / rect.width) * vbW,
        y: minY + ((clientY - rect.top) / rect.height) * vbH,
      };
    },
    [viewBox]
  );

  const wheelHandler = useCallback(
    (e: WheelEvent) => {
      e.preventDefault();
      const factor = e.deltaY < 0 ? 1.15 : 1 / 1.15;
      const nextZoom = clampZoom(zoom * factor);
      if (nextZoom === zoom) return;
      const { x: cx, y: cy } = cursorToViewBox(e.clientX, e.clientY);
      const f = nextZoom / zoom;
      setZoom(nextZoom);
      setPan((p) => ({ x: cx - (cx - p.x) * f, y: cy - (cy - p.y) * f }));
    },
    [zoom, clampZoom, cursorToViewBox]
  );

  useEffect(() => {
    const svg = svgRef.current;
    if (!svg) return;
    svg.addEventListener("wheel", wheelHandler, { passive: false });
    return () => svg.removeEventListener("wheel", wheelHandler);
  }, [wheelHandler]);

  const onPointerDown = (e: ReactPointerEvent<SVGSVGElement>) => {
    const target = e.target as Element;
    if (target.closest("[data-node-id]")) return;
    svgRef.current?.setPointerCapture?.(e.pointerId);
    pointerCache.current.set(e.pointerId, { x: e.clientX, y: e.clientY });
    if (pointerCache.current.size === 2) {
      dragState.current = null;
      const [p1, p2] = [...pointerCache.current.values()];
      pinchState.current = {
        dist: Math.hypot(p2.x - p1.x, p2.y - p1.y),
        zoom,
        pan,
      };
      return;
    }
    dragState.current = {
      startX: e.clientX,
      startY: e.clientY,
      panX: pan.x,
      panY: pan.y,
      moved: false,
    };
  };

  const onPointerMove = (e: ReactPointerEvent<SVGSVGElement>) => {
    const prev = pointerCache.current.get(e.pointerId);
    if (prev) pointerCache.current.set(e.pointerId, { x: e.clientX, y: e.clientY });

    if (pointerCache.current.size >= 2 && pinchState.current) {
      const pts = [...pointerCache.current.values()];
      const dist = Math.hypot(pts[1].x - pts[0].x, pts[1].y - pts[0].y);
      const mx = (pts[0].x + pts[1].x) / 2;
      const my = (pts[0].y + pts[1].y) / 2;
      const { x: cx, y: cy } = cursorToViewBox(mx, my);
      const { dist: startDist, zoom: startZoom, pan: startPan } = pinchState.current;
      if (startDist > 0) {
        const nextZoom = clampZoom(startZoom * (dist / startDist));
        const f = nextZoom / startZoom;
        setZoom(nextZoom);
        setPan({ x: cx - (cx - startPan.x) * f, y: cy - (cy - startPan.y) * f });
      }
      return;
    }

    const drag = dragState.current;
    if (!drag) return;
    const dx = e.clientX - drag.startX;
    const dy = e.clientY - drag.startY;
    if (!drag.moved && Math.hypot(dx, dy) < 3) return;
    if (!drag.moved) {
      drag.moved = true;
      setIsPanning(true);
    }
    setPan({ x: drag.panX + dx, y: drag.panY + dy });
  };

  const endPointer = (e: ReactPointerEvent<SVGSVGElement>) => {
    pointerCache.current.delete(e.pointerId);
    if (pointerCache.current.size < 2) pinchState.current = null;
    dragState.current = null;
    setIsPanning(false);
  };

  const handleBackgroundDoubleClick = (e: ReactMouseEvent<SVGSVGElement>) => {
    const target = e.target as Element;
    if (target.closest("[data-node-id]")) return;
    handleFit();
  };

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
            {summary.data_source_count ? ` \u00b7 ${summary.data_source_count} data sources` : ""}
            {summary.module_count ? ` \u00b7 ${summary.module_count} modules` : ""})
            {" \u00b7 "}
            {groupCount} groups
          </p>
          <p className="text-[10px] text-gray-400 mt-0.5">
            {showSupporting
              ? `Showing all ${topologyCount} nodes including ${implementationCount} implementation resources.`
              : `${visibleCount} of ${topologyCount} nodes visible (${implementationCount} implementation resources hidden)`}
          </p>
          <p className="text-[10px] text-gray-500 mt-0.5 font-medium">
            Drag to pan &middot; Scroll or pinch to zoom &middot; Double-click background to fit &middot; Hover or click a node for details
          </p>
        </div>
      </div>

      {/* Toolbar */}
      <div className="bg-white rounded-xl border border-gray-200 px-3 py-2">
        <Toolbar
          visibleCount={visibleGraph.nodes.length}
          edgeCount={visibleGraph.edges.length}
          zoom={zoom}
          searchQuery={searchQuery}
          onSearchChange={setSearchQuery}
          showSupporting={showSupporting}
          onToggleSupporting={onToggleSupporting}
          onZoomIn={() => setZoom((z) => clampZoom(z * 1.25))}
          onZoomOut={() => setZoom((z) => clampZoom(z / 1.25))}
          onFit={handleFit}
        />
      </div>

      {/* Canvas */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden relative">
        <svg
          ref={svgRef}
          viewBox={viewBox}
          className={`w-full rounded-xl ${isPanning ? "cursor-grabbing" : "cursor-grab"}`}
          style={{ height: "640px", touchAction: "none" }}
          preserveAspectRatio="xMidYMid meet"
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={endPointer}
          onPointerCancel={endPointer}
          onLostPointerCapture={endPointer}
          onDoubleClick={handleBackgroundDoubleClick}
        >
          <defs>
            <marker id="arrow" markerWidth="6" markerHeight="5" refX="12" refY="2.5" orient="auto">
              <path d="M0,0 L6,2.5 L0,5 L1.5,2.5 z" fill="rgba(71,85,105,0.55)" />
            </marker>
            <marker id="arrow-active" markerWidth="6" markerHeight="5" refX="12" refY="2.5" orient="auto">
              <path d="M0,0 L6,2.5 L0,5 L1.5,2.5 z" fill="rgba(15,23,42,0.9)" />
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
                <g key={n.id} data-node-id={n.id} filter={isSearchHit ? "url(#search-glow)" : undefined}>
                  <ArchitectureNode
                    node={n}
                    x={p.x}
                    y={p.y}
                    isHovered={isHovered}
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
        <span className="inline-flex items-center gap-1.5 rounded-full border border-purple-200 bg-purple-50 px-2.5 py-1 text-[10px] text-purple-700">
          <svg viewBox="0 0 24 24" className="h-3 w-3" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M21 8l-9-5-9 5v8l9 5 9-5V8z" />
            <path d="M3 8l9 5 9-5M12 13v9" />
          </svg>
          Terraform module
          <span className="text-purple-500">(dashed = not expanded)</span>
        </span>
      </div>
    </div>
  );
}
