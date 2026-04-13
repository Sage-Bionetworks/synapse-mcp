"""Common service-layer helpers for MCP tool functions."""

import dataclasses
import enum
import functools
import inspect
from collections.abc import Mapping
from contextlib import asynccontextmanager
from datetime import date, datetime
from typing import Any, AsyncIterator, Callable, Dict, Iterator, Tuple

from fastmcp import Context

from ..connection_auth import ConnectionAuthError, get_synapse_client


def dataclass_to_dict(obj: Any) -> Any:
    """Recursively serialize a dataclass into a plain dict.

    Includes all public fields where ``repr=True``. Fields starting with
    ``_`` are considered internal and excluded. Nested dataclasses, dicts,
    and lists are recursively serialized. Datetimes are converted to ISO
    format strings, enums to their ``.value``. Non-dataclass values pass
    through unchanged.
    """
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj

    if isinstance(obj, (datetime, date)):
        return obj.isoformat()

    if isinstance(obj, enum.Enum):
        return obj.value

    if isinstance(obj, dict):
        return {k: dataclass_to_dict(v) for k, v in obj.items()}

    if isinstance(obj, (list, tuple)):
        return [dataclass_to_dict(item) for item in obj]

    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        result: Dict[str, Any] = {}
        for f in dataclasses.fields(obj):
            if not f.repr or f.name.startswith("_"):
                continue
            value = getattr(obj, f.name)
            result[f.name] = dataclass_to_dict(value)
        return result

    return obj


def collect_generator(gen: Iterator, limit: int = 100) -> list:
    """Collect up to *limit* items from a generator.

    All service methods that consume SDK generators must use this
    helper to prevent unbounded iteration.
    """
    items: list = []
    for item in gen:
        items.append(item)
        if len(items) >= limit:
            break
    return items


async def collect_async_generator(gen: AsyncIterator, limit: int = 100) -> list:
    """Collect up to *limit* items from an async generator.

    Async counterpart of ``collect_generator`` for SDK methods that
    return ``AsyncGenerator``.
    """
    items: list = []
    async for item in gen:
        items.append(item)
        if len(items) >= limit:
            break
    return items


@asynccontextmanager
async def synapse_client(ctx: Context):
    """Yield an authenticated Synapse client for the given request context.

    Raises ConnectionAuthError if the client cannot be obtained.
    """
    yield await get_synapse_client(ctx)


def serialize_model(obj: Any) -> Any:
    """Recursively serialize a synapseclient model to JSON-safe types.

    Includes all public dataclass fields except those marked with
    ``repr=False`` or whose name starts with ``_``. Nested
    dataclasses, lists, dicts, dates, and primitives are handled
    recursively.

    Arguments:
        obj: A synapseclient model instance, dict, list, or
            primitive value.

    Returns:
        A JSON-serializable dict, list, or primitive.
    """
    if obj is None:
        return None

    if isinstance(obj, (str, int, float, bool)):
        return obj

    if isinstance(obj, (datetime, date)):
        return obj.isoformat()

    if isinstance(obj, dict):
        return {
            k: serialize_model(v) for k, v in obj.items()
        }

    if isinstance(obj, (list, tuple)):
        return [serialize_model(item) for item in obj]

    if dataclasses.is_dataclass(obj) and not isinstance(
        obj, type
    ):
        result: Dict[str, Any] = {}
        for field in dataclasses.fields(obj):
            if not field.repr or field.name.startswith("_"):
                continue
            val = getattr(obj, field.name, None)
            result[field.name] = serialize_model(val)
        return result

    # Legacy Synapse entity objects (non-dataclass).
    # These are MutableMapping subclasses (dict-like)
    # returned by synapseclient.Synapse.get().
    if isinstance(obj, Mapping):
        return {
            k: serialize_model(v)
            for k, v in obj.items()
        }

    if hasattr(obj, "to_dict"):
        return obj.to_dict()

    return str(obj)


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
                # Extract HTTP status code from SynapseHTTPError
                response = getattr(exc, "response", None)
                if response is not None:
                    status_code = getattr(
                        response, "status_code", None
                    )
                    if status_code is not None:
                        err["status_code"] = status_code
                return [err] if wrap_errors else err

        return wrapper
    return decorator
