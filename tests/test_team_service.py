"""Tests for TeamService."""

from dataclasses import dataclass
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch

from synapse_mcp.connection_auth import ConnectionAuthError
from synapse_mcp.services.team_service import TeamService

import pytest

pytestmark = pytest.mark.anyio("asyncio")


@pytest.fixture
def anyio_backend():
    return "asyncio"


TS = "synapse_mcp.services.tool_service"
SVC = "synapse_mcp.services.team_service"


@dataclass
class FakeTeam:
    id: int = 100
    name: str = "Data Science"
    description: str = "The data science team"
    etag: str = "abc"
    created_on: str = "2025-01-01"
    modified_on: str = "2025-01-02"
    created_by: str = "user1"
    icon: Optional[str] = None
    can_public_join: bool = False
    can_request_membership: bool = True


class TestGetTeam:
    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.Team")
    async def test_given_team_id_when_fetched_then_returns_dict(
        self, mock_team_cls, mock_get_client
    ):
        # GIVEN a team with ID 100
        mock_get_client.return_value = MagicMock()
        mock_team_cls.from_id_async = AsyncMock(return_value=FakeTeam())

        # WHEN we get the team by ID
        result = await TeamService().get_team(
            MagicMock(), team_id=100
        )

        # THEN the team metadata is returned
        assert result["id"] == 100
        assert result["name"] == "Data Science"
        assert result["can_request_membership"] is True

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.Team")
    async def test_given_team_name_when_fetched_then_uses_from_name(
        self, mock_team_cls, mock_get_client
    ):
        # GIVEN a team found by name
        mock_get_client.return_value = MagicMock()
        mock_team_cls.from_name_async = AsyncMock(
            return_value=FakeTeam(name="ML Team")
        )

        # WHEN we get the team by name
        result = await TeamService().get_team(
            MagicMock(), team_name="ML Team"
        )

        # THEN the correct SDK method is called
        assert result["name"] == "ML Team"
        mock_team_cls.from_name_async.assert_called_once()

    async def test_given_no_id_or_name_then_returns_error(self):
        # GIVEN no team_id or team_name
        # WHEN we get a team with no identifiers
        result = await TeamService().get_team(MagicMock())

        # THEN an error is returned
        assert "required" in result["error"]

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    async def test_given_expired_auth_then_returns_error(
        self, mock_get_client
    ):
        # GIVEN expired credentials
        mock_get_client.side_effect = ConnectionAuthError(
            "expired"
        )

        # WHEN we get a team
        result = await TeamService().get_team(
            MagicMock(), team_id=100
        )

        # THEN an auth error is returned
        assert "Authentication required" in result["error"]


@dataclass
class FakeMember:
    team_id: int = 100
    member_id: int = 1
    is_admin: bool = False


class TestGetTeamMembers:
    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.Team")
    async def test_given_team_when_listed_then_returns_members(
        self, mock_team_cls, mock_get_client
    ):
        mock_get_client.return_value = MagicMock()
        instance = mock_team_cls.return_value
        instance.members_async = AsyncMock(
            return_value=[FakeMember(member_id=1), FakeMember(member_id=2)]
        )

        result = await TeamService().get_team_members(MagicMock(), 100)

        assert isinstance(result, list)
        assert [m["member_id"] for m in result] == [1, 2]

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.Team")
    async def test_given_empty_team_when_listed_then_returns_empty_list(
        self, mock_team_cls, mock_get_client
    ):
        mock_get_client.return_value = MagicMock()
        instance = mock_team_cls.return_value
        instance.members_async = AsyncMock(return_value=[])

        result = await TeamService().get_team_members(MagicMock(), 100)

        assert result == []

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.Team")
    async def test_given_limit_when_listed_then_truncates(
        self, mock_team_cls, mock_get_client
    ):
        mock_get_client.return_value = MagicMock()
        instance = mock_team_cls.return_value
        instance.members_async = AsyncMock(
            return_value=[
                FakeMember(member_id=i) for i in range(5)
            ]
        )

        result = await TeamService().get_team_members(
            MagicMock(), 100, limit=2
        )

        assert len(result) == 2
        assert [m["member_id"] for m in result] == [0, 1]

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    async def test_given_expired_auth_then_returns_wrapped_error(
        self, mock_get_client
    ):
        mock_get_client.side_effect = ConnectionAuthError("expired")

        result = await TeamService().get_team_members(MagicMock(), 100)

        assert isinstance(result, list)
        assert "Authentication required" in result[0]["error"]


@dataclass
class FakeInvitation:
    id: str = "inv1"
    team_id: int = 100
    invitee_id: int = 42


class TestGetTeamOpenInvitations:
    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.Team")
    async def test_given_team_when_listed_then_returns_invitations(
        self, mock_team_cls, mock_get_client
    ):
        mock_get_client.return_value = MagicMock()
        instance = mock_team_cls.return_value
        instance.open_invitations_async = AsyncMock(
            return_value=[FakeInvitation(id="inv1"), FakeInvitation(id="inv2")]
        )

        result = await TeamService().get_team_open_invitations(
            MagicMock(), 100
        )

        assert [i["id"] for i in result] == ["inv1", "inv2"]

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.Team")
    async def test_given_limit_when_listed_then_truncates(
        self, mock_team_cls, mock_get_client
    ):
        mock_get_client.return_value = MagicMock()
        instance = mock_team_cls.return_value
        instance.open_invitations_async = AsyncMock(
            return_value=[FakeInvitation(id=f"inv{i}") for i in range(4)]
        )

        result = await TeamService().get_team_open_invitations(
            MagicMock(), 100, limit=1
        )

        assert len(result) == 1
        assert result[0]["id"] == "inv0"

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    async def test_given_expired_auth_then_returns_wrapped_error(
        self, mock_get_client
    ):
        mock_get_client.side_effect = ConnectionAuthError("expired")

        result = await TeamService().get_team_open_invitations(
            MagicMock(), 100
        )

        assert isinstance(result, list)
        assert "Authentication required" in result[0]["error"]


@dataclass
class FakeMembershipStatus:
    team_id: int = 100
    user_id: int = 42
    is_member: bool = True
    has_open_invitation: bool = False


class TestGetTeamMembershipStatus:
    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.Team")
    async def test_given_user_when_status_requested_then_returns_dict(
        self, mock_team_cls, mock_get_client
    ):
        mock_get_client.return_value = MagicMock()
        instance = mock_team_cls.return_value
        instance.get_user_membership_status_async = AsyncMock(
            return_value=FakeMembershipStatus()
        )

        result = await TeamService().get_team_membership_status(
            MagicMock(), 100, 42
        )

        assert result["is_member"] is True
        assert result["has_open_invitation"] is False

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    async def test_given_expired_auth_then_returns_error(
        self, mock_get_client
    ):
        mock_get_client.side_effect = ConnectionAuthError("expired")

        result = await TeamService().get_team_membership_status(
            MagicMock(), 100, 42
        )

        assert "Authentication required" in result["error"]
