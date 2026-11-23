import {
  Background,
  BackgroundVariant,
  MarkerType,
  ReactFlow,
  ReactFlowProvider,
  useReactFlow,
  useViewport,
  type Connection,
  type Edge,
  type OnEdgesChange,
  type OnNodesChange,
} from "@xyflow/react";
import { LocateFixed, Minus, Plus } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, waitForJob } from "../api";
import { PageTitle, u, SHADOW } from "../components/ui";
import { ProgressContent } from "../discover/BottomBar";
import type {
  DeliverState,
  Flow,
  FlowAudit,
  FlowElement,
  FlowScreen,
  Handoff,
  ScreenKind,
  Suggestion,
} from "../types";
import { AuditPanel } from "./AuditPanel";
import { HandoffModal } from "./HandoffModal";
import {
  ScreenNode,
  type ScreenActions,
  type ScreenFlowNode,
} from "./ScreenNode";
import { Toolbox } from "./Toolbox";
import { plural, t } from "../i18n";

const PANEL_TOP = 136.8;
const PANEL_HEIGHT = 293.7;
const nodeTypes = { screen: ScreenNode };

const STAGE_TEXT: Record<string, string> = {
  queued: t("Przygotowuję projekt"),
  context: t("Czytam backlog i personę"),
  thinking: t("Model projektuje ekrany"),
  layout: t("Układam przepływ"),
  audit: t("Liczę metryki audytu"),
  saving: t("Zapisuję"),
  done: t("Gotowe"),
};

const panelStyle = (left: number, width: number) => ({
  left: u(left),
  top: u(PANEL_TOP),
  width: u(width),
  height: u(PANEL_HEIGHT),
  borderRadius: u(9),
  background: "rgba(253, 252, 254, 0.92)",
  boxShadow: SHADOW,
});

const newId = (prefix: string) =>
  `${prefix}${Math.random().toString(16).slice(2, 8)}`;

function ZoomControl() {
  const { zoomIn, zoomOut, fitView } = useReactFlow();
  const { zoom } = useViewport();
  return (
    <div
      className="flex items-center rounded-full bg-white text-mauve"
      style={{
        gap: u(5),
        padding: `${u(2)} ${u(6)}`,
        fontSize: "var(--text-small)",
        boxShadow: SHADOW,
      }}
    >
      <button
        type="button"
        onClick={() => zoomOut({ duration: 200 })}
        aria-label={t("Pomniejsz")}
      >
        <Minus style={{ width: u(5.5), height: u(5.5) }} />
      </button>
      <span style={{ minWidth: u(17), textAlign: "center" }}>
        {Math.round(zoom * 100)}%
      </span>
      <button
        type="button"
        onClick={() => zoomIn({ duration: 200 })}
        aria-label={t("Powiększ")}
      >
        <Plus style={{ width: u(5.5), height: u(5.5) }} />
      </button>
      <button
        type="button"
        onClick={() => fitView({ padding: 0.12, maxZoom: 1, duration: 400 })}
        aria-label={t("Pokaż wszystkie ekrany")}
        title={t("Pokaż wszystkie ekrany")}
        style={{ borderLeft: `${u(0.5)} solid #eee6f5`, paddingLeft: u(5) }}
      >
        <LocateFixed style={{ width: u(5.5), height: u(5.5) }} />
      </button>
    </div>
  );
}

interface CanvasProps {
  detailed: boolean;
  flow: Flow;
  state: DeliverState;
  audit: FlowAudit;
  selectedId: string | null;
  focusRequest: { id: string; at: number } | null;
  onSelect: (id: string | null) => void;
  onChange: (updater: (flow: Flow) => Flow) => void;
  actions: ScreenActions;
}

function Canvas({
  detailed,
  flow,
  state,
  audit,
  selectedId,
  focusRequest,
  onSelect,
  onChange,
  actions,
}: CanvasProps) {
  const { fitView, setCenter, getZoom } = useReactFlow();
  const fitted = useRef(false);
  const box = useRef<HTMLDivElement>(null);
  const viewport = useViewport();
  const [lost, setLost] = useState(false);

  const flagged = useMemo(() => {
    const ids = new Set<string>(audit.fitts.map((f) => f.element_id));
    for (const t of audit.targets.below_aaa)
      if (t.primary) ids.add(t.element_id);
    return ids;
  }, [audit]);

  const nodes: ScreenFlowNode[] = useMemo(() => {
    const dead = new Set(audit.dead_ends.map((d) => d.screen_id));
    const lost = new Set(audit.unreachable.map((d) => d.screen_id));
    return flow.screens.map((screen, index) => ({
      id: screen.id,
      type: "screen",
      position: { x: screen.x, y: screen.y },
      selected: screen.id === selectedId,
      dragHandle: undefined,
      data: {
        screen,
        detailed,
        index,
        features: state.features,
        deadEnd: dead.has(screen.id),
        unreachable: lost.has(screen.id),
        flagged,
        actions,
      },
    }));
  }, [flow, detailed, audit, selectedId, state.features, flagged, actions]);

  const edges: Edge[] = useMemo(() => {
    const ids = new Set(flow.screens.map((s) => s.id));
    return flow.screens.flatMap((screen) =>
      screen.elements
        .filter((e) => e.target && ids.has(e.target) && e.target !== screen.id)
        .map((element) => ({
          id: `${screen.id}:${element.id}`,
          source: screen.id,
          sourceHandle: element.id,
          target: element.target as string,
          label: element.label,
          type: "smoothstep",
          style: { stroke: "#805d91", strokeWidth: 1.7 },
          markerEnd: {
            type: MarkerType.ArrowClosed,
            color: "#805d91",
            width: 14,
            height: 14,
          },
          labelStyle: {
            fontSize: 10,
            fill: "var(--color-muted)",
            fontFamily: "Montserrat",
          },
          labelBgStyle: { fill: "#fdfcfe" },
          labelBgPadding: [4, 2] as [number, number],
        })),
    );
  }, [flow]);

  useEffect(() => {
    if (!fitted.current && flow.screens.length) {
      fitted.current = true;
      window.setTimeout(
        () => fitView({ padding: 0.12, maxZoom: 1, duration: 0 }),
        30,
      );
    }
  }, [flow.screens.length, fitView]);

  useEffect(() => {
    if (!focusRequest) return;
    const screen = flow.screens.find((s) => s.id === focusRequest.id);
    if (screen)
      setCenter(screen.x + 100, screen.y + 80, {
        zoom: Math.max(getZoom(), 0.8),
        duration: 400,
      });
  }, [focusRequest]);

  const onNodesChange: OnNodesChange<ScreenFlowNode> = useCallback(
    (changeset) => {
      const changes = changeset.toArray();
      for (const change of changes) {
        if (change.type === "select" && change.selected) onSelect(change.id);
        if (change.type === "remove") actions.remove(change.id);
      }
      const moves = changes.filter((c) => c.type === "position" && c.position);
      if (moves.length) {
        onChange((current) => ({
          screens: current.screens.map((screen) => {
            const move = moves.find(
              (m) => m.type === "position" && m.id === screen.id,
            );
            return move && move.type === "position" && move.position
              ? { ...screen, x: move.position.x, y: move.position.y }
              : screen;
          }),
        }));
      }
    },
    [onChange, onSelect, actions],
  );

  const onEdgesChange: OnEdgesChange = useCallback(
    (changeset) => {
      const removed = changeset
        .toArray()
        .filter((c) => c.type === "remove")
        .map((c) => c.id);
      if (!removed.length) return;
      onChange((current) => ({
        screens: current.screens.map((screen) => ({
          ...screen,
          elements: screen.elements.map((e) =>
            removed.includes(`${screen.id}:${e.id}`)
              ? { ...e, target: null }
              : e,
          ),
        })),
      }));
    },
    [onChange],
  );

  const onConnect = useCallback(
    (connection: Connection) => {
      if (!connection.sourceHandle || connection.source === connection.target)
        return;
      actions.updateElement(connection.source, connection.sourceHandle, {
        target: connection.target,
      });
    },
    [actions],
  );

  useEffect(() => {
    const element = box.current;
    if (!element || !nodes.length) {
      setLost(false);
      return;
    }
    const xs = nodes.map((n) => n.position.x);
    const ys = nodes.map((n) => n.position.y);
    const left = Math.min(...xs) * viewport.zoom + viewport.x;
    const top = Math.min(...ys) * viewport.zoom + viewport.y;
    const right = (Math.max(...xs) + 200) * viewport.zoom + viewport.x;
    const bottom = (Math.max(...ys) + 160) * viewport.zoom + viewport.y;
    const margin = 24;
    setLost(
      right < margin ||
        bottom < margin ||
        left > element.clientWidth - margin ||
        top > element.clientHeight - margin,
    );
  }, [viewport, nodes]);

  return (
    <div ref={box} className="relative h-full w-full">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        nodesConnectable={detailed}
        onPaneClick={() => onSelect(null)}
        minZoom={0.3}
        maxZoom={1.6}
        proOptions={{ hideAttribution: true }}
        forceColorMode="light"
        style={{ background: "transparent" }}
        deleteKeyCode={["Delete"]}
        connectionLineStyle={{ stroke: "var(--color-pink)", strokeWidth: 1.2 }}
      >
        <Background
          variant={BackgroundVariant.Dots}
          gap={18}
          size={1}
          color="#e8dcf2"
        />
      </ReactFlow>
      {lost && (
        <button
          type="button"
          onClick={() => fitView({ padding: 0.12, maxZoom: 1, duration: 500 })}
          className="pf-fade-up absolute left-1/2 top-1/2 flex -translate-x-1/2 -translate-y-1/2 items-center font-semibold text-on-pink transition-transform hover:scale-[1.03]"
          style={{
            gap: u(4),
            padding: `${u(6)} ${u(11)}`,
            borderRadius: u(20),
            fontSize: "var(--text-small)",
            background: "var(--color-pink-button)",
            boxShadow: SHADOW,
          }}
        >
          <LocateFixed style={{ width: u(7), height: u(7) }} />
          {t("Ekrany są poza widokiem · wróć do nich")}
        </button>
      )}
    </div>
  );
}

interface Props {
  projectId: number;
  notify: (message: string) => void;
  onRestart: () => void;
}

function Studio({ projectId, notify, onRestart }: Props) {
  const [state, setState] = useState<DeliverState | null>(null);
  const [flow, setFlow] = useState<Flow>({ screens: [] });
  const [audit, setAudit] = useState<FlowAudit | null>(null);
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [job, setJob] = useState<{
    kind: "flow" | "optimize";
    stage: string;
  } | null>(null);
  const [detailed, setDetailed] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [focusRequest, setFocusRequest] = useState<{
    id: string;
    at: number;
  } | null>(null);
  const [handoff, setHandoff] = useState<Handoff | null>(null);
  const [handoffBusy, setHandoffBusy] = useState(false);
  const saveTimer = useRef<number | undefined>(undefined);
  const dirty = useRef(false);
  const started = useRef(false);
  const flowRef = useRef(flow);
  flowRef.current = flow;

  const apply = useCallback((next: DeliverState) => {
    setState(next);
    setFlow(next.flow);
    setAudit(next.audit);
    setSuggestions(next.suggestions);
  }, []);

  const runJob = useCallback(
    async (kind: "flow" | "optimize") => {
      setJob({ kind, stage: "queued" });
      try {
        const startedJob =
          kind === "flow"
            ? await api.generateFlow(projectId)
            : await api.optimizeFlow(projectId);
        const finished = await waitForJob(startedJob.id, (j) =>
          setJob({ kind, stage: j.stage }),
        );
        if (finished.warnings.some((w) => w.startsWith("llm:"))) {
          notify(
            t(
              "Lokalny model nie odpowiedział — pokazuję sugestie wyliczone z audytu.",
            ),
          );
        }
        if (finished.status === "error" || !finished.result) {
          notify(
            `${kind === "flow" ? t("Nie udało się zaprojektować przepływu") : t("Optymalizacja nie powiodła się")}: ${finished.error ?? t("nieznany błąd")}`,
          );
          return;
        }
        apply(finished.result as DeliverState);
      } catch (error) {
        notify((error as Error).message);
      } finally {
        setJob(null);
      }
    },
    [projectId, notify, apply],
  );

  useEffect(() => {
    api
      .getDeliver(projectId)
      .then((data) => {
        apply(data);
        if (
          !data.flow.screens.length &&
          data.features.length &&
          !started.current
        ) {
          started.current = true;
          runJob("flow");
        }
      })
      .catch((error: Error) =>
        notify(
          t("Nie udało się wczytać fazy Deliver: {error}", {
            error: error.message,
          }),
        ),
      );
  }, [projectId, apply, runJob, notify]);

  const flush = useCallback(async () => {
    window.clearTimeout(saveTimer.current);
    if (!dirty.current) return;
    dirty.current = false;
    try {
      const saved = await api.saveFlow(projectId, flowRef.current);
      setAudit(saved.audit);
    } catch (error) {
      notify((error as Error).message);
    }
  }, [projectId, notify]);

  useEffect(() => () => void flush(), [flush]);

  const change = useCallback(
    (updater: (flow: Flow) => Flow) => {
      setFlow((current) => updater(current));
      dirty.current = true;
      window.clearTimeout(saveTimer.current);
      saveTimer.current = window.setTimeout(flush, 350);
    },
    [flush],
  );

  const mapScreen = useCallback(
    (screenId: string, fn: (screen: FlowScreen) => FlowScreen) =>
      change((current) => ({
        screens: current.screens.map((s) => (s.id === screenId ? fn(s) : s)),
      })),
    [change],
  );

  const actions: ScreenActions = useMemo(
    () => ({
      rename: (id, name) => mapScreen(id, (s) => ({ ...s, name })),
      cycleKind: (id, kind: ScreenKind) =>
        change((current) => ({
          screens: current.screens.map((s) => {
            if (s.id === id) return { ...s, kind };
            if ((kind === "start" || kind === "goal") && s.kind === kind)
              return { ...s, kind: "step" };
            return s;
          }),
        })),
      remove: (id) =>
        change((current) => ({
          screens: current.screens
            .filter((s) => s.id !== id)
            .map((s) => ({
              ...s,
              elements: s.elements.map((e) =>
                e.target === id ? { ...e, target: null } : e,
              ),
            })),
        })),
      addElement: (id) =>
        mapScreen(id, (s) => ({
          ...s,
          elements: [
            ...s.elements,
            {
              id: newId("e"),
              label: t("Nowy przycisk"),
              type: "button",
              size: "L",
              zone: "bottom",
              options: 1,
              target: null,
            },
          ],
        })),
      updateElement: (screenId, elementId, patch: Partial<FlowElement>) =>
        mapScreen(screenId, (s) => ({
          ...s,
          elements: s.elements.map((e) =>
            e.id === elementId ? { ...e, ...patch } : e,
          ),
        })),
      removeElement: (screenId, elementId) =>
        mapScreen(screenId, (s) => ({
          ...s,
          elements: s.elements.filter((e) => e.id !== elementId),
        })),
      dropFeature: (screenId, featureId) =>
        change((current) => ({
          screens: current.screens.map((s) =>
            s.id === screenId
              ? {
                  ...s,
                  feature_ids: s.feature_ids.includes(featureId)
                    ? s.feature_ids
                    : [...s.feature_ids, featureId],
                }
              : {
                  ...s,
                  feature_ids: s.feature_ids.filter((f) => f !== featureId),
                },
          ),
        })),
      removeFeature: (screenId, featureId) =>
        mapScreen(screenId, (s) => ({
          ...s,
          feature_ids: s.feature_ids.filter((f) => f !== featureId),
        })),
    }),
    [change, mapScreen],
  );

  const addScreen = () => {
    const last = flow.screens.reduce((max, s) => Math.max(max, s.x), -250);
    const screen: FlowScreen = {
      id: newId("s"),
      name: `Ekran ${flow.screens.length + 1}`,
      kind: flow.screens.length ? "step" : "start",
      x: last + 250,
      y: 260,
      feature_ids: [],
      elements: [
        {
          id: newId("e"),
          label: t("Dalej"),
          type: "button",
          size: "L",
          zone: "bottom",
          options: 1,
          target: null,
        },
      ],
    };
    change((current) => ({ screens: [...current.screens, screen] }));
    setSelectedId(screen.id);
    setFocusRequest({ id: screen.id, at: Date.now() });
  };

  const focusScreen = (id: string) => {
    setSelectedId(id);
    setFocusRequest({ id, at: Date.now() });
  };

  const accept = async (s: Suggestion) => {
    await flush();
    try {
      apply(await api.acceptSuggestion(projectId, s.id));
      focusScreen(s.screen_id);
    } catch (error) {
      notify((error as Error).message);
    }
  };

  const dismiss = async (s: Suggestion) => {
    setSuggestions((list) => list.filter((x) => x.id !== s.id));
    try {
      await api.dismissSuggestion(projectId, s.id);
    } catch (error) {
      notify((error as Error).message);
    }
  };

  const optimize = async () => {
    await flush();
    runJob("optimize");
  };

  const generateHandoff = async () => {
    await flush();
    setHandoffBusy(true);
    try {
      setHandoff(await api.handoff(projectId));
    } catch (error) {
      notify((error as Error).message);
    } finally {
      setHandoffBusy(false);
    }
  };

  const persona = state?.persona;
  const subtitle = `${persona ? `${persona.name} · ${persona.focus} · ` : ""}${t("Połącz ekrany i dopracuj doświadczenie")}`;
  const transitions = audit?.transitions ?? 0;

  return (
    <>
      <PageTitle
        title={t("Studio User Flow")}
        subtitle={subtitle}
      />

      <div className="pf-fade-up absolute" style={panelStyle(8.3, 113)}>
        {state && (
          <Toolbox
            features={state.features}
            screens={flow.screens}
            selectedId={selectedId}
            onFocusScreen={focusScreen}
            onAddScreen={addScreen}
          />
        )}
      </div>

      <div
        className="pf-fade-up absolute overflow-hidden"
        style={{ ...panelStyle(129.3, detailed ? 362.2 : 512.6), animationDelay: "60ms" }}
      >
        <div
          className="absolute z-10 flex items-start justify-between"
          style={{ left: u(9), right: u(9), top: u(9) }}
        >
          <div>
            <div
              className="font-serif text-ink"
              style={{ fontSize: "var(--text-title)", lineHeight: 1 }}
            >
              {t("Przepływ aplikacji")}
            </div>
            <div
              className="text-haze"
              style={{ fontSize: "var(--text-small)", marginTop: u(3) }}
            >
              {flow.screens.length}{" "}
              {plural(flow.screens.length, "ekran", "ekrany", "ekranów")} ·{" "}
              {transitions}{" "}
              {plural(transitions, "połączenie", "połączenia", "połączeń")}
            </div>
          </div>
          <div className="flex items-center gap-2 text-mauve" style={{fontSize: "var(--text-small)"}}>
            <button type="button" aria-pressed={detailed} className="rounded-full bg-[#f3ecfa] px-3 py-1"
              onClick={() => setDetailed(value => !value)}>{detailed ? t("Schemat") : t("Edytuj schemat")}</button>
            {!detailed && flow.screens.length > 0 && <button type="button" disabled={handoffBusy} onClick={generateHandoff}
              className="rounded-full bg-[#f3ecfa] px-3 py-1">{t("Eksportuj")}</button>}
            <ZoomControl />
          </div>
        </div>
        <div className="absolute inset-0" style={{ top: u(26) }}>
          {state && (
            <Canvas key={detailed ? "editor" : "diagram"} detailed={detailed}
              flow={flow}
              state={state}
              audit={audit ?? state.audit}
              selectedId={selectedId}
              focusRequest={focusRequest}
              onSelect={setSelectedId}
              onChange={change}
              actions={actions}
            />
          )}
        </div>
        {job?.kind === "flow" && (
          <div
            className="pf-fade-up absolute left-1/2 z-20 -translate-x-1/2"
            style={{
              top: u(120),
              width: u(300),
              height: u(42),
              borderRadius: u(10),
              background: "#fdfcfe",
              boxShadow: SHADOW,
            }}
          >
            <ProgressContent
              title={t("Projektuję przepływ…")}
              text={STAGE_TEXT[job.stage] ?? STAGE_TEXT.thinking}
              stage={job.stage}
            />
          </div>
        )}
        {!job && state && !flow.screens.length && (
          <div
            className="absolute inset-0 flex flex-col items-center justify-center text-center"
            style={{ gap: u(6) }}
          >
            <span className="text-mauve" style={{ fontSize: "var(--text-body)" }}>
              {state.features.length
                ? t("Przepływ jest pusty.")
                : t("Najpierw dodaj funkcje w fazie Develop.")}
            </span>
            {state.features.length > 0 && (
              <button
                type="button"
                onClick={() => runJob("flow")}
                className="rounded font-semibold text-on-pink"
                style={{
                  fontSize: "var(--text-body)",
                  padding: `${u(4)} ${u(10)}`,
                  background: "var(--color-pink-button)",
                }}
              >
                {t("Zaprojektuj przepływ z AI")}
              </button>
            )}
          </div>
        )}
      </div>

      {detailed && <>
      <div
        className="pf-fade-up absolute"
        style={{ ...panelStyle(498.6, 143.3), animationDelay: "120ms" }}
      >
        {audit && (
          <AuditPanel
            audit={audit}
            suggestions={suggestions}
            optimizing={job?.kind === "optimize"}
            handoffBusy={handoffBusy}
            onOptimize={optimize}
            onAccept={accept}
            onDismiss={dismiss}
            onHandoff={generateHandoff}
            onFocusScreen={focusScreen}
          />
        )}
      </div>

      <p
        className="pf-fade pointer-events-none absolute inset-x-0 text-center text-haze"
        style={{ top: u(436), fontSize: "var(--text-small)", lineHeight: 1.2 }}
      >
        {t("Audyt:")} Hick RT = a + b·log₂(n+1) · Fitts ID = log₂(2D/W) · KLM · WCAG 2.2 ·{" "}
        {t("sugestie i projekt z lokalnego modelu do weryfikacji")}
      </p>

      </>}

      {handoff && (
        <HandoffModal
          handoff={handoff}
          onClose={() => setHandoff(null)}
          onRestart={onRestart}
        />
      )}
    </>
  );
}

export function DeliverView(props: Props) {
  return (
    <ReactFlowProvider>
      <Studio {...props} />
    </ReactFlowProvider>
  );
}
