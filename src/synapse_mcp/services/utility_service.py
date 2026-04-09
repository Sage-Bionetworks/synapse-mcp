"""Service layer for 4.12.0 utility operations."""

from typing import Any, Dict

from fastmcp import Context
from synapseclient.operations import find_entity_id, is_synapse_id, md5_query

from .tool_service import (
    error_boundary,
    serialize_model,
    synapse_client,
)


class UtilityService:
    """Orchestrates utility read operations."""

    @error_boundary(error_context_keys=("name",))
    def find_entity_id(
        self,
        ctx: Context,
        name: str,
        parent_id: str = None,
    ) -> Dict[str, Any]:
        """Find a Synapse entity ID by name and parent.

        Arguments:
            ctx: The FastMCP request context.
            name: Entity name to search for.
            parent_id: Optional parent container ID.

        Returns:
            Dict with the found entity_id, or an error
            if not found.
        """
        with synapse_client(ctx) as client:
            entity_id = find_entity_id(
                name=name,
                parent=parent_id,
                synapse_client=client,
            )
            return {
                "entity_id": entity_id,
                "name": name,
                "parent_id": parent_id,
            }

    @error_boundary(error_context_keys=("syn_id",))
    def is_synapse_id(
        self, ctx: Context, syn_id: str
    ) -> Dict[str, Any]:
        """Check whether a Synapse ID exists.

        Arguments:
            ctx: The FastMCP request context.
            syn_id: Synapse ID to validate (e.g. ``"syn123"``).

        Returns:
            Dict with syn_id and is_valid boolean.
        """
        with synapse_client(ctx) as client:
            valid = is_synapse_id(
                syn_id=syn_id,
                synapse_client=client,
            )
            return {
                "syn_id": syn_id,
                "is_valid": valid,
            }

    @error_boundary(error_context_keys=("md5",))
    def md5_query(
        self, ctx: Context, md5: str
    ) -> Dict[str, Any]:
        """Find entities by MD5 hash of their file.

        Arguments:
            ctx: The FastMCP request context.
            md5: MD5 hash string.

        Returns:
            Dict with md5 and a results list of matching
            entities.
        """
        with synapse_client(ctx) as client:
            results = md5_query(
                md5=md5,
                synapse_client=client,
            )
            return {
                "md5": md5,
                "results": serialize_model(results),
            }
