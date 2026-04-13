"""Tests for search_synapse tool via SearchService."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from synapse_mcp.connection_auth import ConnectionAuthError
from synapse_mcp.services.search_service import (
    DEFAULT_RETURN_FIELDS,
    SearchService,
)

pytestmark = pytest.mark.anyio("asyncio")


@pytest.fixture
def anyio_backend():
    return "asyncio"


TS = "synapse_mcp.services.tool_service"
SVC = "synapse_mcp.services.search_service"


class TestSearchService:
    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    async def test_given_search_params_when_searching_then_builds_correct_payload(
        self, mock_get_client
    ):
        # GIVEN a Synapse client that captures the search request
        captured = {}

        class FakeClient:
            async def rest_post_async(self, path, body):
                captured["path"] = path
                captured["body"] = json.loads(body)
                return {
                    "found": 1,
                    "start": 0,
                    "hits": [
                        {"id": "syn999", "name": "Cancer Study", "node_type": "project"}
                    ],
                    "facets": [],
                }

        mock_get_client.return_value = FakeClient()

        # WHEN we search with various filters
        result = await SearchService().search(
            MagicMock(),
            query_term="Cancer",
            name="Cancer",
            entity_type="Project",
            parent_id="syn123",
            limit=5,
            offset=2,
        )

        # THEN the payload is built correctly
        assert captured["path"] == "/search"
        payload = captured["body"]
        assert payload["queryTerm"] == ["Cancer"]
        assert payload["start"] == 2
        assert payload["size"] == 5
        assert payload["returnFields"] == ["name", "description", "node_type"]
        assert {"key": "node_type", "value": "project"} in payload["booleanQuery"]
        assert {"key": "path", "value": "syn123"} in payload["booleanQuery"]
        assert result["hits"][0]["id"] == "syn999"

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    async def test_given_invalid_return_fields_when_searching_then_retries_without_fields(
        self, mock_get_client
    ):
        # GIVEN a client that rejects return fields on first call
        class FakeClient:
            def __init__(self):
                self.calls = 0

            async def rest_post_async(self, path, body):
                self.calls += 1
                if self.calls == 1:
                    raise Exception(
                        "Invalid field name 'id' in return parameter"
                    )
                return {"found": 0, "start": 0, "hits": [], "facets": []}

        mock_get_client.return_value = FakeClient()

        # WHEN we search
        result = await SearchService().search(MagicMock())

        # THEN the result includes warnings about dropped fields
        assert result["original_query"]["returnFields"] == DEFAULT_RETURN_FIELDS
        assert result["dropped_return_fields"] == DEFAULT_RETURN_FIELDS
        assert result["warnings"]

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    async def test_given_expired_auth_when_searching_then_returns_error_dict(
        self, mock_get_client
    ):
        # GIVEN expired credentials
        mock_get_client.side_effect = ConnectionAuthError("missing context")

        # WHEN we search
        result = await SearchService().search(MagicMock())

        # THEN an auth error is returned
        assert "error" in result
        assert "Authentication required" in result["error"]
