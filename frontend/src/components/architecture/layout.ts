import type { Graph, GraphNode } from "@/lib/types";

export interface Point {
  x: number;
  y: number;
}

export interface GroupBounds {
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface LayoutResult {
  positions: Map<string, Point>;
  groupBounds: Map<string, GroupBounds>;
  viewBox: string;
}

const NODE_RADIUS = 22;
const NODE_SPACING_X = 140;
const GROUP_PADDING = 44;
const LABEL_OFFSET = 16;

export function computeLayout(graph: Graph): LayoutResult {
  const positions = new Map<string, Point>();
  const W = 1600;
  const H = 1000;

  const nodes = graph.nodes;
  if (nodes.length === 0) {
    return { positions, groupBounds: new Map(), viewBox: "0 0 400 300" };
  }

  const adj = new Map<string, string[]>();
  const inDeg = new Map<string, number>();
  for (const n of nodes) {
    adj.set(n.id, []);
    inDeg.set(n.id, 0);
  }
  for (const e of graph.edges) {
    if (adj.has(e.source) && adj.has(e.target)) {
      adj.get(e.source)!.push(e.target);
      inDeg.set(e.target, (inDeg.get(e.target) ?? 0) + 1);
    }
  }

  const layerMap = new Map<string, number>();
  const queue: string[] = [];
  for (const n of nodes) {
    if ((inDeg.get(n.id) ?? 0) === 0) {
      queue.push(n.id);
      layerMap.set(n.id, 0);
    }
  }

  if (queue.length === 0) {
    for (const n of nodes) {
      const depth = n.layer === "primary" ? 0 : n.layer === "supporting" ? 1 : 2;
      layerMap.set(n.id, depth);
      if (depth === 0) queue.push(n.id);
    }
  }

  while (queue.length > 0) {
    const cur = queue.shift()!;
    const curLayer = layerMap.get(cur)!;
    for (const next of adj.get(cur) ?? []) {
      const nextLayer = curLayer + 1;
      if (!layerMap.has(next) || layerMap.get(next)! < nextLayer) {
        layerMap.set(next, nextLayer);
        queue.push(next);
      }
    }
  }

  for (const n of nodes) {
    if (!layerMap.has(n.id)) {
      layerMap.set(n.id, n.layer === "primary" ? 0 : n.layer === "supporting" ? 1 : 2);
    }
  }

  const layers = new Map<number, GraphNode[]>();
  for (const n of nodes) {
    const layer = layerMap.get(n.id)!;
    if (!layers.has(layer)) layers.set(layer, []);
    layers.get(layer)!.push(n);
  }

  const sortedLayers = [...layers.keys()].sort((a, b) => a - b);
  const totalLayers = sortedLayers.length;
  const layerHeight = H / (totalLayers + 1);

  for (let li = 0; li < sortedLayers.length; li++) {
    const layerIdx = sortedLayers[li];
    const nodesInLayer = layers.get(layerIdx)!;
    const totalWidth = nodesInLayer.length * NODE_SPACING_X;
    const startX = (W - totalWidth) / 2 + NODE_SPACING_X / 2;
    const y = (li + 1) * layerHeight;

    nodesInLayer.forEach((n, ni) => {
      positions.set(n.id, { x: startX + ni * NODE_SPACING_X, y });
    });
  }

  const groups = new Map<string, GraphNode[]>();
  for (const n of nodes) {
    const g = n.group || "__root__";
    if (!groups.has(g)) groups.set(g, []);
    groups.get(g)!.push(n);
  }

  const groupBounds = new Map<string, GroupBounds>();
  for (const [gId, gNodes] of groups) {
    if (gId === "__root__" || gNodes.length <= 1) continue;
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    for (const n of gNodes) {
      const p = positions.get(n.id);
      if (!p) continue;
      minX = Math.min(minX, p.x);
      minY = Math.min(minY, p.y);
      maxX = Math.max(maxX, p.x);
      maxY = Math.max(maxY, p.y);
    }
    if (minX < Infinity) {
      groupBounds.set(gId, {
        x: minX - GROUP_PADDING,
        y: minY - GROUP_PADDING - 14,
        w: maxX - minX + GROUP_PADDING * 2,
        h: maxY - minY + GROUP_PADDING * 2 + LABEL_OFFSET * 2,
      });
    }
  }

  let bMinX = Infinity, bMinY = Infinity, bMaxX = -Infinity, bMaxY = -Infinity;
  for (const p of positions.values()) {
    bMinX = Math.min(bMinX, p.x);
    bMinY = Math.min(bMinY, p.y);
    bMaxX = Math.max(bMaxX, p.x);
    bMaxY = Math.max(bMaxY, p.y);
  }
  for (const b of groupBounds.values()) {
    bMinX = Math.min(bMinX, b.x);
    bMinY = Math.min(bMinY, b.y);
    bMaxX = Math.max(bMaxX, b.x + b.w);
    bMaxY = Math.max(bMaxY, b.y + b.h);
  }
  const pad = 70;
  const vbW = Math.max(bMaxX - bMinX + pad * 2, 400);
  const vbH = Math.max(bMaxY - bMinY + pad * 2, 300);

  return {
    positions,
    groupBounds,
    viewBox: `${bMinX - pad} ${bMinY - pad} ${vbW} ${vbH}`,
  };
}

export { NODE_RADIUS, NODE_SPACING_X };
