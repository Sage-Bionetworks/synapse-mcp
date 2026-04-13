"""Tool registrations for Synapse MCP."""

from typing import Any, Dict, List, Optional

from fastmcp import Context

from .app import mcp
from .services import (
    ActivityService,
    CurationTaskService,
    EntityService,
    SearchService,
)
from .utils import validate_synapse_id

_RO = {
    "readOnlyHint": True,
    "idempotentHint": True,
    "destructiveHint": False,
    "openWorldHint": True,
}


# ---------------------------------------------------------------------------
# Domain 1: Entity Core
# ---------------------------------------------------------------------------


@mcp.tool(
    title="Fetch Entity",
    description=(
        "Get metadata for any single Synapse entity by ID "
        "(projects, folders, files, tables, etc.). "
        "Only retrieves metadata — does not download "
        "file content."
    ),
    annotations=_RO,
)
async def get_entity(
    entity_id: str, ctx: Context
) -> Dict[str, Any]:
    """Return Synapse entity metadata by ID."""
    if not validate_synapse_id(entity_id):
        return {"error": f"Invalid Synapse ID: {entity_id}"}
    return await EntityService().get_entity(ctx, entity_id)


@mcp.tool(
    title="Fetch Entity Annotations",
    description=(
        "Get only the custom annotation key/value pairs "
        "for a Synapse entity. Use get_entity if you need "
        "full entity metadata instead."
    ),
    annotations=_RO,
)
async def get_entity_annotations(
    entity_id: str, ctx: Context
) -> Dict[str, Any]:
    """Return custom annotations for a Synapse entity."""
    if not validate_synapse_id(entity_id):
        return {"error": f"Invalid Synapse ID: {entity_id}"}
    return await EntityService().get_annotations(ctx, entity_id)


@mcp.tool(
    title="Fetch Entity Provenance",
    description=(
        "Return provenance (activity) metadata for a "
        "Synapse entity, including inputs and code executed."
    ),
    annotations=_RO,
)
async def get_entity_provenance(
    entity_id: str,
    ctx: Context,
    version: Optional[int] = None,
) -> Dict[str, Any]:
    """Return activity metadata for a Synapse entity."""
    if not validate_synapse_id(entity_id):
        return {"error": f"Invalid Synapse ID: {entity_id}"}
    if version is not None:
        try:
            version = int(version)
            if version <= 0:
                return {
                    "error": "Version must be a positive integer",
                    "entity_id": entity_id,
                }
        except (TypeError, ValueError):
            return {
                "error": f"Invalid version number: {version}",
                "entity_id": entity_id,
            }
    return await ActivityService().get_provenance(
        ctx, entity_id, version
    )


@mcp.tool(
    title="List Entity Children",
    description=(
        "List files and folders immediately inside a "
        "container (one level deep). Works on Projects "
        "and Folders. Call repeatedly on child folders "
        "to traverse deeper."
    ),
    annotations=_RO,
)
async def get_entity_children(
    entity_id: str, ctx: Context
) -> List[Dict[str, Any]]:
    """List children for Synapse container entities."""
    if not validate_synapse_id(entity_id):
        return [{"error": f"Invalid Synapse ID: {entity_id}"}]
    return await EntityService().get_children(ctx, entity_id)


@mcp.tool(
    title="Search Synapse",
    description=(
        "Search Synapse entities using keyword queries "
        "with optional name/type/parent filters."
    ),
    annotations=_RO,
)
async def search_synapse(
    ctx: Context,
    query_term: Optional[str] = None,
    name: Optional[str] = None,
    entity_type: Optional[str] = None,
    entity_types: Optional[List[str]] = None,
    parent_id: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
) -> Dict[str, Any]:
    """Search Synapse entities using keyword queries."""
    return await SearchService().search(
        ctx,
        query_term=query_term,
        name=name,
        entity_type=entity_type,
        entity_types=entity_types,
        parent_id=parent_id,
        limit=limit,
        offset=offset,
    )


# ---------------------------------------------------------------------------
# Domain 2: Entity Access Control
# ---------------------------------------------------------------------------


@mcp.tool(
    title="Get Entity ACL",
    description=(
        "Get the access control list for a Synapse entity. "
        "Optionally filter by a specific principal ID."
    ),
    annotations=_RO,
)
async def get_entity_acl(
    entity_id: str,
    ctx: Context,
    principal_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Get the ACL for a Synapse entity."""
    if not validate_synapse_id(entity_id):
        return {"error": f"Invalid Synapse ID: {entity_id}"}
    return await EntityService().get_acl(
        ctx, entity_id, principal_id
    )


@mcp.tool(
    title="Get Entity Permissions",
    description=(
        "Get the current user's permissions on a "
        "Synapse entity."
    ),
    annotations=_RO,
)
async def get_entity_permissions(
    entity_id: str, ctx: Context
) -> Dict[str, Any]:
    """Get current user's permissions on a Synapse entity."""
    if not validate_synapse_id(entity_id):
        return {"error": f"Invalid Synapse ID: {entity_id}"}
    return await EntityService().get_permissions(ctx, entity_id)


@mcp.tool(
    title="List Entity ACL",
    description=(
        "Recursively list all ACLs for an entity and "
        "optionally its descendants."
    ),
    annotations=_RO,
)
async def list_entity_acl(
    entity_id: str,
    ctx: Context,
    recursive: bool = False,
) -> Dict[str, Any]:
    """List all ACLs under an entity."""
    if not validate_synapse_id(entity_id):
        return {"error": f"Invalid Synapse ID: {entity_id}"}
    return await EntityService().list_acl(
        ctx, entity_id, recursive
    )


# ---------------------------------------------------------------------------
# Domain 3: Entity JSON Schema
# ---------------------------------------------------------------------------


@mcp.tool(
    title="Get Entity Schema",
    description=(
        "Get the JSON schema bound to a Synapse entity."
    ),
    annotations=_RO,
)
async def get_entity_schema(
    entity_id: str, ctx: Context
) -> Dict[str, Any]:
    """Get bound JSON schema info for an entity."""
    if not validate_synapse_id(entity_id):
        return {"error": f"Invalid Synapse ID: {entity_id}"}
    return await EntityService().get_schema(ctx, entity_id)


@mcp.tool(
    title="Get Entity Schema Derived Keys",
    description=(
        "Get annotation keys derived from a bound "
        "JSON schema on a Synapse entity."
    ),
    annotations=_RO,
)
async def get_entity_schema_derived_keys(
    entity_id: str, ctx: Context
) -> Dict[str, Any]:
    """Get derived annotation keys from a bound schema."""
    if not validate_synapse_id(entity_id):
        return {"error": f"Invalid Synapse ID: {entity_id}"}
    return await EntityService().get_schema_derived_keys(
        ctx, entity_id
    )


@mcp.tool(
    title="Get Entity Schema Validation Statistics",
    description=(
        "Get validation statistics for a Folder or "
        "Project with a bound JSON schema."
    ),
    annotations=_RO,
)
async def get_entity_schema_validation_statistics(
    entity_id: str, ctx: Context
) -> Dict[str, Any]:
    """Get schema validation stats for a container."""
    if not validate_synapse_id(entity_id):
        return {"error": f"Invalid Synapse ID: {entity_id}"}
    return await EntityService().get_schema_validation_statistics(
        ctx, entity_id
    )


@mcp.tool(
    title="Get Entity Schema Invalid Validations",
    description=(
        "Get entities with invalid JSON schema "
        "validations under a Folder or Project."
    ),
    annotations=_RO,
)
async def get_entity_schema_invalid_validations(
    entity_id: str, ctx: Context
) -> List[Dict[str, Any]]:
    """Get invalid validation results for a container."""
    if not validate_synapse_id(entity_id):
        return [{"error": f"Invalid Synapse ID: {entity_id}"}]
    return await EntityService().get_schema_invalid_validations(
        ctx, entity_id
    )



# ---------------------------------------------------------------------------
# Domain 6: Activity (Provenance)
# ---------------------------------------------------------------------------


@mcp.tool(
    title="Get Activity",
    description=(
        "Get a provenance Activity by its own ID, "
        "or by parent entity ID and optional version."
    ),
    annotations=_RO,
)
async def get_activity(
    ctx: Context,
    activity_id: Optional[str] = None,
    parent_id: Optional[str] = None,
    parent_version_number: Optional[int] = None,
) -> Dict[str, Any]:
    """Get an Activity by ID or by parent entity."""
    return await ActivityService().get_activity(
        ctx, activity_id, parent_id, parent_version_number
    )


# ---------------------------------------------------------------------------
# Domain 7: Link
# ---------------------------------------------------------------------------


@mcp.tool(
    title="Get Link",
    description=(
        "Resolve a Synapse Link entity to its target, "
        "or get the Link metadata itself."
    ),
    annotations=_RO,
)
async def get_link(
    entity_id: str,
    ctx: Context,
    follow_link: bool = True,
) -> Dict[str, Any]:
    """Resolve a Link entity."""
    if not validate_synapse_id(entity_id):
        return {"error": f"Invalid Synapse ID: {entity_id}"}
    return await EntityService().get_link(
        ctx, entity_id, follow_link
    )


# ---------------------------------------------------------------------------
# Domain 13: Curation Tasks
# ---------------------------------------------------------------------------


@mcp.tool(
    title="List Curation Tasks",
    description=(
        "List all curation tasks within a specific "
        "Synapse project."
    ),
    annotations=_RO,
)
async def list_curation_tasks(
    project_id: str, ctx: Context
) -> List[Dict[str, Any]]:
    """List all curation tasks for a given project."""
    if not validate_synapse_id(project_id):
        return [{"error": f"Invalid Synapse ID: {project_id}"}]
    return await CurationTaskService().list_tasks(ctx, project_id)


@mcp.tool(
    title="Get Curation Task",
    description=(
        "Retrieve detailed information about a specific "
        "curation task by its task ID."
    ),
    annotations=_RO,
)
async def get_curation_task(
    task_id: int, ctx: Context
) -> Dict[str, Any]:
    """Get a specific curation task by its task ID."""
    return await CurationTaskService().get_task(ctx, task_id)


@mcp.tool(
    title="Get Curation Task Resources",
    description=(
        "Explore and retrieve resources associated with "
        "a curation task, including RecordSets, Folders, "
        "and EntityViews."
    ),
    annotations=_RO,
)
async def get_curation_task_resources(
    task_id: int, ctx: Context
) -> Dict[str, Any]:
    """Get resources associated with a curation task."""
    return await CurationTaskService().get_task_resources(
        ctx, task_id
    )
