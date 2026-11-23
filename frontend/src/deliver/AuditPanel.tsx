import {
  AlertCircle,
  CheckCircle2,
  Check,
  ChevronDown,
  Sparkles,
  X,
} from "lucide-react";
import { useState, type ReactNode } from "react";
import { u } from "../components/ui";
import type { FlowAudit, Suggestion, TestsState } from "../types";
import { issueText } from "./TestsPanel";
import { ZONE_LABELS } from "./ScreenNode";
import { number, plural, t } from "../i18n";

export const pl = (value: number, digits = 2) => number(value, digits);

type Tone = "good" | "warn" | "neutral";

const TONES: Record<Tone, { background: string; border: string }> = {
  good: { background: "#e6f5ea", border: "#cdebd6" },
  warn: { background: "#fdebf7", border: "#f9d0ef" },
  neutral: { background: "#f7f3fb", border: "#eee6f5" },
};

function Metric({
  tone,
  title,
  value,
  children,
}: {
  tone: Tone;
  title: string;
  value?: ReactNode;
  children?: ReactNode;
}) {
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
        <span
          className="text-ink"
          style={{ fontSize: "var(--text-small)", lineHeight: 1.25 }}
        >
          {title}
        </span>
        {value !== undefined && (
          <span
            className="font-serif text-ink"
            style={{ fontSize: "var(--text-title)", lineHeight: 0.9 }}
          >
            {value}
          </span>
        )}
      </div>
      {children && (
        <div
          style={{
            fontSize: "var(--text-small)",
            lineHeight: 1.45,
            color: "var(--color-muted)",
            marginTop: u(1.5),
          }}
        >
          {children}
        </div>
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
  onCaseStudy: () => void;
  onFocusScreen: (screenId: string) => void;
  tests?: TestsState;
  onOpenTests: () => void;
}

export function AuditPanel({
  audit,
  suggestions,
  optimizing,
  handoffBusy,
  onOptimize,
  onAccept,
  onDismiss,
  onHandoff,
  onCaseStudy,
  onFocusScreen,
  tests,
  onOpenTests,
}: Props) {
  const c = audit.constants;
  const hick = audit.hick[0];
  const fitts = audit.fitts[0];
  const dead = audit.dead_ends;
  const primarySmall = audit.targets.below_aaa.filter((t) => t.primary);
  const steps = audit.steps;
  const [details, setDetails] = useState(false);

  const issues: { text: string; screenId?: string }[] = [];
  if (steps.status === "missing")
    issues.push({
      text: t(
        "Oznacz ekran startowy i ekran celu, żeby policzyć drogę do celu.",
      ),
    });
  if (steps.status === "no_path")
    issues.push({
      text: t("Ze startu nie da się dojść do celu. Połącz ekrany."),
    });
  if (steps.value !== null && steps.value > 3)
    issues.push({
      text: t("Droga do celu: {steps}. Spróbuj skrócić ją do 3.", {
        steps: `${steps.value} ${plural(steps.value, "krok", "kroki", "kroków")}`,
      }),
    });
  dead.forEach((d) =>
    issues.push({
      text: t("{screen}: brak przejścia dalej.", { screen: d.screen }),
      screenId: d.screen_id,
    }),
  );
  audit.unreachable.forEach((d) =>
    issues.push({
      text: t("{screen}: nie da się tu dojść.", { screen: d.screen }),
      screenId: d.screen_id,
    }),
  );
  audit.hick
    .filter((h) => h.warning)
    .slice(0, 2)
    .forEach((h) =>
      issues.push({
        text: t(
          "{screen}: za dużo opcji w {where}. Schowaj część w „Więcej”.",
          {
            screen: h.screen,
            where: h.element ? `„${h.element}”` : t("wyborze akcji"),
          },
        ),
        screenId: h.screen_id,
      }),
    );
  primarySmall
    .slice(0, 2)
    .forEach((target) =>
      issues.push({
        text: t("{screen}: „{element}” jest za mały do kliknięcia kciukiem.", {
          screen: target.screen,
          element: target.element,
        }),
        screenId: target.screen_id,
      }),
    );
  audit.fitts
    .slice(0, 2)
    .forEach((f) =>
      issues.push({
        text: t("{screen}: „{element}” trudno sięgnąć. Przenieś go niżej.", {
          screen: f.screen,
          element: f.element,
        }),
        screenId: f.screen_id,
      }),
    );

  return (
    <div
      className="flex h-full flex-col"
      style={{ padding: `${u(9)} ${u(8)} ${u(8)}` }}
    >
      <div className="flex items-center justify-between">
        <span
          className="font-serif text-ink"
          style={{ fontSize: "var(--text-title)", lineHeight: 1 }}
        >
          {t("Audyt UX")}
        </span>
        <span
          className="flex items-center rounded-full bg-[#f3ecfa] text-mauve"
          style={{ fontSize: "var(--text-small)", padding: `${u(2)} ${u(5)}`, gap: u(2.5) }}
        >
          <span
            className="rounded-full bg-pink"
            style={{
              width: u(3),
              height: u(3),
              animation: "pf-pulse 1.8s ease-in-out infinite",
            }}
          />
          {t("Na żywo")}
        </span>
      </div>
      <span className="text-haze" style={{ fontSize: "var(--text-small)", marginTop: u(3) }}>
        {audit.screens} {plural(audit.screens, "ekran", "ekrany", "ekranów")} ·{" "}
        {t("analiza całego flow")}
      </span>

      <div
        className="pf-scroll flex min-h-0 flex-1 flex-col overflow-y-auto"
        style={{ gap: u(4), marginTop: u(6) }}
      >
        <div
          className="pf-fade shrink-0"
          style={{
            borderRadius: u(5),
            background: issues.length
              ? TONES.warn.background
              : TONES.good.background,
            border: `${u(0.5)} solid ${issues.length ? TONES.warn.border : TONES.good.border}`,
            padding: `${u(4.5)} ${u(6)}`,
          }}
        >
          <div
            className="flex items-center text-ink"
            style={{ gap: u(3), fontSize: "var(--text-small)" }}
          >
            {issues.length ? (
              <AlertCircle
                style={{ width: u(6), height: u(6), color: "var(--color-pink-text)" }}
              />
            ) : (
              <CheckCircle2
                style={{ width: u(6), height: u(6), color: "var(--color-success)" }}
              />
            )}
            {issues.length
              ? t("Do poprawy: {count}", { count: issues.length })
              : t("Flow wygląda dobrze")}
          </div>
          <div
            className="flex flex-col"
            style={{
              gap: u(2),
              marginTop: u(2.5),
              fontSize: "var(--text-small)",
              lineHeight: 1.4,
              color: "var(--color-muted)",
            }}
          >
            {issues.length === 0 && (
              <span>
                {steps.value !== null &&
                  t("{steps} do celu", {
                    steps: `${steps.value} ${plural(steps.value, "krok", "kroki", "kroków")}`,
                  })}
                {audit.klm &&
                  ` · ${t("około {seconds} s", { seconds: pl(audit.klm.seconds, 0) })}`}
                . {t("Brak ślepych uliczek i za małych przycisków.")}
              </span>
            )}
            {issues.map((issue, index) =>
              issue.screenId ? (
                <button
                  key={index}
                  type="button"
                  className="text-left hover:underline"
                  onClick={() => onFocusScreen(issue.screenId!)}
                >
                  {issue.text}
                </button>
              ) : (
                <span key={index}>{issue.text}</span>
              ),
            )}
          </div>
        </div>

        <div
          className="shrink-0"
          style={{
            borderRadius: u(5),
            background: "#ffffff",
            border: `${u(0.5)} solid #eee6f5`,
            padding: `${u(4.5)} ${u(6)}`,
          }}
        >
          <div className="text-ink" style={{ fontSize: "var(--text-small)" }}>
            {tests?.participants
              ? t("Zaobserwowane u {n}", {
                  n: `${tests.participants} ${plural(tests.participants, "osoby", "osób", "osób")}`,
                })
              : t("Jeszcze nie testowano z ludźmi")}
          </div>
          <div
            className="flex flex-col"
            style={{ gap: u(2), marginTop: u(2.5), fontSize: "var(--text-small)", lineHeight: 1.4, color: "var(--color-muted)" }}
          >
            {!tests?.participants && (
              <span>{t("Metryki powyżej to przewidywania. Sprawdź prototyp z 5 osobami.")}</span>
            )}
            {tests?.participants && !tests.issues.length ? (
              <span>{t("Każde zadanie ukończyło co najmniej 80% osób.")}</span>
            ) : null}
            {tests?.issues.slice(0, 4).map((issue, i) => (
              <span key={i}>{issueText(issue)}</span>
            ))}
          </div>
          <button
            type="button"
            onClick={onOpenTests}
            disabled={audit.screens === 0}
            className="text-pink-text hover:underline disabled:opacity-50"
            style={{ fontSize: "var(--text-small)", marginTop: u(3) }}
          >
            {tests?.participants ? t("Wyniki i kolejny test") : t("Przeprowadź test z użytkownikiem")}
          </button>
        </div>

        <button
          type="button"
          onClick={() => setDetails((v) => !v)}
          aria-expanded={details}
          className="flex shrink-0 items-center text-mauve hover:text-plum"
          style={{ gap: u(2), fontSize: "var(--text-small)" }}
        >
          <ChevronDown
            style={{
              width: u(5),
              height: u(5),
              transform: details ? "rotate(180deg)" : undefined,
              transition: "transform 150ms",
            }}
          />
          {details ? t("Ukryj szczegóły pomiarów") : t("Szczegóły pomiarów")}
        </button>

        {details && (
          <>
            <Metric
              tone={
                steps.value !== null
                  ? steps.value <= 3
                    ? "good"
                    : "warn"
                  : "warn"
              }
              title={t("Kroki do celu")}
              value={steps.value ?? "—"}
            >
              {steps.status === "ok"
                ? `Time-to-Value · ${steps.path.join(" → ")}`
                : steps.status === "missing"
                  ? t("Oznacz ekran startowy i ekran celu (CEL).")
                  : t("Cel jest nieosiągalny ze startu — połącz ekrany.")}
            </Metric>

            {audit.klm && (
              <Metric
                tone={audit.klm.seconds <= 10 ? "good" : "warn"}
                title={t("Szacowany czas do celu")}
                value={`${pl(audit.klm.seconds, 1)} s`}
              >
                {t(
                  "Model KLM: przygotowanie {mental} s + Hick + Fitts na każdym kroku ścieżki krytycznej.",
                  { mental: pl(c.klm_mental) },
                )}
              </Metric>
            )}

            {hick && (
              <Metric
                tone={hick.warning ? "warn" : "neutral"}
                title={t("Hick · złożoność decyzji")}
              >
                <button
                  type="button"
                  className="text-left hover:underline"
                  onClick={() => onFocusScreen(hick.screen_id)}
                >
                  {hick.screen} ·{" "}
                  {hick.element ? `„${hick.element}”` : t("wybór akcji")}:{" "}
                  {hick.options}{" "}
                  {plural(hick.options, "opcja", "opcje", "opcji")} ={" "}
                  {pl(hick.seconds)} s.
                </button>
                {hick.warning && (
                  <>
                    <br />
                    {t("Ukryj {options} w sekcji „Więcej”.", {
                      options: `${hick.hide} ${plural(hick.hide, "opcję", "opcje", "opcji")}`,
                    })}
                  </>
                )}
                <br />
                <span className="text-haze">
                  {t("Liczone osobno dla każdej listy, filtra i wyboru akcji")}{" "}
                  · a = {pl(c.hick_a)} s · b = {pl(c.hick_b)} s
                </span>
              </Metric>
            )}

            <Metric
              tone={fitts ? "warn" : "good"}
              title={t("Fitts · ergonomia kliknięć")}
            >
              {fitts ? (
                <button
                  type="button"
                  className="text-left hover:underline"
                  onClick={() => onFocusScreen(fitts.screen_id)}
                >
                  „{fitts.element}”: {fitts.size} = {ZONE_LABELS[fitts.zone]}{" "}
                  (ID {pl(fitts.index, 1)}).
                  <br />
                  {t("Zwiększ cel i przenieś go na dół.")}
                  {audit.fitts.length > 1 &&
                    ` (+${audit.fitts.length - 1} ${t("kolejnych")})`}
                </button>
              ) : (
                t("Wszystkie cele mają ID ≤ {limit} bita.", {
                  limit: pl(c.fitts_limit, 1),
                })
              )}
            </Metric>

            <Metric
              tone={primarySmall.length ? "warn" : "good"}
              title={t("Cele dotykowe · WCAG 2.2")}
              value={`${audit.targets.aaa}/${audit.targets.total}`}
            >
              {primarySmall.length ? (
                <button
                  type="button"
                  className="text-left hover:underline"
                  onClick={() => onFocusScreen(primarySmall[0].screen_id)}
                >
                  {t(
                    "„{element}” ma {pixels} px — przejście powinno mieć ≥ {min} px.",
                    {
                      element: primarySmall[0].element,
                      pixels: primarySmall[0].pixels,
                      min: c.wcag_aaa,
                    },
                  )}
                </button>
              ) : (
                t(
                  "Przejścia mają ≥ {aaa} px (2.5.5 AAA); minimum AA to {aa} px.",
                  { aaa: c.wcag_aaa, aa: c.wcag_aa },
                )
              )}
            </Metric>

            <Metric
              tone={dead.length || audit.unreachable.length ? "warn" : "good"}
              title={
                dead.length
                  ? `${dead.length} ${plural(dead.length, "ślepa uliczka", "ślepe uliczki", "ślepych uliczek")}`
                  : t("Brak ślepych uliczek")
              }
            >
              {dead.length > 0 && (
                <button
                  type="button"
                  className="text-left hover:underline"
                  onClick={() => onFocusScreen(dead[0].screen_id)}
                >
                  {dead.map((d) => d.screen).join(", ")} —{" "}
                  {t("brak przejścia dalej.")}
                </button>
              )}
              {audit.unreachable.length > 0 && (
                <>
                  {dead.length > 0 && <br />}
                  {t("Nieosiągalne:")}{" "}
                  {audit.unreachable.map((d) => d.screen).join(", ")}.
                </>
              )}
              {!dead.length &&
                !audit.unreachable.length &&
                t("Z każdego ekranu da się przejść dalej.")}
            </Metric>
          </>
        )}

        <span
          className="font-serif text-ink"
          style={{ fontSize: "var(--text-body)", marginTop: u(3) }}
        >
          {t("Asystent AI")}
        </span>
        <button
          type="button"
          onClick={onOptimize}
          disabled={optimizing || audit.screens === 0}
          className="flex shrink-0 items-center justify-center transition-transform enabled:hover:scale-[1.01] enabled:active:scale-[0.98] disabled:opacity-60"
          style={{
            height: u(17),
            gap: u(3),
            borderRadius: u(5),
            fontSize: "var(--text-small)",
            background: "#e9dcf8",
            color: "var(--color-ink)",
          }}
        >
          <Sparkles style={{ width: u(6.5), height: u(6.5) }} />
          {optimizing ? t("Analizuję flow…") : t("Optymalizuj flow przez AI")}
        </button>
        {suggestions.map((s) => (
          <div
            key={s.id}
            className="pf-fade-up flex shrink-0 items-center"
            style={{
              gap: u(4),
              padding: `${u(4)} ${u(5)}`,
              borderRadius: u(5),
              background: "#ffffff",
              border: `${u(0.5)} solid #eee6f5`,
            }}
          >
            <div className="min-w-0 flex-1">
              <div
                className="text-ink"
                style={{ fontSize: "var(--text-small)", lineHeight: 1.3 }}
              >
                {s.title}
              </div>
              <div
                className="text-haze"
                style={{ fontSize: "var(--text-small)", lineHeight: 1.3, marginTop: u(1) }}
              >
                {s.reason}
              </div>
            </div>
            <button
              type="button"
              onClick={() => onAccept(s)}
              className="flex shrink-0 items-center rounded font-semibold text-on-pink"
              style={{
                fontSize: "var(--text-small)",
                padding: `${u(2.5)} ${u(4)}`,
                gap: u(1.5),
                background: "var(--color-pink-button)",
              }}
            >
              <Check style={{ width: u(5), height: u(5) }} />
              {t("Akceptuj")}
            </button>
            <button
              type="button"
              onClick={() => onDismiss(s)}
              className="shrink-0 text-haze hover:text-plum"
              aria-label={t("Odrzuć")}
            >
              <X style={{ width: u(5.5), height: u(5.5) }} />
            </button>
          </div>
        ))}
      </div>

      <div className="flex shrink-0" style={{ marginTop: u(6), gap: u(4) }}>
        <button
          type="button"
          onClick={onHandoff}
          disabled={handoffBusy || audit.screens === 0}
          className="flex min-w-0 flex-1 flex-col items-center justify-center font-semibold text-on-pink transition-transform enabled:hover:scale-[1.01] enabled:active:scale-[0.98] disabled:opacity-60"
          style={{
            height: u(30),
            borderRadius: u(7),
            background: "var(--color-pink-button)",
            boxShadow: `0 ${u(1.5)} ${u(6)} rgba(240, 110, 220, 0.35)`,
          }}
        >
          <span style={{ fontSize: "var(--text-body)", lineHeight: 1.1 }}>
            {handoffBusy ? t("Generuję…") : t("Generuj Handoff")}
          </span>
        </button>
        <button
          type="button"
          onClick={onCaseStudy}
          disabled={audit.screens === 0}
          className="flex shrink-0 flex-col items-center justify-center font-semibold text-on-pink transition-transform enabled:hover:scale-[1.01] enabled:active:scale-[0.98] disabled:opacity-60"
          style={{
            width: u(52),
            height: u(30),
            borderRadius: u(7),
            background: "var(--color-pink-button)",
            boxShadow: `0 ${u(1.5)} ${u(6)} rgba(240, 110, 220, 0.35)`,
          }}
        >
          <span style={{ fontSize: "var(--text-body)", lineHeight: 1.1 }}>
            {t("Case study")}
          </span>
        </button>
      </div>
    </div>
  );
}
