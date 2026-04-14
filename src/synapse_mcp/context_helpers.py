"""Helpers for accessing request-scoped context."""

from typing import Any, Dict, List, Optional

from fastmcp import Context
from fastmcp.server.context import request_ctx

from .connection_auth import ConnectionAuthError


def get_request_context() -> Optional[Context]:
    """Return the request-scoped FastMCP context if available."""
    try:
        return request_ctx.get()
    except LookupError:
        return None


def require_request_context() -> Context:
    """Fetch the active request context or raise an auth error."""
    ctx = get_request_context()
    if ctx is None:
        raise ConnectionAuthError(
            "No active request context; ensure the request is routed "
            "through an authenticated MCP connection."
        )
    return ctx


def first_successful_result(
    results: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Return the first non-error result from a list of entity responses."""
    for item in results:
        if not isinstance(item, dict):
            return item
        if not item.get("error"):
            return item
    return None


__all__ = [
    "ConnectionAuthError",
    "first_successful_result",
    "get_request_context",
    "require_request_context",
]
