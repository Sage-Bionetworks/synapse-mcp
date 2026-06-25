"""Tests for EvaluationService."""

from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from synapse_mcp.connection_auth import ConnectionAuthError
from synapse_mcp.services.evaluation_service import EvaluationService

pytestmark = pytest.mark.anyio("asyncio")


@pytest.fixture
def anyio_backend():
    return "asyncio"


TS = "synapse_mcp.services.tool_service"
SVC = "synapse_mcp.services.evaluation_service"


@dataclass
class FakeEvaluation:
    id: str = "9600001"
    name: str = "DREAM Challenge"
    description: str = "A challenge"
    content_source: str = "syn100"
    etag: str = "abc"


class FakeHTTPError(Exception):
    def __init__(self, msg: str = "Not found", status_code: int = 404):
        super().__init__(msg)

        class _Resp:
            pass

        r = _Resp()
        r.status_code = status_code
        self.response = r


class TestGetEvaluation:
    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.Evaluation")
    async def test_given_evaluation_id_then_returns_dict(
        self, mock_eval_cls, mock_get_client
    ):
        mock_get_client.return_value = MagicMock()
        mock_eval_cls.return_value.get_async = AsyncMock(
            return_value=FakeEvaluation()
        )

        result = await EvaluationService().get_evaluation(
            MagicMock(), evaluation_id="9600001"
        )

        assert result["id"] == "9600001"
        assert result["name"] == "DREAM Challenge"

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.Evaluation")
    async def test_given_evaluation_name_then_uses_name_lookup(
        self, mock_eval_cls, mock_get_client
    ):
        mock_get_client.return_value = MagicMock()
        mock_eval_cls.return_value.get_async = AsyncMock(
            return_value=FakeEvaluation(name="Named Eval")
        )

        result = await EvaluationService().get_evaluation(
            MagicMock(), evaluation_name="Named Eval"
        )

        assert result["name"] == "Named Eval"

    async def test_given_no_args_then_returns_error(self):
        result = await EvaluationService().get_evaluation(MagicMock())

        assert "required" in result["error"]

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.Evaluation")
    async def test_given_both_id_and_name_then_id_takes_priority(
        self, mock_eval_cls, mock_get_client
    ):
        mock_get_client.return_value = MagicMock()
        mock_eval_cls.return_value.get_async = AsyncMock(
            return_value=FakeEvaluation()
        )

        await EvaluationService().get_evaluation(
            MagicMock(),
            evaluation_id="9600001",
            evaluation_name="DREAM Challenge",
        )

        mock_eval_cls.assert_called_once_with(id="9600001")

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    async def test_given_expired_auth_then_returns_error(
        self, mock_get_client
    ):
        mock_get_client.side_effect = ConnectionAuthError("expired")

        result = await EvaluationService().get_evaluation(
            MagicMock(), evaluation_id="9600001"
        )

        assert "Authentication required" in result["error"]
        assert result["evaluation_id"] == "9600001"

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    async def test_given_http_error_then_status_code_surfaced(
        self, mock_get_client
    ):
        mock_get_client.side_effect = FakeHTTPError("server error", 500)

        result = await EvaluationService().get_evaluation(
            MagicMock(), evaluation_id="9600001"
        )

        assert result["error"] == "server error"
        assert result["status_code"] == 500
        assert result["evaluation_id"] == "9600001"


class TestListEvaluations:
    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.Evaluation")
    async def test_given_project_id_then_uses_project_scoped_listing(
        self, mock_eval_cls, mock_get_client
    ):
        mock_get_client.return_value = MagicMock()
        mock_eval_cls.get_evaluations_by_project_async = AsyncMock(
            return_value=[FakeEvaluation(id="1"), FakeEvaluation(id="2")]
        )

        result = await EvaluationService().list_evaluations(
            MagicMock(), project_id="syn100"
        )

        assert [e["id"] for e in result] == ["1", "2"]
        mock_eval_cls.get_evaluations_by_project_async.assert_called_once()

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.Evaluation")
    async def test_given_available_only_then_uses_available_listing(
        self, mock_eval_cls, mock_get_client
    ):
        mock_get_client.return_value = MagicMock()
        mock_eval_cls.get_available_evaluations_async = AsyncMock(
            return_value=[FakeEvaluation()]
        )

        result = await EvaluationService().list_evaluations(
            MagicMock(), available_only=True
        )

        assert isinstance(result, list)
        mock_eval_cls.get_available_evaluations_async.assert_called_once()

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.Evaluation")
    async def test_given_defaults_then_uses_all_evaluations(
        self, mock_eval_cls, mock_get_client
    ):
        mock_get_client.return_value = MagicMock()
        mock_eval_cls.get_all_evaluations_async = AsyncMock(
            return_value=[FakeEvaluation()]
        )

        await EvaluationService().list_evaluations(MagicMock())

        mock_eval_cls.get_all_evaluations_async.assert_called_once()

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.Evaluation")
    async def test_given_project_id_then_forwards_all_kwargs(
        self, mock_eval_cls, mock_get_client
    ):
        mock_get_client.return_value = MagicMock()
        mock_eval_cls.get_evaluations_by_project_async = AsyncMock(
            return_value=[]
        )

        await EvaluationService().list_evaluations(
            MagicMock(),
            project_id="syn100",
            access_type="SUBMIT",
            active_only=True,
            evaluation_ids=["1", "2"],
            offset=5,
            limit=10,
        )

        mock_eval_cls.get_evaluations_by_project_async.assert_called_once_with(
            project_id="syn100",
            access_type="SUBMIT",
            active_only=True,
            evaluation_ids=["1", "2"],
            offset=5,
            limit=10,
            synapse_client=mock_get_client.return_value,
        )

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.Evaluation")
    async def test_given_project_id_and_available_only_then_project_id_wins(
        self, mock_eval_cls, mock_get_client
    ):
        mock_get_client.return_value = MagicMock()
        mock_eval_cls.get_evaluations_by_project_async = AsyncMock(
            return_value=[]
        )
        mock_eval_cls.get_available_evaluations_async = AsyncMock(
            return_value=[]
        )

        await EvaluationService().list_evaluations(
            MagicMock(), project_id="syn100", available_only=True
        )

        mock_eval_cls.get_evaluations_by_project_async.assert_called_once()
        mock_eval_cls.get_available_evaluations_async.assert_not_called()

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.Evaluation")
    async def test_given_no_results_then_returns_empty_list(
        self, mock_eval_cls, mock_get_client
    ):
        mock_get_client.return_value = MagicMock()
        mock_eval_cls.get_all_evaluations_async = AsyncMock(return_value=[])

        result = await EvaluationService().list_evaluations(MagicMock())

        assert result == []

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    async def test_given_expired_auth_then_returns_wrapped_error(
        self, mock_get_client
    ):
        mock_get_client.side_effect = ConnectionAuthError("expired")

        result = await EvaluationService().list_evaluations(MagicMock())

        assert isinstance(result, list)
        assert "Authentication required" in result[0]["error"]


class TestGetEvaluationAcl:
    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.Evaluation")
    async def test_given_evaluation_then_returns_acl_dict(
        self, mock_eval_cls, mock_get_client
    ):
        mock_get_client.return_value = MagicMock()
        mock_eval_cls.return_value.get_acl_async = AsyncMock(
            return_value={"resourceAccess": []}
        )

        result = await EvaluationService().get_evaluation_acl(
            MagicMock(), "9600001"
        )

        assert result["evaluation_id"] == "9600001"
        assert "acl" in result
        assert result["acl"] == {"resourceAccess": []}

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    async def test_given_expired_auth_then_returns_error(
        self, mock_get_client
    ):
        mock_get_client.side_effect = ConnectionAuthError("expired")

        result = await EvaluationService().get_evaluation_acl(
            MagicMock(), "9600001"
        )

        assert "Authentication required" in result["error"]
        assert result["evaluation_id"] == "9600001"


class TestGetEvaluationPermissions:
    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.Evaluation")
    async def test_given_evaluation_then_returns_permissions_dict(
        self, mock_eval_cls, mock_get_client
    ):
        mock_get_client.return_value = MagicMock()
        mock_eval_cls.return_value.get_permissions_async = AsyncMock(
            return_value={"canSubmit": True}
        )

        result = await EvaluationService().get_evaluation_permissions(
            MagicMock(), "9600001"
        )

        assert result["evaluation_id"] == "9600001"
        assert result["permissions"] == {"canSubmit": True}

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    async def test_given_expired_auth_then_returns_error(
        self, mock_get_client
    ):
        mock_get_client.side_effect = ConnectionAuthError("expired")

        result = await EvaluationService().get_evaluation_permissions(
            MagicMock(), "9600001"
        )

        assert "Authentication required" in result["error"]
        assert result["evaluation_id"] == "9600001"
