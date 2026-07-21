"""Service layer for entity operations.

Handles get, annotations, children, ACL, permissions,
schema, and container operations for any Synapse entity.
Uses synapseclient.operations and model classes (never
legacy Synapse.get / getChildren / get_annotations).
"""

from typing import Any, Dict, List, Optional, Union

from fastmcp import Context
from synapseclient.models import (
    Column,
    ColumnType,
    Dataset,
    DatasetCollection,
    DockerRepository,
    EntityView,
    File,
    Folder,
    Link,
    MaterializedView,
    Project,
    RecordSet,
    SubmissionView,
    Table,
    VirtualTable,
    ViewTypeMask,
)
from synapseclient.models.activity import Activity, UsedEntity, UsedURL
from synapseclient.operations import get_async as operations_get_async
from synapseclient.operations.factory_operations import (
    FileOptions,
    LinkOptions,
)

from ..tool_types import (
    UNSET,
    ColumnSpec,
    EntityAccessType,
    EntityType,
    ProvenanceSpec,
    ViewScopeType,
)
from .tool_service import (
    error_boundary,
    serialize_model,
    synapse_client,
)

# Entity types that can be created with metadata only (no file upload).
# ``file`` and ``recordset`` are handled separately: each requires an external
# URL or an existing file handle to avoid a data upload.
_CONTAINER_ENTITY_TYPES = {
    "project": Project,
    "folder": Folder,
    "dataset": Dataset,
    "datasetcollection": DatasetCollection,
    "entityview": EntityView,
    "table": Table,
    "materializedview": MaterializedView,
    "virtualtable": VirtualTable,
    "submissionview": SubmissionView,
    "dockerrepository": DockerRepository,
}

async def _resolve_entity(entity_id: str, client):
    """Fetch an entity and return an instance of its concrete subclass.

    ACL / permissions / schema methods are defined on the typed
    subclass (Project, Folder, File, Table, ...); instantiating a
    File for every ID is wrong when the target is a Project or
    Folder. Resolve the concrete class via ``operations.get()``
    once, then the caller invokes the model method on the right
    type.
    """
    return await operations_get_async(
        entity_id,
        file_options=FileOptions(download_file=False),
        synapse_client=client,
    )


# Child list attributes on Folder/Project containers populated by
# ``sync_from_synapse_async``. Mirrors the SDK default include-types in
# ``synapseclient/models/storable_container.py``; if the SDK adds a new
# concrete type to that default, the corresponding attribute name must be
# appended here. The authoritative server-side enum lives at
# https://rest-docs.synapse.org/rest/org/sagebionetworks/repo/model/EntityType.html
# but is not exported as a Python constant by the SDK, so we keep this
# tuple manually synced.
_CONTAINER_CHILD_ATTRS = (
    "files",
    "folders",
    "tables",
    "entityviews",
    "submissionviews",
    "datasets",
    "datasetcollections",
    "materializedviews",
    "virtualtables",
    "dockerrepos",
)


class EntityService:
    """Orchestrates entity read operations."""

    @staticmethod
    @error_boundary(error_context_keys=("entity_id",))
    async def get_entity(
        ctx: Context, entity_id: str
    ) -> Dict[str, Any]:
        """Get entity metadata by Synapse ID.

        Uses ``synapseclient.operations.get()`` which
        auto-detects the entity type and returns the proper
        typed dataclass. File content is never downloaded.

        Arguments:
            ctx: The FastMCP request context.
            entity_id: Synapse ID (e.g. ``"syn123"``).

        Returns:
            Dict with entity metadata (id, name, type,
            parentId, timestamps, etc.).
        """
        async with synapse_client(ctx) as client:
            entity = await operations_get_async(
                entity_id,
                file_options=FileOptions(
                    download_file=False,
                ),
                synapse_client=client,
            )
            return serialize_model(entity)

    @staticmethod
    @error_boundary(error_context_keys=("entity_id",))
    async def get_annotations(
        ctx: Context, entity_id: str
    ) -> Dict[str, Any]:
        """Get custom annotations for an entity.

        Retrieves the full entity via ``operations.get()``
        then reads ``.annotations`` from the returned
        dataclass.

        Arguments:
            ctx: The FastMCP request context.
            entity_id: Synapse ID (e.g. ``"syn123"``).

        Returns:
            Dict mapping annotation keys to their values.
        """
        async with synapse_client(ctx) as client:
            entity = await operations_get_async(
                entity_id,
                file_options=FileOptions(
                    download_file=False,
                ),
                synapse_client=client,
            )
            annotations = getattr(entity, "annotations", None)
            if annotations is None:
                return {}
            return serialize_model(annotations)

    @staticmethod
    @error_boundary(
        error_context_keys=("entity_id",),
        wrap_errors=True,
    )
    async def get_children(
        ctx: Context, entity_id: str
    ) -> List[Dict[str, Any]]:
        """List all immediate children of a container entity.

        Uses ``sync_from_synapse_async(recursive=False)`` to
        populate every child list (files, folders, tables,
        views, datasets, etc.) without downloading content.

        Arguments:
            ctx: The FastMCP request context.
            entity_id: Synapse ID of a Project or Folder.

        Returns:
            List of child entity dicts covering all entity
            types. Returns an error dict inside a list if
            the entity is not a container.
        """
        async with synapse_client(ctx) as client:
            container = Folder(id=entity_id)
            await container.sync_from_synapse_async(
                download_file=False,
                recursive=False,
                synapse_client=client,
            )
            children: List[Dict[str, Any]] = []
            for attr in _CONTAINER_CHILD_ATTRS:
                for item in getattr(container, attr, []) or []:
                    children.append(serialize_model(item))
            return children

    @staticmethod
    @error_boundary(error_context_keys=("entity_id",))
    async def get_acl(
        ctx: Context,
        entity_id: str,
        principal_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Get the access control list for an entity.

        Arguments:
            ctx: The FastMCP request context.
            entity_id: Synapse ID (e.g. ``"syn123"``).
            principal_id: Optional user/group ID to filter
                the ACL for. Defaults to PUBLIC.

        Returns:
            Dict with entity_id, principal_id, and a list
            of access_types (e.g. READ, UPDATE, DELETE).
        """
        async with synapse_client(ctx) as client:
            entity = await _resolve_entity(entity_id, client)
            access_types = await entity.get_acl_async(
                principal_id=principal_id,
                synapse_client=client,
            )
            return {
                "entity_id": entity_id,
                "principal_id": principal_id,
                "access_types": access_types,
            }

    @staticmethod
    @error_boundary(error_context_keys=("entity_id",))
    async def get_permissions(
        ctx: Context, entity_id: str
    ) -> Dict[str, Any]:
        """Get current user's permissions on an entity.

        Arguments:
            ctx: The FastMCP request context.
            entity_id: Synapse ID (e.g. ``"syn123"``).

        Returns:
            Dict with entity_id and boolean permission
            flags (can_view, can_edit, can_download, etc.).
        """
        async with synapse_client(ctx) as client:
            entity = await _resolve_entity(entity_id, client)
            permissions = await entity.get_permissions_async(
                synapse_client=client,
            )
            result = serialize_model(permissions)
            result["entity_id"] = entity_id
            return result

    @staticmethod
    @error_boundary(error_context_keys=("entity_id",))
    async def list_acl(
        ctx: Context,
        entity_id: str,
        recursive: bool = False,
        include_container_content: bool = False,
        target_entity_types: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """List ACLs for an entity (and optionally its descendants).

        Arguments:
            ctx: The FastMCP request context.
            entity_id: Synapse ID (e.g. ``"syn123"``).
            recursive: If True, walk into child containers.
                Must be paired with ``include_container_content=True``;
                the SDK raises ``ValueError`` otherwise.
            include_container_content: If True, include ACLs from
                files/folders directly inside container entities.
                Required for ``recursive`` to have any effect.
            target_entity_types: Optional list of entity types to
                include (e.g. ``["folder", "file"]``). Defaults to
                folders + files when ``None``.

        Returns:
            Dict with entity_acl (current entity's ACL entries) and
            all_entity_acls (descendants if recursive). On error a
            single error dict is returned.
        """
        # Pre-validate the recursive/include_container_content combo so
        # the caller sees a clear error dict rather than a generic
        # ValueError from the SDK boundary.
        if recursive and not include_container_content:
            return {
                "error": (
                    "recursive=True requires include_container_content=True"
                ),
                "entity_id": entity_id,
            }
        async with synapse_client(ctx) as client:
            entity = await _resolve_entity(entity_id, client)
            acl_result = await entity.list_acl_async(
                recursive=recursive,
                include_container_content=include_container_content,
                target_entity_types=target_entity_types,
                synapse_client=client,
            )
            result = serialize_model(acl_result)
            if isinstance(result, dict):
                result["entity_id"] = entity_id
            return result

    @staticmethod
    @error_boundary(error_context_keys=("entity_id",))
    async def get_schema(
        ctx: Context, entity_id: str
    ) -> Dict[str, Any]:
        """Get the bound JSON schema for an entity.

        Arguments:
            ctx: The FastMCP request context.
            entity_id: Synapse ID of an entity with a
                bound JSON schema.

        Returns:
            Dict with JSON schema binding info
            (organization, schema name, version, etc.).
        """
        async with synapse_client(ctx) as client:
            entity = await _resolve_entity(entity_id, client)
            schema_info = await entity.get_schema_async(
                synapse_client=client,
            )
            result = serialize_model(schema_info)
            if isinstance(result, dict):
                result["entity_id"] = entity_id
            return result

    @staticmethod
    @error_boundary(error_context_keys=("entity_id",))
    async def get_schema_derived_keys(
        ctx: Context, entity_id: str
    ) -> Dict[str, Any]:
        """Get derived annotation keys from a bound schema.

        Arguments:
            ctx: The FastMCP request context.
            entity_id: Synapse ID of an entity with a
                bound JSON schema.

        Returns:
            Dict with entity_id and a list of
            derived_keys.
        """
        async with synapse_client(ctx) as client:
            entity = await _resolve_entity(entity_id, client)
            keys = await entity.get_schema_derived_keys_async(
                synapse_client=client,
            )
            return {
                "entity_id": entity_id,
                "derived_keys": serialize_model(keys),
            }

    @staticmethod
    @error_boundary(error_context_keys=("entity_id",))
    async def get_schema_validation_statistics(
        ctx: Context, entity_id: str
    ) -> Dict[str, Any]:
        """Get schema validation stats for a container.

        Arguments:
            ctx: The FastMCP request context.
            entity_id: Synapse ID of a Folder or Project
                with a bound JSON schema.

        Returns:
            Dict with validation statistics (counts of
            valid, invalid, unknown entities).
        """
        async with synapse_client(ctx) as client:
            container = Folder(id=entity_id)
            stats = await container.get_schema_validation_statistics_async(
                synapse_client=client,
            )
            result = serialize_model(stats)
            if isinstance(result, dict):
                result["entity_id"] = entity_id
            return result

    @staticmethod
    @error_boundary(
        error_context_keys=("entity_id",),
        wrap_errors=True,
    )
    async def get_schema_invalid_validations(
        ctx: Context, entity_id: str
    ) -> List[Dict[str, Any]]:
        """Get invalid validation results for a container.

        Arguments:
            ctx: The FastMCP request context.
            entity_id: Synapse ID of a Folder or Project
                with a bound JSON schema.

        Returns:
            List of dicts describing entities that failed
            validation.
        """
        async with synapse_client(ctx) as client:
            container = Folder(id=entity_id)
            # ``get_invalid_validation_async`` is an AsyncGenerator,
            # not a coroutine — drive it with ``async for`` rather
            # than awaiting it.
            return [
                serialize_model(item)
                async for item in container.get_invalid_validation_async(
                    synapse_client=client,
                )
            ]

    @staticmethod
    @error_boundary(error_context_keys=("entity_id",))
    async def get_link(
        ctx: Context,
        entity_id: str,
        follow_link: bool = True,
    ) -> Dict[str, Any]:
        """Resolve a Link entity to its target.

        Uses ``operations.get()`` with ``LinkOptions`` and
        ``FileOptions(download_file=False)`` to safely
        resolve links without downloading files.

        Arguments:
            ctx: The FastMCP request context.
            entity_id: Synapse ID of a Link entity.
            follow_link: If True (default), resolves to
                the target entity. If False, returns the
                Link metadata itself.

        Returns:
            Dict with the resolved target entity or the
            Link entity metadata.
        """
        async with synapse_client(ctx) as client:
            resolved = await operations_get_async(
                entity_id,
                link_options=LinkOptions(
                    follow_link=follow_link,
                ),
                file_options=FileOptions(
                    download_file=False,
                ),
                synapse_client=client,
            )
            return serialize_model(resolved)

    @staticmethod
    @error_boundary(error_context_keys=("entity_type", "parent_id"))
    async def create_entity(
        ctx: Context,
        entity_type: EntityType,
        name: str,
        parent_id: Optional[str] = None,
        description: Optional[str] = None,
        annotations: Optional[Dict[str, List[Any]]] = None,
        columns: Optional[List[ColumnSpec]] = None,
        defining_sql: Optional[str] = None,
        view_type_mask: Optional[List[ViewScopeType]] = None,
        scope_ids: Optional[List[str]] = None,
        target_id: Optional[str] = None,
        target_version_number: Optional[int] = None,
        external_url: Optional[str] = None,
        data_file_handle_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a new Synapse entity from metadata (no file upload).

        Dispatches on ``entity_type`` to the concrete model class and
        stores it. File data is never uploaded: ``file`` and ``recordset``
        entities can only be created from an ``external_url`` (external
        link, file only) or an existing ``data_file_handle_id`` — never
        from local file content.

        Arguments:
            ctx: The FastMCP request context.
            entity_type: The entity type to create.
            name: Entity name.
            parent_id: Parent container Synapse ID. Required for every
                type except project.
            description: Optional entity description.
            annotations: Optional annotations; each key maps to a list of
                values.
            columns: Column definitions for table-like entities.
            defining_sql: SQL for materializedview / virtualtable.
            view_type_mask: Scope types for view/dataset entities
                (e.g. ["file", "folder"]).
            scope_ids: Container IDs an entityview scopes over.
            target_id: For link entities, the entity the link points at.
            target_version_number: Optional pinned version for a link.
            external_url: For file entities, the external URL to link to.
            data_file_handle_id: For file/recordset entities, an existing
                file handle ID to attach.

        Returns:
            Dict with the created entity's metadata (id, name, etc.).
        """
        etype = entity_type.strip().lower().replace("_", "")
        model = EntityService._build_new_entity(
            etype=etype,
            name=name,
            parent_id=parent_id,
            description=description,
            annotations=annotations,
            columns=columns,
            defining_sql=defining_sql,
            view_type_mask=view_type_mask,
            scope_ids=scope_ids,
            target_id=target_id,
            target_version_number=target_version_number,
            external_url=external_url,
            data_file_handle_id=data_file_handle_id,
        )
        if isinstance(model, dict):  # validation error
            return {
                "error_type": "ValueError",
                **model,
                "entity_type": entity_type,
                "parent_id": parent_id,
            }
        async with synapse_client(ctx) as client:
            stored = await model.store_async(synapse_client=client)
            return serialize_model(stored)

    @staticmethod
    def _build_new_entity(
        *,
        etype: str,
        name: str,
        parent_id: Optional[str],
        description: Optional[str],
        annotations: Optional[Dict[str, List[Any]]],
        columns: Optional[List[ColumnSpec]],
        defining_sql: Optional[str],
        view_type_mask: Optional[List[ViewScopeType]],
        scope_ids: Optional[List[str]],
        target_id: Optional[str],
        target_version_number: Optional[int],
        external_url: Optional[str],
        data_file_handle_id: Optional[str],
    ) -> Union[
        Project, Folder, File, Link, RecordSet, Dict[str, Any]
    ]:
        """Construct (but do not store) a model for ``create_entity``.

        Returns the model instance, or an error dict if the inputs are
        invalid for the requested type. Kept separate so the validation
        stays readable and unit-testable without a live client.
        """
        common: Dict[str, Any] = {"name": name}
        if description is not None:
            common["description"] = description
        if annotations:
            common["annotations"] = annotations

        if etype == "link":
            if not target_id:
                return {"error": "target_id is required to create a link"}
            if not parent_id:
                return {"error": "parent_id is required to create a link"}
            return Link(
                parent_id=parent_id,
                target_id=target_id,
                target_version_number=target_version_number,
                **common,
            )

        if etype == "file":
            if external_url and data_file_handle_id:
                return {
                    "error": (
                        "Provide either external_url or "
                        "data_file_handle_id for a file, not both."
                    )
                }
            if not (external_url or data_file_handle_id):
                return {
                    "error": (
                        "A file can only be created through this server "
                        "with an external_url or an existing "
                        "data_file_handle_id — uploading file content is "
                        "not supported."
                    )
                }
            if not parent_id:
                return {"error": "parent_id is required to create a file"}
            return File(
                parent_id=parent_id,
                external_url=external_url,
                data_file_handle_id=data_file_handle_id,
                synapse_store=False if external_url else True,
                **common,
            )

        if etype == "recordset":
            if not data_file_handle_id:
                return {
                    "error": (
                        "A recordset can only be created through this "
                        "server with an existing data_file_handle_id — "
                        "uploading CSV content is not supported."
                    )
                }
            if not parent_id:
                return {
                    "error": "parent_id is required to create a recordset",
                }
            return RecordSet(
                parent_id=parent_id,
                data_file_handle_id=data_file_handle_id,
                **common,
            )

        cls = _CONTAINER_ENTITY_TYPES.get(etype)
        if cls is None:
            return {
                "error": (
                    f"Unsupported entity_type '{etype}'. Supported: "
                    "project, folder, file, link, dataset, "
                    "datasetcollection, entityview, table, "
                    "materializedview, virtualtable, submissionview, "
                    "dockerrepository, recordset."
                )
            }
        if cls is not Project and not parent_id:
            return {
                "error": f"parent_id is required to create a {etype}",
            }
        if cls is not Project:
            common["parent_id"] = parent_id

        kwargs: Dict[str, Any] = dict(common)
        if defining_sql is not None:
            kwargs["defining_sql"] = defining_sql
        if scope_ids is not None:
            kwargs["scope_ids"] = scope_ids
        if view_type_mask:
            kwargs["view_type_mask"] = EntityService._resolve_view_mask(
                view_type_mask
            )
        if columns:
            kwargs["columns"] = [
                EntityService._build_column(c) for c in columns
            ]
        return cls(**kwargs)

    @staticmethod
    def _build_column(spec: ColumnSpec) -> Column:
        """Build a Column from a plain dict spec."""
        if not spec.get("name"):
            raise ValueError("Column spec is missing required 'name'.")
        if not spec.get("column_type"):
            raise ValueError(
                f"Column '{spec.get('name')}' is missing required "
                "'column_type'."
            )
        col_type = spec.get("column_type")
        if isinstance(col_type, str):
            try:
                col_type = ColumnType[col_type.upper()]
            except KeyError:
                valid = ", ".join(c.name for c in ColumnType)
                raise ValueError(
                    f"Unknown column_type '{spec.get('column_type')}'. "
                    f"Valid: {valid}"
                )
        return Column(
            name=spec.get("name"),
            column_type=col_type,
            maximum_size=spec.get("maximum_size"),
            default_value=spec.get("default_value"),
            enum_values=spec.get("enum_values"),
        )

    @staticmethod
    def _resolve_view_mask(masks: List[ViewScopeType]) -> ViewTypeMask:
        """OR together ViewTypeMask flags named by ``masks``."""
        resolved = None
        for m in masks:
            try:
                flag = ViewTypeMask[m.strip().upper()]
            except KeyError:
                valid = ", ".join(v.name for v in ViewTypeMask)
                raise ValueError(
                    f"Unknown view_type_mask '{m}'. Valid: {valid}"
                )
            resolved = flag if resolved is None else resolved | flag
        return resolved

    @staticmethod
    @error_boundary(error_context_keys=("entity_id",))
    async def update_entity(
        ctx: Context,
        entity_id: str,
        name: Optional[str] = UNSET,
        parent_id: Optional[str] = UNSET,
        description: Optional[str] = UNSET,
        annotations: Optional[Dict[str, List[Any]]] = UNSET,
        provenance: Optional[ProvenanceSpec] = UNSET,
        external_url: Optional[str] = UNSET,
        data_file_handle_id: Optional[str] = UNSET,
        target_id: Optional[str] = UNSET,
        target_version_number: Optional[int] = UNSET,
        scope_ids: Optional[List[str]] = UNSET,
        view_type_mask: Optional[List[ViewScopeType]] = UNSET,
        defining_sql: Optional[str] = UNSET,
    ) -> Dict[str, Any]:
        """Update a Synapse entity's metadata, annotations, or provenance.

        Resolves the entity to its concrete type, applies the provided
        fields, and stores. Annotations and provenance (Activity) are just
        attributes persisted on the entity's store — there is no separate
        provenance write path.

        Each optional field is only touched when supplied. Passing an
        explicit ``null`` clears that field: ``description=null`` blanks
        the description and ``annotations=null`` (or ``{}``) removes all
        annotations. Every other field is non-clearable — a null is
        rejected. Type-specific fields (``external_url``, ``target_id``,
        ``scope_ids``, ``defining_sql``, ...) are rejected when the resolved
        entity type does not support them.

        Arguments:
            ctx: The FastMCP request context.
            entity_id: Synapse ID of the entity to update.
            name: New name (rename).
            parent_id: New parent container ID (move).
            description: New description; null clears it.
            annotations: Full replacement annotations (each key maps to a
                list of values); null or {} clears all annotations.
            provenance: Provenance/activity spec — ``name``, ``description``,
                and ``used`` / ``executed`` lists of entity refs or URLs.
            external_url: New external URL (file entities only).
            data_file_handle_id: New file handle to attach (file entities
                only).
            target_id: New link target entity ID (link entities only).
            target_version_number: Pinned target version (link entities
                only).
            scope_ids: Container IDs an entityview scopes over.
            view_type_mask: Scope types for view/dataset entities.
            defining_sql: SQL for materializedview / virtualtable.

        Returns:
            Dict with the updated entity metadata.
        """
        # Generic non-clearable fields (a null is meaningless server-side).
        for field, value in (("name", name), ("parent_id", parent_id)):
            if value is not UNSET and value is None:
                return {
                    "error": (
                        f"'{field}' cannot be cleared to null; supply a "
                        "non-null value or omit it to leave it unchanged."
                    ),
                    "error_type": "ValueError",
                    "entity_id": entity_id,
                }
        if provenance is not UNSET and provenance is None:
            return {
                "error": (
                    "provenance cannot be cleared via this tool; delete the "
                    "entity's activity separately, or omit it to leave it "
                    "unchanged."
                ),
                "error_type": "ValueError",
                "entity_id": entity_id,
            }
        # Type-specific fields keyed by the model attribute they set. All are
        # non-clearable and only valid on entity types that expose the attr.
        type_specific = {
            "external_url": external_url,
            "data_file_handle_id": data_file_handle_id,
            "target_id": target_id,
            "target_version_number": target_version_number,
            "scope_ids": scope_ids,
            "view_type_mask": view_type_mask,
            "defining_sql": defining_sql,
        }
        for field, value in type_specific.items():
            if value is not UNSET and value is None:
                return {
                    "error": (
                        f"'{field}' cannot be cleared to null; supply a "
                        "non-null value or omit it to leave it unchanged."
                    ),
                    "error_type": "ValueError",
                    "entity_id": entity_id,
                }
        async with synapse_client(ctx) as client:
            entity = await _resolve_entity(entity_id, client)
            if name is not UNSET:
                entity.name = name
            if parent_id is not UNSET:
                entity.parent_id = parent_id
            if description is not UNSET:
                entity.description = description
            if annotations is not UNSET:
                entity.annotations = annotations or {}
            if provenance is not UNSET:
                entity.activity = EntityService._build_activity(provenance)
            for field, value in type_specific.items():
                if value is UNSET:
                    continue
                if not hasattr(entity, field):
                    return {
                        "error": (
                            f"'{field}' is not valid for a "
                            f"{type(entity).__name__}."
                        ),
                        "entity_id": entity_id,
                    }
                if field == "view_type_mask":
                    value = EntityService._resolve_view_mask(value)
                setattr(entity, field, value)
            # Setting an external_url means the file is an external link, not
            # a local upload — mirror create_entity's synapse_store guard.
            if external_url is not UNSET and hasattr(entity, "synapse_store"):
                entity.synapse_store = False
            stored = await entity.store_async(synapse_client=client)
            return serialize_model(stored)

    @staticmethod
    def _build_activity(spec: ProvenanceSpec) -> Activity:
        """Build an Activity from a plain dict spec."""

        def _used(items: Optional[List[Dict[str, Any]]]):
            out = []
            for item in items or []:
                if item.get("url"):
                    out.append(
                        UsedURL(name=item.get("name"), url=item["url"])
                    )
                elif item.get("target_id"):
                    out.append(
                        UsedEntity(
                            target_id=item["target_id"],
                            target_version_number=item.get(
                                "target_version_number"
                            ),
                        )
                    )
            return out

        return Activity(
            name=spec.get("name"),
            description=spec.get("description"),
            used=_used(spec.get("used")),
            executed=_used(spec.get("executed")),
        )

    @staticmethod
    @error_boundary(error_context_keys=("entity_id",))
    async def delete_entity(
        ctx: Context, entity_id: str
    ) -> Dict[str, Any]:
        """Delete a Synapse entity by ID.

        Resolves the entity to its concrete type and deletes it. For a
        file this removes the File entity (metadata); it does not touch
        stored file content beyond removing the entity.

        Arguments:
            ctx: The FastMCP request context.
            entity_id: Synapse ID of the entity to delete.

        Returns:
            Dict confirming the deletion.
        """
        async with synapse_client(ctx) as client:
            entity = await _resolve_entity(entity_id, client)
            await entity.delete_async(synapse_client=client)
            return {"entity_id": entity_id, "deleted": True}

    @staticmethod
    @error_boundary(error_context_keys=("entity_id",))
    async def set_acl(
        ctx: Context,
        entity_id: str,
        principal_id: int,
        access_type: List[EntityAccessType],
    ) -> Dict[str, Any]:
        """Set the access an entity grants to one principal.

        Arguments:
            ctx: The FastMCP request context.
            entity_id: Synapse ID of the entity.
            principal_id: User or team ID to grant access to.
            access_type: Permission strings. Pass an empty list to remove
                this principal's entry.

        Returns:
            Dict with the updated ACL.
        """
        async with synapse_client(ctx) as client:
            entity = await _resolve_entity(entity_id, client)
            result = await entity.set_permissions_async(
                principal_id=principal_id,
                access_type=access_type,
                synapse_client=client,
            )
            return {
                "entity_id": entity_id,
                "principal_id": principal_id,
                "acl": serialize_model(result),
            }

    @staticmethod
    @error_boundary(error_context_keys=("entity_id",))
    async def delete_acl(
        ctx: Context, entity_id: str
    ) -> Dict[str, Any]:
        """Delete a Synapse entity's local ACL (revert to inherited sharing).

        Arguments:
            ctx: The FastMCP request context.
            entity_id: Synapse ID whose local sharing settings should be
                removed so it inherits from its benefactor.

        Returns:
            Dict with ``acl_deleted``. A Project's own root ACL cannot be
            deleted in Synapse, so for a Project ``acl_deleted`` is False
            and a ``message`` explains how to revoke access instead.
        """
        async with synapse_client(ctx) as client:
            entity = await _resolve_entity(entity_id, client)
            await entity.delete_permissions_async(synapse_client=client)
            if type(entity).__name__.lower() == "project":
                return {
                    "entity_id": entity_id,
                    "acl_deleted": False,
                    "message": (
                        "A Project's own ACL cannot be deleted; revoke "
                        "individual permissions with update_entity_acl "
                        "instead."
                    ),
                }
            return {"entity_id": entity_id, "acl_deleted": True}

    @staticmethod
    @error_boundary(error_context_keys=("entity_id", "json_schema_uri"))
    async def bind_schema(
        ctx: Context,
        entity_id: str,
        json_schema_uri: str,
        enable_derived_annotations: bool = False,
    ) -> Dict[str, Any]:
        """Bind a JSON schema to a Synapse entity.

        Arguments:
            ctx: The FastMCP request context.
            entity_id: Synapse ID to bind the schema to.
            json_schema_uri: The schema $id, e.g. "my.org-MySchema-1.0.0".
            enable_derived_annotations: Whether to enable schema-derived
                annotations on the entity.

        Returns:
            Dict with the schema binding metadata.
        """
        async with synapse_client(ctx) as client:
            entity = await _resolve_entity(entity_id, client)
            binding = await entity.bind_schema_async(
                json_schema_uri=json_schema_uri,
                enable_derived_annotations=enable_derived_annotations,
                synapse_client=client,
            )
            result = serialize_model(binding)
            if isinstance(result, dict):
                result["entity_id"] = entity_id
            return result

    @staticmethod
    @error_boundary(error_context_keys=("entity_id",))
    async def unbind_schema(
        ctx: Context, entity_id: str
    ) -> Dict[str, Any]:
        """Unbind the JSON schema from a Synapse entity.

        Arguments:
            ctx: The FastMCP request context.
            entity_id: Synapse ID whose bound schema should be removed.

        Returns:
            Dict confirming the schema was unbound.
        """
        async with synapse_client(ctx) as client:
            entity = await _resolve_entity(entity_id, client)
            await entity.unbind_schema_async(synapse_client=client)
            return {"entity_id": entity_id, "schema_unbound": True}

    @staticmethod
    @error_boundary(error_context_keys=("entity_id",))
    async def update_columns(
        ctx: Context,
        entity_id: str,
        add_columns: Optional[List[ColumnSpec]] = None,
        delete_columns: Optional[List[str]] = None,
        rename_columns: Optional[Dict[str, str]] = None,
        reorder_columns: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Change the columns (schema) of a table/view/dataset.

        Resolves the entity to its concrete columnar type (Table,
        EntityView, Dataset, ...), applies the requested column operations,
        and stores the schema change. This never loads row data.

        Operations are applied in a fixed order — delete, then add, then
        rename, then reorder — so names in later operations refer to the
        post-add/post-delete state. ``reorder_columns``, when supplied, must
        list exactly the final set of column names (all of them, no
        duplicates).

        Arguments:
            ctx: The FastMCP request context.
            entity_id: Synapse ID of the table, view, or dataset.
            add_columns: Column specs to add (``name`` + ``column_type`` at
                minimum).
            delete_columns: Column names to delete.
            rename_columns: Map of ``{old_name: new_name}`` for existing
                columns.
            reorder_columns: Complete desired column order, as a list of the
                final column names.

        Returns:
            Dict with the updated entity metadata. Returns an error dict if
            the entity type does not support columns or the reorder list is
            incomplete.
        """
        async with synapse_client(ctx) as client:
            entity = await _resolve_entity(entity_id, client)
            if not hasattr(entity, "add_column") or not hasattr(
                entity, "delete_column"
            ):
                return {
                    "error": (
                        f"Entity {entity_id} is a "
                        f"{type(entity).__name__}, which does not have "
                        "columns. Columns can only be changed on tables, "
                        "views, and datasets."
                    ),
                    "entity_id": entity_id,
                }
            for name in delete_columns or []:
                entity.delete_column(name=name)
            for spec in add_columns or []:
                entity.add_column(EntityService._build_column(spec))
            # Rename by mutating Column.name in place; store diffs by column
            # id, so the OrderedDict key is cosmetic. Re-key here so a later
            # reorder can reference the new names.
            if rename_columns:
                for old_name, new_name in rename_columns.items():
                    col = entity.columns.get(old_name)
                    if col is None:
                        return {
                            "error": (
                                f"Cannot rename column '{old_name}': no such "
                                "column."
                            ),
                            "entity_id": entity_id,
                        }
                    col.name = new_name
                entity.columns = type(entity.columns)(
                    (col.name, col) for col in entity.columns.values()
                )
            if reorder_columns is not None:
                current = set(entity.columns.keys())
                requested = set(reorder_columns)
                if requested != current or len(reorder_columns) != len(
                    current
                ):
                    return {
                        "error": (
                            "reorder_columns must list exactly the final set "
                            f"of column names. Expected {sorted(current)}, "
                            f"got {reorder_columns}."
                        ),
                        "entity_id": entity_id,
                    }
                for index, name in enumerate(reorder_columns):
                    entity.reorder_column(name=name, index=index)
            stored = await entity.store_async(synapse_client=client)
            return serialize_model(stored)
