"""Service layer for Activity (provenance) operations."""

from typing import Any, Dict, Optional

from fastmcp import Context
from synapseclient.models import Activity

from .tool_service import error_boundary, serialize_model, synapse_client


class ActivityService:
    """Orchestrates provenance/activity read operations."""

    @staticmethod
    @error_boundary(
        error_context_keys=("entity_id", "activity_id"),
    )
    async def get_provenance(
        ctx: Context,
        entity_id: Optional[str] = None,
        version: Optional[int] = None,
        activity_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get provenance (Activity) for an entity or by activity ID.

        Provenance and Activity refer to the same Synapse concept — the
        record describing what produced an entity (used inputs, executed
        code, etc.). Either provide ``entity_id`` (with optional
        ``version``) to look up by parent entity, or ``activity_id`` to
        look up the Activity directly.

        Arguments:
            ctx: The FastMCP request context.
            entity_id: Synapse ID (e.g. ``"syn123"``). Mutually
                exclusive with ``activity_id``.
            version: Optional entity version number; only meaningful
                when ``entity_id`` is provided.
            activity_id: Numeric Activity ID for direct lookup.

        Returns:
            Dict with provenance/activity metadata. Returns an error
            dict if neither selector is provided or no record exists.
        """
        if not entity_id and not activity_id:
            return {
                "error": (
                    "Either entity_id or activity_id is required"
                ),
            }
        async with synapse_client(ctx) as client:
            activity = await Activity.get_async(
                activity_id=activity_id,
                parent_id=entity_id,
                parent_version_number=version,
                synapse_client=client,
            )
            if activity is None:
                return {
                    "error": (
                        "No provenance record found"
                        f" for {entity_id or activity_id}"
                    ),
                    "entity_id": entity_id,
                    "activity_id": activity_id,
                    "version": version,
                }
            result: Dict[str, Any] = {
                "activity": serialize_model(activity),
            }
            if entity_id is not None:
                result["entity_id"] = entity_id
            if activity_id is not None:
                result["activity_id"] = activity_id
            if version is not None:
                result["version"] = version
            return result
