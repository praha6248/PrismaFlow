import { Card, Radio, u } from "../components/ui";
import type { Persona } from "../types";

const AVATAR_COLORS = ["#e6dcf7", "#fbdcf3", "#dbe7f9"];

export function yearsLabel(age: number): string {
  const lastTwo = age % 100;
  const last = age % 10;
  if (last >= 2 && last <= 4 && (lastTwo < 12 || lastTwo > 14)) return "lata";
  return "lat";
}

interface Props {
  persona: Persona;
  index: number;
  selectedOption: number | null;
  onSelect: (option: number) => void;
}

export function PersonaCard({ persona, index, selectedOption, onSelect }: Props) {
  const selected = selectedOption !== null;
  return (
    <Card index={index} selected={selected} onSelect={selected ? undefined : () => onSelect(0)}>
      <div className="absolute flex items-center" style={{ left: u(12), top: u(12), right: u(12) }}>
        <span
          className="flex shrink-0 items-center justify-center rounded-full font-serif text-plum"
          style={{ width: u(24), height: u(24), fontSize: u(11), background: AVATAR_COLORS[index % AVATAR_COLORS.length] }}
        >
          {persona.name.trim().charAt(0).toUpperCase()}
        </span>
        <div className="min-w-0" style={{ marginLeft: u(7) }}>
          <div className="truncate text-ink" style={{ fontSize: u(9.3), lineHeight: 1.1 }}>
            {persona.name}, {persona.age} {yearsLabel(persona.age)}
          </div>
          <div className="truncate text-haze" style={{ fontSize: u(5.2), marginTop: u(2.5), lineHeight: 1.1 }}>
            {persona.role}
          </div>
        </div>
      </div>

      <p
        className="absolute line-clamp-4 font-serif text-plum"
        style={{ left: u(12), right: u(12), top: u(46), fontSize: u(10.9), lineHeight: u(14.2) }}
        title={persona.quote}
      >
        „{persona.quote}”
      </p>

      <div className="absolute" style={{ left: u(12), right: u(12), top: u(111.6), height: u(0.6), background: "#efe8f5" }} />
      <div className="absolute tracking-[0.14em] text-haze" style={{ left: u(12), top: u(121.7), fontSize: u(5.2), lineHeight: 1 }}>
        WYBIERZ GŁÓWNY PROBLEM
      </div>

      {persona.options.slice(0, 2).map((option, i) => {
        const checked = selectedOption === i;
        return (
          <button
            key={i}
            type="button"
            onClick={(event) => {
              event.stopPropagation();
              onSelect(i);
            }}
            className="absolute flex items-center text-left transition-[background,box-shadow] duration-200"
            style={{
              left: u(11.25),
              top: u(i === 0 ? 132.5 : 164.3),
              width: u(155),
              height: u(26.4),
              gap: u(6),
              padding: `0 ${u(7)}`,
              borderRadius: u(7),
              background: checked ? "#fef0fc" : "#f7f3fb",
              boxShadow: checked ? `inset 0 0 0 ${u(0.8)} #f783e9` : "none",
            }}
          >
            <Radio checked={checked} size={8.5} />
            <span className="line-clamp-2 text-mauve" style={{ fontSize: u(6.2), lineHeight: u(7.8) }} title={option}>
              {option}
            </span>
          </button>
        );
      })}
    </Card>
  );
}
