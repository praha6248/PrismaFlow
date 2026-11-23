import { ArrowLeft, Plus, Sparkles, Trash2, X } from "lucide-react";
import { useCallback, useEffect, useState, type DragEvent } from "react";
import { api, waitForJob } from "../api";
import {
  BarProgress,
  ChoiceBar,
  FooterNote,
  IconButton,
  PageTitle,
  SHADOW,
  u,
} from "../components/ui";
import { plural, t } from "../i18n";
import type { BoardNote, BoardState, NoteSource, Theme } from "../types";

export const SOURCE_STYLE: Record<NoteSource, { background: string; color: string }> = {
  evidence: { background: "#efe9f7", color: "var(--color-mauve)" },
  note: { background: "#fde7f8", color: "var(--color-pink-text)" },
  interview: { background: "#fde7f8", color: "var(--color-pink-text)" },
  test: { background: "#e3f4ea", color: "var(--color-success)" },
};

export function sourceLabel(source: NoteSource, label: string): string {
  if (source === "interview") return label ? t("Wywiad · {who}", { who: label }) : t("Wywiad");
  if (source === "note") return label ? t("Notatka · {who}", { who: label }) : t("Notatka");
  if (source === "test") return t("Test z użytkownikiem");
  return label || t("Dowód z sieci");
}

interface Props {
  projectId: number;
  onBack: () => void;
  onDone: () => void;
  notify: (message: string) => void;
}

function NoteCard({
  note,
  themes,
  onMove,
  onRemove,
}: {
  note: BoardNote;
  themes: Theme[];
  onMove: (theme: string | null) => void;
  onRemove: () => void;
}) {
  const style = SOURCE_STYLE[note.source];
  return (
    <div
      draggable
      onDragStart={(event) => event.dataTransfer.setData("text/plain", note.id)}
      className="group shrink-0 cursor-grab bg-white active:cursor-grabbing"
      style={{
        padding: u(5),
        borderRadius: u(5),
        border: `${u(0.5)} solid #efe6f6`,
        boxShadow: `0 ${u(0.5)} ${u(2)} rgba(196, 160, 232, 0.18)`,
      }}
    >
      <div className="flex items-center" style={{ gap: u(2) }}>
        <span
          className="truncate rounded-full"
          style={{
            fontSize: "var(--text-small)",
            padding: `0 ${u(3)}`,
            background: style.background,
            color: style.color,
          }}
        >
          {sourceLabel(note.source, note.label)}
        </span>
        <select
          value={note.theme ?? ""}
          onChange={(e) => onMove(e.target.value || null)}
          aria-label={t("Przenieś do tematu")}
          title={t("Przenieś do tematu")}
          className="ml-auto min-w-0 cursor-pointer rounded bg-transparent text-haze outline-none hover:text-ink focus:text-ink"
          style={{ fontSize: "var(--text-small)", maxWidth: u(34) }}
        >
          <option value="">{t("Bez tematu")}</option>
          {themes.map((theme) => (
            <option key={theme.id} value={theme.id}>
              {theme.name}
            </option>
          ))}
        </select>
        <button
          type="button"
          onClick={onRemove}
          aria-label={t("Usuń notatkę")}
          className="text-haze opacity-0 transition-opacity hover:text-ink focus:opacity-100 group-hover:opacity-100"
        >
          <X style={{ width: u(5), height: u(5) }} />
        </button>
      </div>
      <p
        className="line-clamp-5 text-ink"
        title={note.text}
        style={{ fontSize: "var(--text-small)", lineHeight: 1.35, marginTop: u(2.5) }}
      >
        {note.text}
      </p>
    </div>
  );
}

export function BoardView({ projectId, onBack, onDone, notify }: Props) {
  const [state, setState] = useState<BoardState | null>(null);
  const [stage, setStage] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [who, setWho] = useState("");
  const [over, setOver] = useState<string | null>(null);

  useEffect(() => {
    api
      .board(projectId)
      .then(setState)
      .catch((error: Error) => notify(error.message));
  }, [projectId, notify]);

  const run = useCallback(
    async (call: () => Promise<BoardState>) => {
      try {
        setState(await call());
      } catch (error) {
        notify((error as Error).message);
      }
    },
    [notify],
  );

  const cluster = async () => {
    setStage("grouping");
    try {
      const job = await api.clusterBoard(projectId);
      const finished = await waitForJob(job.id, (j) => setStage(j.stage));
      if (finished.status === "error" || !finished.result) {
        notify(
          t("Nie udało się pogrupować notatek: {error}", {
            error: finished.error ?? t("nieznany błąd"),
          }),
        );
        return;
      }
      setState(finished.result as BoardState);
    } catch (error) {
      notify((error as Error).message);
    } finally {
      setStage(null);
    }
  };

  const add = async () => {
    if (!draft.trim()) return;
    await run(() => api.addNotes(projectId, draft, who.trim() ? "interview" : "note", who));
    setDraft("");
  };

  const drop = (theme: string | null) => (event: DragEvent) => {
    event.preventDefault();
    setOver(null);
    const id = event.dataTransfer.getData("text/plain");
    if (id) run(() => api.moveNote(projectId, id, theme));
  };

  const dragOver = (key: string) => (event: DragEvent) => {
    event.preventDefault();
    setOver(key);
  };

  const notes = state?.notes ?? [];
  const themes = state?.themes ?? [];
  const loose = notes.filter((n) => !n.theme);
  const real = notes.filter((n) => n.source !== "evidence").length;
  const busy = stage !== null;

  const column = (key: string) => ({
    width: u(132),
    padding: u(6),
    gap: u(4),
    borderRadius: u(9),
    background: over === key ? "#fbeefa" : "rgba(253, 252, 254, 0.9)",
    boxShadow: SHADOW,
    outline: over === key ? `${u(0.8)} dashed var(--color-pink)` : "none",
  });

  return (
    <>
      <IconButton onClick={onBack} title={t("Wróć do mapy")} left={41} top={102}>
        <ArrowLeft style={{ width: u(9), height: u(9) }} />
      </IconButton>
      <IconButton
        onClick={() => run(() => api.addTheme(projectId, t("Nowy temat")))}
        title={t("Dodaj pusty temat")}
        left={535}
        top={102}
      >
        <Plus style={{ width: u(9), height: u(9) }} />
      </IconButton>
      <IconButton
        onClick={cluster}
        title={t("Pogrupuj notatki z pomocą modelu")}
        left={569.3}
        top={102}
      >
        <Sparkles style={{ width: u(8), height: u(8) }} />
      </IconButton>
      <PageTitle
        title={t("Pogrupuj notatki w tematy")}
        subtitle={t("Fragmenty z forów, wywiadów i Twoje notatki · przeciągnij notatkę do tematu")}
      />

      <div
        className="pf-scroll absolute flex items-stretch overflow-x-auto"
        style={{ left: u(41), top: u(140), width: u(557), height: u(232), gap: u(7), paddingBottom: u(4) }}
      >
        <div
          className="flex shrink-0 flex-col"
          style={column("loose")}
          onDragOver={dragOver("loose")}
          onDragLeave={() => setOver(null)}
          onDrop={drop(null)}
        >
          <span className="tracking-[0.14em] text-haze" style={{ fontSize: "var(--text-small)" }}>
            {t("BEZ TEMATU")} · {loose.length}
          </span>
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder={t("Wklej notatki z rozmowy lub obserwacji. Pusta linia oddziela notatki.")}
            className="pf-scroll shrink-0 select-text resize-none rounded-md border border-[#eadff3] bg-white text-ink outline-none focus:border-pink"
            style={{ fontSize: "var(--text-small)", padding: u(4), height: u(34), lineHeight: 1.35 }}
          />
          <div className="flex shrink-0" style={{ gap: u(3) }}>
            <input
              value={who}
              onChange={(e) => setWho(e.target.value)}
              placeholder={t("Od kogo (opcjonalnie)")}
              className="min-w-0 flex-1 select-text rounded-md border border-[#eadff3] bg-white text-ink outline-none focus:border-pink"
              style={{ fontSize: "var(--text-small)", padding: `${u(2)} ${u(4)}` }}
            />
            <button
              type="button"
              onClick={add}
              disabled={!draft.trim()}
              className="rounded-md font-semibold text-on-pink disabled:opacity-40"
              style={{ fontSize: "var(--text-small)", padding: `0 ${u(5)}`, background: "var(--color-pink-button)" }}
            >
              {t("Dodaj")}
            </button>
          </div>
          <div className="pf-scroll flex min-h-0 flex-1 flex-col overflow-y-auto" style={{ gap: u(4) }}>
            {!state &&
              [0, 1, 2].map((i) => (
                <div key={i} className="shrink-0 animate-pulse rounded-md bg-[#f3ecfa]" style={{ height: u(28) }} />
              ))}
            {loose.map((note) => (
              <NoteCard
                key={note.id}
                note={note}
                themes={themes}
                onMove={(theme) => run(() => api.moveNote(projectId, note.id, theme))}
                onRemove={() => run(() => api.removeNote(projectId, note.id))}
              />
            ))}
          </div>
        </div>

        {themes.map((theme) => {
          const members = notes.filter((n) => n.theme === theme.id);
          return (
            <div
              key={theme.id}
              className="pf-fade flex shrink-0 flex-col"
              style={column(theme.id)}
              onDragOver={dragOver(theme.id)}
              onDragLeave={() => setOver(null)}
              onDrop={drop(theme.id)}
            >
              <div className="flex items-start" style={{ gap: u(2) }}>
                <textarea
                  rows={2}
                  defaultValue={theme.name}
                  onBlur={(e) =>
                    e.target.value.trim() &&
                    e.target.value !== theme.name &&
                    run(() => api.updateTheme(projectId, theme.id, { name: e.target.value }))
                  }
                  aria-label={t("Nazwa tematu")}
                  className="min-w-0 flex-1 select-text resize-none bg-transparent font-semibold text-ink outline-none focus:underline"
                  style={{ fontSize: "var(--text-body)", lineHeight: 1.2 }}
                />
                <span className="text-haze" style={{ fontSize: "var(--text-small)" }}>
                  {members.length}
                </span>
                <button
                  type="button"
                  onClick={() => run(() => api.removeTheme(projectId, theme.id))}
                  aria-label={t("Usuń temat")}
                  className="text-haze hover:text-ink"
                >
                  <Trash2 style={{ width: u(5.5), height: u(5.5) }} />
                </button>
              </div>
              <textarea
                defaultValue={theme.insight}
                onBlur={(e) =>
                  e.target.value !== theme.insight &&
                  run(() => api.updateTheme(projectId, theme.id, { insight: e.target.value }))
                }
                placeholder={t("Czego uczą nas te notatki?")}
                rows={2}
                className="shrink-0 select-text resize-none bg-transparent italic text-mauve outline-none"
                style={{ fontSize: "var(--text-small)", lineHeight: 1.35 }}
              />
              <div className="pf-scroll flex min-h-0 flex-1 flex-col overflow-y-auto" style={{ gap: u(4) }}>
                {members.map((note) => (
                  <NoteCard
                key={note.id}
                note={note}
                themes={themes}
                onMove={(theme) => run(() => api.moveNote(projectId, note.id, theme))}
                onRemove={() => run(() => api.removeNote(projectId, note.id))}
              />
                ))}
                {!members.length && (
                  <p className="text-center text-haze" style={{ fontSize: "var(--text-small)", marginTop: u(10) }}>
                    {t("Przeciągnij tu notatki")}
                  </p>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {busy ? (
        <BarProgress
          title={t("Grupuję notatki…")}
          text={t("Szukam wspólnych potrzeb i frustracji")}
          stage={stage ?? "grouping"}
        />
      ) : (
        <ChoiceBar
          label={t("TABLICA")}
          value={
            themes.length
              ? `${plural(themes.length, "{n} temat", "{n} tematy", "{n} tematów").replace("{n}", String(themes.length))} · ${t("{real} z {all} notatek od ludzi", { real, all: notes.length })}${state?.dropped ? ` · ${t("usunięte nie na temat: {n}", { n: state.dropped })}` : ""}`
              : null
          }
          placeholder={t("Pogrupuj notatki w tematy, zanim nazwiesz problem")}
          action={t("Dalej: problemy")}
          disabled={!state}
          onConfirm={onDone}
        />
      )}
      <FooterNote>
        {t("Problemy w kolejnym kroku powstają z tych tematów · notatki od ludzi ważą więcej niż wątki z forów")}
      </FooterNote>
    </>
  );
}
