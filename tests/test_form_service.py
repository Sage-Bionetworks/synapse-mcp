"""Tests for FormService."""

from dataclasses import dataclass
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from synapse_mcp.connection_auth import ConnectionAuthError
from synapse_mcp.services.form_service import FormService

pytestmark = pytest.mark.anyio("asyncio")


@pytest.fixture
def anyio_backend():
    return "asyncio"


TS = "synapse_mcp.services.tool_service"
SVC = "synapse_mcp.services.form_service"


@dataclass
class FakeFormData:
    form_data_id: str = "fd-1"
    name: str = "submission-1"
    group_id: str = "9"
    etag: str = "abc"
    submission_status: str = "SUBMITTED"
    created_on: str = "2025-01-01"
    modified_on: str = "2025-01-02"
    created_by: str = "user1"
    data_file_handle_id: Optional[str] = None


def fake_list_async(captured_kwargs: Optional[dict] = None):
    """Stand-in for FormGroup.list_async that yields two fixture submissions.

    If captured_kwargs is provided, the kwargs the service forwards to the SDK
    are recorded into it (so tests can assert on input). Returns the async
    generator function itself, ready to assign to mock_fg.return_value.list_async.
    """
    async def _list_async(**kw):
        if captured_kwargs is not None:
            captured_kwargs.update(kw)
        yield FakeFormData(form_data_id="fd-1")
        yield FakeFormData(
            form_data_id="fd-2",
            submission_status="ACCEPTED",
        )
    return _list_async


class TestListFormData:
    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.FormGroup")
    async def test_given_group_id_when_listed_then_returns_submissions(
        self, mock_fg_cls, mock_get_client
    ):
        # GIVEN a FormGroup with two submissions
        mock_get_client.return_value = MagicMock()
        mock_fg_cls.return_value.list_async = fake_list_async()

        # WHEN we list form data for the group
        result = await FormService().list_form_data(
            MagicMock(), group_id="9"
        )

        # THEN both submissions are returned as dicts
        assert len(result) == 2
        assert result[0]["form_data_id"] == "fd-1"
        assert result[0]["submission_status"] == "SUBMITTED"
        assert result[1]["form_data_id"] == "fd-2"
        assert result[1]["submission_status"] == "ACCEPTED"
        mock_fg_cls.assert_called_once_with(group_id="9")

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.FormGroup")
    async def test_given_filter_and_reviewer_when_listed_then_forwarded_to_sdk(
        self, mock_fg_cls, mock_get_client
    ):
        # GIVEN a state filter and reviewer flag
        client = MagicMock()
        mock_get_client.return_value = client
        captured_kwargs: dict = {}
        mock_fg_cls.return_value.list_async = fake_list_async(captured_kwargs)

        # WHEN we list with filter_by_state and as_reviewer
        await FormService().list_form_data(
            MagicMock(),
            group_id="9",
            filter_by_state=["submitted_waiting_for_review", "accepted"],
            as_reviewer=True,
        )

        # THEN the client receives the same arguments
        assert captured_kwargs == {
            "filter_by_state": ["submitted_waiting_for_review", "accepted"],
            "as_reviewer": True,
            "synapse_client": client,
        }

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.FormGroup")
    async def test_given_no_submissions_when_listed_then_returns_empty_list(
        self, mock_fg_cls, mock_get_client
    ):
        # GIVEN a FormGroup with no submissions
        mock_get_client.return_value = MagicMock()

        # An empty async generator: the unreachable yield is what makes
        # Python compile this as a generator instead of a coroutine.
        async def _submissions(**_):
            for _ in ():
                yield

        mock_fg_cls.return_value.list_async = _submissions

        # WHEN we list form data
        result = await FormService().list_form_data(
            MagicMock(), group_id="9"
        )

        # THEN an empty list is returned
        assert result == []

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.FormGroup")
    async def test_given_limit_when_listed_then_stops_at_limit(
        self, mock_fg_cls, mock_get_client
    ):
        # GIVEN a FormGroup that would yield five submissions
        mock_get_client.return_value = MagicMock()
        fetched: list[str] = []

        # Record each yield so we can distinguish "service stopped iterating
        # at the limit" from "service consumed all five and sliced". With
        # limit=2, fetched should contain exactly the two items pulled —
        # if it contains all five, the service is over-fetching.
        async def _submissions(**_):
            for i in range(5):
                fetched.append(f"fd-{i}")
                yield FakeFormData(form_data_id=f"fd-{i}")

        mock_fg_cls.return_value.list_async = _submissions

        # WHEN we list with limit=2
        result = await FormService().list_form_data(
            MagicMock(), group_id="9", limit=2
        )

        # THEN only two are returned AND the SDK is not iterated past the limit
        assert len(result) == 2
        assert result[0]["form_data_id"] == "fd-0"
        assert result[1]["form_data_id"] == "fd-1"
        assert fetched == ["fd-0", "fd-1"]

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    async def test_given_expired_auth_when_listing_then_returns_error_list(
        self, mock_get_client
    ):
        # GIVEN expired credentials
        mock_get_client.side_effect = ConnectionAuthError("expired")

        # WHEN we list form data
        result = await FormService().list_form_data(
            MagicMock(), group_id="9"
        )

        # THEN the auth error is wrapped in a list with group_id context
        assert isinstance(result, list)
        assert "Authentication required" in result[0]["error"]
        assert result[0]["group_id"] == "9"
