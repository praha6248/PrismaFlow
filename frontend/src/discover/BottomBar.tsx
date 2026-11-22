import { useState, type FormEvent, type ReactNode } from "react";
import { SendButton } from "../components/SendButton";

export const STAGE_TEXT: Record<string, string> = {
  queued: "Przygotowuję rozbudowę",
  suggestions: "Sprawdzam podpowiedzi Google",
  thinking: "Model analizuje mapę",
  placing: "Dodaję kolejne węzły",
  evidence: "Zbieram dowody z sieci",
  trends: "Sprawdzam trendy Google",
  scoring: "Liczę popyt",
  done: "Gotowe",
};

function Panel({ children }: { children: ReactNode }) {
  return (
    <div
      className="pf-fade-up absolute left-1/2 -translate-x-1/2"
      style={{
        bottom: "calc(var(--u) * 20)",
        width: "calc(var(--u) * 373)",
        height: "calc(var(--u) * 44)",
        borderRadius: "calc(var(--u) * 12)",
        background: "#fdfcfe",
        boxShadow: "0 calc(var(--u) * 2) calc(var(--u) * 10) rgba(196, 160, 232, 0.28)",
      }}
    >
      {children}
    </div>
  );
}

interface ComposerProps {
  onAdd: (label: string) => Promise<void> | void;
  onDone: () => void;
  disabled?: boolean;
}

export function ComposerBar({ onAdd, onDone, disabled }: ComposerProps) {
  const [value, setValue] = useState("");

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const label = value.trim();
    if (!label || disabled) return;
    setValue("");
    await onAdd(label);
  };

  return (
    <Panel>
      <form onSubmit={submit} className="absolute inset-0">
        <div
          className="absolute flex items-center"
          style={{
            left: "calc(var(--u) * 10)",
            top: "calc(var(--u) * 10)",
            width: "calc(var(--u) * 249)",
            height: "calc(var(--u) * 24)",
            borderRadius: "calc(var(--u) * 12)",
            background: "#f8f4fc",
          }}
        >
          <input
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder="Wpisz skojarzenie..."
            maxLength={48}
            autoFocus
            className="h-full w-full bg-transparent text-mauve outline-none placeholder:text-[#9b8fa6]"
            style={{
              paddingLeft: "calc(var(--u) * 9)",
              paddingRight: "calc(var(--u) * 30)",
              fontSize: "calc(var(--u) * 7.4)",
            }}
          />
          <div className="absolute" style={{ right: "calc(var(--u) * 2)", top: "calc(var(--u) * 2)" }}>
            <SendButton size={20} disabled={!value.trim()} />
          </div>
        </div>
        <button
          type="button"
          onClick={onDone}
          disabled={disabled}
          className="absolute transition-[filter,transform] duration-200 hover:brightness-[0.98] active:scale-[0.98] disabled:opacity-60"
          style={{
            right: "calc(var(--u) * 9)",
            top: "calc(var(--u) * 10)",
            width: "calc(var(--u) * 96)",
            height: "calc(var(--u) * 24)",
            borderRadius: "calc(var(--u) * 9)",
            background: "#fed3f9",
            color: "#853c77",
            fontSize: "calc(var(--u) * 9.6)",
            boxShadow: "0 calc(var(--u) * 1) calc(var(--u) * 4) rgba(237, 150, 225, 0.25)",
          }}
        >
          Gotowe
        </button>
      </form>
    </Panel>
  );
}

export function ExpandProgress({ stage }: { stage: string }) {
  return (
    <Panel>
      <div
        className="absolute flex items-center"
        style={{ left: "calc(var(--u) * 10)", right: "calc(var(--u) * 12)", top: "calc(var(--u) * 9)" }}
      >
        <span
          className="rounded-full"
          style={{
            width: "calc(var(--u) * 4.6)",
            height: "calc(var(--u) * 4.6)",
            background: "#aa55c3",
            animation: "pf-pulse 1.4s ease-in-out infinite",
          }}
        />
        <span className="text-mauve" style={{ marginLeft: "calc(var(--u) * 6)", fontSize: "calc(var(--u) * 8.3)" }}>
          Rozbudowuję mapę...
        </span>
        <span key={stage} className="pf-fade ml-auto text-haze" style={{ fontSize: "calc(var(--u) * 6.8)" }}>
          {STAGE_TEXT[stage] ?? STAGE_TEXT.placing}
        </span>
      </div>
      <div
        className="absolute overflow-hidden"
        style={{
          left: "calc(var(--u) * 10)",
          right: "calc(var(--u) * 10)",
          top: "calc(var(--u) * 32)",
          height: "calc(var(--u) * 2.6)",
          borderRadius: "calc(var(--u) * 2)",
          background: "#eee5f5",
        }}
      >
        <div
          className="absolute top-0 h-full"
          style={{
            width: "33%",
            borderRadius: "calc(var(--u) * 2)",
            background: "linear-gradient(90deg, #b799e5 0%, #d49ce1 60%, #e9a0df 100%)",
            animation: "pf-slide 1.9s cubic-bezier(0.45, 0, 0.35, 1) infinite",
          }}
        />
      </div>
    </Panel>
  );
}
