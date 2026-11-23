import { useState, type FormEvent, type ReactNode } from "react";
import { SendButton } from "../components/SendButton";
import { t } from "../i18n";

export const STAGE_TEXT: Record<string, string> = {
  queued: t("Przygotowuję rozbudowę"),
  suggestions: t("Sprawdzam podpowiedzi Google"),
  thinking: t("Model analizuje mapę"),
  placing: t("Dodaję kolejne węzły"),
  evidence: t("Zbieram dowody z sieci"),
  screening: t("Odrzucam dyskusje nie na temat"),
  translating: t("Tłumaczę wyniki z angielskiego"),
  trends: t("Sprawdzam trendy Google"),
  scoring: t("Porównuję zebrane sygnały"),
  done: t("Gotowe"),
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
        boxShadow:
          "0 calc(var(--u) * 2) calc(var(--u) * 10) rgba(196, 160, 232, 0.28)",
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
            placeholder={t("Wpisz skojarzenie…")}
            maxLength={48}
            autoFocus
            className="h-full w-full bg-transparent text-mauve outline-none placeholder:text-haze"
            style={{
              paddingLeft: "calc(var(--u) * 9)",
              paddingRight: "calc(var(--u) * 30)",
              fontSize: "var(--text-body)",
            }}
          />
          <div
            className="absolute"
            style={{ right: "calc(var(--u) * 2)", top: "calc(var(--u) * 2)" }}
          >
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
            background: "var(--color-pink-soft)",
            color: "#853c77",
            fontSize: "var(--text-body)",
            boxShadow:
              "0 calc(var(--u) * 1) calc(var(--u) * 4) rgba(237, 150, 225, 0.25)",
          }}
        >
          {t("Gotowe")}
        </button>
      </form>
    </Panel>
  );
}

export function ExpandProgress({ stage }: { stage: string }) {
  return (
    <Panel>
      <ProgressContent
        title={t("Rozbudowuję mapę…")}
        text={STAGE_TEXT[stage] ?? STAGE_TEXT.placing}
        stage={stage}
      />
    </Panel>
  );
}

interface ProgressContentProps {
  title: string;
  text: string;
  stage: string;
}

export function ProgressContent({ title, text, stage }: ProgressContentProps) {
  return (
    <>
      <div
        className="absolute flex items-center"
        style={{
          left: "calc(var(--u) * 10)",
          right: "calc(var(--u) * 12)",
          top: "calc(var(--u) * 9)",
        }}
      >
        <span
          className="rounded-full"
          style={{
            width: "calc(var(--u) * 4.6)",
            height: "calc(var(--u) * 4.6)",
            background: "var(--color-pink)",
            animation: "pf-pulse 1.4s ease-in-out infinite",
          }}
        />
        <span
          className="text-mauve"
          style={{
            marginLeft: "calc(var(--u) * 6)",
            fontSize: "var(--text-body)",
          }}
        >
          {title}
        </span>
        <span
          key={stage}
          className="pf-fade ml-auto text-haze"
          style={{ fontSize: "var(--text-body)" }}
        >
          {text}
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
          background: "#fbe3f8",
        }}
      >
        <div
          className="absolute top-0 h-full"
          style={{
            width: "33%",
            borderRadius: "calc(var(--u) * 2)",
            background: "linear-gradient(90deg, #fbb3f2 0%, var(--color-pink) 100%)",
            animation: "pf-slide 1.9s cubic-bezier(0.45, 0, 0.35, 1) infinite",
          }}
        />
      </div>
    </>
  );
}
