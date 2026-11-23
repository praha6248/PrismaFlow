import { Handle, Position, type Node, type NodeProps } from "@xyflow/react";
import { Plus, X } from "lucide-react";
import { memo, useState, type DragEvent, type KeyboardEvent } from "react";
import type { ElementSize, ElementType, ElementZone, Feature, FlowElement, FlowScreen, ScreenKind } from "../types";

export const ZONE_LABELS: Record<ElementZone, string> = { top: "Górny róg", center: "Centrum", bottom: "Dół" };
export const TYPE_LABELS: Record<ElementType, string> = {
  button: "Button",
  link: "Link",
  select: "Select",
  input: "Input",
  toggle: "Toggle",
  list: "Lista",
};
const KIND_ORDER: ScreenKind[] = ["step", "goal", "start"];

export interface ScreenActions {
  rename: (screenId: string, name: string) => void;
  cycleKind: (screenId: string, kind: ScreenKind) => void;
  remove: (screenId: string) => void;
  addElement: (screenId: string) => void;
  updateElement: (screenId: string, elementId: string, patch: Partial<FlowElement>) => void;
  removeElement: (screenId: string, elementId: string) => void;
  dropFeature: (screenId: string, featureId: number) => void;
  removeFeature: (screenId: string, featureId: number) => void;
}

export type ScreenNodeData = {
  screen: FlowScreen;
  index: number;
  features: Feature[];
  deadEnd: boolean;
  unreachable: boolean;
  flagged: Set<string>;
  actions: ScreenActions;
};

export type ScreenFlowNode = Node<ScreenNodeData, "screen">;

function InlineText({ value, onCommit, className, style }: { value: string; onCommit: (v: string) => void; className?: string; style?: React.CSSProperties }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value);
  const commit = () => {
    setEditing(false);
    const next = draft.trim();
    if (next && next !== value) onCommit(next);
    else setDraft(value);
  };
  const onKey = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Enter") commit();
    if (event.key === "Escape") {
      setDraft(value);
      setEditing(false);
    }
  };
  if (editing) {
    return (
      <input
        autoFocus
        value={draft}
        maxLength={60}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={commit}
        onKeyDown={onKey}
        className={`nodrag min-w-0 rounded bg-[#f7f3fb] outline-none ${className ?? ""}`}
        style={style}
      />
    );
  }
  return (
    <span
      className={`truncate ${className ?? ""}`}
      style={{ ...style, cursor: "text" }}
      onDoubleClick={() => {
        setDraft(value);
        setEditing(true);
      }}
      title="Kliknij dwukrotnie, aby zmienić"
    >
      {value}
    </span>
  );
}

function MiniSelect<T extends string>({
  value,
  options,
  onChange,
  width,
  warn,
}: {
  value: T;
  options: [T, string][];
  onChange: (value: T) => void;
  width: number;
  warn?: boolean;
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value as T)}
      className="nodrag cursor-pointer appearance-none rounded-[5px] outline-none"
      style={{
        width,
        height: 15,
        fontSize: 7.5,
        padding: "0 12px 0 6px",
        background: warn
          ? "#fde3f4 url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='6' height='4'%3E%3Cpath d='M0 0l3 4 3-4z' fill='%23b0418f'/%3E%3C/svg%3E\") no-repeat right 5px center"
          : "#ece3f8 url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='6' height='4'%3E%3Cpath d='M0 0l3 4 3-4z' fill='%237c6d88'/%3E%3C/svg%3E\") no-repeat right 5px center",
        color: warn ? "#a0388f" : "#573476",
      }}
    >
      {options.map(([key, label]) => (
        <option key={key} value={key}>
          {label}
        </option>
      ))}
    </select>
  );
}

function ElementRow({ screenId, element, flagged, actions }: { screenId: string; element: FlowElement; flagged: boolean; actions: ScreenActions }) {
  return (
    <div className="group/el relative" style={{ padding: "5px 10px 6px", borderTop: "1px solid #f3edf8" }}>
      <div className="flex items-center" style={{ gap: 4 }}>
        <InlineText
          value={element.label}
          onCommit={(label) => actions.updateElement(screenId, element.id, { label })}
          className="flex-1 text-ink"
          style={{ fontSize: 9 }}
        />
        <select
          value={element.type}
          onChange={(e) => actions.updateElement(screenId, element.id, { type: e.target.value as ElementType })}
          className="nodrag cursor-pointer appearance-none bg-transparent text-right text-haze outline-none"
          style={{ fontSize: 7 }}
        >
          {Object.entries(TYPE_LABELS).map(([key, label]) => (
            <option key={key} value={key}>
              {label}
            </option>
          ))}
        </select>
        <button
          type="button"
          onClick={() => actions.removeElement(screenId, element.id)}
          className="nodrag text-haze opacity-0 transition-opacity hover:text-plum group-hover/el:opacity-100"
          aria-label="Usuń element"
        >
          <X size={9} />
        </button>
      </div>
      <div className="flex items-center" style={{ gap: 5, marginTop: 4 }}>
        <MiniSelect<ElementSize>
          value={element.size}
          options={[
            ["S", "S"],
            ["M", "M"],
            ["L", "L"],
          ]}
          onChange={(size) => actions.updateElement(screenId, element.id, { size })}
          width={30}
          warn={flagged && element.size !== "L"}
        />
        <MiniSelect<ElementZone>
          value={element.zone}
          options={Object.entries(ZONE_LABELS) as [ElementZone, string][]}
          onChange={(zone) => actions.updateElement(screenId, element.id, { zone })}
          width={70}
          warn={flagged && element.zone !== "bottom"}
        />
        {(element.type === "list" || element.type === "select") && (
          <label className="flex items-center text-haze" style={{ fontSize: 7, gap: 2 }} title="Ile opcji widać naraz">
            <input
              type="number"
              min={1}
              max={50}
              value={element.options}
              onChange={(e) => actions.updateElement(screenId, element.id, { options: Math.max(1, Math.min(50, Number(e.target.value) || 1)) })}
              className="nodrag rounded bg-[#f7f3fb] text-center text-mauve outline-none"
              style={{ width: 22, height: 14, fontSize: 7.5 }}
            />
            opcji
          </label>
        )}
      </div>
      <Handle
        type="source"
        id={element.id}
        position={Position.Right}
        className="!border-0"
        style={{ width: 7, height: 7, right: -4, background: element.target ? "#f783e9" : "#e4d6ec" }}
      />
    </div>
  );
}

function ScreenNodeView({ data, selected }: NodeProps<ScreenFlowNode>) {
  const { screen, index, features, deadEnd, unreachable, flagged, actions } = data;
  const [over, setOver] = useState(false);
  const linked = features.filter((f) => screen.feature_ids.includes(f.id));
  const tag = screen.kind === "start" ? "START" : screen.kind === "goal" ? "CEL" : String(index + 1).padStart(2, "0");
  const tagStyle =
    screen.kind === "goal"
      ? { background: "#dff3e4", color: "#3d7a50" }
      : screen.kind === "start"
        ? { background: "#f3ecfa", color: "#7c6d88" }
        : { background: "#f3ecfa", color: "#7c6d88" };

  const onDrop = (event: DragEvent) => {
    setOver(false);
    const id = Number(event.dataTransfer.getData("application/x-prismaflow-feature"));
    if (id) {
      event.preventDefault();
      actions.dropFeature(screen.id, id);
    }
  };

  return (
    <div
      data-screen-id={screen.id}
      onDragOver={(e) => {
        if (e.dataTransfer.types.includes("application/x-prismaflow-feature")) {
          e.preventDefault();
          setOver(true);
        }
      }}
      onDragLeave={() => setOver(false)}
      onDrop={onDrop}
      className="group relative"
      style={{
        width: 200,
        borderRadius: 10,
        background: "#ffffff",
        border: `1.2px solid ${over || selected ? "#f783e9" : deadEnd ? "#f7b6ee" : "#ece3f4"}`,
        boxShadow: over ? "0 0 0 4px rgba(247, 131, 233, 0.18)" : "0 2px 10px rgba(196, 160, 232, 0.25)",
        opacity: unreachable ? 0.72 : 1,
      }}
    >
      <Handle type="target" position={Position.Left} className="!border-0" style={{ width: 8, height: 8, top: 22, left: -4, background: "#d9c6ec" }} />
      <div className="flex items-center" style={{ padding: "7px 10px 2px", gap: 3 }}>
        {[0, 1, 2].map((i) => (
          <span key={i} className="rounded-full bg-[#e9e1f1]" style={{ width: 3.5, height: 3.5 }} />
        ))}
        <button
          type="button"
          onClick={() => actions.remove(screen.id)}
          className="nodrag ml-auto text-haze opacity-0 transition-opacity hover:text-plum group-hover:opacity-100"
          aria-label="Usuń ekran"
          title="Usuń ekran"
        >
          <X size={10} />
        </button>
      </div>
      <div className="flex items-center" style={{ padding: "0 10px 6px", gap: 6 }}>
        <InlineText
          value={screen.name}
          onCommit={(name) => actions.rename(screen.id, name)}
          className="flex-1 font-serif text-ink"
          style={{ fontSize: 12.5 }}
        />
        <button
          type="button"
          onClick={() => actions.cycleKind(screen.id, KIND_ORDER[(KIND_ORDER.indexOf(screen.kind) + 1) % 3])}
          className="nodrag shrink-0 rounded-[4px]"
          style={{ fontSize: 6.5, padding: "2px 6px", letterSpacing: "0.06em", ...tagStyle }}
          title="Zmień rolę ekranu: krok, cel, start"
        >
          {tag}
        </button>
        {deadEnd && (
          <span className="shrink-0 rounded-[4px] bg-[#fde3f4] text-[#a0388f]" style={{ fontSize: 6.5, padding: "2px 5px" }}>
            Brak wyjścia
          </span>
        )}
      </div>
      {linked.length > 0 && (
        <div className="flex flex-wrap" style={{ padding: "0 10px 6px", gap: 3 }}>
          {linked.map((feature) => (
            <span
              key={feature.id}
              className="group/f flex items-center rounded-full bg-[#fdeefb] text-[#a0388f]"
              style={{ fontSize: 6.5, padding: "1px 6px", gap: 3 }}
            >
              <span className="rounded-full bg-[#f783e9]" style={{ width: 4, height: 4 }} />
              {feature.title}
              <button
                type="button"
                className="nodrag hidden group-hover/f:inline"
                onClick={() => actions.removeFeature(screen.id, feature.id)}
                aria-label="Odepnij funkcję"
              >
                <X size={7} />
              </button>
            </span>
          ))}
        </div>
      )}
      {screen.elements.map((element) => (
        <ElementRow key={element.id} screenId={screen.id} element={element} flagged={flagged.has(element.id)} actions={actions} />
      ))}
      <button
        type="button"
        onClick={() => actions.addElement(screen.id)}
        className="nodrag flex w-full items-center justify-center text-haze transition-colors hover:text-plum"
        style={{ fontSize: 7, gap: 3, padding: "5px 0 6px", borderTop: "1px solid #f3edf8" }}
      >
        <Plus size={8} /> element
      </button>
    </div>
  );
}

export const ScreenNode = memo(ScreenNodeView);
