"""Catalog-wide guard: every write/destructive tool argument has a description.

``call_read_tool`` / ``call_write_tool`` (discovery.py) promise the LLM a
description on every argument. This test enforces that promise for every
``mutation``-tagged tool (write + destructive) so a new write tool can't ship
with a bare ``inputSchema`` property. It is scoped to ``mutation`` on purpose
— the read catalog has the same gap and is out of scope here (see
CLAUDE.md / the architecture ADR for DPE's PR-47 review-feedback ticket).
"""

import re

import pytest

from synapse_mcp import mcp

pytestmark = pytest.mark.anyio("asyncio")

ID_PARAM_RE = re.compile(r"(^|_)(id|ids)$")


@pytest.fixture
def anyio_backend():
    return "asyncio"


async def test_every_mutation_tool_argument_has_a_description():
    # ``_list_tools`` (private) returns the pre-transform catalog — the same
    # thing the BM25 index consumes — so every registered tool is visible
    # here, not just the always-visible pair the LLM sees by default.
    tools = await mcp._list_tools()

    missing = []
    for tool in tools:
        if "mutation" not in tool.tags:
            continue
        properties = (tool.parameters or {}).get("properties", {})
        for name, schema in properties.items():
            if not schema.get("description"):
                missing.append(f"{tool.name}.{name}")

    assert not missing, f"Parameters missing a description: {missing}"


async def test_every_mutation_tool_id_argument_has_a_concrete_example():
    # CLAUDE.md requires a concrete example on every ID-accepting parameter.
    # Scoped to ``mutation`` for the same reason as the test above — the read
    # catalog has the same gap and is a recorded out-of-scope follow-up.
    tools = await mcp._list_tools()

    missing = []
    for tool in tools:
        if "mutation" not in tool.tags:
            continue
        properties = (tool.parameters or {}).get("properties", {})
        for name, schema in properties.items():
            if not ID_PARAM_RE.search(name):
                continue
            description = schema.get("description") or ""
            if not any(char.isdigit() for char in description):
                missing.append(f"{tool.name}.{name}")

    assert not missing, f"ID parameters missing a concrete example: {missing}"
