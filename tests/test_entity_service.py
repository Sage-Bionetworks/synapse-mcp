"""Tests for EntityService.

Verifies entity get, annotations, children, ACL,
and permissions operations using the new SDK patterns
(operations.get_async, Folder.walk_async, etc.).
"""

from dataclasses import dataclass
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from synapse_mcp.connection_auth import ConnectionAuthError
from synapse_mcp.services.entity_service import EntityService

pytestmark = pytest.mark.anyio("asyncio")


@pytest.fixture
def anyio_backend():
    return "asyncio"


TS = "synapse_mcp.services.tool_service"
SVC = "synapse_mcp.services.entity_service"


@dataclass
class FakeEntity:
    id: str = "syn123"
    name: str = "My Project"
    parent_id: str = "syn100"
    description: Optional[str] = None
    etag: str = "abc"
    created_on: str = "2025-01-01"
    modified_on: str = "2025-01-02"
    created_by: str = "user1"
    modified_by: str = "user2"
    annotations: Optional[dict] = None


@dataclass
class FakePermissions:
    access_types: object = None
    can_view: Optional[bool] = None
    can_edit: Optional[bool] = None
    can_download: Optional[bool] = None


@dataclass
class FakeEntityHeader:
    id: str = "syn100"
    name: str = "Folder1"
    type: str = "folder"


class TestGetEntity:
    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.operations_get_async", new_callable=AsyncMock)
    async def test_given_valid_entity_when_fetched_then_returns_serialized_dict(
        self, mock_ops_get, mock_get_client
    ):
        mock_get_client.return_value = MagicMock()
        mock_ops_get.return_value = FakeEntity()

        result = await EntityService().get_entity(MagicMock(), "syn123")

        assert result["id"] == "syn123"
        assert result["name"] == "My Project"
        assert result["parent_id"] == "syn100"
        mock_ops_get.assert_called_once()
        call_kwargs = mock_ops_get.call_args
        assert call_kwargs[1]["file_options"].download_file is False

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    async def test_given_expired_auth_when_fetching_then_returns_error(
        self, mock_get_client
    ):
        mock_get_client.side_effect = ConnectionAuthError("expired")

        result = await EntityService().get_entity(MagicMock(), "syn123")

        assert "Authentication required" in result["error"]
        assert result["entity_id"] == "syn123"


class TestGetAnnotations:
    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.operations_get_async", new_callable=AsyncMock)
    async def test_given_entity_with_annotations_when_fetched_then_returns_dict(
        self, mock_ops_get, mock_get_client
    ):
        mock_get_client.return_value = MagicMock()
        mock_ops_get.return_value = FakeEntity(
            annotations={"species": ["human"], "assay": ["RNA-seq"]}
        )

        result = await EntityService().get_annotations(MagicMock(), "syn456")

        assert result["species"] == ["human"]
        assert result["assay"] == ["RNA-seq"]

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.operations_get_async", new_callable=AsyncMock)
    async def test_given_no_annotations_when_fetched_then_returns_empty(
        self, mock_ops_get, mock_get_client
    ):
        mock_get_client.return_value = MagicMock()
        mock_ops_get.return_value = FakeEntity(annotations=None)

        result = await EntityService().get_annotations(MagicMock(), "syn456")

        assert result == {}


class TestGetChildren:
    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.Folder")
    async def test_given_container_with_children_when_listed_then_returns_all_types(
        self, mock_folder_cls, mock_get_client
    ):
        mock_get_client.return_value = MagicMock()
        container = mock_folder_cls.return_value
        container.sync_from_synapse_async = AsyncMock()
        container.folders = [
            FakeEntityHeader(id="syn100", name="Folder1", type="folder"),
        ]
        container.files = [
            FakeEntityHeader(id="syn101", name="File1", type="file"),
        ]
        container.tables = [
            FakeEntityHeader(id="syn102", name="Table1", type="table"),
        ]
        container.entityviews = []
        container.submissionviews = []
        container.datasets = []
        container.datasetcollections = []
        container.materializedviews = []
        container.virtualtables = []
        container.dockerrepos = []

        result = await EntityService().get_children(MagicMock(), "syn789")

        assert len(result) == 3
        ids = {r["id"] for r in result}
        assert ids == {"syn100", "syn101", "syn102"}
        container.sync_from_synapse_async.assert_called_once_with(
            download_file=False,
            recursive=False,
            synapse_client=mock_get_client.return_value,
        )

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.Folder")
    async def test_given_empty_container_when_listed_then_returns_empty_list(
        self, mock_folder_cls, mock_get_client
    ):
        mock_get_client.return_value = MagicMock()
        container = mock_folder_cls.return_value
        container.sync_from_synapse_async = AsyncMock()
        for attr in ("files", "folders", "tables", "entityviews",
                     "submissionviews", "datasets", "datasetcollections",
                     "materializedviews", "virtualtables", "dockerrepos"):
            setattr(container, attr, [])

        result = await EntityService().get_children(MagicMock(), "syn100")

        assert result == []

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.Folder")
    async def test_given_container_with_docker_repo_when_listed_then_includes_docker_repo(
        self, mock_folder_cls, mock_get_client
    ):
        # GIVEN a project that contains a Docker repository child.
        # sync_from_synapse_async populates ``dockerrepos`` (one of the
        # SDK default include-types). Regression for the missing
        # attribute in _CONTAINER_CHILD_ATTRS.
        mock_get_client.return_value = MagicMock()
        container = mock_folder_cls.return_value
        container.sync_from_synapse_async = AsyncMock()
        for attr in ("files", "folders", "tables", "entityviews",
                     "submissionviews", "datasets", "datasetcollections",
                     "materializedviews", "virtualtables"):
            setattr(container, attr, [])
        container.dockerrepos = [
            FakeEntityHeader(id="syn555", name="repo1", type="dockerrepo"),
        ]

        # WHEN children are listed
        result = await EntityService.get_children(MagicMock(), "syn789")

        # THEN the Docker repository surfaces in the response
        assert {r["id"] for r in result} == {"syn555"}

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    async def test_given_expired_auth_when_listing_then_returns_error_list(
        self, mock_get_client
    ):
        mock_get_client.side_effect = ConnectionAuthError("expired")

        result = await EntityService().get_children(MagicMock(), "syn789")

        assert isinstance(result, list)
        assert "Authentication required" in result[0]["error"]


class TestGetAcl:
    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.operations_get_async", new_callable=AsyncMock)
    async def test_given_project_entity_when_getting_acl_then_returns_access_types(
        self, mock_ops_get, mock_get_client
    ):
        # ACL must work on non-File entities: resolve the concrete
        # subclass (here a Project stand-in), then call get_acl_async
        # on it — never hardcoded File(id=...).
        mock_get_client.return_value = MagicMock()
        resolved = MagicMock()
        resolved.get_acl_async = AsyncMock(
            return_value=["READ", "UPDATE", "DELETE"]
        )
        mock_ops_get.return_value = resolved

        result = await EntityService().get_acl(MagicMock(), "syn123")

        assert result["entity_id"] == "syn123"
        assert result["access_types"] == ["READ", "UPDATE", "DELETE"]
        mock_ops_get.assert_called_once()
        assert (
            mock_ops_get.call_args[1]["file_options"].download_file
            is False
        )

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.operations_get_async", new_callable=AsyncMock)
    async def test_given_principal_id_when_getting_acl_then_passes_to_sdk(
        self, mock_ops_get, mock_get_client
    ):
        mock_get_client.return_value = MagicMock()
        resolved = MagicMock()
        resolved.get_acl_async = AsyncMock(return_value=["READ"])
        mock_ops_get.return_value = resolved

        result = await EntityService().get_acl(
            MagicMock(), "syn123", principal_id=12345
        )

        assert result["principal_id"] == 12345
        resolved.get_acl_async.assert_called_once_with(
            principal_id=12345,
            synapse_client=mock_get_client.return_value,
        )


class TestGetPermissions:
    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.operations_get_async", new_callable=AsyncMock)
    async def test_given_entity_when_getting_permissions_then_returns_dict(
        self, mock_ops_get, mock_get_client
    ):
        mock_get_client.return_value = MagicMock()
        resolved = MagicMock()
        resolved.get_permissions_async = AsyncMock(
            return_value=FakePermissions(
                access_types=["READ", "DOWNLOAD"],
                can_view=True,
                can_edit=False,
                can_download=True,
            )
        )
        mock_ops_get.return_value = resolved

        result = await EntityService().get_permissions(MagicMock(), "syn123")

        assert result["entity_id"] == "syn123"
        assert result["access_types"] == ["READ", "DOWNLOAD"]
        assert result["can_view"] is True
        assert result["can_edit"] is False


class TestGetLink:
    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.operations_get_async", new_callable=AsyncMock)
    async def test_given_link_when_resolved_then_returns_target(
        self, mock_ops_get, mock_get_client
    ):
        mock_get_client.return_value = MagicMock()
        mock_ops_get.return_value = FakeEntity(id="syn999", name="Target")

        result = await EntityService().get_link(
            MagicMock(), "syn500", follow_link=True
        )

        assert result["id"] == "syn999"
        assert result["name"] == "Target"
        call_kwargs = mock_ops_get.call_args
        assert call_kwargs[1]["link_options"].follow_link is True
        assert call_kwargs[1]["file_options"].download_file is False


@dataclass
class FakeAclResult:
    entity_acl: Optional[dict] = None
    all_entity_acls: Optional[list] = None


class TestListAcl:
    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.operations_get_async", new_callable=AsyncMock)
    async def test_given_recursive_without_container_content_then_returns_error(
        self, mock_ops_get, mock_get_client
    ):
        # GIVEN the SDK requires include_container_content=True alongside
        # recursive=True (otherwise it raises ValueError). We surface that
        # constraint as a clear error dict before the auth'd client is even
        # opened.
        # WHEN the caller asks for recursive without include_container_content
        result = await EntityService.list_acl(
            MagicMock(), "syn123", recursive=True
        )
        # THEN we get the explanatory error dict, no SDK call fires
        assert "include_container_content=True" in result["error"]
        assert result["entity_id"] == "syn123"
        mock_ops_get.assert_not_called()

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.operations_get_async", new_callable=AsyncMock)
    async def test_given_recursive_and_container_content_then_forwards_both(
        self, mock_ops_get, mock_get_client
    ):
        # GIVEN a Folder with a nested-ACL response
        mock_get_client.return_value = MagicMock()
        resolved = MagicMock()
        resolved.list_acl_async = AsyncMock(
            return_value=FakeAclResult(
                entity_acl={"acl_entries": []},
                all_entity_acls=[{"entity_id": "syn123", "acl_entries": []}],
            )
        )
        mock_ops_get.return_value = resolved

        # WHEN we list ACLs recursively with include_container_content
        await EntityService.list_acl(
            MagicMock(),
            "syn123",
            recursive=True,
            include_container_content=True,
            target_entity_types=["folder", "file"],
        )

        # THEN both flags + target_entity_types reach the SDK
        kwargs = resolved.list_acl_async.call_args.kwargs
        assert kwargs["recursive"] is True
        assert kwargs["include_container_content"] is True
        assert kwargs["target_entity_types"] == ["folder", "file"]


@dataclass
class FakeInvalidValidation:
    entity_id: str = "syn999"
    is_valid: bool = False


class TestGetSchemaInvalidValidations:
    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.Folder")
    async def test_given_failing_entities_when_listed_then_drives_async_generator(
        self, mock_folder_cls, mock_get_client
    ):
        # GIVEN the SDK exposes get_invalid_validation_async as an async
        # generator (NOT an awaitable). Awaiting it directly used to leak
        # an async_generator_asend object; this test guards against that
        # regression by yielding two records and checking both come back.
        mock_get_client.return_value = MagicMock()
        container = mock_folder_cls.return_value

        async def _invalid(**kw):
            yield FakeInvalidValidation(entity_id="syn1")
            yield FakeInvalidValidation(entity_id="syn2")

        container.get_invalid_validation_async = _invalid

        # WHEN the service collects invalid validations
        result = await EntityService.get_schema_invalid_validations(
            MagicMock(), "syn100"
        )

        # THEN every yielded record surfaces as a serialized dict
        assert [r["entity_id"] for r in result] == ["syn1", "syn2"]


class TestCreateEntity:
    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.Project.store_async", new_callable=AsyncMock)
    async def test_given_project_when_created_then_stores_and_returns_dict(
        self, mock_store, mock_get_client
    ):
        # Container types (project) are resolved through
        # _CONTAINER_ENTITY_TYPES which captured the real Project class at
        # import — patch store_async on that class rather than the name.
        mock_get_client.return_value = MagicMock()
        mock_store.return_value = FakeEntity(id="syn9", name="P")

        result = await EntityService.create_entity(
            MagicMock(), "project", "P"
        )

        assert result["id"] == "syn9"
        assert result["name"] == "P"
        mock_store.assert_called_once()

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    async def test_given_folder_without_parent_then_returns_error(
        self, mock_get_client
    ):
        # Validation fires before the auth'd client opens.
        result = await EntityService.create_entity(
            MagicMock(), "folder", "F"
        )

        assert "parent_id" in result["error"]
        mock_get_client.assert_not_called()

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    async def test_given_file_without_url_or_handle_then_returns_error(
        self, mock_get_client
    ):
        # A file cannot be created from local content — only an
        # external_url or an existing data_file_handle_id is supported.
        result = await EntityService.create_entity(
            MagicMock(), "file", "f", parent_id="syn1"
        )

        assert "not supported" in result["error"]
        mock_get_client.assert_not_called()

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.File")
    async def test_given_file_with_external_url_then_creates(
        self, mock_file_cls, mock_get_client
    ):
        mock_get_client.return_value = MagicMock()
        mock_file_cls.return_value.store_async = AsyncMock(
            return_value=FakeEntity(id="syn10", name="f")
        )

        result = await EntityService.create_entity(
            MagicMock(),
            "file",
            "f",
            parent_id="syn1",
            external_url="http://example.com/data.csv",
        )

        assert result["id"] == "syn10"
        mock_file_cls.return_value.store_async.assert_called_once()

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.File")
    async def test_given_file_with_data_file_handle_id_then_creates(
        self, mock_file_cls, mock_get_client
    ):
        mock_get_client.return_value = MagicMock()
        mock_file_cls.return_value.store_async = AsyncMock(
            return_value=FakeEntity(id="syn12", name="f")
        )

        result = await EntityService.create_entity(
            MagicMock(),
            "file",
            "f",
            parent_id="syn1",
            data_file_handle_id="456",
        )

        assert result["id"] == "syn12"
        mock_file_cls.assert_called_once_with(
            name="f",
            parent_id="syn1",
            external_url=None,
            data_file_handle_id="456",
            synapse_store=True,
        )
        mock_file_cls.return_value.store_async.assert_called_once()

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    async def test_given_link_without_target_then_returns_error(
        self, mock_get_client
    ):
        result = await EntityService.create_entity(
            MagicMock(), "link", "L", parent_id="syn1"
        )

        assert "target_id" in result["error"]
        mock_get_client.assert_not_called()

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    async def test_given_unsupported_type_then_returns_error(
        self, mock_get_client
    ):
        result = await EntityService.create_entity(
            MagicMock(), "bogus", "x", parent_id="syn1"
        )

        assert "Unsupported entity_type" in result["error"]
        mock_get_client.assert_not_called()

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    async def test_given_recordset_without_handle_then_returns_error(
        self, mock_get_client
    ):
        # A record set cannot be created from local CSV content — only an
        # existing data_file_handle_id is supported.
        result = await EntityService.create_entity(
            MagicMock(), "recordset", "rs", parent_id="syn1"
        )

        assert "not supported" in result["error"]
        mock_get_client.assert_not_called()

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.RecordSet")
    async def test_given_recordset_with_handle_then_creates(
        self, mock_recordset_cls, mock_get_client
    ):
        mock_get_client.return_value = MagicMock()
        mock_recordset_cls.return_value.store_async = AsyncMock(
            return_value=FakeEntity(id="syn11", name="rs")
        )

        result = await EntityService.create_entity(
            MagicMock(),
            "recordset",
            "rs",
            parent_id="syn1",
            data_file_handle_id="123",
        )

        assert result["id"] == "syn11"
        mock_recordset_cls.return_value.store_async.assert_called_once()

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    async def test_given_file_with_url_and_handle_then_returns_error(
        self, mock_get_client
    ):
        # A file takes exactly one source — external_url or an existing
        # data_file_handle_id, never both.
        result = await EntityService.create_entity(
            MagicMock(),
            "file",
            "f",
            parent_id="syn1",
            external_url="http://example.com/data.csv",
            data_file_handle_id="123",
        )

        assert "not both" in result["error"]
        mock_get_client.assert_not_called()

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    async def test_given_bad_column_type_then_returns_value_error(
        self, mock_get_client
    ):
        result = await EntityService.create_entity(
            MagicMock(),
            "table",
            "T",
            parent_id="syn1",
            columns=[{"name": "age", "column_type": "BOGUS"}],
        )

        assert result["error_type"] == "ValueError"
        assert "BOGUS" in result["error"]
        assert "Valid:" in result["error"]
        mock_get_client.assert_not_called()

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    async def test_given_column_missing_name_then_returns_value_error(
        self, mock_get_client
    ):
        # A column spec without 'name' is rejected up front rather than
        # constructing Column(name=None) that fails with a vague error later.
        result = await EntityService.create_entity(
            MagicMock(),
            "table",
            "T",
            parent_id="syn1",
            columns=[{"column_type": "INTEGER"}],
        )

        assert result["error_type"] == "ValueError"
        assert "name" in result["error"]
        mock_get_client.assert_not_called()

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    async def test_given_column_missing_type_then_returns_value_error(
        self, mock_get_client
    ):
        result = await EntityService.create_entity(
            MagicMock(),
            "table",
            "T",
            parent_id="syn1",
            columns=[{"name": "age"}],
        )

        assert result["error_type"] == "ValueError"
        assert "column_type" in result["error"]
        mock_get_client.assert_not_called()

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    async def test_given_bad_view_mask_then_returns_value_error(
        self, mock_get_client
    ):
        result = await EntityService.create_entity(
            MagicMock(),
            "entityview",
            "V",
            parent_id="syn1",
            view_type_mask=["BOGUS"],
        )

        assert result["error_type"] == "ValueError"
        assert "BOGUS" in result["error"]
        assert "Valid:" in result["error"]
        mock_get_client.assert_not_called()


class TestUpdateEntity:
    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.operations_get_async", new_callable=AsyncMock)
    async def test_given_name_and_annotations_then_sets_and_stores(
        self, mock_ops_get, mock_get_client
    ):
        mock_get_client.return_value = MagicMock()
        entity = MagicMock()
        entity.store_async = AsyncMock(
            return_value=FakeEntity(id="syn1", name="New")
        )
        mock_ops_get.return_value = entity

        result = await EntityService.update_entity(
            MagicMock(),
            "syn1",
            name="New",
            annotations={"species": ["human"]},
        )

        assert entity.name == "New"
        assert entity.annotations == {"species": ["human"]}
        entity.store_async.assert_called_once()
        assert result["name"] == "New"

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.operations_get_async", new_callable=AsyncMock)
    async def test_given_provenance_then_builds_activity(
        self, mock_ops_get, mock_get_client
    ):
        mock_get_client.return_value = MagicMock()
        entity = MagicMock()
        entity.store_async = AsyncMock(return_value=FakeEntity())
        mock_ops_get.return_value = entity

        await EntityService.update_entity(
            MagicMock(),
            "syn1",
            provenance={
                "name": "run1",
                "used": [{"target_id": "syn2"}],
                "executed": [{"name": "script", "url": "http://x/s.py"}],
            },
        )

        # activity is set from the provenance spec before storing
        assert entity.activity is not None
        assert entity.activity.name == "run1"

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.operations_get_async", new_callable=AsyncMock)
    async def test_given_omitted_fields_then_left_unchanged(
        self, mock_ops_get, mock_get_client
    ):
        # Fields not supplied keep the UNSET sentinel and are never touched.
        mock_get_client.return_value = MagicMock()
        entity = MagicMock()
        entity.name = "original"
        entity.description = "original desc"
        entity.store_async = AsyncMock(return_value=FakeEntity())
        mock_ops_get.return_value = entity

        await EntityService.update_entity(MagicMock(), "syn1", name="renamed")

        assert entity.name == "renamed"
        # description was omitted → untouched
        assert entity.description == "original desc"

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.operations_get_async", new_callable=AsyncMock)
    async def test_given_explicit_none_then_clears_field(
        self, mock_ops_get, mock_get_client
    ):
        # An explicit null clears the field (distinct from omitting it):
        # description → None, annotations → {}.
        mock_get_client.return_value = MagicMock()
        entity = MagicMock()
        entity.description = "some desc"
        entity.annotations = {"k": ["v"]}
        entity.store_async = AsyncMock(return_value=FakeEntity())
        mock_ops_get.return_value = entity

        await EntityService.update_entity(
            MagicMock(), "syn1", description=None, annotations=None
        )

        assert entity.description is None
        assert entity.annotations == {}

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.operations_get_async", new_callable=AsyncMock)
    async def test_given_explicit_null_name_then_returns_error(
        self, mock_ops_get, mock_get_client
    ):
        # name/parent_id are not clearable — an explicit null is rejected
        # before the entity is even fetched.
        result = await EntityService.update_entity(
            MagicMock(), "syn1", name=None
        )

        assert "cannot be cleared" in result["error"]
        mock_ops_get.assert_not_called()

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.operations_get_async", new_callable=AsyncMock)
    async def test_given_explicit_null_provenance_then_returns_error(
        self, mock_ops_get, mock_get_client
    ):
        # provenance cannot be cleared via this tool; null is rejected
        # instead of being silently ignored.
        result = await EntityService.update_entity(
            MagicMock(), "syn1", provenance=None
        )

        assert "cannot be cleared" in result["error"]
        mock_ops_get.assert_not_called()

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.operations_get_async", new_callable=AsyncMock)
    async def test_given_external_url_then_sets_and_disables_store(
        self, mock_ops_get, mock_get_client
    ):
        # A new external_url makes the file an external link, so
        # synapse_store must be flipped off (mirrors create_entity).
        mock_get_client.return_value = MagicMock()
        entity = MagicMock()
        entity.store_async = AsyncMock(return_value=FakeEntity())
        mock_ops_get.return_value = entity

        await EntityService.update_entity(
            MagicMock(), "syn1", external_url="http://x/data.csv"
        )

        assert entity.external_url == "http://x/data.csv"
        assert entity.synapse_store is False

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.operations_get_async", new_callable=AsyncMock)
    async def test_given_view_type_mask_then_resolves_flag(
        self, mock_ops_get, mock_get_client
    ):
        from synapseclient.models import ViewTypeMask

        mock_get_client.return_value = MagicMock()
        entity = MagicMock()
        entity.store_async = AsyncMock(return_value=FakeEntity())
        mock_ops_get.return_value = entity

        await EntityService.update_entity(
            MagicMock(), "syn1", view_type_mask=["file"]
        )

        assert entity.view_type_mask == ViewTypeMask.FILE

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.operations_get_async", new_callable=AsyncMock)
    async def test_given_type_specific_field_on_wrong_type_then_errors(
        self, mock_ops_get, mock_get_client
    ):
        # external_url on a type that lacks the attribute (e.g. a Folder)
        # is rejected rather than silently setting a bogus attribute.
        mock_get_client.return_value = MagicMock()

        class FakeFolder:
            name = "F"

        folder = FakeFolder()
        mock_ops_get.return_value = folder

        result = await EntityService.update_entity(
            MagicMock(), "syn1", external_url="http://x/data.csv"
        )

        assert "not valid for a FakeFolder" in result["error"]
        assert result["entity_id"] == "syn1"

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.operations_get_async", new_callable=AsyncMock)
    async def test_given_explicit_null_type_specific_then_returns_error(
        self, mock_ops_get, mock_get_client
    ):
        # Type-specific fields are non-clearable; an explicit null is
        # rejected before the entity is fetched.
        result = await EntityService.update_entity(
            MagicMock(), "syn1", target_id=None
        )

        assert "cannot be cleared" in result["error"]
        mock_ops_get.assert_not_called()


class TestUpdateEntityChangeTracking:
    """Pin the SDK change-tracking contract that makes clearing persist.

    ``update_entity`` fetches the entity first (via ``_resolve_entity`` ->
    ``get_async``), which sets ``_last_persistent_instance``. That is what
    makes the subsequent ``store_async`` take the DESTRUCTIVE path: the
    non-destructive merge (``merge_dataclass_entities``) only runs when
    ``_last_persistent_instance`` is unset, and that merge would copy the
    server's existing value back over a ``None``-cleared field — silently
    reverting the clear. These tests use a real ``Project`` dataclass (not a
    mock) so a regression to a no-fetch/merge path would fail here.
    """

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.operations_get_async", new_callable=AsyncMock)
    async def test_fetched_entity_takes_destructive_store_path(
        self, mock_ops_get, mock_get_client
    ):
        from synapseclient.models import Project

        mock_get_client.return_value = MagicMock()

        # A real, already-fetched Project: get_async stamps the baseline.
        project = Project(
            id="syn1",
            name="P",
            description="original",
            annotations={"k": ["v"]},
        )
        project._set_last_persistent_instance()
        assert project.has_changed is False

        captured = {}

        async def fake_store(*, synapse_client=None):
            # Capture the state the SDK would serialize + whether the
            # non-destructive merge would be bypassed.
            captured["description"] = project.description
            captured["annotations"] = project.annotations
            captured["merge_skipped"] = bool(
                project._last_persistent_instance
            )
            captured["has_changed"] = project.has_changed
            return project

        project.store_async = fake_store
        mock_ops_get.return_value = project

        await EntityService.update_entity(
            MagicMock(), "syn1", description=None, annotations=None
        )

        # The clear reaches the store, the merge is bypassed, and the diff
        # against the fetched baseline marks the entity as changed.
        assert captured["description"] is None
        assert captured["annotations"] == {}
        assert captured["merge_skipped"] is True
        assert captured["has_changed"] is True

    async def test_merge_would_revert_a_clear_on_an_unfetched_instance(self):
        # Documents WHY the pre-fetch is required: if the instance were not
        # fetched first, store's non-destructive merge restores the server
        # value over the caller's None/empty clear.
        from synapseclient.core.utils import merge_dataclass_entities
        from synapseclient.models import Project

        server = Project(
            id="syn1",
            name="P",
            description="original",
            annotations={"k": ["v"]},
        )
        caller = Project(
            id="syn1", name="P", description=None, annotations={}
        )

        merge_dataclass_entities(source=server, destination=caller)

        # The merge is non-destructive: the clear is reverted. This is the
        # behavior update_entity avoids by fetching first.
        assert caller.description == "original"
        assert caller.annotations == {"k": ["v"]}


class TestDeleteEntity:
    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.operations_get_async", new_callable=AsyncMock)
    async def test_given_entity_when_deleted_then_returns_confirmation(
        self, mock_ops_get, mock_get_client
    ):
        mock_get_client.return_value = MagicMock()
        entity = MagicMock()
        entity.delete_async = AsyncMock()
        mock_ops_get.return_value = entity

        result = await EntityService.delete_entity(MagicMock(), "syn123")

        assert result == {"entity_id": "syn123", "deleted": True}
        entity.delete_async.assert_called_once()

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    async def test_given_expired_auth_when_deleting_then_returns_error(
        self, mock_get_client
    ):
        mock_get_client.side_effect = ConnectionAuthError("expired")

        result = await EntityService.delete_entity(MagicMock(), "syn123")

        assert "Authentication required" in result["error"]
        assert result["entity_id"] == "syn123"


class TestSetAcl:
    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.operations_get_async", new_callable=AsyncMock)
    async def test_given_principal_when_set_then_returns_acl(
        self, mock_ops_get, mock_get_client
    ):
        mock_get_client.return_value = MagicMock()
        entity = MagicMock()
        entity.set_permissions_async = AsyncMock(
            return_value={"resourceAccess": []}
        )
        mock_ops_get.return_value = entity

        result = await EntityService.set_acl(
            MagicMock(), "syn123", 12345, ["READ", "DOWNLOAD"]
        )

        assert result["entity_id"] == "syn123"
        assert result["principal_id"] == 12345
        assert result["acl"] == {"resourceAccess": []}
        entity.set_permissions_async.assert_called_once()


class TestDeleteAcl:
    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.operations_get_async", new_callable=AsyncMock)
    async def test_given_entity_when_acl_deleted_then_returns_confirmation(
        self, mock_ops_get, mock_get_client
    ):
        mock_get_client.return_value = MagicMock()
        entity = MagicMock()
        entity.delete_permissions_async = AsyncMock()
        mock_ops_get.return_value = entity

        result = await EntityService.delete_acl(MagicMock(), "syn123")

        assert result == {"entity_id": "syn123", "acl_deleted": True}
        entity.delete_permissions_async.assert_called_once()

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.operations_get_async", new_callable=AsyncMock)
    async def test_given_project_when_acl_deleted_then_reports_not_deleted(
        self, mock_ops_get, mock_get_client
    ):
        # GIVEN the resolved entity is a Project (root ACL is undeletable)
        mock_get_client.return_value = MagicMock()

        class Project:
            def __init__(self):
                self.delete_permissions_async = AsyncMock()

        entity = Project()
        mock_ops_get.return_value = entity

        # WHEN its ACL delete is requested
        result = await EntityService.delete_acl(MagicMock(), "syn123")

        # THEN the response honestly reports the root ACL was not deleted
        assert result["acl_deleted"] is False
        assert "Project" in result["message"]
        entity.delete_permissions_async.assert_called_once()


class TestBindSchema:
    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.operations_get_async", new_callable=AsyncMock)
    async def test_given_uri_when_bound_then_returns_binding(
        self, mock_ops_get, mock_get_client
    ):
        mock_get_client.return_value = MagicMock()
        entity = MagicMock()
        entity.bind_schema_async = AsyncMock(
            return_value={"json_schema_version_info": {}}
        )
        mock_ops_get.return_value = entity

        result = await EntityService.bind_schema(
            MagicMock(), "syn123", "my.org-MySchema-1.0.0"
        )

        assert result["entity_id"] == "syn123"
        entity.bind_schema_async.assert_called_once()
        kwargs = entity.bind_schema_async.call_args.kwargs
        assert kwargs["json_schema_uri"] == "my.org-MySchema-1.0.0"
        assert kwargs["enable_derived_annotations"] is False


class TestUnbindSchema:
    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.operations_get_async", new_callable=AsyncMock)
    async def test_given_entity_when_unbound_then_returns_confirmation(
        self, mock_ops_get, mock_get_client
    ):
        mock_get_client.return_value = MagicMock()
        entity = MagicMock()
        entity.unbind_schema_async = AsyncMock()
        mock_ops_get.return_value = entity

        result = await EntityService.unbind_schema(MagicMock(), "syn123")

        assert result == {"entity_id": "syn123", "schema_unbound": True}
        entity.unbind_schema_async.assert_called_once()


def _columnar_entity(col_names) -> MagicMock:
    """Mock table-like entity for update_columns tests.

    Each key in ``col_names`` becomes a mock Column whose ``.name`` matches
    the key, stored in a real dict so the service's re-key/reorder logic runs
    against genuine dict semantics. ``store_async`` returns a FakeEntity so a
    result can be serialized.
    """
    entity = MagicMock()
    columns = {}
    for name in col_names:
        col = MagicMock()
        col.name = name
        columns[name] = col
    entity.columns = columns
    entity.store_async = AsyncMock(
        return_value=FakeEntity(id="syn5", name="T")
    )
    return entity


class TestUpdateColumns:
    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.operations_get_async", new_callable=AsyncMock)
    async def test_given_add_and_delete_then_applies_and_stores(
        self, mock_ops_get, mock_get_client
    ):
        mock_get_client.return_value = MagicMock()
        entity = MagicMock()
        entity.add_column = MagicMock()
        entity.delete_column = MagicMock()
        entity.store_async = AsyncMock(
            return_value=FakeEntity(id="syn5", name="T")
        )
        mock_ops_get.return_value = entity

        result = await EntityService.update_columns(
            MagicMock(),
            "syn5",
            add_columns=[{"name": "age", "column_type": "INTEGER"}],
            delete_columns=["old_col"],
        )

        entity.delete_column.assert_called_once_with(name="old_col")
        entity.add_column.assert_called_once()
        entity.store_async.assert_called_once()
        assert result["id"] == "syn5"

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.operations_get_async", new_callable=AsyncMock)
    async def test_given_non_columnar_entity_then_returns_error(
        self, mock_ops_get, mock_get_client
    ):
        # GIVEN a resolved entity without column methods (e.g. a Folder)
        mock_get_client.return_value = MagicMock()

        class Folder:
            pass

        mock_ops_get.return_value = Folder()

        # WHEN a column change is requested on it
        result = await EntityService.update_columns(
            MagicMock(),
            "syn5",
            add_columns=[{"name": "age", "column_type": "INTEGER"}],
        )

        # THEN a clear error is returned instead of an AttributeError
        assert "does not have" in result["error"]
        assert result["entity_id"] == "syn5"

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.operations_get_async", new_callable=AsyncMock)
    async def test_given_rename_then_renames_and_rekeys(
        self, mock_ops_get, mock_get_client
    ):
        # A rename mutates Column.name in place AND re-keys the columns
        # dict so a later reorder can reference the new name.
        mock_get_client.return_value = MagicMock()
        entity = _columnar_entity({"age": None, "name": None})
        mock_ops_get.return_value = entity

        result = await EntityService.update_columns(
            MagicMock(), "syn5", rename_columns={"age": "years"}
        )

        assert list(entity.columns.keys()) == ["years", "name"]
        assert entity.columns["years"].name == "years"
        assert result["id"] == "syn5"

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.operations_get_async", new_callable=AsyncMock)
    async def test_given_rename_unknown_column_then_returns_error(
        self, mock_ops_get, mock_get_client
    ):
        mock_get_client.return_value = MagicMock()
        entity = _columnar_entity({"age": None})
        mock_ops_get.return_value = entity

        result = await EntityService.update_columns(
            MagicMock(), "syn5", rename_columns={"nope": "x"}
        )

        assert "no such column" in result["error"]
        entity.store_async.assert_not_called()

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.operations_get_async", new_callable=AsyncMock)
    async def test_given_reorder_then_reorders_each_by_index(
        self, mock_ops_get, mock_get_client
    ):
        mock_get_client.return_value = MagicMock()
        entity = _columnar_entity({"a": None, "b": None})
        mock_ops_get.return_value = entity

        await EntityService.update_columns(
            MagicMock(), "syn5", reorder_columns=["b", "a"]
        )

        assert entity.reorder_column.call_args_list == [
            call(name="b", index=0),
            call(name="a", index=1),
        ]

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.operations_get_async", new_callable=AsyncMock)
    async def test_given_incomplete_reorder_then_returns_error(
        self, mock_ops_get, mock_get_client
    ):
        # reorder_columns must list EXACTLY the final columns — a partial
        # list is rejected rather than dropping columns silently.
        mock_get_client.return_value = MagicMock()
        entity = _columnar_entity({"a": None, "b": None})
        mock_ops_get.return_value = entity

        result = await EntityService.update_columns(
            MagicMock(), "syn5", reorder_columns=["a"]
        )

        assert "exactly the final set" in result["error"]
        entity.reorder_column.assert_not_called()
        entity.store_async.assert_not_called()

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.operations_get_async", new_callable=AsyncMock)
    async def test_given_all_ops_then_applies_in_delete_add_rename_reorder_order(
        self, mock_ops_get, mock_get_client
    ):
        # The four operations compose: delete drops a column, add appends
        # one, rename re-keys, and reorder references the post-add/rename
        # names. Ordering matters — reorder must see the final name set.
        mock_get_client.return_value = MagicMock()
        entity = _columnar_entity({"old": None, "keep": None})

        def _add(col):
            entity.columns[col.name] = col

        def _delete(*, name):
            entity.columns.pop(name)

        entity.add_column.side_effect = _add
        entity.delete_column.side_effect = _delete
        mock_ops_get.return_value = entity

        result = await EntityService.update_columns(
            MagicMock(),
            "syn5",
            delete_columns=["old"],
            add_columns=[{"name": "added", "column_type": "INTEGER"}],
            rename_columns={"keep": "kept"},
            reorder_columns=["added", "kept"],
        )

        assert result["id"] == "syn5"
        assert set(entity.columns.keys()) == {"added", "kept"}
        assert entity.reorder_column.call_args_list == [
            call(name="added", index=0),
            call(name="kept", index=1),
        ]
