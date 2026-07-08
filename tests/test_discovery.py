"""Tests for the split read/write discovery transform.

Covers the post-transform tool listing (pinned reads + search + two call
proxies) and the tag-based routing that keeps read tools out of
``call_write_tool`` and write tools out of ``call_read_tool``.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from synapse_mcp.discovery import (
    WRITE_CALL_TOOL_NAME,
    SplitCallTransform,
)

pytestmark = pytest.mark.anyio("asyncio")


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _tool(name, tags):
    """Minimal stand-in for a FastMCP Tool with a name and tag set."""
    return SimpleNamespace(name=name, tags=set(tags))


def _transform():
    return SplitCallTransform(
        max_results=7,
        always_visible=["search_synapse", "get_entity"],
        call_tool_name="call_read_tool",
    )


class TestTransformShape:
    async def test_transform_exposes_pinned_reads_and_two_proxies(self):
        # GIVEN a catalog of pinned reads, a hidden read, and a write
        transform = _transform()
        tools = [
            _tool("get_entity", {"entity", "read", "readonly"}),
            _tool("search_synapse", {"search", "read", "readonly"}),
            _tool("get_wiki_page", {"wiki", "read", "readonly"}),
            _tool("create_entity", {"entity", "write", "mutation"}),
        ]

        # WHEN the catalog is transformed
        result = await transform.transform_tools(tools)

        # THEN only pinned reads + the three synthetic tools remain
        names = sorted(t.name for t in result)
        assert names == [
            "call_read_tool",
            "call_write_tool",
            "get_entity",
            "search_synapse",
            "search_tools",
        ]


class TestRouting:
    async def _catalog(self, transform):
        transform.get_tool_catalog = AsyncMock(
            return_value=[
                _tool("get_entity", {"entity", "read", "readonly"}),
                _tool("create_entity", {"entity", "write", "mutation"}),
                _tool("delete_entity", {"entity", "destructive", "mutation"}),
            ]
        )

    async def test_read_proxy_rejects_mutation_tool(self):
        # GIVEN the read proxy and a catalog containing a write tool
        transform = _transform()
        await self._catalog(transform)

        # WHEN a mutating tool is routed through the read proxy
        # THEN it is rejected before dispatch
        with pytest.raises(ValueError, match="call_write_tool"):
            await transform._require_mutation_role(
                SimpleNamespace(), "create_entity", expect_mutation=False
            )

    async def test_write_proxy_rejects_read_tool(self):
        # GIVEN the write proxy and a catalog containing a read tool
        transform = _transform()
        await self._catalog(transform)

        # WHEN a read tool is routed through the write proxy
        # THEN it is rejected before dispatch
        with pytest.raises(ValueError, match="call_read_tool"):
            await transform._require_mutation_role(
                SimpleNamespace(), "get_entity", expect_mutation=True
            )

    async def test_write_proxy_allows_destructive_tool(self):
        # GIVEN a destructive tool (mutation tag) and the write proxy
        transform = _transform()
        await self._catalog(transform)

        # WHEN it is routed through the write proxy, no error is raised
        await transform._require_mutation_role(
            SimpleNamespace(), "delete_entity", expect_mutation=True
        )

    async def test_read_proxy_allows_read_tool(self):
        # GIVEN a read tool and the read proxy
        transform = _transform()
        await self._catalog(transform)

        # WHEN it is routed through the read proxy, no error is raised
        await transform._require_mutation_role(
            SimpleNamespace(), "get_entity", expect_mutation=False
        )

    @pytest.mark.parametrize(
        "synthetic",
        ["search_tools", "call_read_tool", WRITE_CALL_TOOL_NAME],
    )
    async def test_proxies_reject_synthetic_names(self, synthetic):
        # GIVEN any synthetic discovery tool name
        transform = _transform()
        await self._catalog(transform)

        # WHEN routed through either proxy, it is rejected as synthetic
        with pytest.raises(ValueError, match="synthetic"):
            await transform._require_mutation_role(
                SimpleNamespace(), synthetic, expect_mutation=True
            )

    async def test_unknown_tool_passes_through(self):
        # GIVEN a name not in the catalog
        transform = _transform()
        await self._catalog(transform)

        # WHEN routed, the guard defers to downstream dispatch (no raise)
        await transform._require_mutation_role(
            SimpleNamespace(), "does_not_exist", expect_mutation=True
        )
