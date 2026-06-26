"""Tests for UtilityService."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from synapse_mcp.connection_auth import ConnectionAuthError
from synapse_mcp.services.utility_service import UtilityService

pytestmark = pytest.mark.anyio("asyncio")


@pytest.fixture
def anyio_backend():
    return "asyncio"


TS = "synapse_mcp.services.tool_service"
SVC = "synapse_mcp.services.utility_service"


class TestFindEntityId:
    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.find_entity_id_async", new_callable=AsyncMock)
    async def test_given_name_and_parent_then_returns_entity_id(
        self, mock_find, mock_get_client
    ):
        mock_get_client.return_value = MagicMock()
        mock_find.return_value = "syn555"

        result = await UtilityService().find_entity_id(
            MagicMock(), name="sample.csv", parent_id="syn100"
        )

        assert result == {
            "entity_id": "syn555",
            "name": "sample.csv",
            "parent_id": "syn100",
        }
        mock_find.assert_called_once()
        call_kwargs = mock_find.call_args[1]
        assert call_kwargs["name"] == "sample.csv"
        assert call_kwargs["parent"] == "syn100"

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.find_entity_id_async", new_callable=AsyncMock)
    async def test_given_name_not_found_then_returns_none_entity_id(
        self, mock_find, mock_get_client
    ):
        mock_get_client.return_value = MagicMock()
        mock_find.return_value = None

        result = await UtilityService().find_entity_id(
            MagicMock(), name="missing", parent_id="syn100"
        )

        assert result["entity_id"] is None

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    async def test_given_expired_auth_then_returns_error(
        self, mock_get_client
    ):
        mock_get_client.side_effect = ConnectionAuthError("expired")

        result = await UtilityService().find_entity_id(
            MagicMock(), name="x"
        )

        assert "Authentication required" in result["error"]
        assert result["name"] == "x"


class TestIsSynapseId:
    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.is_synapse_id_async", new_callable=AsyncMock)
    async def test_given_valid_id_then_returns_true(
        self, mock_check, mock_get_client
    ):
        mock_get_client.return_value = MagicMock()
        mock_check.return_value = True

        result = await UtilityService().is_synapse_id(
            MagicMock(), "syn123"
        )

        assert result == {"syn_id": "syn123", "is_valid": True}

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.is_synapse_id_async", new_callable=AsyncMock)
    async def test_given_invalid_id_then_returns_false(
        self, mock_check, mock_get_client
    ):
        mock_get_client.return_value = MagicMock()
        mock_check.return_value = False

        result = await UtilityService().is_synapse_id(
            MagicMock(), "nope"
        )

        assert result == {"syn_id": "nope", "is_valid": False}

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    async def test_given_expired_auth_then_returns_error(
        self, mock_get_client
    ):
        mock_get_client.side_effect = ConnectionAuthError("expired")

        result = await UtilityService().is_synapse_id(MagicMock(), "syn1")

        assert "Authentication required" in result["error"]
        assert result["syn_id"] == "syn1"


class TestMd5Query:
    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.md5_query_async", new_callable=AsyncMock)
    async def test_given_md5_then_returns_results(
        self, mock_md5, mock_get_client
    ):
        mock_get_client.return_value = MagicMock()
        mock_md5.return_value = [
            {"id": "syn1", "versionNumber": 2},
            {"id": "syn2", "versionNumber": 1},
        ]

        result = await UtilityService().md5_query(
            MagicMock(), "9e107d9d372bb6826bd81d3542a419d6"
        )

        assert result["md5"] == "9e107d9d372bb6826bd81d3542a419d6"
        assert len(result["results"]) == 2

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    async def test_given_expired_auth_then_returns_error(
        self, mock_get_client
    ):
        mock_get_client.side_effect = ConnectionAuthError("expired")

        result = await UtilityService().md5_query(MagicMock(), "abc")

        assert "Authentication required" in result["error"]
        assert result["md5"] == "abc"
