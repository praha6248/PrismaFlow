import type { CSSProperties, ReactNode } from "react";
import { ProgressContent } from "../discover/BottomBar";
import { t } from "../i18n";

export const u = (value: number) => `calc(var(--u) * ${value})`;

export const SHADOW = `0 ${u(2)} ${u(10)} rgba(196, 160, 232, 0.28)`;

export function PageTitle({
  title,
  subtitle,
  top = 101,
  gap = 23,
}: {
  title: string;
  subtitle?: ReactNode;
  top?: number;
  gap?: number;
}) {
  return (
    <>
      <h2
        className="pf-fade pointer-events-none absolute inset-x-0 text-center font-serif font-normal text-plum"
        style={{ top: u(top), fontSize: "var(--text-title)", lineHeight: 1 }}
      >
        {title}
      </h2>
      {subtitle && (
        <p
          className="pf-fade pointer-events-none absolute left-1/2 -translate-x-1/2 truncate text-center"
          style={{
            top: u(top + gap),
            width: u(480),
            fontSize: "var(--text-body)",
            lineHeight: 1.2,
            color: "var(--color-muted)",
          }}
        >
          {subtitle}
        </p>
      )}
    </>
  );
}

export function Radio({
  checked,
  size = 10,
}: {
  checked: boolean;
  size?: number;
}) {
  return (
    <span
      className="flex shrink-0 items-center justify-center rounded-full transition-colors duration-200"
      style={{
        width: u(size),
        height: u(size),
        border: `${u(0.9)} solid ${checked ? "var(--color-pink)" : "#e4d6ec"}`,
        background: "#ffffff",
      }}
    >
      {checked && (
        <span
          className="pf-pop rounded-full"
          style={{
            width: u(size * 0.52),
            height: u(size * 0.52),
            background: "var(--color-pink)",
          }}
        />
      )}
    </span>
  );
}

interface CardProps {
  index: number;
  selected: boolean;
  onSelect?: () => void;
  children: ReactNode;
  style?: CSSProperties;
  disabled?: boolean;
  left?: number;
  top?: number;
  width?: number;
  height?: number;
  gap?: number;
}

export function Card({
  index,
  selected,
  onSelect,
  children,
  style,
  disabled,
  left = 41,
  top = 157,
  width = 177.5,
  height = 203,
  gap = 12.4,
}: CardProps) {
  return (
    <div
      role={onSelect ? "button" : undefined}
      tabIndex={onSelect && !disabled ? 0 : undefined}
      onClick={disabled ? undefined : onSelect}
      onKeyDown={(event) => {
        if (
          !disabled &&
          onSelect &&
          (event.key === "Enter" || event.key === " ")
        ) {
          event.preventDefault();
          onSelect();
        }
      }}
      className="pf-fade-up absolute overflow-hidden text-left outline-none transition-[box-shadow,transform] duration-200 focus-visible:ring-2 focus-visible:ring-[var(--color-pink)]"
      style={{
        left: u(left + index * (width + gap)),
        top: u(top),
        width: u(width),
        height: u(height),
        borderRadius: u(11),
        background: "#fdfcfe",
        boxShadow: selected ? `0 0 0 ${u(1.2)} var(--color-pink), ${SHADOW}` : SHADOW,
        cursor: onSelect && !disabled ? "pointer" : "default",
        animationDelay: `${index * 70}ms`,
        ...style,
      }}
    >
      {children}
    </div>
  );
}

export function SkeletonCards({ count = 3 }: { count?: number }) {
  return (
    <>
      {Array.from({ length: count }, (_, index) => (
        <Card key={index} index={index} selected={false}>
          <div
            style={{
              padding: u(12),
              animation: "pf-pulse 1.6s ease-in-out infinite",
              animationDelay: `${index * 160}ms`,
            }}
          >
            <div
              className="rounded-full bg-[#efe8f5]"
              style={{ width: u(42), height: u(5) }}
            />
            <div
              className="rounded-full bg-[#efe8f5]"
              style={{ width: u(140), height: u(10), marginTop: u(13) }}
            />
            <div
              className="rounded-full bg-[#efe8f5]"
              style={{ width: u(110), height: u(10), marginTop: u(5) }}
            />
            <div
              className="rounded-full bg-[#f4eff8]"
              style={{ width: u(150), height: u(5), marginTop: u(14) }}
            />
            <div
              className="rounded-full bg-[#f4eff8]"
              style={{ width: u(130), height: u(5), marginTop: u(4) }}
            />
            <div
              className="rounded bg-[#f4eff8]"
              style={{ width: u(153.5), height: u(52), marginTop: u(30) }}
            />
          </div>
        </Card>
      ))}
    </>
  );
}

export interface Frame {
  left: number;
  top: number;
  width: number;
  height: number;
}

const DEFINE_BAR: Frame = { left: 41, top: 379, width: 557, height: 42 };

const barStyle = (frame: Frame): CSSProperties => ({
  left: u(frame.left),
  top: u(frame.top),
  width: u(frame.width),
  height: u(frame.height),
  borderRadius: u(10),
  background: "#fdfcfe",
  boxShadow: SHADOW,
});

interface ChoiceBarProps {
  label?: string;
  value: ReactNode | null;
  placeholder: string;
  action?: string;
  disabled: boolean;
  busy?: boolean;
  onConfirm: () => void;
  frame?: Frame;
  button?: Frame;
  tone?: "pink" | "lavender";
}

export function ChoiceBar({
  label = t("TWÓJ WYBÓR"),
  value,
  placeholder,
  action = t("Zatwierdź wybór"),
  disabled,
  busy,
  onConfirm,
  frame = DEFINE_BAR,
  button = { left: 424.7, top: 8.2, width: 121.7, height: 25.6 },
  tone = "pink",
}: ChoiceBarProps) {
  const active =
    tone === "pink"
      ? { background: "var(--color-pink-button)", color: "var(--color-on-pink)", fontWeight: 600 }
      : { background: "#e6d8f7", color: "var(--color-ink)" };
  return (
    <div className="pf-fade-up absolute" style={barStyle(frame)}>
      <div
        className="absolute flex flex-col justify-center"
        style={{ left: u(14), top: 0, bottom: 0, width: u(400) }}
      >
        <span
          className="tracking-[0.12em] text-haze"
          style={{ fontSize: "var(--text-small)", lineHeight: 1 }}
        >
          {label}
        </span>
        <span
          key={value ? "value" : "placeholder"}
          className="pf-fade truncate"
          style={{
            marginTop: u(4.5),
            fontSize: "var(--text-body)",
            lineHeight: 1.15,
            color: value ? "#573476" : "var(--color-haze)",
          }}
        >
          {value ?? placeholder}
        </span>
      </div>
      <button
        type="button"
        onClick={onConfirm}
        disabled={disabled || busy}
        className="absolute transition-[background,color,transform] duration-200 enabled:hover:brightness-[0.98] enabled:active:scale-[0.98]"
        style={{
          left: u(button.left),
          top: u(button.top),
          width: u(button.width),
          height: u(button.height),
          borderRadius: u(8),
          fontSize: "var(--text-body)",
          background: disabled ? "#ece8f1" : active.background,
          color: disabled ? "#b3a9bd" : active.color,
          boxShadow: disabled
            ? "none"
            : `0 ${u(1.5)} ${u(6)} rgba(240, 110, 220, 0.35)`,
        }}
      >
        {busy ? t("Chwileczkę…") : action}
      </button>
    </div>
  );
}

export function BarProgress({
  title,
  text,
  stage,
  frame = DEFINE_BAR,
}: {
  title: string;
  text: string;
  stage: string;
  frame?: Frame;
}) {
  return (
    <div className="pf-fade-up absolute" style={barStyle(frame)}>
      <ProgressContent title={title} text={text} stage={stage} />
    </div>
  );
}

export function FooterNote({
  children,
  top = 431,
}: {
  children: ReactNode;
  top?: number;
}) {
  return (
    <p
      className="pf-fade pointer-events-none absolute inset-x-0 text-center text-haze"
      style={{ top: u(top), fontSize: "var(--text-small)", lineHeight: 1.2 }}
    >
      {children}
    </p>
  );
}

export function IconButton({
  onClick,
  title,
  children,
  left,
  top,
  width = 28.7,
  height = 20,
}: {
  onClick: () => void;
  title: string;
  children: ReactNode;
  left: number;
  top: number;
  width?: number;
  height?: number;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={title}
      aria-label={title}
      className="pf-fade absolute z-10 flex items-center justify-center text-mauve transition-transform hover:scale-[1.04] active:scale-[0.97]"
      style={{
        left: u(left),
        top: u(top),
        width: u(width),
        height: u(height),
        borderRadius: u(7),
        background: "#fdfcfe",
        boxShadow: SHADOW,
      }}
    >
      {children}
    </button>
  );
}
