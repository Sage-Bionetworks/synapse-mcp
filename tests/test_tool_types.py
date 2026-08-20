"""Tests for the shared write-tool types.

Focuses on the ``UNSET`` sentinel, whose whole purpose is to distinguish an
omitted argument (leave a field unchanged) from an explicit ``null`` (clear
the field). The final test drives a FastMCP tool to confirm the sentinel
survives the framework round-trip, which is the contract the update tools
rely on.
"""

import warnings
from typing import Optional

import pytest
from fastmcp import Context, FastMCP
from pydantic.json_schema import PydanticJsonSchemaWarning

from synapse_mcp.tool_types import UNSET, _Unset

pytestmark = pytest.mark.anyio("asyncio")


@pytest.fixture
def anyio_backend():
    return "asyncio"


class TestUnsetSentinel:
    def test_is_singleton(self):
        # Every construction returns the same object, so ``is UNSET``
        # identity checks in the services are reliable.
        assert _Unset() is UNSET
        assert _Unset() is _Unset()

    def test_is_falsy(self):
        assert not UNSET
        assert bool(UNSET) is False

    def test_repr_is_readable(self):
        assert repr(UNSET) == "UNSET"

    def test_is_distinct_from_none(self):
        assert UNSET is not None
        assert UNSET != None  # noqa: E711 - intentional identity/value check


class TestUnsetThroughFastMCP:
    async def test_omitted_stays_unset_explicit_null_becomes_none(self):
        # This is the behavior the update tools depend on: an omitted field
        # arrives as UNSET (leave unchanged); an explicit null arrives as
        # None (clear).
        mcp = FastMCP("test")
        seen = {}

        # Registering a tool with an UNSET default emits a cosmetic pydantic
        # warning (the non-JSON default is dropped from the schema, which is
        # intended). tools.py suppresses it at import; do the same here.
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", PydanticJsonSchemaWarning)

            @mcp.tool
            async def demo(
                entity_id: str,
                description: Optional[str] = UNSET,
                ctx: Context = None,
            ) -> dict:
                seen.clear()
                seen["description"] = description
                seen["is_unset"] = description is UNSET
                return {"ok": True}

        await mcp.call_tool("demo", {"entity_id": "syn1"})
        assert seen["is_unset"] is True

        await mcp.call_tool(
            "demo", {"entity_id": "syn1", "description": None}
        )
        assert seen["is_unset"] is False
        assert seen["description"] is None

        await mcp.call_tool(
            "demo", {"entity_id": "syn1", "description": "hi"}
        )
        assert seen["description"] == "hi"
