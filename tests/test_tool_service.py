"""Tests for the with_synapse_client helper."""

from unittest.mock import MagicMock, patch

from synapse_mcp.connection_auth import ConnectionAuthError
from synapse_mcp.services.tool_service import with_synapse_client


@patch("synapse_mcp.services.tool_service.get_synapse_client")
class TestWithSynapseClient:
    def test_returns_callback_result_on_success(self, mock_get_client):
        mock_get_client.return_value = MagicMock()
        ctx = MagicMock()
        result = with_synapse_client(ctx, lambda client: {"data": 42})
        assert result == {"data": 42}

    def test_auth_error_on_client_creation(self, mock_get_client):
        mock_get_client.side_effect = ConnectionAuthError("expired")
        ctx = MagicMock()
        result = with_synapse_client(ctx, lambda client: None)
        assert "Authentication required" in result["error"]

    def test_auth_error_during_callback(self, mock_get_client):
        mock_get_client.return_value = MagicMock()
        ctx = MagicMock()

        def boom(client):
            raise ConnectionAuthError("revoked")

        result = with_synapse_client(ctx, boom)
        assert "Authentication required" in result["error"]

    def test_generic_exception_includes_error_type(self, mock_get_client):
        mock_get_client.return_value = MagicMock()
        ctx = MagicMock()

        def boom(client):
            raise ValueError("bad input")

        result = with_synapse_client(ctx, boom)
        assert result["error"] == "bad input"
        assert result["error_type"] == "ValueError"

    def test_error_context_merged_into_auth_error(self, mock_get_client):
        mock_get_client.side_effect = ConnectionAuthError("expired")
        ctx = MagicMock()
        result = with_synapse_client(
            ctx, lambda c: None, error_context={"project_id": "syn123"}
        )
        assert result["project_id"] == "syn123"
        assert "Authentication required" in result["error"]

    def test_error_context_merged_into_generic_error(self, mock_get_client):
        mock_get_client.return_value = MagicMock()
        ctx = MagicMock()

        def boom(client):
            raise RuntimeError("oops")

        result = with_synapse_client(
            ctx, boom, error_context={"task_id": 7}
        )
        assert result["task_id"] == 7
        assert result["error_type"] == "RuntimeError"
