import { QualityButton } from "./components/QualitySettings";
import { SetupGuide, useSetup } from "./components/SetupGuide";
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api";
import { Header } from "./components/Header";
import { Toast } from "./components/Toast";
import { DefineView } from "./define/DefineView";
import { ValidateView } from "./validate/ValidateView";
import { BoardView } from "./research/BoardView";
import { EmpathyView } from "./research/EmpathyView";
import { DeliverView } from "./deliver/DeliverView";
import { DevelopView } from "./develop/DevelopView";
import { DiscoverView } from "./discover/DiscoverView";
import { PHASES, type Phase } from "./types";

type Sub = "board" | "validate" | "empathy";

interface Route {
  projectId: number | null;
  phase: Phase;
  sub?: Sub;
}

function parseHash(): Route {
  const match = window.location.hash.match(
    /^#\/p\/(\d+)(?:\/(define|board|validate|empathy|develop|deliver))?/,
  );
  if (!match) return { projectId: null, phase: "discover" };
  if (match[2] === "board" || match[2] === "validate" || match[2] === "empathy")
    return { projectId: Number(match[1]), phase: "define", sub: match[2] };
  return {
    projectId: Number(match[1]),
    phase: (match[2] as Phase | undefined) ?? "discover",
  };
}

function hashFor(route: Route): string {
  if (route.projectId === null) return "";
  if (route.sub) return `#/p/${route.projectId}/${route.sub}`;
  return route.phase === "discover"
    ? `#/p/${route.projectId}`
    : `#/p/${route.projectId}/${route.phase}`;
}

export function App() {
  const [route, setRoute] = useState<Route>(parseHash);
  const [reached, setReached] = useState<Phase>("discover");
  const [toast, setToast] = useState<string | null>(null);
  const toastTimer = useRef<number | undefined>(undefined);

  const notify = useCallback((message: string) => {
    setToast(message);
    window.clearTimeout(toastTimer.current);
    toastTimer.current = window.setTimeout(() => setToast(null), 6000);
  }, []);

  useEffect(() => {
    const onHash = () => setRoute(parseHash());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  const navigate = useCallback((next: Route) => {
    setRoute(next);
    const hash = hashFor(next);
    if (window.location.hash !== hash)
      window.history.pushState(null, "", hash || window.location.pathname);
  }, []);

  useEffect(() => {
    if (route.projectId === null) {
      setReached("discover");
      return;
    }
    api
      .getProject(route.projectId)
      .then((graph) => {
        const phase = graph.project.phase;
        setReached(phase);
        if (PHASES.indexOf(route.phase) > PHASES.indexOf(phase))
          navigate({ projectId: route.projectId, phase });
      })
      .catch(() => navigate({ projectId: null, phase: "discover" }));
  }, [route.projectId, route.phase, navigate]);

  const advance = useCallback(
    async (phase: Phase, sub?: Sub) => {
      if (route.projectId === null) return;
      const projectId = route.projectId;
      if (PHASES.indexOf(phase) > PHASES.indexOf(reached)) {
        try {
          await api.setPhase(projectId, phase);
          setReached(phase);
        } catch (error) {
          notify((error as Error).message);
          return;
        }
      }
      navigate({ projectId, phase, sub });
    },
    [route.projectId, reached, navigate, notify],
  );

  const projectId = route.projectId;
  const setup = useSetup();
  return (
    <div className="frame">
      <main className="card">
        <Header
          active={PHASES.indexOf(route.phase)}
          reached={PHASES.indexOf(reached)}
          onHome={() => navigate({ projectId: null, phase: "discover" })}
          onNavigate={(index) =>
            projectId !== null && navigate({ projectId, phase: PHASES[index] })
          }
        />
        <QualityButton onShowSetup={() => setup.setOpen(true)} />
        {setup.open && (
          <SetupGuide
            state={setup.state}
            onRefresh={setup.refresh}
            onClose={() => setup.setOpen(false)}
          />
        )}
        {route.phase === "discover" && (
          <DiscoverView
            projectId={projectId}
            onCreated={(id) => navigate({ projectId: id, phase: "discover" })}
            onOpenDefine={() => advance("define", "board")}
            notify={notify}
          />
        )}
        {route.phase !== "discover" && (
          <div className="stage">
            {route.phase === "define" &&
              route.sub === "board" &&
              projectId !== null && (
                <BoardView
                  key={projectId}
                  projectId={projectId}
                  onBack={() => navigate({ projectId, phase: "discover" })}
                  onDone={() => navigate({ projectId, phase: "define" })}
                  notify={notify}
                />
              )}
            {route.phase === "define" &&
              route.sub === "validate" &&
              projectId !== null && (
                <ValidateView
                  key={projectId}
                  projectId={projectId}
                  onBack={() => navigate({ projectId, phase: "define" })}
                  onDone={() => navigate({ projectId, phase: "define", sub: "empathy" })}
                  notify={notify}
                />
              )}
            {route.phase === "define" &&
              route.sub === "empathy" &&
              projectId !== null && (
                <EmpathyView
                  key={projectId}
                  projectId={projectId}
                  onBack={() => navigate({ projectId, phase: "define", sub: "validate" })}
                  onDone={() => advance("develop")}
                  notify={notify}
                />
              )}
            {route.phase === "define" &&
              !route.sub &&
              projectId !== null && (
                <DefineView
                  key={projectId}
                  projectId={projectId}
                  onBack={() => navigate({ projectId, phase: "define", sub: "board" })}
                  onDone={() =>
                    navigate({ projectId, phase: "define", sub: "validate" })
                  }
                  notify={notify}
                />
              )}
            {route.phase === "develop" && projectId !== null && (
              <DevelopView
                key={projectId}
                projectId={projectId}
                onDone={() => advance("deliver")}
                notify={notify}
              />
            )}
            {route.phase === "deliver" && projectId !== null && (
              <DeliverView
                key={projectId}
                projectId={projectId}
                notify={notify}
                onRestart={() =>
                  navigate({ projectId: null, phase: "discover" })
                }
              />
            )}
          </div>
        )}
        {toast && <Toast message={toast} onClose={() => setToast(null)} />}
      </main>
    </div>
  );
}
