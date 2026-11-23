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
          fontSize: "var(--text-small)",
          background: empty ? "#f6f0f3" : open ? "var(--color-pink-button)" : "#fbe3f7",
          color: empty ? "var(--color-haze)" : open ? "var(--color-on-pink)" : "var(--color-pink-text)",
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
            style={{ fontSize: "var(--text-small)", marginBottom: u(4) }}
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
              <div className="text-haze" style={{ fontSize: "var(--text-small)" }}>
                {sourceLabel(item)}
              </div>
              <div
                className="text-ink"
                style={{ fontSize: "var(--text-small)", lineHeight: 1.35 }}
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
