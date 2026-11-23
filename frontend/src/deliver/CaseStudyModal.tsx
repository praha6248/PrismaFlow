import { Check, Copy, RotateCcw, X } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { api, waitForJob } from "../api";
import { u } from "../components/ui";
import type { CaseStudy } from "../types";
import { t } from "../i18n";

interface Props {
  projectId: number;
  onClose: () => void;
  notify: (message: string) => void;
}

const STAGES: Record<string, string> = {
  queued: "Przygotowuję…",
  context: "Zbieram dane z projektu…",
  thinking: "Lokalny model pisze opis…",
  writing: "Zapisuję Markdown, HTML i PDF…",
  done: "Gotowe",
};

export function CaseStudyModal({ projectId, onClose, notify }: Props) {
  const [study, setStudy] = useState<CaseStudy | null>(null);
  const [stage, setStage] = useState<string | null>("queued");
  const [progress, setProgress] = useState(0);
  const [copied, setCopied] = useState(false);
  const started = useRef(false);

  const generate = useCallback(async () => {
    setStudy(null);
    setStage("queued");
    setProgress(0);
    try {
      const job = await api.caseStudy(projectId);
      const finished = await waitForJob(job.id, (j) => {
        setStage(j.stage);
        setProgress(j.progress);
      });
      if (finished.status === "error" || !finished.result) {
        notify(
          `${t("Nie udało się napisać case study")}: ${finished.error ?? t("nieznany błąd")}`,
        );
        return;
      }
      if (finished.warnings.some((w) => w.startsWith("llm:"))) {
        notify(
          t("Lokalny model nie odpowiedział — case study zawiera tylko fakty z projektu."),
        );
      }
      setStudy(finished.result as CaseStudy);
    } catch (error) {
      notify((error as Error).message);
    } finally {
      setStage(null);
    }
  }, [projectId, notify]);

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    generate();
  }, [generate]);

  const copy = async () => {
    if (!study) return;
    try {
      await navigator.clipboard.writeText(study.markdown);
    } catch {
      const area = document.createElement("textarea");
      area.value = study.markdown;
      document.body.appendChild(area);
      area.select();
      document.execCommand("copy");
      area.remove();
    }
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1600);
  };

  const busy = stage !== null;

  return (
    <div
      className="pf-fade absolute inset-0 z-40 flex items-center justify-center bg-[rgba(243,238,255,0.6)] backdrop-blur-[2px]"
      onClick={onClose}
    >
      <div
        className="pf-fade-up flex flex-col"
        onClick={(e) => e.stopPropagation()}
        style={{
          width: u(470),
          height: u(330),
          borderRadius: u(12),
          background: "#fdfcfe",
          boxShadow: `0 ${u(6)} ${u(30)} rgba(170, 120, 210, 0.3)`,
          padding: u(14),
        }}
      >
        <div className="flex items-center">
          <span className="font-serif text-plum" style={{ fontSize: "var(--text-title)" }}>
            {t("Case study")}
          </span>
          {study && (
            <span
              className="text-haze"
              style={{ fontSize: "var(--text-small)", marginLeft: u(8) }}
            >
              {t("Miejsca do uzupełnienia: {count}", { count: study.gaps })}
              {study.removed.length > 0 &&
                ` · ${t("usunięte zdania z liczbami spoza danych: {count}", { count: study.removed.length })}`}
            </span>
          )}
          <button
            type="button"
            onClick={onClose}
            className="ml-auto text-haze hover:text-plum"
            aria-label={t("Zamknij")}
          >
            <X style={{ width: u(9), height: u(9) }} />
          </button>
        </div>
        {busy ? (
          <div
            className="flex min-h-0 flex-1 flex-col items-center justify-center text-mauve"
            style={{ gap: u(6), fontSize: "var(--text-body)" }}
          >
            <span>{t(STAGES[stage] ?? STAGES.queued)}</span>
            <div
              className="overflow-hidden rounded-full bg-[#f3ecfa]"
              style={{ width: u(160), height: u(3) }}
            >
              <div
                className="h-full rounded-full transition-[width]"
                style={{
                  width: `${Math.round(progress * 100)}%`,
                  background: "var(--color-pink-button)",
                }}
              />
            </div>
            <span className="text-haze" style={{ fontSize: "var(--text-small)" }}>
              {t("Tylko fakty z projektu; braki zostaną oznaczone „do uzupełnienia”.")}
            </span>
          </div>
        ) : (
          <pre
            className="pf-scroll min-h-0 flex-1 overflow-auto whitespace-pre-wrap text-mauve"
            style={{
              marginTop: u(10),
              padding: u(10),
              borderRadius: u(7),
              background: "#f7f3fb",
              fontSize: "var(--text-small)",
              lineHeight: 1.55,
              fontFamily: "Montserrat, sans-serif",
            }}
          >
            {study?.markdown ?? t("Nie udało się napisać case study")}
          </pre>
        )}
        <div className="flex items-center" style={{ marginTop: u(9), gap: u(8) }}>
          <span
            className="min-w-0 flex-1 truncate text-haze"
            style={{ fontSize: "var(--text-small)" }}
            title={study ? `${study.directory} · ${study.files.join(", ")}` : undefined}
          >
            {study &&
              `${t("Zapisano w {dir}:", { dir: study.directory })} ${study.files.join(", ")}`}
            {study &&
              !study.files.includes("case-study.pdf") &&
              ` · ${t("PDF: otwórz case-study.html i wydrukuj do PDF")}`}
          </span>
          <button
            type="button"
            onClick={generate}
            disabled={busy}
            className="flex items-center transition-colors hover:bg-[#e9dcf8] disabled:opacity-60"
            style={{
              fontSize: "var(--text-body)",
              padding: `${u(5)} ${u(12)}`,
              borderRadius: u(6),
              gap: u(3),
              background: "#f3ecfa",
              color: "var(--color-ink)",
            }}
          >
            <RotateCcw style={{ width: u(7), height: u(7) }} />
            {t("Napisz ponownie")}
          </button>
          <button
            type="button"
            onClick={copy}
            disabled={!study}
            className="flex items-center font-semibold text-on-pink disabled:opacity-60"
            style={{
              fontSize: "var(--text-body)",
              padding: `${u(5)} ${u(12)}`,
              borderRadius: u(6),
              gap: u(3),
              background: "var(--color-pink-button)",
            }}
          >
            {copied ? (
              <Check style={{ width: u(7), height: u(7) }} />
            ) : (
              <Copy style={{ width: u(7), height: u(7) }} />
            )}
            {copied ? t("Skopiowano") : t("Kopiuj")}
          </button>
        </div>
      </div>
    </div>
  );
}
