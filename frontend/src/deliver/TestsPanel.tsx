import { ArrowRight, Flag, Play, RefreshCw, Trash2, X } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { api, waitForJob } from "../api";
import { u } from "../components/ui";
import { number, plural, t } from "../i18n";
import type { Flow, FlowElement, TestIssue, TestResult, TestsState } from "../types";

export function issueText(issue: TestIssue): string {
  if (issue.kind === "success")
    return t("„{task}”: cel osiągnęło {done} z {all} osób.", {
      task: issue.task,
      done: issue.successes,
      all: issue.attempts,
    });
  if (issue.kind === "slow")
    return t("„{task}”: ludzie potrzebowali {ratio}× więcej czasu, niż przewiduje KLM.", {
      task: issue.task,
      ratio: number(issue.ratio, 1),
    });
  return t("„{task}”: na ekranie „{screen}” najkrótszą drogę opuściło: {count}.", {
    task: issue.task,
    count: `${issue.count} ${plural(issue.count, "osoba", "osoby", "osób")}`,
    screen: issue.screen,
  });
}

type Tab = "tasks" | "run" | "results";

interface Props {
  projectId: number;
  flow: Flow;
  onClose: () => void;
  onChanged: (tests: TestsState) => void;
  notify: (message: string) => void;
}

function Phone({
  flow,
  screenId,
  onTap,
}: {
  flow: Flow;
  screenId: string | null;
  onTap: (element: FlowElement) => void;
}) {
  const screen = flow.screens.find((s) => s.id === screenId);
  return (
    <div
      className="flex shrink-0 flex-col bg-white"
      style={{
        width: u(128),
        height: u(240),
        borderRadius: u(14),
        border: `${u(3)} solid #2b1f36`,
        padding: u(7),
        gap: u(4),
      }}
    >
      {screen ? (
        <>
          <span className="font-serif text-ink" style={{ fontSize: "var(--text-body)", lineHeight: 1.1 }}>
            {screen.name}
          </span>
          {(["top", "center", "bottom"] as const).map((zone) => (
            <div
              key={zone}
              className="flex flex-col"
              style={{ gap: u(3), marginTop: zone === "bottom" ? "auto" : undefined, flex: zone === "center" ? 1 : undefined }}
            >
              {screen.elements
                .filter((e) => e.zone === zone)
                .map((element) => {
                  const primary = element.type === "button" && element.target;
                  return (
                    <button
                      key={element.id}
                      type="button"
                      onClick={() => onTap(element)}
                      className={
                        element.type === "link"
                          ? "text-left text-pink-text underline"
                          : primary
                            ? "rounded font-semibold text-on-pink"
                            : "rounded bg-[#f4eff8] text-left text-ink"
                      }
                      style={{
                        fontSize: "var(--text-small)",
                        padding: element.type === "link" ? 0 : `${u(element.size === "L" ? 5 : element.size === "M" ? 3.5 : 2)} ${u(4)}`,
                        background: primary ? "var(--color-pink-button)" : undefined,
                      }}
                    >
                      {element.label}
                    </button>
                  );
                })}
            </div>
          ))}
        </>
      ) : (
        <span className="m-auto text-center text-haze" style={{ fontSize: "var(--text-small)" }}>
          {t("Brak ekranu startowego")}
        </span>
      )}
    </div>
  );
}

export function TestsPanel({ projectId, flow, onClose, onChanged, notify }: Props) {
  const [state, setState] = useState<TestsState | null>(null);
  const [tab, setTab] = useState<Tab>("tasks");
  const [planning, setPlanning] = useState(false);
  const [participant, setParticipant] = useState("");
  const [index, setIndex] = useState(-1);
  const [screen, setScreen] = useState<string | null>(null);
  const [path, setPath] = useState<string[]>([]);
  const [quote, setQuote] = useState("");
  const [outcome, setOutcome] = useState<boolean | null>(null);
  const [results, setResults] = useState<TestResult[]>([]);
  const started = useRef(0);
  const elapsed = useRef(0);
  const [sent, setSent] = useState<Record<string, string>>({});

  const apply = useCallback(
    (next: TestsState) => {
      setState(next);
      onChanged(next);
    },
    [onChanged],
  );

  useEffect(() => {
    api
      .tests(projectId)
      .then((next) => {
        apply(next);
        if (next.participants) setTab("results");
      })
      .catch((error: Error) => notify(error.message));
  }, [projectId, apply, notify]);

  const plan = async () => {
    setPlanning(true);
    try {
      const job = await api.planTests(projectId);
      const finished = await waitForJob(job.id, () => undefined);
      if (finished.status === "error" || !finished.result) {
        notify(t("Nie udało się przygotować zadań: {error}", { error: finished.error ?? t("nieznany błąd") }));
        return;
      }
      apply(finished.result as TestsState);
    } catch (error) {
      notify((error as Error).message);
    } finally {
      setPlanning(false);
    }
  };

  const tasks = state?.tasks ?? [];
  const task = index >= 0 ? tasks[index] : null;

  const beginTask = (next: number) => {
    setIndex(next);
    setScreen(state?.start ?? null);
    setPath(state?.start ? [state.start] : []);
    setQuote("");
    setOutcome(null);
    started.current = performance.now();
  };

  const finish = (success: boolean) => {
    elapsed.current = (performance.now() - started.current) / 1000;
    setOutcome(success);
  };

  const tap = (element: FlowElement) => {
    if (!task || outcome !== null || !element.target) return;
    setScreen(element.target);
    setPath((current) => [...current, element.target!]);
    if (element.target === task.goal) finish(true);
  };

  const next = async () => {
    if (!task || outcome === null) return;
    const all = [
      ...results,
      { task: task.id, success: outcome, seconds: Math.round(elapsed.current * 10) / 10, path, quote: quote.trim() },
    ];
    setResults(all);
    if (index + 1 < tasks.length) {
      beginTask(index + 1);
      return;
    }
    try {
      apply(await api.addSession(projectId, participant.trim(), all));
      setResults([]);
      setIndex(-1);
      setParticipant("");
      setTab("results");
    } catch (error) {
      notify((error as Error).message);
    }
  };

  const send = async (key: string, text: string, target: "board" | "backlog") => {
    try {
      await api.sendFinding(projectId, text, target);
      setSent((current) => ({ ...current, [key]: target }));
    } catch (error) {
      notify((error as Error).message);
    }
  };

  const LoopButtons = ({ id, text }: { id: string; text: string }) =>
    sent[id] ? (
      <span className="shrink-0 text-success" style={{ fontSize: "var(--text-small)" }}>
        {sent[id] === "board" ? t("Na tablicy Define") : t("W backlogu Develop")}
      </span>
    ) : (
      <span className="flex shrink-0" style={{ gap: u(2) }}>
        <button
          type="button"
          onClick={() => send(id, text, "board")}
          className="rounded bg-[#efe9f7] text-ink hover:brightness-95"
          style={{ fontSize: "var(--text-small)", padding: `${u(1)} ${u(3)}` }}
          title={t("Dodaj jako notatkę na tablicy w Define")}
        >
          → Define
        </button>
        <button
          type="button"
          onClick={() => send(id, text, "backlog")}
          className="rounded bg-[#fde7f8] text-ink hover:brightness-95"
          style={{ fontSize: "var(--text-small)", padding: `${u(1)} ${u(3)}` }}
          title={t("Dodaj jako funkcję do backlogu w Develop")}
        >
          → Develop
        </button>
      </span>
    );

  const tabs: [Tab, string][] = [
    ["tasks", t("Zadania")],
    ["run", t("Przeprowadź test")],
    ["results", t("Wyniki")],
  ];

  return (
    <div
      className="pf-fade absolute inset-0 z-40 flex items-center justify-center bg-[rgba(243,238,255,0.6)] backdrop-blur-[2px]"
      onClick={onClose}
    >
      <div
        className="pf-fade-up flex flex-col"
        onClick={(e) => e.stopPropagation()}
        style={{
          width: u(500),
          height: u(340),
          borderRadius: u(12),
          background: "#fdfcfe",
          boxShadow: `0 ${u(6)} ${u(30)} rgba(170, 120, 210, 0.3)`,
          padding: u(14),
          gap: u(8),
        }}
      >
        <div className="flex items-center" style={{ gap: u(6) }}>
          <span className="font-serif text-ink" style={{ fontSize: "var(--text-title)" }}>
            {t("Testy z użytkownikami")}
          </span>
          <div className="ml-auto flex rounded-full bg-[#f3ecfa]" style={{ padding: u(2), gap: u(2) }}>
            {tabs.map(([key, label]) => (
              <button
                key={key}
                type="button"
                onClick={() => setTab(key)}
                className={tab === key ? "rounded-full bg-white text-ink shadow-sm" : "rounded-full text-mauve"}
                style={{ fontSize: "var(--text-small)", padding: `${u(2)} ${u(7)}` }}
              >
                {label}
              </button>
            ))}
          </div>
          <button type="button" onClick={onClose} aria-label={t("Zamknij")} className="text-haze hover:text-ink">
            <X style={{ width: u(9), height: u(9) }} />
          </button>
        </div>

        {tab === "tasks" && (
          <div className="pf-scroll flex min-h-0 flex-1 flex-col overflow-y-auto" style={{ gap: u(5) }}>
            <p className="text-mauve" style={{ fontSize: "var(--text-small)", lineHeight: 1.45 }}>
              {t(
                "Jedno zadanie na każdy ekran celu. Czytaj scenariusz uczestnikowi na głos i nie podpowiadaj, gdzie kliknąć. 5 osób wystarczy, żeby znaleźć większość problemów.",
              )}
            </p>
            {tasks.map((item, i) => (
              <label key={item.id} className="flex flex-col" style={{ gap: u(2) }}>
                <span className="text-haze" style={{ fontSize: "var(--text-small)" }}>
                  {t("Zadanie {n} · cel: {goal}", { n: i + 1, goal: item.goal_name })}
                </span>
                <textarea
                  defaultValue={item.scenario}
                  rows={3}
                  onBlur={async (e) => {
                    if (e.target.value.trim() && e.target.value !== item.scenario) {
                      try {
                        apply(await api.updateTask(projectId, item.id, e.target.value));
                      } catch (error) {
                        notify((error as Error).message);
                      }
                    }
                  }}
                  className="select-text resize-none rounded-md border border-[#eadff3] bg-white text-ink outline-none focus:border-pink"
                  style={{ fontSize: "var(--text-body)", padding: u(5), lineHeight: 1.35 }}
                />
              </label>
            ))}
            <div className="mt-auto flex items-center" style={{ gap: u(5) }}>
              <button
                type="button"
                onClick={plan}
                disabled={planning || !flow.screens.length}
                className="flex items-center rounded-md bg-[#e9dcf8] text-ink disabled:opacity-50"
                style={{ fontSize: "var(--text-small)", padding: `${u(4)} ${u(8)}`, gap: u(3) }}
              >
                <RefreshCw className={planning ? "animate-spin" : undefined} style={{ width: u(6), height: u(6) }} />
                {tasks.length ? t("Napisz zadania ponownie") : t("Przygotuj zadania")}
              </button>
              <button
                type="button"
                onClick={() => setTab("run")}
                disabled={!tasks.length}
                className="ml-auto flex items-center rounded-md font-semibold text-on-pink disabled:opacity-40"
                style={{ fontSize: "var(--text-small)", padding: `${u(4)} ${u(8)}`, gap: u(3), background: "var(--color-pink-button)" }}
              >
                {t("Przejdź do testu")}
                <ArrowRight style={{ width: u(6), height: u(6) }} />
              </button>
            </div>
          </div>
        )}

        {tab === "run" && (
          <div className="flex min-h-0 flex-1" style={{ gap: u(10) }}>
            <Phone flow={flow} screenId={task ? screen : state?.start ?? null} onTap={tap} />
            <div className="flex min-w-0 flex-1 flex-col" style={{ gap: u(5) }}>
              {!task ? (
                <>
                  <p className="text-mauve" style={{ fontSize: "var(--text-small)", lineHeight: 1.45 }}>
                    {t(
                      "Daj uczestnikowi prototyp obok. Czas liczy się od startu zadania; dojście do ekranu celu kończy zadanie sukcesem.",
                    )}
                  </p>
                  <input
                    value={participant}
                    onChange={(e) => setParticipant(e.target.value)}
                    placeholder={t("Uczestnik (imię lub kod, np. P1)")}
                    className="select-text rounded-md border border-[#eadff3] bg-white text-ink outline-none focus:border-pink"
                    style={{ fontSize: "var(--text-body)", padding: `${u(3)} ${u(5)}` }}
                  />
                  <button
                    type="button"
                    onClick={() => beginTask(0)}
                    disabled={!participant.trim() || !tasks.length || !state?.start}
                    className="flex items-center justify-center rounded-md font-semibold text-on-pink disabled:opacity-40"
                    style={{ fontSize: "var(--text-body)", padding: u(5), gap: u(3), background: "var(--color-pink-button)" }}
                  >
                    <Play style={{ width: u(6), height: u(6) }} />
                    {t("Rozpocznij zadanie 1 z {n}", { n: tasks.length })}
                  </button>
                </>
              ) : (
                <>
                  <span className="text-haze" style={{ fontSize: "var(--text-small)" }}>
                    {t("{who} · zadanie {n} z {all}", { who: participant, n: index + 1, all: tasks.length })}
                  </span>
                  <p
                    className="font-serif text-ink"
                    style={{ fontSize: "var(--text-body)", lineHeight: 1.4, padding: u(6), borderRadius: u(6), background: "#f7f3fb" }}
                  >
                    {task.scenario}
                  </p>
                  {outcome === null ? (
                    <button
                      type="button"
                      onClick={() => finish(false)}
                      className="flex items-center self-start text-error hover:underline"
                      style={{ fontSize: "var(--text-small)", gap: u(2) }}
                    >
                      <Flag style={{ width: u(5.5), height: u(5.5) }} />
                      {t("Uczestnik się poddał")}
                    </button>
                  ) : (
                    <span className={outcome ? "text-success" : "text-error"} style={{ fontSize: "var(--text-small)" }}>
                      {outcome
                        ? t("Cel osiągnięty w {s} s, {steps}.", {
                            s: number(elapsed.current, 1),
                            steps: `${path.length - 1} ${plural(path.length - 1, "krok", "kroki", "kroków")}`,
                          })
                        : t("Zadanie nieukończone po {s} s.", { s: number(elapsed.current, 1) })}
                    </span>
                  )}
                  <textarea
                    value={quote}
                    onChange={(e) => setQuote(e.target.value)}
                    placeholder={t("Co uczestnik powiedział lub gdzie się zawahał? Zapisz dosłownie.")}
                    className="pf-scroll min-h-0 flex-1 select-text resize-none rounded-md border border-[#eadff3] bg-white text-ink outline-none focus:border-pink"
                    style={{ fontSize: "var(--text-small)", padding: u(5), lineHeight: 1.4 }}
                  />
                  <button
                    type="button"
                    onClick={next}
                    disabled={outcome === null}
                    className="flex items-center justify-center rounded-md font-semibold text-on-pink disabled:opacity-40"
                    style={{ fontSize: "var(--text-body)", padding: u(5), gap: u(3), background: "var(--color-pink-button)" }}
                  >
                    {index + 1 < tasks.length ? t("Następne zadanie") : t("Zapisz sesję")}
                    <ArrowRight style={{ width: u(6), height: u(6) }} />
                  </button>
                </>
              )}
            </div>
          </div>
        )}

        {tab === "results" && (
          <div className="pf-scroll flex min-h-0 flex-1 flex-col overflow-y-auto" style={{ gap: u(5) }}>
            {!state?.participants && (
              <p className="text-mauve" style={{ fontSize: "var(--text-small)" }}>
                {t("Brak sesji. Przeprowadź test z co najmniej jedną osobą.")}
              </p>
            )}
            {(state?.issues ?? []).map((issue, i) => (
              <div key={`issue-${i}`} className="flex items-center rounded-md bg-[#fdebf7]" style={{ padding: `${u(3)} ${u(5)}`, gap: u(4) }}>
                <span className="min-w-0 flex-1 text-ink" style={{ fontSize: "var(--text-small)", lineHeight: 1.35 }}>
                  {issueText(issue)}
                </span>
                <LoopButtons id={`issue-${i}`} text={issueText(issue)} />
              </div>
            ))}
            {tasks
              .filter((item) => item.attempts)
              .map((item) => (
                <div key={item.id} className="rounded-md bg-white" style={{ padding: u(5), border: `${u(0.5)} solid #efe6f6` }}>
                  <div className="flex items-baseline text-ink" style={{ gap: u(4), fontSize: "var(--text-small)" }}>
                    <span className="font-semibold">{item.goal_name}</span>
                    <span className="ml-auto text-mauve">
                      {t("sukces {done}/{all}", { done: item.successes, all: item.attempts })}
                      {item.seconds !== null && ` · ${t("{s} s", { s: number(item.seconds, 1) })}`}
                      {item.predicted !== null && ` · KLM ${number(item.predicted, 1)} s`}
                    </span>
                  </div>
                  {item.quotes.map((q, i) => (
                    <div key={i} className="flex items-center" style={{ gap: u(4), marginTop: u(3) }}>
                      <span className="min-w-0 flex-1 font-serif italic text-ink" style={{ fontSize: "var(--text-small)" }}>
                        {q.participant}: „{q.quote}”
                      </span>
                      <LoopButtons id={`${item.id}-${i}`} text={`${q.participant} (${item.goal_name}): ${q.quote}`} />
                    </div>
                  ))}
                </div>
              ))}
            {(state?.sessions ?? []).length > 0 && (
              <div className="flex flex-wrap items-center" style={{ gap: u(3) }}>
                <span className="text-haze" style={{ fontSize: "var(--text-small)" }}>
                  {t("Sesje:")}
                </span>
                {state!.sessions.map((session) => (
                  <span
                    key={session.id}
                    className="flex items-center rounded-full bg-[#f3ecfa] text-mauve"
                    style={{ fontSize: "var(--text-small)", padding: `${u(1)} ${u(4)}`, gap: u(2) }}
                  >
                    {session.participant}
                    <button
                      type="button"
                      aria-label={t("Usuń sesję: {who}", { who: session.participant })}
                      onClick={async () => {
                        try {
                          apply(await api.removeSession(projectId, session.id));
                        } catch (error) {
                          notify((error as Error).message);
                        }
                      }}
                      className="text-haze hover:text-ink"
                    >
                      <Trash2 style={{ width: u(4.5), height: u(4.5) }} />
                    </button>
                  </span>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
