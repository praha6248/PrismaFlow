import { Paperclip } from "lucide-react";
import { useState } from "react";
import { u, SHADOW } from "../components/ui";
import type { CitedEvidence } from "../types";
import { plural, t } from "../i18n";

const SOURCE_LABELS: Record<string, string> = {
  autocomplete: "Google",
  community: t("Dyskusja"),
  reddit: "Reddit",
  trends: "Trends",
  llm: t("Model"),
};

function sourceLabel(item: CitedEvidence): string {
  const base = SOURCE_LABELS[item.source] ?? item.source;
  return item.place ? `${base} · ${item.place}` : base;
}

interface Props {
  evidence: CitedEvidence[];
  style?: React.CSSProperties;
}

export function EvidenceBadge({ evidence, style }: Props) {
  const [open, setOpen] = useState(false);
  const empty = evidence.length === 0;
  return (
    <div
      className="absolute"
      style={style}
      onClick={(event) => event.stopPropagation()}
    >
      <button
        type="button"
        disabled={empty}
        onClick={() => setOpen((value) => !value)}
        className="flex items-center rounded-full transition-colors"
        style={{
          gap: u(2.5),
          padding: `${u(2)} ${u(5)}`,
          fontSize: u(5),
          background: empty ? "#f6f0f3" : open ? "#f783e9" : "#fbe3f7",
          color: empty ? "#b18a9c" : open ? "#ffffff" : "#a3358f",
        }}
        title={
          empty
            ? t("Hipoteza bez dowodów — sprawdź ją w rozmowach")
            : t("Pokaż dowody, na których to oparto")
        }
      >
        <Paperclip style={{ width: u(5), height: u(5) }} />
        {empty
          ? t("bez dowodów")
          : `${evidence.length} ${plural(evidence.length, "dowód", "dowody", "dowodów")}`}
      </button>
      {open && !empty && (
        <div
          className="pf-fade-up pf-scroll absolute z-30 overflow-y-auto bg-white"
          style={{
            right: 0,
            bottom: `calc(100% + ${u(4)})`,
            width: u(190),
            maxHeight: u(150),
            padding: u(7),
            borderRadius: u(8),
            boxShadow: SHADOW,
          }}
        >
          <div
            className="tracking-[0.12em] text-haze"
            style={{ fontSize: u(4.6), marginBottom: u(4) }}
          >
            {t("NA PODSTAWIE")}
          </div>
          {evidence.map((item) => (
            <div
              key={item.id}
              style={{
                padding: `${u(3)} 0`,
                borderTop: `${u(0.5)} solid #f2ebf7`,
              }}
            >
              <div className="text-haze" style={{ fontSize: u(4.4) }}>
                {sourceLabel(item)}
              </div>
              <div
                className="text-ink"
                style={{ fontSize: u(5.6), lineHeight: 1.35 }}
                title={item.url ?? undefined}
              >
                {item.title}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
