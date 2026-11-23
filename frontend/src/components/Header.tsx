import { Check } from "lucide-react";
import sparkle from "../assets/sparkle.png";
import { t } from "../i18n";

const PHASES = ["Discover", "Define", "Develop", "Deliver"] as const;
const STEP_X = [145, 262, 379, 500];

interface Props {
  active: number;
  reached: number;
  onHome: () => void;
  onNavigate: (index: number) => void;
}

export function Header({ active, reached, onHome, onNavigate }: Props) {
  return (
    <>
      <button
        type="button"
        onClick={onHome}
        className="absolute z-20 flex items-center"
        style={{ left: "calc(var(--u) * 15)", top: "calc(var(--u) * 16)" }}
        title={t("Nowy projekt")}
      >
        <img
          src={sparkle}
          alt=""
          draggable={false}
          style={{
            width: "calc(var(--u) * 19)",
            height: "calc(var(--u) * 19)",
          }}
        />
        <span
          className="font-serif text-ink"
          style={{
            marginLeft: "calc(var(--u) * 7.5)",
            fontSize: "calc(var(--u) * 14.6)",
            lineHeight: 1,
          }}
        >
          PrismaFlow
        </span>
      </button>

      <nav
        className="pointer-events-none absolute inset-x-0 top-0 z-20"
        aria-label={t("Fazy Double Diamond")}
      >
        <div
          className="absolute"
          style={{
            left: `calc(50% + var(--u) * ${STEP_X[0] - 322})`,
            width: `calc(var(--u) * ${STEP_X[3] - STEP_X[0]})`,
            top: "calc(var(--u) * 80.4)",
            height: "calc(var(--u) * 1.2)",
            background: "#fbd0f5",
          }}
        />
        {reached > 0 && (
          <div
            className="absolute transition-[width] duration-500"
            style={{
              left: `calc(50% + var(--u) * ${STEP_X[0] - 322})`,
              width: `calc(var(--u) * ${STEP_X[reached] - STEP_X[0]})`,
              top: "calc(var(--u) * 80.4)",
              height: "calc(var(--u) * 1.2)",
              background: "var(--color-pink)",
            }}
          />
        )}
        {PHASES.map((phase, index) => {
          const isActive = index === active;
          const done = index < reached && !isActive;
          const locked = index > reached;
          return (
            <button
              type="button"
              key={phase}
              disabled={locked || isActive}
              onClick={() => onNavigate(index)}
              className="pointer-events-auto absolute flex flex-col items-center disabled:cursor-default"
              style={{
                left: `calc(50% + var(--u) * ${STEP_X[index] - 322})`,
                top: "calc(var(--u) * 52.8)",
                transform: "translateX(-50%)",
              }}
              title={locked ? t("Ukończ wcześniejsze fazy") : phase}
              aria-current={isActive ? "step" : undefined}
            >
              <span
                className={locked ? "cursor-not-allowed text-ink" : "text-ink"}
                style={{ fontSize: "calc(var(--u) * 11)", lineHeight: 1 }}
              >
                {phase}
              </span>
              <span
                className="relative flex items-center justify-center rounded-full transition-colors duration-300"
                style={{
                  marginTop: "calc(var(--u) * 10.2)",
                  width: "calc(var(--u) * 14)",
                  height: "calc(var(--u) * 14)",
                  border: `calc(var(--u) * 1) solid ${isActive ? "#f783e9" : done ? "#f783e9" : "#f9c4f1"}`,
                  background: isActive
                    ? "#ffffff"
                    : done
                      ? "#f783e9"
                      : "#fff7fd",
                }}
              >
                {isActive && (
                  <span
                    className="rounded-full"
                    style={{
                      width: "calc(var(--u) * 7.6)",
                      height: "calc(var(--u) * 7.6)",
                      background: "var(--color-pink)",
                    }}
                  />
                )}
                {done && (
                  <Check
                    color="#ffffff"
                    strokeWidth={3}
                    style={{
                      width: "calc(var(--u) * 8)",
                      height: "calc(var(--u) * 8)",
                    }}
                  />
                )}
              </span>
            </button>
          );
        })}
      </nav>
    </>
  );
}
