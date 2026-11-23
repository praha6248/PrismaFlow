import { useState } from "react";
import { Expand } from "lucide-react";
import { CardDialog } from "./CardDialog";
import { Card, Radio, u } from "../components/ui";
import type { Persona } from "../types";
import { EvidenceBadge } from "./EvidenceBadge";
import { t } from "../i18n";

const profileFields = {
  situation: "Miejsce i moment użycia",
  device: "Urządzenie i warunki",
  goal: "Cel użytkownika",
  workaround: "Jak radzi sobie dziś",
  barrier: "Główna bariera",
  success: "Po czym pozna sukces",
  question: "Pytanie do wywiadu",
} as const;

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

export function PersonaCard({
  persona,
  index,
  selectedOption,
  onSelect,
}: Props) {
  const [expanded, setExpanded] = useState(false);
  const selected = selectedOption !== null;
  const source = persona.profile?.quote_source ?? "";
  const forum = source.startsWith("forum:") ? source.slice(6) || "forum" : "";
  return (
    <Card
      index={index}
      selected={selected}
      onSelect={selected ? undefined : () => onSelect(0)}
    >
      <div
        className="absolute flex items-center"
        style={{ left: u(12), top: u(12), right: u(31) }}
      >
        <span
          className="flex shrink-0 items-center justify-center rounded-full font-serif text-plum"
          style={{
            width: u(24),
            height: u(24),
            fontSize: "var(--text-title)",
            background: AVATAR_COLORS[index % AVATAR_COLORS.length],
          }}
        >
          {persona.name.trim().charAt(0).toUpperCase()}
        </span>
        <div className="min-w-0" style={{ marginLeft: u(7) }}>
          <div
            className="truncate text-ink"
            style={{ fontSize: "var(--text-body)", lineHeight: 1.1 }}
          >
            {persona.name}, {persona.age} {yearsLabel(persona.age)}
          </div>
          <div
            className="truncate text-haze"
            style={{ fontSize: "var(--text-small)", marginTop: u(2.5), lineHeight: 1.1 }}
          >
            {persona.role}
          </div>
        </div>
      </div>

      <button type="button" aria-label={t("Rozwiń profil persony")} title={t("Rozwiń profil persony")}
        className="absolute rounded-full p-1 text-mauve hover:bg-purple-50"
        style={{ right: u(8), top: u(12) }}
        onKeyDown={event => event.stopPropagation()}
        onClick={event => { event.stopPropagation(); setExpanded(true); }}>
        <Expand size={18} />
      </button>
      {expanded && (
        <CardDialog title={persona.name} onClose={() => setExpanded(false)}>
          <p className="mb-4 text-haze">{persona.role}</p>
          <p className="mb-2 text-sm font-medium text-mauve">{t("Hipoteza do sprawdzenia w badaniu")}</p>
          <blockquote className="whitespace-pre-wrap break-words font-serif text-2xl leading-snug">„{persona.quote}”</blockquote>
          {forum && <p className="mt-2 text-sm text-haze">{t("Cytat z forum: {place}", { place: forum })}</p>}
          <dl className="mt-5 grid gap-4">
            {(Object.keys(profileFields) as (keyof typeof profileFields)[]).map(key =>
              persona.profile?.[key] && <div key={key}>
                <dt className="text-sm font-semibold text-mauve">{t(profileFields[key])}</dt>
                <dd className="mt-1 break-words text-ink">{persona.profile[key]}</dd>
              </div>
            )}
          </dl>
          {!persona.profile?.situation && <p className="mt-4 text-sm text-haze">{t("Wygeneruj persony ponownie, aby dodać kontekst użycia.")}</p>}
        </CardDialog>
      )}

      <p
        className="absolute line-clamp-4 font-serif text-plum"
        style={{
          left: u(12),
          right: u(12),
          top: u(46),
          fontSize: "var(--text-title)",
          lineHeight: u(14.2),
        }}
        title={forum ? `${persona.quote} — ${t("Cytat z forum: {place}", { place: forum })}` : persona.quote}
      >
        „{persona.quote}”
      </p>

      <div
        className="absolute"
        style={{
          left: u(12),
          right: u(12),
          top: u(111.6),
          height: u(0.6),
          background: "#efe8f5",
        }}
      />
      <div
        className="absolute tracking-[0.14em] text-haze"
        style={{ left: u(12), top: u(121.7), fontSize: "var(--text-small)", lineHeight: 1 }}
      >
        {t("GŁÓWNY PROBLEM")}
      </div>
      <EvidenceBadge
        evidence={persona.evidence ?? []}
        style={{ right: u(12), top: u(118) }}
      />

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
              boxShadow: checked ? `inset 0 0 0 ${u(0.8)} var(--color-pink)` : "none",
            }}
          >
            <Radio checked={checked} size={8.5} />
            <span
              className="line-clamp-2 text-mauve"
              style={{ fontSize: "var(--text-small)", lineHeight: u(7.8) }}
              title={option}
            >
              {option}
            </span>
          </button>
        );
      })}
    </Card>
  );
}
