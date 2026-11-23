import { BaseEdge, useInternalNode, type EdgeProps } from "@xyflow/react";
import { memo } from "react";

function centerOf(node: ReturnType<typeof useInternalNode>) {
  if (!node) return null;
  const width = node.measured.width ?? 0;
  const height = node.measured.height ?? 0;
  return {
    x: node.internals.positionAbsolute.x + width / 2,
    y: node.internals.positionAbsolute.y + height / 2,
    r: Math.min(width, height) / 2,
  };
}

function CenterEdgeView({ id, source, target, style }: EdgeProps) {
  const a = centerOf(useInternalNode(source));
  const b = centerOf(useInternalNode(target));
  if (!a || !b) return null;
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  const length = Math.hypot(dx, dy);
  if (length <= a.r + b.r) return null;
  const ux = dx / length;
  const uy = dy / length;
  const path = `M ${a.x + ux * a.r} ${a.y + uy * a.r} L ${b.x - ux * b.r} ${b.y - uy * b.r}`;
  return (
    <BaseEdge
      id={id}
      path={path}
      style={{ stroke: "#d3cfd6", strokeWidth: 0.6, ...style }}
    />
  );
}

export const CenterEdge = memo(CenterEdgeView);
