"""Common service-layer helpers for MCP tool functions."""

import functools
import inspect
from contextlib import asynccontextmanager
from dataclasses import fields as dataclass_fields, is_dataclass
from typing import Any, Callable, Dict, Tuple

from fastmcp import Context

from ..connection_auth import ConnectionAuthError, get_synapse_client


def dataclass_to_dict(obj: Any) -> Any:
    """Recursively serialize a dataclass into a plain dict.

    Includes all public fields where ``repr=True``. Fields starting with
    ``_`` are considered internal and excluded. Nested dataclasses, dicts,
    and lists are recursively serialized. Non-dataclass values pass through
    unchanged.
    """
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj

    if isinstance(obj, dict):
        return {k: dataclass_to_dict(v) for k, v in obj.items()}

    if isinstance(obj, (list, tuple)):
        return [dataclass_to_dict(item) for item in obj]

    if is_dataclass(obj) and not isinstance(obj, type):
        result: Dict[str, Any] = {}
        for f in dataclass_fields(obj):
            if not f.repr or f.name.startswith("_"):
                continue
            value = getattr(obj, f.name)
            result[f.name] = dataclass_to_dict(value)
        return result

    return obj


@asynccontextmanager
async def synapse_client(ctx: Context):
    """Yield an authenticated Synapse client for the given request context.

    Raises ConnectionAuthError if the client cannot be obtained.
    """
    yield await get_synapse_client(ctx)


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
        async def wrapper(self, ctx, *args, **kwargs):
            extra: Dict[str, Any] = {}
            for name, pos in context_positions.items():
                if pos < len(args):
                    extra[name] = args[pos]
                elif name in kwargs:
                    extra[name] = kwargs[name]

            try:
                return await method(self, ctx, *args, **kwargs)
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
