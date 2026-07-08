"""Discovery transform with separate read and write call proxies.

FastMCP's stock ``BM25SearchTransform`` collapses the catalog into one
``search_tools`` tool plus a single ``call_tool`` proxy. Every tool — read
or write — is then reachable through that one proxy. Many MCP clients gate
permissions at the **tool-name** level (not via the MCP ``annotations``
hints), so a single proxy cannot separate reads from writes: allowing the
proxy allows everything.

``SplitCallTransform`` keeps the shared ``search_tools`` (it still indexes
and returns the whole catalog) but exposes **two** call proxies:

* ``call_read_tool`` — executes read tools only; rejects any tool tagged
  ``mutation``.
* ``call_write_tool`` — executes write/destructive tools only; rejects any
  tool that is *not* tagged ``mutation``.

Routing keys on the ``mutation`` alias tag that ``@service_tool`` already
attaches to every ``write``/``destructive`` tool (see
``services.tool_service._tags_for``). A client can now allow ``call_read_tool``
while withholding ``call_write_tool`` to run the server read-only.
"""

from collections.abc import Sequence
from typing import Annotated, Any, Optional

from fastmcp.server.context import Context
from fastmcp.server.transforms import GetToolNext
from fastmcp.server.transforms.search import BM25SearchTransform
from fastmcp.tools.base import Tool, ToolResult
from fastmcp.utilities.versions import VersionSpec

# Alias tag attached to every write/destructive tool by ``_tags_for``.
MUTATION_TAG = "mutation"

# Name of the second proxy that executes mutating tools.
WRITE_CALL_TOOL_NAME = "call_write_tool"


class SplitCallTransform(BM25SearchTransform):
    """BM25 discovery with split read/write call proxies.

    Reuses the parent's BM25 index and ``search_tools`` unchanged, and the
    parent's ``call_tool`` proxy (renamed to ``call_read_tool`` via the
    ``call_tool_name`` argument) for reads. Adds a ``call_write_tool`` proxy
    for mutations. Each proxy enforces that the target tool's ``mutation``
    tag matches the proxy's role before dispatching.
    """

    async def transform_tools(
        self, tools: Sequence[Tool]
    ) -> Sequence[Tool]:
        """Expose pinned tools + search + both call proxies."""
        pinned = [t for t in tools if t.name in self._always_visible]
        return [
            *pinned,
            self._make_search_tool(),
            self._make_call_tool(),
            self._make_write_call_tool(),
        ]

    async def get_tool(
        self,
        name: str,
        call_next: GetToolNext,
        *,
        version: Optional[VersionSpec] = None,
    ) -> Optional[Tool]:
        """Intercept the three synthetic tool names; delegate the rest."""
        if name == WRITE_CALL_TOOL_NAME:
            return self._make_write_call_tool()
        return await super().get_tool(name, call_next, version=version)

    def _make_write_call_tool(self) -> Tool:
        """Create the ``call_write_tool`` proxy for mutating tools."""
        transform = self

        async def call_write_tool(
            name: Annotated[str, "The name of the write tool to call"],
            arguments: Annotated[
                Optional[dict[str, Any]],
                "Arguments to pass to the tool",
            ] = None,
            ctx: Context = None,  # type: ignore[assignment]
        ) -> ToolResult:
            """Call a write/destructive tool discovered via search_tools.

            Only tools that create, update, or delete Synapse objects are
            reachable here. Read-only tools must be called via
            call_read_tool.
            """
            await transform._require_mutation_role(
                ctx, name, expect_mutation=True
            )
            return await ctx.fastmcp.call_tool(name, arguments)

        return Tool.from_function(
            fn=call_write_tool, name=WRITE_CALL_TOOL_NAME
        )

    def _make_call_tool(self) -> Tool:
        """Wrap the parent read proxy to reject mutating tools."""
        read_tool = super()._make_call_tool()
        transform = self
        read_tool_name = self._call_tool_name

        async def call_read_tool(
            name: Annotated[str, "The name of the read tool to call"],
            arguments: Annotated[
                Optional[dict[str, Any]],
                "Arguments to pass to the tool",
            ] = None,
            ctx: Context = None,  # type: ignore[assignment]
        ) -> ToolResult:
            """Call a read-only tool discovered via search_tools.

            Only tools that read Synapse state are reachable here. Tools
            that create, update, or delete must be called via
            call_write_tool.
            """
            await transform._require_mutation_role(
                ctx, name, expect_mutation=False
            )
            return await ctx.fastmcp.call_tool(name, arguments)

        return Tool.from_function(fn=call_read_tool, name=read_tool_name)

    async def _require_mutation_role(
        self, ctx: Context, name: str, *, expect_mutation: bool
    ) -> None:
        """Raise ValueError if ``name``'s mutation role mismatches the proxy.

        ``expect_mutation=True`` is the write proxy (only mutating tools
        allowed); ``False`` is the read proxy (only read tools allowed). The
        synthetic proxy/search names are always rejected — they are not
        callable through a proxy. Unknown names pass through so the downstream
        dispatch surfaces the usual not-found error.
        """
        synthetic = {
            self._search_tool_name,
            self._call_tool_name,
            WRITE_CALL_TOOL_NAME,
        }
        if name in synthetic:
            raise ValueError(
                f"'{name}' is a synthetic discovery tool and cannot be "
                "called via a call proxy"
            )

        catalog = await self.get_tool_catalog(ctx)
        target = next((t for t in catalog if t.name == name), None)
        if target is None:
            # Let the downstream call surface the not-found error verbatim.
            return

        is_mutation = MUTATION_TAG in (target.tags or set())
        if is_mutation and not expect_mutation:
            raise ValueError(
                f"'{name}' is a write/destructive tool; call it via "
                "call_write_tool, not call_read_tool"
            )
        if not is_mutation and expect_mutation:
            raise ValueError(
                f"'{name}' is a read-only tool; call it via call_read_tool, "
                "not call_write_tool"
            )
