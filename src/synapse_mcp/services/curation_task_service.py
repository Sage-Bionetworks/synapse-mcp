"""Service layer for curation task operations.

This module orchestrates CurationTaskManager calls and translates
CurationTask model objects into tool-friendly response dictionaries.
It owns the serialization logic and response shaping for all three
curation task tools.
"""

import synapseclient
from typing import Any, Dict, List

from synapseclient.models import CurationTask

from ..managers.curation_task_manager import CurationTaskManager


def _format_task_properties(task_properties: Any) -> Dict[str, Any]:
    """Serialize task_properties into a typed dictionary.

    Args:
        task_properties: The task_properties attribute of a CurationTask.

    Returns:
        A dictionary describing the task properties type and its fields,
        or an empty dict if task_properties is None.
    """
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
    """Serialize a CurationTask model object into a response dictionary.

    Args:
        task: A CurationTask instance.

    Returns:
        A dictionary containing the task's metadata and properties.
    """
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

    This is the service layer — it uses CurationTaskManager for Synapse API
    calls and is responsible for translating the results into the dictionaries
    returned by MCP tools.
    """

    def __init__(self, synapse_client: synapseclient.Synapse) -> None:
        """Initialize with an authenticated Synapse client.

        Args:
            synapse_client: An authenticated synapseclient.Synapse instance.
        """
        self._manager = CurationTaskManager(synapse_client)

    def list_tasks(self, project_id: str) -> List[Dict[str, Any]]:
        """List all curation tasks for a project.

        Args:
            project_id: The Synapse ID of the project.

        Returns:
            A list of serialized curation task dictionaries.
        """
        return [_format_task(task) for task in self._manager.list_tasks(project_id)]

    def get_task(self, task_id: int) -> Dict[str, Any]:
        """Retrieve a single curation task by ID.

        Args:
            task_id: The numeric ID of the curation task.

        Returns:
            A serialized curation task dictionary.
        """
        task = self._manager.get_task(task_id)
        return _format_task(task)

    def get_task_resources(self, task_id: int) -> Dict[str, Any]:
        """Retrieve a curation task and its associated Synapse resources.

        For file-based tasks, fetches the upload Folder and EntityView.
        For record-based tasks, fetches the RecordSet.

        Args:
            task_id: The numeric ID of the curation task.

        Returns:
            A dictionary with task metadata and a 'resources' sub-dict
            describing the associated Synapse entities.
        """
        task = self._manager.get_task(task_id)

        result: Dict[str, Any] = {
            "task_id": task.task_id,
            "data_type": task.data_type,
            "project_id": task.project_id,
            "instructions": task.instructions,
            "resources": {},
        }

        if hasattr(task.task_properties, "upload_folder_id"):
            self._populate_file_based_resources(task, result["resources"])
        elif hasattr(task.task_properties, "record_set_id"):
            self._populate_record_based_resources(task, result["resources"])

        return result

    def _populate_file_based_resources(
        self, task: CurationTask, resources: Dict[str, Any]
    ) -> None:
        """Populate resources dict for a file-based curation task.

        Args:
            task: The CurationTask with file-based properties.
            resources: The resources dict to populate in-place.
        """
        resources["type"] = "file-based"
        upload_folder_id = task.task_properties.upload_folder_id
        file_view_id = task.task_properties.file_view_id

        if upload_folder_id:
            try:
                resources["upload_folder"] = self._manager.get_folder(upload_folder_id)
            except Exception as exc:
                resources["upload_folder"] = {
                    "error": str(exc),
                    "id": upload_folder_id,
                }

        if file_view_id:
            try:
                resources["file_view"] = self._manager.get_entity_view(file_view_id)
            except Exception as exc:
                resources["file_view"] = {
                    "error": str(exc),
                    "id": file_view_id,
                }

    def _populate_record_based_resources(
        self, task: CurationTask, resources: Dict[str, Any]
    ) -> None:
        """Populate resources dict for a record-based curation task.

        Args:
            task: The CurationTask with record-based properties.
            resources: The resources dict to populate in-place.
        """
        resources["type"] = "record-based"
        record_set_id = task.task_properties.record_set_id

        if record_set_id:
            try:
                resources["record_set"] = self._manager.get_record_set(record_set_id)
            except Exception as exc:
                resources["record_set"] = {
                    "error": str(exc),
                    "id": record_set_id,
                }
