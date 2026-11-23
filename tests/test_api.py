"""HTTP-level tests for the FastAPI application."""

from fastapi.testclient import TestClient

from backend.api import create_app
from backend.database import Database
from backend.services.discover import DiscoverService

from .conftest import FakeLLM, offline_collectors


def _client(tmp_path) -> TestClient:
    db = Database(":memory:")
    service = DiscoverService(db, FakeLLM({"classified": [], "new_nodes": []}), offline_collectors())
    return TestClient(create_app(db=db, service=service, frontend_dist=tmp_path))


def test_project_and_node_lifecycle(tmp_path) -> None:
    client = _client(tmp_path)
    graph = client.post("/api/projects", json={"seed": "  local   ai "}).json()
    assert graph["project"]["seed"] == "local ai"
    project_id = graph["project"]["id"]

    graph = client.post(f"/api/projects/{project_id}/nodes", json={"label": "privacy"}).json()
    node = next(n for n in graph["nodes"] if n["label"] == "privacy")
    assert len(graph["edges"]) == 1

    starred = client.patch(f"/api/nodes/{node['id']}", json={"starred": True}).json()
    assert starred["starred"] is True

    root = next(n for n in graph["nodes"] if n["is_root"])
    assert client.delete(f"/api/nodes/{root['id']}").status_code == 400
    assert client.delete(f"/api/nodes/{node['id']}").json()["edges"] == []


def test_validation_and_missing_resources(tmp_path) -> None:
    client = _client(tmp_path)
    assert client.post("/api/projects", json={"seed": "   "}).status_code == 422
    assert client.get("/api/projects/999").status_code == 404
    assert client.get("/api/jobs/nope").status_code == 404
    assert client.post("/api/discover/expand", json={"project_id": 999}).status_code == 404


def test_expand_job_runs_to_completion(tmp_path) -> None:
    client = _client(tmp_path)
    with client:
        project_id = client.post("/api/projects", json={"seed": "sport"}).json()["project"]["id"]
        job = client.post("/api/discover/expand", json={"project_id": project_id}).json()
        for _ in range(200):
            state = client.get(f"/api/jobs/{job['id']}").json()
            if state["status"] != "running":
                break
        assert state["status"] == "done", state
        assert state["result"]["project"]["stage"] == "select"


def test_running_expansion_can_be_resumed(tmp_path) -> None:
    import asyncio
    from threading import Event

    release = Event()

    class PausedDiscover(DiscoverService):
        async def expand(self, *args):
            await asyncio.to_thread(release.wait, 5)
            return await super().expand(*args)

    db = Database(":memory:")
    service = PausedDiscover(db, FakeLLM(), offline_collectors())
    with TestClient(create_app(db=db, service=service, frontend_dist=tmp_path)) as client:
        project = client.post("/api/projects", json={"seed": "Planer"}).json()["project"]["id"]
        body = {"project_id": project}
        job = client.post("/api/discover/expand", json=body).json()
        try:
            assert client.get(f"/api/projects/{project}").json()["expansion_job_id"] == job["id"]
            assert client.post("/api/discover/expand", json=body).json()["id"] == job["id"]
        finally:
            release.set()
        for _ in range(200):
            if client.get(f"/api/jobs/{job['id']}").json()["status"] == "done":
                break
        graph = client.get(f"/api/projects/{project}").json()
        assert graph["project"]["stage"] == "select" and "expansion_job_id" not in graph
