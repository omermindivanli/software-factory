"""Hermes tools for submitting work to and inspecting Software Factory runs."""

from __future__ import annotations

import json
import os
from typing import Any
from uuid import UUID
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def _request(path: str, method: str = "GET", body: dict[str, Any] | None = None) -> str:
    base_url = os.getenv("SOFTWARE_FACTORY_URL", "http://127.0.0.1:8000").rstrip("/")
    payload = json.dumps(body).encode("utf-8") if body is not None else None
    request = Request(
        f"{base_url}/api/v1/{path.lstrip('/')}",
        data=payload,
        headers={"Content-Type": "application/json"},
        method=method,
    )
    try:
        with urlopen(request, timeout=20) as response:
            return json.dumps(json.loads(response.read().decode("utf-8")), indent=2)
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:2000]
        return json.dumps({"error": f"Factory API returned HTTP {exc.code}", "detail": detail})
    except (URLError, TimeoutError, OSError) as exc:
        return json.dumps({
            "error": "Could not reach Software Factory. Check that it is running and "
            "SOFTWARE_FACTORY_URL points to its local API.",
            "detail": str(exc),
        })


def register(ctx: Any) -> None:
    """Register Software Factory submission and status tools with Hermes."""

    def submit_work_item(
        title: str,
        description: str,
        repository: str,
        branch: str = "main",
        priority: str = "medium",
        labels: list[str] | None = None,
    ) -> str:
        return _request(
            "/runs/submit",
            method="POST",
            body={
                "title": title,
                "description": description,
                "repository": repository,
                "branch": branch,
                "priority": priority,
                "labels": labels or [],
                "source": "hermes",
            },
        )

    def list_runs(limit: int = 20, offset: int = 0) -> str:
        limit = max(1, min(int(limit), 100))
        offset = max(0, int(offset))
        return _request(f"runs?limit={limit}&offset={offset}")

    def get_run(run_id: str) -> str:
        try:
            safe_run_id = str(UUID(run_id.strip()))
        except ValueError:
            return json.dumps({"error": "run_id must be a valid UUID."})
        return _request(f"runs/{safe_run_id}")

    ctx.register_tool(
        name="factory_submit_work_item",
        toolset="software_factory",
        schema={
            "name": "factory_submit_work_item",
            "description": (
                "Submit a coding work item to the local Software Factory. The factory runs its "
                "configured planning, coding, validation, and release stages asynchronously. "
                "Returns a run ID that can be checked with factory_get_run."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Short task title."},
                    "description": {"type": "string", "description": "Detailed task and acceptance criteria."},
                    "repository": {"type": "string", "description": "Repository path or configured repository identifier."},
                    "branch": {"type": "string", "description": "Target branch; defaults to main."},
                    "priority": {"type": "string", "enum": ["low", "medium", "high", "critical"]},
                    "labels": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["title", "description", "repository"],
            },
        },
        handler=submit_work_item,
    )
    ctx.register_tool(
        name="factory_list_runs",
        toolset="software_factory",
        schema={
            "name": "factory_list_runs",
            "description": "List recent Software Factory runs and their current states.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "minimum": 1, "maximum": 100},
                    "offset": {"type": "integer", "minimum": 0},
                },
            },
        },
        handler=list_runs,
    )
    ctx.register_tool(
        name="factory_get_run",
        toolset="software_factory",
        schema={
            "name": "factory_get_run",
            "description": "Get the status, stage results, and metrics for a Software Factory run ID.",
            "parameters": {
                "type": "object",
                "properties": {"run_id": {"type": "string", "description": "Run ID returned by factory_submit_work_item."}},
                "required": ["run_id"],
            },
        },
        handler=get_run,
    )
