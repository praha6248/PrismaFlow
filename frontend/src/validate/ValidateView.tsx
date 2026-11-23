import { ArrowLeft, Check, Copy, MessageSquareQuote, RefreshCw, X } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { api, waitForJob } from "../api";
import { BarProgress, ChoiceBar, FooterNote, IconButton, PageTitle, SHADOW, u } from "../components/ui";
import type { Hypothesis, ValidateState } from "../types";

const KIND_LABELS: Record<Hypothesis["kind"], string> = {
  problem: "Problem istnieje",
  frequency: "Częstotliwość",
  workaround: "Obecne obejście",
  willingness: "Gotowość do zapłaty",
};

const STATUS: Record<Hypothesis["status"], { label: string; background: string; color: string }> = {
  open: { label: "do sprawdzenia", background: "#f3ecfa", color: "#674e78" },
  confirmed: { label: "potwierdzona", background: "#e3f4ea", color: "#2b6a45" },
  rejected: { label: "obalona", background: "#fbe4e4", color: "#9b2c2c" },
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

interface Props {
  projectId: number;
  onBack: () => void;
  onDone: () => void;
  notify: (message: string) => void;
}

export function ValidateView({ projectId, onBack, onDone, notify }: Props) {
  const [state, setState] = useState<ValidateState | null>(null);
  const [stage, setStage] = useState<string | null>(null);
  const [person, setPerson] = useState("");
  const [notes, setNotes] = useState("");
  const [analysing, setAnalysing] = useState(false);
  const [copied, setCopied] = useState(false);
  const [open, setOpen] = useState<number | null>(null);
  const started = useRef(false);

  const plan = useCallback(async () => {
    setStage("plan");
    try {
      const job = await api.planValidation(projectId);
      const finished = await waitForJob(job.id, (j) => setStage(j.stage));
      if (finished.status === "error" || !finished.result) {
        notify(`Nie udało się przygotować planu wywiadów: ${finished.error ?? "nieznany błąd"}`);
        return;
      }
      if (finished.warnings.some((w) => w.startsWith("validate:"))) notify("Plan się zmienił — wcześniejsze wywiady zostały wyczyszczone.");
      setState(finished.result as ValidateState);
    } catch (error) {
      notify((error as Error).message);
    } finally {
      setStage(null);
    }
  }, [projectId, notify]);

  useEffect(() => {
    api
      .getValidate(projectId)
      .then((data) => {
        setState(data);
        if (!data.hypotheses.length && !started.current) {
          started.current = true;
          plan();
        }
      })
      .catch((error: Error) => notify(`Nie udało się wczytać walidacji: ${error.message}`));
  }, [projectId, plan, notify]);

  const script = state
    ? [
        "Pytania przesiewowe:",
        ...state.screener.map((q, i) => `${i + 1}. ${q}`),
        "",
        "Wywiad (pytaj o przeszłość, nie o opinie i przyszłość; nie opowiadaj o pomyśle):",
        ...state.questions.map((q, i) => `${i + 1}. ${q}`),
      ].join("\n")
    : "";

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(script);
    } catch {
      const area = document.createElement("textarea");
      area.value = script;
      document.body.appendChild(area);
      area.select();
      document.execCommand("copy");
      area.remove();
    }
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1500);
  };

  const analyse = async () => {
    setAnalysing(true);
    try {
      setState(await api.addInterview(projectId, person.trim(), notes.trim()));
      setPerson("");
      setNotes("");
    } catch (error) {
      notify(`Nie udało się przeanalizować wywiadu: ${(error as Error).message}`);
    } finally {
      setAnalysing(false);
    }
  };

  const remove = async (id: string) => {
    try {
      setState(await api.removeInterview(projectId, id));
    } catch (error) {
      notify((error as Error).message);
    }
  };

  const busy = stage !== null;
  const progress = state?.progress;
  const summary = progress
    ? `${progress.interviews}/${state.target} wywiadów · ${progress.confirmed} potwierdzone · ${progress.rejected} obalone`
    : null;

  return (
    <>
      <IconButton onClick={onBack} title="Wróć do person" left={41} top={102}>
        <ArrowLeft style={{ width: u(9), height: u(9) }} />
      </IconButton>
      {!busy && state && state.hypotheses.length > 0 && (
        <IconButton onClick={plan} title="Przygotuj plan ponownie (czyści wywiady)" left={569.3} top={102}>
          <RefreshCw style={{ width: u(8), height: u(8) }} />
        </IconButton>
      )}
      <PageTitle
        title="Sprawdź problem w rozmowach"
        subtitle={state ? `${state.persona.name}, ${state.persona.role} · ${state.persona.focus}` : "Hipotezy, skrypt wywiadu i wnioski z prawdziwych rozmów"}
      />

      <div className="pf-scroll absolute flex flex-col overflow-y-auto" style={{ ...panel(41, 176, 270, 194), padding: u(10), gap: u(5) }}>
        <span className="tracking-[0.14em] text-haze" style={{ fontSize: u(5.2) }}>
          HIPOTEZY DO SPRAWDZENIA
        </span>
        {(busy || !state?.hypotheses.length) &&
          [0, 1, 2].map((i) => <div key={i} className="shrink-0 animate-pulse rounded-md bg-[#f3ecfa]" style={{ height: u(36) }} />)}
        {!busy &&
          state?.hypotheses.map((h, index) => {
            const status = STATUS[h.status];
            return (
              <button
                key={index}
                type="button"
                onClick={() => setOpen(open === index ? null : index)}
                className="shrink-0 text-left"
                style={{ padding: u(6), borderRadius: u(6), background: "#ffffff", border: `${u(0.5)} solid #efe6f6` }}
              >
                <div className="flex items-center" style={{ gap: u(4) }}>
                  <span className="text-haze" style={{ fontSize: u(4.6) }}>
                    {KIND_LABELS[h.kind]}
                  </span>
                  <span className="ml-auto rounded-full" style={{ fontSize: u(4.6), padding: `${u(1)} ${u(4)}`, background: status.background, color: status.color }}>
                    {status.label} · {h.supports}↑ {h.contradicts}↓
                  </span>
                </div>
                <div className="text-ink" style={{ fontSize: u(6.4), lineHeight: 1.35, marginTop: u(3) }}>
                  {h.text}
                </div>
                {open === index && (
                  <div className="text-mauve" style={{ fontSize: u(5.4), lineHeight: 1.4, marginTop: u(4) }}>
                    Potwierdza: {h.signal}
                    {h.quotes.map((q, i) => (
                      <div key={i} className="font-serif italic" style={{ marginTop: u(3), color: q.verdict === "supports" ? "#2b6a45" : "#9b2c2c" }}>
                        {q.person}: „{q.quote}”
                      </div>
                    ))}
                  </div>
                )}
              </button>
            );
          })}
      </div>

      <div className="absolute flex flex-col" style={{ ...panel(321, 176, 277, 194), padding: u(10), gap: u(5) }}>
        <div className="flex items-center">
          <span className="tracking-[0.14em] text-haze" style={{ fontSize: u(5.2) }}>
            SKRYPT WYWIADU · MOM TEST
          </span>
          <button type="button" disabled={!state?.questions.length} onClick={copy} className="ml-auto flex items-center text-plum hover:underline" style={{ fontSize: u(5.4), gap: u(2) }}>
            {copied ? <Check style={{ width: u(6), height: u(6) }} /> : <Copy style={{ width: u(6), height: u(6) }} />}
            {copied ? "Skopiowano" : "Kopiuj"}
          </button>
        </div>
        <ol className="pf-scroll min-h-0 list-decimal overflow-y-auto text-mauve" style={{ fontSize: u(5.6), lineHeight: 1.45, paddingLeft: u(10), maxHeight: u(48) }}>
          {state?.questions.map((q, i) => (
            <li key={i}>{q}</li>
          ))}
        </ol>
        <div style={{ height: u(0.5), background: "#efe8f5" }} />
        <span className="tracking-[0.14em] text-haze" style={{ fontSize: u(5.2) }}>
          DODAJ WYWIAD
        </span>
        <input
          value={person}
          onChange={(e) => setPerson(e.target.value)}
          placeholder="Kto (imię, rola)"
          className="select-text rounded-md border border-[#eadff3] bg-white text-ink outline-none focus:border-[#f783e9]"
          style={{ fontSize: u(6), padding: `${u(3)} ${u(5)}` }}
        />
        <textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder="Wklej notatki lub transkrypcję. Liczą się fakty z przeszłości rozmówcy, nie komplementy."
          className="pf-scroll min-h-0 flex-1 select-text resize-none rounded-md border border-[#eadff3] bg-white text-ink outline-none focus:border-[#f783e9]"
          style={{ fontSize: u(5.8), padding: u(5), lineHeight: 1.4 }}
        />
        <button
          type="button"
          disabled={analysing || !person.trim() || notes.trim().length < 20 || !state?.hypotheses.length}
          onClick={analyse}
          className="flex items-center justify-center rounded-md text-white disabled:opacity-40"
          style={{ fontSize: u(6.2), height: u(17), gap: u(3), background: "#f783e9" }}
        >
          <MessageSquareQuote style={{ width: u(6.5), height: u(6.5) }} />
          {analysing ? "Analizuję wywiad…" : "Oceń hipotezy na podstawie wywiadu"}
        </button>
        {state && state.interviews.length > 0 && (
          <div className="flex flex-wrap" style={{ gap: u(3) }}>
            {state.interviews.map((i) => (
              <span key={i.id} className="flex items-center rounded-full bg-[#f3ecfa] text-mauve" style={{ fontSize: u(4.8), padding: `${u(1.5)} ${u(4)}`, gap: u(2) }} title={i.summary}>
                {i.person}
                <button type="button" onClick={() => remove(i.id)} aria-label={`Usuń wywiad: ${i.person}`} className="text-haze hover:text-plum">
                  <X style={{ width: u(4.5), height: u(4.5) }} />
                </button>
              </span>
            ))}
          </div>
        )}
      </div>

      {busy ? (
        <BarProgress title="Przygotowuję plan wywiadów..." text="Formułuję hipotezy i pytania według Mom Test" stage={stage ?? "plan"} />
      ) : (
        <ChoiceBar
          label="POSTĘP WALIDACJI"
          value={summary}
          placeholder="Przeprowadź co najmniej 5 rozmów z osobami z grupy docelowej"
          action="Przejdź do Develop"
          disabled={!state}
          onConfirm={onDone}
        />
      )}
      <FooterNote>
        Werdykt liczy się tylko z dosłownym cytatem z notatek · hipoteza potwierdzona po 3 wywiadach bez przewagi zaprzeczeń
      </FooterNote>
    </>
  );
}
