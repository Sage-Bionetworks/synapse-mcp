<!-- Last reviewed: 2026-04 -->

## Project

Test suite for the Synapse MCP server. One `test_<domain>_service.py` per service module plus decorator tests in `test_tool_service.py` and a BM25 tool-selection eval under `tests/evals/`. Tests use `pytest` + `anyio` (asyncio backend) and never hit the real Synapse API — every SDK call is mocked.

## Conventions

- **Every test module declares the async backend.** At module top:
  ```python
  pytestmark = pytest.mark.anyio("asyncio")

  @pytest.fixture
  def anyio_backend():
      return "asyncio"
  ```
  Without the fixture, the `anyio` plugin falls back to parametrizing across trio+asyncio and most tests time out on trio.

- **Mock where the name is USED, not where it's DEFINED.** Example: to stub `operations_get_async` called inside `EntityService`, patch `synapse_mcp.services.entity_service.operations_get_async`, not `synapseclient.operations.get_async`. Patching the source module doesn't rebind the import-time reference that the service already holds.

- **Use `AsyncMock` for coroutines, `MagicMock` for everything else.** Common pattern:
  ```python
  @patch(f"{SVC}.operations_get_async", new_callable=AsyncMock)
  @patch(f"{TS}.get_synapse_client", new_callable=AsyncMock)
  async def test_get_entity(self, mock_client, mock_sdk):
      mock_sdk.return_value = FakeEntity(id="syn1")
      ...
  ```
  `MagicMock` on an async function returns a `MagicMock` instead of awaiting, which surfaces as a `TypeError: object MagicMock can't be used in 'await' expression`.

- **Build fake dataclasses as SDK stand-ins.** `serialize_model` walks any `@dataclass`, so a local `@dataclass class FakeEntity: id: str = "syn1"; ...` is the simplest way to mock a synapseclient return value without importing the real class. Each test module defines its own fakes — don't try to share them.

- **Patching path constants.** Convention is to define `TS = "synapse_mcp.services.tool_service"` and `SVC = "synapse_mcp.services.<domain>_service"` at the module top and interpolate with f-strings in `@patch` decorators. Keeps paths consistent when the module layout changes.

## Eval harness — `tests/evals/test_tool_selection.py`

Drives the FastMCP BM25 index directly against the raw tool catalog (no LLM in the loop). Enforces tool-selection accuracy per natural-language query.

- **Uses `mcp._list_tools()` (private), not `mcp.list_tools()`.** `list_tools` runs through the registered transforms — post-transform the catalog is only `[get_entity, search_synapse, search_tools, call_tool]`, which defeats the eval. `_list_tools` returns the pre-transform 50-tool catalog, which is also what `BM25SearchTransform._search()` consumes internally.
- **Each entry in `QUERY_FIXTURES` becomes a parametrized test** (`test_expected_tool_in_top_3`) that asserts the target tool is in the top-3 BM25 results. A regression on any query fails CI — this is stricter than the aggregate ≥90% top-3 gate mentioned in the PR description, because it enforces per-query.
- **Add new fixtures for new tools.** When adding a tool (or changing names/synonyms/siblings), add at least one realistic user-language query here targeting it. Don't use Synapse jargon in the query — use what a real user would type.

## `conftest.py` notes

- Sets `SYNAPSE_PAT=fake-for-tests` before any `synapse_mcp` import because `app.py` raises `ValueError` at import time without auth configured. Don't remove or override.
- Adds `<repo>/src` to `sys.path` so editable installs aren't strictly required. Don't rely on this outside tests.
- Defines `make_task(...)` helpers for curation-task shapes. Reuse these from curation tests instead of hand-rolling.

## Constraints

- Do NOT make real network calls. Every SDK function must be mocked. There's no test fixture for live Synapse auth and running against prod from CI would leak the dummy token.
- Do NOT skip the `anyio_backend` fixture. Without it, async tests silently double-run or time out.
