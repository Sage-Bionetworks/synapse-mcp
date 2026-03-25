"""Service layer for curation task operations."""

from typing import Any, Dict, List

from fastmcp import Context

from ..managers import CurationTaskManager
from .tool_service import with_synapse_client


class CurationTaskService:
    """Orchestrates curation task operations.

    Handles authentication, error wrapping, and delegation to
    CurationTaskManager for Synapse API calls.
    """

    def list_tasks(self, ctx: Context, project_id: str) -> List[Dict[str, Any]]:
        """List all curation tasks for a project."""
        result = with_synapse_client(
            ctx,
            lambda client: CurationTaskManager(client).list_tasks(project_id),
            error_context={"project_id": project_id},
        )
        return result if isinstance(result, list) else [result]

    def get_task(self, ctx: Context, task_id: int) -> Dict[str, Any]:
        """Get a single curation task by ID."""
        return with_synapse_client(
            ctx,
            lambda client: CurationTaskManager(client).get_task(task_id),
            error_context={"task_id": task_id},
        )

    def get_task_resources(self, ctx: Context, task_id: int) -> Dict[str, Any]:
        """Get a task and its associated resources."""
        return with_synapse_client(
            ctx,
            lambda client: CurationTaskManager(client).get_task_resources(task_id),
            error_context={"task_id": task_id},
        )
