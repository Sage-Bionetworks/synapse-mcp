"""Service layer for curation task operations.

Owns serialization (model -> dict) and error boundary handling.
Simple SDK calls (list, get) happen here directly.
Complex multi-step operations delegate to CurationTaskManager.
"""

from typing import Any, Dict, List

from fastmcp import Context
from synapseclient.models import CurationTask

from ..managers.curation_task_manager import CurationTaskManager
from .tool_service import error_boundary, synapse_client_from


def _format_task_properties(task_properties: Any) -> Dict[str, Any]:
    """Serialize task_properties into a typed dictionary."""
    if task_properties is None:
        return {}

    if hasattr(task_properties, "record_set_id"):
        return {
            "type": "record-based",
            "record_set_id": task_properties.record_set_id,
        }

    if hasattr(task_properties, "upload_folder_id"):
        return {
            "type": "file-based",
            "upload_folder_id": task_properties.upload_folder_id,
            "file_view_id": task_properties.file_view_id,
        }

    return {}


def _format_task(task: CurationTask) -> Dict[str, Any]:
    """Serialize a CurationTask model object into a response dict."""
    task_dict: Dict[str, Any] = {
        "task_id": task.task_id,
        "data_type": task.data_type,
        "project_id": task.project_id,
        "instructions": task.instructions,
        "etag": task.etag,
        "created_on": task.created_on,
        "modified_on": task.modified_on,
        "created_by": task.created_by,
        "modified_by": task.modified_by,
    }

    props = _format_task_properties(task.task_properties)
    if props:
        task_dict["task_properties"] = props

    return task_dict


class CurationTaskService:
    """Orchestrates curation task operations and shapes tool responses."""

    @error_boundary(
        error_context_keys=("project_id",),
        wrap_errors=list,
    )
    def list_tasks(
        self, ctx: Context, project_id: str
    ) -> List[Dict[str, Any]]:
        """List all curation tasks for a project."""
        with synapse_client_from(ctx) as client:
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
        """Retrieve a single curation task by ID."""
        with synapse_client_from(ctx) as client:
            task = CurationTask(task_id=task_id).get(
                synapse_client=client,
            )
            return _format_task(task)

    @error_boundary(error_context_keys=("task_id",))
    def get_task_resources(
        self, ctx: Context, task_id: int
    ) -> Dict[str, Any]:
        """Retrieve a curation task and its associated resources."""
        with synapse_client_from(ctx) as client:
            mgr = CurationTaskManager(client)
            task, resources = mgr.get_task_with_resources(
                task_id,
            )
            return {
                "task_id": task.task_id,
                "data_type": task.data_type,
                "project_id": task.project_id,
                "instructions": task.instructions,
                "resources": resources,
            }
