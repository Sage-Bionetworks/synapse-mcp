"""Service layer for entity operations.

Handles get, annotations, children, ACL, permissions,
schema, and container operations for any Synapse entity.
Uses synapseclient.operations and model classes (never
legacy Synapse.get / getChildren / get_annotations).
"""

from typing import Any, Dict, List, Optional

from fastmcp import Context
from synapseclient.models import Folder
from synapseclient.operations import get_async as operations_get_async
from synapseclient.operations.factory_operations import (
    FileOptions,
    LinkOptions,
)

from .tool_service import (
    error_boundary,
    serialize_model,
    synapse_client,
)

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
