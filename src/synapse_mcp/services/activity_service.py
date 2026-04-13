"""Service layer for Activity (provenance) operations."""

from typing import Any, Dict, Optional

from fastmcp import Context
from synapseclient.models import Activity

from .tool_service import error_boundary, serialize_model, synapse_client


class ActivityService:
    """Orchestrates provenance/activity read operations."""

    @error_boundary(error_context_keys=("entity_id",))
    async def get_provenance(
        self,
        ctx: Context,
        entity_id: str,
        version: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Get provenance for an entity.

        Arguments:
            ctx: The FastMCP request context.
            entity_id: Synapse ID (e.g. ``"syn123"``).
            version: Optional entity version number.

        Returns:
            Dict with entity_id and an activity dict
            containing provenance metadata (used entities,
            executed code, etc.). Returns an error dict if
            no provenance exists.
        """
        async with synapse_client(ctx) as client:
            activity = await Activity.get_async(
                parent_id=entity_id,
                parent_version_number=version,
                synapse_client=client,
            )
            if activity is None:
                return {
                    "error": (
                        "No provenance record found"
                        f" for {entity_id}"
                    ),
                    "entity_id": entity_id,
                    "version": version,
                }
            result: Dict[str, Any] = {
                "entity_id": entity_id,
                "activity": serialize_model(activity),
            }
            if version is not None:
                result["version"] = version
            return result

    @error_boundary(
        error_context_keys=(
            "activity_id",
            "parent_id",
        )
    )
    async def get_activity(
        self,
        ctx: Context,
        activity_id: Optional[str] = None,
        parent_id: Optional[str] = None,
        parent_version_number: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Get an Activity by its own ID or by parent.

        Arguments:
            ctx: The FastMCP request context.
            activity_id: Activity ID (direct lookup).
            parent_id: Synapse entity ID whose provenance
                to retrieve.
            parent_version_number: Optional entity version.

        Returns:
            Dict with activity metadata.
        """
        async with synapse_client(ctx) as client:
            activity = await Activity.get_async(
                activity_id=activity_id,
                parent_id=parent_id,
                parent_version_number=parent_version_number,
                synapse_client=client,
            )
            if activity is None:
                return {
                    "error": "No activity found",
                    "activity_id": activity_id,
                    "parent_id": parent_id,
                }
            return serialize_model(activity)
