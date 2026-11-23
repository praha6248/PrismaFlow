import type { MapNode, NodeKind } from "../types";
import { t } from "../i18n";

export interface KindStyle {
  label: string;
  gradient: string;
  badgeBg: string;
  badgeText: string;
}

export const KIND_STYLES: Record<NodeKind, KindStyle> = {
  niche: {
    label: t("nisza"),
    gradient: "linear-gradient(140deg, #ee8bdc 0%, #e48ce6 45%, #d58ff1 100%)",
    badgeBg: "#fbd7f5",
    badgeText: "#aa2c99",
  },
  idea: {
    label: t("pomysł"),
    gradient: "linear-gradient(150deg, #b98cee 0%, #a88bee 50%, #958aed 100%)",
    badgeBg: "#e5d3f8",
    badgeText: "#821bea",
  },
  target_group: {
    label: t("grupa docelowa"),
    gradient: "linear-gradient(140deg, #8fc1ef 0%, #b0c6f6 50%, #d3ccfb 100%)",
    badgeBg: "#d2e5f9",
    badgeText: "#1a66b3",
  },
  pain_point: {
    label: t("problem"),
    gradient: "linear-gradient(150deg, #f167e2 0%, #f34fbd 50%, #f6449a 100%)",
    badgeBg: "#ffd0ec",
    badgeText: "#be035f",
  },
  competitor: {
    label: t("konkurencja"),
    gradient: "linear-gradient(145deg, #fdb68a 0%, #fb9c98 55%, #f68aa9 100%)",
    badgeBg: "#ffe0d0",
    badgeText: "#ab4a19",
  },
};

export function styleFor(node: Pick<MapNode, "kind" | "is_root">): KindStyle {
  if (node.is_root) return KIND_STYLES.niche;
  return KIND_STYLES[node.kind ?? "idea"];
}

export const ROOT_DIAMETER = 84;

export function relativeScores(nodes: MapNode[]): MapNode[] {
  const scored = nodes.filter((n) => !n.is_root && n.enriched_at);
  if (scored.length < 2) return nodes;
  const low = Math.min(...scored.map((n) => n.score));
  const high = Math.max(...scored.map((n) => n.score));
  if (high - low < 0.02) return nodes.map((n) => (n.is_root || !n.enriched_at ? n : { ...n, score: 0.5 }));
  return nodes.map((n) =>
    n.is_root || !n.enriched_at ? n : { ...n, score: (n.score - low) / (high - low) },
  );
}

const CHAR_WIDTH = 0.56;
const LINE_HEIGHT = 1.12;
const fits = new Map<string, number>();

function baseDiameter(node: Pick<MapNode, "is_root" | "score" | "enriched_at">): number {
  if (node.is_root) return ROOT_DIAMETER;
  if (!node.enriched_at) return 60;
  const score = Math.max(0, Math.min(1, node.score));
  return Math.round(56 + score * 42);
}

function wrappedLines(words: string[], font: number, width: number): number {
  const perLine = Math.max(1, Math.floor(width / (font * CHAR_WIDTH)));
  let lines = 1;
  let used = 0;
  for (const word of words) {
    const length = word.length;
    if (used === 0) used = length;
    else if (used + 1 + length <= perLine) used += 1 + length;
    else {
      lines += 1;
      used = length;
    }
  }
  return lines;
}

function fitFont(label: string, diameter: number, largest: number): number {
  const key = `${label}|${diameter}|${largest}`;
  const cached = fits.get(key);
  if (cached !== undefined) return cached;
  const words = label.trim().split(/\s+/).filter(Boolean);
  const longest = Math.max(1, ...words.map((w) => w.length));
  const box = diameter * 0.72;
  let font = largest;
  while (font > 6) {
    const lines = wrappedLines(words, font, box);
    if (longest * font * CHAR_WIDTH <= box && lines * font * LINE_HEIGHT <= box) break;
    font -= 0.25;
  }
  fits.set(key, font);
  return font;
}

function largestFont(diameter: number, isRoot: boolean, label: string): number {
  if (isRoot) return Math.min(20, diameter * 0.24);
  return label.trim().includes(" ") ? diameter * 0.18 : diameter * 0.235;
}

export function diameterFor(
  node: Pick<MapNode, "is_root" | "score" | "enriched_at" | "label">,
): number {
  const base = baseDiameter(node);
  const readable = node.is_root ? 13 : 9.5;
  const limit = node.is_root ? 190 : 130;
  let diameter = base;
  while (
    diameter < limit &&
    fitFont(node.label, diameter, largestFont(diameter, node.is_root, node.label)) < readable
  ) {
    diameter += 4;
  }
  return diameter;
}

export function fontSizeFor(
  label: string,
  diameter: number,
  isRoot: boolean,
): number {
  return fitFont(label, diameter, largestFont(diameter, isRoot, label));
}

export function badgeOffset(id: number, diameter: number): number {
  const steps = [-0.14, 0, 0.3, 0.12, 0.26];
  return steps[id % steps.length] * diameter;
}
