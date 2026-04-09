"""Tests for CurationTaskService.

Verifies error boundary behavior, delegation to
CurationTaskManager, and consistent serialization
via serialize_model.
"""

from dataclasses import dataclass, field
from typing import Optional
from unittest.mock import MagicMock, patch

from conftest import file_based_properties, make_task, record_based_properties
from synapse_mcp.connection_auth import ConnectionAuthError
from synapse_mcp.services.curation_task_service import (
    CurationTaskService,
)

SVC = "synapse_mcp.services.curation_task_service"
TS = "synapse_mcp.services.tool_service"


# -------------------------------------------------------------------
# Dataclass fixtures (serialize_model requires real dataclasses)
# -------------------------------------------------------------------


@dataclass
class FakeFileBasedProps:
    upload_folder_id: str = "syn100"
    file_view_id: str = "syn200"


@dataclass
class FakeRecordBasedProps:
    record_set_id: str = "syn300"


@dataclass
class FakeTask:
    task_id: int = 1
    data_type: str = "DataType"
    project_id: str = "syn999"
    instructions: str = "Do curation"
    etag: str = "abc123"
    created_on: str = "2024-01-01"
    modified_on: str = "2024-01-02"
    created_by: str = "user1"
    modified_by: str = "user2"
    task_properties: Optional[object] = None


# -------------------------------------------------------------------
# CurationTaskService.list_tasks
# -------------------------------------------------------------------


class TestListTasks:
    @patch(f"{TS}.get_synapse_client")
    @patch(f"{SVC}.CurationTask")
    def test_given_project_with_tasks_when_listed_then_returns_serialized_dicts(
        self, mock_ct, mock_get_client
    ):
        # GIVEN a project with file-based and record-based tasks
        mock_get_client.return_value = MagicMock()
        mock_ct.list.return_value = iter(
            [
                FakeTask(
                    task_id=1,
                    task_properties=FakeFileBasedProps(),
                ),
                FakeTask(
                    task_id=2,
                    task_properties=FakeRecordBasedProps(),
                ),
            ]
        )

        # WHEN we list tasks for the project
        result = CurationTaskService().list_tasks(
            MagicMock(), "syn999"
        )

        # THEN both tasks are returned with all fields serialized
        assert len(result) == 2
        assert result[0]["task_id"] == 1
        assert result[0]["task_properties"]["upload_folder_id"] == "syn100"
        assert result[1]["task_id"] == 2
        assert result[1]["task_properties"]["record_set_id"] == "syn300"

    @patch(f"{TS}.get_synapse_client")
    @patch(f"{SVC}.CurationTask")
    def test_given_project_with_no_tasks_when_listed_then_returns_empty_list(
        self, mock_ct, mock_get_client
    ):
        # GIVEN a project with no curation tasks
        mock_get_client.return_value = MagicMock()
        mock_ct.list.return_value = iter([])

        # WHEN we list tasks
        result = CurationTaskService().list_tasks(
            MagicMock(), "syn999"
        )

        # THEN an empty list is returned
        assert result == []

    @patch(f"{TS}.get_synapse_client")
    def test_given_expired_auth_when_listing_then_returns_error_list_with_project_id(
        self, mock_get_client
    ):
        # GIVEN expired credentials
        mock_get_client.side_effect = ConnectionAuthError(
            "expired"
        )

        # WHEN we list tasks for project syn123
        result = CurationTaskService().list_tasks(
            MagicMock(), "syn123"
        )

        # THEN the error is wrapped in a list with project_id
        assert isinstance(result, list)
        assert len(result) == 1
        assert "Authentication required" in result[0]["error"]
        assert result[0]["project_id"] == "syn123"

    @patch(f"{TS}.get_synapse_client")
    @patch(f"{SVC}.CurationTask")
    def test_given_sdk_error_when_listing_then_returns_error_list_with_type(
        self, mock_ct, mock_get_client
    ):
        # GIVEN the SDK raises a RuntimeError
        mock_get_client.return_value = MagicMock()
        mock_ct.list.side_effect = RuntimeError("boom")

        # WHEN we list tasks
        result = CurationTaskService().list_tasks(
            MagicMock(), "syn123"
        )

        # THEN the error is wrapped in a list with type
        assert isinstance(result, list)
        assert result[0]["error"] == "boom"
        assert result[0]["error_type"] == "RuntimeError"


# -------------------------------------------------------------------
# CurationTaskService.get_task
# -------------------------------------------------------------------


class TestGetTask:
    @patch(f"{TS}.get_synapse_client")
    @patch(f"{SVC}.CurationTask")
    def test_given_valid_task_id_when_fetched_then_returns_serialized_dict(
        self, mock_ct, mock_get_client
    ):
        # GIVEN a curation task with ID 42
        mock_get_client.return_value = MagicMock()
        mock_ct.return_value.get.return_value = FakeTask(
            task_id=42,
            task_properties=FakeFileBasedProps(),
        )

        # WHEN we get the task
        result = CurationTaskService().get_task(
            MagicMock(), 42
        )

        # THEN all fields are serialized including properties
        assert result["task_id"] == 42
        assert result["task_properties"]["upload_folder_id"] == "syn100"

    @patch(f"{TS}.get_synapse_client")
    def test_given_expired_auth_when_getting_task_then_returns_error_with_task_id(
        self, mock_get_client
    ):
        # GIVEN expired credentials
        mock_get_client.side_effect = ConnectionAuthError(
            "expired"
        )

        # WHEN we get task 42
        result = CurationTaskService().get_task(
            MagicMock(), 42
        )

        # THEN the error includes the task_id
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
        # GIVEN the manager returns a task and resources
        mock_get_client.return_value = MagicMock()
        task = FakeTask(task_id=1)
        resources = {
            "type": "file-based",
            "upload_folder": {},
        }
        mock_mgr_cls.return_value.get_task_with_resources.return_value = (
            task,
            resources,
        )

        # WHEN we get the task resources
        result = CurationTaskService().get_task_resources(
            MagicMock(), 1
        )

        # THEN the response includes task metadata and resources
        assert result["task_id"] == 1
        assert result["resources"]["type"] == "file-based"

    @patch(f"{TS}.get_synapse_client")
    def test_given_expired_auth_when_fetching_resources_then_returns_error_with_task_id(
        self, mock_get_client
    ):
        # GIVEN expired credentials
        mock_get_client.side_effect = ConnectionAuthError(
            "expired"
        )

        # WHEN we get resources for task 1
        result = CurationTaskService().get_task_resources(
            MagicMock(), 1
        )

        # THEN the error includes the task_id
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
        result = CurationTaskService().get_task_resources(
            MagicMock(), 5
        )

        # THEN the error is captured with task_id
        assert result["error"] == "bad"
        assert result["task_id"] == 5
