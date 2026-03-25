"""Tests for CurationTaskService.

Service tests mock get_synapse_client and the manager class to verify
orchestration, serialization, error wrapping, and partial-failure handling.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from synapse_mcp.connection_auth import ConnectionAuthError
from synapse_mcp.services.curation_task_service import (
    CurationTaskService,
    _format_task,
    _format_task_properties,
)


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

def _file_props(upload_folder_id="syn100", file_view_id="syn200"):
    return SimpleNamespace(
        upload_folder_id=upload_folder_id, file_view_id=file_view_id
    )


def _record_props(record_set_id="syn300"):
    return SimpleNamespace(record_set_id=record_set_id)


def _make_task(*, task_id=1, data_type="DataType", project_id="syn999",
               instructions="Do curation", etag="abc123",
               created_on="2024-01-01", modified_on="2024-01-02",
               created_by="user1", modified_by="user2",
               task_properties=None):
    return SimpleNamespace(
        task_id=task_id, data_type=data_type, project_id=project_id,
        instructions=instructions, etag=etag, created_on=created_on,
        modified_on=modified_on, created_by=created_by, modified_by=modified_by,
        task_properties=task_properties,
    )


# ---------------------------------------------------------------------------
# _format_task_properties (unit)
# ---------------------------------------------------------------------------

class TestFormatTaskProperties:
    def test_file_based(self):
        result = _format_task_properties(_file_props("syn100", "syn200"))
        assert result == {
            "type": "file-based",
            "upload_folder_id": "syn100",
            "file_view_id": "syn200",
        }

    def test_record_based(self):
        result = _format_task_properties(_record_props("syn300"))
        assert result == {
            "type": "record-based",
            "record_set_id": "syn300",
        }

    def test_none(self):
        assert _format_task_properties(None) == {}


# ---------------------------------------------------------------------------
# _format_task (unit)
# ---------------------------------------------------------------------------

class TestFormatTask:
    def test_includes_all_fields(self):
        task = _make_task(task_id=42, task_properties=_file_props())
        result = _format_task(task)
        assert result["task_id"] == 42
        assert result["data_type"] == "DataType"
        assert result["project_id"] == "syn999"
        assert result["instructions"] == "Do curation"
        assert result["etag"] == "abc123"
        assert result["task_properties"]["type"] == "file-based"

    def test_omits_task_properties_when_none(self):
        task = _make_task(task_properties=None)
        result = _format_task(task)
        assert "task_properties" not in result


# ---------------------------------------------------------------------------
# CurationTaskService.list_tasks
# ---------------------------------------------------------------------------

class TestListTasks:
    @patch("synapse_mcp.services.tool_service.get_synapse_client")
    @patch("synapse_mcp.services.curation_task_service.CurationTaskManager")
    def test_returns_formatted_list(self, mock_manager_cls, mock_get_client):
        mock_get_client.return_value = MagicMock()
        tasks = [
            _make_task(task_id=1, task_properties=_file_props()),
            _make_task(task_id=2, task_properties=_record_props()),
        ]
        mock_manager_cls.return_value.list_tasks.return_value = iter(tasks)

        result = CurationTaskService().list_tasks(MagicMock(), "syn999")

        assert len(result) == 2
        assert result[0]["task_id"] == 1
        assert result[0]["task_properties"]["type"] == "file-based"
        assert result[1]["task_id"] == 2
        assert result[1]["task_properties"]["type"] == "record-based"

    @patch("synapse_mcp.services.tool_service.get_synapse_client")
    @patch("synapse_mcp.services.curation_task_service.CurationTaskManager")
    def test_empty_project(self, mock_manager_cls, mock_get_client):
        mock_get_client.return_value = MagicMock()
        mock_manager_cls.return_value.list_tasks.return_value = iter([])

        result = CurationTaskService().list_tasks(MagicMock(), "syn999")

        assert result == []

    @patch("synapse_mcp.services.tool_service.get_synapse_client")
    def test_auth_error_returns_list(self, mock_get_client):
        mock_get_client.side_effect = ConnectionAuthError("expired")

        result = CurationTaskService().list_tasks(MagicMock(), "syn123")

        assert isinstance(result, list)
        assert len(result) == 1
        assert "Authentication required" in result[0]["error"]
        assert result[0]["project_id"] == "syn123"

    @patch("synapse_mcp.services.tool_service.get_synapse_client")
    @patch("synapse_mcp.services.curation_task_service.CurationTaskManager")
    def test_generic_error_returns_list(self, mock_manager_cls, mock_get_client):
        mock_get_client.return_value = MagicMock()
        mock_manager_cls.return_value.list_tasks.side_effect = RuntimeError("boom")

        result = CurationTaskService().list_tasks(MagicMock(), "syn123")

        assert isinstance(result, list)
        assert result[0]["error"] == "boom"
        assert result[0]["error_type"] == "RuntimeError"


# ---------------------------------------------------------------------------
# CurationTaskService.get_task
# ---------------------------------------------------------------------------

class TestGetTask:
    @patch("synapse_mcp.services.tool_service.get_synapse_client")
    @patch("synapse_mcp.services.curation_task_service.CurationTaskManager")
    def test_returns_formatted_task(self, mock_manager_cls, mock_get_client):
        mock_get_client.return_value = MagicMock()
        task = _make_task(task_id=42, task_properties=_file_props())
        mock_manager_cls.return_value.get_task.return_value = task

        result = CurationTaskService().get_task(MagicMock(), 42)

        assert result["task_id"] == 42
        assert result["task_properties"]["type"] == "file-based"

    @patch("synapse_mcp.services.tool_service.get_synapse_client")
    def test_auth_error(self, mock_get_client):
        mock_get_client.side_effect = ConnectionAuthError("expired")

        result = CurationTaskService().get_task(MagicMock(), 42)

        assert "Authentication required" in result["error"]
        assert result["task_id"] == 42


# ---------------------------------------------------------------------------
# CurationTaskService.get_task_resources
# ---------------------------------------------------------------------------

class TestGetTaskResources:
    @patch("synapse_mcp.services.tool_service.get_synapse_client")
    @patch("synapse_mcp.services.curation_task_service.CurationTaskManager")
    def test_file_based_resources(self, mock_manager_cls, mock_get_client):
        mock_get_client.return_value = MagicMock()
        task = _make_task(task_id=1, task_properties=_file_props("syn100", "syn200"))
        mgr = mock_manager_cls.return_value
        mgr.get_task.return_value = task
        mgr.get_folder.return_value = SimpleNamespace(id="syn100", name="uploads")
        mgr.get_entity_view.return_value = SimpleNamespace(id="syn200", name="view")

        result = CurationTaskService().get_task_resources(MagicMock(), 1)

        assert result["task_id"] == 1
        assert result["resources"]["type"] == "file-based"
        assert result["resources"]["upload_folder"].id == "syn100"
        assert result["resources"]["file_view"].id == "syn200"

    @patch("synapse_mcp.services.tool_service.get_synapse_client")
    @patch("synapse_mcp.services.curation_task_service.CurationTaskManager")
    def test_record_based_resources(self, mock_manager_cls, mock_get_client):
        mock_get_client.return_value = MagicMock()
        task = _make_task(task_id=2, task_properties=_record_props("syn300"))
        mgr = mock_manager_cls.return_value
        mgr.get_task.return_value = task
        mgr.get_record_set.return_value = SimpleNamespace(id="syn300", name="records")

        result = CurationTaskService().get_task_resources(MagicMock(), 2)

        assert result["task_id"] == 2
        assert result["resources"]["type"] == "record-based"
        assert result["resources"]["record_set"].id == "syn300"

    @patch("synapse_mcp.services.tool_service.get_synapse_client")
    @patch("synapse_mcp.services.curation_task_service.CurationTaskManager")
    def test_folder_fetch_error_captured_gracefully(self, mock_manager_cls, mock_get_client):
        """A folder fetch failure should be captured, not bubble up."""
        mock_get_client.return_value = MagicMock()
        task = _make_task(task_id=3, task_properties=_file_props("syn100", "syn200"))
        mgr = mock_manager_cls.return_value
        mgr.get_task.return_value = task
        mgr.get_folder.side_effect = RuntimeError("folder unavailable")
        mgr.get_entity_view.return_value = SimpleNamespace(id="syn200", name="view")

        result = CurationTaskService().get_task_resources(MagicMock(), 3)

        assert "error" in result["resources"]["upload_folder"]
        assert result["resources"]["upload_folder"]["id"] == "syn100"
        assert result["resources"]["file_view"].id == "syn200"

    @patch("synapse_mcp.services.tool_service.get_synapse_client")
    @patch("synapse_mcp.services.curation_task_service.CurationTaskManager")
    def test_view_fetch_error_captured_gracefully(self, mock_manager_cls, mock_get_client):
        """An entity view fetch failure should be captured, not bubble up."""
        mock_get_client.return_value = MagicMock()
        task = _make_task(task_id=4, task_properties=_file_props("syn100", "syn200"))
        mgr = mock_manager_cls.return_value
        mgr.get_task.return_value = task
        mgr.get_folder.return_value = SimpleNamespace(id="syn100", name="uploads")
        mgr.get_entity_view.side_effect = RuntimeError("view unavailable")

        result = CurationTaskService().get_task_resources(MagicMock(), 4)

        assert result["resources"]["upload_folder"].id == "syn100"
        assert "error" in result["resources"]["file_view"]
        assert result["resources"]["file_view"]["id"] == "syn200"

    @patch("synapse_mcp.services.tool_service.get_synapse_client")
    @patch("synapse_mcp.services.curation_task_service.CurationTaskManager")
    def test_record_set_fetch_error_captured_gracefully(self, mock_manager_cls, mock_get_client):
        """A record set fetch failure should be captured, not bubble up."""
        mock_get_client.return_value = MagicMock()
        task = _make_task(task_id=5, task_properties=_record_props("syn300"))
        mgr = mock_manager_cls.return_value
        mgr.get_task.return_value = task
        mgr.get_record_set.side_effect = RuntimeError("record set unavailable")

        result = CurationTaskService().get_task_resources(MagicMock(), 5)

        assert result["resources"]["type"] == "record-based"
        assert "error" in result["resources"]["record_set"]
        assert result["resources"]["record_set"]["id"] == "syn300"

    @patch("synapse_mcp.services.tool_service.get_synapse_client")
    @patch("synapse_mcp.services.curation_task_service.CurationTaskManager")
    def test_no_properties_returns_empty_resources(self, mock_manager_cls, mock_get_client):
        """Tasks with no task_properties should return empty resources."""
        mock_get_client.return_value = MagicMock()
        task = _make_task(task_id=6, task_properties=None)
        mgr = mock_manager_cls.return_value
        mgr.get_task.return_value = task

        result = CurationTaskService().get_task_resources(MagicMock(), 6)

        assert result["resources"] == {}

    @patch("synapse_mcp.services.tool_service.get_synapse_client")
    def test_auth_error(self, mock_get_client):
        mock_get_client.side_effect = ConnectionAuthError("expired")

        result = CurationTaskService().get_task_resources(MagicMock(), 1)

        assert "Authentication required" in result["error"]
        assert result["task_id"] == 1

    @patch("synapse_mcp.services.tool_service.get_synapse_client")
    @patch("synapse_mcp.services.curation_task_service.CurationTaskManager")
    def test_generic_error(self, mock_manager_cls, mock_get_client):
        mock_get_client.return_value = MagicMock()
        mock_manager_cls.return_value.get_task.side_effect = ValueError("bad")

        result = CurationTaskService().get_task_resources(MagicMock(), 5)

        assert result["error"] == "bad"
        assert result["task_id"] == 5
