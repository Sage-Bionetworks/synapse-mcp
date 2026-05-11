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


class TestListFormData:
    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.FormGroup")
    async def test_given_group_id_when_listed_then_returns_submissions(
        self, mock_fg_cls, mock_get_client
    ):
        # GIVEN a FormGroup with two submissions
        mock_get_client.return_value = MagicMock()
        mock_fg_cls.return_value.list_async = AsyncMock(
            return_value=[
                FakeFormData(form_data_id="fd-1"),
                FakeFormData(
                    form_data_id="fd-2",
                    submission_status="ACCEPTED",
                ),
            ]
        )

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
    async def test_that_parameters_are_passed_to_client(
        self, mock_fg_cls, mock_get_client
    ):
        # GIVEN a state filter and reviewer flag
        client = MagicMock()
        mock_get_client.return_value = client
        list_async = AsyncMock(return_value=[])
        mock_fg_cls.return_value.list_async = list_async

        # WHEN we list with filter_by_state and as_reviewer
        await FormService().list_form_data(
            MagicMock(),
            group_id="9",
            filter_by_state=["SUBMITTED", "ACCEPTED"],
            as_reviewer=True,
        )

        # THEN the client receives the same arguments
        list_async.assert_awaited_once_with(
            filter_by_state=["SUBMITTED", "ACCEPTED"],
            as_reviewer=True,
            synapse_client=client,
        )

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.FormGroup")
    async def test_given_no_submissions_when_listed_then_returns_empty_list(
        self, mock_fg_cls, mock_get_client
    ):
        # GIVEN a FormGroup with no submissions
        mock_get_client.return_value = MagicMock()
        mock_fg_cls.return_value.list_async = AsyncMock(return_value=[])

        # WHEN we list form data
        result = await FormService().list_form_data(
            MagicMock(), group_id="9"
        )

        # THEN an empty list is returned
        assert result == []

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
