"""Service layer for curation task operations.

This module orchestrates CurationTaskManager calls and translates
CurationTask model objects into tool-friendly response dictionaries.
It owns serialization logic, response shaping, and partial-failure handling.
"""

from typing import Any, Dict, List

from fastmcp import Context
from synapseclient.models import CurationTask

from ..managers.curation_task_manager import CurationTaskManager
from .tool_service import with_synapse_client


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
    """Serialize a CurationTask model object into a response dictionary."""
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
    """Orchestrates curation task operations and shapes tool responses.

    Uses CurationTaskManager for Synapse API calls and is responsible for
    translating the results into the dictionaries returned by MCP tools.
    """

    def list_tasks(self, ctx: Context, project_id: str) -> List[Dict[str, Any]]:
        """List all curation tasks for a project."""
        result = with_synapse_client(
            ctx,
            lambda client: [
                _format_task(task)
                for task in CurationTaskManager(client).list_tasks(project_id)
            ],
            error_context={"project_id": project_id},
        )
        return result if isinstance(result, list) else [result]

    def get_task(self, ctx: Context, task_id: int) -> Dict[str, Any]:
        """Retrieve a single curation task by ID."""
        return with_synapse_client(
            ctx,
            lambda client: _format_task(
                CurationTaskManager(client).get_task(task_id)
            ),
            error_context={"task_id": task_id},
        )

    def get_task_resources(self, ctx: Context, task_id: int) -> Dict[str, Any]:
        """Retrieve a curation task and its associated Synapse resources."""

        def _fetch(client: Any) -> Dict[str, Any]:
            manager = CurationTaskManager(client)
            task = manager.get_task(task_id)

            result: Dict[str, Any] = {
                "task_id": task.task_id,
                "data_type": task.data_type,
                "project_id": task.project_id,
                "instructions": task.instructions,
                "resources": {},
            }

            if hasattr(task.task_properties, "upload_folder_id"):
                self._populate_file_based_resources(
                    manager, task, result["resources"]
                )
            elif hasattr(task.task_properties, "record_set_id"):
                self._populate_record_based_resources(
                    manager, task, result["resources"]
                )

            return result

        return with_synapse_client(
            ctx, _fetch, error_context={"task_id": task_id}
        )

    @staticmethod
    def _populate_file_based_resources(
        manager: CurationTaskManager,
        task: CurationTask,
        resources: Dict[str, Any],
    ) -> None:
        """Populate resources dict for a file-based curation task."""
        resources["type"] = "file-based"
        upload_folder_id = task.task_properties.upload_folder_id
        file_view_id = task.task_properties.file_view_id

        if upload_folder_id:
            try:
                resources["upload_folder"] = manager.get_folder(upload_folder_id)
            except Exception as exc:
                resources["upload_folder"] = {
                    "error": str(exc),
                    "id": upload_folder_id,
                }

        if file_view_id:
            try:
                resources["file_view"] = manager.get_entity_view(file_view_id)
            except Exception as exc:
                resources["file_view"] = {
                    "error": str(exc),
                    "id": file_view_id,
                }

    @staticmethod
    def _populate_record_based_resources(
        manager: CurationTaskManager,
        task: CurationTask,
        resources: Dict[str, Any],
    ) -> None:
        """Populate resources dict for a record-based curation task."""
        resources["type"] = "record-based"
        record_set_id = task.task_properties.record_set_id

        if record_set_id:
            try:
                resources["record_set"] = manager.get_record_set(record_set_id)
            except Exception as exc:
                resources["record_set"] = {
                    "error": str(exc),
                    "id": record_set_id,
                }
