"""Tests for CurationTaskService.

Verifies serialization (model → dict), error boundary behavior,
and delegation to CurationTaskManager for resource fetching.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from synapse_mcp.connection_auth import ConnectionAuthError
from synapse_mcp.services.curation_task_service import (
    CurationTaskService,
    _format_task,
    _format_task_properties,
)

SVC = "synapse_mcp.services.curation_task_service"
TS = "synapse_mcp.services.tool_service"


# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------


def _file_based_properties(upload_folder_id="syn100", file_view_id="syn200"):
    """Simulate a file-based CurationTask's task_properties."""
    return SimpleNamespace(
        upload_folder_id=upload_folder_id,
        file_view_id=file_view_id,
    )


def _record_based_properties(record_set_id="syn300"):
    """Simulate a record-based CurationTask's task_properties."""
    return SimpleNamespace(record_set_id=record_set_id)


def _make_task(
    *,
    task_id=1,
    data_type="DataType",
    project_id="syn999",
    instructions="Do curation",
    etag="abc123",
    created_on="2024-01-01",
    modified_on="2024-01-02",
    created_by="user1",
    modified_by="user2",
    task_properties=None,
):
    """Build a fake CurationTask model object."""
    return SimpleNamespace(
        task_id=task_id,
        data_type=data_type,
        project_id=project_id,
        instructions=instructions,
        etag=etag,
        created_on=created_on,
        modified_on=modified_on,
        created_by=created_by,
        modified_by=modified_by,
        task_properties=task_properties,
    )


# -------------------------------------------------------------------
# _format_task_properties
# -------------------------------------------------------------------


class TestFormatTaskProperties:
    def test_given_file_based_properties_then_returns_typed_dict_with_folder_and_view(
        self,
    ):
        # GIVEN task_properties with upload_folder_id and file_view_id
        props = _file_based_properties("syn100", "syn200")

        # WHEN formatted
        result = _format_task_properties(props)

        # THEN it returns a dict tagged as file-based with both IDs
        assert result == {
            "type": "file-based",
            "upload_folder_id": "syn100",
            "file_view_id": "syn200",
        }

    def test_given_record_based_properties_then_returns_typed_dict_with_record_set(
        self,
    ):
        # GIVEN task_properties with record_set_id
        props = _record_based_properties("syn300")

        # WHEN formatted
        result = _format_task_properties(props)

        # THEN it returns a dict tagged as record-based with the ID
        assert result == {
            "type": "record-based",
            "record_set_id": "syn300",
        }

    def test_given_none_then_returns_empty_dict(self):
        # GIVEN task_properties is None
        # WHEN formatted
        result = _format_task_properties(None)

        # THEN it returns an empty dict
        assert result == {}


# -------------------------------------------------------------------
# _format_task
# -------------------------------------------------------------------


class TestFormatTask:
    def test_given_task_with_properties_then_all_fields_are_serialized(self):
        # GIVEN a CurationTask model with file-based properties
        task = _make_task(task_id=42, task_properties=_file_based_properties())

        # WHEN formatted
        result = _format_task(task)

        # THEN all metadata fields and task_properties are included
        assert result["task_id"] == 42
        assert result["data_type"] == "DataType"
        assert result["project_id"] == "syn999"
        assert result["instructions"] == "Do curation"
        assert result["etag"] == "abc123"
        assert result["task_properties"]["type"] == "file-based"

    def test_given_task_with_no_properties_then_task_properties_key_is_omitted(self):
        # GIVEN a CurationTask model with task_properties=None
        task = _make_task(task_properties=None)

        # WHEN formatted
        result = _format_task(task)

        # THEN the task_properties key is absent (not set to None or {})
        assert "task_properties" not in result


# -------------------------------------------------------------------
# CurationTaskService.list_tasks
# -------------------------------------------------------------------


class TestListTasks:
    @patch(f"{TS}.get_synapse_client")
    @patch(f"{SVC}.CurationTask")
    def test_given_project_with_tasks_when_listed_then_returns_formatted_dicts(
        self, mock_ct, mock_get_client
    ):
        # GIVEN a project containing one file-based and one record-based task
        mock_get_client.return_value = MagicMock()
        mock_ct.list.return_value = iter(
            [
                _make_task(task_id=1, task_properties=_file_based_properties()),
                _make_task(task_id=2, task_properties=_record_based_properties()),
            ]
        )

        # WHEN we list tasks for the project
        result = CurationTaskService().list_tasks(MagicMock(), "syn999")

        # THEN both tasks are returned as serialized dicts with correct types
        assert len(result) == 2
        assert result[0]["task_id"] == 1
        assert result[0]["task_properties"]["type"] == "file-based"
        assert result[1]["task_id"] == 2
        assert result[1]["task_properties"]["type"] == "record-based"

    @patch(f"{TS}.get_synapse_client")
    @patch(f"{SVC}.CurationTask")
    def test_given_project_with_no_tasks_when_listed_then_returns_empty_list(
        self, mock_ct, mock_get_client
    ):
        # GIVEN a project with no curation tasks
        mock_get_client.return_value = MagicMock()
        mock_ct.list.return_value = iter([])

        # WHEN we list tasks
        result = CurationTaskService().list_tasks(MagicMock(), "syn999")

        # THEN an empty list is returned
        assert result == []

    @patch(f"{TS}.get_synapse_client")
    def test_given_expired_auth_when_listing_then_returns_error_list_with_project_id(
        self, mock_get_client
    ):
        # GIVEN expired credentials
        mock_get_client.side_effect = ConnectionAuthError("expired")

        # WHEN we list tasks for project syn123
        result = CurationTaskService().list_tasks(MagicMock(), "syn123")

        # THEN the error is returned as a single-item list (matching List return type)
        # and includes the project_id for debugging context
        assert isinstance(result, list)
        assert len(result) == 1
        assert "Authentication required" in result[0]["error"]
        assert result[0]["project_id"] == "syn123"

    @patch(f"{TS}.get_synapse_client")
    @patch(f"{SVC}.CurationTask")
    def test_given_sdk_error_when_listing_then_returns_error_list_with_type(
        self, mock_ct, mock_get_client
    ):
        # GIVEN the SDK raises a RuntimeError during listing
        mock_get_client.return_value = MagicMock()
        mock_ct.list.side_effect = RuntimeError("boom")

        # WHEN we list tasks
        result = CurationTaskService().list_tasks(MagicMock(), "syn123")

        # THEN the error is wrapped in a list with the exception type
        assert isinstance(result, list)
        assert result[0]["error"] == "boom"
        assert result[0]["error_type"] == "RuntimeError"


# -------------------------------------------------------------------
# CurationTaskService.get_task
# -------------------------------------------------------------------


class TestGetTask:
    @patch(f"{TS}.get_synapse_client")
    @patch(f"{SVC}.CurationTask")
    def test_given_valid_task_id_when_fetched_then_returns_formatted_dict(
        self, mock_ct, mock_get_client
    ):
        # GIVEN a curation task with ID 42 exists
        mock_get_client.return_value = MagicMock()
        mock_ct.return_value.get.return_value = _make_task(
            task_id=42, task_properties=_file_based_properties()
        )

        # WHEN we get the task
        result = CurationTaskService().get_task(MagicMock(), 42)

        # THEN it returns the serialized task dict
        assert result["task_id"] == 42
        assert result["task_properties"]["type"] == "file-based"

    @patch(f"{TS}.get_synapse_client")
    def test_given_expired_auth_when_getting_task_then_returns_error_with_task_id(
        self, mock_get_client
    ):
        # GIVEN expired credentials
        mock_get_client.side_effect = ConnectionAuthError("expired")

        # WHEN we get task 42
        result = CurationTaskService().get_task(MagicMock(), 42)

        # THEN the error response includes the task_id for debugging
        assert "Authentication required" in result["error"]
        assert result["task_id"] == 42


# -------------------------------------------------------------------
# CurationTaskService.get_task_resources
# -------------------------------------------------------------------


class TestGetTaskResources:
    @patch(f"{TS}.get_synapse_client")
    @patch(f"{SVC}.CurationTaskManager")
    def test_given_valid_task_when_fetching_resources_then_delegates_to_manager(
        self, mock_mgr_cls, mock_get_client
    ):
        # GIVEN the manager returns a task and its resources
        mock_get_client.return_value = MagicMock()
        task = _make_task(task_id=1)
        resources = {"type": "file-based", "upload_folder": {}}
        mock_mgr_cls.return_value.get_task_with_resources.return_value = (
            task,
            resources,
        )

        # WHEN we get the task resources
        result = CurationTaskService().get_task_resources(MagicMock(), 1)

        # THEN the response includes task metadata and the resources from the manager
        assert result["task_id"] == 1
        assert result["resources"] is resources

    @patch(f"{TS}.get_synapse_client")
    def test_given_expired_auth_when_fetching_resources_then_returns_error_with_task_id(
        self, mock_get_client
    ):
        # GIVEN expired credentials
        mock_get_client.side_effect = ConnectionAuthError("expired")

        # WHEN we get resources for task 1
        result = CurationTaskService().get_task_resources(MagicMock(), 1)

        # THEN the error response includes the task_id
        assert "Authentication required" in result["error"]
        assert result["task_id"] == 1

    @patch(f"{TS}.get_synapse_client")
    @patch(f"{SVC}.CurationTaskManager")
    def test_given_manager_raises_when_fetching_resources_then_returns_error_with_task_id(
        self, mock_mgr_cls, mock_get_client
    ):
        # GIVEN the manager raises a ValueError
        mock_get_client.return_value = MagicMock()
        mock_mgr_cls.return_value.get_task_with_resources.side_effect = ValueError(
            "bad"
        )

        # WHEN we get resources for task 5
        result = CurationTaskService().get_task_resources(MagicMock(), 5)

        # THEN the error is captured with the task_id for debugging
        assert result["error"] == "bad"
        assert result["task_id"] == 5
