import { Check, Copy, RotateCcw, X } from "lucide-react";
import { useState } from "react";
import { u } from "../components/ui";
import type { Handoff } from "../types";
import { t } from "../i18n";

interface Props {
  handoff: Handoff;
  onClose: () => void;
  onRestart: () => void;
}

export function HandoffModal({ handoff, onClose, onRestart }: Props) {
  const [tab, setTab] = useState<"figma" | "claude">("figma");
  const [copied, setCopied] = useState(false);
  const text = tab === "figma" ? handoff.figma_prompt : handoff.claude_md;

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      const area = document.createElement("textarea");
      area.value = text;
      document.body.appendChild(area);
      area.select();
      document.execCommand("copy");
      area.remove();
    }
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1600);
  };

  return (
    <div
      className="pf-fade absolute inset-0 z-40 flex items-center justify-center bg-[rgba(243,238,255,0.6)] backdrop-blur-[2px]"
      onClick={onClose}
    >
      <div
        className="pf-fade-up flex flex-col"
        onClick={(e) => e.stopPropagation()}
        style={{
          width: u(470),
          height: u(330),
          borderRadius: u(12),
          background: "#fdfcfe",
          boxShadow: `0 ${u(6)} ${u(30)} rgba(170, 120, 210, 0.3)`,
          padding: u(14),
        }}
      >
        <div className="flex items-center">
          <span className="font-serif text-plum" style={{ fontSize: "var(--text-title)" }}>
            {t("Handoff Pack")}
          </span>
          <div
            className="ml-auto flex rounded-full bg-[#f3ecfa]"
            style={{ padding: u(2), gap: u(2) }}
          >
            {(
              [
                ["figma", "Figma prompt"],
                ["claude", "CLAUDE.md"],
              ] as const
            ).map(([key, label]) => (
              <button
                key={key}
                type="button"
                onClick={() => setTab(key)}
                className="rounded-full transition-colors"
                style={{
                  fontSize: "var(--text-small)",
                  padding: `${u(3)} ${u(9)}`,
                  background: tab === key ? "var(--color-pink)" : "transparent",
                  color: tab === key ? "var(--color-on-pink)" : "var(--color-mauve)",
                }}
              >
                {label}
              </button>
            ))}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="text-haze hover:text-plum"
            style={{ marginLeft: u(8) }}
            aria-label="Zamknij"
          >
            <X style={{ width: u(9), height: u(9) }} />
          </button>
        </div>
        <pre
          className="pf-scroll min-h-0 flex-1 overflow-auto whitespace-pre-wrap text-mauve"
          style={{
            marginTop: u(10),
            padding: u(10),
            borderRadius: u(7),
            background: "#f7f3fb",
            fontSize: "var(--text-small)",
            lineHeight: 1.55,
            fontFamily: "Montserrat, sans-serif",
          }}
        >
          {text}
        </pre>
        <div
          className="flex items-center"
          style={{ marginTop: u(9), gap: u(8) }}
        >
          <span
            className="min-w-0 flex-1 truncate text-haze"
            style={{ fontSize: "var(--text-small)" }}
            title={handoff.directory}
          >
            {t("Zapisano:")} {handoff.directory}
          </span>
          <button
            type="button"
            onClick={onRestart}
            className="flex items-center transition-colors hover:bg-[#e9dcf8]"
            style={{
              fontSize: "var(--text-body)",
              padding: `${u(5)} ${u(12)}`,
              borderRadius: u(6),
              gap: u(3),
              background: "#f3ecfa",
              color: "#573476",
            }}
          >
            <RotateCcw style={{ width: u(7), height: u(7) }} />
            {t("Nowy problem")}
          </button>
          <button
            type="button"
            onClick={copy}
            className="flex items-center text-on-pink"
            style={{
              fontSize: "var(--text-body)",
              padding: `${u(5)} ${u(12)}`,
              borderRadius: u(6),
              gap: u(3),
              background: "var(--color-pink)",
            }}
          >
            {copied ? (
              <Check style={{ width: u(7), height: u(7) }} />
            ) : (
              <Copy style={{ width: u(7), height: u(7) }} />
            )}
            {copied ? t("Skopiowano") : t("Kopiuj")}
          </button>
        </div>
      </div>
    </div>
  );
}
