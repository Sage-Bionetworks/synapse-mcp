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
                     "materializedviews", "virtualtables"):
            setattr(container, attr, [])

        result = await EntityService().get_children(MagicMock(), "syn100")

        assert result == []

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
    @patch(f"{SVC}.File")
    async def test_given_entity_when_getting_acl_then_returns_access_types(
        self, mock_file_cls, mock_get_client
    ):
        mock_get_client.return_value = MagicMock()
        mock_file_cls.return_value.get_acl_async = AsyncMock(
            return_value=["READ", "UPDATE", "DELETE"]
        )

        result = await EntityService().get_acl(MagicMock(), "syn123")

        assert result["entity_id"] == "syn123"
        assert result["access_types"] == ["READ", "UPDATE", "DELETE"]

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.File")
    async def test_given_principal_id_when_getting_acl_then_passes_to_sdk(
        self, mock_file_cls, mock_get_client
    ):
        mock_get_client.return_value = MagicMock()
        mock_file_cls.return_value.get_acl_async = AsyncMock(
            return_value=["READ"]
        )

        result = await EntityService().get_acl(
            MagicMock(), "syn123", principal_id=12345
        )

        assert result["principal_id"] == 12345
        mock_file_cls.return_value.get_acl_async.assert_called_once_with(
            principal_id=12345,
            synapse_client=mock_get_client.return_value,
        )


class TestGetPermissions:
    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.File")
    async def test_given_entity_when_getting_permissions_then_returns_dict(
        self, mock_file_cls, mock_get_client
    ):
        mock_get_client.return_value = MagicMock()
        mock_file_cls.return_value.get_permissions_async = AsyncMock(
            return_value=FakePermissions(
                access_types=["READ", "DOWNLOAD"],
                can_view=True,
                can_edit=False,
                can_download=True,
            )
        )

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
