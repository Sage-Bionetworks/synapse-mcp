"""Manager layer for CurationTask Synapse API interactions.

This module owns all raw interactions with the Synapse API for CurationTask
objects.  It returns raw model objects (not dicts) so the service layer can
decide how to serialize them.
"""

from typing import Any, Iterator

import synapseclient
from synapseclient.models import CurationTask, EntityView, Folder, RecordSet


class CurationTaskManager:
    """Handles direct Synapse API calls related to CurationTask objects."""

    def __init__(self, synapse_client: synapseclient.Synapse) -> None:
        self.synapse_client = synapse_client

    def list_tasks(self, project_id: str) -> Iterator[CurationTask]:
        """Yield all CurationTask objects for the given project."""
        yield from CurationTask.list(
            project_id=project_id, synapse_client=self.synapse_client
        )

    def get_task(self, task_id: int) -> CurationTask:
        """Fetch a single CurationTask by its numeric ID."""
        return CurationTask(task_id=task_id).get(synapse_client=self.synapse_client)

    def get_folder(self, folder_id: str) -> Any:
        """Fetch a Folder entity by its Synapse ID."""
        return Folder(id=folder_id).get(synapse_client=self.synapse_client)

    def get_entity_view(self, view_id: str) -> Any:
        """Fetch an EntityView by its Synapse ID."""
        return EntityView(id=view_id).get(synapse_client=self.synapse_client)

    def get_record_set(self, record_set_id: str) -> Any:
        """Fetch a RecordSet by its Synapse ID."""
        return RecordSet(id=record_set_id, download_file=False).get(
            synapse_client=self.synapse_client
        )
