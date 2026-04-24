<!-- Last reviewed: 2026-04 -->

## Project

FastMCP-based server that exposes Synapse (synapse.org) capabilities to LLMs over MCP. Tool catalog is 50+ read-only tools spanning entity, wiki, team, user, activity, evaluation, submission, schema, organization, form, curation, utility, docker, and search domains.

## Stack

- Python 3.11 (CI runs on 3.10)
- FastMCP 3.2.3 (`fastmcp`)
- synapseclient 4.12.0
- pytest with `anyio` (asyncio backend) — see `tests/CLAUDE.md`
- astral/uv for local dev

## Commands

- Install deps: `uv sync`
- Run the full test suite: `uv run pytest`
- Run a single test file: `uv run pytest tests/test_tool_service.py`
- Run the BM25 eval with its printed summary: `uv run pytest tests/evals/test_tool_selection.py -s`
- Run the server over stdio: `uv run synapse-mcp`
- Run the server over HTTP on :9000 (matches the VS Code launch config): `uv run synapse-mcp --http --host 127.0.0.1 --port 9000`

## Tool authoring

Every tool is declared via `@service_tool` (from `synapse_mcp.services`), never `@mcp.tool` directly — because the decorator enforces naming, docstring, and tagging conventions at registration time. See `doc/tool-authoring.md` for the full convention.

- Tool name must start with one of: `get_` `list_` `search_` `create_` `update_` `delete_` `submit_` `check_` `validate_` `register_` — decorator raises `ValueError` at import otherwise.
- First sentence of `description=` must name the concrete Synapse object passed as `synapse_object=` (head-noun matched, plural allowed) — because LLMs pick tools by reading that sentence first, and a typo'd object name makes selection accuracy drop.
- Synonyms live in `synonyms=(...)`; siblings live in `siblings=(...)`. Never embed them in prose — because the `Related terms:` / `Distinct from:` lines the decorator renders keep the primary description scannable for humans while still feeding the BM25 index.
- Tool function bodies stay thin: validate ID with `validate_synapse_id(...)`, delegate to a service-class method, return — because business logic lives in `services/` under `@error_boundary`. Any logic that escapes the tool wrapper becomes a 500 to the LLM.
- ID-accepting parameters must include a concrete example in the description: `syn123456` for entity IDs, numeric strings for team/evaluation/submission/user IDs, URI form for JSON schema `$id` — because LLMs infer argument shape from example values, not just parameter names.
- Tool functions take business args first, `ctx: Context` last. Service methods take `ctx: Context` second (after `self`). Don't swap.

## BM25 discovery transform

`BM25SearchTransform` is registered at the bottom of `src/synapse_mcp/tools.py`, after every `@service_tool` has run — because it builds its index from the catalog at startup. Adding tools below the transform call silently excludes them.

`always_visible = ["search_synapse", "get_entity"]` is intentional — these two cover the common first step of any Synapse workflow (lookup-by-ID, keyword-search). Expanding the list trades LLM context budget for one-shot access. Don't add entries without a justified reason.

## Error response shape

All tool errors are dicts with at minimum `error: str` and `error_type: str`, optional `status_code: int`, plus any context keys declared on the service method's `@error_boundary(error_context_keys=(...))`. Don't invent a different error shape — MCP clients parse this one.

## Related docs

- `doc/tool-authoring.md` — full tool-authoring convention with a canonical example.
- `DEVELOPMENT.md` — contributor setup, linting, release flow.
