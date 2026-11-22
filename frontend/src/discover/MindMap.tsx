import {
  ReactFlow,
  useNodesState,
  useReactFlow,
  type Edge,
  type EdgeTypes,
  type NodeMouseHandler,
  type NodeTypes,
  type OnNodeDrag,
} from "@xyflow/react";
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import type { DiscoverStage as Stage, Graph, MapNode } from "../types";
import { BubbleNode, type BubbleFlowNode } from "./BubbleNode";
import { CenterEdge } from "./CenterEdge";
import { diameterFor } from "./kinds";
import { layoutGraph, type Point } from "./layout";

const nodeTypes: NodeTypes = { bubble: BubbleNode };
const edgeTypes: EdgeTypes = { center: CenterEdge };

const MOCK_CARD_HEIGHT = 448;
const ROOT_Y: Record<Stage, number> = { compose: 221, expanding: 221, select: 249 };
const SAFE_AREAS: Record<Stage, { top: number; bottom: number; side: number }> = {
  compose: { top: 118, bottom: 70, side: 20 },
  expanding: { top: 118, bottom: 70, side: 20 },
  select: { top: 124, bottom: 14, side: 20 },
};

interface Props {
  graph: Graph;
  stage: Stage;
  focusedId: number | null;
  onFocus: (id: number | null) => void;
  onToggleStar: (node: MapNode) => void;
  onPositions: (positions: { id: number; x: number; y: number }[]) => void;
  rightInset: number;
}

function useElementSize<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  const [size, setSize] = useState({ width: 0, height: 0 });
  useLayoutEffect(() => {
    const element = ref.current;
    if (!element) return;
    const update = () => setSize({ width: element.clientWidth, height: element.clientHeight });
    update();
    const observer = new ResizeObserver(update);
    observer.observe(element);
    return () => observer.disconnect();
  }, []);
  return [ref, size] as const;
}

function unitPx(): number {
  return Math.min(window.innerWidth / 672, window.innerHeight / 477);
}

export function MindMap({ graph, stage, focusedId, onFocus, onToggleStar, onPositions, rightInset }: Props) {
  const [containerRef, size] = useElementSize<HTMLDivElement>();
  const { setViewport } = useReactFlow();
  const [nodes, setNodes, onNodesChange] = useNodesState<BubbleFlowNode>([]);
  const positions = useRef(new Map<number, Point>());
  const seen = useRef(new Set<number>());
  const firstRender = useRef(true);
  const animationTimer = useRef<number | undefined>(undefined);

  const laidOut = useMemo(() => {
    const withKnown = graph.nodes.map((n) => {
      const known = positions.current.get(n.id);
      return known ? { ...n, x: known.x, y: known.y } : n;
    });
    return layoutGraph(withKnown, graph.edges);
  }, [graph]);

  useEffect(() => {
    const changed: { id: number; x: number; y: number }[] = [];
    const moved = new Set<number>();
    for (const node of graph.nodes) {
      const point = laidOut.get(node.id)!;
      const known = positions.current.get(node.id);
      if (known && (known.x !== point.x || known.y !== point.y)) moved.add(node.id);
      const stored = known ?? (node.x !== null && node.y !== null ? { x: node.x, y: node.y } : null);
      if (!node.is_root && (!stored || stored.x !== point.x || stored.y !== point.y)) {
        changed.push({ id: node.id, ...point });
      }
      positions.current.set(node.id, point);
    }
    for (const id of [...positions.current.keys()]) {
      if (!graph.nodes.some((n) => n.id === id)) positions.current.delete(id);
    }
    if (changed.length) onPositions(changed);
    if (moved.size) {
      window.clearTimeout(animationTimer.current);
      animationTimer.current = window.setTimeout(
        () => setNodes((current) => current.map((n) => (n.className ? { ...n, className: undefined } : n))),
        800,
      );
    }

    let order = 0;
    setNodes(
      graph.nodes.map((node) => {
        const point = positions.current.get(node.id)!;
        const diameter = diameterFor(node);
        const fresh = !seen.current.has(node.id);
        const delay = fresh && !firstRender.current ? order++ * 140 : 0;
        return {
          id: String(node.id),
          type: "bubble",
          position: { x: point.x - diameter / 2, y: point.y - diameter / 2 },
          width: diameter,
          height: diameter,
          className: moved.has(node.id) ? "pf-animate" : undefined,
          draggable: true,
          selectable: false,
          data: {
            node,
            fresh,
            delay,
            focused: node.id === focusedId,
            showBadge: stage === "select",
            onToggleStar,
          },
        } satisfies BubbleFlowNode;
      }),
    );
    for (const node of graph.nodes) seen.current.add(node.id);
    firstRender.current = false;
  }, [graph, laidOut, focusedId, stage, onToggleStar, onPositions, setNodes]);

  const edges: Edge[] = useMemo(
    () =>
      graph.edges.map((edge) => ({
        id: `e${edge.id}`,
        source: String(edge.source_id),
        target: String(edge.target_id),
        type: "center",
        selectable: false,
        focusable: false,
        className: "pf-fade",
      })),
    [graph.edges],
  );

  const nodeCount = graph.nodes.length;
  const lastViewport = useRef("");
  useEffect(() => {
    if (!size.width || !size.height) return;
    const u = unitPx();
    let minX = 0;
    let maxX = 0;
    let minY = 0;
    let maxY = 0;
    for (const node of graph.nodes) {
      const point = positions.current.get(node.id);
      if (!point) continue;
      const r = diameterFor(node) / 2;
      minX = Math.min(minX, point.x - r - 30);
      maxX = Math.max(maxX, point.x + r + 30);
      minY = Math.min(minY, point.y - r);
      maxY = Math.max(maxY, point.y + r + 22);
    }
    const safe = SAFE_AREAS[stage];
    const width = size.width - rightInset * u;
    const anchorX = width / 2;
    const anchorY = ROOT_Y[stage] * u + (size.height - MOCK_CARD_HEIGHT * u) / 2;
    const fits =
      anchorX + minX * u >= safe.side * u &&
      anchorX + maxX * u <= width - safe.side * u &&
      anchorY + minY * u >= safe.top * u &&
      anchorY + maxY * u <= size.height - safe.bottom * u;
    let viewport = { x: anchorX, y: anchorY, zoom: u };
    if (!fits) {
      const availW = width - 2 * safe.side * u;
      const availH = size.height - (safe.top + safe.bottom) * u;
      const zoom = Math.min(u, availW / (maxX - minX), availH / (maxY - minY));
      viewport = {
        x: width / 2 - ((minX + maxX) / 2) * zoom,
        y: safe.top * u + availH / 2 - ((minY + maxY) / 2) * zoom,
        zoom,
      };
    }
    const key = `${Math.round(viewport.x)}:${Math.round(viewport.y)}:${viewport.zoom.toFixed(4)}`;
    if (key === lastViewport.current) return;
    const animate = lastViewport.current !== "";
    lastViewport.current = key;
    setViewport(viewport, animate ? { duration: 650 } : undefined);
  }, [size, stage, nodeCount, graph.nodes, rightInset, setViewport]);

  const onNodeClick: NodeMouseHandler<BubbleFlowNode> = useCallback(
    (_, node) => onFocus(Number(node.id)),
    [onFocus],
  );

  const onNodeDragStop: OnNodeDrag<BubbleFlowNode> = useCallback(
    (_, node) => {
      const diameter = node.width ?? diameterFor(node.data.node);
      const point = { x: Math.round(node.position.x + diameter / 2), y: Math.round(node.position.y + diameter / 2) };
      positions.current.set(Number(node.id), point);
      onPositions([{ id: Number(node.id), ...point }]);
    },
    [onPositions],
  );

  return (
    <div ref={containerRef} className="absolute inset-0">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        onNodesChange={onNodesChange}
        onNodeClick={onNodeClick}
        onNodeDragStop={onNodeDragStop}
        onPaneClick={() => onFocus(null)}
        nodesConnectable={false}
        elementsSelectable={false}
        zoomOnDoubleClick={false}
        minZoom={0.3}
        maxZoom={6}
        proOptions={{ hideAttribution: true }}
        style={{ background: "transparent" }}
      />
    </div>
  );
}
