import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { CircleHelp, GripVertical, X } from "lucide-react";
import { useId, useState, type KeyboardEvent } from "react";
import { createPortal } from "react-dom";
import { u } from "../components/ui";
import type { Feature, Priority } from "../types";
import { number, plural, t } from "../i18n";

const IMPACTS = [0.25, 0.5, 1, 2, 3];
const IMPACT_LABELS: Record<number, string> = {
  0.25: t("minimalny"),
  0.5: t("mały"),
  1: t("średni"),
  2: t("duży"),
  3: t("ogromny"),
};
const EFFORTS = [0.5, 1, 2, 3, 4, 6, 8];

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
    color: "#5f5867",
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
  onRice?: (patch: { impact?: number; effort?: number }) => void;
  handleProps?: Record<string, unknown>;
}

export function FeatureCardView({
  feature,
  dragging,
  overlay,
  onRename,
  onDelete,
  onRice,
  handleProps,
}: ViewProps) {
  const [riceAt, setRiceAt] = useState<{ left: number; top: number } | null>(null);
  const riceOpen = riceAt !== null;
  const rice = feature.rice;
  const style = PRIORITY_STYLES[feature.priority];
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(feature.title);

  const [showEvidence, setShowEvidence] = useState(false);
  const tooltipId = useId();
  const evidence = `${feature.support}/${feature.pool} ${evidenceLabel(feature.pool)}`;

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
            fontSize: "var(--text-body)",
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
            fontSize: "var(--text-body)",
            lineHeight: u(10.3),
          }}
          onDoubleClick={() => onRename && setEditing(true)}
        >
          {feature.title}
        </div>
      )}
      <GripVertical
        className="absolute text-haze transition-opacity group-hover:opacity-0"
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
          fontSize: "var(--text-small)",
          lineHeight: 1.2,
          color: "var(--color-muted)",
        }}
        title={feature.description}
      >
        {feature.description}
      </div>
      <div
        className="absolute flex items-center"
        style={{ left: u(5.5), top: u(40.5), gap: u(4) }}
      >
        <span
          className="flex items-center justify-center"
          style={{
            height: u(11.7),
            minWidth: u(48),
            padding: `0 ${u(4)}`,
            borderRadius: u(3.5),
            fontSize: "var(--text-small)",
            background: style.background,
            color: style.color,
          }}
        >
          {feature.pool ? t("Źródła {n}/{all}", { n: feature.support, all: feature.pool }) : t("Brak źródeł")}
        </span>
        {rice && (
          <button
            type="button"
            onPointerDown={(e) => e.stopPropagation()}
            onClick={(e) => {
              e.stopPropagation();
              const rect = e.currentTarget.getBoundingClientRect();
              setRiceAt(riceAt ? null : { left: rect.left, top: rect.bottom + 4 });
            }}
            title={t("RICE = zasięg × wpływ × pewność ÷ nakład")}
            className="flex items-center justify-center font-semibold text-ink hover:underline"
            style={{
              height: u(11.7),
              padding: `0 ${u(3)}`,
              borderRadius: u(3.5),
              fontSize: "var(--text-small)",
              background: "#f3ecfa",
            }}
          >
            RICE {number(rice.score, 1)}
          </button>
        )}
        <button type="button" aria-label={t("Pokaż dowody, na których to oparto")}
          aria-describedby={showEvidence ? tooltipId : undefined}
          className="flex items-center justify-center rounded-full text-haze hover:text-plum"
          style={{width: u(14), height: u(14)}}
          onPointerEnter={e => { if (e.pointerType !== "touch") setShowEvidence(true); }}
          onPointerLeave={() => setShowEvidence(false)}
          onFocus={() => setShowEvidence(true)} onBlur={() => setShowEvidence(false)}
          onPointerDown={e => e.stopPropagation()}
          onClick={e => { e.stopPropagation(); setShowEvidence(true); }}
          onKeyDown={e => { e.stopPropagation(); if (e.key === "Escape") setShowEvidence(false); }}>
          <CircleHelp size={16} />
        </button>
        {riceOpen && rice && createPortal(
          <div
            onPointerDown={(e) => e.stopPropagation()}
            className="fixed z-50 flex flex-col bg-white text-ink"
            style={{
              left: riceAt.left,
              top: riceAt.top,
              width: u(150),
              padding: u(6),
              gap: u(3),
              borderRadius: u(6),
              boxShadow: `0 ${u(3)} ${u(12)} rgba(170, 120, 210, 0.3)`,
              fontSize: "var(--text-small)",
              cursor: "default",
            }}
          >
            <span>{t("Zasięg: {n} dowodów z puli", { n: rice.reach })}</span>
            <span>{t("Pewność: {n}% (dowody i wywiady)", { n: Math.round(rice.confidence * 100) })}</span>
            <label className="flex items-center" style={{ gap: u(3) }}>
              {t("Wpływ")}
              <select
                value={rice.impact}
                onChange={(e) => onRice?.({ impact: Number(e.target.value) })}
                disabled={!onRice}
                className="ml-auto rounded border border-[#eadff3] bg-white"
              >
                {IMPACTS.map((v) => (
                  <option key={v} value={v}>
                    {number(v, v < 1 ? 2 : 0)} · {IMPACT_LABELS[v]}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex items-center" style={{ gap: u(3) }}>
              {t("Nakład (osobotygodnie)")}
              <select
                value={rice.effort}
                onChange={(e) => onRice?.({ effort: Number(e.target.value) })}
                disabled={!onRice}
                className="ml-auto rounded border border-[#eadff3] bg-white"
              >
                {EFFORTS.map((v) => (
                  <option key={v} value={v}>
                    {number(v, v < 1 ? 1 : 0)}
                  </option>
                ))}
              </select>
            </label>
            <button
              type="button"
              onClick={() => setRiceAt(null)}
              className="self-end text-pink-text hover:underline"
            >
              {t("Zamknij")}
            </button>
          </div>
        , document.body)}
        {showEvidence && (
          <span role="tooltip" id={tooltipId}
            className="pointer-events-none absolute bottom-full left-0 z-10 mb-1 whitespace-nowrap rounded-md bg-plum px-2 py-1 text-white"
            style={{fontSize: "var(--text-small)"}}>
            {evidence}
          </span>
        )}
      </div>
    </div>
  );
}

interface SortableProps {
  feature: Feature;
  onRename: (feature: Feature, title: string) => void;
  onDelete: (feature: Feature) => void;
  onRice: (feature: Feature, patch: { impact?: number; effort?: number }) => void;
}

export function SortableFeatureCard({
  feature,
  onRename,
  onDelete,
  onRice,
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
        onRice={(patch) => onRice(feature, patch)}
        handleProps={{ ...attributes, ...listeners }}
      />
    </div>
  );
}
