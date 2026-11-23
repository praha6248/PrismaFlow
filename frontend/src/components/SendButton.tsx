import { t } from "../i18n";

interface Props {
  size: number;
  disabled?: boolean;
}

export function SendButton({ size, disabled }: Props) {
  return (
    <button
      type="submit"
      disabled={disabled}
      aria-label={t("Wyślij")}
      className="flex items-center justify-center rounded-full transition-[transform,filter] duration-200 hover:brightness-105 active:scale-95 disabled:cursor-default"
      style={{
        width: `calc(var(--u) * ${size})`,
        height: `calc(var(--u) * ${size})`,
        background: "#f783e9",
        boxShadow:
          "0 0 0 calc(var(--u) * 1) #ffffff, 0 calc(var(--u) * 1) calc(var(--u) * 3) rgba(240, 110, 220, 0.35)",
      }}
    >
      <svg
        viewBox="0 0 20 20"
        style={{
          width: `calc(var(--u) * ${size * 0.62})`,
          height: `calc(var(--u) * ${size * 0.62})`,
        }}
      >
        <path
          d="M2.6 2.8 L18 10 L2.6 17.2 L6.6 10 Z"
          fill="#ffffff"
          stroke="#ffffff"
          strokeWidth="1.2"
          strokeLinejoin="round"
        />
      </svg>
    </button>
  );
}
