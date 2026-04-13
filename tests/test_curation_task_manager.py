"""Tests for CurationTaskManager.get_task_with_resources.

Verifies multi-step orchestration: fetch task, inspect its property type,
fetch related Synapse resources, and handle partial failures gracefully.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from conftest import file_based_properties, make_task, record_based_properties
from synapse_mcp.managers.curation_task_manager import CurationTaskManager

MGR = "synapse_mcp.managers.curation_task_manager"

pytestmark = pytest.mark.anyio("asyncio")


@pytest.fixture
def anyio_backend():
    return "asyncio"


class TestFileBasedTasks:
    @patch(f"{MGR}.EntityView")
    @patch(f"{MGR}.Folder")
    @patch(f"{MGR}.CurationTask")
    async def test_given_file_based_task_when_both_resources_exist_then_returns_folder_and_view(
        self, mock_ct, mock_folder, mock_ev
    ):
        # GIVEN a file-based curation task with an upload folder and file view
        task = make_task(
            task_id=1,
            task_properties=file_based_properties("syn100", "syn200"),
        )
        mock_ct.return_value.get_async = AsyncMock(return_value=task)
        mock_folder.return_value.get_async = AsyncMock(
            return_value=SimpleNamespace(id="syn100", name="uploads")
        )
        mock_ev.return_value.get_async = AsyncMock(
            return_value=SimpleNamespace(id="syn200", name="view")
        )

        # WHEN we fetch the task with resources
        result_task, resources = await CurationTaskManager(
            MagicMock()
        ).get_task_with_resources(1)

        # THEN the task is returned with both resources populated
        assert result_task.task_id == 1
        assert resources["type"] == "file-based"
        assert resources["upload_folder"].id == "syn100"
        assert resources["file_view"].id == "syn200"

    @patch(f"{MGR}.Folder")
    @patch(f"{MGR}.CurationTask")
    async def test_given_file_based_task_when_folder_fetch_fails_then_captures_error_with_id(
        self, mock_ct, mock_folder
    ):
        # GIVEN a file-based task whose upload folder cannot be fetched
        task = make_task(
            task_id=2,
            task_properties=file_based_properties("syn100", None),
        )
        mock_ct.return_value.get_async = AsyncMock(return_value=task)
        mock_folder.return_value.get_async = AsyncMock(
            side_effect=RuntimeError("not found")
        )

        # WHEN we fetch the task with resources
        _, resources = await CurationTaskManager(
            MagicMock()
        ).get_task_with_resources(2)

        # THEN the folder entry contains the error message and the original ID
        assert resources["upload_folder"]["error"] == "not found"
        assert resources["upload_folder"]["id"] == "syn100"

    @patch(f"{MGR}.EntityView")
    @patch(f"{MGR}.Folder")
    @patch(f"{MGR}.CurationTask")
    async def test_given_file_based_task_when_view_fails_then_folder_is_still_returned(
        self, mock_ct, mock_folder, mock_ev
    ):
        # GIVEN a file-based task where the folder succeeds but the view fails
        task = make_task(
            task_id=3,
            task_properties=file_based_properties("syn100", "syn200"),
        )
        mock_ct.return_value.get_async = AsyncMock(return_value=task)
        mock_folder.return_value.get_async = AsyncMock(
            return_value=SimpleNamespace(id="syn100", name="uploads")
        )
        mock_ev.return_value.get_async = AsyncMock(
            side_effect=RuntimeError("view unavailable")
        )

        # WHEN we fetch the task with resources
        _, resources = await CurationTaskManager(
            MagicMock()
        ).get_task_with_resources(3)

        # THEN the folder is returned successfully and the view has an error
        assert resources["upload_folder"].id == "syn100"
        assert resources["file_view"]["error"] == "view unavailable"
        assert resources["file_view"]["id"] == "syn200"


class TestRecordBasedTasks:
    @patch(f"{MGR}.RecordSet")
    @patch(f"{MGR}.CurationTask")
    async def test_given_record_based_task_when_record_set_exists_then_returns_it(
        self, mock_ct, mock_rs
    ):
        # GIVEN a record-based curation task with a valid record set
        task = make_task(
            task_id=4,
            task_properties=record_based_properties("syn300"),
        )
        mock_ct.return_value.get_async = AsyncMock(return_value=task)
        mock_rs.return_value.get_async = AsyncMock(
            return_value=SimpleNamespace(id="syn300", name="records")
        )

        # WHEN we fetch the task with resources
        _, resources = await CurationTaskManager(
            MagicMock()
        ).get_task_with_resources(4)

        # THEN the record set is returned
        assert resources["type"] == "record-based"
        assert resources["record_set"].id == "syn300"

    @patch(f"{MGR}.RecordSet")
    @patch(f"{MGR}.CurationTask")
    async def test_given_record_based_task_when_record_set_fetch_fails_then_captures_error(
        self, mock_ct, mock_rs
    ):
        # GIVEN a record-based task whose record set cannot be fetched
        task = make_task(
            task_id=5,
            task_properties=record_based_properties("syn300"),
        )
        mock_ct.return_value.get_async = AsyncMock(return_value=task)
        mock_rs.return_value.get_async = AsyncMock(
            side_effect=RuntimeError("unavailable")
        )

        # WHEN we fetch the task with resources
        _, resources = await CurationTaskManager(
            MagicMock()
        ).get_task_with_resources(5)

        # THEN the record_set entry contains the error and original ID
        assert resources["record_set"]["error"] == "unavailable"
        assert resources["record_set"]["id"] == "syn300"


class TestTaskWithNoProperties:
    @patch(f"{MGR}.CurationTask")
    async def test_given_task_with_no_properties_when_fetched_then_returns_empty_resources(
        self, mock_ct
    ):
        # GIVEN a curation task with task_properties=None
        task = make_task(task_id=6, task_properties=None)
        mock_ct.return_value.get_async = AsyncMock(return_value=task)

        # WHEN we fetch the task with resources
        _, resources = await CurationTaskManager(
            MagicMock()
        ).get_task_with_resources(6)

        # THEN no resources are returned
        assert resources == {}
