"""Tests for CurationTaskManager.get_task_with_resources.

Verifies multi-step orchestration: fetch task, inspect its property type,
fetch related Synapse resources, and handle partial failures gracefully.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from synapse_mcp.managers.curation_task_manager import CurationTaskManager

MGR = "synapse_mcp.managers.curation_task_manager"


def _file_based_properties(upload_folder_id="syn100", file_view_id="syn200"):
    """Simulate a file-based CurationTask's task_properties."""
    return SimpleNamespace(
        upload_folder_id=upload_folder_id,
        file_view_id=file_view_id,
    )


def _record_based_properties(record_set_id="syn300"):
    """Simulate a record-based CurationTask's task_properties."""
    return SimpleNamespace(record_set_id=record_set_id)


def _make_task(*, task_id=1, task_properties=None, **overrides):
    """Build a fake CurationTask model object."""
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
    defaults.update(overrides)
    return SimpleNamespace(
        task_id=task_id,
        task_properties=task_properties,
        **defaults,
    )


class TestFileBasedTasks:
    @patch(f"{MGR}.EntityView")
    @patch(f"{MGR}.Folder")
    @patch(f"{MGR}.CurationTask")
    def test_given_file_based_task_when_both_resources_exist_then_returns_folder_and_view(
        self, mock_ct, mock_folder, mock_ev
    ):
        # GIVEN a file-based curation task with an upload folder and file view
        task = _make_task(
            task_id=1,
            task_properties=_file_based_properties("syn100", "syn200"),
        )
        mock_ct.return_value.get.return_value = task
        mock_folder.return_value.get.return_value = SimpleNamespace(
            id="syn100", name="uploads"
        )
        mock_ev.return_value.get.return_value = SimpleNamespace(
            id="syn200", name="view"
        )

        # WHEN we fetch the task with resources
        result_task, resources = CurationTaskManager(
            MagicMock()
        ).get_task_with_resources(1)

        # THEN the task is returned with both resources populated
        assert result_task.task_id == 1
        assert resources["type"] == "file-based"
        assert resources["upload_folder"].id == "syn100"
        assert resources["file_view"].id == "syn200"

    @patch(f"{MGR}.Folder")
    @patch(f"{MGR}.CurationTask")
    def test_given_file_based_task_when_folder_fetch_fails_then_captures_error_with_id(
        self, mock_ct, mock_folder
    ):
        # GIVEN a file-based task whose upload folder cannot be fetched
        task = _make_task(
            task_id=2,
            task_properties=_file_based_properties("syn100", None),
        )
        mock_ct.return_value.get.return_value = task
        mock_folder.return_value.get.side_effect = RuntimeError("not found")

        # WHEN we fetch the task with resources
        _, resources = CurationTaskManager(
            MagicMock()
        ).get_task_with_resources(2)

        # THEN the folder entry contains the error message and the original ID
        assert resources["upload_folder"]["error"] == "not found"
        assert resources["upload_folder"]["id"] == "syn100"

    @patch(f"{MGR}.EntityView")
    @patch(f"{MGR}.Folder")
    @patch(f"{MGR}.CurationTask")
    def test_given_file_based_task_when_view_fails_then_folder_is_still_returned(
        self, mock_ct, mock_folder, mock_ev
    ):
        # GIVEN a file-based task where the folder succeeds but the view fails
        task = _make_task(
            task_id=3,
            task_properties=_file_based_properties("syn100", "syn200"),
        )
        mock_ct.return_value.get.return_value = task
        mock_folder.return_value.get.return_value = SimpleNamespace(
            id="syn100", name="uploads"
        )
        mock_ev.return_value.get.side_effect = RuntimeError("view unavailable")

        # WHEN we fetch the task with resources
        _, resources = CurationTaskManager(
            MagicMock()
        ).get_task_with_resources(3)

        # THEN the folder is returned successfully and the view has an error
        assert resources["upload_folder"].id == "syn100"
        assert resources["file_view"]["error"] == "view unavailable"
        assert resources["file_view"]["id"] == "syn200"


class TestRecordBasedTasks:
    @patch(f"{MGR}.RecordSet")
    @patch(f"{MGR}.CurationTask")
    def test_given_record_based_task_when_record_set_exists_then_returns_it(
        self, mock_ct, mock_rs
    ):
        # GIVEN a record-based curation task with a valid record set
        task = _make_task(
            task_id=4,
            task_properties=_record_based_properties("syn300"),
        )
        mock_ct.return_value.get.return_value = task
        mock_rs.return_value.get.return_value = SimpleNamespace(
            id="syn300", name="records"
        )

        # WHEN we fetch the task with resources
        _, resources = CurationTaskManager(
            MagicMock()
        ).get_task_with_resources(4)

        # THEN the record set is returned
        assert resources["type"] == "record-based"
        assert resources["record_set"].id == "syn300"

    @patch(f"{MGR}.RecordSet")
    @patch(f"{MGR}.CurationTask")
    def test_given_record_based_task_when_record_set_fetch_fails_then_captures_error(
        self, mock_ct, mock_rs
    ):
        # GIVEN a record-based task whose record set cannot be fetched
        task = _make_task(
            task_id=5,
            task_properties=_record_based_properties("syn300"),
        )
        mock_ct.return_value.get.return_value = task
        mock_rs.return_value.get.side_effect = RuntimeError("unavailable")

        # WHEN we fetch the task with resources
        _, resources = CurationTaskManager(
            MagicMock()
        ).get_task_with_resources(5)

        # THEN the record_set entry contains the error and original ID
        assert resources["record_set"]["error"] == "unavailable"
        assert resources["record_set"]["id"] == "syn300"


class TestTaskWithNoProperties:
    @patch(f"{MGR}.CurationTask")
    def test_given_task_with_no_properties_when_fetched_then_returns_empty_resources(
        self, mock_ct
    ):
        # GIVEN a curation task with task_properties=None
        task = _make_task(task_id=6, task_properties=None)
        mock_ct.return_value.get.return_value = task

        # WHEN we fetch the task with resources
        _, resources = CurationTaskManager(
            MagicMock()
        ).get_task_with_resources(6)

        # THEN no resources are returned
        assert resources == {}
