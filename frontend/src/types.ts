export type NodeKind =
  "niche" | "idea" | "target_group" | "pain_point" | "competitor";

export type Stage =
  | "compose"
  | "expanding"
  | "select"
  | "problems"
  | "personas"
  | "validate"
  | "done"
  | "board"
  | "flow";

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
  source: "autocomplete" | "community" | "reddit" | "trends" | "llm";
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

export interface CitedEvidence {
  id: number;
  source: string;
  title: string;
  url: string | null;
  place: string | null;
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
  evidence: CitedEvidence[];
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
  evidence_ids: number[];
  evidence: CitedEvidence[];
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

export type ElementType =
  "button" | "link" | "select" | "input" | "toggle" | "list";
export type ElementSize = "S" | "M" | "L";
export type ElementZone = "top" | "center" | "bottom";
export type ScreenKind = "start" | "step" | "goal";

export interface FlowElement {
  id: string;
  label: string;
  type: ElementType;
  size: ElementSize;
  zone: ElementZone;
  options: number;
  target: string | null;
}

export interface FlowScreen {
  id: string;
  name: string;
  kind: ScreenKind;
  x: number;
  y: number;
  feature_ids: number[];
  elements: FlowElement[];
}

export interface Flow {
  screens: FlowScreen[];
}

export interface FlowAudit {
  screens: number;
  transitions: number;
  steps: {
    value: number | null;
    path: string[];
    status: "ok" | "no_path" | "missing";
  };
  klm: {
    seconds: number;
    steps: { screen: string; element: string; seconds: number }[];
  } | null;
  targets: {
    total: number;
    aa: number;
    aaa: number;
    below_aaa: {
      screen_id: string;
      screen: string;
      element_id: string;
      element: string;
      size: ElementSize;
      pixels: number;
      primary: boolean;
    }[];
  };
  hick: {
    screen_id: string;
    screen: string;
    element_id: string | null;
    element: string | null;
    options: number;
    seconds: number;
    warning: boolean;
    hide: number;
  }[];
  fitts: {
    screen_id: string;
    screen: string;
    element_id: string;
    element: string;
    size: ElementSize;
    zone: ElementZone;
    index: number;
  }[];
  dead_ends: { screen_id: string; screen: string }[];
  unreachable: { screen_id: string; screen: string }[];
  constants: Record<string, number>;
  issues: number;
}

export interface Suggestion {
  id: string;
  title: string;
  reason: string;
  op: string;
  screen_id: string;
  element_id: string | null;
  value: string;
  label: string | null;
}

export interface DeliverState {
  project: Project;
  problem: Problem | null;
  persona: ChosenPersona | null;
  features: Feature[];
  flow: Flow;
  audit: FlowAudit;
  suggestions: Suggestion[];
}

export interface Handoff {
  figma_prompt: string;
  claude_md: string;
  directory: string;
}

export interface QualityState {
  enabled: boolean;
  has_key: boolean;
  model: string;
}

export type HypothesisStatus = "open" | "confirmed" | "rejected";

export interface Hypothesis {
  kind: "problem" | "frequency" | "workaround" | "willingness";
  text: string;
  signal: string;
  supports: number;
  contradicts: number;
  status: HypothesisStatus;
  quotes: {
    person: string;
    verdict: "supports" | "contradicts";
    quote: string;
  }[];
}

export interface Interview {
  id: string;
  person: string;
  notes: string;
  summary: string;
  verdicts: {
    hypothesis: number;
    verdict: "supports" | "contradicts" | "no_data";
    quote: string;
  }[];
  created_at: number;
}

export interface ValidateState {
  project: Project;
  problem: Problem;
  persona: Persona & { focus: string };
  hypotheses: Hypothesis[];
  screener: string[];
  questions: string[];
  interviews: Interview[];
  target: number;
  progress: { interviews: number; confirmed: number; rejected: number };
}

export interface SetupModel {
  id: "chat" | "embed" | "ux";
  name: string;
  size: string;
  required: boolean;
  installed: boolean;
  command: string;
  source: string;
}

export interface SetupState {
  ready: boolean;
  ollama: { ok: boolean; url: string; download: string };
  memory_gb: number | null;
  models: SetupModel[];
}
