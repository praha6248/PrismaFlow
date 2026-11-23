import { Sparkles, X } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "../api";
import type { QualityState } from "../types";
import { SHADOW, u } from "./ui";
import { locale, setLocale, t } from "../i18n";

export function QualityButton({ onShowSetup }: { onShowSetup: () => void }) {
  const [open, setOpen] = useState(false);
  const [state, setState] = useState<QualityState | null>(null);

  useEffect(() => {
    api
      .quality()
      .then(setState)
      .catch(() => setState(null));
  }, []);

  return (
    <>
      <div
        className="absolute z-20 flex items-center"
        style={{ right: u(16), top: u(18), gap: u(5) }}
      >
        <div
          className="flex rounded-full bg-[#f3ecfa]"
          style={{ padding: u(1.5), fontSize: u(5) }}
          role="group"
          aria-label={t("Język interfejsu")}
        >
          {(["pl", "en"] as const).map((code) => (
            <button
              key={code}
              type="button"
              onClick={() => code !== locale && setLocale(code)}
              aria-pressed={code === locale}
              className="rounded-full uppercase transition-colors"
              style={{
                padding: `${u(1.5)} ${u(4)}`,
                background: code === locale ? "#ffffff" : "transparent",
                color: code === locale ? "#573476" : "#9a87a8",
              }}
            >
              {code}
            </button>
          ))}
        </div>
        <button
          type="button"
          onClick={() => setOpen(true)}
          className="flex items-center rounded-full transition-colors"
          style={{
            gap: u(3),
            padding: `${u(3)} ${u(7)}`,
            fontSize: u(5.6),
            background: state?.enabled ? "#f783e9" : "#f3ecfa",
            color: state?.enabled ? "#ffffff" : "#674e78",
          }}
          title={t("Tryb jakości: Claude zamiast lokalnego modelu")}
        >
          <Sparkles style={{ width: u(6), height: u(6) }} />
          {state?.enabled ? t("Tryb jakości") : t("Model lokalny")}
        </button>
      </div>
      {open && (
        <QualityModal
          state={state}
          onChange={setState}
          onClose={() => setOpen(false)}
          onShowSetup={() => {
            setOpen(false);
            onShowSetup();
          }}
        />
      )}
    </>
  );
}

interface ModalProps {
  state: QualityState | null;
  onChange: (state: QualityState) => void;
  onClose: () => void;
  onShowSetup: () => void;
}

function QualityModal({ state, onChange, onClose, onShowSetup }: ModalProps) {
  const [key, setKey] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const save = async (enabled: boolean, newKey?: string) => {
    setBusy(true);
    setError(null);
    try {
      const next = await api.updateQuality({
        enabled,
        ...(newKey !== undefined ? { key: newKey } : {}),
      });
      onChange(next);
      setKey("");
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : t("Nie udało się zapisać"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div
      className="pf-fade absolute inset-0 z-50 flex items-center justify-center bg-[rgba(243,238,255,0.6)] backdrop-blur-[2px]"
      onClick={onClose}
    >
      <div
        className="pf-fade-up flex flex-col"
        onClick={(event) => event.stopPropagation()}
        style={{
          width: u(300),
          padding: u(14),
          borderRadius: u(12),
          background: "#fdfcfe",
          boxShadow: SHADOW,
          gap: u(8),
        }}
      >
        <div className="flex items-center">
          <span className="font-serif text-plum" style={{ fontSize: u(13) }}>
            {t("Tryb jakości")}
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
            "Problemy, persony, backlog i flow generuje {model} zamiast lokalnej Gemmy. Odpowiedzi nadal muszą cytować zebrane dowody. Gdy Claude jest niedostępny, aplikacja wraca do modelu lokalnego.",
            { model: state?.model ?? "Claude" },
          )}
        </p>
        <p
          className="rounded-md text-[#8a4a7e]"
          style={{
            fontSize: u(5.4),
            lineHeight: 1.5,
            padding: u(6),
            background: "#fdf0fa",
          }}
        >
          {t(
            "Prywatność: w tym trybie treść promptów, w tym zebrane dyskusje i opis niszy, trafia do API Anthropic. Używasz własnego klucza i płacisz według swojego planu. Klucz zapisuje się tylko lokalnie w ~/.config/PrismaFlow (chmod 600).",
          )}
        </p>

        <label
          className="flex flex-col text-haze"
          style={{ fontSize: u(5), gap: u(3) }}
        >
          {t("KLUCZ API ANTHROPIC")} {state?.has_key ? t("· zapisany") : ""}
          <input
            type="password"
            value={key}
            autoComplete="off"
            onChange={(event) => setKey(event.target.value)}
            placeholder={
              state?.has_key ? t("Wpisz nowy, aby zastąpić") : "sk-ant-…"
            }
            className="select-text rounded-md border border-[#eadff3] bg-white text-ink outline-none focus:border-[#f783e9]"
            style={{ fontSize: u(6.4), padding: `${u(5)} ${u(6)}` }}
          />
        </label>

        {error && (
          <span className="text-[#b3261e]" style={{ fontSize: u(5.4) }}>
            {error}
          </span>
        )}

        <div
          className="flex items-center"
          style={{ gap: u(6), marginTop: u(2) }}
        >
          <button
            type="button"
            onClick={onShowSetup}
            className="text-haze underline hover:text-plum"
            style={{ fontSize: u(5.6) }}
          >
            {t("Modele lokalne")}
          </button>
          {state?.has_key && (
            <button
              type="button"
              disabled={busy}
              onClick={() => save(false, "")}
              className="text-haze hover:text-plum"
              style={{ fontSize: u(5.6) }}
            >
              {t("Usuń klucz")}
            </button>
          )}
          <div className="ml-auto flex" style={{ gap: u(6) }}>
            {state?.enabled ? (
              <button
                type="button"
                disabled={busy}
                onClick={() => save(false)}
                className="rounded-md"
                style={{
                  fontSize: u(6.4),
                  padding: `${u(5)} ${u(12)}`,
                  background: "#f3ecfa",
                  color: "#573476",
                }}
              >
                {t("Wróć do modelu lokalnego")}
              </button>
            ) : (
              <button
                type="button"
                disabled={busy || (!key && !state?.has_key)}
                onClick={() => save(true, key || undefined)}
                className="rounded-md text-white disabled:opacity-40"
                style={{
                  fontSize: u(6.4),
                  padding: `${u(5)} ${u(12)}`,
                  background: "#f783e9",
                }}
              >
                {t("Włącz tryb jakości")}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
