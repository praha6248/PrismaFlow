import type { DefineState, Evidence, Graph, Health, Job, MapNode, Phase, Project, Stage } from "./types";

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
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
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
  createProject: (seed: string) => request<Graph>("/projects", { method: "POST", body: json({ seed }) }),
  getProject: (id: number) => request<Graph>(`/projects/${id}`),
  setStage: (id: number, stage: Stage) =>
    request<Graph>(`/projects/${id}`, { method: "PATCH", body: json({ stage }) }),
  addNode: (projectId: number, label: string, connectTo?: number, x?: number, y?: number) =>
    request<Graph>(`/projects/${projectId}/nodes`, {
      method: "POST",
      body: json({ label, connect_to: connectTo ?? null, x: x ?? null, y: y ?? null }),
    }),
  savePositions: (projectId: number, positions: { id: number; x: number; y: number }[]) =>
    request<void>(`/projects/${projectId}/positions`, { method: "PUT", body: json({ positions }) }),
  updateNode: (id: number, patch: Partial<Pick<MapNode, "label" | "starred" | "x" | "y">>) =>
    request<MapNode>(`/nodes/${id}`, { method: "PATCH", body: json(patch) }),
  deleteNode: (id: number) => request<Graph>(`/nodes/${id}`, { method: "DELETE" }),
  evidence: (id: number) => request<Evidence>(`/nodes/${id}/evidence`),
  expand: (projectId: number, nodeId?: number, count = 3) =>
    request<Job>("/discover/expand", {
      method: "POST",
      body: json({ project_id: projectId, node_id: nodeId ?? null, count }),
    }),
  job: (id: string) => request<Job>(`/jobs/${id}`),
  setPhase: (id: number, phase: Phase) =>
    request<Graph>(`/projects/${id}`, { method: "PATCH", body: json({ phase }) }).then((g) => g.project as Project),
  getDefine: (projectId: number) => request<DefineState>(`/projects/${projectId}/define`),
  generateProblems: (projectId: number) =>
    request<Job>("/define/problems", { method: "POST", body: json({ project_id: projectId }) }),
  chooseProblem: (problemId: number) => request<DefineState>(`/problems/${problemId}/choose`, { method: "POST" }),
  generatePersonas: (projectId: number) =>
    request<Job>("/define/personas", { method: "POST", body: json({ project_id: projectId }) }),
  choosePersona: (personaId: number, option: number) =>
    request<DefineState>(`/personas/${personaId}/choose`, { method: "POST", body: json({ option }) }),
};

export async function waitForJob(id: string, onProgress: (job: Job) => void, intervalMs = 450): Promise<Job> {
  for (;;) {
    const job = await api.job(id);
    onProgress(job);
    if (job.status !== "running") return job;
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }
}
