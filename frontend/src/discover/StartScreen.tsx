import { useState, type FormEvent } from "react";
import diamonds from "../assets/diamonds.png";
import { SendButton } from "../components/SendButton";
import { t } from "../i18n";

interface Props {
  leaving: boolean;
  busy: boolean;
  onSubmit: (seed: string) => void;
}

export function StartScreen({ leaving, busy, onSubmit }: Props) {
  const [value, setValue] = useState("");

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const seed = value.trim();
    if (seed && !busy) onSubmit(seed);
  };

  const offset = "calc((100% - var(--u) * 448) / 2)";

  return (
    <div className={`absolute inset-0 ${leaving ? "pf-leave" : "pf-fade"}`}>
      <img
        src={diamonds}
        alt=""
        draggable={false}
        className="absolute left-1/2"
        style={{
          top: `calc(${offset} + var(--u) * 139)`,
          width: "calc(var(--u) * 213.5)",
          transform: "translateX(calc(-50% - var(--u) * 5))",
        }}
      />
      <h1
        className="absolute inset-x-0 text-center font-serif font-normal text-ink"
        style={{
          top: `calc(${offset} + var(--u) * 248.5)`,
          fontSize: "var(--text-title)",
          lineHeight: 1,
        }}
      >
        {t("Co chcesz")}{" "}
        <span style={{ color: "var(--color-pink-deep)" }}>{t("stworzyć?")}</span>
      </h1>
      <form
        onSubmit={submit}
        className="absolute left-1/2 flex -translate-x-1/2 items-center bg-white"
        style={{
          top: `calc(${offset} + var(--u) * 320)`,
          width: "calc(var(--u) * 241)",
          height: "calc(var(--u) * 22)",
          borderRadius: "calc(var(--u) * 11)",
          boxShadow:
            "0 calc(var(--u) * 2) calc(var(--u) * 6) rgba(170, 140, 205, 0.28)",
        }}
      >
        <input
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder={t("Wpisz myśl przewodnią…")}
          maxLength={80}
          autoFocus
          className="h-full w-full bg-transparent text-mauve outline-none placeholder:text-haze"
          style={{
            paddingLeft: "calc(var(--u) * 7)",
            paddingRight: "calc(var(--u) * 28)",
            fontSize: "var(--text-body)",
          }}
        />
        <div
          className="absolute"
          style={{ right: "calc(var(--u) * 1.5)", top: "calc(var(--u) * 1)" }}
        >
          <SendButton size={20} disabled={!value.trim() || busy} />
        </div>
      </form>
    </div>
  );
}
