"""Tests for CurationTaskService."""

from unittest.mock import MagicMock, patch

from synapse_mcp.connection_auth import ConnectionAuthError
from synapse_mcp.services.curation_task_service import CurationTaskService


class TestListTasks:
    @patch("synapse_mcp.services.tool_service.get_synapse_client")
    @patch("synapse_mcp.services.curation_task_service.CurationTaskManager")
    def test_delegates_to_manager(self, mock_manager_cls, mock_get_client):
        mock_get_client.return_value = MagicMock()
        mock_manager_cls.return_value.list_tasks.return_value = [
            {"task_id": 1}, {"task_id": 2}
        ]
        ctx = MagicMock()
        result = CurationTaskService().list_tasks(ctx, "syn123")
        assert result == [{"task_id": 1}, {"task_id": 2}]
        mock_manager_cls.return_value.list_tasks.assert_called_once_with("syn123")

    @patch("synapse_mcp.services.tool_service.get_synapse_client")
    def test_auth_error_returns_list(self, mock_get_client):
        mock_get_client.side_effect = ConnectionAuthError("expired")
        ctx = MagicMock()
        result = CurationTaskService().list_tasks(ctx, "syn123")
        assert isinstance(result, list)
        assert len(result) == 1
        assert "Authentication required" in result[0]["error"]
        assert result[0]["project_id"] == "syn123"

    @patch("synapse_mcp.services.tool_service.get_synapse_client")
    @patch("synapse_mcp.services.curation_task_service.CurationTaskManager")
    def test_generic_error_returns_list(self, mock_manager_cls, mock_get_client):
        mock_get_client.return_value = MagicMock()
        mock_manager_cls.return_value.list_tasks.side_effect = RuntimeError("boom")
        ctx = MagicMock()
        result = CurationTaskService().list_tasks(ctx, "syn123")
        assert isinstance(result, list)
        assert result[0]["error"] == "boom"
        assert result[0]["error_type"] == "RuntimeError"


class TestGetTask:
    @patch("synapse_mcp.services.tool_service.get_synapse_client")
    @patch("synapse_mcp.services.curation_task_service.CurationTaskManager")
    def test_delegates_to_manager(self, mock_manager_cls, mock_get_client):
        mock_get_client.return_value = MagicMock()
        mock_manager_cls.return_value.get_task.return_value = {"task_id": 42}
        ctx = MagicMock()
        result = CurationTaskService().get_task(ctx, 42)
        assert result == {"task_id": 42}
        mock_manager_cls.return_value.get_task.assert_called_once_with(42)

    @patch("synapse_mcp.services.tool_service.get_synapse_client")
    def test_auth_error(self, mock_get_client):
        mock_get_client.side_effect = ConnectionAuthError("expired")
        ctx = MagicMock()
        result = CurationTaskService().get_task(ctx, 42)
        assert "Authentication required" in result["error"]
        assert result["task_id"] == 42


class TestGetTaskResources:
    @patch("synapse_mcp.services.tool_service.get_synapse_client")
    @patch("synapse_mcp.services.curation_task_service.CurationTaskManager")
    def test_delegates_to_manager(self, mock_manager_cls, mock_get_client):
        mock_get_client.return_value = MagicMock()
        mock_manager_cls.return_value.get_task_resources.return_value = {
            "task_id": 5, "resources": {"type": "file-based"}
        }
        ctx = MagicMock()
        result = CurationTaskService().get_task_resources(ctx, 5)
        assert result["resources"]["type"] == "file-based"
        mock_manager_cls.return_value.get_task_resources.assert_called_once_with(5)

    @patch("synapse_mcp.services.tool_service.get_synapse_client")
    @patch("synapse_mcp.services.curation_task_service.CurationTaskManager")
    def test_generic_error(self, mock_manager_cls, mock_get_client):
        mock_get_client.return_value = MagicMock()
        mock_manager_cls.return_value.get_task_resources.side_effect = ValueError("bad")
        ctx = MagicMock()
        result = CurationTaskService().get_task_resources(ctx, 5)
        assert result["error"] == "bad"
        assert result["task_id"] == 5
