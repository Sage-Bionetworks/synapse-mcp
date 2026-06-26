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
    @patch(f"{SVC}.rest_get_paginated_async")
    async def test_given_team_when_listed_then_paginates_with_limit_offset(
        self, mock_paginate, mock_get_client
    ):
        # GIVEN the team-members endpoint will yield two members
        mock_get_client.return_value = MagicMock()
        captured = {}

        async def _fake(uri, *, limit, offset, synapse_client):
            captured["uri"] = uri
            captured["limit"] = limit
            captured["offset"] = offset
            for i in (1, 2):
                # Match the REST shape: teamId/member/isAdmin so
                # TeamMember.fill_from_dict can construct a typed
                # member object.
                yield {
                    "teamId": "100",
                    "member": {"ownerId": str(i), "userName": f"u{i}"},
                    "isAdmin": False,
                }

        mock_paginate.side_effect = _fake

        # WHEN we list members
        result = await TeamService.get_team_members(
            MagicMock(), 100, offset=10, limit=2
        )

        # THEN limit/offset reach the wire and members come back as the
        # same typed shape that Team.members_async would have produced
        # (team_id/member/is_admin keys, not the raw REST camelCase).
        assert captured["uri"] == "/teamMembers/100"
        assert captured["limit"] == 2
        assert captured["offset"] == 10
        assert [m["team_id"] for m in result] == [100, 100]
        assert [m["is_admin"] for m in result] == [False, False]
        assert [m["member"]["owner_id"] for m in result] == ["1", "2"]

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.rest_get_paginated_async")
    async def test_given_empty_team_when_listed_then_returns_empty_list(
        self, mock_paginate, mock_get_client
    ):
        mock_get_client.return_value = MagicMock()

        async def _fake(*args, **kwargs):
            if False:
                yield  # pragma: no cover

        mock_paginate.side_effect = _fake

        result = await TeamService.get_team_members(MagicMock(), 100)

        assert result == []

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.rest_get_paginated_async")
    async def test_given_limit_when_listed_then_caps_results(
        self, mock_paginate, mock_get_client
    ):
        mock_get_client.return_value = MagicMock()

        async def _fake(*args, **kwargs):
            for i in range(5):
                yield {
                    "teamId": "100",
                    "member": {"ownerId": str(i)},
                    "isAdmin": False,
                }

        mock_paginate.side_effect = _fake

        result = await TeamService.get_team_members(
            MagicMock(), 100, limit=2
        )

        assert len(result) == 2
        assert [m["member"]["owner_id"] for m in result] == ["0", "1"]

    async def test_given_negative_limit_then_returns_wrapped_error(self):
        # GIVEN a misuse — negative limit
        # WHEN listing members the service raises and the wrapper catches
        result = await TeamService.get_team_members(
            MagicMock(), 100, limit=-1
        )
        assert isinstance(result, list)
        assert "limit must be" in result[0]["error"]

    async def test_given_zero_limit_then_returns_empty_without_calling_api(self):
        # GIVEN an explicit 0 cap, no API call should fire.
        result = await TeamService.get_team_members(
            MagicMock(), 100, limit=0
        )
        assert result == []

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    async def test_given_expired_auth_then_returns_wrapped_error(
        self, mock_get_client
    ):
        mock_get_client.side_effect = ConnectionAuthError("expired")

        result = await TeamService.get_team_members(MagicMock(), 100)

        assert isinstance(result, list)
        assert "Authentication required" in result[0]["error"]


@dataclass
class FakeInvitation:
    id: str = "inv1"
    team_id: int = 100
    invitee_id: int = 42


class TestGetTeamOpenInvitations:
    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.rest_get_paginated_async")
    async def test_given_team_when_listed_then_paginates_with_limit_offset(
        self, mock_paginate, mock_get_client
    ):
        mock_get_client.return_value = MagicMock()
        captured = {}

        async def _fake(uri, *, limit, offset, synapse_client):
            captured["uri"] = uri
            captured["limit"] = limit
            captured["offset"] = offset
            for invite_id in ("inv1", "inv2"):
                yield {"id": invite_id}

        mock_paginate.side_effect = _fake

        result = await TeamService.get_team_open_invitations(
            MagicMock(), 100, offset=5, limit=2
        )

        assert captured["uri"] == "/team/100/openInvitation"
        assert captured["limit"] == 2
        assert captured["offset"] == 5
        assert [i["id"] for i in result] == ["inv1", "inv2"]

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.rest_get_paginated_async")
    async def test_given_limit_when_listed_then_caps_results(
        self, mock_paginate, mock_get_client
    ):
        mock_get_client.return_value = MagicMock()

        async def _fake(*args, **kwargs):
            for i in range(4):
                yield {"id": f"inv{i}"}

        mock_paginate.side_effect = _fake

        result = await TeamService.get_team_open_invitations(
            MagicMock(), 100, limit=1
        )

        assert len(result) == 1
        assert result[0]["id"] == "inv0"

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    async def test_given_expired_auth_then_returns_wrapped_error(
        self, mock_get_client
    ):
        mock_get_client.side_effect = ConnectionAuthError("expired")

        result = await TeamService.get_team_open_invitations(
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
