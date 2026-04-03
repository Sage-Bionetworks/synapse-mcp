"""Service layer for curation task operations.

Owns serialization (model -> dict) and error boundary handling.
Simple SDK calls (list, get) happen here directly.
Complex multi-step operations delegate to CurationTaskManager.
"""

from typing import Any, Dict, List

from fastmcp import Context
from synapseclient.models import (
    CurationTask,
    FileBasedMetadataTaskProperties,
    RecordBasedMetadataTaskProperties,
)

from ..managers.curation_task_manager import CurationTaskManager
from .tool_service import dataclass_to_dict, error_boundary, synapse_client

_TASK_PROPERTY_TYPE_LABELS: Dict[type, str] = {
    RecordBasedMetadataTaskProperties: "record-based",
    FileBasedMetadataTaskProperties: "file-based",
}


def _format_task(task: CurationTask) -> Dict[str, Any]:
    """Serialize a CurationTask model into a response dict.

    Uses ``dataclass_to_dict`` to auto-include all dataclass fields where
    ``repr=True``. Adds a ``type`` discriminator to ``task_properties``.
    """
    result = dataclass_to_dict(task)

    props = task.task_properties
    if result.get("task_properties") and props is not None:
        label = _TASK_PROPERTY_TYPE_LABELS.get(type(props))
        if label:
            result["task_properties"]["type"] = label

    return result


class CurationTaskService:
    """Orchestrates curation task operations and shapes tool responses."""

    @error_boundary(
        error_context_keys=("project_id",),
        wrap_errors=True,
    )
    def list_tasks(
        self, ctx: Context, project_id: str
    ) -> List[Dict[str, Any]]:
        """List all curation tasks for a project.

        Args:
            ctx: MCP request context for authentication.
            project_id: Synapse project ID (e.g. ``"syn123"``).
        """
        with synapse_client(ctx) as client:
            return [
                _format_task(task)
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

        Args:
            ctx: MCP request context for authentication.
            task_id: Numeric curation task identifier.
        """
        with synapse_client(ctx) as client:
            task = CurationTask(task_id=task_id).get(
                synapse_client=client,
            )
            return _format_task(task)

    @error_boundary(error_context_keys=("task_id",))
    def get_task_resources(
        self, ctx: Context, task_id: int
    ) -> Dict[str, Any]:
        """Retrieve a curation task and its associated resources.

        Args:
            ctx: MCP request context for authentication.
            task_id: Numeric curation task identifier.
        """
        with synapse_client(ctx) as client:
            mgr = CurationTaskManager(client)
            task, resources = mgr.get_task_with_resources(
                task_id,
            )
            result = _format_task(task)
            result["resources"] = dataclass_to_dict(resources)
            return result
