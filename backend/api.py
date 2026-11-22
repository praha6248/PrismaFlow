"""FastAPI application exposing the Discover phase and serving the compiled frontend."""

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
    Job,
    NodeCreate,
    NodeUpdate,
    PersonaChoice,
    PositionsUpdate,
    ProjectCreate,
    ProjectUpdate,
)
from .ollama_client import OllamaClient
from .services import discover
from .services.define import DefineService, define_state
from .services.discover import DiscoverService
from .services.jobs import JobRegistry


def create_app(
    db: Database | None = None,
    llm: OllamaClient | None = None,
    service: DiscoverService | None = None,
    frontend_dist: Path | None = None,
    define_service: DefineService | None = None,
) -> FastAPI:
    """Build the FastAPI app with its dependencies wired in."""
    database = db or Database(settings.database_path)
    ollama = llm or OllamaClient()
    discover_service = service or DiscoverService(database, ollama)
    define = define_service or DefineService(database, ollama)
    jobs = JobRegistry()

    app = FastAPI(title="PrismFlow", version="0.1.0", docs_url="/api/docs", openapi_url="/api/openapi.json")
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
