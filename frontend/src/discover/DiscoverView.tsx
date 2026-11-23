import { ReactFlowProvider } from "@xyflow/react";
import { ArrowRight } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, waitForJob } from "../api";
import type { DiscoverStage, Graph, MapNode, Stage } from "../types";
import { ComposerBar, ExpandProgress } from "./BottomBar";
import { EvidenceDrawer } from "./EvidenceDrawer";
import { composeSlot } from "./layout";
import { MindMap } from "./MindMap";
import { StartScreen } from "./StartScreen";
import { t } from "../i18n";

const WARNINGS: [string, string][] = [
  [
    "llm:",
    t(
      "Lokalny model jest niedostępny — mapę rozbudowano na podstawie podpowiedzi Google.",
    ),
  ],
  [
    "community:",
    t("Stack Exchange i Lemmy chwilowo nie odpowiadają — pomijam dyskusje."),
  ],
  [
    "trends:",
    t(
      "Google Trends chwilowo nie odpowiada — trendy uzupełnię przy kolejnej rozbudowie.",
    ),
  ],
  [
    "autocomplete:",
    t("Google Autocomplete nie odpowiada — pomijam podpowiedzi."),
  ],
];

const DISCOVER_STAGES: Stage[] = ["compose", "expanding", "select"];

interface Props {
  projectId: number | null;
  onCreated: (projectId: number) => void;
  onOpenDefine: () => void;
  notify: (message: string) => void;
}

export function DiscoverView({
  projectId,
  onCreated,
  onOpenDefine,
  notify,
}: Props) {
  const [graph, setGraph] = useState<Graph | null>(null);
  const [leaving, setLeaving] = useState(false);
  const [creating, setCreating] = useState(false);
  const [localStage, setLocalStage] = useState<DiscoverStage | null>(null);
  const [jobStage, setJobStage] = useState("queued");
  const [focusedId, setFocusedId] = useState<number | null>(null);
  const shownWarnings = useRef(new Set<string>());
  const loadedId = graph?.project.id ?? null;

  useEffect(() => {
    if (projectId === null) {
      setGraph(null);
      setLeaving(false);
      setFocusedId(null);
      setLocalStage(null);
      return;
    }
    if (projectId === loadedId) return;
    api
      .getProject(projectId)
      .then((data) => {
        const enriched = data.nodes.some((n) => n.enriched_at !== null);
        if (
          !DISCOVER_STAGES.includes(data.project.stage) ||
          data.project.stage === "expanding"
        ) {
          data = {
            ...data,
            project: {
              ...data.project,
              stage: enriched ? "select" : "compose",
            },
          };
        }
        setGraph(data);
      })
      .catch((error: Error) =>
        notify(
          t("Nie udało się wczytać projektu: {error}", {
            error: error.message,
          }),
        ),
      );
  }, [projectId, loadedId, notify]);

  const stage = (localStage ??
    graph?.project.stage ??
    "compose") as DiscoverStage;
  const busy = stage === "expanding";

  const start = async (seed: string) => {
    setCreating(true);
    setLeaving(true);
    try {
      const [data] = await Promise.all([
        api.createProject(seed),
        new Promise((r) => setTimeout(r, 380)),
      ]);
      setGraph(data);
      onCreated(data.project.id);
    } catch (error) {
      setLeaving(false);
      notify(
        t("Nie udało się utworzyć projektu: {error}", {
          error: (error as Error).message,
        }),
      );
    } finally {
      setCreating(false);
    }
  };

  const addNode = async (label: string) => {
    if (!graph) return;
    const slot = composeSlot(graph.nodes.filter((n) => !n.is_root).length);
    try {
      setGraph(
        await api.addNode(graph.project.id, label, undefined, slot.x, slot.y),
      );
    } catch (error) {
      notify((error as Error).message);
    }
  };

  const expand = async (node?: MapNode) => {
    if (!graph || busy) return;
    const previous = stage;
    setLocalStage("expanding");
    setJobStage("queued");
    try {
      const job = await api.expand(
        graph.project.id,
        node?.is_root ? undefined : node?.id,
        3,
      );
      const finished = await waitForJob(job.id, (j) => setJobStage(j.stage));
      for (const warning of finished.warnings) {
        const match = WARNINGS.find(([prefix]) => warning.startsWith(prefix));
        if (match && !shownWarnings.current.has(match[0])) {
          shownWarnings.current.add(match[0]);
          notify(match[1]);
        }
      }
      if (finished.status === "error" || !finished.result) {
        notify(
          t("Rozbudowa nie powiodła się: {error}", {
            error: finished.error ?? t("nieznany błąd"),
          }),
        );
        setGraph(await api.getProject(graph.project.id));
        setLocalStage(previous);
        return;
      }
      setGraph(finished.result as Graph);
      setLocalStage(null);
    } catch (error) {
      notify((error as Error).message);
      setLocalStage(previous);
    }
  };

  const toggleStar = useCallback(
    async (node: MapNode) => {
      const starred = !node.starred;
      setGraph(
        (g) =>
          g && {
            ...g,
            nodes: g.nodes.map((n) =>
              n.id === node.id ? { ...n, starred } : n,
            ),
          },
      );
      try {
        await api.updateNode(node.id, { starred });
      } catch (error) {
        setGraph(
          (g) =>
            g && {
              ...g,
              nodes: g.nodes.map((n) =>
                n.id === node.id ? { ...n, starred: !starred } : n,
              ),
            },
        );
        notify((error as Error).message);
      }
    },
    [notify],
  );

  const removeNode = async (node: MapNode) => {
    try {
      setGraph(await api.deleteNode(node.id));
      setFocusedId(null);
    } catch (error) {
      notify((error as Error).message);
    }
  };

  const savePositions = useCallback(
    (positions: { id: number; x: number; y: number }[]) => {
      if (loadedId)
        api.savePositions(loadedId, positions).catch(() => undefined);
    },
    [loadedId],
  );

  const focused = useMemo(
    () => graph?.nodes.find((n) => n.id === focusedId) ?? null,
    [graph, focusedId],
  );
  const starredCount = graph?.nodes.filter((n) => n.starred).length ?? 0;
  const mapStage: DiscoverStage =
    stage === "expanding" && graph?.project.stage === "select"
      ? "select"
      : stage;

  return (
    <>
      {!graph && (
        <StartScreen leaving={leaving} busy={creating} onSubmit={start} />
      )}

      {graph && (
        <ReactFlowProvider>
          <div className="pf-fade absolute inset-0">
            <MindMap
              graph={graph}
              stage={mapStage}
              focusedId={focusedId}
              onFocus={setFocusedId}
              onToggleStar={toggleStar}
              onPositions={savePositions}
              rightInset={focused ? 172 : 0}
            />
          </div>
        </ReactFlowProvider>
      )}

      {graph && mapStage === "select" && (
        <h2
          className="pf-fade pointer-events-none absolute inset-x-0 z-10 text-center font-serif font-normal text-plum"
          style={{
            top: "calc(var(--u) * 104.2)",
            fontSize: "var(--text-title)",
            lineHeight: 1,
          }}
        >
          {t("Wybierz tematy, które Cię interesują")}
        </h2>
      )}

      {graph && stage === "compose" && (
        <ComposerBar onAdd={addNode} onDone={() => expand()} />
      )}
      {graph && stage === "expanding" && <ExpandProgress stage={jobStage} />}

      {graph && stage === "select" && starredCount > 0 && !focused && (
        <button
          type="button"
          onClick={onOpenDefine}
          className="pf-fade-up absolute left-1/2 z-10 flex -translate-x-1/2 items-center rounded-full transition-transform hover:scale-[1.02] active:scale-[0.98]"
          style={{
            bottom: "calc(var(--u) * 18)",
            gap: "calc(var(--u) * 5)",
            padding: "calc(var(--u) * 6) calc(var(--u) * 12)",
            background: "#fdfcfe",
            color: "#853c77",
            fontSize: "var(--text-body)",
            boxShadow:
              "0 calc(var(--u) * 2) calc(var(--u) * 10) rgba(196, 160, 232, 0.28)",
          }}
        >
          {t("Przejdź do Define")}
          <span
            className="rounded-full bg-pink-soft"
            style={{ padding: "0 calc(var(--u) * 5)" }}
          >
            {starredCount}
          </span>
          <ArrowRight style={{ width: "calc(var(--u) * 7)" }} />
        </button>
      )}

      {graph && focused && (
        <EvidenceDrawer
          node={focused}
          busy={busy}
          onClose={() => setFocusedId(null)}
          onToggleStar={toggleStar}
          onExpand={(n) => expand(n)}
          onDelete={removeNode}
        />
      )}
    </>
  );
}
