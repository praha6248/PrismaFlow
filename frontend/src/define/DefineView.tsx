import { ArrowLeft, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, waitForJob } from "../api";
import {
  BarProgress,
  ChoiceBar,
  FooterNote,
  IconButton,
  PageTitle,
  SkeletonCards,
  u,
} from "../components/ui";
import type { DefineState } from "../types";
import { PersonaCard } from "./PersonaCard";
import { ProblemCard } from "./ProblemCard";
import { t } from "../i18n";

const STAGE_TEXT: Record<string, string> = {
  queued: t("Przygotowuję analizę"),
  context: t("Zbieram dowody z mapy"),
  thinking: t("Model formułuje problemy"),
  trends: t("Porównuję w Google Trends"),
  quotes: t("Dobieram cytaty"),
  personas: t("Model tworzy persony"),
  saving: t("Zapisuję wyniki"),
  done: t("Gotowe"),
};

const COUNTRY_NAMES: Record<string, string> = {
  PL: t("Polska"),
  US: "USA",
  GB: t("Wielka Brytania"),
  DE: t("Niemcy"),
  FR: t("Francja"),
  ES: t("Hiszpania"),
  IT: t("Włochy"),
  CZ: t("Czechy"),
  UA: t("Ukraina"),
};

const WARNINGS: [string, string][] = [
  [
    "trends:",
    t(
      "Google Trends chwilowo nie odpowiada — pokazuję problemy bez indeksu zainteresowania.",
    ),
  ],
  [
    "autocomplete:",
    t("Google Autocomplete nie odpowiada — część cytatów może być pusta."),
  ],
];

type Screen = "problems" | "personas";

interface Props {
  projectId: number;
  onBack: () => void;
  onDone: () => void;
  notify: (message: string) => void;
}

export function DefineView({ projectId, onBack, onDone, notify }: Props) {
  const [state, setState] = useState<DefineState | null>(null);
  const [screen, setScreen] = useState<Screen>("problems");
  const [job, setJob] = useState<{
    kind: "problems" | "personas";
    stage: string;
  } | null>(null);
  const [problemId, setProblemId] = useState<number | null>(null);
  const [personaChoice, setPersonaChoice] = useState<{
    id: number;
    option: number;
  } | null>(null);
  const [saving, setSaving] = useState(false);
  const started = useRef(false);

  const run = useCallback(
    async (kind: "problems" | "personas") => {
      setJob({ kind, stage: "queued" });
      try {
        const started =
          kind === "problems"
            ? await api.generateProblems(projectId)
            : await api.generatePersonas(projectId);
        const finished = await waitForJob(started.id, (j) =>
          setJob({ kind, stage: j.stage }),
        );
        const seen = new Set<string>();
        for (const warning of finished.warnings) {
          const match = WARNINGS.find(([prefix]) => warning.startsWith(prefix));
          if (match && !seen.has(match[0])) {
            seen.add(match[0]);
            notify(match[1]);
          }
        }
        if (finished.status === "error" || !finished.result) {
          notify(
            kind === "problems"
              ? t("Nie udało się sformułować problemów: {error}", {
                  error: finished.error ?? t("nieznany błąd"),
                })
              : t("Nie udało się utworzyć person: {error}", {
                  error: finished.error ?? t("nieznany błąd"),
                }),
          );
          setState(await api.getDefine(projectId));
          return null;
        }
        const next = finished.result as DefineState;
        setState(next);
        return next;
      } catch (error) {
        notify((error as Error).message);
        return null;
      } finally {
        setJob(null);
      }
    },
    [projectId, notify],
  );

  useEffect(() => {
    api
      .getDefine(projectId)
      .then((data) => {
        setState(data);
        setProblemId(data.chosen_problem_id);
        const chosenPersona = data.personas.find(
          (p) => p.chosen_option !== null,
        );
        if (chosenPersona)
          setPersonaChoice({
            id: chosenPersona.id,
            option: chosenPersona.chosen_option as number,
          });
        if (
          data.project.stage === "personas" ||
          data.project.stage === "validate" ||
          data.project.stage === "done"
        ) {
          if (data.personas.length) setScreen("personas");
        }
        if (!data.problems.length && !started.current) {
          started.current = true;
          run("problems");
        }
      })
      .catch((error: Error) =>
        notify(
          t("Nie udało się wczytać fazy Define: {error}", {
            error: error.message,
          }),
        ),
      );
  }, [projectId, run, notify]);

  const problems = state?.problems ?? [];
  const chosenProblem =
    problems.find((p) => p.id === state?.chosen_problem_id) ?? null;
  const selectedProblem = problems.find((p) => p.id === problemId) ?? null;
  const scaleMax = useMemo(
    () =>
      Math.max(
        1,
        ...problems.flatMap((p) =>
          p.trend?.available ? (p.trend.months ?? []).map((m) => m.value) : [],
        ),
      ),
    [problems],
  );

  const confirmProblem = async () => {
    if (!selectedProblem) return;
    setSaving(true);
    try {
      const sameAsBefore =
        state?.chosen_problem_id === selectedProblem.id &&
        (state?.personas.length ?? 0) > 0;
      const next = await api.chooseProblem(selectedProblem.id);
      setState(next);
      setScreen("personas");
      if (!sameAsBefore || !next.personas.length) {
        setPersonaChoice(null);
        await run("personas");
      }
    } catch (error) {
      notify((error as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const confirmPersona = async () => {
    if (!personaChoice) return;
    setSaving(true);
    try {
      setState(await api.choosePersona(personaChoice.id, personaChoice.option));
      onDone();
    } catch (error) {
      notify((error as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const regenerate = () => {
    setProblemId(null);
    setPersonaChoice(null);
    if (screen === "problems") run("problems");
    else run("personas");
  };

  const country = state
    ? (COUNTRY_NAMES[state.project.geo] ?? state.project.geo)
    : "";
  const busy = job !== null;
  const progressTitle =
    job?.kind === "personas"
      ? t("Tworzę persony…")
      : t("Definiuję problemy…");

  if (screen === "personas") {
    const personas = state?.personas ?? [];
    const pickedPersona =
      personas.find((p) => p.id === personaChoice?.id) ?? null;
    return (
      <>
        <IconButton
          onClick={() => setScreen("problems")}
          title={t("Wróć do problemów")}
          left={41}
          top={102}
        >
          <ArrowLeft style={{ width: u(9), height: u(9) }} />
        </IconButton>
        {!busy && personas.length > 0 && (
          <IconButton
            onClick={regenerate}
            title={t("Wygeneruj persony ponownie")}
            left={569.3}
            top={102}
          >
            <RefreshCw style={{ width: u(8), height: u(8) }} />
          </IconButton>
        )}
        <PageTitle
          title={t("Czyj problem chcesz rozwiązać?")}
          subtitle={chosenProblem?.title}
        />
        {busy || !personas.length ? (
          <SkeletonCards />
        ) : (
          personas.map((persona, index) => (
            <PersonaCard
              key={persona.id}
              persona={persona}
              index={index}
              selectedOption={
                personaChoice?.id === persona.id ? personaChoice.option : null
              }
              onSelect={(option) =>
                setPersonaChoice({ id: persona.id, option })
              }
            />
          ))
        )}
        {busy ? (
          <BarProgress
            title={progressTitle}
            text={STAGE_TEXT[job.stage] ?? STAGE_TEXT.personas}
            stage={job.stage}
          />
        ) : (
          <ChoiceBar
            value={
              pickedPersona && personaChoice
                ? `${pickedPersona.name} · ${pickedPersona.options[personaChoice.option]}`
                : null
            }
            placeholder={
              personas.length
                ? t("Wybierz personę i jej główny problem")
                : t("Brak person — wygeneruj je ponownie")
            }
            disabled={!pickedPersona}
            busy={saving}
            onConfirm={confirmPersona}
          />
        )}
        <FooterNote>
          {t(
            "Persony i cytaty wygenerowane przez lokalny model · materiał koncepcyjny, nie wyniki wywiadów",
          )}
        </FooterNote>
        {!busy && !personas.length && state && (
          <button
            type="button"
            onClick={() => run("personas")}
            className="absolute left-1/2 -translate-x-1/2 text-plum underline"
            style={{ top: u(250), fontSize: u(7) }}
          >
            {t("Wygeneruj persony")}
          </button>
        )}
      </>
    );
  }

  return (
    <>
      <IconButton
        onClick={onBack}
        title={t("Wróć do mapy")}
        left={41}
        top={102}
      >
        <ArrowLeft style={{ width: u(9), height: u(9) }} />
      </IconButton>
      {!busy && problems.length > 0 && (
        <IconButton
          onClick={regenerate}
          title={t("Sformułuj problemy ponownie")}
          left={569.3}
          top={102}
        >
          <RefreshCw style={{ width: u(8), height: u(8) }} />
        </IconButton>
      )}
      <PageTitle
        title={t("Który problem chcesz rozwiązać?")}
        subtitle={t(
          "Porównaj sygnały zainteresowania i wybierz jeden główny problem.",
        )}
      />
      {busy || !problems.length ? (
        <SkeletonCards />
      ) : (
        problems.map((problem, index) => (
          <ProblemCard
            key={problem.id}
            problem={problem}
            index={index}
            selected={problem.id === problemId}
            scaleMax={scaleMax}
            onSelect={() => setProblemId(problem.id)}
          />
        ))
      )}
      {busy ? (
        <BarProgress
          title={progressTitle}
          text={STAGE_TEXT[job.stage] ?? STAGE_TEXT.thinking}
          stage={job.stage}
        />
      ) : (
        <ChoiceBar
          value={selectedProblem?.title ?? null}
          placeholder={
            problems.length
              ? t("Wybierz jeden problem")
              : t("Brak problemów — spróbuj ponownie")
          }
          disabled={!selectedProblem}
          busy={saving}
          onConfirm={confirmProblem}
        />
      )}
      <FooterNote>
        Google Trends · {country || "—"} ·{" "}
        {t("indeks względny 0–100 na wspólnej skali trzech haseł")}
      </FooterNote>
      {!busy && !problems.length && state && (
        <button
          type="button"
          onClick={() => run("problems")}
          className="absolute left-1/2 -translate-x-1/2 text-plum underline"
          style={{ top: u(250), fontSize: u(7) }}
        >
          {t("Sformułuj problemy")}
        </button>
      )}
    </>
  );
}
