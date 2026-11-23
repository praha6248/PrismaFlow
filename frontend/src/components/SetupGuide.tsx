import {
  Check,
  CircleDashed,
  Copy,
  ExternalLink,
  RefreshCw,
  X,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import type { SetupModel, SetupState } from "../types";
import { SHADOW, u } from "./ui";
import { number, t } from "../i18n";

const PURPOSE: Record<SetupModel["id"], string> = {
  chat: "Główny model: mapa tematów, problemy, persony, backlog i flow.",
  embed:
    "Wyszukiwanie dowodów po znaczeniu. Bez niego działa wyszukiwanie pełnotekstowe.",
  ux: "Model dostrojony do UX. Lepsze flow i sugestie w Deliver.",
};

function CopyCommand({ command }: { command: string }) {
  const [copied, setCopied] = useState(false);
  const copy = () => {
    navigator.clipboard
      ?.writeText(command)
      .then(() => {
        setCopied(true);
        window.setTimeout(() => setCopied(false), 1500);
      })
      .catch(() => undefined);
  };
  return (
    <div
      className="flex items-center rounded-md bg-[#2b1f36] text-[#f7eefc]"
      style={{ marginTop: u(3), padding: `${u(3)} ${u(5)}`, gap: u(4) }}
    >
      <code
        className="min-w-0 flex-1 select-text break-all"
        style={{ fontSize: u(5.2) }}
      >
        {command}
      </code>
      <button
        type="button"
        onClick={copy}
        className="shrink-0 opacity-80 hover:opacity-100"
        aria-label={t("Kopiuj polecenie")}
      >
        {copied ? (
          <Check style={{ width: u(6), height: u(6) }} />
        ) : (
          <Copy style={{ width: u(6), height: u(6) }} />
        )}
      </button>
    </div>
  );
}

function Step({
  done,
  title,
  children,
}: {
  done: boolean;
  title: string;
  children?: React.ReactNode;
}) {
  return (
    <div className="flex" style={{ gap: u(5) }}>
      {done ? (
        <Check
          className="shrink-0 text-[#3d9a5b]"
          style={{ width: u(8), height: u(8) }}
        />
      ) : (
        <CircleDashed
          className="shrink-0 text-[#d65bc4]"
          style={{ width: u(8), height: u(8) }}
        />
      )}
      <div className="min-w-0 flex-1">
        <div className="text-ink" style={{ fontSize: u(6.4), lineHeight: 1.3 }}>
          {title}
        </div>
        {children && (
          <div
            className="text-mauve"
            style={{ fontSize: u(5.4), lineHeight: 1.45, marginTop: u(1.5) }}
          >
            {children}
          </div>
        )}
      </div>
    </div>
  );
}

export function useSetup() {
  const [state, setState] = useState<SetupState | null>(null);
  const [open, setOpen] = useState(false);
  const refresh = useCallback(async () => {
    try {
      const next = await api.setup();
      setState(next);
      return next;
    } catch {
      return null;
    }
  }, []);
  useEffect(() => {
    refresh().then((next) => {
      if (next && !next.ready) setOpen(true);
    });
  }, [refresh]);
  return { state, open, setOpen, refresh };
}

interface Props {
  state: SetupState | null;
  onRefresh: () => Promise<unknown>;
  onClose: () => void;
}

export function SetupGuide({ state, onRefresh, onClose }: Props) {
  const [checking, setChecking] = useState(false);
  const check = async () => {
    setChecking(true);
    await onRefresh();
    setChecking(false);
  };

  return (
    <div
      className="pf-fade absolute inset-0 z-50 flex items-center justify-center bg-[rgba(243,238,255,0.6)] backdrop-blur-[2px]"
      onClick={onClose}
    >
      <div
        className="pf-fade-up pf-scroll flex flex-col overflow-y-auto"
        onClick={(event) => event.stopPropagation()}
        style={{
          width: u(330),
          maxHeight: "92%",
          padding: u(14),
          borderRadius: u(12),
          background: "#fdfcfe",
          boxShadow: SHADOW,
          gap: u(8),
        }}
      >
        <div className="flex items-center">
          <span className="font-serif text-plum" style={{ fontSize: u(13) }}>
            {state?.ready ? t("Modele lokalne") : t("Zanim zaczniesz")}
          </span>
          <button
            type="button"
            onClick={onClose}
            className="ml-auto text-haze hover:text-plum"
            aria-label={t("Zamknij")}
          >
            <X style={{ width: u(9), height: u(9) }} />
          </button>
        </div>
        <p className="text-mauve" style={{ fontSize: u(6), lineHeight: 1.5 }}>
          {t(
            "PrismaFlow działa na Twoim komputerze. Tekst generuje lokalny model w Ollamie, więc dane nie opuszczają dysku.",
          )}
          {state?.memory_gb
            ? ` ${t("Masz {ram} GB RAM, dlatego polecamy model poniżej.", { ram: number(state.memory_gb, 1) })}`
            : ""}
        </p>

        <Step
          done={!!state?.ollama.ok}
          title={`1. ${t("Zainstaluj i uruchom Ollamę")}`}
        >
          {state?.ollama.ok ? (
            t("Działa pod {url}.", { url: state.ollama.url })
          ) : (
            <>
              {t("Nie widzę Ollamy pod {url}. Pobierz ją ze strony", {
                url: state?.ollama.url ?? "127.0.0.1:11434",
              })}{" "}
              <a
                href={state?.ollama.download ?? "https://ollama.com/download"}
                target="_blank"
                rel="noreferrer"
                className="text-[#c03fae] underline"
              >
                ollama.com/download
              </a>
              . {t("Na Linuksie:")}
              <CopyCommand command="curl -fsSL https://ollama.com/install.sh | sh" />
            </>
          )}
        </Step>

        {(state?.models ?? []).map((model, index) => (
          <Step
            key={model.id}
            done={model.installed}
            title={`${index + 2}. ${model.name} · ${model.size}${model.required ? "" : ` · ${t("opcjonalnie")}`}`}
          >
            {t(PURPOSE[model.id])}{" "}
            <a
              href={model.source}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center text-[#c03fae] underline"
              style={{ gap: u(1) }}
            >
              {t("Źródło")}
              <ExternalLink style={{ width: u(4.5), height: u(4.5) }} />
            </a>
            {!model.installed && <CopyCommand command={model.command} />}
          </Step>
        ))}

        <div
          className="flex items-center"
          style={{ gap: u(6), marginTop: u(2) }}
        >
          <span className="text-haze" style={{ fontSize: u(5) }}>
            {t(
              "Nie chcesz pobierać modeli? Włącz tryb jakości z własnym kluczem Claude.",
            )}
          </span>
          <button
            type="button"
            onClick={check}
            disabled={checking}
            className="ml-auto flex shrink-0 items-center rounded-md text-white disabled:opacity-60"
            style={{
              fontSize: u(6.4),
              padding: `${u(5)} ${u(10)}`,
              gap: u(3),
              background: "var(--color-pink)",
            }}
          >
            <RefreshCw
              className={checking ? "animate-spin" : undefined}
              style={{ width: u(6), height: u(6) }}
            />
            {t("Sprawdź ponownie")}
          </button>
        </div>
      </div>
    </div>
  );
}
