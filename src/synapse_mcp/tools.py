"""Tool registrations for Synapse MCP."""

import json
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastmcp import Context
from synapseclient.core.exceptions import SynapseHTTPError
from synapseclient.extensions.curator import generate_jsonschema
from synapseclient.models import CurationTask, Folder, JSONSchema, SchemaOrganization, EntityView, RecordSet
from synapseclient.operations import get, FileOptions

from .app import mcp
from .connection_auth import get_synapse_client
from .context_helpers import ConnectionAuthError, get_entity_operations
from .utils import format_annotations, validate_synapse_id


DEFAULT_RETURN_FIELDS: List[str] = ["name", "description", "node_type"]


def _normalize_fields(fields: Optional[List[str]]) -> List[str]:
    """Deduplicate and strip return field entries while preserving order."""
    if not fields:
        return []

    seen: set[str] = set()
    normalized: List[str] = []
    for raw in fields:
        cleaned = str(raw).strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        normalized.append(cleaned)
    return normalized


@mcp.tool(
    title="Fetch Entity",
    description="Return Synapse entity metadata by ID (projects, folders, files, tables, etc.). Only retrieves metadata information - does not download file content.",
    annotations={
        "readOnlyHint": True,
        "idempotentHint": True,
        "destructiveHint": False,
        "openWorldHint": True,
    },
)
def get_entity(entity_id: str, ctx: Context) -> Dict[str, Any]:
    """Return Synapse entity metadata by ID (projects, folders, files, tables, etc.)."""
    if not validate_synapse_id(entity_id):
        return {"error": f"Invalid Synapse ID: {entity_id}"}

    try:
        entity_ops = get_entity_operations(ctx)
        return entity_ops["base"].get_entity_by_id(entity_id)
    except ConnectionAuthError as exc:
        return {"error": f"Authentication required: {exc}", "entity_id": entity_id}
    except Exception as exc:  # pragma: no cover - defensive path
        return {"error": str(exc), "error_type": type(exc).__name__, "entity_id": entity_id}


@mcp.tool(
    title="Fetch Entity Annotations",
    description="Return custom annotation key/value pairs for a Synapse entity.",
    annotations={
        "readOnlyHint": True,
        "idempotentHint": True,
        "destructiveHint": False,
        "openWorldHint": True,
    },
)
def get_entity_annotations(entity_id: str, ctx: Context) -> Dict[str, Any]:
    """Return custom annotation key/value pairs for a Synapse entity."""
    if not validate_synapse_id(entity_id):
        return {"error": f"Invalid Synapse ID: {entity_id}"}

    try:
        entity_ops = get_entity_operations(ctx)
        annotations = entity_ops["base"].get_entity_annotations(entity_id)
        return format_annotations(annotations)
    except ConnectionAuthError as exc:
        return {"error": f"Authentication required: {exc}", "entity_id": entity_id}
    except Exception as exc:  # pragma: no cover - defensive path
        return {"error": str(exc), "error_type": type(exc).__name__, "entity_id": entity_id}


@mcp.tool(
    title="Fetch Entity Provenance",
    description="Return provenance (activity) metadata for a Synapse entity, including inputs and code executed.",
    annotations={
        "readOnlyHint": True,
        "idempotentHint": True,
        "destructiveHint": False,
        "openWorldHint": True,
    },
)
def get_entity_provenance(
    entity_id: str,
    ctx: Context,
    version: Optional[int] = None,
) -> Dict[str, Any]:
    """Return activity metadata for a Synapse entity, optionally scoping to a specific version."""
    if not validate_synapse_id(entity_id):
        return {"error": f"Invalid Synapse ID: {entity_id}"}

    try:
        synapse_client = get_synapse_client(ctx)
    except ConnectionAuthError as exc:
        return {"error": f"Authentication required: {exc}", "entity_id": entity_id}

    normalized_version: Optional[int] = None
    if version is not None:
        try:
            normalized_version = int(version)
            if normalized_version <= 0:
                return {"error": "Version must be a positive integer", "entity_id": entity_id, "version": version}
        except (TypeError, ValueError):
            return {"error": f"Invalid version number: {version}", "entity_id": entity_id}

    try:
        activity = synapse_client.getProvenance(
            entity_id, version=normalized_version)
    except SynapseHTTPError as exc:
        response = getattr(exc, "response", None)
        status_code = getattr(response, "status_code", None)
        if status_code == 404:
            return {
                "error": f"No provenance record found for {entity_id}",
                "entity_id": entity_id,
                "version": normalized_version,
            }
        return {
            "error": str(exc),
            "error_type": type(exc).__name__,
            "entity_id": entity_id,
            "version": normalized_version,
        }
    except ConnectionAuthError as exc:  # pragma: no cover - defensive path
        return {"error": f"Authentication required: {exc}", "entity_id": entity_id}
    except Exception as exc:  # pragma: no cover - defensive path
        return {
            "error": str(exc),
            "error_type": type(exc).__name__,
            "entity_id": entity_id,
            "version": normalized_version,
        }

    activity_payload: Dict[str, Any]
    if hasattr(activity, "to_dict"):
        activity_payload = activity.to_dict()
    elif isinstance(activity, dict):
        activity_payload = activity
    else:  # pragma: no cover - defensive fallback
        activity_payload = {"raw": str(activity)}

    result: Dict[str, Any] = {
        "entity_id": entity_id,
        "activity": activity_payload,
    }
    if normalized_version is not None:
        result["version"] = normalized_version

    return result


@mcp.tool(
    title="List Entity Children",
    description="List children for Synapse container entities (projects or folders).",
    annotations={
        "readOnlyHint": True,
        "idempotentHint": True,
        "destructiveHint": False,
        "openWorldHint": True,
    },
)
def get_entity_children(entity_id: str, ctx: Context) -> List[Dict[str, Any]]:
    """List children for Synapse container entities (projects or folders)."""
    if not validate_synapse_id(entity_id):
        return [{"error": f"Invalid Synapse ID: {entity_id}"}]

    try:
        entity_ops = get_entity_operations(ctx)
        entity = entity_ops["base"].get_entity_by_id(entity_id)
        entity_type = entity.get("type", "").lower()

        if entity_type == "project":
            return entity_ops["project"].get_project_children(entity_id)
        if entity_type == "folder":
            return entity_ops["folder"].get_folder_children(entity_id)
        return [{"error": f"Entity {entity_id} is not a container entity"}]
    except ConnectionAuthError as exc:
        return [{"error": f"Authentication required: {exc}", "entity_id": entity_id}]
    except Exception as exc:  # pragma: no cover - defensive path
        return [{"error": str(exc), "entity_id": entity_id}]


@mcp.tool(
    title="Search Synapse",
    description=(
        "Search Synapse entities using keyword queries with optional name/type/parent filters. "
        "Results are served by Synapse as data custodian. Attribution and licensing are "
        "determined by the original contributors; check the specific entity's annotations or Wiki for details."
    ),
    annotations={
        "readOnlyHint": True,
        "idempotentHint": True,
        "destructiveHint": False,
        "openWorldHint": True,
    },
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
    """Search Synapse entities using keyword queries with optional name/type/parent filters.

    Results are served by Synapse as data custodian. Attribution and licensing are
    determined by the original contributors; review the returned entity metadata for
    details."""
    try:
        synapse_client = get_synapse_client(ctx)
    except ConnectionAuthError as exc:
        return {"error": f"Authentication required: {exc}"}

    sanitized_limit = max(0, min(limit, 100))
    sanitized_offset = max(0, offset)

    query_terms: List[str] = []
    if query_term:
        query_terms.append(query_term)
    if name and name not in query_terms:
        query_terms.append(name)

    default_return_fields = _normalize_fields(DEFAULT_RETURN_FIELDS)
    request_payload: Dict[str, Any] = {
        "queryTerm": query_terms,
        "start": sanitized_offset,
        "size": sanitized_limit,
    }

    normalized_fields = default_return_fields
    if normalized_fields:
        request_payload["returnFields"] = normalized_fields

    requested_types: List[str] = []
    if entity_types:
        requested_types.extend(entity_types)
    if entity_type:
        requested_types.append(entity_type)

    boolean_query: List[Dict[str, Any]] = []
    for item in requested_types:
        normalized = (item or "").strip().lower()
        if not normalized:
            continue
        boolean_query.append({"key": "node_type", "value": normalized})

    if parent_id:
        boolean_query.append({"key": "path", "value": parent_id})

    if boolean_query:
        request_payload["booleanQuery"] = boolean_query

    warnings: List[str] = []
    original_payload: Optional[Dict[str, Any]] = None
    dropped_return_fields: Optional[List[str]] = None

    try:
        response = synapse_client.restPOST(
            "/search", body=json.dumps(request_payload))
    except ConnectionAuthError as exc:
        return {"error": f"Authentication required: {exc}"}
    except Exception as exc:  # pragma: no cover - defensive path
        error_message = str(exc)
        if "Invalid field name" in error_message and "returnFields" in request_payload:
            original_payload = dict(request_payload)
            dropped_return_fields = list(
                request_payload.get("returnFields", []))
            fallback_payload = {
                k: v for k, v in request_payload.items() if k != "returnFields"}

            try:
                response = synapse_client.restPOST(
                    "/search", body=json.dumps(fallback_payload))
            except Exception as fallback_exc:  # pragma: no cover - defensive path
                return {
                    "error": str(fallback_exc),
                    "query": fallback_payload,
                    "original_query": original_payload,
                    "dropped_return_fields": dropped_return_fields,
                }

            warnings.append(
                f"Synapse rejected requested return fields {dropped_return_fields}; retried without custom return fields."
            )
            request_payload = fallback_payload
        else:
            return {"error": error_message, "query": request_payload}

    result: Dict[str, Any] = {
        "found": response.get("found", 0),
        "start": response.get("start", sanitized_offset),
        "hits": response.get("hits", []),
        "facets": response.get("facets", []),
        "query": request_payload,
    }

    if warnings:
        result["warnings"] = warnings
    if original_payload:
        result["original_query"] = original_payload
    if dropped_return_fields:
        result["dropped_return_fields"] = dropped_return_fields

    return result


@mcp.tool(
    title="List Curation Tasks",
    description=(
        "List all curation tasks within a specific Synapse project. "
        "Returns task metadata including task IDs, data types, "
        "instructions, and task properties."
    ),
    annotations={
        "readOnlyHint": True,
        "idempotentHint": True,
        "destructiveHint": False,
        "openWorldHint": True,
    },
)
def list_curation_tasks(project_id: str, ctx: Context) -> List[Dict[str, Any]]:
    """List all curation tasks for a given project.

    Uses synapseclient.models.CurationTask.list() to retrieve all tasks
    for a project.

    Args:
        project_id: The synId of the project to list tasks for
        ctx: The FastMCP context

    Returns:
        A list of curation task dictionaries
    """
    if not validate_synapse_id(project_id):
        return [{"error": f"Invalid Synapse ID: {project_id}"}]

    try:
        synapse_client = get_synapse_client(ctx)
    except ConnectionAuthError as exc:
        return [
            {
                "error": f"Authentication required: {exc}",
                "project_id": project_id,
            }
        ]

    try:
        # Use CurationTask.list() to get all tasks for the project
        tasks = []
        for task in CurationTask.list(
            project_id=project_id, synapse_client=synapse_client
        ):
            # Convert the task object to a dictionary representation
            task_dict = {
                "task_id": task.task_id,
                "data_type": task.data_type,
                "project_id": task.project_id,
                "instructions": task.instructions,
                "etag": task.etag,
                "created_on": task.created_on,
                "modified_on": task.modified_on,
                "created_by": task.created_by,
                "modified_by": task.modified_by,
            }

            # Add task properties if available
            if task.task_properties:
                task_dict["task_properties"] = {}
                # Check the type of task properties
                if hasattr(task.task_properties, "record_set_id"):
                    task_dict["task_properties"]["type"] = "record-based"
                    task_dict["task_properties"]["record_set_id"] = (
                        task.task_properties.record_set_id
                    )
                elif hasattr(task.task_properties, "upload_folder_id"):
                    task_dict["task_properties"]["type"] = "file-based"
                    task_dict["task_properties"]["upload_folder_id"] = (
                        task.task_properties.upload_folder_id
                    )
                    task_dict["task_properties"]["file_view_id"] = (
                        task.task_properties.file_view_id
                    )

            tasks.append(task_dict)

        return tasks
    except ConnectionAuthError as exc:
        return [
            {
                "error": f"Authentication required: {exc}",
                "project_id": project_id,
            }
        ]
    except Exception as exc:
        return [{"error": str(exc), "error_type": type(exc).__name__, "project_id": project_id}]


@mcp.tool(
    title="Get Curation Task",
    description=(
        "Retrieve detailed information about a specific curation task "
        "by its task ID."
    ),
    annotations={
        "readOnlyHint": True,
        "idempotentHint": True,
        "destructiveHint": False,
        "openWorldHint": True,
    },
)
def get_curation_task(task_id: int, ctx: Context) -> Dict[str, Any]:
    """Get a specific curation task by its task ID.

    Uses synapseclient.models.CurationTask.get() to retrieve a specific task.

    Args:
        task_id: The numeric ID of the curation task
        ctx: The FastMCP context

    Returns:
        The curation task details as a dictionary
    """
    try:
        synapse_client = get_synapse_client(ctx)
    except ConnectionAuthError as exc:
        return {"error": f"Authentication required: {exc}", "task_id": task_id}

    try:
        # Use CurationTask.get() to retrieve the task
        task = CurationTask(task_id=task_id).get(synapse_client=synapse_client)

        # Convert to dictionary
        task_dict = {
            "task_id": task.task_id,
            "data_type": task.data_type,
            "project_id": task.project_id,
            "instructions": task.instructions,
            "etag": task.etag,
            "created_on": task.created_on,
            "modified_on": task.modified_on,
            "created_by": task.created_by,
            "modified_by": task.modified_by,
        }

        # Add task properties if available
        if task.task_properties:
            task_dict["task_properties"] = {}
            # Check the type of task properties
            if hasattr(task.task_properties, "record_set_id"):
                task_dict["task_properties"]["type"] = "record-based"
                task_dict["task_properties"]["record_set_id"] = (
                    task.task_properties.record_set_id
                )
            elif hasattr(task.task_properties, "upload_folder_id"):
                task_dict["task_properties"]["type"] = "file-based"
                task_dict["task_properties"]["upload_folder_id"] = (
                    task.task_properties.upload_folder_id
                )
                task_dict["task_properties"]["file_view_id"] = (
                    task.task_properties.file_view_id
                )

        return task_dict
    except ConnectionAuthError as exc:
        return {"error": f"Authentication required: {exc}", "task_id": task_id}
    except Exception as exc:
        return {"error": str(exc), "error_type": type(exc).__name__, "task_id": task_id}


@mcp.tool(
    title="Get Curation Task Resources",
    description=(
        "Explore and retrieve resources associated with a curation task, "
        "including RecordSets, Folders, and EntityViews based on the task "
        "type (file-based or record-based)."
    ),
    annotations={
        "readOnlyHint": True,
        "idempotentHint": True,
        "destructiveHint": False,
        "openWorldHint": True,
    },
)
def get_curation_task_resources(task_id: int, ctx: Context) -> Dict[str, Any]:
    """Get resources associated with a curation task.

    This tool retrieves the task details using CurationTask.get() and then
    fetches information about associated resources based on the task type:
    - For file-based tasks: Returns information about the upload folder
      and file view
    - For record-based tasks: Returns information about the record set

    Args:
        task_id: The numeric ID of the curation task
        ctx: The FastMCP context

    Returns:
        A dictionary containing the task details and associated resource
        information
    """
    try:
        synapse_client = get_synapse_client(ctx)
    except ConnectionAuthError as exc:
        return {"error": f"Authentication required: {exc}", "task_id": task_id}

    try:
        # Use CurationTask.get() to retrieve the task
        task = CurationTask(task_id=task_id).get(synapse_client=synapse_client)

        result: Dict[str, Any] = {
            "task_id": task.task_id,
            "data_type": task.data_type,
            "project_id": task.project_id,
            "instructions": task.instructions,
            "resources": {},
        }

        # Handle file-based metadata tasks
        if hasattr(task.task_properties, "upload_folder_id"):
            upload_folder_id = task.task_properties.upload_folder_id
            file_view_id = task.task_properties.file_view_id

            resources = result["resources"]
            resources["type"] = "file-based"

            if upload_folder_id:
                try:
                    folder_info = Folder(id=upload_folder_id).get(
                        synapse_client=synapse_client)
                    resources["upload_folder"] = folder_info
                except Exception as folder_exc:
                    resources["upload_folder"] = {
                        "error": str(folder_exc),
                        "id": upload_folder_id,
                    }

            if file_view_id:
                try:
                    view_info = EntityView(id=file_view_id).get(
                        synapse_client=synapse_client)
                    resources["file_view"] = view_info
                except Exception as view_exc:
                    resources["file_view"] = {
                        "error": str(view_exc),
                        "id": file_view_id,
                    }

        # Handle record-based metadata tasks
        elif hasattr(task.task_properties, "record_set_id"):
            record_set_id = task.task_properties.record_set_id

            result["resources"]["type"] = "record-based"

            if record_set_id:
                try:
                    record_set_info = RecordSet(id=record_set_id, download_file=False).get(
                        synapse_client=synapse_client)
                    result["resources"]["record_set"] = record_set_info
                except Exception as rs_exc:
                    result["resources"]["record_set"] = {
                        "error": str(rs_exc),
                        "id": record_set_id,
                    }

        return result
    except ConnectionAuthError as exc:
        return {"error": f"Authentication required: {exc}", "task_id": task_id}
    except Exception as exc:
        return {"error": str(exc), "error_type": type(exc).__name__, "task_id": task_id}


@mcp.tool(
    title="Get Bound JSON Schema",
    description=(
        "Retrieve the JSON schema that is bound to a Synapse folder or RecordSet. "
        "Returns the schema body (data model definition) and entity metadata. "
        "This tool retrieves entity metadata itself, so there is no need to run the Fetch Entity tool first."
    ),
    annotations={
        "readOnlyHint": True,
        "idempotentHint": True,
        "destructiveHint": False,
        "openWorldHint": True,
    },
)
def get_bound_schema(entity_id: str, ctx: Context) -> Dict[str, Any]:
    """Get the JSON schema bound to a folder or RecordSet.

    This tool retrieves the bound schema and returns the full schema body
    (data model definition) along with entity and schema metadata.

    Args:
        entity_id: The Synapse ID of the folder or RecordSet
        ctx: The FastMCP context

    Returns:
        Dictionary containing:
        - entity_metadata: Information about the folder/RecordSet
        - schema_info: Schema version information (URI, organization, name)
        - schema_body: The full JSON schema definition (data model)
    """
    if not validate_synapse_id(entity_id):
        return {"error": f"Invalid Synapse ID: {entity_id}"}

    try:
        synapse_client = get_synapse_client(ctx)
    except ConnectionAuthError as exc:
        return {"error": f"Authentication required: {exc}", "entity_id": entity_id}

    try:
        # Use synapseclient.operations.get to retrieve the entity
        entity = get(
            synapse_id=entity_id,
            file_options=FileOptions(download_file=False),
            synapse_client=synapse_client
        )

        # Format entity metadata
        entity_metadata = {
            "id": entity.id if hasattr(entity, 'id') else entity_id,
            "name": entity.name if hasattr(entity, 'name') else None,
            "type": entity.concreteType.split('.')[-1] if hasattr(entity, 'concreteType') else None,
            "parent_id": entity.parentId if hasattr(entity, 'parentId') else None,
            "created_on": entity.createdOn if hasattr(entity, 'createdOn') else None,
            "modified_on": entity.modifiedOn if hasattr(entity, 'modifiedOn') else None,
        }

        # Get the bound schema using Folder model
        folder = Folder(id=entity_id)
        schema = folder.get_schema(synapse_client=synapse_client)

        # Check if a schema is bound
        if not schema or not schema.json_schema_version_info:
            return {
                "entity_id": entity_id,
                "entity_metadata": entity_metadata,
                "has_schema": False,
                "message": "No JSON schema is bound to this entity",
            }

        # Extract schema version info
        schema_version_info = schema.json_schema_version_info
        schema_info = {
            "json_schema_uri": schema_version_info.json_schema_uri if hasattr(schema_version_info, 'json_schema_uri') else None,
            "version_id": schema_version_info.version_id if hasattr(schema_version_info, 'version_id') else None,
            "organization_name": schema_version_info.organization_name if hasattr(schema_version_info, 'organization_name') else None,
            "schema_name": schema_version_info.schema_name if hasattr(schema_version_info, 'schema_name') else None,
        }

        result = {
            "entity_id": entity_id,
            "entity_metadata": entity_metadata,
            "has_schema": True,
            "schema_info": schema_info,
        }

        # Get the full schema body (data model definition)
        try:
            if schema_version_info.schema_name and schema_version_info.organization_name:
                json_schema = JSONSchema(
                    name=schema_version_info.schema_name,
                    organization_name=schema_version_info.organization_name
                )
                schema_body = json_schema.get_body(
                    synapse_client=synapse_client)
                result["schema_body"] = schema_body
        except Exception as body_exc:
            result["schema_body_error"] = f"Could not retrieve schema body: {str(body_exc)}"

        return result

    except ConnectionAuthError as exc:
        return {"error": f"Authentication required: {exc}", "entity_id": entity_id}
    except Exception as exc:
        return {
            "error": str(exc),
            "entity_id": entity_id,
            "error_type": type(exc).__name__
        }


@mcp.tool(
    title="Generate JSON Schema from JSON-LD or CSV Data Model",
    description=(
        "Convert a JSON-LD or CSV data model to JSON Schema format using the Synapse curator extension. "
        "The input should be a URL containing the data model definition with components and attributes. "
        "Supports both JSON-LD and CSV formats. "
        "Returns the generated schemas. The URL can be any number of sources including external websites."
    ),
    annotations={
        "readOnlyHint": False,
        "idempotentHint": False,
        "destructiveHint": False,
        "openWorldHint": False,
    },
)
def generate_json_schema(
    data_model_source: str,
    ctx: Context,
    data_type: Optional[str] = None,
    data_model_labels: str = "class_label",
) -> Dict[str, Any]:
    """Generate JSON Schema from a JSON-LD or CSV data model.

    This tool converts a JSON-LD or CSV data model into JSON Schema format using the
    Synapse curator extension's generate_jsonschema function. Files are written
    to a temporary directory that is automatically cleaned up after generation.

    Args:
        data_model_source: URL containing the data model definition. Supports both
                          JSON-LD and CSV formats.
        ctx: The FastMCP context
        data_type: Optional specific component/data type to generate schema for.
                  If None, generates schemas for all components in the data model.
        data_model_labels: Column name that contains the class labels
                          (default: "class_label")

    Returns:
        Dictionary containing:
        - schemas: Dict mapping data types to their generated JSON schemas
        - data_model_source: The source data model path/ID used
    """
    try:
        synapse_client = get_synapse_client(ctx)
    except ConnectionAuthError as exc:
        return {"error": f"Authentication required: {exc}", "success": False}

    # Create a temporary directory that will be automatically cleaned up
    temp_dir = tempfile.mkdtemp(prefix="synapse_json_schema_")

    try:
        # Generate JSON schemas from the JSON-LD data model
        schemas, file_paths = generate_jsonschema(
            data_model_source=data_model_source,
            output_directory=temp_dir,
            data_type=data_type,
            data_model_labels=data_model_labels,
            synapse_client=synapse_client
        )

        return {
            "success": True,
            "schemas": schemas,
            "data_model_source": data_model_source,
            "data_type": data_type,
            "message": f"Generated {len(schemas)} JSON schema(s)"
        }

    except ConnectionAuthError as exc:
        return {"error": f"Authentication required: {exc}", "success": False}
    except FileNotFoundError as exc:
        return {
            "error": f"Data model file not found: {str(exc)}",
            "success": False,
            "error_type": type(exc).__name__,
            "data_model_source": data_model_source,
        }
    except Exception as exc:
        return {
            "error": str(exc),
            "success": False,
            "error_type": type(exc).__name__,
            "data_model_source": data_model_source,
        }
    finally:
        # Always clean up the temporary directory
        try:
            shutil.rmtree(temp_dir)
        except Exception:
            # Silently ignore cleanup errors
            pass


@mcp.tool(
    title="Register Schema Organization",
    description=(
        "Create a new schema organization in Synapse. Schema organizations act as "
        "namespaces for JSON schemas. Organization names must be at least 6 characters, "
        "cannot start with a number, and should follow dot-separated alphanumeric format "
        "(e.g., 'my.organization'). Returns the created organization metadata."
    ),
    annotations={
        "readOnlyHint": False,
        "idempotentHint": False,
        "destructiveHint": False,
        "openWorldHint": False,
    },
)
def register_schema_organization(
    organization_name: str,
    ctx: Context,
) -> Dict[str, Any]:
    """Register a new schema organization in Synapse.

    Creates a new schema organization that serves as a namespace for JSON schemas.
    The new organization will have an auto-generated AccessControlList (ACL) granting
    the caller all relevant permissions.

    Args:
        organization_name: Unique name for the organization. Must be at least 6 characters,
                          cannot start with a number, and should follow dot-separated
                          alphanumeric format (e.g., "my.organization")
        ctx: The FastMCP context

    Returns:
        Dictionary containing:
        - success: Boolean indicating if the operation was successful
        - organization: Dict with organization metadata (id, name, created_on, created_by)
        - message: Success or error message

    Example:
        org_result = register_schema_organization("my.new.org", ctx)
        if org_result["success"]:
            print(f"Created organization: {org_result['organization']}")
    """
    try:
        synapse_client = get_synapse_client(ctx)
    except ConnectionAuthError as exc:
        return {"error": f"Authentication required: {exc}", "success": False}

    try:
        # Create the schema organization using the SchemaOrganization model
        org = SchemaOrganization(name=organization_name)
        org.store(synapse_client=synapse_client)

        return {
            "success": True,
            "organization": {
                "id": org.id,
                "name": org.name,
                "created_on": org.created_on,
                "created_by": org.created_by,
            },
            "message": f"Successfully created organization '{organization_name}'",
        }

    except ValueError as exc:
        # Handle validation errors (e.g., invalid name format)
        return {
            "error": str(exc),
            "success": False,
            "organization_name": organization_name,
        }
    except SynapseHTTPError as exc:
        # Handle HTTP errors (e.g., organization already exists, permission issues)
        error_msg = str(exc)
        if "already exists" in error_msg.lower():
            return {
                "error": f"Organization '{organization_name}' already exists",
                "success": False,
                "organization_name": organization_name,
            }
        return {
            "error": error_msg,
            "success": False,
            "organization_name": organization_name,
        }
    except ConnectionAuthError as exc:
        return {
            "error": f"Authentication required: {exc}",
            "success": False,
            "organization_name": organization_name,
        }
    except Exception as exc:
        return {
            "error": str(exc),
            "error_type": type(exc).__name__,
            "success": False,
            "organization_name": organization_name,
        }


@mcp.tool(
    title="Register JSON Schema from JSON-LD or CSV Data Model",
    description=(
        "Generate and register all JSON schemas from a data model (JSON-LD or CSV) to a Synapse "
        "organization. This tool converts a data model into JSON Schema format and automatically "
        "registers all generated schemas to the specified organization with the given version. "
        "The organization must already exist."
    ),
    annotations={
        "readOnlyHint": False,
        "idempotentHint": False,
        "destructiveHint": False,
        "openWorldHint": False,
    },
)
def register_json_schema_from_data_model(
    data_model_source: str,
    organization_name: str,
    ctx: Context,
    schema_prefix: Optional[str] = None,
    version: Optional[str] = None,
    data_type: Optional[str] = None,
    data_model_labels: str = "class_label",
) -> Dict[str, Any]:
    """Generate and register JSON schemas from a JSON-LD or CSV data model to a Synapse organization.

    This tool converts a JSON-LD or CSV data model into JSON Schema format using the
    Synapse curator extension's generate_jsonschema function, then automatically registers
    all generated schemas to the specified organization. Files are written to a temporary
    directory that is automatically cleaned up after generation.

    Args:
        data_model_source: URL containing the data model definition. Supports both
                          JSON-LD and CSV formats.
        organization_name: Name of the organization to register the schemas to.
        ctx: The FastMCP context
        schema_prefix: Optional prefix to prepend to each schema name upon registration
        version: Optional semantic version (e.g., "0.0.1") to assign to all registered schemas
        data_type: Optional specific component/data type to generate schema for.
                  If None, generates schemas for all components in the data model.
        data_model_labels: Column name that contains the class labels
                          (default: "class_label")

    Returns:
        Dictionary containing:
        - success: Boolean indicating if the operation was successful
        - registered_schemas: List of registered JSONSchema objects
        - data_model_source: The source data model path/ID used
        - data_type: The specific data type if specified
        - message: Success or error message
    """
    try:
        synapse_client = get_synapse_client(ctx)
    except ConnectionAuthError as exc:
        return {"error": f"Authentication required: {exc}", "success": False}

    # Verify organization exists
    try:
        org = SchemaOrganization(name=organization_name)
        org.get(synapse_client=synapse_client)
    except ValueError as exc:
        return {
            "error": f"Organization '{organization_name}' does not exist. Create it first using register_schema_organization.",
            "success": False,
            "error_type": type(exc).__name__,
            "organization_name": organization_name,
        }
    except Exception as exc:
        return {
            "error": f"Error checking organization: {str(exc)}",
            "success": False,
            "error_type": type(exc).__name__,
            "organization_name": organization_name,
        }

    # Create a temporary directory that will be automatically cleaned up
    temp_dir = tempfile.mkdtemp(prefix="synapse_json_schema_")

    try:
        # Generate JSON schemas from the JSON-LD data model
        schemas, _ = generate_jsonschema(
            data_model_source=data_model_source,
            output_directory=temp_dir,
            data_type=data_type,
            data_model_labels=data_model_labels,
            synapse_client=synapse_client
        )

        registered_schemas = []

        # Register each generated schema to the specified organization
        for schema_body in schemas:
            title_from_schema = schema_body.get("title")
            assert title_from_schema is not None, "Generated schema missing 'title' field"
            title_from_schema = title_from_schema.replace("_validation", "")
            if schema_prefix:
                schema_name = f"{schema_prefix}.{title_from_schema}.schema"
            else:
                schema_name = f"{title_from_schema}.schema"
            json_schema = JSONSchema(
                name=schema_name, organization_name=organization_name)
            json_schema.store(
                schema_body=schema_body,
                version=version,
                dry_run=False,
                synapse_client=synapse_client,
            )
            registered_schemas.append(json_schema)

        return {
            "success": True,
            "registered_schemas": registered_schemas,
            "data_model_source": data_model_source,
            "data_type": data_type,
            "message": f"Generated and registered {len(registered_schemas)} JSON schema(s) to organization '{organization_name}'"
        }

    except ConnectionAuthError as exc:
        return {"error": f"Authentication required: {exc}", "success": False}
    except FileNotFoundError as exc:
        return {
            "error": f"Data model file not found: {str(exc)}",
            "success": False,
            "error_type": type(exc).__name__,
            "data_model_source": data_model_source,
        }
    except Exception as exc:
        return {
            "error": str(exc),
            "success": False,
            "error_type": type(exc).__name__,
            "data_model_source": data_model_source,
        }
    finally:
        # Always clean up the temporary directory
        try:
            shutil.rmtree(temp_dir)
        except Exception:
            # Silently ignore cleanup errors
            pass


@mcp.tool(
    title="Register JSON Schema to Organization",
    description=(
        "Register a JSON schema to a Synapse schema organization. The schema will be "
        "stored under the specified organization with the given name and body. "
        "Optionally specify a semantic version (e.g., '0.0.1'). Returns the registered schema metadata."
    ),
    annotations={
        "readOnlyHint": False,
        "idempotentHint": False,
        "destructiveHint": False,
        "openWorldHint": False,
    },
)
def register_json_schema_json_body(
    organization_name: str,
    schema_name: str,
    schema_body: Dict[str, Any],
    ctx: Context,
    version: Optional[str] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Register a JSON schema to a Synapse organization.

    Creates and stores a JSON schema under the specified organization. The organization
    must already exist in Synapse before registering schemas to it.

    Args:
        organization_name: Name of the organization to register the schema to
        schema_name: Name for the JSON schema
        schema_body: The JSON schema definition (dict following JSON Schema Draft-07 or later)
        ctx: The FastMCP context
        version: Optional semantic version (e.g., "0.0.1"). Must start at 0.0.1 with
                major.minor.patch format
        dry_run: If True, validates the schema without actually storing it

    Returns:
        Dictionary containing:
        - success: Boolean indicating if the operation was successful
        - schema: Dict with schema metadata (uri, organization_id, organization_name, name, created_on, created_by)
        - message: Success or error message

    Example:
        schema_body = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"}
            },
            "required": ["name"]
        }
        result = register_json_schema("my.org", "person.schema", schema_body, ctx, version="0.0.1")
        if result["success"]:
            print(f"Registered schema: {result['schema']['uri']}")
    """
    try:
        synapse_client = get_synapse_client(ctx)
    except ConnectionAuthError as exc:
        return {"error": f"Authentication required: {exc}", "success": False}

    # Verify organization exists
    try:
        org = SchemaOrganization(name=organization_name)
        org.get(synapse_client=synapse_client)
    except ValueError as exc:
        return {
            "error": f"Organization '{organization_name}' does not exist. Create it first using register_schema_organization.",
            "success": False,
            "organization_name": organization_name,
        }
    except Exception as exc:
        return {
            "error": f"Error checking organization: {str(exc)}",
            "success": False,
            "organization_name": organization_name,
        }

    try:
        # Create the JSONSchema object
        schema = JSONSchema(
            name=schema_name, organization_name=organization_name)

        # Store the schema with the provided body
        schema.store(
            schema_body=schema_body,
            version=version,
            dry_run=dry_run,
            synapse_client=synapse_client,
        )

        return {
            "success": True,
            "schema": {
                "uri": schema.uri,
                "organization_id": schema.organization_id,
                "organization_name": schema.organization_name,
                "name": schema.name,
                "created_on": schema.created_on,
                "created_by": schema.created_by,
            },
            "message": f"Successfully registered schema '{schema_name}' to organization '{organization_name}'"
            + (f" with version {version}" if version else ""),
            "dry_run": dry_run,
        }

    except ValueError as exc:
        # Handle validation errors (e.g., invalid name, version format, missing organization)
        return {
            "error": str(exc),
            "success": False,
            "organization_name": organization_name,
            "schema_name": schema_name,
        }
    except SynapseHTTPError as exc:
        # Handle HTTP errors (e.g., organization doesn't exist, schema already exists, permission issues)
        error_msg = str(exc)
        if "not found" in error_msg.lower() or "does not exist" in error_msg.lower():
            return {
                "error": f"Organization '{organization_name}' does not exist. Create it first using register_schema_organization.",
                "success": False,
                "organization_name": organization_name,
                "schema_name": schema_name,
            }
        elif "already exists" in error_msg.lower():
            return {
                "error": f"Schema '{schema_name}' with version '{version}' already exists in organization '{organization_name}'",
                "success": False,
                "organization_name": organization_name,
                "schema_name": schema_name,
                "version": version,
            }
        return {
            "error": error_msg,
            "success": False,
            "organization_name": organization_name,
            "schema_name": schema_name,
        }
    except ConnectionAuthError as exc:
        return {
            "error": f"Authentication required: {exc}",
            "success": False,
            "organization_name": organization_name,
            "schema_name": schema_name,
        }
    except Exception as exc:
        return {
            "error": str(exc),
            "error_type": type(exc).__name__,
            "success": False,
            "organization_name": organization_name,
            "schema_name": schema_name,
        }


__all__ = [
    "get_entity",
    "get_entity_annotations",
    "get_entity_provenance",
    "get_entity_children",
    "search_synapse",
    "list_curation_tasks",
    "get_curation_task",
    "get_curation_task_resources",
    "get_bound_schema",
    "generate_json_schema",
    "register_schema_organization",
    "register_json_schema_json_body",
    "register_json_schema_from_data_model",
]
