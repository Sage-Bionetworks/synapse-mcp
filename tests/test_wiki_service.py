"""Tests for WikiService."""

from dataclasses import dataclass, field
from typing import List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from synapseclient.core.exceptions import SynapseHTTPError

from synapse_mcp.connection_auth import ConnectionAuthError
from synapse_mcp.services.wiki_service import WikiService

pytestmark = pytest.mark.anyio("asyncio")


@pytest.fixture
def anyio_backend():
    return "asyncio"


TS = "synapse_mcp.services.tool_service"
SVC = "synapse_mcp.services.wiki_service"


@dataclass
class FakeWikiPage:
    id: str = "111"
    etag: str = "abc"
    title: str = "Home"
    parent_id: Optional[str] = None
    markdown: str = "# Welcome"
    attachments: Optional[List[str]] = None
    owner_id: str = "syn123"
    created_on: str = "2025-01-01"
    created_by: str = "user1"
    modified_on: str = "2025-01-02"
    modified_by: str = "user2"
    wiki_version: str = "1"
    markdown_file_handle_id: Optional[str] = "abcd"
    attachment_file_handle_ids: Optional[List[str]] = None


@dataclass
class FakeWikiHeader:
    id: str = "1"
    title: str = "Home"
    parent_id: Optional[str] = None


class TestGetWikiPage:
    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.WikiPage")
    @patch(f"{SVC}.WikiHeader")
    async def test_given_entity_with_wiki_when_fetched_without_id_then_finds_root_page(
        self, mock_wh_cls, mock_wp_cls, mock_get_client
    ):
        mock_get_client.return_value = MagicMock()

        async def _wiki_headers(**kw):
            yield FakeWikiHeader(id="111", title="Home", parent_id=None)
            yield FakeWikiHeader(id="222", title="Methods", parent_id="111")

        mock_wh_cls.get_async = _wiki_headers
        mock_wp_cls.return_value.get_async = AsyncMock(
            return_value=FakeWikiPage(markdown="# Project Wiki\nMain page.")
        )

        result = await WikiService().get_wiki_page(MagicMock(), "syn123")

        mock_wp_cls.assert_called_once_with(owner_id="syn123", id="111")

        assert result["id"] == "111"
        assert result["title"] == "Home"
        assert result["parent_id"] is None
        assert result["owner_id"] == "syn123"
        assert result["wiki_version"] == "1"
        assert result["markdown_file_handle_id"] == "abcd"
        assert result["attachment_file_handle_ids"] is None
        assert result["created_on"] == "2025-01-01"
        assert result["created_by"] == "user1"
        assert result["modified_on"] == "2025-01-02"
        assert result["modified_by"] == "user2"
        assert result["markdown"] == "# Project Wiki\nMain page."

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.WikiPage")
    async def test_given_wiki_id_when_fetched_then_passes_to_sdk(
        self, mock_wp_cls, mock_get_client
    ):
        mock_get_client.return_value = MagicMock()
        mock_wp_cls.return_value.get_async = AsyncMock(
            return_value=FakeWikiPage(id="222", title="wiki page 222")
        )

        result = await WikiService().get_wiki_page(MagicMock(), "syn123", wiki_id="222")

        mock_wp_cls.assert_called_once_with(owner_id="syn123", id="222")
        assert result["id"] == "222"
        assert result["title"] == "wiki page 222"
        assert result["parent_id"] is None
        assert result["owner_id"] == "syn123"
        assert result["wiki_version"] == "1"
        assert result["markdown_file_handle_id"] == "abcd"
        assert result["attachment_file_handle_ids"] is None
        assert result["created_on"] == "2025-01-01"
        assert result["created_by"] == "user1"
        assert result["modified_on"] == "2025-01-02"
        assert result["modified_by"] == "user2"
        assert result["markdown"] == "# Welcome"

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    async def test_given_expired_auth_when_fetched_then_returns_error(
        self, mock_get_client
    ):
        mock_get_client.side_effect = ConnectionAuthError("expired")

        result = await WikiService().get_wiki_page(MagicMock(), "syn123")

        assert "Authentication required" in result["error"]
        assert result["owner_id"] == "syn123"

    async def test_given_missing_owner_id_when_fetched_then_returns_error(self):
        result = await WikiService().get_wiki_page(MagicMock(), "")

        assert result["error"] == "The owner_id is required to get a wiki page"

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.WikiHeader")
    async def test_given_entity_without_wiki_then_returns_not_found(
        self, mock_wh_cls, mock_get_client
    ):
        mock_get_client.return_value = MagicMock()

        async def _raise_404(**_):
            exc = SynapseHTTPError("404 Client Error: A root wiki does not exist")
            exc.response = MagicMock(status_code=404)
            raise exc
            if False:
                yield

        mock_wh_cls.get_async = _raise_404

        result = await WikiService().get_wiki_page(MagicMock(), "syn123")

        assert result["error"] == "No root wiki page found for syn123"
        assert result["owner_id"] == "syn123"


class TestGetWikiHeaders:
    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.WikiHeader")
    async def test_given_wiki_tree_when_fetched_then_returns_header_list(
        self, mock_wh_cls, mock_get_client
    ):
        mock_get_client.return_value = MagicMock()

        async def _wiki_headers(**kw):
            yield FakeWikiHeader(id="1", title="Home", parent_id=None)
            yield FakeWikiHeader(id="2", title="subpage 1", parent_id="1")

        mock_wh_cls.get_async = _wiki_headers

        result = await WikiService().get_wiki_headers(MagicMock(), "syn123")

        assert len(result) == 2
        assert result[0]["title"] == "Home"
        assert result[0]["parent_id"] is None
        assert result[1]["title"] == "subpage 1"
        assert result[1]["parent_id"] == "1"

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    async def test_given_expired_auth_when_fetched_then_returns_error_list(
        self, mock_get_client
    ):
        mock_get_client.side_effect = ConnectionAuthError("expired")

        result = await WikiService().get_wiki_headers(MagicMock(), "syn123")

        assert isinstance(result, list)
        assert "Authentication required" in result[0]["error"]

    async def test_given_missing_owner_id_then_returns_error(self):
        result = await WikiService().get_wiki_headers(MagicMock(), "")

        assert result["error"] == "The owner_id is required to get the wiki header tree"

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.WikiHeader")
    async def test_given_entity_with_no_wiki_then_returns_error(
        self, mock_wh_cls, mock_get_client
    ):
        mock_get_client.return_value = MagicMock()

        async def _empty(**_):
            if False:
                yield

        mock_wh_cls.get_async = _empty
        result = await WikiService().get_wiki_headers(MagicMock(), "syn123")

        assert result["error"] == "No wiki headers found for the given owner_id"


@dataclass
class FakeWikiHistorySnapshot:
    version: int = 1
    modified_on: str = "2025-01-01"


class TestGetWikiHistory:
    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.WikiHistorySnapshot")
    async def test_given_wiki_when_history_fetched_then_returns_snapshots(
        self, mock_hist_cls, mock_get_client
    ):
        mock_get_client.return_value = MagicMock()

        async def _snapshots(**kw):
            yield FakeWikiHistorySnapshot(version=1)
            yield FakeWikiHistorySnapshot(version=2)
            yield FakeWikiHistorySnapshot(version=3)

        mock_hist_cls.get_async = _snapshots

        result = await WikiService().get_wiki_history(MagicMock(), "syn123", "111")

        assert [s["version"] for s in result] == [1, 2, 3]

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.WikiHistorySnapshot")
    async def test_given_limit_when_history_fetched_then_truncates(
        self, mock_hist_cls, mock_get_client
    ):
        mock_get_client.return_value = MagicMock()

        async def _snapshots(**kw):
            for i in range(5):
                yield FakeWikiHistorySnapshot(version=i)

        mock_hist_cls.get_async = _snapshots

        result = await WikiService().get_wiki_history(
            MagicMock(), "syn123", "111", limit=2
        )

        assert len(result) == 2
        assert [s["version"] for s in result] == [0, 1]

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    async def test_given_expired_auth_when_history_fetched_then_returns_error_list(
        self, mock_get_client
    ):
        mock_get_client.side_effect = ConnectionAuthError("expired")

        result = await WikiService().get_wiki_history(MagicMock(), "syn123", "111")

        assert isinstance(result, list)
        assert "Authentication required" in result[0]["error"]

    async def test_given_missing_owner_id_when_history_fetched_then_returns_error(self):
        result = await WikiService().get_wiki_history(MagicMock(), "", "111")

        assert (
            result["error"]
            == "Both the owner_id and wiki_id are required to get the wiki history"
        )

    async def test_given_missing_wiki_id_when_history_fetched_then_returns_error(self):
        result = await WikiService().get_wiki_history(MagicMock(), "syn123", "")

        assert (
            result["error"]
            == "Both the owner_id and wiki_id are required to get the wiki history"
        )


@dataclass
class FakeWikiOrderHint:
    owner_id: str = "syn123"
    owner_object_type: str = "entity"
    id_list: List[str] = field(default_factory=list)
    etag: str = "abc"


class TestGetWikiOrderHint:
    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.WikiOrderHint")
    async def test_given_wiki_when_order_hint_fetched_then_returns_dict(
        self, mock_hint_cls, mock_get_client
    ):
        mock_get_client.return_value = MagicMock()
        mock_hint_cls.return_value.get_async = AsyncMock(
            return_value=FakeWikiOrderHint(
                owner_id="syn123",
                owner_object_type="entity",
                id_list=["111", "222", "333"],
                etag="abc",
            )
        )

        result = await WikiService().get_wiki_order_hint(MagicMock(), "syn123")

        assert result["owner_id"] == "syn123"
        assert result["owner_object_type"] == "entity"
        assert result["id_list"] == ["111", "222", "333"]
        assert result["etag"] == "abc"

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    async def test_given_expired_auth_when_order_hint_fetched_then_returns_error(
        self, mock_get_client
    ):
        mock_get_client.side_effect = ConnectionAuthError("expired")

        result = await WikiService().get_wiki_order_hint(MagicMock(), "syn123")

        assert "Authentication required" in result["error"]
        assert result["owner_id"] == "syn123"

    async def test_given_missing_owner_id_when_order_hint_fetched_then_returns_error(
        self,
    ):
        result = await WikiService().get_wiki_order_hint(MagicMock(), "")

        assert result["error"] == "The owner_id is required to get the wiki order hint"

    @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
    @patch(f"{SVC}.WikiOrderHint")
    async def test_given_no_hint_set_when_order_hint_fetched_then_returns_error(
        self, mock_hint_cls, mock_get_client
    ):
        mock_get_client.return_value = MagicMock()
        mock_hint_cls.return_value.get_async = AsyncMock(return_value=None)

        result = await WikiService().get_wiki_order_hint(MagicMock(), "syn123")

        assert (
            result["error"] == "The wiki order hint is not set for the given owner_id."
        )
