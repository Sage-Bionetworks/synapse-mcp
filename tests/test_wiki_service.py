"""Tests for WikiService."""

from dataclasses import dataclass, field
from typing import List, Optional
from unittest.mock import MagicMock, patch

from synapse_mcp.connection_auth import ConnectionAuthError
from synapse_mcp.services.wiki_service import WikiService

TS = "synapse_mcp.services.tool_service"
SVC = "synapse_mcp.services.wiki_service"


@dataclass
class FakeWikiPage:
    id: str = "111"
    title: str = "Home"
    owner_id: str = "syn123"
    markdown: str = "# Welcome"
    parent_wiki_id: Optional[str] = None
    etag: str = "abc"
    created_on: str = "2025-01-01"
    created_by: str = "user1"
    modified_on: str = "2025-01-02"
    modified_by: str = "user2"
    attachment_file_handle_ids: Optional[List[str]] = None
    parent_id: Optional[str] = None
    attachments: List[str] = field(default_factory=list)


@dataclass
class FakeWikiHeader:
    id: str = "1"
    title: str = "Home"
    parent_id: Optional[str] = None


class TestGetWikiPage:
    @patch(f"{TS}.get_synapse_client")
    @patch(f"{SVC}.WikiPage")
    @patch(f"{SVC}.WikiHeader")
    def test_given_entity_with_wiki_when_fetched_without_id_then_finds_root_page(
        self, mock_wh_cls, mock_wp_cls, mock_get_client
    ):
        # GIVEN an entity with a wiki tree where root has id "111"
        mock_get_client.return_value = MagicMock()
        mock_wh_cls.get.return_value = iter(
            [
                FakeWikiHeader(
                    id="111", title="Home", parent_id=None
                ),
                FakeWikiHeader(
                    id="222", title="Methods", parent_id="111"
                ),
            ]
        )
        mock_wp_cls.return_value.get.return_value = (
            FakeWikiPage(
                markdown="# Project Wiki\nMain page."
            )
        )

        # WHEN we get the wiki page without wiki_id
        result = WikiService().get_wiki_page(
            MagicMock(), "syn123"
        )

        # THEN it finds the root page and returns content
        assert result["id"] == "111"
        assert result["title"] == "Home"
        assert "Project Wiki" in result["markdown"]
        # The WikiPage is constructed with the root wiki ID
        mock_wp_cls.assert_called_once_with(
            owner_id="syn123", id="111"
        )

    @patch(f"{TS}.get_synapse_client")
    @patch(f"{SVC}.WikiPage")
    def test_given_wiki_id_when_fetched_then_passes_to_sdk(
        self, mock_wp_cls, mock_get_client
    ):
        # GIVEN a request for a specific wiki page
        mock_get_client.return_value = MagicMock()
        mock_wp_cls.return_value.get.return_value = (
            FakeWikiPage(id="222")
        )

        # WHEN we get a specific wiki page
        WikiService().get_wiki_page(
            MagicMock(), "syn123", wiki_id="222"
        )

        # THEN the wiki ID is passed to the constructor
        mock_wp_cls.assert_called_once_with(
            owner_id="syn123", id="222"
        )

    @patch(f"{TS}.get_synapse_client")
    def test_given_expired_auth_when_fetching_then_returns_error(
        self, mock_get_client
    ):
        # GIVEN expired credentials
        mock_get_client.side_effect = ConnectionAuthError(
            "expired"
        )

        # WHEN we get a wiki page
        result = WikiService().get_wiki_page(
            MagicMock(), "syn123"
        )

        # THEN an auth error is returned
        assert "Authentication required" in result["error"]
        assert result["owner_id"] == "syn123"


class TestGetWikiHeaders:
    @patch(f"{TS}.get_synapse_client")
    @patch(f"{SVC}.WikiHeader")
    def test_given_wiki_tree_when_fetched_then_returns_header_list(
        self, mock_wh_cls, mock_get_client
    ):
        # GIVEN an entity with a wiki page tree
        mock_get_client.return_value = MagicMock()
        mock_wh_cls.get.return_value = iter(
            [
                FakeWikiHeader(
                    id="1", title="Home", parent_id=None
                ),
                FakeWikiHeader(
                    id="2", title="Methods", parent_id="1"
                ),
            ]
        )

        # WHEN we get wiki headers
        result = WikiService().get_wiki_headers(
            MagicMock(), "syn123"
        )

        # THEN the headers are returned as a list
        assert len(result) == 2
        assert result[0]["title"] == "Home"
        assert result[1]["parent_id"] == "1"

    @patch(f"{TS}.get_synapse_client")
    def test_given_expired_auth_when_fetching_then_returns_error_list(
        self, mock_get_client
    ):
        # GIVEN expired credentials
        mock_get_client.side_effect = ConnectionAuthError(
            "expired"
        )

        # WHEN we get wiki headers
        result = WikiService().get_wiki_headers(
            MagicMock(), "syn123"
        )

        # THEN error is wrapped in a list
        assert isinstance(result, list)
        assert "Authentication required" in result[0]["error"]
