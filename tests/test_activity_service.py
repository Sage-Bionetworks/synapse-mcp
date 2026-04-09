"""Tests for ActivityService."""

from dataclasses import dataclass, field
from typing import List, Optional
from unittest.mock import MagicMock, patch

from synapse_mcp.connection_auth import ConnectionAuthError
from synapse_mcp.services.activity_service import ActivityService

TS = "synapse_mcp.services.tool_service"
SVC = "synapse_mcp.services.activity_service"


@dataclass
class FakeUsedEntity:
    reference_target_id: str = "syn100"
    reference_target_version: Optional[int] = None
    was_executed: bool = False


@dataclass
class FakeActivity:
    id: str = "act123"
    name: str = "Analysis Pipeline"
    description: Optional[str] = None
    etag: str = "abc"
    created_on: str = "2025-01-01"
    modified_on: str = "2025-01-02"
    created_by: str = "user1"
    modified_by: str = "user2"
    used: List[FakeUsedEntity] = field(
        default_factory=list
    )
    executed: List[FakeUsedEntity] = field(
        default_factory=list
    )


class TestGetProvenance:
    @patch(f"{TS}.get_synapse_client")
    @patch(f"{SVC}.Activity")
    def test_given_entity_with_provenance_when_fetched_then_returns_activity(
        self, mock_activity_cls, mock_get_client
    ):
        # GIVEN an entity that has provenance
        mock_get_client.return_value = MagicMock()
        mock_activity_cls.get.return_value = FakeActivity()

        # WHEN we get provenance
        result = ActivityService().get_provenance(
            MagicMock(), "syn456"
        )

        # THEN the activity dict is returned
        assert result["entity_id"] == "syn456"
        assert result["activity"]["id"] == "act123"
        assert result["activity"]["name"] == "Analysis Pipeline"

    @patch(f"{TS}.get_synapse_client")
    @patch(f"{SVC}.Activity")
    def test_given_no_provenance_when_fetched_then_returns_error(
        self, mock_activity_cls, mock_get_client
    ):
        # GIVEN an entity with no provenance
        mock_get_client.return_value = MagicMock()
        mock_activity_cls.get.return_value = None

        # WHEN we get provenance
        result = ActivityService().get_provenance(
            MagicMock(), "syn456"
        )

        # THEN an error message is returned
        assert "No provenance record found" in result["error"]
        assert result["entity_id"] == "syn456"

    @patch(f"{TS}.get_synapse_client")
    @patch(f"{SVC}.Activity")
    def test_given_version_when_fetching_then_passes_to_sdk(
        self, mock_activity_cls, mock_get_client
    ):
        # GIVEN a request for a specific version
        mock_get_client.return_value = MagicMock()
        mock_activity_cls.get.return_value = FakeActivity()

        # WHEN we get provenance with a version
        result = ActivityService().get_provenance(
            MagicMock(), "syn456", version=3
        )

        # THEN the version is passed and included in response
        mock_activity_cls.get.assert_called_once_with(
            parent_id="syn456",
            parent_version_number=3,
            synapse_client=mock_get_client.return_value,
        )
        assert result["version"] == 3

    @patch(f"{TS}.get_synapse_client")
    def test_given_expired_auth_when_fetching_then_returns_error(
        self, mock_get_client
    ):
        # GIVEN expired credentials
        mock_get_client.side_effect = ConnectionAuthError(
            "expired"
        )

        # WHEN we get provenance
        result = ActivityService().get_provenance(
            MagicMock(), "syn456"
        )

        # THEN an auth error is returned
        assert "Authentication required" in result["error"]
        assert result["entity_id"] == "syn456"
