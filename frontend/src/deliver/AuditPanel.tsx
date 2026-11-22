import { Check, Sparkles, X } from "lucide-react";
import type { ReactNode } from "react";
import { u } from "../components/ui";
import type { FlowAudit, Suggestion } from "../types";
import { ZONE_LABELS } from "./ScreenNode";

export const pl = (value: number, digits = 2) => value.toFixed(digits).replace(".", ",");

function plural(count: number, one: string, few: string, many: string): string {
  if (count === 1) return one;
  const last = count % 10;
  const lastTwo = count % 100;
  return last >= 2 && last <= 4 && (lastTwo < 12 || lastTwo > 14) ? few : many;
}

type Tone = "good" | "warn" | "neutral";

const TONES: Record<Tone, { background: string; border: string }> = {
  good: { background: "#e6f5ea", border: "#cdebd6" },
  warn: { background: "#fdebf7", border: "#f9d0ef" },
  neutral: { background: "#f7f3fb", border: "#eee6f5" },
};

function Metric({ tone, title, value, children }: { tone: Tone; title: string; value?: ReactNode; children?: ReactNode }) {
  const colors = TONES[tone];
  return (
    <div
      className="pf-fade relative shrink-0"
      style={{
        borderRadius: u(5),
        background: colors.background,
        border: `${u(0.5)} solid ${colors.border}`,
        padding: `${u(4.5)} ${u(6)}`,
      }}
    >
      <div className="flex items-start justify-between" style={{ gap: u(4) }}>
        <span className="text-ink" style={{ fontSize: u(5.8), lineHeight: 1.25 }}>
          {title}
        </span>
        {value !== undefined && (
          <span className="font-serif text-ink" style={{ fontSize: u(12), lineHeight: 0.9 }}>
            {value}
          </span>
        )}
      </div>
      {children && (
        <div style={{ fontSize: u(4.6), lineHeight: 1.45, color: "#7c6d88", marginTop: u(1.5) }}>{children}</div>
      )}
    </div>
  );
}

interface Props {
  audit: FlowAudit;
  suggestions: Suggestion[];
  optimizing: boolean;
  handoffBusy: boolean;
  onOptimize: () => void;
  onAccept: (s: Suggestion) => void;
  onDismiss: (s: Suggestion) => void;
  onHandoff: () => void;
  onFocusScreen: (screenId: string) => void;
}

export function AuditPanel({ audit, suggestions, optimizing, handoffBusy, onOptimize, onAccept, onDismiss, onHandoff, onFocusScreen }: Props) {
  const c = audit.constants;
  const hick = audit.hick[0];
  const fitts = audit.fitts[0];
  const dead = audit.dead_ends;
  const primarySmall = audit.targets.below_aaa.filter((t) => t.primary);
  const steps = audit.steps;

  return (
    <div className="flex h-full flex-col" style={{ padding: `${u(9)} ${u(8)} ${u(8)}` }}>
      <div className="flex items-center justify-between">
        <span className="font-serif text-ink" style={{ fontSize: u(10), lineHeight: 1 }}>
          Audyt UX
        </span>
        <span className="flex items-center rounded-full bg-[#f3ecfa] text-mauve" style={{ fontSize: u(4.8), padding: `${u(2)} ${u(5)}`, gap: u(2.5) }}>
          <span className="rounded-full bg-[#f783e9]" style={{ width: u(3), height: u(3), animation: "pf-pulse 1.8s ease-in-out infinite" }} />
          Na żywo
        </span>
      </div>
      <span className="text-haze" style={{ fontSize: u(4.8), marginTop: u(3) }}>
        {audit.screens} {plural(audit.screens, "ekran", "ekrany", "ekranów")} · analiza całego flow
      </span>

      <div className="pf-scroll flex min-h-0 flex-1 flex-col overflow-y-auto" style={{ gap: u(4), marginTop: u(6) }}>
        <Metric
          tone={steps.value !== null ? (steps.value <= 3 ? "good" : "warn") : "warn"}
          title="Kroki do celu"
          value={steps.value ?? "—"}
        >
          {steps.status === "ok"
            ? `Time-to-Value · ${steps.path.join(" → ")}`
            : steps.status === "missing"
              ? "Oznacz ekran startowy i ekran celu (CEL)."
              : "Cel jest nieosiągalny ze startu — połącz ekrany."}
        </Metric>

        {audit.klm && (
          <Metric tone={audit.klm.seconds <= 10 ? "good" : "warn"} title="Szacowany czas do celu" value={`${pl(audit.klm.seconds, 1)} s`}>
            Model KLM: przygotowanie {pl(c.klm_mental)} s + Hick + Fitts na każdym kroku ścieżki krytycznej.
          </Metric>
        )}

        {hick && (
          <Metric tone={hick.warning ? "warn" : "neutral"} title="Hick · złożoność decyzji">
            <button type="button" className="text-left hover:underline" onClick={() => onFocusScreen(hick.screen_id)}>
              {hick.screen}: {hick.options} {plural(hick.options, "opcja", "opcje", "opcji")} = {pl(hick.seconds)} s.
            </button>
            {hick.warning && (
              <>
                <br />
                Ukryj {hick.hide} {plural(hick.hide, "opcję", "opcje", "opcji")} w sekcji „Więcej”.
              </>
            )}
            <br />
            <span className="text-haze">
              a = {pl(c.hick_a)} s · b = {pl(c.hick_b)} s
            </span>
          </Metric>
        )}

        <Metric tone={fitts ? "warn" : "good"} title="Fitts · ergonomia kliknięć">
          {fitts ? (
            <button type="button" className="text-left hover:underline" onClick={() => onFocusScreen(fitts.screen_id)}>
              „{fitts.element}”: {fitts.size} = {ZONE_LABELS[fitts.zone]} (ID {pl(fitts.index, 1)}).
              <br />
              Zwiększ cel i przenieś go na dół.
              {audit.fitts.length > 1 && ` (+${audit.fitts.length - 1} kolejnych)`}
            </button>
          ) : (
            `Wszystkie cele mają ID ≤ ${pl(c.fitts_limit, 1)} bita.`
          )}
        </Metric>

        <Metric
          tone={primarySmall.length ? "warn" : "good"}
          title="Cele dotykowe · WCAG 2.2"
          value={`${audit.targets.aaa}/${audit.targets.total}`}
        >
          {primarySmall.length ? (
            <button type="button" className="text-left hover:underline" onClick={() => onFocusScreen(primarySmall[0].screen_id)}>
              „{primarySmall[0].element}” ma {primarySmall[0].pixels} px — przejście powinno mieć ≥ {c.wcag_aaa} px.
            </button>
          ) : (
            `Przejścia mają ≥ ${c.wcag_aaa} px (2.5.5 AAA); minimum AA to ${c.wcag_aa} px.`
          )}
        </Metric>

        <Metric
          tone={dead.length || audit.unreachable.length ? "warn" : "good"}
          title={dead.length ? `${dead.length} ${plural(dead.length, "ślepa uliczka", "ślepe uliczki", "ślepych uliczek")}` : "Brak ślepych uliczek"}
        >
          {dead.length > 0 && (
            <button type="button" className="text-left hover:underline" onClick={() => onFocusScreen(dead[0].screen_id)}>
              {dead.map((d) => d.screen).join(", ")} — brak przejścia dalej.
            </button>
          )}
          {audit.unreachable.length > 0 && (
            <>
              {dead.length > 0 && <br />}
              Nieosiągalne: {audit.unreachable.map((d) => d.screen).join(", ")}.
            </>
          )}
          {!dead.length && !audit.unreachable.length && "Z każdego ekranu da się przejść dalej."}
        </Metric>

        <span className="font-serif text-ink" style={{ fontSize: u(7.5), marginTop: u(3) }}>
          Asystent AI · Ollama
        </span>
        <button
          type="button"
          onClick={onOptimize}
          disabled={optimizing || audit.screens === 0}
          className="flex shrink-0 items-center justify-center transition-transform enabled:hover:scale-[1.01] enabled:active:scale-[0.98] disabled:opacity-60"
          style={{ height: u(17), gap: u(3), borderRadius: u(5), fontSize: u(6.2), background: "#e9dcf8", color: "#573476" }}
        >
          <Sparkles style={{ width: u(6.5), height: u(6.5) }} />
          {optimizing ? "Analizuję flow..." : "Optymalizuj flow przez AI"}
        </button>
        {suggestions.map((s) => (
          <div
            key={s.id}
            className="pf-fade-up flex shrink-0 items-center"
            style={{ gap: u(4), padding: `${u(4)} ${u(5)}`, borderRadius: u(5), background: "#ffffff", border: `${u(0.5)} solid #eee6f5` }}
          >
            <div className="min-w-0 flex-1">
              <div className="text-ink" style={{ fontSize: u(5.4), lineHeight: 1.3 }}>
                {s.title}
              </div>
              <div className="text-haze" style={{ fontSize: u(4.4), lineHeight: 1.3, marginTop: u(1) }}>
                {s.reason}
              </div>
            </div>
            <button
              type="button"
              onClick={() => onAccept(s)}
              className="flex shrink-0 items-center rounded text-white"
              style={{ fontSize: u(5), padding: `${u(2.5)} ${u(4)}`, gap: u(1.5), background: "#f783e9" }}
            >
              <Check style={{ width: u(5), height: u(5) }} />
              Akceptuj
            </button>
            <button type="button" onClick={() => onDismiss(s)} className="shrink-0 text-haze hover:text-plum" aria-label="Odrzuć">
              <X style={{ width: u(5.5), height: u(5.5) }} />
            </button>
          </div>
        ))}
      </div>

      <button
        type="button"
        onClick={onHandoff}
        disabled={handoffBusy || audit.screens === 0}
        className="flex shrink-0 flex-col items-center justify-center text-white transition-transform enabled:hover:scale-[1.01] enabled:active:scale-[0.98] disabled:opacity-60"
        style={{
          marginTop: u(6),
          height: u(30),
          borderRadius: u(7),
          background: "#f783e9",
          boxShadow: `0 ${u(1.5)} ${u(6)} rgba(240, 110, 220, 0.35)`,
        }}
      >
        <span style={{ fontSize: u(8.4), lineHeight: 1.1 }}>{handoffBusy ? "Generuję..." : "Generuj Handoff"}</span>
        <span style={{ fontSize: u(4.8), opacity: 0.9, marginTop: u(1.5) }}>Figma + Claude</span>
      </button>
    </div>
  );
}
