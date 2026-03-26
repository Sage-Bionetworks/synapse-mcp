"""Common service-layer helpers for MCP tool functions."""

import functools
import inspect
from contextlib import contextmanager
from typing import Any, Callable, Dict, Optional, Tuple, Type

from fastmcp import Context

from ..connection_auth import ConnectionAuthError, get_synapse_client


@contextmanager
def synapse_client_from(ctx: Context):
    """Yield an authenticated Synapse client for the given request context.

    Raises ConnectionAuthError if the client cannot be obtained.
    """
    yield get_synapse_client(ctx)


def error_boundary(
    *,
    error_context_keys: Tuple[str, ...] = (),
    wrap_errors: Optional[Type] = None,
) -> Callable:
    """Decorator that catches exceptions in service methods and returns error dicts.

    Args:
        error_context_keys: Parameter names whose values should be included in
            error responses for debugging context (e.g. ``("project_id",)``).
        wrap_errors: If set to ``list``, wraps error dicts in a list so the
            return type stays consistent for list-returning service methods.
    """
    def decorator(method: Callable) -> Callable:
        # Pre-compute parameter positions at decoration time.
        sig = inspect.signature(method)
        param_names = list(sig.parameters.keys())[2:]  # skip self, ctx
        context_positions = {
            name: i for i, name in enumerate(param_names)
            if name in error_context_keys
        }

        @functools.wraps(method)
        def wrapper(self, ctx, *args, **kwargs):
            extra: Dict[str, Any] = {}
            for name, pos in context_positions.items():
                if pos < len(args):
                    extra[name] = args[pos]
                elif name in kwargs:
                    extra[name] = kwargs[name]

            try:
                return method(self, ctx, *args, **kwargs)
            except ConnectionAuthError as exc:
                err = {"error": f"Authentication required: {exc}", **extra}
                return [err] if wrap_errors is list else err
            except Exception as exc:
                err = {
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                    **extra,
                }
                return [err] if wrap_errors is list else err

        return wrapper
    return decorator
