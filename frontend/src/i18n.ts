import en from "./locales/en.json";

export type Locale = "pl" | "en";

const CATALOGS: Record<Locale, Record<string, string>> = { pl: {}, en };
const STORAGE_KEY = "pf-locale";

function detect(): Locale {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved === "pl" || saved === "en") return saved;
  } catch {
    return navigator.language.toLowerCase().startsWith("pl") ? "pl" : "en";
  }
  return navigator.language.toLowerCase().startsWith("pl") ? "pl" : "en";
}

export const locale: Locale = detect();
document.documentElement.lang = locale;

export function setLocale(next: Locale): void {
  try {
    localStorage.setItem(STORAGE_KEY, next);
  } catch {
    return;
  }
  window.location.reload();
}

function fill(text: string, vars?: Record<string, string | number>): string {
  if (!vars) return text;
  return text.replace(/\{(\w+)\}/g, (match, name: string) =>
    name in vars ? String(vars[name]) : match,
  );
}

export function t(
  source: string,
  vars?: Record<string, string | number>,
): string {
  return fill(CATALOGS[locale][source] ?? source, vars);
}

export function plural(
  count: number,
  one: string,
  few: string,
  many: string,
): string {
  if (locale === "en") {
    const forms = (
      CATALOGS.en[`${one}|${few}|${many}`] ?? `${one}|${many}`
    ).split("|");
    return count === 1 ? forms[0] : forms[forms.length - 1];
  }
  if (count === 1) return one;
  const last = count % 10;
  const lastTwo = count % 100;
  return last >= 2 && last <= 4 && (lastTwo < 12 || lastTwo > 14) ? few : many;
}

export function number(value: number, digits = 2): string {
  const fixed = value.toFixed(digits);
  return locale === "pl" ? fixed.replace(".", ",") : fixed;
}
