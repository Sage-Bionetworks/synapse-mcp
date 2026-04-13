"""Tests for CurationTaskService.

Verifies serialization (model -> dict), error boundary behavior,
and delegation to CurationTaskManager for resource fetching.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from conftest import file_based_properties, make_task, record_based_properties
from synapse_mcp.connection_auth import ConnectionAuthError
from synapse_mcp.services.curation_task_service import (
    CurationTaskService,
    _format_task,
)

SVC = "synapse_mcp.services.curation_task_service"
TS = "synapse_mcp.services.tool_service"

pytestmark = pytest.mark.anyio("asyncio")


@pytest.fixture
def anyio_backend():
    return "asyncio"


# -------------------------------------------------------------------
# _format_task
# -------------------------------------------------------------------


class TestFormatTask:
    def test_given_task_with_file_based_properties_then_all_fields_are_serialized(self):
        # GIVEN a CurationTask model with file-based properties
        task = make_task(task_id=42, task_properties=file_based_properties())

        # WHEN formatted
        result = _format_task(task)

        # THEN all metadata fields and task_properties are included
        assert result["task_id"] == 42
        assert result["data_type"] == "DataType"
        assert result["project_id"] == "syn999"
        assert result["instructions"] == "Do curation"
        assert result["etag"] == "abc123"
        assert result["task_properties"]["type"] == "file-based"
        assert result["task_properties"]["upload_folder_id"] == "syn100"
        assert result["task_properties"]["file_view_id"] == "syn200"

    def test_given_task_with_record_based_properties_then_type_and_id_are_included(
        self,
    ):
        # GIVEN a CurationTask model with record-based properties
        task = make_task(task_id=10, task_properties=record_based_properties("syn300"))

        # WHEN formatted
        result = _format_task(task)

        # THEN task_properties is tagged as record-based with the record_set_id
        assert result["task_properties"]["type"] == "record-based"
        assert result["task_properties"]["record_set_id"] == "syn300"

    def test_given_task_with_no_properties_then_task_properties_is_none(self):
        # GIVEN a CurationTask model with task_properties=None
        task = make_task(task_properties=None)

        # WHEN formatted
        result = _format_task(task)

        # THEN task_properties is None (not a dict)
        assert result["task_properties"] is None


# -------------------------------------------------------------------
# CurationTaskService.list_tasks
# -------------------------------------------------------------------


class TestListTasks:
    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.CurationTask")
    async def test_given_project_with_tasks_when_listed_then_returns_formatted_dicts(
        self, mock_ct, mock_get_client
    ):
        # GIVEN a project containing one file-based and one record-based task
        mock_get_client.return_value = MagicMock()

        async def _list_tasks(**kwargs):
            for t in [
                make_task(task_id=1, task_properties=file_based_properties()),
                make_task(task_id=2, task_properties=record_based_properties()),
            ]:
                yield t

        mock_ct.list_async.return_value = _list_tasks()

        # WHEN we list tasks for the project
        result = await CurationTaskService().list_tasks(MagicMock(), "syn999")

        # THEN both tasks are returned as serialized dicts with correct types
        assert len(result) == 2
        assert result[0]["task_id"] == 1
        assert result[0]["task_properties"]["type"] == "file-based"
        assert result[1]["task_id"] == 2
        assert result[1]["task_properties"]["type"] == "record-based"

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.CurationTask")
    async def test_given_project_with_no_tasks_when_listed_then_returns_empty_list(
        self, mock_ct, mock_get_client
    ):
        # GIVEN a project with no curation tasks
        mock_get_client.return_value = MagicMock()

        async def _empty(**kwargs):
            return
            yield  # noqa: make it an async generator

        mock_ct.list_async.return_value = _empty()

        # WHEN we list tasks
        result = await CurationTaskService().list_tasks(MagicMock(), "syn999")

        # THEN an empty list is returned
        assert result == []

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    async def test_given_expired_auth_when_listing_then_returns_error_list_with_project_id(
        self, mock_get_client
    ):
        # GIVEN expired credentials
        mock_get_client.side_effect = ConnectionAuthError("expired")

        # WHEN we list tasks for project syn123
        result = await CurationTaskService().list_tasks(MagicMock(), "syn123")

        # THEN the error is returned as a single-item list (matching List return type)
        # and includes the project_id for debugging context
        assert isinstance(result, list)
        assert len(result) == 1
        assert "Authentication required" in result[0]["error"]
        assert result[0]["project_id"] == "syn123"

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.CurationTask")
    async def test_given_sdk_error_when_listing_then_returns_error_list_with_type(
        self, mock_ct, mock_get_client
    ):
        # GIVEN the SDK raises a RuntimeError during listing
        mock_get_client.return_value = MagicMock()

        async def _raise_error(**kwargs):
            raise RuntimeError("boom")
            yield  # noqa: make it an async generator

        mock_ct.list_async.return_value = _raise_error()

        # WHEN we list tasks
        result = await CurationTaskService().list_tasks(MagicMock(), "syn123")

        # THEN the error is wrapped in a list with the exception type
        assert isinstance(result, list)
        assert result[0]["error"] == "boom"
        assert result[0]["error_type"] == "RuntimeError"


# -------------------------------------------------------------------
# CurationTaskService.get_task
# -------------------------------------------------------------------


class TestGetTask:
    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.CurationTask")
    async def test_given_valid_task_id_when_fetched_then_returns_formatted_dict(
        self, mock_ct, mock_get_client
    ):
        # GIVEN a curation task with ID 42 exists
        mock_get_client.return_value = MagicMock()
        mock_ct.return_value.get_async = AsyncMock(
            return_value=make_task(
                task_id=42, task_properties=file_based_properties()
            )
        )

        # WHEN we get the task
        result = await CurationTaskService().get_task(MagicMock(), 42)

        # THEN it returns the serialized task dict
        assert result["task_id"] == 42
        assert result["task_properties"]["type"] == "file-based"

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    async def test_given_expired_auth_when_getting_task_then_returns_error_with_task_id(
        self, mock_get_client
    ):
        # GIVEN expired credentials
        mock_get_client.side_effect = ConnectionAuthError("expired")

        # WHEN we get task 42
        result = await CurationTaskService().get_task(MagicMock(), 42)

        # THEN the error response includes the task_id for debugging
        assert "Authentication required" in result["error"]
        assert result["task_id"] == 42


# -------------------------------------------------------------------
# CurationTaskService.get_task_resources
# -------------------------------------------------------------------


class TestGetTaskResources:
    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.CurationTaskManager")
    async def test_given_valid_task_when_fetching_resources_then_delegates_to_manager(
        self, mock_mgr_cls, mock_get_client
    ):
        # GIVEN the manager returns a task and its resources
        mock_get_client.return_value = MagicMock()
        task = make_task(task_id=1)
        resources = {"type": "file-based", "upload_folder": {}}
        mock_mgr_cls.return_value.get_task_with_resources = AsyncMock(
            return_value=(task, resources)
        )

        # WHEN we get the task resources
        result = await CurationTaskService().get_task_resources(MagicMock(), 1)

        # THEN the response includes all task metadata fields and resources
        assert result["task_id"] == 1
        assert result["etag"] == "abc123"
        assert result["created_by"] == "user1"
        assert result["resources"] == resources

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    async def test_given_expired_auth_when_fetching_resources_then_returns_error_with_task_id(
        self, mock_get_client
    ):
        # GIVEN expired credentials
        mock_get_client.side_effect = ConnectionAuthError("expired")

        # WHEN we get resources for task 1
        result = await CurationTaskService().get_task_resources(MagicMock(), 1)

        # THEN the error response includes the task_id
        assert "Authentication required" in result["error"]
        assert result["task_id"] == 1

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.CurationTaskManager")
    async def test_given_manager_raises_when_fetching_resources_then_returns_error_with_task_id(
        self, mock_mgr_cls, mock_get_client
    ):
        # GIVEN the manager raises a ValueError
        mock_get_client.return_value = MagicMock()
        mock_mgr_cls.return_value.get_task_with_resources = AsyncMock(
            side_effect=ValueError("bad")
        )

        # WHEN we get resources for task 5
        result = await CurationTaskService().get_task_resources(MagicMock(), 5)

        # THEN the error is captured with the task_id for debugging
        assert result["error"] == "bad"
        assert result["task_id"] == 5
