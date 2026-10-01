"""Tests for CurationTaskManager.get_task_with_resources.

Verifies multi-step orchestration: fetch task, inspect its property type,
fetch related Synapse resources, and handle partial failures gracefully.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from conftest import file_based_properties, make_task, record_based_properties
from synapse_mcp.managers.curation_task_manager import (
    CurationTaskManager,
    RecordBasedTaskCreationError,
    _csv_file_name,
)

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


# -------------------------------------------------------------------
# CurationTaskManager.create_record_based_task
# -------------------------------------------------------------------

SCHEMA_BODY = {
    "properties": {
        "tissue": {"type": "string"},
        "specimenID": {"type": "string"},
        "assay": {"type": "string"},
    }
}


def _client_with_project(project_id="syn1"):
    client = MagicMock()
    client.rest_get_async = AsyncMock(
        return_value={"path": [{"id": "syn4489"}, {"id": project_id}, {"id": "syn50"}]}
    )
    return client


def _no_existing_tasks(mock_ct, existing=()):
    async def list_async(project_id, synapse_client):
        for task in existing:
            yield task

    mock_ct.list_async = list_async


def _mock_schema(mock_schema, body=SCHEMA_BODY):
    schema = mock_schema.from_uri.return_value
    schema.get_async = AsyncMock()
    schema.get_body_async = AsyncMock(return_value=body)
    return schema


class TestCreateRecordBasedTask:
    @patch(f"{MGR}.CurationTask")
    @patch(f"{MGR}.RecordSet")
    @patch(f"{MGR}.JSONSchema")
    async def test_given_valid_inputs_then_creates_templated_record_set_binds_and_creates_task(
        self, mock_schema, mock_rs, mock_ct
    ):
        # GIVEN a folder in project syn1 and a schema with three properties,
        # and the project has a task only for a different data_type
        _mock_schema(mock_schema)
        _no_existing_tasks(mock_ct, [make_task(task_id=3, data_type="OtherType")])
        captured = {}

        async def store_rs(synapse_client):
            with open(mock_rs.call_args.kwargs["path"], encoding="utf-8") as f:
                captured["csv"] = f.read()
            return stored_rs

        stored_rs = MagicMock(id="syn77")
        stored_rs.bind_schema_async = AsyncMock()
        mock_rs.return_value.store_async = store_rs
        created = make_task(task_id=9, task_properties=record_based_properties("syn77"))
        mock_ct.return_value.store_async = AsyncMock(return_value=created)

        # WHEN we create the record-based task
        record_set, task = await CurationTaskManager(
            _client_with_project("syn1")
        ).create_record_based_task(
            folder_id="syn50",
            record_set_name="Biospecimen",
            data_type="Biospecimen",
            schema_uri="org-Biospecimen-1.0.0",
            upsert_keys=["specimenID"],
            instructions="Fill it in",
            assignee_principal_id="3379097",
        )

        # THEN the CSV is a header row with upsert keys first
        assert captured["csv"].strip() == "specimenID,tissue,assay"
        rs_kwargs = mock_rs.call_args.kwargs
        assert rs_kwargs["parent_id"] == "syn50"
        assert rs_kwargs["upsert_keys"] == ["specimenID"]
        # AND the schema is bound to the new RecordSet
        stored_rs.bind_schema_async.assert_awaited_once()
        assert (
            stored_rs.bind_schema_async.call_args.kwargs["json_schema_uri"]
            == "org-Biospecimen-1.0.0"
        )
        # AND the task targets the folder's project and the new RecordSet
        ct_kwargs = mock_ct.call_args.kwargs
        assert ct_kwargs["project_id"] == "syn1"
        assert ct_kwargs["assignee_principal_id"] == "3379097"
        assert ct_kwargs["task_properties"].record_set_id == "syn77"
        assert record_set is stored_rs
        assert task is created

    @patch(f"{MGR}.CurationTask")
    @patch(f"{MGR}.RecordSet")
    @patch(f"{MGR}.JSONSchema")
    async def test_given_bind_schema_false_then_skips_binding(
        self, mock_schema, mock_rs, mock_ct
    ):
        # GIVEN binding is disabled
        _mock_schema(mock_schema)
        _no_existing_tasks(mock_ct)
        stored_rs = MagicMock(id="syn77")
        stored_rs.bind_schema_async = AsyncMock()
        mock_rs.return_value.store_async = AsyncMock(return_value=stored_rs)
        mock_ct.return_value.store_async = AsyncMock(return_value=make_task())

        # WHEN we create the task
        await CurationTaskManager(_client_with_project()).create_record_based_task(
            folder_id="syn50",
            record_set_name="rs",
            data_type="dt",
            schema_uri="org-s-1.0.0",
            upsert_keys=["specimenID"],
            instructions="x",
            bind_schema=False,
        )

        # THEN no schema binding is attempted
        stored_rs.bind_schema_async.assert_not_awaited()

    @patch(f"{MGR}.CurationTask")
    @patch(f"{MGR}.RecordSet")
    @patch(f"{MGR}.JSONSchema")
    async def test_given_unknown_upsert_key_then_raises_before_creating_anything(
        self, mock_schema, mock_rs, mock_ct
    ):
        # GIVEN an upsert key the schema does not define
        _mock_schema(mock_schema)
        _no_existing_tasks(mock_ct)

        # WHEN / THEN creation fails with a ValueError naming the key
        with pytest.raises(ValueError, match="sampleID"):
            await CurationTaskManager(_client_with_project()).create_record_based_task(
                folder_id="syn50",
                record_set_name="rs",
                data_type="dt",
                schema_uri="org-s-1.0.0",
                upsert_keys=["sampleID"],
                instructions="x",
            )
        # AND no RecordSet was created
        mock_rs.assert_not_called()

    @patch(f"{MGR}.CurationTask")
    @patch(f"{MGR}.RecordSet")
    @patch(f"{MGR}.JSONSchema")
    async def test_given_schema_without_properties_then_raises(
        self, mock_schema, mock_rs, mock_ct
    ):
        # GIVEN a schema with no properties
        _mock_schema(mock_schema, body={"type": "object"})
        _no_existing_tasks(mock_ct)

        # WHEN / THEN creation fails before any write
        with pytest.raises(ValueError, match="no properties"):
            await CurationTaskManager(_client_with_project()).create_record_based_task(
                folder_id="syn50",
                record_set_name="rs",
                data_type="dt",
                schema_uri="org-s-1.0.0",
                upsert_keys=["id"],
                instructions="x",
            )
        mock_rs.assert_not_called()

    @patch(f"{MGR}.CurationTask")
    @patch(f"{MGR}.RecordSet")
    @patch(f"{MGR}.JSONSchema")
    async def test_given_task_store_fails_then_raises_with_record_set_id(
        self, mock_schema, mock_rs, mock_ct
    ):
        # GIVEN the RecordSet is created but the task store fails with an HTTP error
        _mock_schema(mock_schema)
        _no_existing_tasks(mock_ct)
        stored_rs = MagicMock(id="syn77")
        stored_rs.bind_schema_async = AsyncMock()
        mock_rs.return_value.store_async = AsyncMock(return_value=stored_rs)
        http_error = RuntimeError("403 forbidden")
        http_error.response = SimpleNamespace(status_code=403)
        mock_ct.return_value.store_async = AsyncMock(side_effect=http_error)

        # WHEN / THEN the error carries the orphaned RecordSet ID
        with pytest.raises(RecordBasedTaskCreationError) as exc_info:
            await CurationTaskManager(_client_with_project()).create_record_based_task(
                folder_id="syn50",
                record_set_name="rs",
                data_type="dt",
                schema_uri="org-s-1.0.0",
                upsert_keys=["specimenID"],
                instructions="x",
            )
        assert exc_info.value.record_set_id == "syn77"
        assert exc_info.value.status_code == 403
        assert "403 forbidden" in str(exc_info.value)

    @patch(f"{MGR}.CurationTask")
    @patch(f"{MGR}.RecordSet")
    @patch(f"{MGR}.JSONSchema")
    async def test_given_existing_task_for_data_type_then_raises_before_creating_anything(
        self, mock_schema, mock_rs, mock_ct
    ):
        # GIVEN the project already has a task for this data_type
        _mock_schema(mock_schema)
        _no_existing_tasks(mock_ct, [make_task(task_id=42, data_type="dt")])

        # WHEN / THEN creation is refused and names the existing task
        with pytest.raises(ValueError, match="task_id 42"):
            await CurationTaskManager(_client_with_project()).create_record_based_task(
                folder_id="syn50",
                record_set_name="rs",
                data_type="dt",
                schema_uri="org-s-1.0.0",
                upsert_keys=["specimenID"],
                instructions="x",
            )
        # AND no RecordSet or task was written
        mock_rs.assert_not_called()
        mock_ct.assert_not_called()

    @patch(f"{MGR}.CurationTask")
    @patch(f"{MGR}.RecordSet")
    @patch(f"{MGR}.JSONSchema")
    async def test_given_repeated_upsert_key_then_raises_before_creating_anything(
        self, mock_schema, mock_rs, mock_ct
    ):
        # GIVEN the same upsert key twice
        _mock_schema(mock_schema)
        _no_existing_tasks(mock_ct)

        # WHEN / THEN creation fails naming the repeated key
        with pytest.raises(ValueError, match="repeated keys"):
            await CurationTaskManager(_client_with_project()).create_record_based_task(
                folder_id="syn50",
                record_set_name="rs",
                data_type="dt",
                schema_uri="org-s-1.0.0",
                upsert_keys=["specimenID", "specimenID"],
                instructions="x",
            )
        mock_rs.assert_not_called()


class TestCsvFileName:
    def test_given_long_multibyte_name_then_base_name_is_bounded(self):
        # GIVEN a RecordSet name far over the filesystem component limit
        name = "\u00e9chantillon " * 60

        # WHEN we build the temp file name
        file_name = _csv_file_name(name)

        # THEN it stays within the byte budget and is still a CSV
        assert len(file_name.encode("utf-8")) <= 104
        assert file_name.endswith(".csv")

    def test_given_unsafe_characters_then_replaced(self):
        assert _csv_file_name("a/b:c*d") == "a_b_c_d.csv"

    def test_given_blank_name_then_falls_back(self):
        assert _csv_file_name("   ") == "recordset.csv"
