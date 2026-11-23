"""FastAPI application exposing the Double Diamond phases and serving the compiled frontend."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
from .database import Database
from .models import (
    DefineRequest,
    ExpandRequest,
    FeatureCreate,
    InterviewCreate,
    FeatureOrder,
    FeatureUpdate,
    FlowUpdate,
    Job,
    NodeCreate,
    NodeUpdate,
    PersonaChoice,
    PositionsUpdate,
    ProjectCreate,
    ProjectUpdate,
    QualityUpdate,
)
from .claude_client import HybridLLM, QualityConfig
from .ollama_client import OllamaClient
from .services.setup import memory_gb, setup_status
from .services import discover
from .services.define import DefineService, define_state
from .services.validate import ValidateService
from .services.deliver import DeliverService
from .services.develop import DevelopService, develop_state
from .services.discover import DiscoverService
from .services.jobs import JobRegistry


def create_app(
    db: Database | None = None,
    llm: OllamaClient | None = None,
    service: DiscoverService | None = None,
    frontend_dist: Path | None = None,
    define_service: DefineService | None = None,
    develop_service: DevelopService | None = None,
    deliver_service: DeliverService | None = None,
) -> FastAPI:
    """Build the FastAPI app with its dependencies wired in."""
    database = db or Database(settings.database_path)
    quality = QualityConfig()
    ollama = llm or HybridLLM(OllamaClient(), quality)
    discover_service = service or DiscoverService(database, ollama)
    define = define_service or DefineService(database, ollama)
    validate = ValidateService(database, ollama)
    develop = develop_service or DevelopService(database, ollama)
    deliver = deliver_service or DeliverService(database, ollama)
    jobs = JobRegistry()

    app = FastAPI(title="PrismaFlow", version="0.1.0", docs_url="/api/docs", openapi_url="/api/openapi.json")
    app.state.db = database
    app.state.jobs = jobs
    api = APIRouter(prefix="/api")

    @app.exception_handler(LookupError)
    async def not_found(_: Request, exc: LookupError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @api.get("/health")
    async def health() -> dict:
        """Report backend and local model status."""
        return {"ok": True, "ollama": await ollama.health(), "language": settings.language, "geo": settings.country}

    @api.get("/setup")
    async def setup() -> dict:
        """Report which local models are installed and how to install the missing ones."""
        health = await ollama.health()
        return setup_status(health["ok"], health["models"], health["url"], memory_gb(), settings.ux_model_repo)

    @api.get("/settings/quality")
    def quality_settings() -> dict:
        """Return whether the Claude quality mode is on and whether a key is saved (never the key)."""
        return quality.public()

    @api.put("/settings/quality")
    def update_quality(body: QualityUpdate) -> dict:
        """Turn the Claude quality mode on or off and save or remove the user's API key."""
        return quality.update(enabled=body.enabled, key=body.key)

    @api.get("/projects")
    def list_projects() -> list[dict]:
        """List recent projects."""
        return database.list_projects()

    @api.post("/projects", status_code=201)
    def create_project(body: ProjectCreate) -> dict:
        """Start a new project from a seed niche."""
        return discover.create_project(database, body.seed)

    @api.get("/projects/{project_id}")
    def get_project(project_id: int) -> dict:
        """Return a project's full mind map."""
        return discover.graph(database, project_id)

    @api.patch("/projects/{project_id}")
    def update_project(project_id: int, body: ProjectUpdate) -> dict:
        """Update project metadata such as the Discover stage."""
        if database.update_project(project_id, **body.model_dump()) is None:
            raise HTTPException(404, "project not found")
        return discover.graph(database, project_id)

    @api.delete("/projects/{project_id}", status_code=204)
    def delete_project(project_id: int) -> None:
        """Delete a project."""
        database.delete_project(project_id)

    @api.post("/projects/{project_id}/nodes", status_code=201)
    def add_node(project_id: int, body: NodeCreate) -> dict:
        """Add a user-typed association to the map."""
        if database.get_project(project_id) is None:
            raise HTTPException(404, "project not found")
        return discover.add_node(database, project_id, body.label, body.connect_to, body.x, body.y)

    @api.put("/projects/{project_id}/positions", status_code=204)
    def save_positions(project_id: int, body: PositionsUpdate) -> None:
        """Persist layout coordinates."""
        database.update_positions([(p.id, p.x, p.y) for p in body.positions])

    @api.patch("/nodes/{node_id}")
    def update_node(node_id: int, body: NodeUpdate) -> dict:
        """Star, rename or move a node."""
        node = database.update_node(node_id, **body.model_dump())
        if node is None:
            raise HTTPException(404, "node not found")
        return node

    @api.delete("/nodes/{node_id}")
    def delete_node(node_id: int) -> dict:
        """Remove a node and its edges."""
        node = database.get_node(node_id)
        if node is None:
            raise HTTPException(404, "node not found")
        if node["is_root"]:
            raise HTTPException(400, "the root niche cannot be removed")
        database.delete_node(node_id)
        return discover.graph(database, node["project_id"])

    @api.get("/nodes/{node_id}/evidence")
    def node_evidence(node_id: int) -> dict:
        """Return collected evidence for a node."""
        return discover.node_evidence(database, node_id)

    @api.get("/projects/{project_id}/search")
    def search(project_id: int, q: str) -> list[dict]:
        """Full-text search across the project's evidence."""
        return database.search_evidence(project_id, q)

    @api.post("/discover/expand", status_code=202)
    async def expand(body: ExpandRequest) -> Job:
        """Start an AI expansion job and return its handle."""
        if database.get_project(body.project_id) is None:
            raise HTTPException(404, "project not found")
        database.update_project(body.project_id, stage="expanding")

        async def run(progress, warn) -> dict:
            try:
                return await discover_service.expand(body.project_id, body.node_id, body.count, progress, warn)
            except Exception:
                database.update_project(body.project_id, stage="compose" if body.node_id is None else "select")
                raise

        return jobs.start("discover.expand", run)

    @api.get("/projects/{project_id}/validate")
    def get_validate(project_id: int) -> dict:
        """Return the validation plan, logged interviews and hypothesis statuses."""
        try:
            return validate.state(project_id)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    @api.post("/projects/{project_id}/validate/plan", status_code=202)
    async def plan_validation(project_id: int) -> Job:
        """Draft hypotheses and a Mom Test interview script in the background."""
        try:
            validate.state(project_id)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        return jobs.start("validate.plan", lambda progress, warn: validate.plan(project_id, progress, warn))

    @api.post("/projects/{project_id}/interviews")
    async def add_interview(project_id: int, body: InterviewCreate) -> dict:
        """Log an interview and score every hypothesis against its notes."""
        try:
            return await validate.add_interview(project_id, body.person, body.notes)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    @api.delete("/projects/{project_id}/interviews/{interview_id}")
    def remove_interview(project_id: int, interview_id: str) -> dict:
        """Delete a logged interview."""
        return validate.remove_interview(project_id, interview_id)

    @api.get("/projects/{project_id}/define")
    def get_define(project_id: int) -> dict:
        """Return problem statements, the chosen problem and its personas."""
        return define_state(database, project_id)

    @api.post("/define/problems", status_code=202)
    async def define_problems(body: DefineRequest) -> Job:
        """Start generating three problem statements from the selected topics."""
        if database.get_project(body.project_id) is None:
            raise HTTPException(404, "project not found")
        database.update_project(body.project_id, phase="define")
        return jobs.start(
            "define.problems", lambda progress, warn: define.generate_problems(body.project_id, progress, warn)
        )

    @api.post("/problems/{problem_id}/choose")
    def choose_problem(problem_id: int) -> dict:
        """Pick the main problem."""
        problem = database.choose_problem(problem_id)
        if problem is None:
            raise HTTPException(404, "problem not found")
        return define_state(database, problem["project_id"])

    @api.post("/define/personas", status_code=202)
    async def define_personas(body: DefineRequest) -> Job:
        """Start generating personas for the chosen problem."""
        state = define_state(database, body.project_id)
        if state["chosen_problem_id"] is None:
            raise HTTPException(400, "choose a problem first")
        return jobs.start(
            "define.personas", lambda progress, warn: define.generate_personas(body.project_id, progress, warn)
        )

    @api.post("/personas/{persona_id}/choose")
    def choose_persona(persona_id: int, body: PersonaChoice) -> dict:
        """Pick a persona and its main sub-problem."""
        persona = database.choose_persona(persona_id, body.option)
        if persona is None:
            raise HTTPException(404, "persona or option not found")
        return define_state(database, persona["project_id"])

    @api.get("/projects/{project_id}/develop")
    def get_develop(project_id: int) -> dict:
        """Return the MoSCoW backlog with the persona and problem it serves."""
        return develop_state(database, project_id)

    @api.post("/develop/features", status_code=202)
    async def develop_features(body: DefineRequest) -> Job:
        """Start generating the feature backlog for the chosen persona."""
        state = develop_state(database, body.project_id)
        if state["persona"] is None:
            raise HTTPException(400, "choose a persona in Define first")
        return jobs.start("develop.features", lambda progress, warn: develop.generate(body.project_id, progress, warn))

    @api.post("/projects/{project_id}/features", status_code=201)
    def add_feature(project_id: int, body: FeatureCreate) -> dict:
        """Add a feature written by the user."""
        if database.get_project(project_id) is None:
            raise HTTPException(404, "project not found")
        return develop.add(project_id, body.title, body.description, body.priority)

    @api.patch("/features/{feature_id}")
    def update_feature(feature_id: int, body: FeatureUpdate) -> dict:
        """Edit a feature card and rescore it when its text changed."""
        if database.get_feature(feature_id) is None:
            raise HTTPException(404, "feature not found")
        database.update_feature(feature_id, **body.model_dump(exclude_none=True))
        if body.title is not None or body.description is not None:
            return develop.rescore(feature_id)
        return database.get_feature(feature_id)

    @api.put("/projects/{project_id}/features/order")
    def order_features(project_id: int, body: FeatureOrder) -> list[dict]:
        """Store the board layout after drag and drop."""
        return database.reorder_features(project_id, [(i.id, i.priority, i.position) for i in body.items])

    @api.delete("/features/{feature_id}", status_code=204)
    def delete_feature(feature_id: int) -> None:
        """Remove a feature card."""
        database.delete_feature(feature_id)

    @api.get("/projects/{project_id}/deliver")
    def get_deliver(project_id: int) -> dict:
        """Return the user flow, its live audit and pending AI suggestions."""
        return deliver.state(project_id)

    @api.put("/projects/{project_id}/flow")
    def save_flow(project_id: int, body: FlowUpdate) -> dict:
        """Store the edited flow and return a fresh audit."""
        return deliver.save(project_id, body.flow)

    @api.post("/deliver/flow", status_code=202)
    async def deliver_flow(body: DefineRequest) -> Job:
        """Start generating a first user flow from the backlog."""
        if not [f for f in database.list_features(body.project_id) if f["priority"] != "wont"]:
            raise HTTPException(400, "add features in Develop first")
        return jobs.start("deliver.flow", lambda progress, warn: deliver.generate(body.project_id, progress, warn))

    @api.post("/deliver/optimize", status_code=202)
    async def deliver_optimize(body: DefineRequest) -> Job:
        """Start asking the local model for flow optimisations."""
        if not deliver.flow(body.project_id).screens:
            raise HTTPException(400, "the flow is empty")
        return jobs.start("deliver.optimize", lambda progress, warn: deliver.optimize(body.project_id, progress, warn))

    @api.post("/projects/{project_id}/suggestions/{suggestion_id}/accept")
    def accept_suggestion(project_id: int, suggestion_id: str) -> dict:
        """Apply an AI suggestion to the flow."""
        return deliver.accept(project_id, suggestion_id)

    @api.delete("/projects/{project_id}/suggestions/{suggestion_id}")
    def dismiss_suggestion(project_id: int, suggestion_id: str) -> dict:
        """Dismiss an AI suggestion."""
        return deliver.dismiss(project_id, suggestion_id)

    @api.post("/projects/{project_id}/handoff")
    async def handoff(project_id: int) -> dict:
        """Export the Figma prompt and CLAUDE.md and return their contents."""
        if not deliver.flow(project_id).screens:
            raise HTTPException(400, "the flow is empty")
        return await deliver.handoff(project_id)

    @api.get("/jobs/{job_id}")
    def job_status(job_id: str) -> Job:
        """Poll a background job."""
        job = jobs.get(job_id)
        if job is None:
            raise HTTPException(404, "job not found")
        return job

    app.include_router(api)

    dist = frontend_dist or settings.frontend_dist
    if dist.is_dir() and (dist / "index.html").is_file():
        assets = dist / "assets"
        if assets.is_dir():
            app.mount("/assets", StaticFiles(directory=assets), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str) -> FileResponse:
            candidate = (dist / path).resolve()
            if path and candidate.is_file() and dist.resolve() in candidate.parents:
                return FileResponse(candidate)
            return FileResponse(dist / "index.html")

    return app
