"""Common service-layer helpers for MCP tool functions."""

import functools
import inspect
from contextlib import contextmanager
from dataclasses import fields as dataclass_fields, is_dataclass
from typing import Any, Callable, Dict, Tuple

from fastmcp import Context

from ..connection_auth import ConnectionAuthError, get_synapse_client


def dataclass_to_dict(obj: Any) -> Any:
    """Recursively serialize a dataclass into a plain dict.

    Includes all fields where ``repr=True``. Nested dataclasses are
    recursively serialized. Non-dataclass values pass through unchanged.
    """
    if obj is None or not is_dataclass(obj) or isinstance(obj, type):
        return obj

    result: Dict[str, Any] = {}
    for f in dataclass_fields(obj):
        if not f.repr:
            continue
        value = getattr(obj, f.name)
        if is_dataclass(value) and not isinstance(value, type):
            result[f.name] = dataclass_to_dict(value)
        else:
            result[f.name] = value
    return result


@contextmanager
def synapse_client(ctx: Context):
    """Yield an authenticated Synapse client for the given request context.

    Raises ConnectionAuthError if the client cannot be obtained.
    """
    yield get_synapse_client(ctx)


def error_boundary(
    *,
    error_context_keys: Tuple[str, ...] = (),
    wrap_errors: bool = False,
) -> Callable:
    """Decorator that catches exceptions in service methods and returns error dicts.

    Args:
        error_context_keys: Parameter names whose values should be included in
            error responses for debugging context (e.g. ``("project_id",)``).
        wrap_errors: If ``True``, wraps error dicts in a list so the
            return type stays consistent for list-returning service methods.
    """
    def decorator(method: Callable) -> Callable:
        # Pre-compute parameter positions at decoration time.
        # Slice past ``self`` and ``ctx`` (the first two params) to get
        # only the business-logic parameters whose values may be included
        # in error responses via ``error_context_keys``.
        sig = inspect.signature(method)
        param_names = list(sig.parameters.keys())[2:]
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
                err = {
                    "error": f"Authentication required: {exc}",
                    "error_type": type(exc).__name__,
                    **extra,
                }
                return [err] if wrap_errors else err
            except Exception as exc:
                err = {
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                    **extra,
                }
                return [err] if wrap_errors else err

        return wrapper
    return decorator
