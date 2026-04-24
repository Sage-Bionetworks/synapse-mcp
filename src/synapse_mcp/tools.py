"""Tool registrations for Synapse MCP.

Every tool is declared via ``@service_tool`` (not ``@mcp.tool``
directly). See ``doc/tool-authoring.md`` for naming, description,
synonym, and sibling conventions.

This module also installs the BM25 tool-discovery transform at the
end (after every ``@service_tool`` has run), so the transform has
the full catalog to index.
"""

from typing import Any, Dict, List, Optional

from fastmcp import Context
from fastmcp.server.transforms.search import BM25SearchTransform

from .app import mcp
from .services import (
    ActivityService,
    CurationTaskService,
    DockerService,
    EntityService,
    EvaluationService,
    FormService,
    SchemaOrganizationService,
    SearchService,
    SubmissionService,
    TeamService,
    UserService,
    UtilityService,
    WikiService,
    service_tool,
)
from .utils import validate_synapse_id


# Reusable synonym sets so BM25 indexes user-language aliases for every
# relevant tool without copy-pasting the same list 8 times. Keep these
# tight: only include aliases users actually say, not every tangential
# synonym.
_ENTITY_TYPES = (
    "project",
    "folder",
    "file",
    "table",
    "view",
    "dataset",
    "dataset collection",
)
_EVALUATION_SYNONYMS = ("challenge", "queue", "competition", "leaderboard")
_SUBMISSION_SYNONYMS = ("submit", "entry", "challenge entry")
_PROVENANCE_SYNONYMS = (
    "lineage",
    "history",
    "inputs",
    "outputs",
    "derived from",
    "provenance record",
    "run",
    "execution",
)
_ANNOTATION_SYNONYMS = ("metadata", "tags", "properties", "key-value pairs")
_WIKI_SYNONYMS = ("documentation", "docs", "markdown", "page")
_TEAM_SYNONYMS = ("group", "collaborators", "members")
_SCHEMA_SYNONYMS = ("JSON schema", "validation", "data model")
_ACL_SYNONYMS = ("permissions", "access control", "sharing", "who can access")


# ---------------------------------------------------------------------------
# Domain 1: Entity Core
# ---------------------------------------------------------------------------


@service_tool(
    mcp,
    service="entity",
    operation="read",
    synapse_object="Synapse entity",
    title="Fetch Entity",
    description=(
        "Use this when the user wants the metadata, record, "
        "details, or info for a specific Synapse entity "
        "given its Synapse ID. A Synapse entity is any "
        "first-class Synapse object — project, folder, file, "
        "table, view, dataset, dataset collection, or Docker "
        "repository. Entity ID example: syn123456. Only metadata "
        "is returned; file content is never downloaded."
    ),
    synonyms=_ENTITY_TYPES + ("record", "details", "info", "fetch"),
    siblings=(
        "get_entity_annotations",
        "get_entity_children",
        "get_link",
        "search_synapse",
    ),
)
async def get_entity(entity_id: str, ctx: Context) -> Dict[str, Any]:
    """Return Synapse entity metadata by ID."""
    if not validate_synapse_id(entity_id):
        return {"error": f"Invalid Synapse ID: {entity_id}"}
    return await EntityService().get_entity(ctx, entity_id)


@service_tool(
    mcp,
    service="entity",
    operation="read",
    synapse_object="Synapse entity",
    title="Fetch Entity Annotations",
    description=(
        "Use this when the user wants the custom annotations "
        "(metadata key/value pairs) attached to a Synapse "
        "entity. Annotations are user-defined tags/properties "
        "on an entity such as tissue type, disease, assay, or "
        "any other arbitrary key/value pair. Entity ID "
        "example: syn123456. Returns only annotations — call "
        "get_entity for full entity metadata instead."
    ),
    synonyms=_ANNOTATION_SYNONYMS,
    siblings=(
        "get_entity",
        "get_entity_schema_derived_keys",
    ),
)
async def get_entity_annotations(
    entity_id: str, ctx: Context
) -> Dict[str, Any]:
    """Return custom annotations for a Synapse entity."""
    if not validate_synapse_id(entity_id):
        return {"error": f"Invalid Synapse ID: {entity_id}"}
    return await EntityService().get_annotations(ctx, entity_id)


@service_tool(
    mcp,
    service="activity",
    operation="read",
    synapse_object="Synapse entity",
    title="Fetch Entity Provenance",
    description=(
        "Use this when the user wants to know what produced a "
        "Synapse entity — its data lineage, inputs, outputs, "
        "code executed, and the activity that generated it. "
        "Works on any Synapse entity (project, folder, file, "
        "table, view, dataset). Entity ID example: syn123456. "
        "Optionally scope to a specific version of the entity."
    ),
    synonyms=_PROVENANCE_SYNONYMS,
    siblings=("get_activity", "get_entity"),
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


@service_tool(
    mcp,
    service="entity",
    operation="read",
    synapse_object="Synapse entity",
    title="List Entity Children",
    description=(
        "Use this when the user wants to list the files and "
        "sub-folders immediately inside a Synapse entity "
        "container (one level deep). Works on Projects and "
        "Folders. Entity ID example: syn123456. Call "
        "repeatedly on child folders to traverse deeper."
    ),
    synonyms=("contents", "files in folder", "listing") + _ENTITY_TYPES,
    siblings=("get_entity", "search_synapse"),
)
async def get_entity_children(
    entity_id: str, ctx: Context
) -> List[Dict[str, Any]]:
    """List children for Synapse container entities."""
    if not validate_synapse_id(entity_id):
        return [{"error": f"Invalid Synapse ID: {entity_id}"}]
    return await EntityService().get_children(ctx, entity_id)


@service_tool(
    mcp,
    service="search",
    operation="read",
    synapse_object="Synapse entity",
    title="Search Synapse",
    description=(
        "Use this when the user wants to search for Synapse "
        "entities matching a keyword, topic, or subject "
        "(e.g. 'brain tissue', 'cancer_type=glioma'). "
        "Searches across all Synapse entity types (project, "
        "folder, file, table, view, dataset). Example entity "
        "type filter: 'file'. Parent ID example: syn123456. "
        "Returns ranked matches. Use search_entity_by_name "
        "when looking up an entity by exact name, "
        "search_entities_by_md5 for MD5 hash lookups."
    ),
    synonyms=_ENTITY_TYPES
    + ("find", "lookup", "query", "discover", "keyword", "topic", "about"),
    siblings=("get_entity", "search_entity_by_name", "search_entities_by_md5"),
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


@service_tool(
    mcp,
    service="entity",
    operation="read",
    synapse_object="Synapse entity",
    title="Get Entity ACL",
    description=(
        "Use this when the user wants the sharing settings "
        "or access control list (ACL) of one single Synapse "
        "entity — who can access it and with what "
        "permissions. Entity ID example: syn123456. "
        "Optionally filter to a single principal ID (user "
        "or team), e.g. '3379097'. Use list_entity_acl to "
        "audit ACLs across many entities under a container."
    ),
    synonyms=_ACL_SYNONYMS + ("sharing settings",),
    siblings=("get_entity_permissions", "list_entity_acl"),
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


@service_tool(
    mcp,
    service="entity",
    operation="read",
    synapse_object="Synapse entity",
    title="Get Entity Permissions",
    description=(
        "Use this when the user wants to know what the "
        "currently authenticated user is allowed to do on a "
        "Synapse entity (READ, UPDATE, DELETE, etc.). Entity "
        "ID example: syn123456. Returns the caller's own "
        "permissions only — use get_entity_acl to see "
        "everyone's permissions."
    ),
    synonyms=_ACL_SYNONYMS + ("can I", "my access"),
    siblings=("get_entity_acl", "list_entity_acl"),
)
async def get_entity_permissions(
    entity_id: str, ctx: Context
) -> Dict[str, Any]:
    """Get current user's permissions on a Synapse entity."""
    if not validate_synapse_id(entity_id):
        return {"error": f"Invalid Synapse ID: {entity_id}"}
    return await EntityService().get_permissions(ctx, entity_id)


@service_tool(
    mcp,
    service="entity",
    operation="read",
    synapse_object="Synapse entity",
    title="List Entity ACL",
    description=(
        "Use this when the user wants every ACL on a Synapse "
        "entity and, with recursive=True, on all its "
        "descendants — useful for auditing sharing across a "
        "project subtree. Entity ID example: syn123456."
    ),
    synonyms=_ACL_SYNONYMS + ("audit", "recursive"),
    siblings=("get_entity_acl", "get_entity_permissions"),
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


@service_tool(
    mcp,
    service="schema",
    operation="read",
    synapse_object="Synapse entity",
    title="Get Entity Schema",
    description=(
        "Use this when the user wants to know which JSON "
        "schema (data model / validation contract) is bound "
        "to a Synapse entity. Entity ID example: syn123456. "
        "Returns the schema binding metadata, not the schema "
        "body — use get_json_schema_body for that."
    ),
    synonyms=_SCHEMA_SYNONYMS + ("bound schema", "data contract"),
    siblings=(
        "get_entity_schema_derived_keys",
        "get_entity_schema_validation_statistics",
        "get_json_schema",
    ),
)
async def get_entity_schema(
    entity_id: str, ctx: Context
) -> Dict[str, Any]:
    """Get bound JSON schema info for an entity."""
    if not validate_synapse_id(entity_id):
        return {"error": f"Invalid Synapse ID: {entity_id}"}
    return await EntityService().get_schema(ctx, entity_id)


@service_tool(
    mcp,
    service="schema",
    operation="read",
    synapse_object="Synapse entity",
    title="Get Entity Schema Derived Keys",
    description=(
        "Use this when the user wants the annotation keys a "
        "bound JSON schema requires on a Synapse entity. "
        "Useful for knowing what metadata fields a schema is "
        "enforcing. Entity ID example: syn123456."
    ),
    synonyms=_ANNOTATION_SYNONYMS
    + _SCHEMA_SYNONYMS
    + ("required fields", "expected keys"),
    siblings=(
        "get_entity_schema",
        "get_entity_annotations",
    ),
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


@service_tool(
    mcp,
    service="schema",
    operation="read",
    synapse_object="Synapse entity",
    title="Get Entity Schema Validation Statistics",
    description=(
        "Use this when the user wants an aggregate "
        "validation summary for a Synapse entity container "
        "(Folder or Project) with a bound JSON schema — how "
        "many child entities pass or fail validation. Entity "
        "ID example: syn123456."
    ),
    synonyms=_SCHEMA_SYNONYMS + ("compliance", "summary", "pass fail"),
    siblings=(
        "get_entity_schema_invalid_validations",
        "get_entity_schema",
    ),
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


@service_tool(
    mcp,
    service="schema",
    operation="read",
    synapse_object="Synapse entity",
    title="Get Entity Schema Invalid Validations",
    description=(
        "Use this when the user wants the list of Synapse "
        "entities inside a Folder or Project that currently "
        "fail their bound JSON schema — the 'what's broken' "
        "view. Container entity ID example: syn123456."
    ),
    synonyms=_SCHEMA_SYNONYMS + ("failing", "invalid", "broken"),
    siblings=(
        "get_entity_schema_validation_statistics",
        "get_entity_schema",
    ),
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


@service_tool(
    mcp,
    service="activity",
    operation="read",
    synapse_object="Synapse activity",
    title="Get Activity",
    description=(
        "Use this when the user has a standalone Synapse "
        "activity (provenance record) they want to look up "
        "by activity ID, or when they want the activity that "
        "produced a specific entity version. Activity ID "
        "example: '9660001'. Parent entity ID example: "
        "syn123456."
    ),
    synonyms=_PROVENANCE_SYNONYMS,
    siblings=("get_entity_provenance",),
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


@service_tool(
    mcp,
    service="entity",
    operation="read",
    synapse_object="Synapse Link entity",
    title="Get Link",
    description=(
        "Use this when the user has a Synapse Link entity "
        "(a shortcut that points at another entity) and "
        "wants either the Link's own metadata or the target "
        "it resolves to. Link entity ID example: syn123456. "
        "Set follow_link=False to inspect the Link itself "
        "instead of its target."
    ),
    synonyms=("shortcut", "alias", "pointer", "reference"),
    siblings=("get_entity",),
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
# Domain 8: Wiki
# ---------------------------------------------------------------------------


@service_tool(
    mcp,
    service="wiki",
    operation="read",
    synapse_object="Synapse wiki",
    title="Get Wiki Page",
    description=(
        "Use this when the user wants to read a Synapse "
        "wiki page — its markdown content and metadata — "
        "attached to a project, folder, or file. A Synapse "
        "wiki is the markdown documentation surfaced on an "
        "entity. Owner entity ID example: syn123456. Omit "
        "wiki_id to get the root wiki page."
    ),
    synonyms=_WIKI_SYNONYMS + ("readme", "content"),
    siblings=(
        "get_wiki_headers",
        "get_wiki_history",
        "get_wiki_order_hint",
    ),
)
async def get_wiki_page(
    owner_id: str,
    ctx: Context,
    wiki_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Get a wiki page's content and metadata."""
    if not validate_synapse_id(owner_id):
        return {"error": f"Invalid Synapse ID: {owner_id}"}
    return await WikiService().get_wiki_page(
        ctx, owner_id, wiki_id
    )


@service_tool(
    mcp,
    service="wiki",
    operation="read",
    synapse_object="Synapse wiki",
    title="Get Wiki Headers",
    description=(
        "Use this when the user wants the table of contents "
        "of a Synapse wiki — the list of pages and sub-pages "
        "attached to an entity. Owner entity ID example: "
        "syn123456. If the result hits the limit, call again "
        "with a higher offset to paginate."
    ),
    synonyms=_WIKI_SYNONYMS + ("toc", "table of contents", "navigation"),
    siblings=(
        "get_wiki_page",
        "get_wiki_history",
        "get_wiki_order_hint",
    ),
)
async def get_wiki_headers(
    owner_id: str,
    ctx: Context,
    offset: int = 0,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """Get the wiki table of contents for an entity."""
    if not validate_synapse_id(owner_id):
        return [{"error": f"Invalid Synapse ID: {owner_id}"}]
    return await WikiService().get_wiki_headers(
        ctx, owner_id, offset, limit
    )


@service_tool(
    mcp,
    service="wiki",
    operation="read",
    synapse_object="Synapse wiki",
    title="Get Wiki History",
    description=(
        "Use this when the user wants the revision history "
        "(edit log) of a specific Synapse wiki page — who "
        "changed it and when. Owner entity ID example: "
        "syn123456. Wiki ID example: '123456' (numeric "
        "wiki page id). Paginate via offset if needed."
    ),
    synonyms=_WIKI_SYNONYMS
    + ("revisions", "edits", "changelog"),
    siblings=(
        "get_wiki_page",
        "get_wiki_headers",
    ),
)
async def get_wiki_history(
    owner_id: str,
    wiki_id: str,
    ctx: Context,
    offset: int = 0,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """Get revision history of a wiki page."""
    if not validate_synapse_id(owner_id):
        return [{"error": f"Invalid Synapse ID: {owner_id}"}]
    return await WikiService().get_wiki_history(
        ctx, owner_id, wiki_id, offset, limit
    )


@service_tool(
    mcp,
    service="wiki",
    operation="read",
    synapse_object="Synapse wiki",
    title="Get Wiki Order Hint",
    description=(
        "Use this when the user wants to know the display "
        "order of sub-pages in a Synapse wiki — how the wiki "
        "navigation is sorted. Owner entity ID example: "
        "syn123456."
    ),
    synonyms=_WIKI_SYNONYMS + ("order", "sort", "arrangement"),
    siblings=(
        "get_wiki_page",
        "get_wiki_headers",
    ),
)
async def get_wiki_order_hint(
    owner_id: str, ctx: Context
) -> Dict[str, Any]:
    """Get wiki page display ordering."""
    if not validate_synapse_id(owner_id):
        return {"error": f"Invalid Synapse ID: {owner_id}"}
    return await WikiService().get_wiki_order_hint(ctx, owner_id)


# ---------------------------------------------------------------------------
# Domain 9: Team & User
# ---------------------------------------------------------------------------


@service_tool(
    mcp,
    service="team",
    operation="read",
    synapse_object="Synapse team",
    title="Get Team",
    description=(
        "Use this when the user wants a Synapse team by its "
        "numeric ID or name. A Synapse team is a group of "
        "users (collaborators, members) that can be granted "
        "access to entities collectively. Team ID example: "
        "'3379097'. Team name example: 'NF-OSI Curators'."
    ),
    synonyms=_TEAM_SYNONYMS,
    siblings=(
        "get_team_members",
        "get_team_open_invitations",
        "get_team_membership_status",
    ),
)
async def get_team(
    ctx: Context,
    team_id: Optional[int] = None,
    team_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Get a Synapse Team by ID or name."""
    return await TeamService().get_team(ctx, team_id, team_name)


@service_tool(
    mcp,
    service="team",
    operation="read",
    synapse_object="Synapse team",
    title="Get Team Members",
    description=(
        "Use this when the user wants the roster of a "
        "Synapse team — who is on it. Team ID example: "
        "'3379097'."
    ),
    synonyms=_TEAM_SYNONYMS + ("roster", "who"),
    siblings=(
        "get_team",
        "get_team_membership_status",
        "get_team_open_invitations",
    ),
)
async def get_team_members(
    team_id: int, ctx: Context
) -> List[Dict[str, Any]]:
    """List all members of a Team."""
    return await TeamService().get_team_members(ctx, team_id)


@service_tool(
    mcp,
    service="team",
    operation="read",
    synapse_object="Synapse team",
    title="Get Team Open Invitations",
    description=(
        "Use this when the user wants the pending (not yet "
        "accepted or rejected) invitations for a Synapse "
        "team. Team ID example: '3379097'."
    ),
    synonyms=_TEAM_SYNONYMS + ("pending", "invited", "invite"),
    siblings=(
        "get_team",
        "get_team_members",
        "get_team_membership_status",
    ),
)
async def get_team_open_invitations(
    team_id: int, ctx: Context
) -> List[Dict[str, Any]]:
    """List pending Team invitations."""
    return await TeamService().get_team_open_invitations(
        ctx, team_id
    )


@service_tool(
    mcp,
    service="team",
    operation="read",
    synapse_object="Synapse team",
    title="Get Team Membership Status",
    description=(
        "Use this when the user wants to know whether a "
        "specific Synapse user is already a member of, has "
        "applied to, or has been invited to a Synapse team. "
        "Team ID example: '3379097'. User ID example: "
        "'1234567'."
    ),
    synonyms=_TEAM_SYNONYMS + ("is member", "joined", "status"),
    siblings=(
        "get_team",
        "get_team_members",
        "get_team_open_invitations",
    ),
)
async def get_team_membership_status(
    team_id: int, user_id: str, ctx: Context
) -> Dict[str, Any]:
    """Check a user's Team membership status."""
    return await TeamService().get_team_membership_status(
        ctx, team_id, user_id
    )


@service_tool(
    mcp,
    service="user",
    operation="read",
    synapse_object="Synapse user",
    title="Get User Profile",
    description=(
        "Use this when the user wants a Synapse user profile "
        "by numeric user ID or username, or the "
        "authenticated caller's own profile when called with "
        "no arguments. User ID example: '1234567'. Username "
        "example: 'janedoe'."
    ),
    synonyms=("profile", "account", "person", "me", "whoami"),
    siblings=("check_user_certified",),
)
async def get_user_profile(
    ctx: Context,
    user_id: Optional[int] = None,
    username: Optional[str] = None,
) -> Dict[str, Any]:
    """Get a Synapse user profile."""
    return await UserService().get_user_profile(
        ctx, user_id, username
    )


@service_tool(
    mcp,
    service="user",
    operation="read",
    synapse_object="Synapse user",
    title="Check User Certified",
    description=(
        "Use this when the user wants to know whether a "
        "Synapse user has passed the certification quiz "
        "required for uploading human data. User ID "
        "example: '1234567'."
    ),
    synonyms=("certification", "quiz", "passed", "qualified"),
    siblings=("get_user_profile",),
)
async def check_user_certified(
    user_id: int, ctx: Context
) -> Dict[str, Any]:
    """Check if a user is certified."""
    return await UserService().is_user_certified(ctx, user_id)


# ---------------------------------------------------------------------------
# Domain 10: Evaluation (Challenge Queue)
# ---------------------------------------------------------------------------


@service_tool(
    mcp,
    service="evaluation",
    operation="read",
    synapse_object="Synapse evaluation",
    title="Get Evaluation",
    description=(
        "Use this when the user wants a Synapse Evaluation "
        "queue — the challenge/competition queue that "
        "participants submit models or results to. "
        "Synonymous with 'challenge queue', 'leaderboard "
        "queue'. Evaluation ID example: '9600001'. "
        "Evaluation name example: 'DREAM Patient Data'."
    ),
    synonyms=_EVALUATION_SYNONYMS,
    siblings=(
        "list_evaluations",
        "get_evaluation_acl",
        "get_evaluation_permissions",
    ),
)
async def get_evaluation(
    ctx: Context,
    evaluation_id: Optional[str] = None,
    evaluation_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Get an Evaluation by ID or name."""
    return await EvaluationService().get_evaluation(
        ctx, evaluation_id, evaluation_name
    )


@service_tool(
    mcp,
    service="evaluation",
    operation="read",
    synapse_object="Synapse evaluation",
    title="List Evaluations",
    description=(
        "Use this when the user wants to enumerate Synapse "
        "Evaluation queues (challenges, competitions, "
        "leaderboards) — optionally filtered by project, "
        "access type, or active-only. Project ID example: "
        "syn123456. Paginate via offset."
    ),
    synonyms=_EVALUATION_SYNONYMS,
    siblings=(
        "get_evaluation",
        "get_evaluation_acl",
        "list_evaluation_submissions",
    ),
)
async def list_evaluations(
    ctx: Context,
    project_id: Optional[str] = None,
    access_type: Optional[str] = None,
    active_only: Optional[bool] = None,
    available_only: bool = False,
    evaluation_ids: Optional[List[str]] = None,
    offset: int = 0,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """List evaluations with filters."""
    return await EvaluationService().list_evaluations(
        ctx,
        project_id=project_id,
        access_type=access_type,
        active_only=active_only,
        available_only=available_only,
        evaluation_ids=evaluation_ids,
        offset=offset,
        limit=limit,
    )


@service_tool(
    mcp,
    service="evaluation",
    operation="read",
    synapse_object="Synapse evaluation",
    title="Get Evaluation ACL",
    description=(
        "Use this when the user wants the access control "
        "list of a Synapse Evaluation queue (challenge "
        "queue) — who is allowed to submit, administer, or "
        "view. Evaluation ID example: '9600001'."
    ),
    synonyms=_EVALUATION_SYNONYMS + _ACL_SYNONYMS,
    siblings=(
        "get_evaluation",
        "get_evaluation_permissions",
    ),
)
async def get_evaluation_acl(
    evaluation_id: str, ctx: Context
) -> Dict[str, Any]:
    """Get ACL for an Evaluation queue."""
    return await EvaluationService().get_evaluation_acl(
        ctx, evaluation_id
    )


@service_tool(
    mcp,
    service="evaluation",
    operation="read",
    synapse_object="Synapse evaluation",
    title="Get Evaluation Permissions",
    description=(
        "Use this when the user wants to know what the "
        "authenticated caller is allowed to do on a Synapse "
        "Evaluation queue (challenge queue) — submit, "
        "administer, etc. Evaluation ID example: '9600001'."
    ),
    synonyms=_EVALUATION_SYNONYMS + _ACL_SYNONYMS + ("my access",),
    siblings=(
        "get_evaluation",
        "get_evaluation_acl",
    ),
)
async def get_evaluation_permissions(
    evaluation_id: str, ctx: Context
) -> Dict[str, Any]:
    """Get permissions on an Evaluation queue."""
    return await EvaluationService().get_evaluation_permissions(
        ctx, evaluation_id
    )


# ---------------------------------------------------------------------------
# Domain 11: Submission
# ---------------------------------------------------------------------------


@service_tool(
    mcp,
    service="submission",
    operation="read",
    synapse_object="Synapse submission",
    title="Get Submission",
    description=(
        "Use this when the user wants a specific Synapse "
        "submission — a challenge entry a participant sent "
        "to an Evaluation queue. Submission ID example: "
        "'9722233'."
    ),
    synonyms=_SUBMISSION_SYNONYMS + _EVALUATION_SYNONYMS,
    siblings=(
        "get_submission_status",
        "list_evaluation_submissions",
        "list_my_submissions",
    ),
)
async def get_submission(
    submission_id: str, ctx: Context
) -> Dict[str, Any]:
    """Get a Submission by ID."""
    return await SubmissionService().get_submission(
        ctx, submission_id
    )


@service_tool(
    mcp,
    service="submission",
    operation="read",
    synapse_object="Synapse submission",
    title="List Evaluation Submissions",
    description=(
        "Use this when the user wants ALL submissions "
        "(every challenge entry from every participant) "
        "sent to a Synapse Evaluation queue — optionally "
        "filtered by status (SCORED, INVALID, etc.). NOT "
        "just the caller's own — use list_my_submissions "
        "for that. Evaluation ID example: '9600001'. "
        "Returns raw Submission objects; use "
        "list_submission_statuses for status-only data and "
        "list_evaluation_submission_bundles for bundled "
        "submission+status pairs."
    ),
    synonyms=_SUBMISSION_SYNONYMS
    + _EVALUATION_SYNONYMS
    + ("all entries", "all submissions", "everyone"),
    siblings=(
        "list_submission_statuses",
        "list_evaluation_submission_bundles",
        "list_my_submissions",
    ),
)
async def list_evaluation_submissions(
    evaluation_id: str,
    ctx: Context,
    status: Optional[str] = None,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """List submissions to an Evaluation."""
    return await SubmissionService().list_evaluation_submissions(
        ctx, evaluation_id, status, limit
    )


@service_tool(
    mcp,
    service="submission",
    operation="read",
    synapse_object="Synapse submission",
    title="List My Submissions",
    description=(
        "Use this when the user wants their own submissions "
        "(challenge entries) to a Synapse Evaluation queue. "
        "Evaluation ID example: '9600001'."
    ),
    synonyms=_SUBMISSION_SYNONYMS
    + _EVALUATION_SYNONYMS
    + ("mine", "my entries"),
    siblings=(
        "list_my_submission_bundles",
        "list_evaluation_submissions",
    ),
)
async def list_my_submissions(
    evaluation_id: str,
    ctx: Context,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """List current user's submissions."""
    return await SubmissionService().list_my_submissions(
        ctx, evaluation_id, limit
    )


@service_tool(
    mcp,
    service="submission",
    operation="read",
    synapse_object="Synapse submission",
    title="Get Submission Count",
    description=(
        "Use this when the user wants only the count of "
        "Synapse submissions (challenge entries) in an "
        "Evaluation queue, not the submissions themselves. "
        "Evaluation ID example: '9600001'."
    ),
    synonyms=_SUBMISSION_SYNONYMS
    + _EVALUATION_SYNONYMS
    + ("count", "how many", "total"),
    siblings=(
        "list_evaluation_submissions",
        "list_submission_statuses",
    ),
)
async def get_submission_count(
    evaluation_id: str, ctx: Context
) -> Dict[str, Any]:
    """Get submission count for an Evaluation."""
    return await SubmissionService().get_submission_count(
        ctx, evaluation_id
    )


@service_tool(
    mcp,
    service="submission",
    operation="read",
    synapse_object="Synapse submission",
    title="Get Submission Status",
    description=(
        "Use this when the user wants the scoring status of "
        "a single Synapse submission (challenge entry) — "
        "e.g. RECEIVED, EVALUATION_IN_PROGRESS, SCORED. "
        "Submission ID example: '9722233'."
    ),
    synonyms=_SUBMISSION_SYNONYMS + ("scored", "state", "progress"),
    siblings=(
        "list_submission_statuses",
        "get_submission",
    ),
)
async def get_submission_status(
    submission_id: str, ctx: Context
) -> Dict[str, Any]:
    """Get status of a Submission."""
    return await SubmissionService().get_submission_status(
        ctx, submission_id
    )


@service_tool(
    mcp,
    service="submission",
    operation="read",
    synapse_object="Synapse submission",
    title="List Submission Statuses",
    description=(
        "Use this when the user wants the scoring statuses "
        "of every Synapse submission in an Evaluation queue "
        "— optionally filtered (SCORED, INVALID, etc.). "
        "Evaluation ID example: '9600001'. Returns status "
        "records only; use list_evaluation_submissions for "
        "the submissions themselves."
    ),
    synonyms=_SUBMISSION_SYNONYMS + _EVALUATION_SYNONYMS + ("scored",),
    siblings=(
        "list_evaluation_submissions",
        "list_evaluation_submission_bundles",
        "get_submission_status",
    ),
)
async def list_submission_statuses(
    evaluation_id: str,
    ctx: Context,
    status: Optional[str] = None,
    limit: int = 10,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    """List submission statuses for an Evaluation."""
    return await SubmissionService().list_submission_statuses(
        ctx, evaluation_id, status, limit, offset
    )


@service_tool(
    mcp,
    service="submission",
    operation="read",
    synapse_object="Synapse submission",
    title="List Evaluation Submission Bundles",
    description=(
        "Use this when the user wants Synapse submission "
        "plus scoring status together (as bundles) for an "
        "Evaluation queue — one call returns both sides. "
        "Evaluation ID example: '9600001'."
    ),
    synonyms=_SUBMISSION_SYNONYMS + _EVALUATION_SYNONYMS + ("bundle",),
    siblings=(
        "list_evaluation_submissions",
        "list_submission_statuses",
        "list_my_submission_bundles",
    ),
)
async def list_evaluation_submission_bundles(
    evaluation_id: str,
    ctx: Context,
    status: Optional[str] = None,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """List submission bundles for an Evaluation."""
    return await SubmissionService().list_evaluation_submission_bundles(
        ctx, evaluation_id, status, limit
    )


@service_tool(
    mcp,
    service="submission",
    operation="read",
    synapse_object="Synapse submission",
    title="List My Submission Bundles",
    description=(
        "Use this when the user wants their own Synapse "
        "submission+status bundles for an Evaluation queue "
        "— one call returns both submission and scoring "
        "status for every entry they made. Evaluation ID "
        "example: '9600001'."
    ),
    synonyms=_SUBMISSION_SYNONYMS
    + _EVALUATION_SYNONYMS
    + ("mine", "my entries", "bundle"),
    siblings=(
        "list_my_submissions",
        "list_evaluation_submission_bundles",
    ),
)
async def list_my_submission_bundles(
    evaluation_id: str,
    ctx: Context,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """List current user's submission bundles."""
    return await SubmissionService().list_my_submission_bundles(
        ctx, evaluation_id, limit
    )


# ---------------------------------------------------------------------------
# Domain 13: Curation Tasks
# ---------------------------------------------------------------------------


@service_tool(
    mcp,
    service="curation",
    operation="read",
    synapse_object="Synapse curation task",
    title="List Curation Tasks",
    description=(
        "Use this when the user wants every Synapse "
        "curation task in a project — the queue of "
        "data-curation work items attached to that "
        "project. Project entity ID example: syn123456."
    ),
    synonyms=("curator", "work items", "queue", "backlog"),
    siblings=(
        "get_curation_task",
        "get_curation_task_resources",
    ),
)
async def list_curation_tasks(
    project_id: str, ctx: Context
) -> List[Dict[str, Any]]:
    """List all curation tasks for a given project."""
    if not validate_synapse_id(project_id):
        return [{"error": f"Invalid Synapse ID: {project_id}"}]
    return await CurationTaskService().list_tasks(ctx, project_id)


@service_tool(
    mcp,
    service="curation",
    operation="read",
    synapse_object="Synapse curation task",
    title="Get Curation Task",
    description=(
        "Use this when the user wants the details of a "
        "single Synapse curation task by its numeric task "
        "ID. Task ID example: 42."
    ),
    synonyms=("curator", "work item", "todo"),
    siblings=(
        "list_curation_tasks",
        "get_curation_task_resources",
    ),
)
async def get_curation_task(
    task_id: int, ctx: Context
) -> Dict[str, Any]:
    """Get a specific curation task by its task ID."""
    return await CurationTaskService().get_task(ctx, task_id)


@service_tool(
    mcp,
    service="curation",
    operation="read",
    synapse_object="Synapse curation task",
    title="Get Curation Task Resources",
    description=(
        "Use this when the user wants the Synapse "
        "resources (RecordSets, Folders, EntityViews) "
        "linked to a curation task — the data the curator "
        "will act on. Task ID example: 42."
    ),
    synonyms=("curator", "recordset", "entityview", "resources"),
    siblings=(
        "list_curation_tasks",
        "get_curation_task",
    ),
)
async def get_curation_task_resources(
    task_id: int, ctx: Context
) -> Dict[str, Any]:
    """Get resources associated with a curation task."""
    return await CurationTaskService().get_task_resources(
        ctx, task_id
    )


# ---------------------------------------------------------------------------
# Domain 12: JSON Schema Organizations
# ---------------------------------------------------------------------------


@service_tool(
    mcp,
    service="organization",
    operation="read",
    synapse_object="Synapse JSON Schema Organization",
    title="Get Schema Organization",
    description=(
        "Use this when the user wants a Synapse JSON Schema "
        "Organization (namespace that owns a set of JSON "
        "schemas / data models) by name or numeric ID. "
        "Organization name example: 'org.sagebionetworks'. "
        "Organization ID example: 42."
    ),
    synonyms=_SCHEMA_SYNONYMS + ("namespace", "owner"),
    siblings=(
        "get_schema_organization_acl",
        "list_json_schemas",
    ),
)
async def get_schema_organization(
    ctx: Context,
    organization_name: Optional[str] = None,
    organization_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Get a Schema Organization by name or ID."""
    return await SchemaOrganizationService().get_schema_organization(
        ctx, organization_name, organization_id
    )


@service_tool(
    mcp,
    service="organization",
    operation="read",
    synapse_object="Synapse JSON Schema Organization",
    title="Get Schema Organization ACL",
    description=(
        "Use this when the user wants the ACL of a Synapse "
        "JSON Schema Organization — who may publish schemas "
        "under that namespace. Organization name example: "
        "'org.sagebionetworks'."
    ),
    synonyms=_SCHEMA_SYNONYMS + _ACL_SYNONYMS,
    siblings=("get_schema_organization",),
)
async def get_schema_organization_acl(
    organization_name: str, ctx: Context
) -> Dict[str, Any]:
    """Get ACL for a Schema Organization."""
    return await SchemaOrganizationService().get_schema_organization_acl(
        ctx, organization_name
    )


@service_tool(
    mcp,
    service="schema",
    operation="read",
    synapse_object="Synapse JSON Schema",
    title="List JSON Schemas",
    description=(
        "Use this when the user wants every Synapse JSON "
        "Schema (data model, validation contract) owned by "
        "an organization. Organization name example: "
        "'org.sagebionetworks'."
    ),
    synonyms=_SCHEMA_SYNONYMS,
    siblings=(
        "get_json_schema",
        "list_json_schema_versions",
        "get_schema_organization",
    ),
)
async def list_json_schemas(
    organization_name: str, ctx: Context
) -> List[Dict[str, Any]]:
    """List schemas in an organization."""
    return await SchemaOrganizationService().list_json_schemas(
        ctx, organization_name
    )


@service_tool(
    mcp,
    service="schema",
    operation="read",
    synapse_object="Synapse JSON Schema",
    title="Get JSON Schema",
    description=(
        "Use this when the user wants metadata about a "
        "specific Synapse JSON Schema (data model, "
        "validation contract). Organization name example: "
        "'org.sagebionetworks'. Schema name example: "
        "'myDataset-1.0.0'."
    ),
    synonyms=_SCHEMA_SYNONYMS,
    siblings=(
        "list_json_schemas",
        "get_json_schema_body",
        "list_json_schema_versions",
    ),
)
async def get_json_schema(
    organization_name: str,
    schema_name: str,
    ctx: Context,
) -> Dict[str, Any]:
    """Get metadata for a JSON Schema."""
    return await SchemaOrganizationService().get_json_schema(
        ctx, organization_name, schema_name
    )


@service_tool(
    mcp,
    service="schema",
    operation="read",
    synapse_object="Synapse JSON Schema",
    title="Get JSON Schema Body",
    description=(
        "Use this when the user wants the raw JSON document "
        "of a Synapse JSON Schema — the actual data model / "
        "validation rules. Organization name example: "
        "'org.sagebionetworks'. Schema name example: "
        "'myDataset-1.0.0'."
    ),
    synonyms=_SCHEMA_SYNONYMS + ("body", "document", "raw"),
    siblings=(
        "get_json_schema",
        "list_json_schema_versions",
    ),
)
async def get_json_schema_body(
    organization_name: str,
    schema_name: str,
    ctx: Context,
    version: Optional[str] = None,
) -> Dict[str, Any]:
    """Get the raw JSON schema document."""
    return await SchemaOrganizationService().get_json_schema_body(
        ctx, organization_name, schema_name, version
    )


@service_tool(
    mcp,
    service="schema",
    operation="read",
    synapse_object="Synapse JSON Schema",
    title="List JSON Schema Versions",
    description=(
        "Use this when the user wants every version "
        "published for a Synapse JSON Schema. Organization "
        "name example: 'org.sagebionetworks'. Schema name "
        "example: 'myDataset-1.0.0'."
    ),
    synonyms=_SCHEMA_SYNONYMS + ("versions", "releases"),
    siblings=(
        "get_json_schema",
        "get_json_schema_body",
    ),
)
async def list_json_schema_versions(
    organization_name: str,
    schema_name: str,
    ctx: Context,
) -> List[Dict[str, Any]]:
    """List versions of a JSON Schema."""
    return await SchemaOrganizationService().list_json_schema_versions(
        ctx, organization_name, schema_name
    )


# ---------------------------------------------------------------------------
# Domain 14: Forms
# ---------------------------------------------------------------------------


@service_tool(
    mcp,
    service="form",
    operation="read",
    synapse_object="Synapse FormGroup",
    title="List Form Data",
    description=(
        "Use this when the user wants the form submissions "
        "for a Synapse FormGroup — a collection of "
        "structured-data forms submitted by users. Form "
        "group ID example: '42'. Optionally filter by state "
        "('SUBMITTED_WAITING_FOR_REVIEW', 'ACCEPTED', etc.)."
    ),
    synonyms=("form", "survey", "intake", "questionnaire"),
    siblings=(),
)
async def list_form_data(
    group_id: str,
    ctx: Context,
    filter_by_state: Optional[List[str]] = None,
    as_reviewer: bool = False,
) -> List[Dict[str, Any]]:
    """List form submissions for a FormGroup."""
    return await FormService().list_form_data(
        ctx, group_id, filter_by_state, as_reviewer
    )


# ---------------------------------------------------------------------------
# Domain 14: Utility Operations
# ---------------------------------------------------------------------------


@service_tool(
    mcp,
    service="utility",
    operation="read",
    synapse_object="Synapse entity",
    title="Search Entity By Name",
    description=(
        "Use this when the user has a file name or Synapse "
        "entity name (and optionally its parent folder or "
        "project) but does not know the Synapse ID — "
        "resolves a name to its Synapse ID. Parent entity "
        "ID example: syn123456. Name example: 'sample.csv'."
    ),
    synonyms=(
        "lookup",
        "find",
        "resolve",
        "by name",
        "named",
        "filename",
        "id of",
        "synapse id",
    ),
    siblings=("search_synapse", "check_synapse_id"),
)
async def search_entity_by_name(
    name: str,
    ctx: Context,
    parent_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Find an entity's Synapse ID by name and parent."""
    return await UtilityService().find_entity_id(
        ctx, name, parent_id
    )


@service_tool(
    mcp,
    service="utility",
    operation="read",
    synapse_object="Synapse",
    title="Validate Synapse ID",
    description=(
        "Use this when the user has a string that looks "
        "like a Synapse ID (e.g. syn123456) and wants to "
        "check whether the ID exist or does exist — verify "
        "it is valid by querying the Synapse backend."
    ),
    synonyms=(
        "exist",
        "exists",
        "verify",
        "validate",
        "does exist",
        "is valid",
    ),
    siblings=("get_entity", "search_entity_by_name"),
)
async def check_synapse_id(
    syn_id: str, ctx: Context
) -> Dict[str, Any]:
    """Validate whether a Synapse ID exists."""
    return await UtilityService().is_synapse_id(ctx, syn_id)


@service_tool(
    mcp,
    service="utility",
    operation="read",
    synapse_object="Synapse entity",
    title="Search Entities By MD5",
    description=(
        "Use this when the user has an MD5 hash of a file "
        "and wants the Synapse entities (file entities) "
        "whose attached file has that exact MD5 — useful "
        "for deduplication and 'is this already in Synapse' "
        "checks. MD5 example: '9e107d9d372bb6826bd81d3542a419d6'."
    ),
    synonyms=("hash", "checksum", "deduplicate"),
    siblings=("search_synapse", "search_entity_by_name"),
)
async def search_entities_by_md5(
    md5: str, ctx: Context
) -> Dict[str, Any]:
    """Find entities by MD5 hash."""
    return await UtilityService().md5_query(ctx, md5)


# ---------------------------------------------------------------------------
# Domain 15: DockerRepository
# ---------------------------------------------------------------------------


@service_tool(
    mcp,
    service="docker",
    operation="read",
    synapse_object="Synapse Docker repository",
    title="Get Docker Repository",
    description=(
        "Use this when the user wants a Synapse Docker "
        "repository entity — a first-class Synapse object "
        "that points to a Docker image stored in Synapse's "
        "container registry. NOT a general Docker "
        "container, NOT a container runtime, NOT a Docker "
        "daemon — this is the Synapse metadata record for "
        "an image. Entity ID example: syn123456. ACL and "
        "caller permissions use the generic entity ACL "
        "tools."
    ),
    synonyms=(
        "synapse docker",
        "docker image",
        "image repository",
        "container registry entity",
    ),
    siblings=("get_entity", "get_entity_acl"),
)
async def get_docker_repository(
    entity_id: str, ctx: Context
) -> Dict[str, Any]:
    """Get a DockerRepository entity by Synapse ID."""
    if not validate_synapse_id(entity_id):
        return {"error": f"Invalid Synapse ID: {entity_id}"}
    return await DockerService().get_docker_repository(
        ctx, entity_id
    )


# ---------------------------------------------------------------------------
# Discovery: BM25 search transform
# ---------------------------------------------------------------------------
# Applied after all tools are registered so the transform has the full
# catalog to index. The LLM's default view becomes the two pinned tools
# plus the synthetic ``search_tools`` / ``call_tool`` pair; every other
# tool is reached by calling ``search_tools`` with a natural-language
# query and then invoking ``call_tool``.


def _configure_discovery_transforms() -> None:
    """Register the BM25 search transform on the live FastMCP server."""
    mcp.add_transform(
        BM25SearchTransform(
            max_results=7,
            always_visible=["search_synapse", "get_entity"],
        )
    )


_configure_discovery_transforms()
