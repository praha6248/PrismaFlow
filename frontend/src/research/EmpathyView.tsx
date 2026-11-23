import { ArrowLeft, Frown, Quote, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { api, waitForJob } from "../api";
import {
  BarProgress,
  ChoiceBar,
  FooterNote,
  IconButton,
  PageTitle,
  Radio,
  SHADOW,
  u,
} from "../components/ui";
import { t } from "../i18n";
import type { EmpathyItem, EmpathyState, JourneyStage, NoteRef } from "../types";
import { sourceLabel } from "./BoardView";

const QUADRANTS: { key: "says" | "thinks" | "does" | "feels"; label: string }[] = [
  { key: "says", label: t("MÓWI") },
  { key: "thinks", label: t("MYŚLI") },
  { key: "does", label: t("ROBI") },
  { key: "feels", label: t("CZUJE") },
];

const PHASES: Record<JourneyStage["phase"], string> = {
  before: t("Przed"),
  during: t("W trakcie"),
  after: t("Po"),
};

const panel = (left: number, top: number, width: number, height: number) => ({
  left: u(left),
  top: u(top),
  width: u(width),
  height: u(height),
  borderRadius: u(10),
  background: "#fdfcfe",
  boxShadow: SHADOW,
});

function origin(from: NoteRef | null): string {
  return from
    ? `${sourceLabel(from.source, from.label)}: „${from.text}”`
    : t("Wniosek modelu z profilu persony — sprawdź w rozmowie");
}

function Item({ item }: { item: EmpathyItem }) {
  return (
    <li
      title={origin(item.from)}
      className={item.from ? "text-ink" : "italic text-mauve"}
      style={{ fontSize: "var(--text-small)", lineHeight: 1.35 }}
    >
      {item.from && (
        <Quote
          className="mr-1 inline text-pink-text"
          style={{ width: u(4.5), height: u(4.5), verticalAlign: "baseline" }}
        />
      )}
      {item.text}
    </li>
  );
}

interface Props {
  projectId: number;
  onBack: () => void;
  onDone: () => void;
  notify: (message: string) => void;
}

export function EmpathyView({ projectId, onBack, onDone, notify }: Props) {
  const [state, setState] = useState<EmpathyState | null>(null);
  const [stage, setStage] = useState<string | null>(null);
  const [question, setQuestion] = useState("");
  const started = useRef(false);

  const generate = useCallback(async () => {
    setStage("thinking");
    try {
      const job = await api.generateEmpathy(projectId);
      const finished = await waitForJob(job.id, (j) => setStage(j.stage));
      if (finished.status === "error" || !finished.result) {
        notify(
          t("Nie udało się zbudować mapy empatii: {error}", {
            error: finished.error ?? t("nieznany błąd"),
          }),
        );
        return;
      }
      const next = finished.result as EmpathyState;
      setState(next);
      setQuestion(next.map?.hmw_chosen ?? "");
    } catch (error) {
      notify((error as Error).message);
    } finally {
      setStage(null);
    }
  }, [projectId, notify]);

  useEffect(() => {
    api
      .empathy(projectId)
      .then((data) => {
        setState(data);
        setQuestion(data.map?.hmw_chosen ?? "");
        if (!data.map && data.persona && !started.current) {
          started.current = true;
          generate();
        }
      })
      .catch((error: Error) => notify(error.message));
  }, [projectId, generate, notify]);

  const choose = async (text: string) => {
    const clean = text.trim();
    setQuestion(clean);
    if (!state?.map || clean.length < 5 || clean === state.map.hmw_chosen) return;
    try {
      setState(await api.chooseHmw(projectId, clean));
    } catch (error) {
      notify((error as Error).message);
    }
  };

  const map = state?.map;
  const busy = stage !== null;
  const journey = map?.journey ?? [];
  const points = journey
    .map((s, i) => `${((i + 0.5) / journey.length) * 100},${20 - s.emotion * 8}`)
    .join(" ");

  return (
    <>
      <IconButton onClick={onBack} title={t("Wróć do wywiadów")} left={41} top={102}>
        <ArrowLeft style={{ width: u(9), height: u(9) }} />
      </IconButton>
      {!busy && map && (
        <IconButton onClick={generate} title={t("Zbuduj mapę ponownie")} left={569.3} top={102}>
          <RefreshCw style={{ width: u(8), height: u(8) }} />
        </IconButton>
      )}
      <PageTitle
        title={t("Mapa empatii i ścieżka użytkownika")}
        subtitle={
          state?.persona
            ? `${state.persona.name}, ${state.persona.role} · ${state.persona.focus}`
            : t("Co persona mówi, myśli, robi i czuje — przed, w trakcie i po")
        }
      />

      <div className="absolute grid grid-cols-2" style={{ ...panel(41, 140, 236, 160), padding: u(8), gap: u(6) }}>
        {QUADRANTS.map((q) => (
          <div key={q.key} className="pf-scroll min-h-0 overflow-y-auto">
            <span className="tracking-[0.14em] text-haze" style={{ fontSize: "var(--text-small)" }}>
              {q.label}
            </span>
            <ul className="flex flex-col" style={{ gap: u(2.5), marginTop: u(3) }}>
              {(busy || !map) &&
                [0, 1].map((i) => (
                  <li key={i} className="animate-pulse rounded bg-[#f3ecfa]" style={{ height: u(10) }} />
                ))}
              {!busy && map?.[q.key].map((item, i) => <Item key={i} item={item} />)}
            </ul>
          </div>
        ))}
      </div>

      <div className="absolute flex flex-col" style={{ ...panel(285, 140, 313, 160), padding: u(8) }}>
        <span className="tracking-[0.14em] text-haze" style={{ fontSize: "var(--text-small)" }}>
          {t("ŚCIEŻKA UŻYTKOWNIKA")}
        </span>
        <div className="pf-scroll min-h-0 flex-1 overflow-auto" style={{ marginTop: u(3) }}>
          <div className="flex flex-col" style={{ minWidth: "100%", width: journey.length ? u(journey.length * 70) : "100%" }}>
            <div className="relative shrink-0" style={{ height: u(22) }}>
              <svg viewBox="0 0 100 40" preserveAspectRatio="none" className="absolute inset-0 h-full w-full">
                <line x1="0" y1="20" x2="100" y2="20" stroke="#efe6f6" strokeWidth="0.6" />
                {journey.length > 1 && (
                  <polyline
                    points={points}
                    fill="none"
                    stroke="var(--color-pink)"
                    strokeWidth="1.6"
                    vectorEffect="non-scaling-stroke"
                  />
                )}
              </svg>
              {journey.map((s, i) => (
                <span
                  key={i}
                  className="absolute rounded-full"
                  title={t("Emocja: {value}", { value: s.emotion })}
                  style={{
                    left: `calc(${((i + 0.5) / journey.length) * 100}% - ${u(2.5)})`,
                    top: `calc(${((20 - s.emotion * 8) / 40) * 100}% - ${u(2.5)})`,
                    width: u(5),
                    height: u(5),
                    background: s.emotion < 0 ? "var(--color-error)" : "var(--color-pink-button)",
                    border: `${u(0.8)} solid #ffffff`,
                  }}
                />
              ))}
            </div>
            <div className="flex" style={{ gap: u(5), marginTop: u(3) }}>
              {journey.map((s, i) => (
                <div key={i} className="flex min-w-0 flex-1 flex-col break-words" title={origin(s.from)} style={{ gap: u(2) }}>
                  <span className="text-haze" style={{ fontSize: "var(--text-small)" }}>
                    {PHASES[s.phase]}
                  </span>
                  <span className="font-semibold text-ink" style={{ fontSize: "var(--text-small)", lineHeight: 1.2 }}>
                    {s.name}
                  </span>
                  <span className="text-ink" style={{ fontSize: "var(--text-small)", lineHeight: 1.3 }}>
                    {s.action}
                  </span>
                  <span className="italic text-mauve" style={{ fontSize: "var(--text-small)", lineHeight: 1.3 }}>
                    „{s.thought}”
                  </span>
                  {s.pain && (
                    <span className="flex text-error" style={{ fontSize: "var(--text-small)", lineHeight: 1.3, gap: u(1.5) }}>
                      <Frown className="shrink-0" style={{ width: u(5), height: u(5), marginTop: u(0.5) }} />
                      {s.pain}
                    </span>
                  )}
                </div>
              ))}
              {(busy || !map) &&
                [0, 1, 2, 3, 4].map((i) => (
                  <div key={i} className="flex-1 animate-pulse rounded bg-[#f3ecfa]" style={{ height: u(60) }} />
                ))}
            </div>
          </div>
        </div>
      </div>

      <div className="absolute flex flex-col" style={{ ...panel(41, 307, 557, 64), padding: `${u(6)} ${u(8)}`, gap: u(4) }}>
        <span className="tracking-[0.14em] text-haze" style={{ fontSize: "var(--text-small)" }}>
          {t("JAK MOGLIBYŚMY…? · WYBIERZ PYTANIE, NA KTÓRE ODPOWIE DEVELOP")}
        </span>
        <div className="flex" style={{ gap: u(4) }}>
          {(map?.hmw ?? []).slice(0, 3).map((option) => (
            <button
              key={option}
              type="button"
              onClick={() => choose(option)}
              className="flex min-w-0 flex-1 items-center text-left text-ink"
              style={{
                gap: u(3),
                padding: `${u(2.5)} ${u(4)}`,
                borderRadius: u(6),
                fontSize: "var(--text-small)",
                lineHeight: 1.3,
                border: `${u(0.6)} solid ${question === option ? "var(--color-pink)" : "#efe6f6"}`,
                background: "#ffffff",
              }}
            >
              <Radio checked={question === option} size={7} />
              <span className="line-clamp-2">{option}</span>
            </button>
          ))}
        </div>
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onBlur={(e) => choose(e.target.value)}
          disabled={!map}
          placeholder={t("Albo napisz własne pytanie „Jak moglibyśmy…?”")}
          aria-label={t("Pytanie „Jak moglibyśmy…?”")}
          className="select-text rounded-md border border-[#eadff3] bg-white text-ink outline-none focus:border-pink"
          style={{ fontSize: "var(--text-small)", padding: `${u(2)} ${u(4)}` }}
        />
      </div>

      {busy ? (
        <BarProgress
          title={t("Buduję mapę empatii…")}
          text={t("Łączę notatki, wywiady i profil persony")}
          stage={stage ?? "thinking"}
        />
      ) : (
        <ChoiceBar
          label={t("PYTANIE DLA DEVELOP")}
          value={map?.hmw_chosen || null}
          placeholder={t("Wybierz pytanie „Jak moglibyśmy…?”")}
          action={t("Dalej: Develop")}
          disabled={!map?.hmw_chosen}
          onConfirm={onDone}
        />
      )}
      <FooterNote>
        {t("Elementy z ikoną cytatu pochodzą z notatek · kursywa to wnioski modelu do sprawdzenia w rozmowie")}
      </FooterNote>
    </>
  );
}
