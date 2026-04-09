"""Tests for EntityService.

Verifies entity get, annotations, children, ACL,
and permissions operations using the new SDK patterns
(operations.get, Folder.walk, etc.).
"""

from dataclasses import dataclass
from typing import Optional
from unittest.mock import MagicMock, patch

from synapse_mcp.connection_auth import ConnectionAuthError
from synapse_mcp.services.entity_service import EntityService

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
    @patch(f"{TS}.get_synapse_client")
    @patch(f"{SVC}.operations_get")
    def test_given_valid_entity_when_fetched_then_returns_serialized_dict(
        self, mock_ops_get, mock_get_client
    ):
        # GIVEN a client that returns a dataclass entity
        mock_get_client.return_value = MagicMock()
        mock_ops_get.return_value = FakeEntity()

        # WHEN we get the entity
        result = EntityService().get_entity(
            MagicMock(), "syn123"
        )

        # THEN it returns all public dataclass fields
        assert result["id"] == "syn123"
        assert result["name"] == "My Project"
        assert result["parent_id"] == "syn100"
        mock_ops_get.assert_called_once()
        # Verify FileOptions(download_file=False) was passed
        call_kwargs = mock_ops_get.call_args
        assert call_kwargs[1]["file_options"].download_file is False

    @patch(f"{TS}.get_synapse_client")
    def test_given_expired_auth_when_fetching_then_returns_error(
        self, mock_get_client
    ):
        # GIVEN expired credentials
        mock_get_client.side_effect = ConnectionAuthError(
            "expired"
        )

        # WHEN we get an entity
        result = EntityService().get_entity(
            MagicMock(), "syn123"
        )

        # THEN the error includes the entity_id
        assert "Authentication required" in result["error"]
        assert result["entity_id"] == "syn123"


class TestGetAnnotations:
    @patch(f"{TS}.get_synapse_client")
    @patch(f"{SVC}.operations_get")
    def test_given_entity_with_annotations_when_fetched_then_returns_dict(
        self, mock_ops_get, mock_get_client
    ):
        # GIVEN an entity with annotations
        mock_get_client.return_value = MagicMock()
        mock_ops_get.return_value = FakeEntity(
            annotations={
                "species": ["human"],
                "assay": ["RNA-seq"],
            }
        )

        # WHEN we get annotations
        result = EntityService().get_annotations(
            MagicMock(), "syn456"
        )

        # THEN annotations are returned as a dict
        assert result["species"] == ["human"]
        assert result["assay"] == ["RNA-seq"]

    @patch(f"{TS}.get_synapse_client")
    @patch(f"{SVC}.operations_get")
    def test_given_no_annotations_when_fetched_then_returns_empty(
        self, mock_ops_get, mock_get_client
    ):
        # GIVEN an entity with None annotations
        mock_get_client.return_value = MagicMock()
        mock_ops_get.return_value = FakeEntity(annotations=None)

        # WHEN we get annotations
        result = EntityService().get_annotations(
            MagicMock(), "syn456"
        )

        # THEN an empty dict is returned
        assert result == {}


class TestGetChildren:
    @patch(f"{TS}.get_synapse_client")
    @patch(f"{SVC}.Folder")
    def test_given_container_with_children_when_listed_then_returns_list(
        self, mock_folder_cls, mock_get_client
    ):
        # GIVEN a container with children returned by walk()
        mock_get_client.return_value = MagicMock()
        path_info = ("My Folder", "syn789")
        folder_headers = [
            FakeEntityHeader(id="syn100", name="Folder1", type="folder"),
        ]
        file_headers = [
            FakeEntityHeader(id="syn101", name="File1", type="file"),
        ]
        mock_folder_cls.return_value.walk.return_value = iter(
            [(path_info, folder_headers, file_headers)]
        )

        # WHEN we list children
        result = EntityService().get_children(
            MagicMock(), "syn789"
        )

        # THEN the children are returned as a flat list
        assert len(result) == 2
        assert result[0]["id"] == "syn100"
        assert result[0]["name"] == "Folder1"
        assert result[1]["id"] == "syn101"
        assert result[1]["name"] == "File1"

    @patch(f"{TS}.get_synapse_client")
    @patch(f"{SVC}.Folder")
    def test_given_empty_container_when_listed_then_returns_empty_list(
        self, mock_folder_cls, mock_get_client
    ):
        # GIVEN a container with no children
        mock_get_client.return_value = MagicMock()
        mock_folder_cls.return_value.walk.return_value = iter(
            [(("Empty", "syn100"), [], [])]
        )

        # WHEN we list children
        result = EntityService().get_children(
            MagicMock(), "syn100"
        )

        # THEN an empty list is returned
        assert result == []

    @patch(f"{TS}.get_synapse_client")
    def test_given_expired_auth_when_listing_then_returns_error_list(
        self, mock_get_client
    ):
        # GIVEN expired credentials
        mock_get_client.side_effect = ConnectionAuthError(
            "expired"
        )

        # WHEN we list children
        result = EntityService().get_children(
            MagicMock(), "syn789"
        )

        # THEN error is wrapped in a list
        assert isinstance(result, list)
        assert "Authentication required" in result[0]["error"]


class TestGetAcl:
    @patch(f"{TS}.get_synapse_client")
    @patch(f"{SVC}.File")
    def test_given_entity_when_getting_acl_then_returns_access_types(
        self, mock_file_cls, mock_get_client
    ):
        # GIVEN an entity whose ACL returns access types
        mock_get_client.return_value = MagicMock()
        mock_file_cls.return_value.get_acl.return_value = [
            "READ", "UPDATE", "DELETE",
        ]

        # WHEN we get the ACL
        result = EntityService().get_acl(
            MagicMock(), "syn123"
        )

        # THEN the access types are returned
        assert result["entity_id"] == "syn123"
        assert result["access_types"] == [
            "READ", "UPDATE", "DELETE",
        ]

    @patch(f"{TS}.get_synapse_client")
    @patch(f"{SVC}.File")
    def test_given_principal_id_when_getting_acl_then_passes_to_sdk(
        self, mock_file_cls, mock_get_client
    ):
        # GIVEN a specific principal_id
        mock_get_client.return_value = MagicMock()
        mock_file_cls.return_value.get_acl.return_value = [
            "READ",
        ]

        # WHEN we get ACL for a specific principal
        result = EntityService().get_acl(
            MagicMock(), "syn123", principal_id=12345
        )

        # THEN the principal_id is in the response
        assert result["principal_id"] == 12345
        mock_file_cls.return_value.get_acl.assert_called_once_with(
            principal_id=12345,
            synapse_client=mock_get_client.return_value,
        )


class TestGetPermissions:
    @patch(f"{TS}.get_synapse_client")
    @patch(f"{SVC}.File")
    def test_given_entity_when_getting_permissions_then_returns_dict(
        self, mock_file_cls, mock_get_client
    ):
        # GIVEN an entity with permissions
        mock_get_client.return_value = MagicMock()
        mock_file_cls.return_value.get_permissions.return_value = (
            FakePermissions(
                access_types=["READ", "DOWNLOAD"],
                can_view=True,
                can_edit=False,
                can_download=True,
            )
        )

        # WHEN we get permissions
        result = EntityService().get_permissions(
            MagicMock(), "syn123"
        )

        # THEN permissions are returned with entity_id
        assert result["entity_id"] == "syn123"
        assert result["access_types"] == [
            "READ", "DOWNLOAD",
        ]
        assert result["can_view"] is True
        assert result["can_edit"] is False


class TestGetLink:
    @patch(f"{TS}.get_synapse_client")
    @patch(f"{SVC}.operations_get")
    def test_given_link_when_resolved_then_returns_target(
        self, mock_ops_get, mock_get_client
    ):
        # GIVEN a link that resolves to a target entity
        mock_get_client.return_value = MagicMock()
        mock_ops_get.return_value = FakeEntity(
            id="syn999", name="Target"
        )

        # WHEN we resolve the link
        result = EntityService().get_link(
            MagicMock(), "syn500", follow_link=True
        )

        # THEN the target entity is returned
        assert result["id"] == "syn999"
        assert result["name"] == "Target"
        # Verify LinkOptions and FileOptions were passed
        call_kwargs = mock_ops_get.call_args
        assert call_kwargs[1]["link_options"].follow_link is True
        assert call_kwargs[1]["file_options"].download_file is False
