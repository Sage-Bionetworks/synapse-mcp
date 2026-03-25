"""Common service-layer helpers for MCP tool functions."""

from typing import Any, Callable, Dict, Optional, TypeVar

from fastmcp import Context

from ..connection_auth import ConnectionAuthError, get_synapse_client

T = TypeVar("T")


def with_synapse_client(
    ctx: Context,
    callback: Callable[..., T],
    *,
    error_context: Optional[Dict[str, Any]] = None,
) -> T:
    """Get an authenticated Synapse client and invoke *callback*, returning
    its result directly on success or a standardised error dict on failure.

    Args:
        ctx: The FastMCP request context.
        callback: A callable that receives a ``synapseclient.Synapse`` instance
            and returns the tool result.
        error_context: Optional extra keys (e.g. ``{"project_id": "syn123"}``)
            merged into every error response so callers don't lose context.
    """
    extra = error_context or {}

    try:
        synapse_client = get_synapse_client(ctx)
    except ConnectionAuthError as exc:
        return {"error": f"Authentication required: {exc}", **extra}

    try:
        return callback(synapse_client)
    except ConnectionAuthError as exc:
        return {"error": f"Authentication required: {exc}", **extra}
    except Exception as exc:
        return {
            "error": str(exc),
            "error_type": type(exc).__name__,
            **extra,
        }
