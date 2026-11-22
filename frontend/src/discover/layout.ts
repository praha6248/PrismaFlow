import { forceCollide, forceLink, forceManyBody, forceSimulation, forceX, forceY, type SimulationNodeDatum } from "d3-force";
import type { MapEdge, MapNode } from "../types";
import { diameterFor } from "./kinds";

export interface Point {
  x: number;
  y: number;
}

interface SimNode extends SimulationNodeDatum {
  id: number;
  r: number;
}

const COMPOSE_SLOTS: Point[] = [
  { x: -132, y: -55 },
  { x: 125, y: 70 },
  { x: 150, y: -72 },
  { x: -118, y: 92 },
  { x: 4, y: -118 },
  { x: 6, y: 124 },
  { x: -210, y: 18 },
  { x: 214, y: -4 },
];

const BOUNDS = { left: -290, right: 290, top: -119, bottom: 176 };

export function composeSlot(index: number): Point {
  if (index < COMPOSE_SLOTS.length) return COMPOSE_SLOTS[index];
  const angle = index * 2.399963;
  const radius = 150 + 24 * Math.floor(index / COMPOSE_SLOTS.length);
  return { x: Math.cos(angle) * radius * 1.35, y: Math.sin(angle) * radius * 0.8 };
}

function hash(id: number): number {
  const s = Math.sin(id * 12.9898) * 43758.5453;
  return s - Math.floor(s);
}

export function layoutGraph(nodes: MapNode[], edges: MapEdge[]): Map<number, Point> {
  const positions = new Map<number, Point>();
  const placed = new Set<number>();
  for (const node of nodes) {
    if (node.is_root) {
      positions.set(node.id, { x: 0, y: 0 });
      placed.add(node.id);
    } else if (node.x !== null && node.y !== null) {
      positions.set(node.id, { x: node.x, y: node.y });
      placed.add(node.id);
    }
  }
  const pending = nodes.filter((n) => !placed.has(n.id));
  if (pending.length === 0) return relax(nodes, positions);

  const neighbours = new Map<number, number[]>();
  for (const edge of edges) {
    neighbours.set(edge.source_id, [...(neighbours.get(edge.source_id) ?? []), edge.target_id]);
    neighbours.set(edge.target_id, [...(neighbours.get(edge.target_id) ?? []), edge.source_id]);
  }

  const placedPoints = [...positions.values()];
  const centroid = {
    x: placedPoints.reduce((sum, p) => sum + p.x, 0) / placedPoints.length,
    y: placedPoints.reduce((sum, p) => sum + p.y, 0) / placedPoints.length,
  };
  const spreadIndex = new Map<string, number>();

  const simNodes: SimNode[] = nodes.map((node) => {
    const r = diameterFor(node) / 2;
    const fixed = positions.get(node.id);
    if (fixed) return { id: node.id, r, x: fixed.x, y: fixed.y, fx: fixed.x, fy: fixed.y };
    const anchors = (neighbours.get(node.id) ?? []).map((id) => positions.get(id)).filter(Boolean) as Point[];
    const anchor = anchors.length
      ? { x: anchors.reduce((s, p) => s + p.x, 0) / anchors.length, y: anchors.reduce((s, p) => s + p.y, 0) / anchors.length }
      : { x: 0, y: 0 };
    const key = `${Math.round(anchor.x)}:${Math.round(anchor.y)}`;
    const slot = spreadIndex.get(key) ?? 0;
    spreadIndex.set(key, slot + 1);
    const away = Math.hypot(anchor.x - centroid.x, anchor.y - centroid.y) > 20
      ? Math.atan2(anchor.y - centroid.y, anchor.x - centroid.x)
      : hash(node.id) * Math.PI * 2;
    const fan = [0, 0.9, -0.9, 1.7, -1.7, 2.5, -2.5][slot % 7];
    const angle = away + fan;
    const distance = r + 120;
    return { id: node.id, r, x: anchor.x + Math.cos(angle) * distance, y: anchor.y + Math.sin(angle) * distance * 0.8 };
  });

  const byId = new Map(simNodes.map((n) => [n.id, n]));
  const links = edges
    .filter((e) => byId.has(e.source_id) && byId.has(e.target_id))
    .map((e) => ({ source: e.source_id, target: e.target_id }));

  const simulation = forceSimulation(simNodes)
    .force(
      "link",
      forceLink<SimNode, { source: number; target: number }>(links)
        .id((d) => d.id)
        .distance((l) => (l.source as unknown as SimNode).r + (l.target as unknown as SimNode).r + 95)
        .strength(0.35),
    )
    .force("charge", forceManyBody<SimNode>().strength(-520).distanceMax(420))
    .force("collide", forceCollide<SimNode>((d) => d.r + 30).strength(1).iterations(3))
    .force("x", forceX<SimNode>(0).strength(0.02))
    .force("y", forceY<SimNode>(10).strength(0.04))
    .stop();

  const growth = Math.sqrt(Math.max(1, nodes.length / 7));
  const bounds = {
    left: BOUNDS.left * growth,
    right: BOUNDS.right * growth,
    top: BOUNDS.top * growth,
    bottom: BOUNDS.bottom * growth,
  };
  for (let i = 0; i < 360; i++) {
    simulation.tick();
    for (const n of simNodes) {
      if (n.fx !== undefined && n.fx !== null) continue;
      n.x = Math.max(bounds.left + n.r, Math.min(bounds.right - n.r, n.x ?? 0));
      n.y = Math.max(bounds.top + n.r, Math.min(bounds.bottom - n.r - 16, n.y ?? 0));
    }
  }

  for (const node of pending) {
    const sim = byId.get(node.id)!;
    positions.set(node.id, { x: Math.round(sim.x ?? 0), y: Math.round(sim.y ?? 0) });
  }
  return relax(nodes, positions);
}

export function relax(nodes: MapNode[], positions: Map<number, Point>, gap = 26): Map<number, Point> {
  const sims: SimNode[] = nodes.map((node) => {
    const p = positions.get(node.id)!;
    const r = diameterFor(node) / 2;
    return node.is_root ? { id: node.id, r, x: p.x, y: p.y, fx: p.x, fy: p.y } : { id: node.id, r, x: p.x, y: p.y };
  });
  const overlapping = () =>
    sims.some((a, i) => sims.some((b, j) => j > i && Math.hypot(a.x! - b.x!, a.y! - b.y!) < a.r + b.r + gap - 1));
  if (!overlapping()) return positions;
  const homes = new Map(sims.map((n) => [n.id, { x: n.x!, y: n.y! }]));
  const simulation = forceSimulation(sims)
    .force("collide", forceCollide<SimNode>((d) => d.r + gap / 2).strength(0.9).iterations(4))
    .force("x", forceX<SimNode>((d) => homes.get(d.id)!.x).strength(0.08))
    .force("y", forceY<SimNode>((d) => homes.get(d.id)!.y).strength(0.08))
    .stop();
  for (let i = 0; i < 200; i++) simulation.tick();
  const result = new Map<number, Point>();
  for (const n of sims) result.set(n.id, { x: Math.round(n.x ?? 0), y: Math.round(n.y ?? 0) });
  return result;
}
