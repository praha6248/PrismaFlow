import { Handle, Position, type Node, type NodeProps } from "@xyflow/react";
import { Star } from "lucide-react";
import { memo, type CSSProperties, type MouseEvent } from "react";
import type { MapNode } from "../types";
import { badgeOffset, diameterFor, fontSizeFor, styleFor } from "./kinds";
import { t } from "../i18n";

export interface BubbleData extends Record<string, unknown> {
  node: MapNode;
  fresh: boolean;
  delay: number;
  focused: boolean;
  showBadge: boolean;
  onToggleStar: (node: MapNode) => void;
}

export type BubbleFlowNode = Node<BubbleData, "bubble">;

const hiddenHandle: CSSProperties = {
  left: "50%",
  top: "50%",
  width: 1,
  height: 1,
  minWidth: 0,
  minHeight: 0,
  border: 0,
  background: "transparent",
  transform: "translate(-50%, -50%)",
  pointerEvents: "none",
  opacity: 0,
};

function BubbleNodeView({ data }: NodeProps<BubbleFlowNode>) {
  const { node, fresh, delay, focused, showBadge, onToggleStar } = data;
  const diameter = diameterFor(node);
  const style = styleFor(node);
  const fontSize = fontSizeFor(node.label, diameter, node.is_root);
  const badgeVisible = showBadge && !node.is_root && node.kind !== null;

  const toggleStar = (event: MouseEvent) => {
    event.stopPropagation();
    onToggleStar(node);
  };

  return (
    <div
      className="group relative"
      style={{ width: diameter, height: diameter }}
    >
      <Handle
        type="target"
        position={Position.Top}
        style={hiddenHandle}
        isConnectable={false}
      />
      <Handle
        type="source"
        position={Position.Top}
        style={hiddenHandle}
        isConnectable={false}
      />
      <div
        className={fresh ? "pf-pop h-full w-full" : "h-full w-full"}
        style={{ animationDelay: `${delay}ms` }}
      >
        <div
          className="flex h-full w-full cursor-pointer items-center justify-center rounded-full text-center text-bubble-text transition-[box-shadow,transform] duration-300 ease-out hover:scale-[1.04]"
          style={{
            background: style.gradient,
            boxShadow: [
              "0 4px 12px rgba(150, 104, 214, 0.22)",
              "0 1px 3px rgba(150, 104, 214, 0.12)",
              node.starred ? "0 0 0 2.5px #ffffff, 0 0 0 3.6px var(--color-pink)" : "",
              focused && !node.starred
                ? "0 0 0 2.5px rgba(255,255,255,0.95), 0 0 0 3.4px rgba(160,120,230,0.55)"
                : "",
            ]
              .filter(Boolean)
              .join(", "),
          }}
        >
          <span
            className="block px-[6%] font-normal leading-[1.12] tracking-[0.005em]"
            style={{ fontSize, overflowWrap: "break-word", hyphens: "manual" }}
          >
            {node.label}
          </span>
        </div>

        <button
          type="button"
          onClick={toggleStar}
          aria-label={node.starred ? t("Odznacz temat") : t("Zaznacz temat")}
          className={`absolute flex items-center justify-center rounded-full bg-white transition-all duration-200 ${
            node.starred ? "opacity-100" : "opacity-0 group-hover:opacity-100"
          }`}
          style={{
            width: 15,
            height: 15,
            right: diameter * 0.03,
            top: diameter * 0.03,
            boxShadow: "0 1px 4px rgba(150, 104, 214, 0.3)",
          }}
        >
          <Star
            size={8.5}
            strokeWidth={2}
            color="var(--color-pink)"
            fill={node.starred ? "var(--color-pink)" : "transparent"}
          />
        </button>

        {badgeVisible && (
          <span
            className="pf-fade absolute whitespace-nowrap rounded-full font-medium"
            style={{
              top: diameter + 4,
              left: diameter / 2 + badgeOffset(node.id, diameter),
              transform: "translateX(-50%)",
              background: style.badgeBg,
              color: style.badgeText,
              fontSize: 7.5,
              lineHeight: "13px",
              height: 13,
              padding: "0 7px",
              animationDelay: `${delay + 200}ms`,
            }}
          >
            {style.label}
          </span>
        )}
      </div>
    </div>
  );
}

export const BubbleNode = memo(BubbleNodeView);
