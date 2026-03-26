"""Tests for synapse_client_from and @error_boundary."""

from unittest.mock import MagicMock, patch

import pytest

from synapse_mcp.connection_auth import ConnectionAuthError
from synapse_mcp.services.tool_service import (
    error_boundary,
    synapse_client_from,
)


# -------------------------------------------------------------------
# synapse_client_from
# -------------------------------------------------------------------

@patch("synapse_mcp.services.tool_service.get_synapse_client")
class TestSynapseClientFrom:
    def test_yields_client(self, mock_get_client):
        mock_get_client.return_value = MagicMock()
        ctx = MagicMock()
        with synapse_client_from(ctx) as client:
            assert client is mock_get_client.return_value
        mock_get_client.assert_called_once_with(ctx)

    def test_raises_on_auth_failure(self, mock_get_client):
        mock_get_client.side_effect = ConnectionAuthError("expired")
        ctx = MagicMock()
        with pytest.raises(ConnectionAuthError):
            with synapse_client_from(ctx):
                pass


# -------------------------------------------------------------------
# @error_boundary
# -------------------------------------------------------------------

class TestErrorBoundary:
    def test_passes_through_success(self):
        class Svc:
            @error_boundary()
            def do_thing(self, ctx):
                return {"data": 42}

        assert Svc().do_thing(MagicMock()) == {"data": 42}

    def test_catches_auth_error(self):
        class Svc:
            @error_boundary()
            def do_thing(self, ctx):
                raise ConnectionAuthError("expired")

        result = Svc().do_thing(MagicMock())
        assert "Authentication required" in result["error"]

    def test_catches_generic_error_with_type(self):
        class Svc:
            @error_boundary()
            def do_thing(self, ctx):
                raise ValueError("bad input")

        result = Svc().do_thing(MagicMock())
        assert result["error"] == "bad input"
        assert result["error_type"] == "ValueError"

    def test_error_context_keys_from_positional(self):
        class Svc:
            @error_boundary(
                error_context_keys=("project_id",),
            )
            def do_thing(self, ctx, project_id):
                raise RuntimeError("boom")

        result = Svc().do_thing(MagicMock(), "syn123")
        assert result["project_id"] == "syn123"
        assert result["error"] == "boom"

    def test_error_context_keys_from_keyword(self):
        class Svc:
            @error_boundary(
                error_context_keys=("task_id",),
            )
            def do_thing(self, ctx, task_id):
                raise RuntimeError("boom")

        result = Svc().do_thing(MagicMock(), task_id=7)
        assert result["task_id"] == 7

    def test_wrap_errors_list(self):
        class Svc:
            @error_boundary(wrap_errors=list)
            def do_thing(self, ctx):
                raise RuntimeError("boom")

        result = Svc().do_thing(MagicMock())
        assert isinstance(result, list)
        assert result[0]["error"] == "boom"

    def test_wrap_errors_list_with_context(self):
        class Svc:
            @error_boundary(
                error_context_keys=("project_id",),
                wrap_errors=list,
            )
            def do_thing(self, ctx, project_id):
                raise ConnectionAuthError("expired")

        result = Svc().do_thing(MagicMock(), "syn123")
        assert isinstance(result, list)
        assert "Authentication required" in result[0]["error"]
        assert result[0]["project_id"] == "syn123"

    def test_success_not_wrapped_in_list(self):
        class Svc:
            @error_boundary(wrap_errors=list)
            def do_thing(self, ctx):
                return [{"data": 1}, {"data": 2}]

        result = Svc().do_thing(MagicMock())
        assert result == [{"data": 1}, {"data": 2}]
