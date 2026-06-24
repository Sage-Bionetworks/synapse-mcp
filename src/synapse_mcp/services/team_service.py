"""Service layer for Team operations."""

from typing import Any, Dict, List, Optional

from fastmcp import Context
from synapseclient.api.api_client import rest_get_paginated_async
from synapseclient.models import Team
from synapseclient.models.team import TeamMember

from .tool_service import error_boundary, serialize_model, synapse_client


class TeamService:
    """Orchestrates team read operations."""

    @staticmethod
    @error_boundary(error_context_keys=("team_id", "team_name"))
    async def get_team(
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

    @staticmethod
    @error_boundary(
        error_context_keys=("team_id",),
        wrap_errors=True,
    )
    async def get_team_members(
        ctx: Context,
        team_id: int,
        offset: int = 0,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """List members of a Team.

        Pagination reaches the wire via ``rest_get_paginated_async``
        against ``/teamMembers/{team_id}``: ``limit`` controls the
        page size and acts as the response cap, ``offset`` skips that
        many members from the start of the list. The high-level
        ``Team.members_async`` wrapper is intentionally bypassed
        because it collects every page exhaustively before returning.

        Arguments:
            ctx: The FastMCP request context.
            team_id: Numeric team ID.
            offset: Index of the first member to return (default 0).
            limit: Maximum members to return (default 50). Must be
                non-negative.

        Returns:
            List of team member dicts.
        """
        if limit < 0:
            raise ValueError("limit must be >= 0")
        if offset < 0:
            raise ValueError("offset must be >= 0")
        if limit == 0:
            return []
        async with synapse_client(ctx) as client:
            results: List[Dict[str, Any]] = []
            async for raw in rest_get_paginated_async(
                uri=f"/teamMembers/{team_id}",
                limit=limit,
                offset=offset,
                synapse_client=client,
            ):
                # Mirror the response shape produced by
                # ``Team.members_async``: REST dicts go through
                # ``TeamMember.fill_from_dict`` and then the standard
                # ``serialize_model`` so callers see ``team_id``,
                # ``member``, and ``is_admin`` keys (not the camelCase
                # API representation).
                member = TeamMember().fill_from_dict(
                    synapse_team_member=raw,
                )
                results.append(serialize_model(member))
                if len(results) >= limit:
                    break
            return results

    @staticmethod
    @error_boundary(
        error_context_keys=("team_id",),
        wrap_errors=True,
    )
    async def get_team_open_invitations(
        ctx: Context,
        team_id: int,
        offset: int = 0,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """List pending invitations for a Team.

        Same pagination strategy as ``get_team_members`` — talks to
        ``/team/{team_id}/openInvitation`` directly via
        ``rest_get_paginated_async`` so ``limit``/``offset`` reach
        the REST API rather than slicing a fully-collected list.

        Arguments:
            ctx: The FastMCP request context.
            team_id: Numeric team ID.
            offset: Index of the first invitation to return.
            limit: Maximum invitations to return (default 50).

        Returns:
            List of invitation dicts.
        """
        if limit < 0:
            raise ValueError("limit must be >= 0")
        if offset < 0:
            raise ValueError("offset must be >= 0")
        if limit == 0:
            return []
        async with synapse_client(ctx) as client:
            results: List[Dict[str, Any]] = []
            async for invitation in rest_get_paginated_async(
                uri=f"/team/{team_id}/openInvitation",
                limit=limit,
                offset=offset,
                synapse_client=client,
            ):
                results.append(serialize_model(invitation))
                if len(results) >= limit:
                    break
            return results

    @staticmethod
    @error_boundary(error_context_keys=("team_id",))
    async def get_team_membership_status(
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
