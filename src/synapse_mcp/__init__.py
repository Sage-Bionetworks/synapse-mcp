"""Public exports for the Synapse MCP package."""

from .app import auth, health_check, mcp
from .connection_auth import get_synapse_client
from .context_helpers import (
    ConnectionAuthError,
    first_successful_result,
    get_entity_operations,
    get_request_context,
    require_request_context,
)
from .resources import synapse_blog_feed
from .tools import (
    get_entity,
    get_entity_annotations,
    get_entity_children,
    get_curation_task,
    get_curation_task_resources,
    list_curation_tasks,
    search_synapse,
)

__all__ = [
    "auth",
    "ConnectionAuthError",
    "first_successful_result",
    "get_curation_task",
    "get_curation_task_resources",
    "get_entity",
    "get_entity_annotations",
    "get_entity_children",
    "get_entity_operations",
    "get_synapse_client",
    "get_request_context",
    "health_check",
    "list_curation_tasks",
    "mcp",
    "require_request_context",
    "search_synapse",
    "synapse_blog_feed",
]
