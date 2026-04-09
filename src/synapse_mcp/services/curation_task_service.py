"""Service layer for curation task operations.

Owns error boundary handling and delegation to the manager
for complex multi-step operations. Uses serialize_model for
consistent serialization across all services.
"""

from typing import Any, Dict, List

from fastmcp import Context
from synapseclient.models import (
    CurationTask,
    FileBasedMetadataTaskProperties,
    RecordBasedMetadataTaskProperties,
)

from ..managers.curation_task_manager import CurationTaskManager
from .tool_service import error_boundary, serialize_model, synapse_client


class CurationTaskService:
    """Orchestrates curation task operations."""

    @error_boundary(
        error_context_keys=("project_id",),
        wrap_errors=True,
    )
    def list_tasks(
        self, ctx: Context, project_id: str
    ) -> List[Dict[str, Any]]:
        """List all curation tasks for a project.

        Arguments:
            ctx: The FastMCP request context.
            project_id: Synapse project ID
                (e.g. ``"syn123"``).

        Returns:
            List of dicts, each containing task metadata
            (task_id, data_type, instructions,
            task_properties, etc.).
        """
        with synapse_client(ctx) as client:
            return [
                serialize_model(task)
                for task in CurationTask.list(
                    project_id=project_id,
                    synapse_client=client,
                )
            ]

    @error_boundary(error_context_keys=("task_id",))
    def get_task(
        self, ctx: Context, task_id: int
    ) -> Dict[str, Any]:
        """Retrieve a single curation task by ID.

        Arguments:
            ctx: The FastMCP request context.
            task_id: Numeric curation task ID.

        Returns:
            Dict with task metadata (task_id, data_type,
            instructions, task_properties, etc.).
        """
        with synapse_client(ctx) as client:
            task = CurationTask(task_id=task_id).get(
                synapse_client=client,
            )
            return serialize_model(task)

    @error_boundary(error_context_keys=("task_id",))
    def get_task_resources(
        self, ctx: Context, task_id: int
    ) -> Dict[str, Any]:
        """Retrieve a curation task and its resources.

        Arguments:
            ctx: The FastMCP request context.
            task_id: Numeric curation task ID.

        Returns:
            Dict with task_id, data_type, project_id,
            instructions, and a resources dict containing
            the associated Folder/EntityView (file-based)
            or RecordSet (record-based).
        """
        with synapse_client(ctx) as client:
            mgr = CurationTaskManager(client)
            task, resources = mgr.get_task_with_resources(
                task_id,
            )
            return {
                "task_id": task.task_id,
                "data_type": task.data_type,
                "project_id": task.project_id,
                "instructions": task.instructions,
                "resources": serialize_model(resources),
            }
