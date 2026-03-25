"""Tests for CurationTaskManager.

Manager tests mock synapseclient models at module level and verify
API call delegation and that raw model objects are returned.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

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


class TestListTasks:
    @patch("synapse_mcp.managers.curation_task_manager.CurationTask")
    def test_yields_task_objects(self, mock_ct_cls):
        tasks = [_make_task(task_id=1), _make_task(task_id=2)]
        mock_ct_cls.list.return_value = iter(tasks)
        client = MagicMock()

        result = list(CurationTaskManager(client).list_tasks("syn123"))

        assert len(result) == 2
        assert result[0].task_id == 1
        assert result[1].task_id == 2
        mock_ct_cls.list.assert_called_once_with(
            project_id="syn123", synapse_client=client
        )

    @patch("synapse_mcp.managers.curation_task_manager.CurationTask")
    def test_empty_project(self, mock_ct_cls):
        mock_ct_cls.list.return_value = iter([])
        client = MagicMock()

        result = list(CurationTaskManager(client).list_tasks("syn999"))

        assert result == []


class TestGetTask:
    @patch("synapse_mcp.managers.curation_task_manager.CurationTask")
    def test_returns_task_object(self, mock_ct_cls):
        task = _make_task(task_id=42)
        mock_ct_cls.return_value.get.return_value = task
        client = MagicMock()

        result = CurationTaskManager(client).get_task(42)

        assert result.task_id == 42


class TestGetFolder:
    @patch("synapse_mcp.managers.curation_task_manager.Folder")
    def test_returns_folder(self, mock_folder_cls):
        folder = SimpleNamespace(id="syn100", name="uploads")
        mock_folder_cls.return_value.get.return_value = folder
        client = MagicMock()

        result = CurationTaskManager(client).get_folder("syn100")

        assert result.id == "syn100"


class TestGetEntityView:
    @patch("synapse_mcp.managers.curation_task_manager.EntityView")
    def test_returns_view(self, mock_ev_cls):
        view = SimpleNamespace(id="syn200", name="view")
        mock_ev_cls.return_value.get.return_value = view
        client = MagicMock()

        result = CurationTaskManager(client).get_entity_view("syn200")

        assert result.id == "syn200"


class TestGetRecordSet:
    @patch("synapse_mcp.managers.curation_task_manager.RecordSet")
    def test_returns_record_set(self, mock_rs_cls):
        rs = SimpleNamespace(id="syn300", name="records")
        mock_rs_cls.return_value.get.return_value = rs
        client = MagicMock()

        result = CurationTaskManager(client).get_record_set("syn300")

        assert result.id == "syn300"
