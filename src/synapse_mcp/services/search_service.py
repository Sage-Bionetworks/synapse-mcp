"""Service layer for Synapse search operations."""

import json
from typing import Any, Dict, List, Optional

from fastmcp import Context

from .tool_service import error_boundary, synapse_client


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


class SearchService:
    """Orchestrates Synapse search operations."""

    @error_boundary()
    def search(
        self,
        ctx: Context,
        query_term: Optional[str] = None,
        name: Optional[str] = None,
        entity_type: Optional[str] = None,
        entity_types: Optional[List[str]] = None,
        parent_id: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """Search Synapse entities using keyword queries.

        Arguments:
            ctx: The FastMCP request context.
            query_term: Keyword search term.
            name: Entity name filter (also added to
                query terms if not already present).
            entity_type: Single entity type filter
                (e.g. ``"project"``).
            entity_types: List of entity type filters.
            parent_id: Synapse ID to scope search under.
            limit: Max results (1--100, default 20).
            offset: Pagination offset (default 0).

        Returns:
            Dict with found count, start offset, hits
            list, facets, and the query payload used.
        """
        with synapse_client(ctx) as client:
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

            if default_return_fields:
                request_payload["returnFields"] = default_return_fields

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
                response = client.restPOST(
                    "/search", body=json.dumps(request_payload)
                )
            except Exception as exc:
                error_message = str(exc)
                if (
                    "Invalid field name" in error_message
                    and "returnFields" in request_payload
                ):
                    original_payload = dict(request_payload)
                    dropped_return_fields = list(
                        request_payload.get("returnFields", [])
                    )
                    fallback_payload = {
                        k: v
                        for k, v in request_payload.items()
                        if k != "returnFields"
                    }
                    response = client.restPOST(
                        "/search", body=json.dumps(fallback_payload)
                    )
                    warnings.append(
                        f"Synapse rejected requested return fields "
                        f"{dropped_return_fields}; retried without custom "
                        f"return fields."
                    )
                    request_payload = fallback_payload
                else:
                    raise

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
