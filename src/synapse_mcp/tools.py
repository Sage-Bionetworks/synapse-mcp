"""Tool registrations for Synapse MCP."""

from typing import Any, Dict, List, Optional

from fastmcp import Context

from .app import mcp
from .services import (
    ActivityService,
    CurationTaskService,
    EntityService,
    SearchService,
    TeamService,
    UserService,
    WikiService,
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
def get_entity(
    entity_id: str, ctx: Context
) -> Dict[str, Any]:
    """Return Synapse entity metadata by ID."""
    if not validate_synapse_id(entity_id):
        return {"error": f"Invalid Synapse ID: {entity_id}"}
    return EntityService().get_entity(ctx, entity_id)


@mcp.tool(
    title="Fetch Entity Annotations",
    description=(
        "Get only the custom annotation key/value pairs "
        "for a Synapse entity. Use get_entity if you need "
        "full entity metadata instead."
    ),
    annotations=_RO,
)
def get_entity_annotations(
    entity_id: str, ctx: Context
) -> Dict[str, Any]:
    """Return custom annotations for a Synapse entity."""
    if not validate_synapse_id(entity_id):
        return {"error": f"Invalid Synapse ID: {entity_id}"}
    return EntityService().get_annotations(ctx, entity_id)


@mcp.tool(
    title="Fetch Entity Provenance",
    description=(
        "Return provenance (activity) metadata for a "
        "Synapse entity, including inputs and code executed."
    ),
    annotations=_RO,
)
def get_entity_provenance(
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
    return ActivityService().get_provenance(
        ctx, entity_id, version
    )


@mcp.tool(
    title="List Entity Children",
    description=(
        "List files and folders immediately inside a "
        "container (one level deep). Works on Projects "
        "and Folders. Use sync_container for the full "
        "deep nested tree."
    ),
    annotations=_RO,
)
def get_entity_children(
    entity_id: str, ctx: Context
) -> List[Dict[str, Any]]:
    """List children for Synapse container entities."""
    if not validate_synapse_id(entity_id):
        return [{"error": f"Invalid Synapse ID: {entity_id}"}]
    return EntityService().get_children(ctx, entity_id)


@mcp.tool(
    title="Search Synapse",
    description=(
        "Search Synapse entities using keyword queries "
        "with optional name/type/parent filters."
    ),
    annotations=_RO,
)
def search_synapse(
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
    return SearchService().search(
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
def get_entity_acl(
    entity_id: str,
    ctx: Context,
    principal_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Get the ACL for a Synapse entity."""
    if not validate_synapse_id(entity_id):
        return {"error": f"Invalid Synapse ID: {entity_id}"}
    return EntityService().get_acl(
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
def get_entity_permissions(
    entity_id: str, ctx: Context
) -> Dict[str, Any]:
    """Get current user's permissions on a Synapse entity."""
    if not validate_synapse_id(entity_id):
        return {"error": f"Invalid Synapse ID: {entity_id}"}
    return EntityService().get_permissions(ctx, entity_id)


@mcp.tool(
    title="List Entity ACL",
    description=(
        "Recursively list all ACLs for an entity and "
        "optionally its descendants."
    ),
    annotations=_RO,
)
def list_entity_acl(
    entity_id: str,
    ctx: Context,
    recursive: bool = False,
) -> Dict[str, Any]:
    """List all ACLs under an entity."""
    if not validate_synapse_id(entity_id):
        return {"error": f"Invalid Synapse ID: {entity_id}"}
    return EntityService().list_acl(
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
def get_entity_schema(
    entity_id: str, ctx: Context
) -> Dict[str, Any]:
    """Get bound JSON schema info for an entity."""
    if not validate_synapse_id(entity_id):
        return {"error": f"Invalid Synapse ID: {entity_id}"}
    return EntityService().get_schema(ctx, entity_id)


@mcp.tool(
    title="Get Entity Schema Derived Keys",
    description=(
        "Get annotation keys derived from a bound "
        "JSON schema on a Synapse entity."
    ),
    annotations=_RO,
)
def get_entity_schema_derived_keys(
    entity_id: str, ctx: Context
) -> Dict[str, Any]:
    """Get derived annotation keys from a bound schema."""
    if not validate_synapse_id(entity_id):
        return {"error": f"Invalid Synapse ID: {entity_id}"}
    return EntityService().get_schema_derived_keys(
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
def get_entity_schema_validation_statistics(
    entity_id: str, ctx: Context
) -> Dict[str, Any]:
    """Get schema validation stats for a container."""
    if not validate_synapse_id(entity_id):
        return {"error": f"Invalid Synapse ID: {entity_id}"}
    return EntityService().get_schema_validation_statistics(
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
def get_entity_schema_invalid_validations(
    entity_id: str, ctx: Context
) -> List[Dict[str, Any]]:
    """Get invalid validation results for a container."""
    if not validate_synapse_id(entity_id):
        return [{"error": f"Invalid Synapse ID: {entity_id}"}]
    return EntityService().get_schema_invalid_validations(
        ctx, entity_id
    )


# ---------------------------------------------------------------------------
# Domain 4: Container Traversal
# ---------------------------------------------------------------------------


@mcp.tool(
    title="Sync Container",
    description=(
        "Get the entire deep nested tree of a Project or "
        "Folder, populating all child entity lists "
        "(files, folders, tables, views, etc.) without "
        "downloading file content. Defaults to non-recursive "
        "(one level). Set recursive=True for full depth — "
        "may be slow on large containers."
    ),
    annotations=_RO,
)
def sync_container(
    entity_id: str,
    ctx: Context,
    recursive: bool = False,
    include_types: Optional[List[str]] = None,
    follow_link: bool = False,
) -> Dict[str, Any]:
    """Sync container metadata without downloading files."""
    if not validate_synapse_id(entity_id):
        return {"error": f"Invalid Synapse ID: {entity_id}"}
    return EntityService().sync_container(
        ctx, entity_id, recursive, include_types, follow_link
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
def get_activity(
    ctx: Context,
    activity_id: Optional[str] = None,
    parent_id: Optional[str] = None,
    parent_version_number: Optional[int] = None,
) -> Dict[str, Any]:
    """Get an Activity by ID or by parent entity."""
    return ActivityService().get_activity(
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
def get_link(
    entity_id: str,
    ctx: Context,
    follow_link: bool = True,
) -> Dict[str, Any]:
    """Resolve a Link entity."""
    if not validate_synapse_id(entity_id):
        return {"error": f"Invalid Synapse ID: {entity_id}"}
    return EntityService().get_link(
        ctx, entity_id, follow_link
    )


# ---------------------------------------------------------------------------
# Domain 8: Wiki
# ---------------------------------------------------------------------------


@mcp.tool(
    title="Get Wiki Page",
    description=(
        "Get a wiki page's content (markdown) and "
        "metadata for any Synapse entity. If wiki_id "
        "is omitted, returns the root wiki page."
    ),
    annotations=_RO,
)
def get_wiki_page(
    owner_id: str,
    ctx: Context,
    wiki_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Get a wiki page's content and metadata."""
    if not validate_synapse_id(owner_id):
        return {"error": f"Invalid Synapse ID: {owner_id}"}
    return WikiService().get_wiki_page(
        ctx, owner_id, wiki_id
    )


@mcp.tool(
    title="Get Wiki Headers",
    description=(
        "Get the hierarchical table of contents "
        "(wiki page tree) for a Synapse entity. "
        "If the result set hits the limit, call again "
        "with a higher offset to retrieve the next page."
    ),
    annotations=_RO,
)
def get_wiki_headers(
    owner_id: str,
    ctx: Context,
    offset: int = 0,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """Get the wiki table of contents for an entity."""
    if not validate_synapse_id(owner_id):
        return [{"error": f"Invalid Synapse ID: {owner_id}"}]
    return WikiService().get_wiki_headers(
        ctx, owner_id, offset, limit
    )


@mcp.tool(
    title="Get Wiki History",
    description=(
        "Get the revision history of a specific "
        "wiki page. If the result set hits the limit, "
        "call again with a higher offset to retrieve "
        "the next page."
    ),
    annotations=_RO,
)
def get_wiki_history(
    owner_id: str,
    wiki_id: str,
    ctx: Context,
    offset: int = 0,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """Get revision history of a wiki page."""
    if not validate_synapse_id(owner_id):
        return [{"error": f"Invalid Synapse ID: {owner_id}"}]
    return WikiService().get_wiki_history(
        ctx, owner_id, wiki_id, offset, limit
    )


@mcp.tool(
    title="Get Wiki Order Hint",
    description=(
        "Get the display ordering of wiki sub-pages "
        "for a Synapse entity."
    ),
    annotations=_RO,
)
def get_wiki_order_hint(
    owner_id: str, ctx: Context
) -> Dict[str, Any]:
    """Get wiki page display ordering."""
    if not validate_synapse_id(owner_id):
        return {"error": f"Invalid Synapse ID: {owner_id}"}
    return WikiService().get_wiki_order_hint(ctx, owner_id)


# ---------------------------------------------------------------------------
# Domain 9: Team & User
# ---------------------------------------------------------------------------


@mcp.tool(
    title="Get Team",
    description=(
        "Get a Synapse Team by its numeric ID or "
        "by name."
    ),
    annotations=_RO,
)
def get_team(
    ctx: Context,
    team_id: Optional[int] = None,
    team_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Get a Synapse Team by ID or name."""
    return TeamService().get_team(ctx, team_id, team_name)


@mcp.tool(
    title="Get Team Members",
    description="List all members of a Synapse Team.",
    annotations=_RO,
)
def get_team_members(
    team_id: int, ctx: Context
) -> List[Dict[str, Any]]:
    """List all members of a Team."""
    return TeamService().get_team_members(ctx, team_id)


@mcp.tool(
    title="Get Team Open Invitations",
    description=(
        "List pending invitations for a Synapse Team."
    ),
    annotations=_RO,
)
def get_team_open_invitations(
    team_id: int, ctx: Context
) -> List[Dict[str, Any]]:
    """List pending Team invitations."""
    return TeamService().get_team_open_invitations(
        ctx, team_id
    )


@mcp.tool(
    title="Get Team Membership Status",
    description=(
        "Check if a specific user is a member of "
        "or has applied to a Synapse Team."
    ),
    annotations=_RO,
)
def get_team_membership_status(
    team_id: int, user_id: str, ctx: Context
) -> Dict[str, Any]:
    """Check a user's Team membership status."""
    return TeamService().get_team_membership_status(
        ctx, team_id, user_id
    )


@mcp.tool(
    title="Get User Profile",
    description=(
        "Get a Synapse user's profile by numeric ID, "
        "username, or self (no args returns the "
        "authenticated user's own profile)."
    ),
    annotations=_RO,
)
def get_user_profile(
    ctx: Context,
    user_id: Optional[int] = None,
    username: Optional[str] = None,
) -> Dict[str, Any]:
    """Get a Synapse user profile."""
    return UserService().get_user_profile(
        ctx, user_id, username
    )


@mcp.tool(
    title="Is User Certified",
    description=(
        "Check if a Synapse user is certified."
    ),
    annotations=_RO,
)
def is_user_certified(
    user_id: int, ctx: Context
) -> Dict[str, Any]:
    """Check if a user is certified."""
    return UserService().is_user_certified(ctx, user_id)


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
def list_curation_tasks(
    project_id: str, ctx: Context
) -> List[Dict[str, Any]]:
    """List all curation tasks for a given project."""
    if not validate_synapse_id(project_id):
        return [{"error": f"Invalid Synapse ID: {project_id}"}]
    return CurationTaskService().list_tasks(ctx, project_id)


@mcp.tool(
    title="Get Curation Task",
    description=(
        "Retrieve detailed information about a specific "
        "curation task by its task ID."
    ),
    annotations=_RO,
)
def get_curation_task(
    task_id: int, ctx: Context
) -> Dict[str, Any]:
    """Get a specific curation task by its task ID."""
    return CurationTaskService().get_task(ctx, task_id)


@mcp.tool(
    title="Get Curation Task Resources",
    description=(
        "Explore and retrieve resources associated with "
        "a curation task, including RecordSets, Folders, "
        "and EntityViews."
    ),
    annotations=_RO,
)
def get_curation_task_resources(
    task_id: int, ctx: Context
) -> Dict[str, Any]:
    """Get resources associated with a curation task."""
    return CurationTaskService().get_task_resources(
        ctx, task_id
    )
