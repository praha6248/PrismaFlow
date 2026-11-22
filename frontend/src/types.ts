export type NodeKind = "niche" | "idea" | "target_group" | "pain_point" | "competitor";

export type Stage = "compose" | "expanding" | "select" | "problems" | "personas" | "done";

export type DiscoverStage = "compose" | "expanding" | "select";

export type Phase = "discover" | "define" | "develop" | "deliver";

export const PHASES: Phase[] = ["discover", "define", "develop", "deliver"];

export interface Project {
  id: number;
  name: string;
  seed: string;
  language: string;
  geo: string;
  phase: Phase;
  stage: Stage;
  created_at: number;
  updated_at: number;
}

export interface MapNode {
  id: number;
  project_id: number;
  label: string;
  kind: NodeKind | null;
  is_root: boolean;
  starred: boolean;
  origin: "user" | "ai";
  search_query: string | null;
  score: number;
  trend_growth: number | null;
  enriched_at: number | null;
  x: number | null;
  y: number | null;
}

export interface MapEdge {
  id: number;
  project_id: number;
  source_id: number;
  target_id: number;
  origin: string;
}

export interface Graph {
  project: Project;
  nodes: MapNode[];
  edges: MapEdge[];
}

export interface Job {
  id: string;
  kind: string;
  status: "running" | "done" | "error";
  progress: number;
  stage: string;
  result: unknown;
  error: string | null;
  warnings: string[];
}

export interface EvidenceItem {
  id: number;
  source: "autocomplete" | "reddit" | "trends" | "llm";
  title: string;
  body: string;
  url: string | null;
  weight: number;
  meta: Record<string, unknown>;
}

export interface Evidence {
  node: MapNode;
  suggestions: EvidenceItem[];
  quotes: EvidenceItem[];
  trend: {
    growth: number | null;
    series: number[];
    dates: string[];
    anchor: string | null;
    anchor_ratio: number | null;
  };
}

export interface Health {
  ok: boolean;
  ollama: { ok: boolean; url: string; model: string | null; error?: string };
}

export interface TrendSummary {
  available: boolean;
  index?: number;
  peak?: number;
  growth?: number | null;
  anchor: string;
  anchor_ratio?: number | null;
  months?: { month: string; value: number }[];
}

export interface Problem {
  id: number;
  project_id: number;
  position: number;
  title: string;
  description: string;
  keyword: string;
  quote: string | null;
  quote_source: string | null;
  node_ids: number[];
  evidence_ids: number[];
  trend: TrendSummary | null;
  chosen: boolean;
}

export interface Persona {
  id: number;
  project_id: number;
  problem_id: number;
  position: number;
  name: string;
  age: number;
  role: string;
  quote: string;
  options: string[];
  chosen_option: number | null;
}

export interface DefineState {
  project: Project;
  problems: Problem[];
  personas: Persona[];
  chosen_problem_id: number | null;
}

export type Priority = "must" | "should" | "could" | "wont";

export interface Feature {
  id: number;
  project_id: number;
  priority: Priority;
  position: number;
  title: string;
  description: string;
  keywords: string[];
  evidence_ids: number[];
  support: number;
  pool: number;
  demand: number;
  origin: "user" | "ai";
}

export interface ChosenPersona extends Persona {
  focus: string;
}

export interface DevelopState {
  project: Project;
  problem: Problem | null;
  persona: ChosenPersona | null;
  features: Feature[];
}
