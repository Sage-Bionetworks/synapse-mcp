"""Tests for CurationTaskService.

Service tests verify serialization, error boundary behavior,
and delegation to the manager for complex operations.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from synapse_mcp.connection_auth import ConnectionAuthError
from synapse_mcp.services.curation_task_service import (
    CurationTaskService,
    _format_task,
    _format_task_properties,
)


# -------------------------------------------------------------------
# Shared fixtures
# -------------------------------------------------------------------

def _file_props(upload_folder_id="syn100", file_view_id="syn200"):
    return SimpleNamespace(
        upload_folder_id=upload_folder_id,
        file_view_id=file_view_id,
    )


def _record_props(record_set_id="syn300"):
    return SimpleNamespace(record_set_id=record_set_id)


def _make_task(
    *, task_id=1, data_type="DataType", project_id="syn999",
    instructions="Do curation", etag="abc123",
    created_on="2024-01-01", modified_on="2024-01-02",
    created_by="user1", modified_by="user2",
    task_properties=None,
):
    return SimpleNamespace(
        task_id=task_id, data_type=data_type,
        project_id=project_id, instructions=instructions,
        etag=etag, created_on=created_on,
        modified_on=modified_on, created_by=created_by,
        modified_by=modified_by,
        task_properties=task_properties,
    )


# -------------------------------------------------------------------
# _format_task_properties (unit)
# -------------------------------------------------------------------

class TestFormatTaskProperties:
    def test_file_based(self):
        result = _format_task_properties(
            _file_props("syn100", "syn200"),
        )
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


# -------------------------------------------------------------------
# _format_task (unit)
# -------------------------------------------------------------------

class TestFormatTask:
    def test_includes_all_fields(self):
        task = _make_task(
            task_id=42, task_properties=_file_props(),
        )
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


# -------------------------------------------------------------------
# CurationTaskService.list_tasks
# -------------------------------------------------------------------

SVC = "synapse_mcp.services.curation_task_service"
TS = "synapse_mcp.services.tool_service"


class TestListTasks:
    @patch(f"{TS}.get_synapse_client")
    @patch(f"{SVC}.CurationTask")
    def test_returns_formatted_list(
        self, mock_ct, mock_get_client
    ):
        mock_get_client.return_value = MagicMock()
        tasks = [
            _make_task(
                task_id=1, task_properties=_file_props(),
            ),
            _make_task(
                task_id=2, task_properties=_record_props(),
            ),
        ]
        mock_ct.list.return_value = iter(tasks)

        result = CurationTaskService().list_tasks(
            MagicMock(), "syn999",
        )

        assert len(result) == 2
        assert result[0]["task_id"] == 1
        assert result[0]["task_properties"]["type"] == "file-based"
        assert result[1]["task_id"] == 2
        tp = result[1]["task_properties"]
        assert tp["type"] == "record-based"

    @patch(f"{TS}.get_synapse_client")
    @patch(f"{SVC}.CurationTask")
    def test_empty_project(self, mock_ct, mock_get_client):
        mock_get_client.return_value = MagicMock()
        mock_ct.list.return_value = iter([])

        result = CurationTaskService().list_tasks(
            MagicMock(), "syn999",
        )

        assert result == []

    @patch(f"{TS}.get_synapse_client")
    def test_auth_error_returns_list(self, mock_get_client):
        mock_get_client.side_effect = ConnectionAuthError(
            "expired",
        )

        result = CurationTaskService().list_tasks(
            MagicMock(), "syn123",
        )

        assert isinstance(result, list)
        assert len(result) == 1
        assert "Authentication required" in result[0]["error"]
        assert result[0]["project_id"] == "syn123"

    @patch(f"{TS}.get_synapse_client")
    @patch(f"{SVC}.CurationTask")
    def test_generic_error_returns_list(
        self, mock_ct, mock_get_client
    ):
        mock_get_client.return_value = MagicMock()
        mock_ct.list.side_effect = RuntimeError("boom")

        result = CurationTaskService().list_tasks(
            MagicMock(), "syn123",
        )

        assert isinstance(result, list)
        assert result[0]["error"] == "boom"
        assert result[0]["error_type"] == "RuntimeError"


# -------------------------------------------------------------------
# CurationTaskService.get_task
# -------------------------------------------------------------------

class TestGetTask:
    @patch(f"{TS}.get_synapse_client")
    @patch(f"{SVC}.CurationTask")
    def test_returns_formatted_task(
        self, mock_ct, mock_get_client
    ):
        mock_get_client.return_value = MagicMock()
        task = _make_task(
            task_id=42, task_properties=_file_props(),
        )
        mock_ct.return_value.get.return_value = task

        result = CurationTaskService().get_task(MagicMock(), 42)

        assert result["task_id"] == 42
        assert result["task_properties"]["type"] == "file-based"

    @patch(f"{TS}.get_synapse_client")
    def test_auth_error(self, mock_get_client):
        mock_get_client.side_effect = ConnectionAuthError(
            "expired",
        )

        result = CurationTaskService().get_task(MagicMock(), 42)

        assert "Authentication required" in result["error"]
        assert result["task_id"] == 42


# -------------------------------------------------------------------
# CurationTaskService.get_task_resources
# -------------------------------------------------------------------

class TestGetTaskResources:
    @patch(f"{TS}.get_synapse_client")
    @patch(f"{SVC}.CurationTaskManager")
    def test_delegates_to_manager(
        self, mock_mgr_cls, mock_get_client
    ):
        mock_get_client.return_value = MagicMock()
        task = _make_task(task_id=1)
        resources = {"type": "file-based", "upload_folder": {}}
        mock_mgr_cls.return_value \
            .get_task_with_resources.return_value = (
                task, resources,
            )

        result = CurationTaskService().get_task_resources(
            MagicMock(), 1,
        )

        assert result["task_id"] == 1
        assert result["resources"] is resources

    @patch(f"{TS}.get_synapse_client")
    def test_auth_error(self, mock_get_client):
        mock_get_client.side_effect = ConnectionAuthError(
            "expired",
        )

        result = CurationTaskService().get_task_resources(
            MagicMock(), 1,
        )

        assert "Authentication required" in result["error"]
        assert result["task_id"] == 1

    @patch(f"{TS}.get_synapse_client")
    @patch(f"{SVC}.CurationTaskManager")
    def test_generic_error(
        self, mock_mgr_cls, mock_get_client
    ):
        mock_get_client.return_value = MagicMock()
        mock_mgr_cls.return_value \
            .get_task_with_resources.side_effect = (
                ValueError("bad")
            )

        result = CurationTaskService().get_task_resources(
            MagicMock(), 5,
        )

        assert result["error"] == "bad"
        assert result["task_id"] == 5
