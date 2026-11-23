import { u } from "../components/ui";
import { plural, t } from "../i18n";
import type { Flow, FlowElement } from "../types";
import { ITEM_TYPES, TYPE_LABELS } from "./ScreenNode";

function optionCount(element: FlowElement): string {
  const n = (element.items ?? []).length >= 2 ? element.items!.length : element.options;
  return `${n} ${plural(n, "opcja", "opcje", "opcji")}`;
}

function Arrow({ to, names }: { to: string | null | undefined; names: Record<string, string> }) {
  return to && names[to] ? (
    <span className="shrink-0 text-pink-text">→ {names[to]}</span>
  ) : (
    <span className="shrink-0 text-haze">{t("bez przejścia")}</span>
  );
}

export function ElementMap({ flow, only }: { flow: Flow; only?: string | null }) {
  const names = Object.fromEntries(flow.screens.map((s) => [s.id, s.name]));
  const screens = only ? flow.screens.filter((s) => s.id === only) : flow.screens;
  const small = { fontSize: "var(--text-small)", lineHeight: 1.35 } as const;

  return (
    <div className="flex flex-col" style={{ gap: u(4) }}>
      {screens.map((screen) => {
        const active = screen.elements.filter((e) => e.type !== "text");
        const buttons = active.filter((e) => e.type === "button" || e.type === "link").length;
        return (
          <div key={screen.id} className="rounded-md bg-white" style={{ padding: u(4), border: `${u(0.5)} solid #efe6f6` }}>
            <div className="flex items-baseline text-ink" style={{ ...small, gap: u(3) }}>
              <span className="font-semibold">{screen.name}</span>
              <span className="ml-auto text-haze">
                {`${active.length} ${plural(active.length, "element", "elementy", "elementów")} · ${t("przyciski i linki: {b}", { b: buttons })}`}
              </span>
            </div>
            {active.map((element) => (
              <div key={element.id} style={{ marginTop: u(2) }}>
                <div className="flex items-baseline text-ink" style={{ ...small, gap: u(3) }}>
                  <span className="min-w-0 truncate">{element.label}</span>
                  <span className="shrink-0 text-haze">
                    {TYPE_LABELS[element.type]}
                    {ITEM_TYPES.includes(element.type) && ` · ${optionCount(element)}`}
                  </span>
                  <span className="ml-auto" />
                  {(!ITEM_TYPES.includes(element.type) || element.target) && <Arrow to={element.target} names={names} />}
                </div>
                {ITEM_TYPES.includes(element.type) &&
                  (element.items ?? []).map((item, i) => (
                    <div key={i} className="flex items-baseline text-mauve" style={{ ...small, gap: u(3), paddingLeft: u(6) }}>
                      <span className="min-w-0 truncate">
                        {i + 1}. {item}
                      </span>
                      <span className="ml-auto" />
                      {element.item_targets?.[i] ? (
                        <Arrow to={element.item_targets[i]} names={names} />
                      ) : (
                        <span className="shrink-0 text-haze">{t("zmienia widok")}</span>
                      )}
                    </div>
                  ))}
              </div>
            ))}
          </div>
        );
      })}
    </div>
  );
}
