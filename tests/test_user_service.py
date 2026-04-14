"""Tests for UserService."""

from dataclasses import dataclass
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch

from synapse_mcp.connection_auth import ConnectionAuthError
from synapse_mcp.services.user_service import UserService

import pytest

pytestmark = pytest.mark.anyio("asyncio")


@pytest.fixture
def anyio_backend():
    return "asyncio"


TS = "synapse_mcp.services.tool_service"
SVC = "synapse_mcp.services.user_service"


@dataclass
class FakeUserProfile:
    id: int = 12345
    username: str = "jsmith"
    first_name: str = "Jane"
    last_name: str = "Smith"
    email: Optional[str] = "jane@example.com"
    etag: str = "abc"
    created_on: str = "2025-01-01"


class TestGetUserProfile:
    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.UserProfile")
    async def test_given_user_id_when_fetched_then_returns_dict(
        self, mock_up_cls, mock_get_client
    ):
        # GIVEN a user profile found by ID
        mock_get_client.return_value = MagicMock()
        mock_up_cls.from_id_async = AsyncMock(
            return_value=FakeUserProfile()
        )

        # WHEN we get the profile by user ID
        result = await UserService().get_user_profile(
            MagicMock(), user_id=12345
        )

        # THEN the profile fields are returned
        assert result["id"] == 12345
        assert result["username"] == "jsmith"
        assert result["first_name"] == "Jane"
        mock_up_cls.from_id_async.assert_called_once()

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.UserProfile")
    async def test_given_username_when_fetched_then_uses_from_username(
        self, mock_up_cls, mock_get_client
    ):
        # GIVEN a user profile found by username
        mock_get_client.return_value = MagicMock()
        mock_up_cls.from_username_async = AsyncMock(
            return_value=FakeUserProfile(username="jdoe")
        )

        # WHEN we get the profile by username
        result = await UserService().get_user_profile(
            MagicMock(), username="jdoe"
        )

        # THEN the correct SDK method is called
        assert result["username"] == "jdoe"
        mock_up_cls.from_username_async.assert_called_once()

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.UserProfile")
    async def test_given_no_args_when_fetched_then_returns_self(
        self, mock_up_cls, mock_get_client
    ):
        # GIVEN no user_id or username (self-lookup)
        mock_get_client.return_value = MagicMock()
        mock_up_cls.return_value.get_async = AsyncMock(
            return_value=FakeUserProfile(username="me")
        )

        # WHEN we get the profile with no args
        result = await UserService().get_user_profile(
            MagicMock()
        )

        # THEN it returns the current user's profile
        assert result["username"] == "me"
        mock_up_cls.return_value.get_async.assert_called_once()

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    async def test_given_expired_auth_then_returns_error(
        self, mock_get_client
    ):
        # GIVEN expired credentials
        mock_get_client.side_effect = ConnectionAuthError(
            "expired"
        )

        # WHEN we get a profile
        result = await UserService().get_user_profile(
            MagicMock(), user_id=12345
        )

        # THEN an auth error is returned
        assert "Authentication required" in result["error"]
