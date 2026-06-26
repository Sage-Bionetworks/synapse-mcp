"""Tests for EntityService.

Verifies entity get, annotations, children, ACL,
and permissions operations using the new SDK patterns
(operations.get_async, Folder.walk_async, etc.).
"""

from dataclasses import dataclass
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch

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
