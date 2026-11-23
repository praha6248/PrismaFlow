import { locale } from "./i18n";
import type {
  DefineState,
  DeliverState,
  DevelopState,
  Flow,
  FlowAudit,
  Handoff,
  Evidence,
  Feature,
  Priority,
  Graph,
  Health,
  Job,
  MapNode,
  Phase,
  Project,
  QualityState,
  Stage,
  ValidateState,
  SetupState,
  BoardState,
  EmpathyState,
  NoteSource,
  TestResult,
  TestsState,
} from "./types";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`api${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      detail =
        typeof body.detail === "string"
          ? body.detail
          : JSON.stringify(body.detail);
    } catch {
      detail = response.statusText;
    }
    throw new ApiError(detail, response.status);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

const json = (body: unknown) => JSON.stringify(body);

export const api = {
  health: () => request<Health>("/health"),
  setup: () => request<SetupState>("/setup"),
  quality: () => request<QualityState>("/settings/quality"),
  getValidate: (projectId: number) =>
    request<ValidateState>(`/projects/${projectId}/validate`),
  planValidation: (projectId: number) =>
    request<Job>(`/projects/${projectId}/validate/plan`, { method: "POST" }),
  addInterview: (projectId: number, person: string, notes: string) =>
    request<ValidateState>(`/projects/${projectId}/interviews`, {
      method: "POST",
      body: JSON.stringify({ person, notes }),
    }),
  removeInterview: (projectId: number, interviewId: string) =>
    request<ValidateState>(`/projects/${projectId}/interviews/${interviewId}`, {
      method: "DELETE",
    }),
  updateQuality: (body: { enabled?: boolean; key?: string }) =>
    request<QualityState>("/settings/quality", {
      method: "PUT",
      body: JSON.stringify(body),
    }),
  createProject: (seed: string) =>
    request<Graph>("/projects", { method: "POST", body: json({ seed }) }),
  getProject: (id: number) => request<Graph>(`/projects/${id}`),
  setStage: (id: number, stage: Stage) =>
    request<Graph>(`/projects/${id}`, {
      method: "PATCH",
      body: json({ stage }),
    }),
  addNode: (
    projectId: number,
    label: string,
    connectTo?: number,
    x?: number,
    y?: number,
  ) =>
    request<Graph>(`/projects/${projectId}/nodes`, {
      method: "POST",
      body: json({
        label,
        connect_to: connectTo ?? null,
        x: x ?? null,
        y: y ?? null,
      }),
    }),
  savePositions: (
    projectId: number,
    positions: { id: number; x: number; y: number }[],
  ) =>
    request<void>(`/projects/${projectId}/positions`, {
      method: "PUT",
      body: json({ positions }),
    }),
  updateNode: (
    id: number,
    patch: Partial<Pick<MapNode, "label" | "starred" | "x" | "y">>,
  ) => request<MapNode>(`/nodes/${id}`, { method: "PATCH", body: json(patch) }),
  deleteNode: (id: number) =>
    request<Graph>(`/nodes/${id}`, { method: "DELETE" }),
  evidence: (id: number) => request<Evidence>(`/nodes/${id}/evidence?locale=${locale}`),
  expand: (projectId: number, nodeId?: number, count = 3) =>
    request<Job>("/discover/expand", {
      method: "POST",
      body: json({ project_id: projectId, node_id: nodeId ?? null, count }),
    }),
  job: (id: string) => request<Job>(`/jobs/${id}`),
  setPhase: (id: number, phase: Phase) =>
    request<Graph>(`/projects/${id}`, {
      method: "PATCH",
      body: json({ phase }),
    }).then((g) => g.project as Project),
  getDefine: (projectId: number) =>
    request<DefineState>(`/projects/${projectId}/define`),
  generateProblems: (projectId: number) =>
    request<Job>("/define/problems", {
      method: "POST",
      body: json({ project_id: projectId }),
    }),
  chooseProblem: (problemId: number) =>
    request<DefineState>(`/problems/${problemId}/choose`, { method: "POST" }),
  generatePersonas: (projectId: number) =>
    request<Job>("/define/personas", {
      method: "POST",
      body: json({ project_id: projectId }),
    }),
  getDevelop: (projectId: number) =>
    request<DevelopState>(`/projects/${projectId}/develop`),
  generateFeatures: (projectId: number) =>
    request<Job>("/develop/features", {
      method: "POST",
      body: json({ project_id: projectId }),
    }),
  addFeature: (
    projectId: number,
    title: string,
    description: string,
    priority: Priority,
  ) =>
    request<Feature>(`/projects/${projectId}/features`, {
      method: "POST",
      body: json({ title, description, priority }),
    }),
  updateFeature: (
    id: number,
    patch: Partial<Pick<Feature, "title" | "description" | "priority" | "impact" | "effort">>,
  ) =>
    request<Feature>(`/features/${id}`, { method: "PATCH", body: json(patch) }),
  orderFeatures: (
    projectId: number,
    items: { id: number; priority: Priority; position: number }[],
  ) =>
    request<Feature[]>(`/projects/${projectId}/features/order`, {
      method: "PUT",
      body: json({ items }),
    }),
  deleteFeature: (id: number) =>
    request<void>(`/features/${id}`, { method: "DELETE" }),
  getDeliver: (projectId: number) =>
    request<DeliverState>(`/projects/${projectId}/deliver`),
  saveFlow: (projectId: number, flow: Flow) =>
    request<{ flow: Flow; audit: FlowAudit }>(`/projects/${projectId}/flow`, {
      method: "PUT",
      body: json({ flow }),
    }),
  generateFlow: (projectId: number) =>
    request<Job>("/deliver/flow", {
      method: "POST",
      body: json({ project_id: projectId }),
    }),
  optimizeFlow: (projectId: number) =>
    request<Job>("/deliver/optimize", {
      method: "POST",
      body: json({ project_id: projectId }),
    }),
  acceptSuggestion: (projectId: number, id: string) =>
    request<DeliverState>(`/projects/${projectId}/suggestions/${id}/accept`, {
      method: "POST",
    }),
  dismissSuggestion: (projectId: number, id: string) =>
    request<DeliverState>(`/projects/${projectId}/suggestions/${id}`, {
      method: "DELETE",
    }),
  handoff: (projectId: number) =>
    request<Handoff>(`/projects/${projectId}/handoff`, { method: "POST" }),
  caseStudy: (projectId: number) =>
    request<Job>(`/projects/${projectId}/case-study`, { method: "POST" }),
  board: (projectId: number) => request<BoardState>(`/projects/${projectId}/board`),
  addNotes: (projectId: number, text: string, source: NoteSource, label = "", theme: string | null = null) =>
    request<BoardState>(`/projects/${projectId}/board/notes`, {
      method: "POST",
      body: json({ text, source, label, theme }),
    }),
  moveNote: (projectId: number, noteId: string, theme: string | null) =>
    request<BoardState>(`/projects/${projectId}/board/notes/${noteId}`, {
      method: "PATCH",
      body: json({ theme }),
    }),
  removeNote: (projectId: number, noteId: string) =>
    request<BoardState>(`/projects/${projectId}/board/notes/${noteId}`, { method: "DELETE" }),
  addTheme: (projectId: number, name: string) =>
    request<BoardState>(`/projects/${projectId}/board/themes`, {
      method: "POST",
      body: json({ name }),
    }),
  updateTheme: (projectId: number, themeId: string, patch: { name?: string; insight?: string }) =>
    request<BoardState>(`/projects/${projectId}/board/themes/${themeId}`, {
      method: "PATCH",
      body: json(patch),
    }),
  removeTheme: (projectId: number, themeId: string) =>
    request<BoardState>(`/projects/${projectId}/board/themes/${themeId}`, { method: "DELETE" }),
  clusterBoard: (projectId: number) =>
    request<Job>(`/projects/${projectId}/board/cluster`, { method: "POST" }),
  empathy: (projectId: number) => request<EmpathyState>(`/projects/${projectId}/empathy`),
  generateEmpathy: (projectId: number) =>
    request<Job>(`/projects/${projectId}/empathy`, { method: "POST" }),
  chooseHmw: (projectId: number, text: string) =>
    request<EmpathyState>(`/projects/${projectId}/hmw`, {
      method: "PUT",
      body: json({ text }),
    }),
  tests: (projectId: number) => request<TestsState>(`/projects/${projectId}/tests`),
  planTests: (projectId: number) =>
    request<Job>(`/projects/${projectId}/tests/plan`, { method: "POST" }),
  updateTask: (projectId: number, taskId: string, scenario: string) =>
    request<TestsState>(`/projects/${projectId}/tests/tasks/${taskId}`, {
      method: "PATCH",
      body: json({ scenario }),
    }),
  addSession: (projectId: number, participant: string, results: TestResult[]) =>
    request<TestsState>(`/projects/${projectId}/tests/sessions`, {
      method: "POST",
      body: json({ participant, results }),
    }),
  removeSession: (projectId: number, sessionId: string) =>
    request<TestsState>(`/projects/${projectId}/tests/sessions/${sessionId}`, { method: "DELETE" }),
  sendFinding: (projectId: number, text: string, target: "board" | "backlog") =>
    request<{ target: string }>(`/projects/${projectId}/findings`, {
      method: "POST",
      body: json({ text, target }),
    }),
  choosePersona: (personaId: number, option: number) =>
    request<DefineState>(`/personas/${personaId}/choose`, {
      method: "POST",
      body: json({ option }),
    }),
};

export async function waitForJob(
  id: string,
  onProgress: (job: Job) => void,
  intervalMs = 450,
): Promise<Job> {
  for (;;) {
    const job = await api.job(id);
    onProgress(job);
    if (job.status !== "running") return job;
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }
}
