"""Tool registrations for Synapse MCP.

Every tool is declared via ``@service_tool`` (not ``@mcp.tool``
directly). See ``doc/tool-authoring.md`` for naming, description,
synonym, and sibling conventions.

This module also installs the BM25 tool-discovery transform at the
end (after every ``@service_tool`` has run), so the transform has
the full catalog to index.
"""

import warnings
from typing import Annotated, Any, Dict, List, Optional

from fastmcp import Context
from pydantic import Field
from pydantic.json_schema import PydanticJsonSchemaWarning

from .app import mcp
from .discovery import SplitCallTransform
from .services import (
    ActivityService,
    CurationTaskService,
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
from .tool_types import (
    UNSET,
    ColumnSpec,
    EntityAccessType,
    EntityType,
    EvaluationAccessType,
    OrganizationAccessType,
    ProvenanceSpec,
    SubmissionStatusValue,
    TaskProperties,
    ViewScopeType,
)
from .utils import validate_synapse_id

# Update tools default optional fields to the UNSET sentinel so an omitted
# argument (leave unchanged) is distinguishable from an explicit null (clear).
# pydantic warns that this non-JSON default is dropped from the schema, which
# is exactly what we want — silence that one cosmetic warning at import.
# Match by message so unrelated PydanticJsonSchemaWarnings still surface.
warnings.filterwarnings(
    "ignore",
    message=r"Default value UNSET is not JSON serializable",
    category=PydanticJsonSchemaWarning,
)


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
_CREATE_SYNONYMS = ("create", "make", "new", "add")
_UPDATE_SYNONYMS = ("update", "edit", "modify", "change", "set", "rename")
_DELETE_SYNONYMS = ("delete", "remove", "destroy")


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
    return await EntityService.get_entity(ctx, entity_id)


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
    return await EntityService.get_annotations(ctx, entity_id)


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
        "table, view, dataset). Look up by entity ID (with "
        "optional version) or by Activity ID directly. Entity "
        "ID example: syn123456. Activity ID example: 9660001."
    ),
    synonyms=_PROVENANCE_SYNONYMS,
    siblings=("get_entity",),
)
async def get_entity_provenance(
    ctx: Context,
    entity_id: Optional[str] = None,
    version: Optional[int] = None,
    activity_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Return provenance/activity metadata for a Synapse entity."""
    if entity_id is None and activity_id is None:
        return {
            "error": "Either entity_id or activity_id is required",
        }
    if entity_id is not None and not validate_synapse_id(entity_id):
        return {"error": f"Invalid Synapse ID: {entity_id}"}
    if version is not None and entity_id is None:
        return {
            "error": (
                "version is only valid when entity_id is provided"
            ),
        }
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
    return await ActivityService.get_provenance(
        ctx,
        entity_id=entity_id,
        version=version,
        activity_id=activity_id,
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
    return await EntityService.get_children(ctx, entity_id)


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
    return await SearchService.search(
        ctx,
        query_term=query_term,
        name=name,
        entity_type=entity_type,
        entity_types=entity_types,
        parent_id=parent_id,
        limit=limit,
        offset=offset,
    )


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
    return await EntityService.get_acl(
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
    return await EntityService.get_permissions(ctx, entity_id)


@service_tool(
    mcp,
    service="entity",
    operation="read",
    synapse_object="Synapse entity",
    title="List Entity ACL",
    description=(
        "Use this when the user wants every ACL on a Synapse "
        "entity and, with recursive=True, on all its "
        "descendants — useful for auditing sharing recursively "
        "across a project subtree. Set "
        "include_container_content=True to include files and "
        "folders inside containers; recursive=True requires "
        "include_container_content=True and walks into child "
        "containers as well. Entity ID example: syn123456."
    ),
    synonyms=_ACL_SYNONYMS + ("audit", "recursive"),
    siblings=("get_entity_acl", "get_entity_permissions"),
)
async def list_entity_acl(
    entity_id: str,
    ctx: Context,
    recursive: bool = False,
    include_container_content: bool = False,
    target_entity_types: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """List all ACLs under an entity."""
    if not validate_synapse_id(entity_id):
        return {"error": f"Invalid Synapse ID: {entity_id}"}
    return await EntityService.list_acl(
        ctx,
        entity_id,
        recursive,
        include_container_content,
        target_entity_types,
    )


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
    return await EntityService.get_schema(ctx, entity_id)


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
    return await EntityService.get_schema_derived_keys(
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
    return await EntityService.get_schema_validation_statistics(
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
    return await EntityService.get_schema_invalid_validations(
        ctx, entity_id
    )


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
    return await EntityService.get_link(
        ctx, entity_id, follow_link
    )


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
    return await WikiService.get_wiki_page(
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
    return await WikiService.get_wiki_headers(
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
    return await WikiService.get_wiki_history(
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
    return await WikiService.get_wiki_order_hint(ctx, owner_id)


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
    return await TeamService.get_team(ctx, team_id, team_name)


@service_tool(
    mcp,
    service="team",
    operation="read",
    synapse_object="Synapse team",
    title="Get Team Members",
    description=(
        "Use this when the user wants the roster of a "
        "Synapse team — who is on it. Pages through the "
        "team membership API; pass an increased ``offset`` "
        "to fetch the next batch. Team ID example: "
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
    team_id: int,
    ctx: Context,
    offset: int = 0,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """List members of a Team."""
    return await TeamService.get_team_members(
        ctx, team_id, offset=offset, limit=limit
    )


@service_tool(
    mcp,
    service="team",
    operation="read",
    synapse_object="Synapse team",
    title="Get Team Open Invitations",
    description=(
        "Use this when the user wants the pending (not yet "
        "accepted or rejected) invitations for a Synapse "
        "team. Pages through the open-invitation API; pass "
        "an increased ``offset`` to fetch the next batch. "
        "Team ID example: '3379097'."
    ),
    synonyms=_TEAM_SYNONYMS + ("pending", "invited", "invite"),
    siblings=(
        "get_team",
        "get_team_members",
        "get_team_membership_status",
    ),
)
async def get_team_open_invitations(
    team_id: int,
    ctx: Context,
    offset: int = 0,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """List pending Team invitations."""
    return await TeamService.get_team_open_invitations(
        ctx, team_id, offset=offset, limit=limit
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
    team_id: int, user_id: int, ctx: Context
) -> Dict[str, Any]:
    """Check a user's Team membership status."""
    return await TeamService.get_team_membership_status(
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
    return await UserService.get_user_profile(
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
    return await UserService.is_user_certified(ctx, user_id)


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
    return await EvaluationService.get_evaluation(
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
    return await EvaluationService.list_evaluations(
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
        "Use this when the user wants the resource-level "
        "access control list of a Synapse Evaluation queue "
        "(challenge queue) — which principals (users and "
        "teams) hold which access types on the queue. Use "
        "for queue-administration questions like \"who can "
        "score submissions\". Distinct from "
        "get_evaluation_permissions, which reports the "
        "caller's own effective permissions. Evaluation ID "
        "example: '9600001'."
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
    return await EvaluationService.get_evaluation_acl(
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
        "administer, etc. Returns the caller's own effective "
        "permission flags. Distinct from get_evaluation_acl, "
        "which lists the queue's full ACL across every "
        "principal. Evaluation ID example: '9600001'."
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
    return await EvaluationService.get_evaluation_permissions(
        ctx, evaluation_id
    )


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
    return await SubmissionService.get_submission(
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
        "for that. Pages through the queue's submission "
        "list; pass an increased ``offset`` to fetch the "
        "next batch. Evaluation ID example: '9600001'. "
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
    offset: int = 0,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """List submissions to an Evaluation."""
    return await SubmissionService.list_evaluation_submissions(
        ctx, evaluation_id, status, offset, limit
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
        "Pass an increased ``offset`` to page beyond the "
        "first batch. Evaluation ID example: '9600001'."
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
    offset: int = 0,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """List current user's submissions."""
    return await SubmissionService.list_my_submissions(
        ctx, evaluation_id, offset, limit
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
    return await SubmissionService.get_submission_count(
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
    return await SubmissionService.get_submission_status(
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
    return await SubmissionService.list_submission_statuses(
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
        "Pass an increased ``offset`` to fetch the next "
        "batch. Evaluation ID example: '9600001'."
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
    offset: int = 0,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """List submission bundles for an Evaluation."""
    return await SubmissionService.list_evaluation_submission_bundles(
        ctx, evaluation_id, status, offset, limit
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
        "status for every entry they made. Pass an "
        "increased ``offset`` to fetch the next batch. "
        "Evaluation ID example: '9600001'."
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
    offset: int = 0,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """List current user's submission bundles."""
    return await SubmissionService.list_my_submission_bundles(
        ctx, evaluation_id, offset, limit
    )


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
    return await CurationTaskService.list_tasks(ctx, project_id)


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
    return await CurationTaskService.get_task(ctx, task_id)


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
    return await CurationTaskService.get_task_resources(
        ctx, task_id
    )


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
    organization_name: str, ctx: Context
) -> Dict[str, Any]:
    """Get a Schema Organization by name."""
    return await SchemaOrganizationService.get_schema_organization(
        ctx, organization_name
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
    return await SchemaOrganizationService.get_schema_organization_acl(
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
        "an organization. Token-paginated (no limit/offset): "
        "the response includes ``next_page_token``; pass it "
        "back as the next call's ``next_page_token`` argument "
        "to fetch the following page. ``next_page_token`` is "
        "null on the final page. Organization name example: "
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
    organization_name: str,
    ctx: Context,
    next_page_token: Optional[str] = None,
) -> Dict[str, Any]:
    """List schemas in an organization (token-paginated)."""
    return await SchemaOrganizationService.list_json_schemas(
        ctx, organization_name, next_page_token
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
    return await SchemaOrganizationService.get_json_schema(
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
    return await SchemaOrganizationService.get_json_schema_body(
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
        "published for a Synapse JSON Schema. Token-paginated "
        "like list_json_schemas: pass the returned "
        "``next_page_token`` back to fetch the next page. "
        "Organization name example: 'org.sagebionetworks'. "
        "Schema name example: 'myDataset-1.0.0'."
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
    next_page_token: Optional[str] = None,
) -> Dict[str, Any]:
    """List versions of a JSON Schema (token-paginated)."""
    return await SchemaOrganizationService.list_json_schema_versions(
        ctx, organization_name, schema_name, next_page_token
    )


@service_tool(
    mcp,
    service="form",
    operation="read",
    synapse_object="Synapse FormGroup",
    title="List Form Data",
    description=(
        "Use this when the user wants the form submissions "
        "for a Synapse FormGroup — a collection of "
        "structured-data forms submitted by users. Optionally "
        "filter by state (valid filter_by_state values: "
        "'waiting_for_submission', "
        "'submitted_waiting_for_review', 'accepted', "
        "'rejected'). When as_reviewer=True the caller lists "
        "submissions they can review "
        "('waiting_for_submission' is not allowed in this "
        "mode); when False (default) lists submissions the "
        "caller owns. Token-paginated: response includes "
        "``next_page_token``; pass it back to fetch the next "
        "page (null on final page). Form group ID example: "
        "'42'."
    ),
    synonyms=("form", "survey", "intake", "questionnaire"),
    siblings=(),
)
async def list_form_data(
    group_id: str,
    ctx: Context,
    filter_by_state: Optional[List[str]] = None,
    as_reviewer: bool = False,
    next_page_token: Optional[str] = None,
) -> Dict[str, Any]:
    """List form submissions for a FormGroup (token-paginated)."""
    return await FormService.list_form_data(
        ctx, group_id, filter_by_state, as_reviewer, next_page_token
    )


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
        "resolves an exact name to its Synapse ID. The name "
        "match is case-sensitive (e.g. 'Patient Record Set' "
        "will not match 'Patient record set'); use "
        "search_synapse for fuzzy or case-insensitive lookup. "
        "Parent entity ID example: syn123456. Name example: "
        "'sample.csv'."
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
    """Find an entity's Synapse ID by exact name and parent."""
    return await UtilityService.find_entity_id(
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
        "check whether it exists in Synapse — verifies "
        "validity by querying the Synapse backend."
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
    return await UtilityService.is_synapse_id(ctx, syn_id)


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
    return await UtilityService.md5_query(ctx, md5)


@service_tool(
    mcp,
    service="entity",
    operation="write",
    synapse_object="Synapse entity",
    title="Create Entity",
    description=(
        "Use this when the user wants to create a new Synapse entity — a "
        "project, folder, table, view, dataset, dataset collection, link, "
        "materialized view, virtual table, submission view, docker "
        "repository, file, or record set. Set entity_type accordingly. "
        "Every type except project requires parent_id (example: "
        "syn123456). IMPORTANT: a file can only be created here from an "
        "external_url (external link) or an existing data_file_handle_id, "
        "and a record set only from an existing data_file_handle_id — this "
        "server never uploads local file content."
    ),
    synonyms=_CREATE_SYNONYMS + _ENTITY_TYPES + ("record set",),
    siblings=("update_entity", "delete_entity", "get_entity"),
)
async def create_entity(
    entity_type: Annotated[
        EntityType,
        Field(description="The type of entity to create (e.g. project, folder, file)."),
    ],
    name: Annotated[str, Field(description="Name for the new entity.")],
    ctx: Context,
    parent_id: Annotated[
        Optional[str],
        Field(
            description=(
                "Parent container Synapse ID, e.g. syn123456. Required for "
                "every type except project."
            )
        ),
    ] = None,
    description: Annotated[
        Optional[str], Field(description="Optional entity description.")
    ] = None,
    annotations: Annotated[
        Optional[Dict[str, List[Any]]],
        Field(description="Optional annotations; each key maps to a list of values."),
    ] = None,
    columns: Annotated[
        Optional[List[ColumnSpec]],
        Field(description="Column definitions for table-like entities."),
    ] = None,
    defining_sql: Annotated[
        Optional[str],
        Field(description="SQL for materializedview / virtualtable entities."),
    ] = None,
    view_type_mask: Annotated[
        Optional[List[ViewScopeType]],
        Field(description="Scope types for view/dataset entities, e.g. ['file']."),
    ] = None,
    scope_ids: Annotated[
        Optional[List[str]],
        Field(description="Container IDs an entityview scopes over."),
    ] = None,
    target_id: Annotated[
        Optional[str],
        Field(description="For link entities, the entity the link points at."),
    ] = None,
    target_version_number: Annotated[
        Optional[int],
        Field(description="Optional pinned version for a link entity."),
    ] = None,
    external_url: Annotated[
        Optional[str],
        Field(description="For file entities, the external URL to link to."),
    ] = None,
    data_file_handle_id: Annotated[
        Optional[str],
        Field(description="For file/recordset entities, an existing file handle ID."),
    ] = None,
) -> Dict[str, Any]:
    """Create a new Synapse entity from metadata."""
    if parent_id is not None and not validate_synapse_id(parent_id):
        return {
            "error": f"Invalid Synapse ID: {parent_id}",
            "error_type": "ValueError",
        }
    return await EntityService.create_entity(
        ctx,
        entity_type=entity_type,
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


@service_tool(
    mcp,
    service="entity",
    operation="write",
    synapse_object="Synapse entity",
    title="Update Entity",
    description=(
        "Use this to rename a Synapse entity, move it to a new parent, "
        "change its description, replace its annotations, or set its "
        "provenance. Type-specific fields are set via the individual "
        "arguments. Pass an explicit null to clear description or "
        "annotations. To change table columns, use update_columns. "
        "Entity ID example: syn123456."
    ),
    synonyms=_UPDATE_SYNONYMS + _ANNOTATION_SYNONYMS + _PROVENANCE_SYNONYMS,
    siblings=("create_entity", "delete_entity", "get_entity", "update_columns"),
)
async def update_entity(
    entity_id: Annotated[
        str, Field(description="Synapse ID of the entity to update, e.g. syn123456.")
    ],
    ctx: Context,
    name: Annotated[
        Optional[str],
        Field(description="New name (rename). Omit to leave unchanged."),
    ] = UNSET,
    parent_id: Annotated[
        Optional[str],
        Field(description="New parent container ID (move), e.g. syn123456."),
    ] = UNSET,
    description: Annotated[
        Optional[str],
        Field(description="New description; pass null to clear it."),
    ] = UNSET,
    annotations: Annotated[
        Optional[Dict[str, List[Any]]],
        Field(
            description=(
                "Full replacement annotations (each key maps to a list of "
                "values); null or {} clears all annotations."
            )
        ),
    ] = UNSET,
    provenance: Annotated[
        Optional[ProvenanceSpec],
        Field(
            description=(
                "Provenance/activity that produced this entity. Cannot be "
                "cleared here."
            )
        ),
    ] = UNSET,
    external_url: Annotated[
        Optional[str],
        Field(description="New external URL (file entities only)."),
    ] = UNSET,
    data_file_handle_id: Annotated[
        Optional[str],
        Field(description="New file handle to attach (file entities only)."),
    ] = UNSET,
    target_id: Annotated[
        Optional[str],
        Field(description="New link target entity ID (link entities only)."),
    ] = UNSET,
    target_version_number: Annotated[
        Optional[int],
        Field(description="Pinned target version (link entities only)."),
    ] = UNSET,
    scope_ids: Annotated[
        Optional[List[str]],
        Field(description="Container IDs an entityview scopes over."),
    ] = UNSET,
    view_type_mask: Annotated[
        Optional[List[ViewScopeType]],
        Field(description="Scope types for view/dataset entities."),
    ] = UNSET,
    defining_sql: Annotated[
        Optional[str],
        Field(description="SQL for materializedview / virtualtable."),
    ] = UNSET,
) -> Dict[str, Any]:
    """Update a Synapse entity's metadata, annotations, or provenance."""
    if not validate_synapse_id(entity_id):
        return {
            "error": f"Invalid Synapse ID: {entity_id}",
            "error_type": "ValueError",
        }
    if (
        parent_id is not UNSET
        and parent_id is not None
        and not validate_synapse_id(parent_id)
    ):
        return {
            "error": f"Invalid Synapse ID: {parent_id}",
            "error_type": "ValueError",
        }
    return await EntityService.update_entity(
        ctx,
        entity_id=entity_id,
        name=name,
        parent_id=parent_id,
        description=description,
        annotations=annotations,
        provenance=provenance,
        external_url=external_url,
        data_file_handle_id=data_file_handle_id,
        target_id=target_id,
        target_version_number=target_version_number,
        scope_ids=scope_ids,
        view_type_mask=view_type_mask,
        defining_sql=defining_sql,
    )


@service_tool(
    mcp,
    service="entity",
    operation="destructive",
    synapse_object="Synapse entity",
    title="Delete Entity",
    description=(
        "Use this when the user wants to delete a Synapse entity — a "
        "project, folder, file, table, view, or dataset — by its ID. For "
        "a file this removes the File entity (metadata). Entity ID "
        "example: syn123456. This is irreversible."
    ),
    synonyms=_DELETE_SYNONYMS + _ENTITY_TYPES,
    siblings=("create_entity", "update_entity", "get_entity"),
)
async def delete_entity(
    entity_id: Annotated[
        str, Field(description="Synapse ID of the entity to delete, e.g. syn123456.")
    ],
    ctx: Context,
) -> Dict[str, Any]:
    """Delete a Synapse entity by ID."""
    if not validate_synapse_id(entity_id):
        return {
            "error": f"Invalid Synapse ID: {entity_id}",
            "error_type": "ValueError",
        }
    return await EntityService.delete_entity(ctx, entity_id)


@service_tool(
    mcp,
    service="entity",
    operation="write",
    synapse_object="Synapse entity",
    title="Set Entity ACL",
    description=(
        "Use this when the user wants to share a Synapse entity — grant "
        "or change what a specific user or team can do with it. Valid "
        "access_type values are READ, DOWNLOAD, UPDATE, CREATE, DELETE, "
        "MODERATE, CHANGE_PERMISSIONS, and CHANGE_SETTINGS. Entity ID "
        "example: syn123456. Principal ID example: 3379097 (user or team). "
        "Pass an empty access_type list to remove that principal's access."
    ),
    synonyms=_ACL_SYNONYMS + _UPDATE_SYNONYMS,
    siblings=("delete_entity_acl", "get_entity_acl", "get_entity_permissions"),
)
async def update_entity_acl(
    entity_id: Annotated[
        str, Field(description="Synapse ID of the entity, e.g. syn123456.")
    ],
    principal_id: Annotated[
        int, Field(description="User or team ID to grant access to, e.g. 3379097.")
    ],
    access_type: Annotated[
        List[EntityAccessType],
        Field(
            description=(
                "Permission strings, e.g. ['READ', 'DOWNLOAD']. Pass an "
                "empty list to remove the principal's access."
            )
        ),
    ],
    ctx: Context,
) -> Dict[str, Any]:
    """Set an entity's ACL for one principal."""
    if not validate_synapse_id(entity_id):
        return {
            "error": f"Invalid Synapse ID: {entity_id}",
            "error_type": "ValueError",
        }
    return await EntityService.set_acl(
        ctx, entity_id, principal_id, access_type
    )


@service_tool(
    mcp,
    service="entity",
    operation="destructive",
    synapse_object="Synapse entity",
    title="Delete Entity ACL",
    description=(
        "Use this when the user wants a Synapse entity to stop having its "
        "own sharing settings and instead inherit permissions from its "
        "parent container (delete its local ACL). Entity ID example: "
        "syn123456."
    ),
    synonyms=_ACL_SYNONYMS + _DELETE_SYNONYMS + ("inherit", "revert sharing"),
    siblings=("update_entity_acl", "get_entity_acl"),
)
async def delete_entity_acl(
    entity_id: Annotated[
        str, Field(description="Synapse ID of the entity, e.g. syn123456.")
    ],
    ctx: Context,
) -> Dict[str, Any]:
    """Delete an entity's local ACL."""
    if not validate_synapse_id(entity_id):
        return {
            "error": f"Invalid Synapse ID: {entity_id}",
            "error_type": "ValueError",
        }
    return await EntityService.delete_acl(ctx, entity_id)


@service_tool(
    mcp,
    service="schema",
    operation="write",
    synapse_object="Synapse entity",
    title="Bind Entity Schema",
    description=(
        "Use this when the user wants to bind (attach) a JSON schema "
        "(data model / validation contract) to a Synapse entity so its "
        "annotations are validated against that schema. Entity ID "
        "example: syn123456. Schema $id example: 'my.org-MySchema-1.0.0'."
    ),
    synonyms=_SCHEMA_SYNONYMS + ("bind", "attach schema", "validate"),
    siblings=("delete_entity_schema", "get_entity_schema"),
)
async def update_entity_schema(
    entity_id: Annotated[
        str, Field(description="Synapse ID of the entity, e.g. syn123456.")
    ],
    json_schema_uri: Annotated[
        str,
        Field(description="JSON Schema $id to bind, e.g. 'my.org-MySchema-1.0.0'."),
    ],
    ctx: Context,
    enable_derived_annotations: Annotated[
        bool,
        Field(
            description=(
                "Whether Synapse should derive annotations from the schema "
                "on this entity."
            )
        ),
    ] = False,
) -> Dict[str, Any]:
    """Bind a JSON schema to a Synapse entity."""
    if not validate_synapse_id(entity_id):
        return {
            "error": f"Invalid Synapse ID: {entity_id}",
            "error_type": "ValueError",
        }
    return await EntityService.bind_schema(
        ctx, entity_id, json_schema_uri, enable_derived_annotations
    )


@service_tool(
    mcp,
    service="schema",
    operation="destructive",
    synapse_object="Synapse entity",
    title="Unbind Entity Schema",
    description=(
        "Use this when the user wants to unbind (remove) the JSON schema "
        "from a Synapse entity so it is no longer validated. Entity ID "
        "example: syn123456."
    ),
    synonyms=_SCHEMA_SYNONYMS + _DELETE_SYNONYMS + ("unbind", "detach"),
    siblings=("update_entity_schema", "get_entity_schema"),
)
async def delete_entity_schema(
    entity_id: Annotated[
        str, Field(description="Synapse ID of the entity, e.g. syn123456.")
    ],
    ctx: Context,
) -> Dict[str, Any]:
    """Unbind the JSON schema from a Synapse entity."""
    if not validate_synapse_id(entity_id):
        return {
            "error": f"Invalid Synapse ID: {entity_id}",
            "error_type": "ValueError",
        }
    return await EntityService.unbind_schema(ctx, entity_id)


@service_tool(
    mcp,
    service="entity",
    operation="write",
    synapse_object="Synapse table",
    title="Update Columns",
    description=(
        "Use this when the user wants to change a Synapse table, view, or "
        "dataset column layout — add, delete, rename, or reorder columns. "
        "This only changes the schema; it never loads row data. Operations "
        "apply in order: delete, add, rename, reorder. Entity ID example: "
        "syn123456."
    ),
    synonyms=(
        "column",
        "schema",
        "add column",
        "delete column",
    ),
    siblings=("create_entity", "update_entity"),
)
async def update_columns(
    entity_id: Annotated[
        str,
        Field(description="Synapse ID of the table, view, or dataset, e.g. syn123456."),
    ],
    ctx: Context,
    add_columns: Annotated[
        Optional[List[ColumnSpec]],
        Field(description="Column specs to add (name + column_type at minimum)."),
    ] = None,
    delete_columns: Annotated[
        Optional[List[str]],
        Field(description="Names of existing columns to delete."),
    ] = None,
    rename_columns: Annotated[
        Optional[Dict[str, str]],
        Field(description="Map of {old_name: new_name} for existing columns."),
    ] = None,
    reorder_columns: Annotated[
        Optional[List[str]],
        Field(
            description=(
                "Complete desired column order as a list of the final column "
                "names (all of them, no duplicates)."
            )
        ),
    ] = None,
) -> Dict[str, Any]:
    """Add, remove, rename, or reorder columns on a Synapse table/view/dataset."""
    if not validate_synapse_id(entity_id):
        return {
            "error": f"Invalid Synapse ID: {entity_id}",
            "error_type": "ValueError",
        }
    return await EntityService.update_columns(
        ctx,
        entity_id,
        add_columns,
        delete_columns,
        rename_columns,
        reorder_columns,
    )


@service_tool(
    mcp,
    service="team",
    operation="write",
    synapse_object="Synapse team",
    title="Create Team",
    description=(
        "Use this when the user wants to create a new Synapse team — a "
        "named group of users that can be granted access to entities "
        "collectively. Team name example: 'NF-OSI Curators'."
    ),
    synonyms=_CREATE_SYNONYMS + _TEAM_SYNONYMS,
    siblings=("delete_team", "create_team_invitation", "get_team"),
)
async def create_team(
    name: Annotated[
        str, Field(description="Team name, e.g. 'NF-OSI Curators'.")
    ],
    ctx: Context,
    description: Annotated[
        Optional[str], Field(description="Description of the team.")
    ] = None,
    can_public_join: Annotated[
        bool, Field(description="Whether anyone can join without an invitation.")
    ] = False,
    can_request_membership: Annotated[
        bool, Field(description="Whether users can request to join.")
    ] = True,
) -> Dict[str, Any]:
    """Create a new Synapse Team."""
    return await TeamService.create_team(
        ctx,
        name=name,
        description=description,
        can_public_join=can_public_join,
        can_request_membership=can_request_membership,
    )


@service_tool(
    mcp,
    service="team",
    operation="destructive",
    synapse_object="Synapse team",
    title="Delete Team",
    description=(
        "Use this when the user wants to delete a Synapse team by its "
        "numeric ID. Team ID example: '3379097'. This is irreversible."
    ),
    synonyms=_DELETE_SYNONYMS + _TEAM_SYNONYMS,
    siblings=("create_team", "get_team"),
)
async def delete_team(
    team_id: Annotated[
        int, Field(description="Numeric ID of the team to delete, e.g. 3379097.")
    ],
    ctx: Context,
) -> Dict[str, Any]:
    """Delete a Synapse Team by ID."""
    return await TeamService.delete_team(ctx, team_id)


@service_tool(
    mcp,
    service="team",
    operation="write",
    synapse_object="Synapse team",
    title="Invite To Team",
    description=(
        "Use this when the user wants to create an invitation for a user "
        "to join a Synapse team. Team ID example: '3379097'. User can be "
        "a username or numeric user ID (example: '1234567')."
    ),
    synonyms=_TEAM_SYNONYMS + ("invite", "add member", "membership"),
    siblings=("create_team", "get_team_open_invitations"),
)
async def create_team_invitation(
    team_id: Annotated[
        int, Field(description="Numeric ID of the team, e.g. 3379097.")
    ],
    user: Annotated[
        str,
        Field(
            description=(
                "Username or numeric user ID to invite, e.g. '1234567'."
            )
        ),
    ],
    ctx: Context,
    message: Annotated[
        Optional[str], Field(description="Optional message shown with the invitation.")
    ] = None,
    force: Annotated[
        bool,
        Field(
            description=(
                "Whether to send the invitation even if the user is "
                "already a member or has a pending invitation."
            )
        ),
    ] = True,
) -> Dict[str, Any]:
    """Invite a user to a Synapse Team."""
    return await TeamService.invite_to_team(
        ctx, team_id, user, message=message, force=force
    )


@service_tool(
    mcp,
    service="evaluation",
    operation="write",
    synapse_object="Synapse evaluation",
    title="Create Evaluation",
    description=(
        "Use this when the user wants to create a new Synapse Evaluation "
        "queue (challenge/competition queue) on a project. content_source "
        "is the owning project ID (example: syn123456). Synapse requires "
        "a description, submitter instructions, and a submission-receipt "
        "message — all are mandatory."
    ),
    synonyms=_CREATE_SYNONYMS + _EVALUATION_SYNONYMS,
    siblings=("update_evaluation", "delete_evaluation", "get_evaluation"),
)
async def create_evaluation(
    name: Annotated[str, Field(description="Name for the new evaluation queue.")],
    content_source: Annotated[
        str,
        Field(description="Owning project Synapse ID, e.g. syn123456."),
    ],
    description: Annotated[
        str, Field(description="Description of the queue (required by Synapse).")
    ],
    submission_instructions_message: Annotated[
        str,
        Field(description="Instructions shown to submitters (required by Synapse)."),
    ],
    submission_receipt_message: Annotated[
        str,
        Field(description="Message shown after a submission (required by Synapse)."),
    ],
    ctx: Context,
) -> Dict[str, Any]:
    """Create a new Evaluation queue."""
    if not validate_synapse_id(content_source):
        return {
            "error": f"Invalid Synapse ID: {content_source}",
            "error_type": "ValueError",
        }
    return await EvaluationService.create_evaluation(
        ctx,
        name=name,
        content_source=content_source,
        description=description,
        submission_instructions_message=submission_instructions_message,
        submission_receipt_message=submission_receipt_message,
    )


@service_tool(
    mcp,
    service="evaluation",
    operation="write",
    synapse_object="Synapse evaluation",
    title="Update Evaluation",
    description=(
        "Use this when the user wants to update a Synapse Evaluation "
        "queue's metadata — its name, description, or submitter "
        "instructions. Evaluation ID example: '9600001'."
    ),
    synonyms=_UPDATE_SYNONYMS + _EVALUATION_SYNONYMS,
    siblings=("create_evaluation", "delete_evaluation", "get_evaluation"),
)
async def update_evaluation(
    evaluation_id: Annotated[
        str, Field(description="Numeric ID of the evaluation queue, e.g. '9600001'.")
    ],
    ctx: Context,
    name: Annotated[
        Optional[str], Field(description="New name for the queue.")
    ] = UNSET,
    description: Annotated[
        Optional[str], Field(description="New description for the queue.")
    ] = UNSET,
    submission_instructions_message: Annotated[
        Optional[str],
        Field(description="New instructions shown to submitters."),
    ] = UNSET,
) -> Dict[str, Any]:
    """Update an Evaluation queue's metadata."""
    return await EvaluationService.update_evaluation(
        ctx,
        evaluation_id=evaluation_id,
        name=name,
        description=description,
        submission_instructions_message=submission_instructions_message,
    )


@service_tool(
    mcp,
    service="evaluation",
    operation="destructive",
    synapse_object="Synapse evaluation",
    title="Delete Evaluation",
    description=(
        "Use this when the user wants to delete a Synapse Evaluation "
        "queue by ID. Evaluation ID example: '9600001'. This is "
        "irreversible."
    ),
    synonyms=_DELETE_SYNONYMS + _EVALUATION_SYNONYMS,
    siblings=("create_evaluation", "get_evaluation"),
)
async def delete_evaluation(
    evaluation_id: Annotated[
        str, Field(description="Numeric ID of the evaluation queue, e.g. '9600001'.")
    ],
    ctx: Context,
) -> Dict[str, Any]:
    """Delete an Evaluation queue by ID."""
    return await EvaluationService.delete_evaluation(ctx, evaluation_id)


@service_tool(
    mcp,
    service="evaluation",
    operation="write",
    synapse_object="Synapse evaluation",
    title="Update Evaluation ACL",
    description=(
        "Use this when the user wants to grant or change a user's or "
        "team's access on a Synapse Evaluation queue (challenge queue) — "
        "e.g. who can submit or score. Valid access_type values are READ, "
        "UPDATE, DELETE, CREATE, SUBMIT, READ_PRIVATE_SUBMISSION, "
        "DELETE_SUBMISSION, UPDATE_SUBMISSION, and CHANGE_PERMISSIONS. "
        "Evaluation ID example: '9600001'. Principal ID example: 3379097."
    ),
    synonyms=_EVALUATION_SYNONYMS + _ACL_SYNONYMS + _UPDATE_SYNONYMS,
    siblings=("get_evaluation_acl", "get_evaluation_permissions"),
)
async def update_evaluation_acl(
    evaluation_id: Annotated[
        str, Field(description="Numeric ID of the evaluation queue, e.g. '9600001'.")
    ],
    principal_id: Annotated[
        int, Field(description="User or team ID to grant access to, e.g. 3379097.")
    ],
    access_type: Annotated[
        List[EvaluationAccessType],
        Field(description="Permission strings, e.g. ['READ', 'SUBMIT']."),
    ],
    ctx: Context,
) -> Dict[str, Any]:
    """Update an Evaluation queue's ACL for one principal."""
    return await EvaluationService.update_evaluation_acl(
        ctx, evaluation_id, principal_id, access_type
    )


@service_tool(
    mcp,
    service="submission",
    operation="write",
    synapse_object="Synapse submission",
    title="Submit To Evaluation",
    description=(
        "Use this when the user wants to submit an existing Synapse entity "
        "to an Evaluation queue as a challenge submission. The entity must "
        "already exist in Synapse (no file is uploaded here). Evaluation "
        "ID example: '9600001'. Entity ID example: syn123456."
    ),
    synonyms=_SUBMISSION_SYNONYMS + _EVALUATION_SYNONYMS + ("submit",),
    siblings=("get_submission", "update_submission_status"),
)
async def submit_to_evaluation(
    evaluation_id: Annotated[
        str, Field(description="Numeric ID of the evaluation queue, e.g. '9600001'.")
    ],
    entity_id: Annotated[
        str, Field(description="Synapse ID of the entity to submit, e.g. syn123456.")
    ],
    ctx: Context,
    name: Annotated[
        Optional[str], Field(description="Optional name for the submission.")
    ] = None,
    submitter_alias: Annotated[
        Optional[str],
        Field(description="Optional display name shown for the submitter."),
    ] = None,
) -> Dict[str, Any]:
    """Submit an existing entity to an Evaluation queue."""
    if not validate_synapse_id(entity_id):
        return {
            "error": f"Invalid Synapse ID: {entity_id}",
            "error_type": "ValueError",
        }
    return await SubmissionService.submit_to_evaluation(
        ctx,
        evaluation_id,
        entity_id,
        name=name,
        submitter_alias=submitter_alias,
    )


@service_tool(
    mcp,
    service="submission",
    operation="write",
    synapse_object="Synapse submission",
    title="Update Submission Status",
    description=(
        "Use this when the user wants to update the scoring status of a "
        "Synapse submission (challenge entry). Valid status values are "
        "OPEN, CLOSED, RECEIVED, VALIDATED, EVALUATION_IN_PROGRESS, "
        "SCORED, INVALID, ACCEPTED, and REJECTED. You can also set status "
        "annotations. Submission ID example: '9722233'. Pass null "
        "annotations to clear them."
    ),
    synonyms=_SUBMISSION_SYNONYMS + _UPDATE_SYNONYMS + ("score", "status"),
    siblings=("get_submission_status", "submit_to_evaluation"),
)
async def update_submission_status(
    submission_id: Annotated[
        str, Field(description="Numeric ID of the submission, e.g. '9722112'.")
    ],
    ctx: Context,
    status: Annotated[
        Optional[SubmissionStatusValue],
        Field(description="New scoring status, e.g. 'SCORED'."),
    ] = UNSET,
    annotations: Annotated[
        Optional[Dict[str, List[Any]]],
        Field(
            description=(
                "Full replacement status annotations; null clears them."
            )
        ),
    ] = UNSET,
) -> Dict[str, Any]:
    """Update a submission's scoring status."""
    return await SubmissionService.update_submission_status(
        ctx, submission_id, status=status, annotations=annotations
    )


@service_tool(
    mcp,
    service="organization",
    operation="write",
    synapse_object="Synapse Organization",
    title="Create Organization",
    description=(
        "Use this when the user wants to create a new Synapse Organization "
        "— a named namespace under which resources such as JSON schemas "
        "are published. Organization name example: 'my.org'."
    ),
    synonyms=_CREATE_SYNONYMS + _SCHEMA_SYNONYMS + ("namespace",),
    siblings=("delete_organization", "get_schema_organization"),
)
async def create_organization(
    organization_name: Annotated[
        str, Field(description="Namespace to register, e.g. 'my.org'.")
    ],
    ctx: Context,
) -> Dict[str, Any]:
    """Create a new Synapse Organization."""
    return await SchemaOrganizationService.create_organization(
        ctx, organization_name
    )


@service_tool(
    mcp,
    service="organization",
    operation="destructive",
    synapse_object="Synapse Organization",
    title="Delete Organization",
    description=(
        "Use this when the user wants to delete a Synapse Organization "
        "(a namespace) by id or by name. This is irreversible."
    ),
    synonyms=_DELETE_SYNONYMS + _SCHEMA_SYNONYMS + ("namespace",),
    siblings=("create_organization", "get_schema_organization"),
)
async def delete_organization(
    organization: Annotated[
        str,
        Field(
            description=(
                "Organization id or name, e.g. '1075' or 'my.org'."
            )
        ),
    ],
    ctx: Context,
) -> Dict[str, Any]:
    """Delete a Synapse Organization by id or by name."""
    return await SchemaOrganizationService.delete_organization(
        ctx, organization
    )


@service_tool(
    mcp,
    service="organization",
    operation="write",
    synapse_object="Synapse Organization",
    title="Update Organization ACL",
    description=(
        "Use this when the user wants to grant or change who can publish "
        "resources (such as JSON schemas) under a Synapse Organization "
        "namespace, addressed by id or by name. Valid access_type values "
        "are READ, CREATE, UPDATE, DELETE, and CHANGE_PERMISSIONS. "
        "Principal ID example: 3379097."
    ),
    synonyms=_SCHEMA_SYNONYMS + _ACL_SYNONYMS + _UPDATE_SYNONYMS,
    siblings=("get_schema_organization_acl", "get_schema_organization"),
)
async def update_organization_acl(
    organization: Annotated[
        str,
        Field(
            description=(
                "Organization id or name, e.g. '1075' or 'my.org'."
            )
        ),
    ],
    principal_id: Annotated[
        int,
        Field(description="User or team ID to grant access to, e.g. 3379097."),
    ],
    access_type: Annotated[
        List[OrganizationAccessType],
        Field(description="Permission strings, e.g. ['READ', 'CREATE']."),
    ],
    ctx: Context,
) -> Dict[str, Any]:
    """Set a principal's access on a Synapse Organization."""
    return await SchemaOrganizationService.update_organization_acl(
        ctx, organization, principal_id, access_type
    )


@service_tool(
    mcp,
    service="schema",
    operation="write",
    synapse_object="Synapse JSON Schema",
    title="Register JSON Schema",
    description=(
        "Use this when the user wants to register (publish a version of) a "
        "Synapse JSON Schema from an inline JSON document. The owning "
        "organization is addressed by its name (e.g. 'my.org'), not a "
        "numeric or syn id. Schema name example: 'MySchema'. Optional "
        "version example: '1.0.0'."
    ),
    synonyms=_SCHEMA_SYNONYMS + _CREATE_SYNONYMS + ("register", "publish"),
    siblings=("delete_json_schema", "get_json_schema"),
)
async def register_json_schema(
    organization_name: Annotated[
        str, Field(description="Owning organization name, e.g. 'my.org'.")
    ],
    schema_name: Annotated[
        str, Field(description="Schema name, e.g. 'MySchema'.")
    ],
    schema_body: Annotated[
        Dict[str, Any], Field(description="The JSON Schema document as an inline dict.")
    ],
    ctx: Context,
    version: Annotated[
        Optional[str], Field(description="Optional semantic version, e.g. '1.0.0'.")
    ] = None,
) -> Dict[str, Any]:
    """Register a JSON Schema from an inline body."""
    return await SchemaOrganizationService.register_json_schema(
        ctx,
        organization_name,
        schema_name,
        schema_body,
        version=version,
    )


@service_tool(
    mcp,
    service="schema",
    operation="destructive",
    synapse_object="Synapse JSON Schema",
    title="Delete JSON Schema",
    description=(
        "Use this when the user wants to delete a Synapse JSON Schema by "
        "organization and name. Organization name example: 'my.org'. "
        "Schema name example: 'MySchema'. This is irreversible."
    ),
    synonyms=_DELETE_SYNONYMS + _SCHEMA_SYNONYMS,
    siblings=("register_json_schema", "get_json_schema"),
)
async def delete_json_schema(
    organization_name: Annotated[
        str, Field(description="Owning organization name, e.g. 'my.org'.")
    ],
    schema_name: Annotated[
        str, Field(description="Schema name to delete, e.g. 'MySchema'.")
    ],
    ctx: Context,
) -> Dict[str, Any]:
    """Delete a JSON Schema by organization and name."""
    return await SchemaOrganizationService.delete_json_schema(
        ctx, organization_name, schema_name
    )


@service_tool(
    mcp,
    service="curation",
    operation="write",
    synapse_object="Synapse curation task",
    title="Create Curation Task",
    description=(
        "Use this when the user wants to create a Synapse curation task on "
        "a project — a data-curation work item. Project ID example: "
        "syn123456. task_properties selects the shape: a record_set_id "
        "for record-based, or an upload_folder_id (and optional "
        "file_view_id) for file-based."
    ),
    synonyms=_CREATE_SYNONYMS + ("curator", "work item", "task"),
    siblings=("delete_curation_task", "get_curation_task"),
)
async def create_curation_task(
    project_id: Annotated[
        str, Field(description="Project Synapse ID the task belongs to, e.g. syn123456.")
    ],
    data_type: Annotated[
        str, Field(description="The kind of data being curated.")
    ],
    task_properties: Annotated[
        TaskProperties,
        Field(
            description=(
                "Selects the task shape: record_set_id for record-based, or "
                "upload_folder_id (+ optional file_view_id) for file-based."
            )
        ),
    ],
    ctx: Context,
    instructions: Annotated[
        Optional[str], Field(description="Optional free-text instructions.")
    ] = None,
) -> Dict[str, Any]:
    """Create a curation task on a project."""
    if not validate_synapse_id(project_id):
        return {
            "error": f"Invalid Synapse ID: {project_id}",
            "error_type": "ValueError",
        }
    return await CurationTaskService.create_task(
        ctx,
        project_id=project_id,
        data_type=data_type,
        task_properties=task_properties,
        instructions=instructions,
    )


@service_tool(
    mcp,
    service="curation",
    operation="destructive",
    synapse_object="Synapse curation task",
    title="Delete Curation Task",
    description=(
        "Use this when the user wants to delete a Synapse curation task by "
        "its numeric task ID. Task ID example: 42. This is irreversible."
    ),
    synonyms=_DELETE_SYNONYMS + ("curator", "work item", "task"),
    siblings=("create_curation_task", "get_curation_task"),
)
async def delete_curation_task(
    task_id: Annotated[
        int, Field(description="Numeric ID of the curation task, e.g. 42.")
    ],
    ctx: Context,
) -> Dict[str, Any]:
    """Delete a curation task by ID."""
    return await CurationTaskService.delete_task(ctx, task_id)


# Applied after all tools are registered so the transform has the full
# catalog to index. The LLM's default view becomes the two pinned tools
# plus the synthetic ``search_tools`` / ``call_read_tool`` / ``call_write_tool``
# trio; every other tool is reached by calling ``search_tools`` with a
# natural-language query and then invoking ``call_read_tool`` (reads) or
# ``call_write_tool`` (writes/deletes). The split lets clients that gate by
# tool name allow reads while withholding writes.


def _configure_discovery_transforms() -> None:
    """Register the split-proxy BM25 search transform on the live server."""
    mcp.add_transform(
        SplitCallTransform(
            max_results=7,
            always_visible=["search_synapse", "get_entity"],
            call_tool_name="call_read_tool",
        )
    )


_configure_discovery_transforms()
