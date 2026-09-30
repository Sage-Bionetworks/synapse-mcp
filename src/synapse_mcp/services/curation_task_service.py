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

from ..managers.curation_task_manager import (
    CurationTaskManager,
    RecordBasedTaskCreationError,
)
from ..tool_types import TaskProperties
from .tool_service import (
    dataclass_to_dict,
    error_boundary,
    serialize_model,
    synapse_client,
)

_TASK_PROPERTY_TYPE_LABELS: Dict[type, str] = {
    RecordBasedMetadataTaskProperties: "record-based",
    FileBasedMetadataTaskProperties: "file-based",
}


def _build_task_properties(spec: TaskProperties):
    """Build a task-properties model from a plain dict, or an error dict.

    Record-based tasks carry ``record_set_id``; file-based tasks carry
    ``upload_folder_id`` (and optionally ``file_view_id``). The presence
    of ``record_set_id`` selects record-based; otherwise file-based.
    The two shapes are mutually exclusive.
    """
    if spec.get("record_set_id") and spec.get("upload_folder_id"):
        return {
            "error": (
                "task_properties must include either 'record_set_id' "
                "(record-based) or 'upload_folder_id' (file-based), "
                "not both."
            )
        }
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
        task_properties: TaskProperties,
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
            return {
                "error_type": "ValueError",
                **props,
                "project_id": project_id,
                "data_type": data_type,
            }
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
    @error_boundary(error_context_keys=("folder_id", "data_type", "schema_uri"))
    async def create_record_based_task(
        ctx: Context,
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
    ) -> Dict[str, Any]:
        """Create a RecordSet templated from a JSON schema plus a task on it.

        The RecordSet's CSV is a header-only template the server generates
        from the schema's properties; no caller-supplied file content is
        uploaded.

        Arguments:
            ctx: The FastMCP request context.
            folder_id: Folder that will hold the RecordSet (e.g. syn123456).
            record_set_name: Name for the new RecordSet entity.
            data_type: The data type the task curates; unique per project.
            schema_uri: Registered JSON schema $id to template from.
            upsert_keys: Schema properties that uniquely identify a record.
            instructions: Curator instructions.
            record_set_description: Optional RecordSet description.
            bind_schema: Bind the schema to the RecordSet for validation.
            enable_derived_annotations: Enable derived annotations on bind.
            assignee_principal_id: Optional user or team to assign the task to.

        Returns:
            Dict with the created ``record_set`` and ``curation_task``.
        """
        async with synapse_client(ctx) as client:
            mgr = CurationTaskManager(client)
            try:
                record_set, task = await mgr.create_record_based_task(
                    folder_id=folder_id,
                    record_set_name=record_set_name,
                    data_type=data_type,
                    schema_uri=schema_uri,
                    upsert_keys=upsert_keys,
                    instructions=instructions,
                    record_set_description=record_set_description,
                    bind_schema=bind_schema,
                    enable_derived_annotations=enable_derived_annotations,
                    assignee_principal_id=assignee_principal_id,
                )
            except RecordBasedTaskCreationError as exc:
                return {
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                    "record_set_id": exc.record_set_id,
                    "folder_id": folder_id,
                    "data_type": data_type,
                    "schema_uri": schema_uri,
                }
            record_set_dict = serialize_model(record_set)
            # ``path`` is the server's temp file, already deleted; not useful.
            record_set_dict.pop("path", None)
            return {
                "record_set": record_set_dict,
                "curation_task": _format_task(task),
                "schema_bound": bind_schema,
            }

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
