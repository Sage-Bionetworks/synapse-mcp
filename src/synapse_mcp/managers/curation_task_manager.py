"""Manager layer for CurationTask Synapse API interactions.

This module owns all raw interactions with the Synapse API for CurationTask
objects, including fetching tasks, listing tasks, and retrieving associated
resources (Folders, EntityViews, RecordSets).
"""

import synapseclient
from typing import Any, Dict, Iterator, List

from synapseclient.models import CurationTask, EntityView, Folder, RecordSet


class CurationTaskManager:
    """Handles direct Synapse API calls related to CurationTask objects.

    This is the manager layer — it speaks directly to synapseclient and
    returns raw model objects or minimally processed data. It has no
    knowledge of MCP tool response shapes.
    """

    def __init__(self, synapse_client: synapseclient.Synapse) -> None:
        """Initialize with an authenticated Synapse client.

        Args:
            synapse_client: An authenticated synapseclient.Synapse instance.
        """
        self.synapse_client = synapse_client

    def list_tasks(self, project_id: str) -> Iterator[CurationTask]:
        """Yield all CurationTask objects for the given project.

        Args:
            project_id: The Synapse ID of the project.

        Yields:
            CurationTask instances for the project.
        """
        yield from CurationTask.list(
            project_id=project_id, synapse_client=self.synapse_client
        )

    def get_task(self, task_id: int) -> CurationTask:
        """Fetch a single CurationTask by its numeric ID.

        Args:
            task_id: The numeric ID of the curation task.

        Returns:
            The fetched CurationTask instance.
        """
        return CurationTask(task_id=task_id).get(synapse_client=self.synapse_client)

    def get_folder(self, folder_id: str) -> Any:
        """Fetch a Folder entity by its Synapse ID.

        Args:
            folder_id: The Synapse ID of the folder.

        Returns:
            The fetched Folder instance.
        """
        return Folder(id=folder_id).get(synapse_client=self.synapse_client)

    def get_entity_view(self, view_id: str) -> Any:
        """Fetch an EntityView by its Synapse ID.

        Args:
            view_id: The Synapse ID of the entity view.

        Returns:
            The fetched EntityView instance.
        """
        return EntityView(id=view_id).get(synapse_client=self.synapse_client)

    def get_record_set(self, record_set_id: str) -> Any:
        """Fetch a RecordSet by its Synapse ID.

        Args:
            record_set_id: The Synapse ID of the record set.

        Returns:
            The fetched RecordSet instance (without downloading file content).
        """
        return RecordSet(id=record_set_id, download_file=False).get(
            synapse_client=self.synapse_client
        )
