<!-- Last reviewed: 2026-04 -->

## Project

FastMCP-based server that exposes Synapse (synapse.org) capabilities to LLMs over MCP. Tool catalog is 72 tools (48 read-only, 24 write/destructive) spanning entity, wiki, team, user, activity, evaluation, submission, schema, organization, form, curation, utility, and search domains.

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
- Tool functions put `ctx: Context` last, EXCEPT when every business arg is optional (defaulted): then `ctx` comes first, because Python forbids a non-default arg after a defaulted one (e.g. `get_entity_provenance(ctx, entity_id=None, ...)`). Service methods take `ctx: Context` first, then business args — no `self`, since services are `@staticmethod`. Don't swap the service/tool convention.

## BM25 discovery transform

`SplitCallTransform` (`src/synapse_mcp/discovery.py`, a `BM25SearchTransform` subclass) is registered at the bottom of `src/synapse_mcp/tools.py`, after every `@service_tool` has run — because it builds its index from the catalog at startup. Adding tools below the transform call silently excludes them.

The transform exposes `search_tools` (indexes the full catalog) plus **two** dispatch proxies: `call_read_tool` for read tools and `call_write_tool` for `write`/`destructive` tools. Routing is by the `mutation` alias tag — a read tool cannot be invoked through `call_write_tool` and vice versa. This split lets clients that gate permissions by tool name allow reads while withholding writes. So a tool's `operation=` is what determines which proxy can reach it.

`always_visible = ["search_synapse", "get_entity"]` is intentional — these two cover the common first step of any Synapse workflow (lookup-by-ID, keyword-search). Expanding the list trades LLM context budget for one-shot access. Don't add entries without a justified reason.

No tool uploads or downloads file bytes. A File entity is creatable only via external URL or an existing file handle (`create_entity` with `entity_type="file"`); there is no wiki-write tool because the SDK wiki store path always writes markdown to disk.

## Error response shape

All tool errors are dicts with at minimum `error: str` and `error_type: str`, optional `status_code: int`, plus any context keys declared on the service method's `@error_boundary(error_context_keys=(...))`. Don't invent a different error shape — MCP clients parse this one.

## Dependency and vulnerability triage

`uv.lock` is the single install source for local dev, CI (`uv sync --locked`), and the container image — so an upper bound in `pyproject.toml` is itself an exposure, not just a version pin. `cryptography>=48.0.1,<50` shipped vulnerable 49.x into CI and the image while the Dependabot alert that prompted the DPE-1769 bump was lockfile-only; the cap was the real hole.

Triage Dependabot alerts by whether the vulnerable version is actually installed on a shipped path (lockfile vs. `pyproject.toml` cap vs. transitive-only), comparing each alert's `first_patched_version` against the floor already being adopted — before ranking by bump size or deferring to a follow-up ticket.

## Related docs

- `doc/tool-authoring.md` — full tool-authoring convention with a canonical example.
- `DEVELOPMENT.md` — contributor setup, linting, release flow.
