"""Service layer for Team operations."""

from typing import Any, Dict, List, Optional

from fastmcp import Context
from synapseclient.models import Team

from .tool_service import error_boundary, serialize_model, synapse_client


class TeamService:
    """Orchestrates team read operations."""

    @error_boundary(error_context_keys=("team_id", "team_name"))
    async def get_team(
        self,
        ctx: Context,
        team_id: Optional[int] = None,
        team_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get a Team by numeric ID or by name.

        Exactly one of ``team_id`` or ``team_name`` must be
        provided. If both are supplied, ``team_id`` takes
        precedence.

        Arguments:
            ctx: The FastMCP request context.
            team_id: Numeric team ID. If provided, ``team_name``
                is ignored.
            team_name: Team name string. Only consulted when
                ``team_id`` is not provided.

        Returns:
            Dict with team metadata (id, name, description,
            can_public_join, can_request_membership, etc.).
            Returns an error dict if neither argument is
            provided.
        """
        # Validate inputs before opening the auth'd client so a
        # misuse doesn't surface as an authentication error.
        if team_id is None and team_name is None:
            return {
                "error": (
                    "Either team_id or team_name"
                    " is required"
                )
            }
        async with synapse_client(ctx) as client:
            if team_id is not None:
                team = await Team.from_id_async(
                    id=team_id, synapse_client=client
                )
            else:
                team = await Team.from_name_async(
                    name=team_name, synapse_client=client
                )
            return serialize_model(team)

    @error_boundary(
        error_context_keys=("team_id",),
        wrap_errors=True,
    )
    async def get_team_members(
        self,
        ctx: Context,
        team_id: int,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """List members of a Team.

        Note: ``Team.members_async`` collects every page from
        the Synapse API before returning, so fetch cost scales
        with the full team size regardless of ``limit``. The
        ``limit`` slices the final list to bound response size
        sent back to the LLM.

        Arguments:
            ctx: The FastMCP request context.
            team_id: Numeric team ID.
            limit: If provided, must be non-negative; returns
                at most this many members.

        Returns:
            List of team member dicts.
        """
        if limit is not None and limit < 0:
            raise ValueError("limit must be >= 0")
        async with synapse_client(ctx) as client:
            team = Team(id=team_id)
            members = await team.members_async(
                synapse_client=client,
            )
            if limit is not None:
                members = members[:limit]
            return [serialize_model(m) for m in members]

    @error_boundary(
        error_context_keys=("team_id",),
        wrap_errors=True,
    )
    async def get_team_open_invitations(
        self,
        ctx: Context,
        team_id: int,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """List pending invitations for a Team.

        Note: ``Team.open_invitations_async`` collects every
        page from the Synapse API before returning. ``limit``
        slices the final list but does not reduce API cost.

        Arguments:
            ctx: The FastMCP request context.
            team_id: Numeric team ID.
            limit: If provided, must be non-negative; returns
                at most this many invitations.

        Returns:
            List of invitation dicts.
        """
        if limit is not None and limit < 0:
            raise ValueError("limit must be >= 0")
        async with synapse_client(ctx) as client:
            team = Team(id=team_id)
            invitations = await team.open_invitations_async(
                synapse_client=client,
            )
            if limit is not None:
                invitations = invitations[:limit]
            return [
                serialize_model(i) for i in invitations
            ]

    @error_boundary(error_context_keys=("team_id",))
    async def get_team_membership_status(
        self,
        ctx: Context,
        team_id: int,
        user_id: int,
    ) -> Dict[str, Any]:
        """Check a user's membership status in a Team.

        Arguments:
            ctx: The FastMCP request context.
            team_id: Numeric team ID.
            user_id: Numeric Synapse user ID.

        Returns:
            Dict with membership status flags
            (is_member, has_open_invitation, etc.).
        """
        async with synapse_client(ctx) as client:
            team = Team(id=team_id)
            status = await team.get_user_membership_status_async(
                user_id=user_id,
                synapse_client=client,
            )
            return serialize_model(status)
