"""Tests for SubmissionService."""

from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from synapse_mcp.connection_auth import ConnectionAuthError
from synapse_mcp.services.submission_service import SubmissionService

pytestmark = pytest.mark.anyio("asyncio")


@pytest.fixture
def anyio_backend():
    return "asyncio"


TS = "synapse_mcp.services.tool_service"
SVC = "synapse_mcp.services.submission_service"


@dataclass
class FakeSubmission:
    id: str = "777"
    evaluation_id: str = "9600001"
    user_id: str = "42"


@dataclass
class FakeSubmissionStatus:
    id: str = "777"
    status: str = "SCORED"
    score: float = 0.91


@dataclass
class FakeBundle:
    submission_id: str = "777"
    status: str = "SCORED"


async def _agen(items):
    for it in items:
        yield it


class TestGetSubmission:
    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.Submission")
    async def test_given_submission_id_then_returns_dict(
        self, mock_sub_cls, mock_get_client
    ):
        mock_get_client.return_value = MagicMock()
        mock_sub_cls.return_value.get_async = AsyncMock(
            return_value=FakeSubmission()
        )

        result = await SubmissionService().get_submission(
            MagicMock(), "777"
        )

        assert result["id"] == "777"


class TestListEvaluationSubmissions:
    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.Submission")
    async def test_given_queue_then_returns_submissions(
        self, mock_sub_cls, mock_get_client
    ):
        mock_get_client.return_value = MagicMock()
        mock_sub_cls.get_evaluation_submissions_async = MagicMock(
            return_value=_agen(
                [FakeSubmission(id="1"), FakeSubmission(id="2")]
            )
        )

        result = await SubmissionService().list_evaluation_submissions(
            MagicMock(), "9600001"
        )

        assert [s["id"] for s in result] == ["1", "2"]

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.Submission")
    async def test_given_limit_then_truncates_results(
        self, mock_sub_cls, mock_get_client
    ):
        mock_get_client.return_value = MagicMock()
        mock_sub_cls.get_evaluation_submissions_async = MagicMock(
            return_value=_agen(
                [FakeSubmission(id=str(i)) for i in range(5)]
            )
        )

        result = await SubmissionService().list_evaluation_submissions(
            MagicMock(), "9600001", limit=2
        )

        assert len(result) == 2

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    async def test_given_expired_auth_then_returns_wrapped_error(
        self, mock_get_client
    ):
        mock_get_client.side_effect = ConnectionAuthError("expired")

        result = await SubmissionService().list_evaluation_submissions(
            MagicMock(), "9600001"
        )

        assert isinstance(result, list)
        assert "Authentication required" in result[0]["error"]


class TestGetSubmissionCount:
    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.Submission")
    async def test_given_queue_then_wraps_count_in_dict(
        self, mock_sub_cls, mock_get_client
    ):
        mock_get_client.return_value = MagicMock()
        mock_sub_cls.get_submission_count_async = AsyncMock(return_value=123)

        result = await SubmissionService().get_submission_count(
            MagicMock(), "9600001"
        )

        assert result == {"evaluation_id": "9600001", "count": 123}


class TestGetSubmissionStatus:
    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.SubmissionStatus")
    async def test_given_submission_then_returns_status_dict(
        self, mock_status_cls, mock_get_client
    ):
        mock_get_client.return_value = MagicMock()
        mock_status_cls.return_value.get_async = AsyncMock(
            return_value=FakeSubmissionStatus()
        )

        result = await SubmissionService().get_submission_status(
            MagicMock(), "777"
        )

        assert result["status"] == "SCORED"
        assert result["score"] == 0.91


class TestListSubmissionStatuses:
    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.SubmissionStatus")
    async def test_given_queue_then_forwards_filters(
        self, mock_status_cls, mock_get_client
    ):
        mock_get_client.return_value = MagicMock()
        mock_status_cls.get_all_submission_statuses_async = AsyncMock(
            return_value=[FakeSubmissionStatus(id="a"), FakeSubmissionStatus(id="b")]
        )

        result = await SubmissionService().list_submission_statuses(
            MagicMock(), "9600001", status="SCORED", limit=5, offset=0
        )

        assert [s["id"] for s in result] == ["a", "b"]
        call_kwargs = (
            mock_status_cls.get_all_submission_statuses_async.call_args[1]
        )
        assert call_kwargs["status"] == "SCORED"
        assert call_kwargs["limit"] == 5

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    async def test_given_expired_auth_then_returns_wrapped_error(
        self, mock_get_client
    ):
        mock_get_client.side_effect = ConnectionAuthError("expired")

        result = await SubmissionService().list_submission_statuses(
            MagicMock(), "9600001"
        )

        assert isinstance(result, list)
        assert "Authentication required" in result[0]["error"]


class TestListEvaluationSubmissionBundles:
    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.SubmissionBundle")
    async def test_given_queue_then_returns_bundles(
        self, mock_bundle_cls, mock_get_client
    ):
        mock_get_client.return_value = MagicMock()
        mock_bundle_cls.get_evaluation_submission_bundles_async = (
            MagicMock(return_value=_agen([FakeBundle(), FakeBundle()]))
        )

        result = await SubmissionService().list_evaluation_submission_bundles(
            MagicMock(), "9600001"
        )

        assert len(result) == 2


class TestListMySubmissionBundles:
    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.SubmissionBundle")
    async def test_given_queue_then_returns_bundles(
        self, mock_bundle_cls, mock_get_client
    ):
        mock_get_client.return_value = MagicMock()
        mock_bundle_cls.get_user_submission_bundles_async = MagicMock(
            return_value=_agen([FakeBundle()])
        )

        result = await SubmissionService().list_my_submission_bundles(
            MagicMock(), "9600001"
        )

        assert len(result) == 1
