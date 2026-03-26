"""Tests for CurationTaskManager.get_task_with_resources.

Tests the multi-step orchestration: fetch task, inspect properties,
fetch related resources, handle partial failures.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from synapse_mcp.managers.curation_task_manager import (
    CurationTaskManager,
)


def _file_props(upload_folder_id="syn100", file_view_id="syn200"):
    return SimpleNamespace(
        upload_folder_id=upload_folder_id,
        file_view_id=file_view_id,
    )


def _record_props(record_set_id="syn300"):
    return SimpleNamespace(record_set_id=record_set_id)


def _make_task(*, task_id=1, task_properties=None, **kw):
    defaults = dict(
        data_type="biospecimen",
        project_id="syn123",
        instructions="Fill in",
        etag="abc",
        created_on="2025-01-01",
        modified_on="2025-01-02",
        created_by="user1",
        modified_by="user2",
    )
    defaults.update(kw)
    return SimpleNamespace(
        task_id=task_id,
        task_properties=task_properties,
        **defaults,
    )


MGR = "synapse_mcp.managers.curation_task_manager"


class TestFileBased:
    @patch(f"{MGR}.EntityView")
    @patch(f"{MGR}.Folder")
    @patch(f"{MGR}.CurationTask")
    def test_fetches_folder_and_view(
        self, mock_ct, mock_folder, mock_ev
    ):
        props = _file_props("syn100", "syn200")
        task = _make_task(task_id=1, task_properties=props)
        mock_ct.return_value.get.return_value = task
        folder = SimpleNamespace(id="syn100", name="uploads")
        mock_folder.return_value.get.return_value = folder
        view = SimpleNamespace(id="syn200", name="view")
        mock_ev.return_value.get.return_value = view

        client = MagicMock()
        result_task, resources = (
            CurationTaskManager(client).get_task_with_resources(1)
        )

        assert result_task.task_id == 1
        assert resources["type"] == "file-based"
        assert resources["upload_folder"].id == "syn100"
        assert resources["file_view"].id == "syn200"

    @patch(f"{MGR}.Folder")
    @patch(f"{MGR}.CurationTask")
    def test_folder_failure_captured(self, mock_ct, mock_folder):
        props = _file_props("syn100", None)
        task = _make_task(task_id=2, task_properties=props)
        mock_ct.return_value.get.return_value = task
        mock_folder.return_value.get.side_effect = RuntimeError(
            "not found"
        )

        client = MagicMock()
        _, resources = (
            CurationTaskManager(client).get_task_with_resources(2)
        )

        assert resources["upload_folder"]["error"] == "not found"
        assert resources["upload_folder"]["id"] == "syn100"

    @patch(f"{MGR}.EntityView")
    @patch(f"{MGR}.Folder")
    @patch(f"{MGR}.CurationTask")
    def test_view_failure_does_not_block_folder(
        self, mock_ct, mock_folder, mock_ev
    ):
        props = _file_props("syn100", "syn200")
        task = _make_task(task_id=3, task_properties=props)
        mock_ct.return_value.get.return_value = task
        folder = SimpleNamespace(id="syn100", name="uploads")
        mock_folder.return_value.get.return_value = folder
        mock_ev.return_value.get.side_effect = RuntimeError(
            "view unavailable"
        )

        client = MagicMock()
        _, resources = (
            CurationTaskManager(client).get_task_with_resources(3)
        )

        assert resources["upload_folder"].id == "syn100"
        assert "error" in resources["file_view"]
        assert resources["file_view"]["id"] == "syn200"


class TestRecordBased:
    @patch(f"{MGR}.RecordSet")
    @patch(f"{MGR}.CurationTask")
    def test_fetches_record_set(self, mock_ct, mock_rs):
        props = _record_props("syn300")
        task = _make_task(task_id=4, task_properties=props)
        mock_ct.return_value.get.return_value = task
        rs = SimpleNamespace(id="syn300", name="records")
        mock_rs.return_value.get.return_value = rs

        client = MagicMock()
        _, resources = (
            CurationTaskManager(client).get_task_with_resources(4)
        )

        assert resources["type"] == "record-based"
        assert resources["record_set"].id == "syn300"

    @patch(f"{MGR}.RecordSet")
    @patch(f"{MGR}.CurationTask")
    def test_record_set_failure_captured(self, mock_ct, mock_rs):
        props = _record_props("syn300")
        task = _make_task(task_id=5, task_properties=props)
        mock_ct.return_value.get.return_value = task
        mock_rs.return_value.get.side_effect = RuntimeError(
            "unavailable"
        )

        client = MagicMock()
        _, resources = (
            CurationTaskManager(client).get_task_with_resources(5)
        )

        assert resources["record_set"]["error"] == "unavailable"
        assert resources["record_set"]["id"] == "syn300"


class TestNoProperties:
    @patch(f"{MGR}.CurationTask")
    def test_returns_empty_resources(self, mock_ct):
        task = _make_task(task_id=6, task_properties=None)
        mock_ct.return_value.get.return_value = task

        client = MagicMock()
        _, resources = (
            CurationTaskManager(client).get_task_with_resources(6)
        )

        assert resources == {}
