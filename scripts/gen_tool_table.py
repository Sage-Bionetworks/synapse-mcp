#!/usr/bin/env python3
"""Generate the Available Tools table in README.md from the live catalog.

Introspects the registered FastMCP tools (the same pre-transform catalog the
BM25 eval consumes) and renders a Markdown table that is injected into
README.md between the BEGIN/END markers. Keeping the table generated means it
never drifts from ``src/synapse_mcp/tools.py``.

Usage:
    uv run python scripts/gen_tool_table.py            # rewrite README.md
    uv run python scripts/gen_tool_table.py --write     # same as default
    uv run python scripts/gen_tool_table.py --check      # verify, never write

``--write`` exits non-zero if it changed the file (pre-commit convention).
``--check`` exits non-zero if the table is stale, printing a unified diff.
"""

from __future__ import annotations

import argparse
import asyncio
import difflib
import os
import sys
from pathlib import Path
from typing import Iterable

# app.py raises at import time without auth configured; set a dummy PAT before
# importing synapse_mcp (same trick as tests/conftest.py).
os.environ.setdefault("SYNAPSE_PAT", "readme-gen")

from fastmcp.tools import Tool  # noqa: E402  (base class, not FunctionTool)
from synapse_mcp import mcp  # noqa: E402
from synapse_mcp.services.tool_service import ServiceName  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
README_PATH = REPO_ROOT / "README.md"

BEGIN_MARKER = (
    "<!-- BEGIN GENERATED TOOLS: run "
    "`uv run python scripts/gen_tool_table.py` to update -->"
)
END_MARKER = "<!-- END GENERATED TOOLS -->"

# Curated domain order, mirroring the "Domain N" sections in tools.py so the
# README and source tell the same story. Tools with a domain not listed here
# are appended alphabetically after a warning (never silently dropped).
DOMAIN_ORDER = [
    "entity",
    "search",
    "activity",
    "schema",
    "wiki",
    "team",
    "user",
    "evaluation",
    "submission",
    "curation",
    "organization",
    "form",
    "utility",
]

# Service-name tags, used to pick the domain tag out of the full tag set
# (which also carries alias tags like "read"/"readonly").
_SERVICE_TAGS = set(ServiceName.__args__)


def _domain_for(tool: Tool) -> str:
    """Return the single service-domain tag for a tool."""
    domains = sorted(set(tool.tags) & _SERVICE_TAGS)
    if not domains:
        return "?"
    return domains[0]


def _signature(tool: Tool) -> str:
    """Render ``name(required_param, ...)`` from the tool's parameter schema.

    ``ctx`` is already excluded by FastMCP. Only required params are shown;
    tools whose args are all optional render as ``name()``.
    """
    params = getattr(tool, "parameters", None) or {}
    required = params.get("required", []) or []
    return f"{tool.name}({', '.join(required)})"


# Abbreviations whose trailing period is not a sentence end. Compared
# case-insensitively against the word immediately before a candidate period.
_ABBREVIATIONS = {"e.g", "i.e", "etc", "vs", "cf", "al", "no", "st"}


def _first_sentence(description: str) -> str:
    """First sentence of the core description.

    The @service_tool decorator appends ``Related terms:`` / ``Distinct from:``
    sections separated by a blank line; split those off first, then take the
    first sentence (which the decorator guarantees names the object + intent).
    Periods inside common abbreviations (e.g., i.e.) are not treated as
    sentence ends.
    """
    core = description.split("\n\n", 1)[0].strip()
    for i, ch in enumerate(core):
        if ch != "." or i + 1 >= len(core) or core[i + 1] not in " \n\t":
            continue
        # Word preceding this period; skip if it's a known abbreviation
        # or a single letter (e.g. "A. Smith"). "e.g" matches after the
        # leading "e." is stripped, so compare the final dotted segment too.
        word = core[:i].rsplit(" ", 1)[-1].lower().lstrip("([")
        dotted = word.rsplit(".", 1)[-1] if "." in word else word
        if word in _ABBREVIATIONS or dotted in _ABBREVIATIONS or len(word) == 1:
            continue
        return core[: i + 1].strip()
    return core


def _escape_cell(text: str) -> str:
    """Escape characters that would break a Markdown table cell."""
    return text.replace("|", "\\|")


def _sort_key(tool: Tool, domain: str):
    try:
        domain_rank = DOMAIN_ORDER.index(domain)
    except ValueError:
        # Unknown domain: sort after all known ones, alphabetically.
        domain_rank = len(DOMAIN_ORDER)
    return (domain_rank, domain, tool.name)


def build_table(tools: Iterable[Tool]) -> str:
    """Build the Markdown tool table from a catalog of FastMCP tools."""
    # Resolve each tool's domain once; every downstream step reuses it.
    pairs = [(tool, _domain_for(tool)) for tool in tools]
    pairs.sort(key=lambda pair: _sort_key(*pair))

    unknown = sorted({d for _, d in pairs} - set(DOMAIN_ORDER) - {"?"})
    if unknown:
        print(
            f"WARNING: tools have domains not in DOMAIN_ORDER: {unknown}. "
            "Add them to scripts/gen_tool_table.py to control ordering.",
            file=sys.stderr,
        )

    lines = [
        "| Tool | Domain | Description |",
        "| --- | --- | --- |",
    ]
    for tool, domain in pairs:
        signature = _escape_cell(_signature(tool))
        domain_cell = _escape_cell(domain)
        description = _escape_cell(_first_sentence(tool.description))
        lines.append(f"| `{signature}` | {domain_cell} | {description} |")
    return "\n".join(lines)


async def _load_tools():
    # _list_tools() returns the raw pre-transform catalog (all tools).
    # list_tools() would return only the post-transform always-visible +
    # synthetic search tools. See tests/evals/test_tool_selection.py.
    return await mcp._list_tools()


def _render_block(table: str) -> str:
    """Wrap the table in the BEGIN/END markers."""
    return f"{BEGIN_MARKER}\n\n{table}\n\n{END_MARKER}"


def _replace_block(readme_text: str, new_block: str) -> str:
    """Return README text with the marked block replaced by new_block."""
    start = readme_text.find(BEGIN_MARKER)
    end = readme_text.find(END_MARKER, start) if start != -1 else -1
    if start == -1 or end == -1:
        raise SystemExit(
            "Could not find the BEGIN/END GENERATED TOOLS markers in "
            f"{README_PATH}. Add them where the table should live."
        )
    end += len(END_MARKER)
    return readme_text[:start] + new_block + readme_text[end:]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--write",
        action="store_true",
        help="Rewrite the table in README.md (default).",
    )
    mode.add_argument(
        "--check",
        action="store_true",
        help="Verify README.md is in sync; never write. Non-zero if stale.",
    )
    args = parser.parse_args()

    tools = asyncio.run(_load_tools())
    new_block = _render_block(build_table(tools))

    readme_text = README_PATH.read_text()
    updated_text = _replace_block(readme_text, new_block)

    if args.check:
        if updated_text != readme_text:
            print(
                "README.md tool table is out of sync. Run:\n"
                "    uv run python scripts/gen_tool_table.py\n",
                file=sys.stderr,
            )
            diff = difflib.unified_diff(
                readme_text.splitlines(keepends=True),
                updated_text.splitlines(keepends=True),
                fromfile="README.md (current)",
                tofile="README.md (expected)",
            )
            sys.stderr.writelines(diff)
            return 1
        return 0

    # --write (default)
    if updated_text != readme_text:
        README_PATH.write_text(updated_text)
        print(f"Updated tool table in {README_PATH}")
        return 1
    print("README.md tool table already up to date.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
