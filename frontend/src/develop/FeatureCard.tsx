import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { GripVertical, X } from "lucide-react";
import { useState, type KeyboardEvent } from "react";
import { u } from "../components/ui";
import type { Feature, Priority } from "../types";
import { plural, t } from "../i18n";

export const PRIORITY_STYLES: Record<
  Priority,
  { label: string; hint: string; background: string; color: string }
> = {
  must: {
    label: "Must",
    hint: t("Niezbędne w MVP"),
    background: "#fcd6f6",
    color: "#a0388f",
  },
  should: {
    label: "Should",
    hint: t("Ważne, w kolejnym kroku"),
    background: "#ead9fa",
    color: "#6c3f9c",
  },
  could: {
    label: "Could",
    hint: t("Dodatkowa wartość"),
    background: "#d9e7fb",
    color: "#3f65a0",
  },
  wont: {
    label: "Won't",
    hint: t("Poza zakresem tej wersji"),
    background: "#ebe8ef",
    color: "#6f6878",
  },
};

export const CARD_HEIGHT = 57;
export const CARD_GAP = 8.2;

function evidenceLabel(count: number): string {
  return plural(count, "dowód", "dowody", "dowodów");
}

interface ViewProps {
  feature: Feature;
  dragging?: boolean;
  overlay?: boolean;
  onRename?: (title: string) => void;
  onDelete?: () => void;
  handleProps?: Record<string, unknown>;
}

export function FeatureCardView({
  feature,
  dragging,
  overlay,
  onRename,
  onDelete,
  handleProps,
}: ViewProps) {
  const style = PRIORITY_STYLES[feature.priority];
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(feature.title);

  const commit = () => {
    setEditing(false);
    const title = draft.trim();
    if (title && title !== feature.title) onRename?.(title);
    else setDraft(feature.title);
  };

  const onKey = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Enter") commit();
    if (event.key === "Escape") {
      setDraft(feature.title);
      setEditing(false);
    }
  };

  return (
    <div
      className="group relative select-none"
      style={{
        width: u(126.4),
        height: u(CARD_HEIGHT),
        borderRadius: u(5.5),
        background: "#ffffff",
        boxShadow: overlay
          ? `0 ${u(6)} ${u(16)} rgba(170, 120, 210, 0.3)`
          : `0 ${u(1)} ${u(5)} rgba(196, 160, 232, 0.22)`,
        opacity: dragging ? 0.35 : 1,
        transform: overlay ? "rotate(1.5deg)" : undefined,
        cursor: overlay ? "grabbing" : "grab",
      }}
      title={
        feature.keywords.length
          ? t("Słowa dopasowane do dowodów: {words}", {
              words: feature.keywords.join(", "),
            })
          : undefined
      }
      {...handleProps}
    >
      {editing ? (
        <input
          autoFocus
          value={draft}
          maxLength={60}
          onChange={(e) => setDraft(e.target.value)}
          onBlur={commit}
          onKeyDown={onKey}
          onPointerDown={(e) => e.stopPropagation()}
          className="absolute rounded bg-[#f7f3fb] text-ink outline-none"
          style={{
            left: u(6),
            right: u(16),
            top: u(5.5),
            height: u(12),
            fontSize: u(8.2),
            padding: `0 ${u(2)}`,
          }}
        />
      ) : (
        <div
          className="absolute line-clamp-2 text-ink"
          style={{
            left: u(8),
            right: u(18),
            top: u(5.6),
            fontSize: u(8.6),
            lineHeight: u(10.3),
          }}
          onDoubleClick={() => onRename && setEditing(true)}
        >
          {feature.title}
        </div>
      )}
      <GripVertical
        className="absolute text-[#c9bfd3] transition-opacity group-hover:opacity-0"
        style={{ right: u(5), top: u(6), width: u(8), height: u(8) }}
      />
      {onDelete && (
        <button
          type="button"
          aria-label={t("Usuń funkcję")}
          title={t("Usuń funkcję")}
          onPointerDown={(e) => e.stopPropagation()}
          onClick={onDelete}
          className="absolute flex items-center justify-center rounded-full text-haze opacity-0 transition-opacity hover:bg-[#f7f0fb] hover:text-plum group-hover:opacity-100"
          style={{ right: u(4), top: u(5), width: u(10), height: u(10) }}
        >
          <X style={{ width: u(6.5), height: u(6.5) }} />
        </button>
      )}
      <div
        className="absolute truncate"
        style={{
          left: u(8),
          right: u(8),
          top: u(28),
          fontSize: u(5.8),
          lineHeight: 1.2,
          color: "var(--color-muted)",
        }}
        title={feature.description}
      >
        {feature.description}
      </div>
      <div
        className="absolute flex items-center"
        style={{ left: u(5.5), top: u(40.5), gap: u(7) }}
      >
        <span
          className="flex items-center justify-center"
          style={{
            height: u(11.7),
            minWidth: u(53),
            padding: `0 ${u(4)}`,
            borderRadius: u(3.5),
            fontSize: u(6),
            background: style.background,
            color: style.color,
          }}
        >
          Popyt {feature.demand}/100
        </span>
        <span className="text-haze" style={{ fontSize: u(5) }}>
          {feature.support}/{feature.pool} {evidenceLabel(feature.pool)}
        </span>
      </div>
    </div>
  );
}

interface SortableProps {
  feature: Feature;
  onRename: (feature: Feature, title: string) => void;
  onDelete: (feature: Feature) => void;
}

export function SortableFeatureCard({
  feature,
  onRename,
  onDelete,
}: SortableProps) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({
    id: feature.id,
    data: { priority: feature.priority },
  });
  return (
    <div
      ref={setNodeRef}
      style={{
        transform: CSS.Translate.toString(transform),
        transition,
        marginBottom: u(CARD_GAP),
      }}
    >
      <FeatureCardView
        feature={feature}
        dragging={isDragging}
        onRename={(title) => onRename(feature, title)}
        onDelete={() => onDelete(feature)}
        handleProps={{ ...attributes, ...listeners }}
      />
    </div>
  );
}
