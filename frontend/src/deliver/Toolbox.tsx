import { GripVertical, Plus } from "lucide-react";
import { u } from "../components/ui";
import type { Feature, FlowScreen } from "../types";
import { t } from "../i18n";

interface Props {
  features: Feature[];
  screens: FlowScreen[];
  selectedId: string | null;
  onFocusScreen: (screenId: string) => void;
  onAddScreen: () => void;
}

export function Toolbox({
  features,
  screens,
  selectedId,
  onFocusScreen,
  onAddScreen,
}: Props) {
  const must = features.filter((f) => f.priority === "must");
  const usedOn = (feature: Feature) =>
    screens.find((s) => s.feature_ids.includes(feature.id));
  const ordered = [...must, ...features.filter((f) => f.priority !== "must")];

  return (
    <div
      className="flex h-full flex-col"
      style={{ padding: `${u(9)} ${u(8)} ${u(8)}` }}
    >
      <span
        className="font-serif text-ink"
        style={{ fontSize: u(10), lineHeight: 1 }}
      >
        {t("Przybornik")}
      </span>
      <span className="text-haze" style={{ fontSize: u(4.8), marginTop: u(3) }}>
        {t("{count} z Develop", { count: features.length })} · {must.length}{" "}
        Must-Have
      </span>
      <span
        className="text-mauve"
        style={{ fontSize: u(5.4), lineHeight: 1.4, marginTop: u(6) }}
      >
        {t("Przeciągnij funkcję na ekran na kanwie obok.")}
      </span>

      <div
        className="pf-scroll flex min-h-0 flex-1 flex-col overflow-y-auto"
        style={{ gap: u(4), marginTop: u(6) }}
      >
        {ordered.map((feature) => {
          const screen = usedOn(feature);
          return (
            <div
              key={feature.id}
              draggable
              onDragStart={(event) => {
                event.dataTransfer.setData(
                  "application/x-prismaflow-feature",
                  String(feature.id),
                );
                event.dataTransfer.effectAllowed = "copy";
              }}
              className="relative shrink-0 cursor-grab active:cursor-grabbing"
              style={{
                padding: `${u(5)} ${u(6)} ${u(5)} ${u(12)}`,
                borderRadius: u(5),
                background: "#ffffff",
                border: `${u(0.5)} solid ${feature.priority === "must" ? "#f9d0ef" : "#eee6f5"}`,
                boxShadow: `0 ${u(1)} ${u(4)} rgba(196, 160, 232, 0.16)`,
              }}
            >
              <span
                className="absolute rounded-full"
                style={{
                  left: u(5),
                  top: u(7.5),
                  width: u(3.4),
                  height: u(3.4),
                  background: screen ? "#f783e9" : "#d9c6ec",
                }}
              />
              <GripVertical
                className="absolute text-[#cfc4da]"
                style={{ right: u(3), top: u(5), width: u(6), height: u(6) }}
              />
              <div
                className="text-ink"
                style={{ fontSize: u(6), lineHeight: 1.3, paddingRight: u(6) }}
              >
                {feature.title}
              </div>
              <div
                className="text-haze"
                style={{ fontSize: u(4.4), marginTop: u(2.5) }}
              >
                {feature.priority === "must"
                  ? "Must"
                  : feature.priority === "should"
                    ? "Should"
                    : "Could"}{" "}
                ·{" "}
                {screen
                  ? t("Użyto: {screen}", { screen: screen.name })
                  : t("Jeszcze nieprzypisana")}
              </div>
            </div>
          );
        })}

        <div
          className="flex shrink-0 items-center text-haze"
          style={{ gap: u(8), fontSize: u(4.4), marginTop: u(2) }}
        >
          <span className="flex items-center" style={{ gap: u(2) }}>
            <span
              className="rounded-full bg-[#d9c6ec]"
              style={{ width: u(3), height: u(3) }}
            />
            {t("nieprzypisana")}
          </span>
          <span className="flex items-center" style={{ gap: u(2) }}>
            <span
              className="rounded-full bg-[#f783e9]"
              style={{ width: u(3), height: u(3) }}
            />
            {t("użyta")}
          </span>
        </div>

        <span
          className="shrink-0 tracking-[0.1em] text-haze"
          style={{ fontSize: u(4.6), marginTop: u(6) }}
        >
          {t("EKRANY W PRZEPŁYWIE")} · {screens.length}
        </span>
        {screens.map((screen, index) => (
          <button
            key={screen.id}
            type="button"
            onClick={() => onFocusScreen(screen.id)}
            className="shrink-0 text-left transition-colors hover:text-plum"
            style={{
              fontSize: u(5.6),
              color: selectedId === screen.id ? "#e04fcf" : "var(--color-mauve)",
            }}
          >
            <span className="text-haze" style={{ marginRight: u(4) }}>
              {String(index + 1).padStart(2, "0")}
            </span>
            {screen.name}
          </button>
        ))}
      </div>

      <button
        type="button"
        onClick={onAddScreen}
        className="flex shrink-0 items-center justify-center transition-transform hover:scale-[1.01] active:scale-[0.98]"
        style={{
          marginTop: u(6),
          height: u(20),
          gap: u(3),
          borderRadius: u(6),
          fontSize: u(6.2),
          background: "#e9dcf8",
          color: "#573476",
        }}
      >
        <Plus style={{ width: u(6.5), height: u(6.5) }} />
        {t("Dodaj pusty ekran")}
      </button>
    </div>
  );
}
