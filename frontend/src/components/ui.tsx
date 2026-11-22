import type { CSSProperties, ReactNode } from "react";
import { ProgressContent } from "../discover/BottomBar";

export const u = (value: number) => `calc(var(--u) * ${value})`;

export const SHADOW = `0 ${u(2)} ${u(10)} rgba(196, 160, 232, 0.28)`;

export function PageTitle({ title, subtitle, top = 114 }: { title: string; subtitle?: ReactNode; top?: number }) {
  return (
    <>
      <h2
        className="pf-fade pointer-events-none absolute inset-x-0 text-center font-serif font-normal text-plum"
        style={{ top: u(top), fontSize: u(18.8), lineHeight: 1 }}
      >
        {title}
      </h2>
      {subtitle && (
        <p
          className="pf-fade pointer-events-none absolute left-1/2 -translate-x-1/2 truncate text-center"
          style={{ top: u(top + 20), width: u(480), fontSize: u(7.5), lineHeight: 1.2, color: "#7c6d88" }}
        >
          {subtitle}
        </p>
      )}
    </>
  );
}

export function Radio({ checked, size = 10 }: { checked: boolean; size?: number }) {
  return (
    <span
      className="flex shrink-0 items-center justify-center rounded-full transition-colors duration-200"
      style={{
        width: u(size),
        height: u(size),
        border: `${u(0.9)} solid ${checked ? "#cfa0e4" : "#d9cfe2"}`,
        background: "#ffffff",
      }}
    >
      {checked && <span className="pf-pop rounded-full" style={{ width: u(size * 0.52), height: u(size * 0.52), background: "linear-gradient(135deg, #c8a5e8 0%, #dca0e2 100%)" }} />}
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
        if (!disabled && onSelect && (event.key === "Enter" || event.key === " ")) {
          event.preventDefault();
          onSelect();
        }
      }}
      className="pf-fade-up absolute overflow-hidden text-left outline-none transition-[box-shadow,transform] duration-200 focus-visible:ring-2 focus-visible:ring-[#f6a6ec]"
      style={{
        left: u(left + index * (width + gap)),
        top: u(top),
        width: u(width),
        height: u(height),
        borderRadius: u(11),
        background: "#fdfcfe",
        boxShadow: selected ? `0 0 0 ${u(1.2)} #dcb2ea, ${SHADOW}` : SHADOW,
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
          <div style={{ padding: u(12), animation: "pf-pulse 1.6s ease-in-out infinite", animationDelay: `${index * 160}ms` }}>
            <div className="rounded-full bg-[#efe8f5]" style={{ width: u(42), height: u(5) }} />
            <div className="rounded-full bg-[#efe8f5]" style={{ width: u(140), height: u(10), marginTop: u(13) }} />
            <div className="rounded-full bg-[#efe8f5]" style={{ width: u(110), height: u(10), marginTop: u(5) }} />
            <div className="rounded-full bg-[#f4eff8]" style={{ width: u(150), height: u(5), marginTop: u(14) }} />
            <div className="rounded-full bg-[#f4eff8]" style={{ width: u(130), height: u(5), marginTop: u(4) }} />
            <div className="rounded bg-[#f4eff8]" style={{ width: u(153.5), height: u(52), marginTop: u(30) }} />
          </div>
        </Card>
      ))}
    </>
  );
}

const BAR_STYLE: CSSProperties = {
  left: u(41),
  top: u(379),
  width: u(557),
  height: u(42),
  borderRadius: u(10),
  background: "#fdfcfe",
  boxShadow: SHADOW,
};

interface ChoiceBarProps {
  label?: string;
  value: ReactNode | null;
  placeholder: string;
  action?: string;
  disabled: boolean;
  busy?: boolean;
  onConfirm: () => void;
}

export function ChoiceBar({ label = "TWÓJ WYBÓR", value, placeholder, action = "Zatwierdź wybór", disabled, busy, onConfirm }: ChoiceBarProps) {
  return (
    <div className="pf-fade-up absolute" style={BAR_STYLE}>
      <div className="absolute flex flex-col justify-center" style={{ left: u(14), top: 0, bottom: 0, width: u(400) }}>
        <span className="tracking-[0.12em] text-haze" style={{ fontSize: u(5.4), lineHeight: 1 }}>
          {label}
        </span>
        <span
          key={value ? "value" : "placeholder"}
          className="pf-fade truncate"
          style={{ marginTop: u(4.5), fontSize: u(8), lineHeight: 1.15, color: value ? "#573476" : "#9b8fa6" }}
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
          left: u(424.7),
          top: u(8.2),
          width: u(121.7),
          height: u(25.6),
          borderRadius: u(8),
          fontSize: u(8),
          background: disabled ? "#ece8f1" : "#fed3f9",
          color: disabled ? "#b3a9bd" : "#853c77",
          boxShadow: disabled ? "none" : `0 ${u(1)} ${u(4)} rgba(237, 150, 225, 0.25)`,
        }}
      >
        {busy ? "Chwileczkę..." : action}
      </button>
    </div>
  );
}

export function BarProgress({ title, text, stage }: { title: string; text: string; stage: string }) {
  return (
    <div className="pf-fade-up absolute" style={BAR_STYLE}>
      <ProgressContent title={title} text={text} stage={stage} />
    </div>
  );
}

export function FooterNote({ children, top = 431 }: { children: ReactNode; top?: number }) {
  return (
    <p
      className="pf-fade pointer-events-none absolute inset-x-0 text-center text-haze"
      style={{ top: u(top), fontSize: u(4.8), lineHeight: 1.2 }}
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
      style={{ left: u(left), top: u(top), width: u(width), height: u(height), borderRadius: u(7), background: "#fdfcfe", boxShadow: SHADOW }}
    >
      {children}
    </button>
  );
}
