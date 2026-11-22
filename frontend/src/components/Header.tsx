import sparkle from "../assets/sparkle.png";

const PHASES = ["Discover", "Define", "Develop", "Deliver"] as const;
const STEP_X = [145, 262, 379, 500];

interface Props {
  active: number;
  onHome: () => void;
}

export function Header({ active, onHome }: Props) {
  return (
    <>
      <button
        type="button"
        onClick={onHome}
        className="absolute z-20 flex items-center"
        style={{ left: "calc(var(--u) * 15)", top: "calc(var(--u) * 16)" }}
        title="Nowy projekt"
      >
        <img
          src={sparkle}
          alt=""
          draggable={false}
          style={{ width: "calc(var(--u) * 19)", height: "calc(var(--u) * 19)" }}
        />
        <span
          className="font-serif text-ink"
          style={{ marginLeft: "calc(var(--u) * 7.5)", fontSize: "calc(var(--u) * 14.6)", lineHeight: 1 }}
        >
          PrismFlow
        </span>
      </button>

      <nav className="pointer-events-none absolute inset-x-0 top-0 z-20" aria-label="Fazy Double Diamond">
        <div
          className="absolute"
          style={{
            left: `calc(50% + var(--u) * ${STEP_X[0] - 322})`,
            width: `calc(var(--u) * ${STEP_X[3] - STEP_X[0]})`,
            top: "calc(var(--u) * 80.4)",
            height: "calc(var(--u) * 1.2)",
            background: "#fcdbfb",
          }}
        />
        {PHASES.map((phase, index) => {
          const isActive = index === active;
          const locked = index > active;
          return (
            <div
              key={phase}
              className="pointer-events-auto absolute flex flex-col items-center"
              style={{ left: `calc(50% + var(--u) * ${STEP_X[index] - 322})`, top: "calc(var(--u) * 52.8)", transform: "translateX(-50%)" }}
              title={locked ? "Faza w przygotowaniu" : phase}
              aria-current={isActive ? "step" : undefined}
              aria-disabled={locked}
            >
              <span
                className={locked ? "cursor-not-allowed text-ink" : "text-ink"}
                style={{ fontSize: "calc(var(--u) * 11)", lineHeight: 1 }}
              >
                {phase}
              </span>
              <span
                className="relative flex items-center justify-center rounded-full"
                style={{
                  marginTop: "calc(var(--u) * 10.2)",
                  width: "calc(var(--u) * 14)",
                  height: "calc(var(--u) * 14)",
                  border: `calc(var(--u) * 1) solid ${isActive ? "#fbb4f2" : "#fdd3fa"}`,
                  background: isActive ? "#fff4fd" : "#f9f5ff",
                }}
              >
                {isActive && (
                  <span
                    className="rounded-full"
                    style={{ width: "calc(var(--u) * 7.6)", height: "calc(var(--u) * 7.6)", background: "#f783e9" }}
                  />
                )}
              </span>
            </div>
          );
        })}
      </nav>
    </>
  );
}
