"""Service layer for UserProfile operations."""

from typing import Any, Dict, Optional

from fastmcp import Context
from synapseclient.models import UserProfile

from .tool_service import error_boundary, serialize_model, synapse_client


class UserService:
    """Orchestrates user profile read operations."""

    @error_boundary(error_context_keys=("user_id", "username"))
    async def get_user_profile(
        self,
        ctx: Context,
        user_id: Optional[int] = None,
        username: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get a user profile by ID, username, or self.

        Arguments:
            ctx: The FastMCP request context.
            user_id: Numeric Synapse user ID.
            username: Synapse username string.

        Returns:
            Dict with profile fields (id, username,
            first_name, last_name, email, etc.). When
            neither argument is provided, returns the
            authenticated user's own profile.
        """
        async with synapse_client(ctx) as client:
            if user_id is not None:
                profile = await UserProfile.from_id_async(
                    user_id=user_id,
                    synapse_client=client,
                )
            elif username is not None:
                profile = await UserProfile.from_username_async(
                    username=username,
                    synapse_client=client,
                )
            else:
                profile = await UserProfile().get_async(
                    synapse_client=client,
                )
            return serialize_model(profile)

    @error_boundary(error_context_keys=("user_id",))
    async def is_user_certified(
        self, ctx: Context, user_id: int
    ) -> Dict[str, Any]:
        """Check if a Synapse user is certified.

        Arguments:
            ctx: The FastMCP request context.
            user_id: Numeric Synapse user ID.

        Returns:
            Dict with user_id and is_certified boolean.
        """
        async with synapse_client(ctx) as client:
            profile = UserProfile(id=user_id)
            certified = await profile.is_certified_async(
                synapse_client=client,
            )
            return {
                "user_id": user_id,
                "is_certified": certified,
            }
