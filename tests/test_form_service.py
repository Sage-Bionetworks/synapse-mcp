"""Tests for FormService."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from synapse_mcp.connection_auth import ConnectionAuthError
from synapse_mcp.services.form_service import FormService

pytestmark = pytest.mark.anyio("asyncio")


@pytest.fixture
def anyio_backend():
    return "asyncio"


TS = "synapse_mcp.services.tool_service"


class TestListFormData:
    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    async def test_given_group_id_when_listed_then_returns_one_page_with_token(
        self, mock_get_client
    ):
        # GIVEN /form/data/list returns a page plus a continuation token.
        client = MagicMock()
        client.rest_post_async = AsyncMock(
            return_value={
                "page": [
                    {"formDataId": "fd-1", "submissionStatus": "SUBMITTED"},
                    {"formDataId": "fd-2", "submissionStatus": "ACCEPTED"},
                ],
                "nextPageToken": "fd-tok-2",
            }
        )
        mock_get_client.return_value = client

        # WHEN we list form data for the group
        result = await FormService.list_form_data(
            MagicMock(), group_id="9"
        )

        # THEN we get a single page surfacing the next token, and the
        # request hits the caller-scoped endpoint with no token in body.
        assert result["group_id"] == "9"
        assert result["next_page_token"] == "fd-tok-2"
        assert [r["formDataId"] for r in result["results"]] == ["fd-1", "fd-2"]
        assert client.rest_post_async.call_args.kwargs["uri"] == "/form/data/list"
        body = json.loads(client.rest_post_async.call_args.kwargs["body"])
        assert body == {"groupId": "9", "filterByState": []}

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    async def test_given_filter_and_reviewer_when_listed_then_routes_to_reviewer(
        self, mock_get_client
    ):
        # GIVEN a state filter and reviewer flag
        client = MagicMock()
        client.rest_post_async = AsyncMock(
            return_value={"page": [], "nextPageToken": None}
        )
        mock_get_client.return_value = client

        # WHEN we list with filter_by_state and as_reviewer
        await FormService.list_form_data(
            MagicMock(),
            group_id="9",
            filter_by_state=["submitted_waiting_for_review", "accepted"],
            as_reviewer=True,
        )

        # THEN the reviewer URI is used and filterByState rides in the body.
        assert (
            client.rest_post_async.call_args.kwargs["uri"]
            == "/form/data/list/reviewer"
        )
        body = json.loads(client.rest_post_async.call_args.kwargs["body"])
        assert body == {
            "groupId": "9",
            "filterByState": [
                "submitted_waiting_for_review",
                "accepted",
            ],
        }

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    async def test_given_token_when_listed_then_forwards_in_body(
        self, mock_get_client
    ):
        # GIVEN a caller paginating with a previous page's token
        client = MagicMock()
        client.rest_post_async = AsyncMock(
            return_value={"page": [], "nextPageToken": None}
        )
        mock_get_client.return_value = client

        # WHEN we ask for the next page
        result = await FormService.list_form_data(
            MagicMock(), group_id="9", next_page_token="fd-tok-2"
        )

        # THEN the token rides in the body and the response surfaces a
        # null next_page_token (signalling end of pagination).
        body = json.loads(client.rest_post_async.call_args.kwargs["body"])
        assert body == {
            "groupId": "9",
            "filterByState": [],
            "nextPageToken": "fd-tok-2",
        }
        assert result["next_page_token"] is None
        assert result["results"] == []

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    async def test_given_expired_auth_when_listing_then_returns_error_dict(
        self, mock_get_client
    ):
        # GIVEN expired credentials
        mock_get_client.side_effect = ConnectionAuthError("expired")

        # WHEN we list form data
        result = await FormService.list_form_data(
            MagicMock(), group_id="9"
        )

        # THEN the auth error comes back as a single error dict
        # (the response shape is now a dict, not a list).
        assert isinstance(result, dict)
        assert "Authentication required" in result["error"]
        assert result["group_id"] == "9"
