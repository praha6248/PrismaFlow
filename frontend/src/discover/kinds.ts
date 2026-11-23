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
    badgeText: "#d14fc0",
  },
  idea: {
    label: t("pomysł"),
    gradient: "linear-gradient(150deg, #b98cee 0%, #a88bee 50%, #958aed 100%)",
    badgeBg: "#e5d3f8",
    badgeText: "#9e4eef",
  },
  target_group: {
    label: t("grupa docelowa"),
    gradient: "linear-gradient(140deg, #8fc1ef 0%, #b0c6f6 50%, #d3ccfb 100%)",
    badgeBg: "#d2e5f9",
    badgeText: "#4c98e5",
  },
  pain_point: {
    label: t("problem"),
    gradient: "linear-gradient(150deg, #f167e2 0%, #f34fbd 50%, #f6449a 100%)",
    badgeBg: "#ffd0ec",
    badgeText: "#fc4aa1",
  },
  competitor: {
    label: t("konkurencja"),
    gradient: "linear-gradient(145deg, #fdb68a 0%, #fb9c98 55%, #f68aa9 100%)",
    badgeBg: "#ffe0d0",
    badgeText: "#e3743c",
  },
};

export function styleFor(node: Pick<MapNode, "kind" | "is_root">): KindStyle {
  if (node.is_root) return KIND_STYLES.niche;
  return KIND_STYLES[node.kind ?? "idea"];
}

export const ROOT_DIAMETER = 84;

export function diameterFor(
  node: Pick<MapNode, "is_root" | "score" | "enriched_at">,
): number {
  if (node.is_root) return ROOT_DIAMETER;
  if (!node.enriched_at) return 60;
  const score = Math.max(0, Math.min(1, node.score));
  return Math.round(56 + score * 42);
}

export function fontSizeFor(
  label: string,
  diameter: number,
  isRoot: boolean,
): number {
  const byWord = (diameter * 0.84) / (longestWord(label) * 0.62);
  if (isRoot) return Math.max(9, Math.min(20, byWord));
  const words = label.trim().split(/\s+/);
  const lines = Math.max(
    words.length,
    Math.ceil(label.length / Math.max(6, longestWord(label))),
  );
  const base = lines > 1 ? diameter * 0.18 : diameter * 0.235;
  const byHeight = (diameter * 0.66) / (Math.min(lines, 3) * 1.15);
  return Math.max(7, Math.min(base, byWord, byHeight));
}

function longestWord(label: string): number {
  return Math.max(1, ...label.split(/\s+/).map((w) => w.length));
}

export function badgeOffset(id: number, diameter: number): number {
  const steps = [-0.14, 0, 0.3, 0.12, 0.26];
  return steps[id % steps.length] * diameter;
}
