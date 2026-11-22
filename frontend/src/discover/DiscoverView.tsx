import { ReactFlowProvider } from "@xyflow/react";
import { ArrowRight, Lock } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, waitForJob } from "../api";
import type { Graph, MapNode, Stage } from "../types";
import { ComposerBar, ExpandProgress } from "./BottomBar";
import { EvidenceDrawer } from "./EvidenceDrawer";
import { composeSlot } from "./layout";
import { MindMap } from "./MindMap";
import { StartScreen } from "./StartScreen";

const WARNINGS: [string, string][] = [
  ["llm:", "Lokalny model jest niedostępny — mapę rozbudowano na podstawie podpowiedzi Google."],
  ["reddit:", "Reddit odrzucił zapytania — pomijam wątki z Reddita."],
  ["trends:", "Google Trends chwilowo nie odpowiada — trendy uzupełnię przy kolejnej rozbudowie."],
  ["autocomplete:", "Google Autocomplete nie odpowiada — pomijam podpowiedzi."],
];

function projectFromHash(): number | null {
  const match = window.location.hash.match(/^#\/p\/(\d+)/);
  return match ? Number(match[1]) : null;
}

interface Props {
  resetSignal: number;
}

export function DiscoverView({ resetSignal }: Props) {
  const [graph, setGraph] = useState<Graph | null>(null);
  const [leaving, setLeaving] = useState(false);
  const [creating, setCreating] = useState(false);
  const [localStage, setLocalStage] = useState<Stage | null>(null);
  const [jobStage, setJobStage] = useState("queued");
  const [focusedId, setFocusedId] = useState<number | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const shownWarnings = useRef(new Set<string>());
  const toastTimer = useRef<number | undefined>(undefined);

  const notify = useCallback((message: string) => {
    setToast(message);
    window.clearTimeout(toastTimer.current);
    toastTimer.current = window.setTimeout(() => setToast(null), 6000);
  }, []);

  useEffect(() => {
    const id = projectFromHash();
    if (!id) return;
    api
      .getProject(id)
      .then((data) => {
        if (data.project.stage === "expanding") {
          const enriched = data.nodes.some((n) => n.enriched_at !== null);
          data = { ...data, project: { ...data.project, stage: enriched ? "select" : "compose" } };
        }
        setGraph(data);
      })
      .catch(() => (window.location.hash = ""));
  }, []);

  useEffect(() => {
    if (resetSignal === 0) return;
    setGraph(null);
    setLeaving(false);
    setFocusedId(null);
    setLocalStage(null);
    window.location.hash = "";
  }, [resetSignal]);

  const stage: Stage = localStage ?? graph?.project.stage ?? "compose";
  const busy = stage === "expanding";

  const start = async (seed: string) => {
    setCreating(true);
    setLeaving(true);
    try {
      const [data] = await Promise.all([api.createProject(seed), new Promise((r) => setTimeout(r, 380))]);
      window.location.hash = `#/p/${data.project.id}`;
      setGraph(data);
    } catch (error) {
      setLeaving(false);
      notify(`Nie udało się utworzyć projektu: ${(error as Error).message}`);
    } finally {
      setCreating(false);
    }
  };

  const addNode = async (label: string) => {
    if (!graph) return;
    const slot = composeSlot(graph.nodes.filter((n) => !n.is_root).length);
    try {
      setGraph(await api.addNode(graph.project.id, label, undefined, slot.x, slot.y));
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
      const job = await api.expand(graph.project.id, node?.is_root ? undefined : node?.id, 3);
      const finished = await waitForJob(job.id, (j) => setJobStage(j.stage));
      for (const warning of finished.warnings) {
        const match = WARNINGS.find(([prefix]) => warning.startsWith(prefix));
        if (match && !shownWarnings.current.has(match[0])) {
          shownWarnings.current.add(match[0]);
          notify(match[1]);
        }
      }
      if (finished.status === "error" || !finished.result) {
        notify(`Rozbudowa nie powiodła się: ${finished.error ?? "nieznany błąd"}`);
        setGraph(await api.getProject(graph.project.id));
        setLocalStage(previous);
        return;
      }
      setGraph(finished.result);
      setLocalStage(null);
    } catch (error) {
      notify((error as Error).message);
      setLocalStage(previous);
    }
  };

  const toggleStar = useCallback(
    async (node: MapNode) => {
      const starred = !node.starred;
      setGraph((g) => g && { ...g, nodes: g.nodes.map((n) => (n.id === node.id ? { ...n, starred } : n)) });
      try {
        await api.updateNode(node.id, { starred });
      } catch (error) {
        setGraph((g) => g && { ...g, nodes: g.nodes.map((n) => (n.id === node.id ? { ...n, starred: !starred } : n)) });
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

  const projectId = graph?.project.id;
  const savePositions = useCallback(
    (positions: { id: number; x: number; y: number }[]) => {
      if (projectId) api.savePositions(projectId, positions).catch(() => undefined);
    },
    [projectId],
  );

  const focused = useMemo(() => graph?.nodes.find((n) => n.id === focusedId) ?? null, [graph, focusedId]);
  const starredCount = graph?.nodes.filter((n) => n.starred).length ?? 0;
  const mapStage: Stage = stage === "expanding" && graph?.project.stage === "select" ? "select" : stage;

  return (
    <>
      {!graph && <StartScreen leaving={leaving} busy={creating} onSubmit={start} />}

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
          style={{ top: "calc(var(--u) * 104.2)", fontSize: "calc(var(--u) * 15)", lineHeight: 1 }}
        >
          Wybierz tematy, które Cię interesują
        </h2>
      )}

      {graph && stage === "compose" && <ComposerBar onAdd={addNode} onDone={() => expand()} />}
      {graph && stage === "expanding" && <ExpandProgress stage={jobStage} />}

      {graph && stage === "select" && starredCount > 0 && !focused && (
        <button
          type="button"
          disabled
          title="Faza Define jest w przygotowaniu"
          className="pf-fade-up absolute left-1/2 z-10 flex -translate-x-1/2 items-center rounded-full"
          style={{
            bottom: "calc(var(--u) * 18)",
            gap: "calc(var(--u) * 5)",
            padding: "calc(var(--u) * 6) calc(var(--u) * 12)",
            background: "#fdfcfe",
            color: "#853c77",
            fontSize: "calc(var(--u) * 7)",
            boxShadow: "0 calc(var(--u) * 2) calc(var(--u) * 10) rgba(196, 160, 232, 0.28)",
          }}
        >
          <Lock style={{ width: "calc(var(--u) * 7)" }} color="#aa9fb2" />
          Przejdź do Define
          <span className="rounded-full bg-[#fed3f9]" style={{ padding: "0 calc(var(--u) * 5)" }}>
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

      {toast && (
        <div
          role="status"
          className="pf-fade-up absolute left-1/2 z-40 -translate-x-1/2 text-center text-mauve"
          style={{
            top: "calc(var(--u) * 98)",
            maxWidth: "calc(var(--u) * 340)",
            padding: "calc(var(--u) * 5) calc(var(--u) * 12)",
            borderRadius: "calc(var(--u) * 10)",
            background: "rgba(255,255,255,0.92)",
            boxShadow: "0 calc(var(--u) * 2) calc(var(--u) * 10) rgba(196, 160, 232, 0.3)",
            fontSize: "calc(var(--u) * 6.4)",
          }}
          onClick={() => setToast(null)}
        >
          {toast}
        </div>
      )}
    </>
  );
}
