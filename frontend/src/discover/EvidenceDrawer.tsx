import {
  ExternalLink,
  Search,
  Sparkles,
  Star,
  Trash2,
  TrendingDown,
  TrendingUp,
  X,
} from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "../api";
import type { Evidence, MapNode } from "../types";
import { styleFor } from "./kinds";
import { locale, plural, t } from "../i18n";

interface Props {
  node: MapNode;
  busy: boolean;
  onClose: () => void;
  onToggleStar: (node: MapNode) => void;
  onExpand: (node: MapNode) => void;
  onDelete: (node: MapNode) => void;
}

function Sparkline({ series }: { series: number[] }) {
  if (series.length < 2) return null;
  const max = Math.max(1, ...series);
  const w = 100;
  const h = 26;
  const step = w / (series.length - 1);
  const points = series.map(
    (v, i) =>
      `${(i * step).toFixed(2)},${(h - (v / max) * (h - 2) - 1).toFixed(2)}`,
  );
  const area = `0,${h} ${points.join(" ")} ${w},${h}`;
  return (
    <svg
      viewBox={`0 0 ${w} ${h}`}
      preserveAspectRatio="none"
      className="block w-full"
      style={{ height: "calc(var(--u) * 26)" }}
    >
      <defs>
        <linearGradient id="pf-spark" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor="#e59fe0" stopOpacity="0.45" />
          <stop offset="100%" stopColor="#e59fe0" stopOpacity="0" />
        </linearGradient>
      </defs>
      <polygon points={area} fill="url(#pf-spark)" />
      <polyline
        points={points.join(" ")}
        fill="none"
        stroke="#c77bdc"
        strokeWidth="1.2"
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  );
}

function SectionTitle({ children }: { children: string }) {
  return (
    <div
      className="uppercase text-haze"
      style={{
        fontSize: "var(--text-small)",
        letterSpacing: "0.08em",
        marginBottom: "calc(var(--u) * 4)",
      }}
    >
      {children}
    </div>
  );
}

export function EvidenceDrawer({
  node,
  busy,
  onClose,
  onToggleStar,
  onExpand,
  onDelete,
}: Props) {
  const [evidence, setEvidence] = useState<Evidence | null>(null);
  const [error, setError] = useState<string | null>(null);
  const style = styleFor(node);

  useEffect(() => {
    let cancelled = false;
    setEvidence(null);
    setError(null);
    api
      .evidence(node.id)
      .then((data) => !cancelled && setEvidence(data))
      .catch((e: Error) => !cancelled && setError(e.message));
    return () => {
      cancelled = true;
    };
  }, [node.id, node.enriched_at]);

  const growth = evidence?.trend.growth ?? null;
  const enriched = node.enriched_at !== null;

  return (
    <aside
      className="pf-fade-up absolute z-30 flex flex-col overflow-hidden"
      style={{
        right: "calc(var(--u) * 14)",
        top: "calc(var(--u) * 108)",
        bottom: "calc(var(--u) * 16)",
        width: "calc(var(--u) * 168)",
        borderRadius: "calc(var(--u) * 12)",
        background: "rgba(255, 255, 255, 0.86)",
        backdropFilter: "blur(10px)",
        boxShadow:
          "0 calc(var(--u) * 4) calc(var(--u) * 18) rgba(180, 140, 225, 0.28)",
        fontSize: "var(--text-body)",
      }}
    >
      <header
        style={{
          padding: "calc(var(--u) * 12) calc(var(--u) * 12) calc(var(--u) * 8)",
        }}
      >
        <div className="flex items-start">
          <span
            className="rounded-full font-medium"
            style={{
              background: style.badgeBg,
              color: style.badgeText,
              fontSize: "var(--text-small)",
              padding: "calc(var(--u) * 1.5) calc(var(--u) * 6)",
            }}
          >
            {node.is_root
              ? t("nisza")
              : node.kind
                ? style.label
                : t("bez kategorii")}
          </span>
          <button
            type="button"
            onClick={onClose}
            className="ml-auto text-haze hover:text-mauve"
            aria-label={t("Zamknij")}
          >
            <X
              style={{
                width: "calc(var(--u) * 9)",
                height: "calc(var(--u) * 9)",
              }}
            />
          </button>
        </div>
        <h2
          className="font-serif text-plum"
          style={{
            fontSize: "var(--text-title)",
            lineHeight: 1.1,
            marginTop: "calc(var(--u) * 6)",
          }}
        >
          {node.label}
        </h2>
        <button
          type="button"
          onClick={() => onToggleStar(node)}
          className="flex items-center rounded-full transition-colors"
          style={{
            marginTop: "calc(var(--u) * 7)",
            padding: "calc(var(--u) * 3) calc(var(--u) * 8)",
            gap: "calc(var(--u) * 4)",
            background: node.starred ? "var(--color-pink-soft)" : "#f8f4fc",
            color: node.starred ? "#853c77" : "var(--color-mauve)",
          }}
        >
          <Star
            style={{
              width: "calc(var(--u) * 7.5)",
              height: "calc(var(--u) * 7.5)",
            }}
            color="var(--color-pink)"
            fill={node.starred ? "var(--color-pink)" : "transparent"}
          />
          {node.starred ? t("Wybrany do analizy") : t("Zaznacz do analizy")}
        </button>
      </header>

      <div
        className="min-h-0 flex-1 overflow-y-auto"
        style={{ padding: "0 calc(var(--u) * 12) calc(var(--u) * 10)" }}
      >
        {error && <p className="text-error">{error}</p>}
        {!evidence && !error && (
          <p className="text-haze">{t("Wczytuję dowody…")}</p>
        )}
        {evidence && !enriched && (
          <p className="text-haze" style={{ lineHeight: 1.5 }}>
            {t(
              "Ten węzeł nie ma jeszcze dowodów. Rozwiń go przez AI, aby pobrać podpowiedzi Google, trendy i wątki.",
            )}
          </p>
        )}
        {evidence && enriched && (
          <>
            <section style={{ marginTop: "calc(var(--u) * 4)" }}>
              <SectionTitle>{`Google Trends · ${t("12 mies.")}`}</SectionTitle>
              {evidence.trend.series.length > 1 ? (
                <>
                  {evidence.trend.primary && (
                    <p>{evidence.trend.primary === "pl" ? t("Polska") : t("Angielski · świat")} · {evidence.trend.markets?.[evidence.trend.primary]?.query}</p>
                  )}
                  <Sparkline series={evidence.trend.series} />
                  <div
                    className="flex items-center text-mauve"
                    style={{
                      gap: "calc(var(--u) * 3)",
                      marginTop: "calc(var(--u) * 3)",
                    }}
                  >
                    {growth !== null && growth >= 0 ? (
                      <TrendingUp
                        style={{ width: "calc(var(--u) * 8)" }}
                        color="#9e4eef"
                      />
                    ) : (
                      <TrendingDown
                        style={{ width: "calc(var(--u) * 8)" }}
                        color="#fc4aa1"
                      />
                    )}
                    <span className="font-medium">
                      {growth === null
                        ? t("brak danych")
                        : `${growth >= 0 ? "+" : ""}${Math.round(growth * 100)}%`}
                    </span>
                    <span className="text-haze">{t("3 mies. vs 9 mies.")}</span>
                  </div>
                  {evidence.trend.anchor_ratio !== null &&
                    evidence.trend.anchor && (
                      <div
                        className="text-haze"
                        style={{
                          marginTop: "calc(var(--u) * 2)",
                          fontSize: "var(--text-small)",
                        }}
                      >
                        {t("{ratio}× zainteresowania hasłem „{anchor}”", {
                          ratio: evidence.trend.anchor_ratio.toFixed(2),
                          anchor: evidence.trend.anchor,
                        })}
                      </div>
                    )}
                </>
              ) : (
                <p className="text-haze">
                  {t("Google Trends nie zwrócił danych dla tego hasła.")}
                </p>
              )}
              {Object.entries(evidence.trend.markets ?? {}).filter(([code]) => code !== evidence.trend.primary).map(([code, market]) => (
                <div key={code} className="mt-3">
                  <p>{code === "pl" ? t("Polska") : t("Angielski · świat")} · {market.query}</p>
                  <Sparkline series={market.series} />
                  {market.growth != null && <span>{Math.round(market.growth * 100)}% · {t("3 mies. vs 9 mies.")}</span>}
                </div>
              ))}
            </section>

            <section style={{ marginTop: "calc(var(--u) * 11)" }}>
              <SectionTitle>{t("Google podpowiada")}</SectionTitle>
              {evidence.suggestions.length ? (
                <ul
                  className="flex flex-wrap"
                  style={{ gap: "calc(var(--u) * 3)" }}
                >
                  {evidence.suggestions.slice(0, 8).map((item) => (
                    <li
                      key={item.id}
                      className="flex items-center rounded-full text-mauve"
                      style={{
                        background: "#f8f4fc",
                        padding: "calc(var(--u) * 1.5) calc(var(--u) * 5)",
                        gap: "calc(var(--u) * 2.5)",
                        fontSize: "var(--text-small)",
                      }}
                    >
                      <Search
                        style={{ width: "calc(var(--u) * 5.5)" }}
                        color="#aa9fb2"
                      />
                      <span
                        title={
                          item.meta.original
                            ? `${t("Oryginał:")} ${String(item.meta.original)}`
                            : undefined
                        }
                      >
                        {item.title}
                      </span>
                      {item.meta.lang === "en" && <EnTag />}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-haze">{t("Brak podpowiedzi.")}</p>
              )}
            </section>

            <section style={{ marginTop: "calc(var(--u) * 11)" }}>
              <SectionTitle>{t("Dyskusje")}</SectionTitle>
              {evidence.quotes.length ? (
                <ul
                  className="flex flex-col"
                  style={{ gap: "calc(var(--u) * 6)" }}
                >
                  {evidence.quotes.slice(0, 5).map((quote) => (
                    <li
                      key={quote.id}
                      className="border-l-2 border-[#f3c4ee]"
                      style={{ paddingLeft: "calc(var(--u) * 5)" }}
                    >
                      <p
                        className="text-mauve"
                        style={{ lineHeight: 1.4 }}
                        title={
                          quote.meta.original
                            ? `${t("Oryginał:")} ${String(quote.meta.original)}`
                            : undefined
                        }
                      >
                        {locale === "en" ? "“" : "„"}{quote.title}”{quote.meta.lang === "en" && <EnTag />}
                        {quote.meta.translation_unavailable === true && <small> · {t("Oryginał")}</small>}
                      </p>
                      <a
                        href={quote.url ?? undefined}
                        target="_blank"
                        rel="noreferrer"
                        className="mt-0.5 inline-flex items-center text-haze hover:text-mauve"
                        style={{
                          gap: "calc(var(--u) * 2)",
                          fontSize: "var(--text-small)",
                        }}
                      >
                        {sourceLabel(quote.meta)} ·{" "}
                        {String(quote.meta.comments ?? 0)}{" "}
                        {quote.meta.platform === "stackexchange"
                          ? plural(Number(quote.meta.comments ?? 0), "odpowiedź", "odpowiedzi", "odpowiedzi")
                          : plural(Number(quote.meta.comments ?? 0), "komentarz", "komentarze", "komentarzy")}
                        <ExternalLink style={{ width: "calc(var(--u) * 5)" }} />
                      </a>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-haze" style={{ lineHeight: 1.5 }}>
                  {t(
                    "Brak pasujących dyskusji na Stack Exchange i Lemmy dla tego hasła.",
                  )}
                </p>
              )}
            </section>
          </>
        )}
      </div>

      <footer
        className="flex"
        style={{
          gap: "calc(var(--u) * 5)",
          padding: "calc(var(--u) * 8) calc(var(--u) * 12) calc(var(--u) * 11)",
        }}
      >
        <button
          type="button"
          onClick={() => onExpand(node)}
          disabled={busy}
          className="flex flex-1 items-center justify-center transition-[filter] hover:brightness-[0.98] disabled:opacity-50"
          style={{
            height: "calc(var(--u) * 20)",
            borderRadius: "calc(var(--u) * 8)",
            background: "var(--color-pink-soft)",
            color: "#853c77",
            gap: "calc(var(--u) * 3)",
          }}
        >
          <Sparkles style={{ width: "calc(var(--u) * 7.5)" }} />
          {t("Rozwiń przez AI")}
        </button>
        {!node.is_root && (
          <button
            type="button"
            onClick={() => onDelete(node)}
            disabled={busy}
            aria-label={t("Usuń węzeł")}
            title={t("Usuń węzeł")}
            className="flex items-center justify-center text-haze transition-colors hover:text-error disabled:opacity-50"
            style={{
              width: "calc(var(--u) * 20)",
              height: "calc(var(--u) * 20)",
              borderRadius: "calc(var(--u) * 8)",
              background: "#f8f4fc",
            }}
          >
            <Trash2 style={{ width: "calc(var(--u) * 7.5)" }} />
          </button>
        )}
      </footer>
    </aside>
  );
}

function EnTag() {
  return (
    <span
      className="ml-1 inline-block rounded align-middle text-haze"
      style={{
        fontSize: "var(--text-small)",
        padding: "0 calc(var(--u) * 2)",
        border: "1px solid #e4d6ec",
        lineHeight: 1.5,
      }}
      title={t("Przetłumaczono z angielskiego")}
    >
      EN
    </span>
  );
}

function sourceLabel(meta: Record<string, unknown>): string {
  const place = String(meta.place ?? meta.subreddit ?? "");
  if (meta.platform === "stackexchange") return `Stack Exchange · ${place}`;
  if (meta.platform === "lemmy") return `Lemmy · !${place}`;
  return `Reddit · r/${place}`;
}
