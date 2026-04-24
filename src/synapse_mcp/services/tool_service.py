"""Common service-layer helpers for MCP tool functions."""

import dataclasses
import enum
import functools
import inspect
import re
from collections.abc import Mapping
from contextlib import asynccontextmanager
from datetime import date, datetime
from typing import (
    Any,
    AsyncIterator,
    Callable,
    Dict,
    Iterable,
    Iterator,
    Literal,
    Optional,
    Tuple,
)

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


# ---------------------------------------------------------------------------
# Tool registration decorator
# ---------------------------------------------------------------------------


ServiceName = Literal[
    "entity",
    "wiki",
    "team",
    "user",
    "activity",
    "evaluation",
    "submission",
    "schema",
    "organization",
    "form",
    "curation",
    "utility",
    "docker",
    "search",
]


Operation = Literal["read", "write", "destructive", "admin"]


VALID_TOOL_PREFIXES: Tuple[str, ...] = (
    "get_",
    "list_",
    "search_",
    "create_",
    "update_",
    "delete_",
    "submit_",
    "check_",
    "validate_",
    "register_",
)


DEFAULT_READ_ANNOTATIONS: Dict[str, bool] = {
    "readOnlyHint": True,
    "idempotentHint": True,
    "destructiveHint": False,
    "openWorldHint": True,
}


DEFAULT_WRITE_ANNOTATIONS: Dict[str, bool] = {
    "readOnlyHint": False,
    "idempotentHint": False,
    "destructiveHint": False,
    "openWorldHint": True,
}


DEFAULT_DESTRUCTIVE_ANNOTATIONS: Dict[str, bool] = {
    "readOnlyHint": False,
    "idempotentHint": False,
    "destructiveHint": True,
    "openWorldHint": True,
}


def _first_sentence(text: str) -> str:
    """Return the first sentence of ``text`` (up to the first period+space)."""
    for sep in (". ", ".\n", ".\t"):
        if sep in text:
            return text.split(sep, 1)[0].strip() + "."
    return text.strip()


def _synapse_object_forms(obj: str) -> Tuple[str, ...]:
    """Return accepted first-sentence forms of a Synapse object phrase.

    Returns the full lowercase phrase and the head noun (last alphabetic
    word) in both singular and plural forms. The head-noun match is
    what typically appears in natural descriptions — e.g. for
    ``"Synapse submission"`` the description may read
    "every submission...", which should match.
    """
    lo = obj.lower().strip()
    if not lo:
        return ()
    words = re.findall(r"[a-z]+", lo)
    if not words:
        return ()
    head = words[-1]
    if head.endswith("y"):
        plural = head[:-1] + "ies"
    elif head.endswith("s"):
        plural = head
    else:
        plural = head + "s"
    forms = {head, plural, lo}
    return tuple(forms)


def _tags_for(service: ServiceName, operation: Operation) -> frozenset:
    """Compute the Visibility-transform tag set for a given service/operation.

    Includes alias tags (``readonly``, ``mutation``, ``destructive``,
    ``admin``) so a single Visibility rule can target a broad category
    without listing every specific service name.
    """
    tags = {service, operation}
    if operation == "read":
        tags.add("readonly")
    if operation in ("write", "destructive"):
        tags.add("mutation")
    if operation == "destructive":
        tags.add("destructive")
    if operation == "admin":
        tags.add("admin")
    return frozenset(tags)


def _build_extended_description(
    description: str,
    synonyms: Iterable[str],
    siblings: Iterable[str],
) -> str:
    """Append ``Related terms:`` and ``Distinct from:`` sections.

    Separated from the primary description with a blank line so a human
    reader sees the core copy first, but BM25 tokenises the whole
    string and still indexes the synonyms / sibling names.
    """
    parts = [description]
    syn_list = list(synonyms)
    sib_list = list(siblings)
    if syn_list:
        parts.append("Related terms: " + ", ".join(syn_list))
    if sib_list:
        parts.append("Distinct from: " + ", ".join(sib_list))
    return "\n\n".join(parts)


def _default_annotations_for(operation: Operation) -> Dict[str, bool]:
    """Pick the MCP annotation set that best matches the operation kind."""
    if operation == "read":
        return DEFAULT_READ_ANNOTATIONS
    if operation == "destructive":
        return DEFAULT_DESTRUCTIVE_ANNOTATIONS
    return DEFAULT_WRITE_ANNOTATIONS


def _tool_exception_to_error(exc: Exception) -> Dict[str, Any]:
    """Convert an exception raised inside a tool wrapper into the standard
    error dict shape (``error``, ``error_type``, optional ``status_code``).
    """
    if isinstance(exc, ConnectionAuthError):
        return {
            "error": f"Authentication required: {exc}",
            "error_type": type(exc).__name__,
        }
    err: Dict[str, Any] = {
        "error": str(exc),
        "error_type": type(exc).__name__,
    }
    response = getattr(exc, "response", None)
    if response is not None:
        status_code = getattr(response, "status_code", None)
        if status_code is not None:
            err["status_code"] = status_code
    return err


def service_tool(
    mcp,
    *,
    service: ServiceName,
    operation: Operation,
    synapse_object: str,
    title: str,
    description: str,
    synonyms: Iterable[str] = (),
    siblings: Iterable[str] = (),
    annotations: Optional[Dict[str, Any]] = None,
) -> Callable:
    """Register a Synapse MCP tool with enforced naming and tagging.

    Wraps ``@mcp.tool(...)`` with registration-time validation and
    consistent metadata (tags, annotations, synonym and sibling lists
    for BM25 recall and LLM disambiguation).

    Arguments:
        mcp: The FastMCP server instance to register with.
        service: Which Synapse service this tool exposes.
        operation: One of read / write / destructive / admin.
        synapse_object: The concrete Synapse object type the tool
            operates on (e.g. ``"Synapse entity"``, ``"Evaluation queue"``).
            Must appear in the first sentence of ``description``.
        title: Human-readable title (shown in some MCP clients).
        description: LLM-visible description. First sentence should
            follow the pattern "Use this when <user intent>.
            <Synapse object> is <one-line definition>." and must name
            ``synapse_object``.
        synonyms: Common user-language aliases for the Synapse terms
            in this tool (e.g. ``("lineage", "history")`` for
            provenance). Appended to the description so the BM25
            index matches them, without polluting the primary copy.
        siblings: Names of closely-related tools. Appended as a
            "Distinct from:" line so the LLM sees the disambiguation.
        annotations: Override for MCP tool annotations. When omitted,
            defaults are chosen based on ``operation``.

    Raises:
        ValueError at registration time if the tool name does not use
            an approved verb prefix, or if the first sentence of
            ``description`` does not name ``synapse_object``.
    """

    def decorator(fn: Callable) -> Callable:
        if not any(fn.__name__.startswith(p) for p in VALID_TOOL_PREFIXES):
            raise ValueError(
                f"Tool '{fn.__name__}' must start with one of "
                f"{VALID_TOOL_PREFIXES}"
            )

        first = _first_sentence(description).lower()
        forms = _synapse_object_forms(synapse_object)
        if not any(f in first for f in forms):
            raise ValueError(
                f"Tool '{fn.__name__}' description first sentence must "
                f"name the Synapse object '{synapse_object}' (or its "
                f"plural). First sentence was: "
                f"'{_first_sentence(description)}'"
            )

        extended = _build_extended_description(
            description, synonyms, siblings
        )
        tags = _tags_for(service, operation)
        resolved_annotations = (
            annotations
            if annotations is not None
            else _default_annotations_for(operation)
        )

        @functools.wraps(fn)
        async def wrapped(*args: Any, **kwargs: Any) -> Any:
            try:
                return await fn(*args, **kwargs)
            except Exception as exc:
                return _tool_exception_to_error(exc)

        return mcp.tool(
            title=title,
            description=extended,
            tags=tags,
            annotations=resolved_annotations,
        )(wrapped)

    return decorator
