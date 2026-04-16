"""Tool registrations for Synapse MCP."""

from typing import Any, Dict, List, Optional

from fastmcp import Context

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


@mcp.tool(
    title="Get Wiki Order Hint",
    description=(
        "Get the display ordering of wiki sub-pages "
        "for a Synapse entity."
    ),
    annotations=_RO,
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


@mcp.tool(
    title="Get Team",
    description=(
        "Get a Synapse Team by its numeric ID or "
        "by name."
    ),
    annotations=_RO,
)
async def get_team(
    ctx: Context,
    team_id: Optional[int] = None,
    team_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Get a Synapse Team by ID or name."""
    return await TeamService().get_team(ctx, team_id, team_name)


@mcp.tool(
    title="Get Team Members",
    description="List all members of a Synapse Team.",
    annotations=_RO,
)
async def get_team_members(
    team_id: int, ctx: Context
) -> List[Dict[str, Any]]:
    """List all members of a Team."""
    return await TeamService().get_team_members(ctx, team_id)


@mcp.tool(
    title="Get Team Open Invitations",
    description=(
        "List pending invitations for a Synapse Team."
    ),
    annotations=_RO,
)
async def get_team_open_invitations(
    team_id: int, ctx: Context
) -> List[Dict[str, Any]]:
    """List pending Team invitations."""
    return await TeamService().get_team_open_invitations(
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
async def get_team_membership_status(
    team_id: int, user_id: str, ctx: Context
) -> Dict[str, Any]:
    """Check a user's Team membership status."""
    return await TeamService().get_team_membership_status(
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
async def get_user_profile(
    ctx: Context,
    user_id: Optional[int] = None,
    username: Optional[str] = None,
) -> Dict[str, Any]:
    """Get a Synapse user profile."""
    return await UserService().get_user_profile(
        ctx, user_id, username
    )


@mcp.tool(
    title="Is User Certified",
    description=(
        "Check if a Synapse user is certified."
    ),
    annotations=_RO,
)
async def is_user_certified(
    user_id: int, ctx: Context
) -> Dict[str, Any]:
    """Check if a user is certified."""
    return await UserService().is_user_certified(ctx, user_id)


# ---------------------------------------------------------------------------
# Domain 10: Evaluation (Challenge Queue)
# ---------------------------------------------------------------------------


@mcp.tool(
    title="Get Evaluation",
    description=(
        "Get a Synapse Evaluation (challenge queue) "
        "by ID or name."
    ),
    annotations=_RO,
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


@mcp.tool(
    title="List Evaluations",
    description=(
        "List Synapse Evaluations with optional "
        "filters (project, access type, active only). "
        "If the result set hits the limit, call again "
        "with a higher offset to retrieve the next page."
    ),
    annotations=_RO,
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


@mcp.tool(
    title="Get Evaluation ACL",
    description=(
        "Get the access control list for a Synapse "
        "Evaluation queue."
    ),
    annotations=_RO,
)
async def get_evaluation_acl(
    evaluation_id: str, ctx: Context
) -> Dict[str, Any]:
    """Get ACL for an Evaluation queue."""
    return await EvaluationService().get_evaluation_acl(
        ctx, evaluation_id
    )


@mcp.tool(
    title="Get Evaluation Permissions",
    description=(
        "Get the current user's permissions on a "
        "Synapse Evaluation queue."
    ),
    annotations=_RO,
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


@mcp.tool(
    title="Get Submission",
    description="Get a Synapse Submission by its ID.",
    annotations=_RO,
)
async def get_submission(
    submission_id: str, ctx: Context
) -> Dict[str, Any]:
    """Get a Submission by ID."""
    return await SubmissionService().get_submission(
        ctx, submission_id
    )


@mcp.tool(
    title="List Evaluation Submissions",
    description=(
        "List all submissions to a Synapse Evaluation "
        "queue, optionally filtered by status. "
        "If the result set hits the limit, call again "
        "with a higher offset to retrieve the next page."
    ),
    annotations=_RO,
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


@mcp.tool(
    title="List My Submissions",
    description=(
        "List the current user's submissions to a "
        "Synapse Evaluation queue."
    ),
    annotations=_RO,
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


@mcp.tool(
    title="Get Submission Count",
    description=(
        "Get the count of submissions to a Synapse "
        "Evaluation queue."
    ),
    annotations=_RO,
)
async def get_submission_count(
    evaluation_id: str, ctx: Context
) -> Dict[str, Any]:
    """Get submission count for an Evaluation."""
    return await SubmissionService().get_submission_count(
        ctx, evaluation_id
    )


@mcp.tool(
    title="Get Submission Status",
    description=(
        "Get the status of a specific Synapse Submission."
    ),
    annotations=_RO,
)
async def get_submission_status(
    submission_id: str, ctx: Context
) -> Dict[str, Any]:
    """Get status of a Submission."""
    return await SubmissionService().get_submission_status(
        ctx, submission_id
    )


@mcp.tool(
    title="List Submission Statuses",
    description=(
        "List statuses for all submissions in a "
        "Synapse Evaluation queue. "
        "If the result set hits the limit, call again "
        "with a higher offset to retrieve the next page."
    ),
    annotations=_RO,
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


@mcp.tool(
    title="List Evaluation Submission Bundles",
    description=(
        "List submission+status bundles for a Synapse "
        "Evaluation queue."
    ),
    annotations=_RO,
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


@mcp.tool(
    title="List My Submission Bundles",
    description=(
        "List the current user's submission bundles "
        "for a Synapse Evaluation queue."
    ),
    annotations=_RO,
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


# ---------------------------------------------------------------------------
# Domain 12: JSON Schema Organizations
# ---------------------------------------------------------------------------


@mcp.tool(
    title="Get Schema Organization",
    description=(
        "Get a Synapse JSON Schema Organization "
        "by name or ID."
    ),
    annotations=_RO,
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


@mcp.tool(
    title="Get Schema Organization ACL",
    description=(
        "Get the ACL for a Synapse JSON Schema "
        "Organization."
    ),
    annotations=_RO,
)
async def get_schema_organization_acl(
    organization_name: str, ctx: Context
) -> Dict[str, Any]:
    """Get ACL for a Schema Organization."""
    return await SchemaOrganizationService().get_schema_organization_acl(
        ctx, organization_name
    )


@mcp.tool(
    title="List JSON Schemas",
    description=(
        "List all JSON Schemas in a Synapse "
        "Schema Organization."
    ),
    annotations=_RO,
)
async def list_json_schemas(
    organization_name: str, ctx: Context
) -> List[Dict[str, Any]]:
    """List schemas in an organization."""
    return await SchemaOrganizationService().list_json_schemas(
        ctx, organization_name
    )


@mcp.tool(
    title="Get JSON Schema",
    description=(
        "Get metadata for a specific Synapse "
        "JSON Schema."
    ),
    annotations=_RO,
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


@mcp.tool(
    title="Get JSON Schema Body",
    description=(
        "Get the actual JSON document of a Synapse "
        "JSON Schema."
    ),
    annotations=_RO,
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


@mcp.tool(
    title="List JSON Schema Versions",
    description=(
        "List all versions of a Synapse JSON Schema."
    ),
    annotations=_RO,
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


@mcp.tool(
    title="List Form Data",
    description=(
        "List form submissions for a Synapse FormGroup, "
        "optionally filtered by state."
    ),
    annotations=_RO,
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


@mcp.tool(
    title="Find Entity ID",
    description=(
        "Find a Synapse entity's ID by its name and "
        "optional parent container. Useful when you know "
        "the name but not the synapse ID."
    ),
    annotations=_RO,
)
async def find_entity_id(
    name: str,
    ctx: Context,
    parent_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Find an entity's Synapse ID by name and parent."""
    return await UtilityService().find_entity_id(
        ctx, name, parent_id
    )


@mcp.tool(
    title="Validate Synapse ID",
    description=(
        "Check whether a Synapse ID exists and is valid "
        "by querying the Synapse backend."
    ),
    annotations=_RO,
)
async def check_synapse_id(
    syn_id: str, ctx: Context
) -> Dict[str, Any]:
    """Validate whether a Synapse ID exists."""
    return await UtilityService().is_synapse_id(ctx, syn_id)


@mcp.tool(
    title="MD5 Query",
    description=(
        "Find Synapse entities by the MD5 hash of "
        "their attached file."
    ),
    annotations=_RO,
)
async def md5_query(
    md5: str, ctx: Context
) -> Dict[str, Any]:
    """Find entities by MD5 hash."""
    return await UtilityService().md5_query(ctx, md5)


# ---------------------------------------------------------------------------
# Domain 15: DockerRepository
# ---------------------------------------------------------------------------


@mcp.tool(
    title="Get Docker Repository",
    description=(
        "Get a Synapse DockerRepository entity by ID. "
        "ACL and permissions use the generic entity "
        "ACL tools."
    ),
    annotations=_RO,
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
