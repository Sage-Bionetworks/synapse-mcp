"""Manager for CurationTask API calls and data conversion."""

from typing import Any, Dict, List

import synapseclient
from synapseclient.models import CurationTask, EntityView, Folder, RecordSet


class CurationTaskManager:
    """Handles CurationTask Synapse API interactions and model-to-dict conversion."""

    def __init__(self, synapse_client: synapseclient.Synapse) -> None:
        self.synapse_client = synapse_client

    @staticmethod
    def _task_to_dict(task: CurationTask) -> Dict[str, Any]:
        """Convert a CurationTask model to a plain dictionary."""
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

        if task.task_properties:
            task_dict["task_properties"] = {}
            if hasattr(task.task_properties, "record_set_id"):
                task_dict["task_properties"]["type"] = "record-based"
                task_dict["task_properties"]["record_set_id"] = (
                    task.task_properties.record_set_id
                )
            elif hasattr(task.task_properties, "upload_folder_id"):
                task_dict["task_properties"]["type"] = "file-based"
                task_dict["task_properties"]["upload_folder_id"] = (
                    task.task_properties.upload_folder_id
                )
                task_dict["task_properties"]["file_view_id"] = (
                    task.task_properties.file_view_id
                )

        return task_dict

    def list_tasks(self, project_id: str) -> List[Dict[str, Any]]:
        """List all curation tasks for a project."""
        return [
            self._task_to_dict(task)
            for task in CurationTask.list(
                project_id=project_id, synapse_client=self.synapse_client
            )
        ]

    def get_task(self, task_id: int) -> Dict[str, Any]:
        """Get a single curation task by ID."""
        task = CurationTask(task_id=task_id).get(
            synapse_client=self.synapse_client
        )
        return self._task_to_dict(task)

    def get_task_resources(self, task_id: int) -> Dict[str, Any]:
        """Get a task and its associated resources (folder/view or record set)."""
        task = CurationTask(task_id=task_id).get(
            synapse_client=self.synapse_client
        )

        result: Dict[str, Any] = {
            "task_id": task.task_id,
            "data_type": task.data_type,
            "project_id": task.project_id,
            "instructions": task.instructions,
            "resources": {},
        }

        if hasattr(task.task_properties, "upload_folder_id"):
            self._fetch_file_based_resources(task, result["resources"])
        elif hasattr(task.task_properties, "record_set_id"):
            self._fetch_record_based_resources(task, result["resources"])

        return result

    def _fetch_file_based_resources(
        self, task: CurationTask, resources: Dict[str, Any]
    ) -> None:
        upload_folder_id = task.task_properties.upload_folder_id
        file_view_id = task.task_properties.file_view_id
        resources["type"] = "file-based"

        if upload_folder_id:
            try:
                resources["upload_folder"] = Folder(id=upload_folder_id).get(
                    synapse_client=self.synapse_client
                )
            except Exception as exc:
                resources["upload_folder"] = {
                    "error": str(exc),
                    "id": upload_folder_id,
                }

        if file_view_id:
            try:
                resources["file_view"] = EntityView(id=file_view_id).get(
                    synapse_client=self.synapse_client
                )
            except Exception as exc:
                resources["file_view"] = {
                    "error": str(exc),
                    "id": file_view_id,
                }

    def _fetch_record_based_resources(
        self, task: CurationTask, resources: Dict[str, Any]
    ) -> None:
        record_set_id = task.task_properties.record_set_id
        resources["type"] = "record-based"

        if record_set_id:
            try:
                resources["record_set"] = RecordSet(
                    id=record_set_id, download_file=False
                ).get(synapse_client=self.synapse_client)
            except Exception as exc:
                resources["record_set"] = {
                    "error": str(exc),
                    "id": record_set_id,
                }
