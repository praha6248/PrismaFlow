import {
  closestCorners,
  DndContext,
  DragOverlay,
  PointerSensor,
  useDroppable,
  useSensor,
  useSensors,
  type DragEndEvent,
  type DragOverEvent,
  type DragStartEvent,
} from "@dnd-kit/core";
import { arrayMove, SortableContext, verticalListSortingStrategy } from "@dnd-kit/sortable";
import { Plus } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { api, waitForJob } from "../api";
import { BarProgress, ChoiceBar, FooterNote, PageTitle, SHADOW, u, type Frame } from "../components/ui";
import type { DevelopState, Feature, Priority } from "../types";
import { CARD_GAP, CARD_HEIGHT, FeatureCardView, PRIORITY_STYLES, SortableFeatureCard } from "./FeatureCard";

const COLUMNS: Priority[] = ["must", "should", "could", "wont"];
const COLUMN = { left: 25.2, top: 179, width: 140, height: 207.5, gap: 11.7 };
const BAR: Frame = { left: 25.2, top: 397.4, width: 595, height: 31 };
const BAR_BUTTON: Frame = { left: 461.7, top: 4.8, width: 122, height: 21.3 };

const STAGE_TEXT: Record<string, string> = {
  queued: "Przygotowuję propozycje",
  context: "Zbieram dowody z mapy",
  thinking: "Model proponuje funkcje",
  scoring: "Liczę popyt na podstawie dowodów",
  saving: "Zapisuję tablicę",
  done: "Gotowe",
};

type Board = Record<Priority, Feature[]>;

function toBoard(features: Feature[]): Board {
  const board: Board = { must: [], should: [], could: [], wont: [] };
  for (const feature of [...features].sort((a, b) => a.position - b.position)) board[feature.priority].push(feature);
  return board;
}

function plural(count: number, one: string, few: string, many: string): string {
  if (count === 1) return one;
  const last = count % 10;
  const lastTwo = count % 100;
  return last >= 2 && last <= 4 && (lastTwo < 12 || lastTwo > 14) ? few : many;
}

function columnOf(board: Board, id: number | string): Priority | null {
  if (typeof id === "string" && (COLUMNS as string[]).includes(id)) return id as Priority;
  return COLUMNS.find((column) => board[column].some((f) => f.id === id)) ?? null;
}

interface ColumnProps {
  priority: Priority;
  index: number;
  features: Feature[];
  onRename: (feature: Feature, title: string) => void;
  onDelete: (feature: Feature) => void;
}

function Column({ priority, index, features, onRename, onDelete }: ColumnProps) {
  const { setNodeRef, isOver } = useDroppable({ id: priority });
  const style = PRIORITY_STYLES[priority];
  return (
    <div
      ref={setNodeRef}
      className="pf-fade-up absolute"
      style={{
        left: u(COLUMN.left + index * (COLUMN.width + COLUMN.gap)),
        top: u(COLUMN.top),
        width: u(COLUMN.width),
        height: u(COLUMN.height),
        borderRadius: u(8),
        background: isOver ? "rgba(255, 255, 255, 0.62)" : "rgba(255, 255, 255, 0.4)",
        border: `${u(0.7)} solid ${isOver ? "#f7b6ee" : "#ebdff4"}`,
        transition: "background 160ms, border-color 160ms",
        animationDelay: `${index * 60}ms`,
      }}
    >
      <span
        className="absolute flex items-center justify-center"
        style={{
          left: u(7.5),
          top: u(6.9),
          minWidth: u(46),
          height: u(15),
          padding: `0 ${u(6)}`,
          borderRadius: u(4.5),
          fontSize: u(8.2),
          background: style.background,
          color: style.color,
        }}
      >
        {style.label}
      </span>
      <span className="absolute text-haze" style={{ left: u(112), top: u(10.5), fontSize: u(7) }}>
        {features.length}
      </span>
      <span className="absolute text-haze" style={{ left: u(8), top: u(27.4), fontSize: u(5.6) }}>
        {style.hint}
      </span>
      <div
        className="pf-scroll absolute overflow-y-auto overflow-x-hidden"
        style={{ left: u(6.8), right: u(0), top: u(42.6), bottom: u(4), paddingRight: u(6.8) }}
      >
        <SortableContext items={features.map((f) => f.id)} strategy={verticalListSortingStrategy}>
          {features.map((feature) => (
            <SortableFeatureCard key={feature.id} feature={feature} onRename={onRename} onDelete={onDelete} />
          ))}
        </SortableContext>
        {(priority === "wont" || features.length === 0) && (
          <div
            className="flex items-center justify-center text-center text-haze"
            style={{
              width: u(126.4),
              height: u(CARD_HEIGHT),
              marginTop: features.length ? u(CARD_GAP) : 0,
              borderRadius: u(5.5),
              border: `${u(0.7)} dashed #dccfe6`,
              fontSize: u(5.8),
              lineHeight: 1.5,
              padding: `0 ${u(14)}`,
            }}
          >
            {priority === "wont" ? "Odłóż tutaj funkcje, które mogą poczekać." : "Przeciągnij tutaj funkcję."}
          </div>
        )}
      </div>
    </div>
  );
}

interface AddFormProps {
  onSubmit: (title: string, description: string, priority: Priority) => Promise<void>;
  onClose: () => void;
}

function AddFeatureForm({ onSubmit, onClose }: AddFormProps) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [priority, setPriority] = useState<Priority>("should");
  const [busy, setBusy] = useState(false);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!title.trim()) return;
    setBusy(true);
    await onSubmit(title.trim(), description.trim(), priority);
    setBusy(false);
  };

  return (
    <form
      onSubmit={submit}
      onKeyDown={(e) => e.key === "Escape" && onClose()}
      className="pf-fade-up absolute z-30 flex flex-col"
      style={{
        left: u(388),
        top: u(170),
        width: u(232),
        padding: u(9),
        gap: u(5),
        borderRadius: u(9),
        background: "#fdfcfe",
        boxShadow: `0 ${u(4)} ${u(18)} rgba(170, 120, 210, 0.3)`,
      }}
    >
      <input
        autoFocus
        value={title}
        maxLength={60}
        onChange={(e) => setTitle(e.target.value)}
        placeholder="Nazwa funkcji"
        className="rounded bg-[#f7f3fb] text-ink outline-none placeholder:text-[#9b8fa6]"
        style={{ height: u(17), padding: `0 ${u(6)}`, fontSize: u(7.4) }}
      />
      <input
        value={description}
        maxLength={140}
        onChange={(e) => setDescription(e.target.value)}
        placeholder="Co daje użytkownikowi?"
        className="rounded bg-[#f7f3fb] text-mauve outline-none placeholder:text-[#9b8fa6]"
        style={{ height: u(15), padding: `0 ${u(6)}`, fontSize: u(6.4) }}
      />
      <div className="flex items-center" style={{ gap: u(4) }}>
        {COLUMNS.map((column) => (
          <button
            key={column}
            type="button"
            onClick={() => setPriority(column)}
            className="transition-shadow"
            style={{
              height: u(12),
              padding: `0 ${u(6)}`,
              borderRadius: u(3.5),
              fontSize: u(6),
              background: PRIORITY_STYLES[column].background,
              color: PRIORITY_STYLES[column].color,
              boxShadow: priority === column ? `0 0 0 ${u(0.9)} #f783e9` : "none",
            }}
          >
            {PRIORITY_STYLES[column].label}
          </button>
        ))}
        <button type="button" onClick={onClose} className="ml-auto text-haze" style={{ fontSize: u(6.4) }}>
          Anuluj
        </button>
        <button
          type="submit"
          disabled={!title.trim() || busy}
          className="text-white disabled:opacity-50"
          style={{ height: u(14), padding: `0 ${u(8)}`, borderRadius: u(5), fontSize: u(6.6), background: "#f783e9" }}
        >
          Dodaj
        </button>
      </div>
    </form>
  );
}

interface Props {
  projectId: number;
  onDone: () => void;
  notify: (message: string) => void;
}

export function DevelopView({ projectId, onDone, notify }: Props) {
  const [state, setState] = useState<DevelopState | null>(null);
  const [board, setBoard] = useState<Board>(toBoard([]));
  const [jobStage, setJobStage] = useState<string | null>(null);
  const [activeId, setActiveId] = useState<number | null>(null);
  const [adding, setAdding] = useState(false);
  const started = useRef(false);
  const dragOrigin = useRef<Priority | null>(null);

  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 4 } }));

  const apply = useCallback((next: DevelopState) => {
    setState(next);
    setBoard(toBoard(next.features));
  }, []);

  const generate = useCallback(async () => {
    setJobStage("queued");
    try {
      const job = await api.generateFeatures(projectId);
      const finished = await waitForJob(job.id, (j) => setJobStage(j.stage));
      if (finished.status === "error" || !finished.result) {
        notify(`Nie udało się zaproponować funkcji: ${finished.error ?? "nieznany błąd"}`);
        apply(await api.getDevelop(projectId));
        return;
      }
      apply(finished.result as DevelopState);
    } catch (error) {
      notify((error as Error).message);
    } finally {
      setJobStage(null);
    }
  }, [projectId, notify, apply]);

  useEffect(() => {
    api
      .getDevelop(projectId)
      .then((data) => {
        apply(data);
        if (!data.features.length && data.persona && !started.current) {
          started.current = true;
          generate();
        }
      })
      .catch((error: Error) => notify(`Nie udało się wczytać fazy Develop: ${error.message}`));
  }, [projectId, apply, generate, notify]);

  const persist = useCallback(
    (next: Board) => {
      const items = COLUMNS.flatMap((priority) => next[priority].map((f, position) => ({ id: f.id, priority, position })));
      api.orderFeatures(projectId, items).catch((error: Error) => notify(error.message));
    },
    [projectId, notify],
  );

  const onDragStart = (event: DragStartEvent) => {
    setActiveId(Number(event.active.id));
    dragOrigin.current = columnOf(board, event.active.id);
  };

  const onDragOver = ({ active, over }: DragOverEvent) => {
    if (!over) return;
    const from = columnOf(board, active.id);
    const to = columnOf(board, over.id);
    if (!from || !to || from === to) return;
    setBoard((current) => {
      const moving = current[from].find((f) => f.id === active.id);
      if (!moving) return current;
      const target = current[to];
      const overIndex = target.findIndex((f) => f.id === over.id);
      const index = overIndex >= 0 ? overIndex : target.length;
      return {
        ...current,
        [from]: current[from].filter((f) => f.id !== active.id),
        [to]: [...target.slice(0, index), { ...moving, priority: to }, ...target.slice(index)],
      };
    });
  };

  const onDragEnd = ({ active, over }: DragEndEvent) => {
    setActiveId(null);
    const origin = dragOrigin.current;
    dragOrigin.current = null;
    if (!over) return;
    const column = columnOf(board, active.id);
    if (!column) return;
    const items = board[column];
    const oldIndex = items.findIndex((f) => f.id === active.id);
    const newIndex = items.findIndex((f) => f.id === over.id);
    let next = board;
    if (oldIndex >= 0 && newIndex >= 0 && oldIndex !== newIndex) {
      next = { ...board, [column]: arrayMove(items, oldIndex, newIndex) };
      setBoard(next);
    } else if (origin === column && oldIndex === newIndex) {
      return;
    }
    persist(next);
  };

  const rename = async (feature: Feature, title: string) => {
    try {
      const updated = await api.updateFeature(feature.id, { title });
      setBoard((current) => ({
        ...current,
        [updated.priority]: current[updated.priority].map((f) => (f.id === updated.id ? updated : f)),
      }));
    } catch (error) {
      notify((error as Error).message);
    }
  };

  const remove = async (feature: Feature) => {
    setBoard((current) => ({ ...current, [feature.priority]: current[feature.priority].filter((f) => f.id !== feature.id) }));
    try {
      await api.deleteFeature(feature.id);
    } catch (error) {
      notify((error as Error).message);
      apply(await api.getDevelop(projectId));
    }
  };

  const add = async (title: string, description: string, priority: Priority) => {
    try {
      const feature = await api.addFeature(projectId, title, description, priority);
      setBoard((current) => ({ ...current, [priority]: [...current[priority], feature] }));
      setAdding(false);
    } catch (error) {
      notify((error as Error).message);
    }
  };

  const all = useMemo(() => COLUMNS.flatMap((c) => board[c]), [board]);
  const active = all.find((f) => f.id === activeId) ?? null;
  const inScope = all.filter((f) => f.priority !== "wont").length;
  const mustCount = board.must.length;
  const busy = jobStage !== null;
  const persona = state?.persona;
  const subtitle = persona ? `${persona.name} · ${persona.focus} · Zakres pierwszej wersji` : "Zakres pierwszej wersji";
  const scope = `${inScope} ${plural(inScope, "funkcja", "funkcje", "funkcji")} · ${mustCount} ${plural(mustCount, "niezbędna", "niezbędne", "niezbędnych")} w MVP`;

  return (
    <>
      <PageTitle title="Zamień potrzeby w priorytety" subtitle={subtitle} top={101} size={16.5} gap={23} />

      <div className="pf-fade absolute" style={{ left: u(25.2), top: u(143) }}>
        <div className="font-serif text-plum" style={{ fontSize: u(10), lineHeight: 1 }}>
          Propozycje lokalnego LLM
        </div>
        <div className="text-haze" style={{ fontSize: u(5.8), marginTop: u(5) }}>
          Przeciągnij karty między kolumnami MoSCoW.
        </div>
      </div>

      <button
        type="button"
        onClick={() => setAdding((v) => !v)}
        disabled={busy || !state}
        className="pf-fade absolute flex items-center justify-center transition-transform enabled:hover:scale-[1.02] enabled:active:scale-[0.98] disabled:opacity-60"
        style={{
          left: u(388),
          top: u(143),
          width: u(113),
          height: u(22),
          gap: u(3),
          borderRadius: u(7),
          fontSize: u(7),
          background: "#fde3f9",
          color: "#a0388f",
        }}
      >
        <Plus style={{ width: u(7), height: u(7) }} />
        Dodaj własną funkcję
      </button>
      <button
        type="button"
        onClick={generate}
        disabled={busy || !persona}
        className="pf-fade absolute transition-transform enabled:hover:scale-[1.02] enabled:active:scale-[0.98] disabled:opacity-60"
        style={{
          left: u(509.6),
          top: u(143),
          width: u(110),
          height: u(22),
          borderRadius: u(7),
          fontSize: u(7),
          background: "#e7d8f8",
          color: "#573476",
          boxShadow: SHADOW,
        }}
      >
        Wygeneruj ponownie
      </button>
      {adding && <AddFeatureForm onSubmit={add} onClose={() => setAdding(false)} />}

      <DndContext
        sensors={sensors}
        collisionDetection={closestCorners}
        onDragStart={onDragStart}
        onDragOver={onDragOver}
        onDragEnd={onDragEnd}
        onDragCancel={() => {
          setActiveId(null);
          if (state) setBoard(toBoard(all));
        }}
      >
        {COLUMNS.map((priority, index) => (
          <Column
            key={priority}
            priority={priority}
            index={index}
            features={busy ? [] : board[priority]}
            onRename={rename}
            onDelete={remove}
          />
        ))}
        <DragOverlay dropAnimation={{ duration: 180, easing: "cubic-bezier(0.22, 1, 0.36, 1)" }}>
          {active ? <FeatureCardView feature={active} overlay /> : null}
        </DragOverlay>
      </DndContext>

      {busy ? (
        <BarProgress title="Układam tablicę MoSCoW..." text={STAGE_TEXT[jobStage] ?? STAGE_TEXT.thinking} stage={jobStage} frame={BAR} />
      ) : (
        <ChoiceBar
          label="TWÓJ ZAKRES"
          value={all.length ? scope : null}
          placeholder={persona ? "Brak funkcji — wygeneruj propozycje" : "Najpierw wybierz personę w fazie Define"}
          action="Przejdź do user flow"
          disabled={mustCount === 0}
          onConfirm={onDone}
          frame={BAR}
          button={BAR_BUTTON}
        />
      )}
      <FooterNote top={436}>
        Popyt = odsetek dowodów z mapy (Google, Stack Exchange, Lemmy) wspierających funkcję × 100 · propozycje lokalnego modelu do weryfikacji
      </FooterNote>
    </>
  );
}
