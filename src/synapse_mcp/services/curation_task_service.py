"""Service layer for curation task operations.

Owns serialization (model -> dict) and error boundary handling.
Simple SDK calls (list, get) happen here directly.
Complex multi-step operations delegate to CurationTaskManager.
"""

from typing import Any, Dict, List, Optional

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


def _build_task_properties(spec: Dict[str, Any]):
    """Build a task-properties model from a plain dict, or an error dict.

    Record-based tasks carry ``record_set_id``; file-based tasks carry
    ``upload_folder_id`` (and optionally ``file_view_id``). The presence
    of ``record_set_id`` selects record-based; otherwise file-based.
    """
    if spec.get("record_set_id"):
        return RecordBasedMetadataTaskProperties(
            record_set_id=spec["record_set_id"],
        )
    if spec.get("upload_folder_id"):
        return FileBasedMetadataTaskProperties(
            upload_folder_id=spec["upload_folder_id"],
            file_view_id=spec.get("file_view_id"),
        )
    return {
        "error": (
            "task_properties must include either 'record_set_id' "
            "(record-based) or 'upload_folder_id' (file-based)."
        )
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

    @staticmethod
    @error_boundary(
        error_context_keys=("project_id",),
        wrap_errors=True,
    )
    async def list_tasks(
        ctx: Context, project_id: str
    ) -> List[Dict[str, Any]]:
        """List all curation tasks for a project.

        Args:
            ctx: MCP request context for authentication.
            project_id: Synapse project ID (e.g. ``"syn123"``).
        """
        async with synapse_client(ctx) as client:
            return [
                _format_task(task)
                async for task in CurationTask.list_async(
                    project_id=project_id,
                    synapse_client=client,
                )
            ]

    @staticmethod
    @error_boundary(error_context_keys=("task_id",))
    async def get_task(
        ctx: Context, task_id: int
    ) -> Dict[str, Any]:
        """Retrieve a single curation task by ID.

        Args:
            ctx: MCP request context for authentication.
            task_id: Numeric curation task identifier.
        """
        async with synapse_client(ctx) as client:
            task = await CurationTask(task_id=task_id).get_async(
                synapse_client=client,
            )
            return _format_task(task)

    @staticmethod
    @error_boundary(error_context_keys=("task_id",))
    async def get_task_resources(
        ctx: Context, task_id: int
    ) -> Dict[str, Any]:
        """Retrieve a curation task and its associated resources.

        Args:
            ctx: MCP request context for authentication.
            task_id: Numeric curation task identifier.
        """
        async with synapse_client(ctx) as client:
            mgr = CurationTaskManager(client)
            task, resources = await mgr.get_task_with_resources(
                task_id,
            )
            result = _format_task(task)
            result["resources"] = dataclass_to_dict(resources)
            return result

    @staticmethod
    @error_boundary(error_context_keys=("project_id", "data_type"))
    async def create_task(
        ctx: Context,
        project_id: str,
        data_type: str,
        task_properties: Dict[str, Any],
        instructions: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a curation task on a Synapse project.

        ``task_properties`` selects the task shape:
        - record-based: ``{"record_set_id": "syn123"}``
        - file-based: ``{"upload_folder_id": "syn123",
          "file_view_id": "syn456"}``

        Arguments:
            ctx: The FastMCP request context.
            project_id: Synapse project ID owning the task (e.g. syn123456).
            data_type: The data type the task curates.
            task_properties: Record- or file-based property dict (see above).
            instructions: Optional curator instructions.

        Returns:
            Dict with the created curation task.
        """
        props = _build_task_properties(task_properties)
        if isinstance(props, dict):  # validation error
            return props
        async with synapse_client(ctx) as client:
            task = CurationTask(
                project_id=project_id,
                data_type=data_type,
                instructions=instructions,
                task_properties=props,
            )
            stored = await task.store_async(synapse_client=client)
            return _format_task(stored)

    @staticmethod
    @error_boundary(error_context_keys=("task_id",))
    async def delete_task(
        ctx: Context, task_id: int
    ) -> Dict[str, Any]:
        """Delete a curation task by ID.

        Arguments:
            ctx: The FastMCP request context.
            task_id: Numeric curation task identifier (e.g. 42).

        Returns:
            Dict confirming the deletion.
        """
        async with synapse_client(ctx) as client:
            await CurationTask(task_id=task_id).delete_async(
                synapse_client=client,
            )
            return {"task_id": task_id, "deleted": True}
