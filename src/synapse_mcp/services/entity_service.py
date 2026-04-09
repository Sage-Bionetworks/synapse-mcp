"""Service layer for entity operations.

Handles get, annotations, children, ACL, permissions,
schema, and container operations for any Synapse entity.
Uses synapseclient.operations and model classes (never
legacy Synapse.get / getChildren / get_annotations).
"""

from typing import Any, Dict, List, Optional

from fastmcp import Context
from synapseclient.models import File, Folder, Link, Project
from synapseclient.operations import get as operations_get
from synapseclient.operations.factory_operations import (
    FileOptions,
    LinkOptions,
)

from .tool_service import (
    dataclass_to_dict,
    error_boundary,
    serialize_model,
    synapse_client,
)

# Child list attributes on Folder/Project containers.
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
)


class EntityService:
    """Orchestrates entity read operations."""

    @error_boundary(error_context_keys=("entity_id",))
    def get_entity(
        self, ctx: Context, entity_id: str
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
        with synapse_client(ctx) as client:
            entity = operations_get(
                entity_id,
                file_options=FileOptions(
                    download_file=False,
                ),
                synapse_client=client,
            )
            return serialize_model(entity)

    @error_boundary(error_context_keys=("entity_id",))
    def get_annotations(
        self, ctx: Context, entity_id: str
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
        with synapse_client(ctx) as client:
            entity = operations_get(
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

    @error_boundary(
        error_context_keys=("entity_id",),
        wrap_errors=True,
    )
    def get_children(
        self, ctx: Context, entity_id: str
    ) -> List[Dict[str, Any]]:
        """List immediate children of a container entity.

        Uses ``Folder(id=...).walk(recursive=False)`` which
        yields ``(path_info, folders, files)`` tuples where
        folders and files are lists of ``EntityHeader``
        dataclasses.

        Arguments:
            ctx: The FastMCP request context.
            entity_id: Synapse ID of a Project or Folder.

        Returns:
            List of child entity dicts (id, name, type).
            Returns an error dict inside a list if the
            entity is not a container.
        """
        with synapse_client(ctx) as client:
            container = Folder(id=entity_id)
            children: List[Dict[str, Any]] = []
            for _path_info, folders, files in container.walk(
                recursive=False,
                synapse_client=client,
            ):
                for header in folders:
                    children.append(
                        serialize_model(header)
                    )
                for header in files:
                    children.append(
                        serialize_model(header)
                    )
            return children

    @error_boundary(error_context_keys=("entity_id",))
    def get_acl(
        self,
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
        with synapse_client(ctx) as client:
            entity = File(id=entity_id)
            access_types = entity.get_acl(
                principal_id=principal_id,
                synapse_client=client,
            )
            return {
                "entity_id": entity_id,
                "principal_id": principal_id,
                "access_types": access_types,
            }

    @error_boundary(error_context_keys=("entity_id",))
    def get_permissions(
        self, ctx: Context, entity_id: str
    ) -> Dict[str, Any]:
        """Get current user's permissions on an entity.

        Arguments:
            ctx: The FastMCP request context.
            entity_id: Synapse ID (e.g. ``"syn123"``).

        Returns:
            Dict with entity_id and boolean permission
            flags (can_view, can_edit, can_download, etc.).
        """
        with synapse_client(ctx) as client:
            entity = File(id=entity_id)
            permissions = entity.get_permissions(
                synapse_client=client,
            )
            result = serialize_model(permissions)
            result["entity_id"] = entity_id
            return result

    @error_boundary(error_context_keys=("entity_id",))
    def list_acl(
        self,
        ctx: Context,
        entity_id: str,
        recursive: bool = False,
    ) -> Dict[str, Any]:
        """Recursively list all ACLs under an entity.

        Arguments:
            ctx: The FastMCP request context.
            entity_id: Synapse ID (e.g. ``"syn123"``).
            recursive: If True, list ACLs for all
                descendants. Defaults to False.

        Returns:
            Dict with entity_acl (current entity's ACL
            entries) and all_entity_acls (includes
            descendants if recursive).
        """
        with synapse_client(ctx) as client:
            entity = File(id=entity_id)
            acl_result = entity.list_acl(
                recursive=recursive,
                synapse_client=client,
            )
            result = serialize_model(acl_result)
            if isinstance(result, dict):
                result["entity_id"] = entity_id
            return result

    @error_boundary(error_context_keys=("entity_id",))
    def get_schema(
        self, ctx: Context, entity_id: str
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
        with synapse_client(ctx) as client:
            entity = File(id=entity_id)
            schema_info = entity.get_schema(
                synapse_client=client,
            )
            result = serialize_model(schema_info)
            if isinstance(result, dict):
                result["entity_id"] = entity_id
            return result

    @error_boundary(error_context_keys=("entity_id",))
    def get_schema_derived_keys(
        self, ctx: Context, entity_id: str
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
        with synapse_client(ctx) as client:
            entity = File(id=entity_id)
            keys = entity.get_schema_derived_keys(
                synapse_client=client,
            )
            return {
                "entity_id": entity_id,
                "derived_keys": serialize_model(keys),
            }

    @error_boundary(error_context_keys=("entity_id",))
    def get_schema_validation_statistics(
        self, ctx: Context, entity_id: str
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
        with synapse_client(ctx) as client:
            container = Folder(id=entity_id)
            stats = container.get_schema_validation_statistics(
                synapse_client=client,
            )
            result = serialize_model(stats)
            if isinstance(result, dict):
                result["entity_id"] = entity_id
            return result

    @error_boundary(
        error_context_keys=("entity_id",),
        wrap_errors=True,
    )
    def get_schema_invalid_validations(
        self, ctx: Context, entity_id: str
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
        with synapse_client(ctx) as client:
            container = Folder(id=entity_id)
            results = container.get_invalid_validation(
                synapse_client=client,
            )
            return [
                serialize_model(item) for item in results
            ]

    @error_boundary(error_context_keys=("entity_id",))
    def sync_container(
        self,
        ctx: Context,
        entity_id: str,
        recursive: bool = False,
        include_types: Optional[List[str]] = None,
        follow_link: bool = False,
    ) -> Dict[str, Any]:
        """Retrieve full metadata tree for a container.

        Uses sync_from_synapse with download_file=False to
        populate all child entity lists without downloading
        file content.

        Arguments:
            ctx: The FastMCP request context.
            entity_id: Synapse ID of a Folder or Project.
            recursive: Traverse subdirectories
                (default False). Warning: may be slow on
                large containers.
            include_types: Entity types to include
                (default all).
            follow_link: Resolve Link entities
                (default False).

        Returns:
            Dict with container metadata and child entity
            lists (files, folders, tables, entityviews,
            etc.).
        """
        with synapse_client(ctx) as client:
            container = Folder(id=entity_id)
            container.sync_from_synapse(
                download_file=False,
                recursive=recursive,
                include_types=include_types,
                follow_link=follow_link,
                synapse_client=client,
            )
            result = serialize_model(container)
            return result

    @error_boundary(error_context_keys=("entity_id",))
    def get_link(
        self,
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
        with synapse_client(ctx) as client:
            resolved = operations_get(
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
