"""Service layer for Team operations."""

from typing import Any, Dict, List, Optional

from fastmcp import Context
from synapseclient.models import Team

from .tool_service import error_boundary, serialize_model, synapse_client


class TeamService:
    """Orchestrates team read operations."""

    @error_boundary(error_context_keys=("team_id", "team_name"))
    def get_team(
        self,
        ctx: Context,
        team_id: Optional[int] = None,
        team_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get a Team by numeric ID or by name.

        Arguments:
            ctx: The FastMCP request context.
            team_id: Numeric team ID. Mutually exclusive
                with team_name.
            team_name: Team name string. Mutually exclusive
                with team_id.

        Returns:
            Dict with team metadata (id, name, description,
            can_public_join, can_request_membership, etc.).
            Returns an error dict if neither argument is
            provided.
        """
        with synapse_client(ctx) as client:
            if team_id is not None:
                team = Team.from_id(
                    id=team_id, synapse_client=client
                )
            elif team_name is not None:
                team = Team.from_name(
                    name=team_name, synapse_client=client
                )
            else:
                return {
                    "error": (
                        "Either team_id or team_name"
                        " is required"
                    )
                }
            return serialize_model(team)

    @error_boundary(
        error_context_keys=("team_id",),
        wrap_errors=list,
    )
    def get_team_members(
        self, ctx: Context, team_id: int
    ) -> List[Dict[str, Any]]:
        """List all members of a Team.

        Arguments:
            ctx: The FastMCP request context.
            team_id: Numeric team ID.

        Returns:
            List of team member dicts.
        """
        with synapse_client(ctx) as client:
            team = Team(id=team_id)
            members = team.members(
                synapse_client=client,
            )
            return [serialize_model(m) for m in members]

    @error_boundary(
        error_context_keys=("team_id",),
        wrap_errors=list,
    )
    def get_team_open_invitations(
        self, ctx: Context, team_id: int
    ) -> List[Dict[str, Any]]:
        """List pending invitations for a Team.

        Arguments:
            ctx: The FastMCP request context.
            team_id: Numeric team ID.

        Returns:
            List of invitation dicts.
        """
        with synapse_client(ctx) as client:
            team = Team(id=team_id)
            invitations = team.open_invitations(
                synapse_client=client,
            )
            return [
                serialize_model(i) for i in invitations
            ]

    @error_boundary(error_context_keys=("team_id",))
    def get_team_membership_status(
        self,
        ctx: Context,
        team_id: int,
        user_id: str,
    ) -> Dict[str, Any]:
        """Check a user's membership status in a Team.

        Arguments:
            ctx: The FastMCP request context.
            team_id: Numeric team ID.
            user_id: Synapse user ID string.

        Returns:
            Dict with membership status flags
            (is_member, has_open_invitation, etc.).
        """
        with synapse_client(ctx) as client:
            team = Team(id=team_id)
            status = team.get_user_membership_status(
                user_id=user_id,
                synapse_client=client,
            )
            return serialize_model(status)
