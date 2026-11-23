import { ArrowDownRight, ArrowRight, ArrowUpRight } from "lucide-react";
import { Card, Radio, u } from "../components/ui";
import type { Problem } from "../types";
import { EvidenceBadge } from "./EvidenceBadge";

interface Props {
  problem: Problem;
  index: number;
  selected: boolean;
  scaleMax: number;
  onSelect: () => void;
}

function growthStyle(growth: number) {
  if (growth >= 5) return { background: "#efe6fb", color: "#6d4f8e", Icon: ArrowUpRight };
  if (growth <= -5) return { background: "#f4f0f8", color: "#8a7d96", Icon: ArrowDownRight };
  return { background: "#f2edf8", color: "#7c6d88", Icon: ArrowRight };
}

export function ProblemCard({ problem, index, selected, scaleMax, onSelect }: Props) {
  const trend = problem.trend;
  const months = trend?.available ? (trend.months ?? []).map((m) => m.value) : [];
  const growth = trend?.available && typeof trend.growth === "number" ? Math.round(trend.growth * 100) : null;
  const pill = growth !== null ? growthStyle(growth) : null;

  return (
    <Card index={index} selected={selected} onSelect={onSelect}>
      <div className="absolute flex items-center justify-between" style={{ left: u(12), right: u(12), top: u(12) }}>
        <span className="tracking-[0.14em] text-haze" style={{ fontSize: u(5.4), lineHeight: 1 }}>
          PROBLEM {String(index + 1).padStart(2, "0")}
        </span>
        <Radio checked={selected} />
      </div>

      <h3
        className="absolute line-clamp-2 font-serif font-normal text-plum"
        style={{ left: u(12), right: u(12), top: u(29.5), fontSize: u(13.2), lineHeight: u(16.3) }}
        title={problem.title}
      >
        {problem.title}
      </h3>

      <p
        className="absolute line-clamp-3"
        style={{ left: u(12), right: u(12), top: u(65), fontSize: u(6.4), lineHeight: u(8.4), color: "#7c6d88" }}
        title={problem.description}
      >
        {problem.description}
      </p>

      <div className="absolute" style={{ left: u(12), right: u(12), top: u(92), height: u(0.6), background: "#efe8f5" }} />

      <div className="absolute" style={{ left: u(12), top: u(101) }}>
        <div className="font-serif text-ink" style={{ fontSize: u(14.7), lineHeight: 1 }}>
          {trend?.available ? trend.index : "—"}
        </div>
        <div className="text-haze" style={{ fontSize: u(4.8), marginTop: u(3), lineHeight: 1 }}>
          {trend?.available ? "indeks Google Trends (0–100)" : "brak danych w Google Trends"}
        </div>
      </div>

      <div className="absolute flex flex-col items-center" style={{ left: u(109), top: u(101) }}>
        <span
          className="flex items-center justify-center rounded-full"
          style={{
            width: u(57),
            height: u(16),
            gap: u(2),
            fontSize: u(7),
            background: pill?.background ?? "#f1edf6",
            color: pill?.color ?? "#aa9fb2",
          }}
        >
          {growth !== null ? `${growth > 0 ? "+" : ""}${growth}%` : "—"}
          {pill && <pill.Icon style={{ width: u(7), height: u(7) }} />}
        </span>
        <span className="text-haze" style={{ fontSize: u(4.8), marginTop: u(3), lineHeight: 1 }}>
          3 mies. vs 9 mies.
        </span>
      </div>

      <div className="absolute flex items-end" style={{ left: u(12), top: u(135.6), width: u(153.5), height: u(21), gap: u(2.2) }}>
        {(months.length ? months : Array<number>(12).fill(0)).map((value, i, list) => (
          <div
            key={i}
            className="flex-1 transition-[height] duration-700"
            style={{
              height: `${Math.max(6, (value / Math.max(1, scaleMax)) * 100)}%`,
              borderRadius: u(1.4),
              background: i >= list.length - 3 ? "#cdb3ea" : "#ece4f5",
              opacity: months.length ? 1 : 0.5,
            }}
            title={months.length ? `${Math.round(value)}` : undefined}
          />
        ))}
      </div>
      <div className="absolute text-haze" style={{ left: u(12), top: u(162), fontSize: u(4.8), lineHeight: 1 }}>
        Zainteresowanie w ostatnich 12 miesiącach
      </div>
      <EvidenceBadge evidence={problem.evidence ?? []} style={{ right: u(12), top: u(158) }} />

      {problem.quote && (
        <p
          className="absolute line-clamp-2 font-serif italic text-mauve"
          style={{ left: u(12), right: u(12), top: u(176), fontSize: u(7.2), lineHeight: u(9) }}
          title={problem.quote_source === "autocomplete" ? "Podpowiedź Google" : "Dyskusja społeczności (Stack Exchange, Lemmy)"}
        >
          „{problem.quote}”
        </p>
      )}
    </Card>
  );
}
