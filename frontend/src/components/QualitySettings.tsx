import { Sparkles, X } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "../api";
import type { Provider, QualityState } from "../types";
import { SHADOW, u } from "./ui";
import { locale, setLocale, t } from "../i18n";

export function QualityButton({ open, setOpen, onShowSetup }: {
  open: boolean;
  setOpen: (open: boolean) => void;
  onShowSetup: () => void;
}) {
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
          style={{ padding: u(1.5), fontSize: "var(--text-small)" }}
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
            fontSize: "var(--text-small)",
            background: state?.enabled ? "var(--color-pink-button)" : "#f3ecfa",
            fontWeight: state?.enabled ? 600 : undefined,
            color: state?.enabled ? "var(--color-on-pink)" : "var(--color-mauve)",
          }}
          title={t("Wybierz model")}
        >
          <Sparkles style={{ width: u(6), height: u(6) }} />
          {state?.provider === "gemini" ? "Gemini" : state?.enabled ? "Claude" : t("Model lokalny")}
        </button>
      </div>
      {open && state && (
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
  state: QualityState;
  onChange: (state: QualityState) => void;
  onClose: () => void;
  onShowSetup: () => void;
}

function QualityModal({ state, onChange, onClose, onShowSetup }: ModalProps) {
  const [provider, setProvider] = useState<Provider>(state.provider === "local" ? "gemini" : state.provider);
  const gemini = provider === "gemini";
  const hasKey = gemini ? state.has_gemini_key : state.has_key;
  const [key, setKey] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const save = async (enabled: boolean, newKey?: string) => {
    setBusy(true);
    setError(null);
    try {
      const next = await api.updateQuality({
        provider, enabled,
        ...(newKey !== undefined ? { key: newKey } : {}),
      });
      onChange(next);
      if (newKey !== "") onClose();
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
          <span className="font-serif text-plum" style={{ fontSize: "var(--text-title)" }}>
            {t("Wybierz model")}
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
        <select aria-label={t("Wybierz model")} value={provider} disabled={busy}
          className="rounded-md border border-[#eadff3] bg-white p-2 text-ink"
          onChange={(event) => { setProvider(event.target.value as Provider); setKey(""); setError(null); }}>
          <option value="local">Ollama</option>
          <option value="gemini">Gemini</option>
          <option value="claude">Claude</option>
        </select>
        {provider !== "local" && <>
          <p className="text-mauve" style={{ fontSize: "var(--text-small)" }}>
            {t("Wybrane źródła i notatki z projektu trafią do {company}. Klucz jest zapisywany lokalnie.", { company: gemini ? "Google" : "Anthropic" })}
          </p>
          {gemini && <a href="https://aistudio.google.com/apikey" target="_blank" rel="noreferrer"
            className="text-pink-text underline">{t("Utwórz klucz w Google AI Studio")}</a>}
          <label className="flex flex-col text-mauve" style={{ gap: u(3) }}>
            {gemini ? "Gemini API key" : "Anthropic API key"} {hasKey && t("· zapisany")}
            <input type="password" value={key} autoComplete="off" disabled={busy}
              onChange={(event) => setKey(event.target.value)}
              placeholder={hasKey ? t("Wpisz nowy, aby zastąpić") : ""}
              className="select-text rounded-md border border-[#eadff3] bg-white p-2 text-ink" />
          </label>
        </>}
        {error && (
          <span className="text-error" style={{ fontSize: "var(--text-small)" }}>
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
            style={{ fontSize: "var(--text-small)" }}
          >
            {t("Modele lokalne")}
          </button>
          {provider !== "local" && hasKey && (
            <button type="button" disabled={busy} onClick={() => save(false, "")}
              className="text-haze hover:text-plum">{t("Usuń klucz")}</button>
          )}
          <button type="button" disabled={busy || (provider !== "local" && !key.trim() && !hasKey)}
            onClick={() => save(provider !== "local", key.trim() || undefined)}
            className="ml-auto rounded-md font-semibold text-on-pink disabled:opacity-40"
            style={{ background: "var(--color-pink-button)", padding: `${u(5)} ${u(12)}` }}>
            {busy ? t("Zapisuję…") : t("Zapisz")}
          </button>
        </div>
      </div>
    </div>
  );
}
