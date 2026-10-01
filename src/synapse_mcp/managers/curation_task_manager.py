"""Manager for multi-step CurationTask API orchestration."""

import csv
import os
import re
import tempfile
from typing import Any, Dict, List, Optional, Tuple

import synapseclient
from synapseclient.models import (
    CurationTask,
    EntityView,
    FileBasedMetadataTaskProperties,
    Folder,
    JSONSchema,
    RecordBasedMetadataTaskProperties,
    RecordSet,
)


class RecordBasedTaskCreationError(Exception):
    """A step failed after the RecordSet was already created.

    Carries ``record_set_id`` so the caller can report (and the user can
    clean up) the orphaned RecordSet.
    """

    def __init__(
        self,
        message: str,
        record_set_id: str,
        status_code: Optional[int] = None,
    ) -> None:
        super().__init__(message)
        self.record_set_id = record_set_id
        self.status_code = status_code


# Max bytes for the temp CSV's base name; filesystems cap a path component at
# 255 bytes, and RecordSet names can be long or multibyte.
_MAX_CSV_NAME_BYTES = 100


def _csv_file_name(record_set_name: str) -> str:
    """Filesystem-safe, length-bounded CSV file name for a RecordSet."""
    safe = re.sub(r"[^\w.\-() +]", "_", record_set_name).strip() or "recordset"
    safe = safe.encode("utf-8")[:_MAX_CSV_NAME_BYTES].decode("utf-8", errors="ignore")
    return safe + ".csv"


def _template_columns(schema_body: Dict[str, Any], upsert_keys: List[str]) -> List[str]:
    """Column headers for a RecordSet template: schema properties, upsert keys first.

    Raises ``ValueError`` if the schema has no properties, an upsert key is
    repeated, or an upsert key is not one of the properties.
    """
    repeated = sorted({key for key in upsert_keys if upsert_keys.count(key) > 1})
    if repeated:
        raise ValueError(f"upsert_keys contains repeated keys: {repeated}")
    properties = list((schema_body.get("properties") or {}).keys())
    if not properties:
        raise ValueError("The JSON schema defines no properties to build a template from.")
    missing = [key for key in upsert_keys if key not in properties]
    if missing:
        raise ValueError(
            f"upsert_keys not found among the schema properties: {missing}. "
            f"Available properties: {properties}"
        )
    if len(upsert_keys) != len(set(upsert_keys)):
        raise ValueError("upsert_keys must contain distinct schema properties.")
    return list(upsert_keys) + [p for p in properties if p not in upsert_keys]


class CurationTaskManager:
    """Composes multiple Synapse API calls for curation task resources."""

    def __init__(self, synapse_client: synapseclient.Synapse) -> None:
        self.synapse_client = synapse_client

    async def get_task_with_resources(
        self, task_id: int
    ) -> Tuple[CurationTask, Dict[str, Any]]:
        """Fetch a curation task and its associated Synapse resources.

        Args:
            task_id: Numeric curation task identifier.

        Returns a (task, resources) tuple. The resources dict contains raw
        model objects on success or error dicts for individual fetch failures.
        Partial failures are captured — one resource failing does not prevent
        others from being fetched.
        """
        task = await CurationTask(task_id=task_id).get_async(
            synapse_client=self.synapse_client
        )

        resources: Dict[str, Any] = {}

        if isinstance(task.task_properties, RecordBasedMetadataTaskProperties):
            await self._fetch_record_based_resources(task, resources)
        elif isinstance(task.task_properties, FileBasedMetadataTaskProperties):
            await self._fetch_file_based_resources(task, resources)

        return task, resources

    async def create_record_based_task(
        self,
        folder_id: str,
        record_set_name: str,
        data_type: str,
        schema_uri: str,
        upsert_keys: List[str],
        instructions: str,
        record_set_description: Optional[str] = None,
        bind_schema: bool = True,
        enable_derived_annotations: bool = False,
        assignee_principal_id: Optional[str] = None,
    ) -> Tuple[RecordSet, CurationTask]:
        """Create a schema-templated RecordSet and a record-based task on it.

        Mirrors ``synapseclient.extensions.curator.create_record_based_metadata_task``
        but runs async and skips the deprecated Grid creation. Steps:

        1. Resolve the folder's project (also verifies the folder is visible)
           and refuse if the project already has a task for ``data_type``.
        2. Fetch the registered JSON schema and build header-only CSV columns
           from its properties, upsert keys first.
        3. Store the template as a RecordSet under ``folder_id``.
        4. Optionally bind the schema to the RecordSet.
        5. Create the curation task pointing at the RecordSet.

        Steps 1-2 fail before anything is written. A failure in step 4 or 5
        raises ``RecordBasedTaskCreationError`` carrying the RecordSet ID.
        """
        path = await self.synapse_client.rest_get_async(f"/entity/{folder_id}/path")
        # path[0] is the root; path[1] is the project that owns the folder.
        project_id = path["path"][1]["id"]

        # CurationTask.store_async upserts on (project_id, data_type): an
        # existing task would be updated in place, keeping its own RecordSet
        # and orphaning the new one. Refuse instead.
        async for existing in CurationTask.list_async(
            project_id=project_id, synapse_client=self.synapse_client
        ):
            if existing.data_type == data_type:
                raise ValueError(
                    f"Project {project_id} already has a curation task "
                    f"(task_id {existing.task_id}) for data_type "
                    f"'{data_type}'. Choose a different data_type."
                )

        schema = JSONSchema.from_uri(schema_uri)
        await schema.get_async(synapse_client=self.synapse_client)
        body = await schema.get_body_async(synapse_client=self.synapse_client)
        columns = _template_columns(body, upsert_keys)

        with tempfile.TemporaryDirectory() as tmp_dir:
            csv_path = os.path.join(tmp_dir, _csv_file_name(record_set_name))
            with open(csv_path, "w", encoding="utf-8", newline="") as f:
                csv.writer(f).writerow(columns)
            record_set = await RecordSet(
                name=record_set_name,
                parent_id=folder_id,
                description=record_set_description,
                path=csv_path,
                upsert_keys=list(upsert_keys),
            ).store_async(synapse_client=self.synapse_client)

        try:
            if bind_schema:
                await record_set.bind_schema_async(
                    json_schema_uri=schema_uri,
                    enable_derived_annotations=enable_derived_annotations,
                    synapse_client=self.synapse_client,
                )
            task = await CurationTask(
                project_id=project_id,
                data_type=data_type,
                instructions=instructions,
                assignee_principal_id=assignee_principal_id,
                task_properties=RecordBasedMetadataTaskProperties(
                    record_set_id=record_set.id,
                ),
            ).store_async(synapse_client=self.synapse_client)
        except Exception as exc:
            response = getattr(exc, "response", None)
            raise RecordBasedTaskCreationError(
                f"RecordSet {record_set.id} was created, but a later step "
                f"failed: {exc}",
                record_set_id=record_set.id,
                status_code=getattr(response, "status_code", None),
            ) from exc

        return record_set, task

    async def _fetch_file_based_resources(
        self, task: CurationTask, resources: Dict[str, Any]
    ) -> None:
        resources["type"] = "file-based"
        upload_folder_id = task.task_properties.upload_folder_id
        file_view_id = task.task_properties.file_view_id

        if upload_folder_id:
            try:
                resources["upload_folder"] = await Folder(id=upload_folder_id).get_async(
                    synapse_client=self.synapse_client
                )
            except Exception as exc:
                resources["upload_folder"] = {
                    "error": str(exc),
                    "id": upload_folder_id,
                }

        if file_view_id:
            try:
                resources["file_view"] = await EntityView(id=file_view_id).get_async(
                    synapse_client=self.synapse_client
                )
            except Exception as exc:
                resources["file_view"] = {
                    "error": str(exc),
                    "id": file_view_id,
                }

    async def _fetch_record_based_resources(
        self, task: CurationTask, resources: Dict[str, Any]
    ) -> None:
        resources["type"] = "record-based"
        record_set_id = task.task_properties.record_set_id

        if record_set_id:
            try:
                resources["record_set"] = await RecordSet(
                    id=record_set_id, download_file=False
                ).get_async(synapse_client=self.synapse_client)
            except Exception as exc:
                resources["record_set"] = {
                    "error": str(exc),
                    "id": record_set_id,
                }
