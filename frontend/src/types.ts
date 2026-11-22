export type NodeKind = "niche" | "idea" | "target_group" | "pain_point" | "competitor";

export type Stage = "compose" | "expanding" | "select";

export interface Project {
  id: number;
  name: string;
  seed: string;
  language: string;
  geo: string;
  phase: string;
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
  result: Graph | null;
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
