"""In-process registry of background jobs with pollable progress."""

from __future__ import annotations

import asyncio
import uuid
from collections import OrderedDict
from typing import Any, Awaitable, Callable

from ..models import Job

ProgressFn = Callable[[float, str], None]
WarnFn = Callable[[str], None]
JobBody = Callable[[ProgressFn, WarnFn], Awaitable[dict[str, Any]]]


class JobRegistry:
    """Keeps recent jobs in memory and runs their bodies as asyncio tasks."""

    def __init__(self, keep: int = 64) -> None:
        self._jobs: OrderedDict[str, Job] = OrderedDict()
        self._tasks: dict[str, asyncio.Task] = {}
        self._keep = keep

    def get(self, job_id: str) -> Job | None:
        """Return a job snapshot by id."""
        return self._jobs.get(job_id)

    def start(self, kind: str, body: JobBody) -> Job:
        """Create a job and schedule its body on the running event loop."""
        job = Job(id=uuid.uuid4().hex[:12], kind=kind)
        self._jobs[job.id] = job
        while len(self._jobs) > self._keep:
            self._jobs.popitem(last=False)

        def progress(value: float, stage: str) -> None:
            job.progress = max(job.progress, min(1.0, value))
            job.stage = stage

        def warn(message: str) -> None:
            if message not in job.warnings:
                job.warnings.append(message)

        async def runner() -> None:
            try:
                job.result = await body(progress, warn)
                job.progress = 1.0
                job.stage = "done"
                job.status = "done"
            except Exception as exc:
                job.status = "error"
                job.error = str(exc) or exc.__class__.__name__
            finally:
                self._tasks.pop(job.id, None)

        self._tasks[job.id] = asyncio.get_running_loop().create_task(runner())
        return job
