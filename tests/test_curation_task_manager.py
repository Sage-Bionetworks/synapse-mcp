"""Tests for CurationTaskManager."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from synapse_mcp.managers.curation_task_manager import CurationTaskManager


def _make_task(*, task_id=1, data_type="biospecimen", project_id="syn123",
               instructions="Fill in", etag="abc", created_on="2025-01-01",
               modified_on="2025-01-02", created_by="user1", modified_by="user2",
               task_properties=None):
    return SimpleNamespace(
        task_id=task_id, data_type=data_type, project_id=project_id,
        instructions=instructions, etag=etag, created_on=created_on,
        modified_on=modified_on, created_by=created_by, modified_by=modified_by,
        task_properties=task_properties,
    )


class TestTaskToDict:
    def test_no_properties(self):
        task = _make_task(task_properties=None)
        result = CurationTaskManager._task_to_dict(task)
        assert result["task_id"] == 1
        assert result["data_type"] == "biospecimen"
        assert "task_properties" not in result

    def test_file_based_properties(self):
        props = SimpleNamespace(upload_folder_id="syn456", file_view_id="syn789")
        task = _make_task(task_properties=props)
        result = CurationTaskManager._task_to_dict(task)
        assert result["task_properties"]["type"] == "file-based"
        assert result["task_properties"]["upload_folder_id"] == "syn456"
        assert result["task_properties"]["file_view_id"] == "syn789"

    def test_record_based_properties(self):
        props = SimpleNamespace(record_set_id="rs-100")
        task = _make_task(task_properties=props)
        result = CurationTaskManager._task_to_dict(task)
        assert result["task_properties"]["type"] == "record-based"
        assert result["task_properties"]["record_set_id"] == "rs-100"


class TestListTasks:
    @patch("synapse_mcp.managers.curation_task_manager.CurationTask")
    def test_returns_list_of_dicts(self, mock_ct_cls):
        props = SimpleNamespace(upload_folder_id="syn10", file_view_id="syn11")
        mock_ct_cls.list.return_value = [
            _make_task(task_id=1, task_properties=props),
            _make_task(task_id=2, task_properties=None),
        ]
        client = MagicMock()
        result = CurationTaskManager(client).list_tasks("syn123")
        assert len(result) == 2
        assert result[0]["task_id"] == 1
        assert result[1]["task_id"] == 2
        mock_ct_cls.list.assert_called_once_with(
            project_id="syn123", synapse_client=client
        )


class TestGetTask:
    @patch("synapse_mcp.managers.curation_task_manager.CurationTask")
    def test_returns_task_dict(self, mock_ct_cls):
        task = _make_task(task_id=42, task_properties=None)
        mock_ct_cls.return_value.get.return_value = task
        client = MagicMock()
        result = CurationTaskManager(client).get_task(42)
        assert result["task_id"] == 42


class TestGetTaskResources:
    @patch("synapse_mcp.managers.curation_task_manager.Folder")
    @patch("synapse_mcp.managers.curation_task_manager.EntityView")
    @patch("synapse_mcp.managers.curation_task_manager.CurationTask")
    def test_file_based_resources(self, mock_ct_cls, mock_ev_cls, mock_folder_cls):
        props = SimpleNamespace(upload_folder_id="syn10", file_view_id="syn11")
        task = _make_task(task_id=1, task_properties=props)
        mock_ct_cls.return_value.get.return_value = task
        mock_folder_cls.return_value.get.return_value = {"id": "syn10", "name": "uploads"}
        mock_ev_cls.return_value.get.return_value = {"id": "syn11", "name": "view"}

        client = MagicMock()
        result = CurationTaskManager(client).get_task_resources(1)

        assert result["resources"]["type"] == "file-based"
        assert result["resources"]["upload_folder"]["id"] == "syn10"
        assert result["resources"]["file_view"]["id"] == "syn11"

    @patch("synapse_mcp.managers.curation_task_manager.RecordSet")
    @patch("synapse_mcp.managers.curation_task_manager.CurationTask")
    def test_record_based_resources(self, mock_ct_cls, mock_rs_cls):
        props = SimpleNamespace(record_set_id="rs-5")
        task = _make_task(task_id=2, task_properties=props)
        mock_ct_cls.return_value.get.return_value = task
        mock_rs_cls.return_value.get.return_value = {"id": "rs-5", "name": "records"}

        client = MagicMock()
        result = CurationTaskManager(client).get_task_resources(2)

        assert result["resources"]["type"] == "record-based"
        assert result["resources"]["record_set"]["id"] == "rs-5"

    @patch("synapse_mcp.managers.curation_task_manager.Folder")
    @patch("synapse_mcp.managers.curation_task_manager.CurationTask")
    def test_sub_resource_error_is_captured(self, mock_ct_cls, mock_folder_cls):
        props = SimpleNamespace(upload_folder_id="syn10", file_view_id=None)
        task = _make_task(task_id=3, task_properties=props)
        mock_ct_cls.return_value.get.return_value = task
        mock_folder_cls.return_value.get.side_effect = RuntimeError("not found")

        client = MagicMock()
        result = CurationTaskManager(client).get_task_resources(3)

        assert result["resources"]["upload_folder"]["error"] == "not found"
        assert result["resources"]["upload_folder"]["id"] == "syn10"
