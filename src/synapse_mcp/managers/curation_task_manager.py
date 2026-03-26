"""Manager for multi-step CurationTask API orchestration."""

from typing import Any, Dict, Tuple

import synapseclient
from synapseclient.models import CurationTask, EntityView, Folder, RecordSet


class CurationTaskManager:
    """Composes multiple Synapse API calls for curation task resources."""

    def __init__(self, synapse_client: synapseclient.Synapse) -> None:
        self.synapse_client = synapse_client

    def get_task_with_resources(
        self, task_id: int
    ) -> Tuple[CurationTask, Dict[str, Any]]:
        """Fetch a curation task and its associated Synapse resources.

        Returns a (task, resources) tuple. The resources dict contains raw
        model objects on success or error dicts for individual fetch failures.
        Partial failures are captured — one resource failing does not prevent
        others from being fetched.
        """
        task = CurationTask(task_id=task_id).get(
            synapse_client=self.synapse_client
        )

        resources: Dict[str, Any] = {}

        if hasattr(task.task_properties, "record_set_id"):
            self._fetch_record_based_resources(task, resources)
        elif hasattr(task.task_properties, "upload_folder_id"):
            self._fetch_file_based_resources(task, resources)

        return task, resources

    def _fetch_file_based_resources(
        self, task: CurationTask, resources: Dict[str, Any]
    ) -> None:
        resources["type"] = "file-based"
        upload_folder_id = task.task_properties.upload_folder_id
        file_view_id = task.task_properties.file_view_id

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
        resources["type"] = "record-based"
        record_set_id = task.task_properties.record_set_id

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
