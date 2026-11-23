import { ReactFlowProvider } from "@xyflow/react";
import { ArrowRight } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, waitForJob } from "../api";
import type { DiscoverStage, Graph, MapNode, Project, Stage } from "../types";
import { ComposerBar, ExpandProgress } from "./BottomBar";
import { relativeScores } from "./kinds";
import { EvidenceDrawer } from "./EvidenceDrawer";
import { composeSlot } from "./layout";
import { MindMap } from "./MindMap";
import { StartScreen } from "./StartScreen";
import { t } from "../i18n";

const WARNINGS: [string, string][] = [
  [
    "google trends: too many requests",
    t(
      "Google Trends ogranicza liczbę zapytań — wstrzymuję trendy na pewien czas, reszta mapy działa bez nich.",
    ),
  ],
  [
    "google trends: paused for",
    t(
      "Google Trends ogranicza liczbę zapytań — wstrzymuję trendy na pewien czas, reszta mapy działa bez nich.",
    ),
  ],
  [
    "(429)",
    t(
      "YouTube lub Stack Exchange ograniczają liczbę zapytań — wstrzymuję je na 15 minut, dyskusji będzie mniej.",
    ),
  ],
  [
    "competitor:",
    t(
      "Usunięto konkurencję, której nazwa nie pojawia się w wyszukiwaniach ani dyskusjach — model mógł ją zmyślić.",
    ),
  ],
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
    "autocomplete:",
    t("Google Autocomplete nie odpowiada — pomijam podpowiedzi."),
  ],
  [
    "trends:",
    t(
      "Google Trends chwilowo nie odpowiada — trendy uzupełnię przy kolejnej rozbudowie.",
    ),
  ],
];

const DISCOVER_STAGES: Stage[] = ["compose", "expanding", "select"];

interface Props {
  projectId: number | null;
  onResume: (project: Project) => void;
  onCreated: (projectId: number) => void;
  onOpenDefine: () => void;
  notify: (message: string) => void;
}

export function DiscoverView({
  projectId,
  onCreated,
  onResume,
  onOpenDefine,
  notify,
}: Props) {
  const [graph, setGraph] = useState<Graph | null>(null);
  const shown = useMemo(
    () => (graph ? { ...graph, nodes: relativeScores(graph.nodes) } : null),
    [graph],
  );
  const [leaving, setLeaving] = useState(false);
  const [creating, setCreating] = useState(false);
  const [localStage, setLocalStage] = useState<DiscoverStage | null>(null);
  const [jobStage, setJobStage] = useState("queued");
  const [focusedId, setFocusedId] = useState<number | null>(null);
  const shownWarnings = useRef(new Set<string>());
  const loadedId = graph?.project.id ?? null;
  const graphWasEnriched = useRef(false);
  const [jobId, setJobId] = useState<string | null>(null);

  useEffect(() => {
    if (projectId === null) return;
    let current = true;
    api
      .getProject(projectId)
      .then((data) => {
        if (!current) return;
        setJobId(data.expansion_job_id ?? null);
        const enriched = data.nodes.some((n) => n.enriched_at !== null);
        graphWasEnriched.current = enriched;
        if (
          !DISCOVER_STAGES.includes(data.project.stage) ||
          (data.project.stage === "expanding" && !data.expansion_job_id)
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
    return () => { current = false; };
  }, [projectId, notify]);

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
    graphWasEnriched.current = stage === "select";
    setLocalStage("expanding");
    setJobStage("queued");
    try {
      const job = await api.expand(
        graph.project.id,
        node?.is_root ? undefined : node?.id,
        3,
      );
      setJobId(job.id);
    } catch (error) {
      notify((error as Error).message);
      setLocalStage(previous);
    }
  };

  useEffect(() => {
    if (!jobId || projectId === null) return;
    const controller = new AbortController();
    const follow = async () => {
      const finished = await waitForJob(jobId, (j) => setJobStage(j.stage), 450, controller.signal);
      for (const warning of finished.warnings) {
        const match = WARNINGS.find(([prefix]) => warning.startsWith(prefix) || warning.includes(prefix));
        if (match && !shownWarnings.current.has(match[1])) {
          shownWarnings.current.add(match[1]);
          notify(match[1]);
        }
      }
      if (finished.status === "error" || !finished.result) {
        notify(
          t("Rozbudowa nie powiodła się: {error}", {
            error: finished.error ?? t("nieznany błąd"),
          }),
        );
        setGraph(await api.getProject(projectId));
        setLocalStage(null);
        return;
      }
      setGraph(finished.result as Graph);
      setLocalStage(null);
    };
    follow().catch((error: Error) => {
      if (controller.signal.aborted) return;
      notify(error.message);
      setJobId(null);
      setLocalStage(graphWasEnriched.current ? "select" : "compose");
    });
    return () => controller.abort();
  }, [jobId, projectId, notify]);

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
      {!graph && projectId === null && (
        <StartScreen onResume={onResume} notify={notify} leaving={leaving} busy={creating} onSubmit={start} />
      )}

      {graph && (
        <ReactFlowProvider>
          <div className="pf-fade absolute inset-0">
            <MindMap
              graph={shown ?? graph}
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
