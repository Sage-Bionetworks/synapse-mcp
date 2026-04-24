<!-- Last reviewed: 2026-04 -->

## Project

Service-layer modules that wrap `synapseclient` SDK calls. Each Synapse domain (entity, wiki, team, user, activity, evaluation, submission, schema, organization, form, curation, utility, docker, search) has one class here. Tool functions in `src/synapse_mcp/tools.py` delegate into these classes via `@service_tool` — they never call `synapseclient` directly.

## Conventions

- **One class per domain.** Name pattern: `<Domain>Service` (e.g. `EntityService`, `WikiService`). Put them in `<domain>_service.py`. Export via `services/__init__.py`.
- **Methods are `async`.** First parameter is `self`, second is `ctx: Context` (from `fastmcp`), then business args. Tool functions call them as `EntityService().method(ctx, ...)` — fresh instance per call, no shared state.
- **Every method is decorated with `@error_boundary`.** Always pass `error_context_keys=(...)` naming the parameters that should be included in the error response so the caller can tell which entity/team/evaluation failed. Example: `@error_boundary(error_context_keys=("entity_id",))`.
- **Use `wrap_errors=True` when the method returns `List[...]`.** The boundary wraps the error dict in a single-element list so the return-type contract still holds on the error path — without this, a list-typed method returns a bare dict on failure and callers break.
- **Use `async with synapse_client(ctx) as client:` for every SDK call.** Yields an authenticated `synapseclient.Synapse`. Never construct a client directly — `synapse_client` is the only path that threads auth through the request context.
- **Serialize every return value through `serialize_model(...)`.** Handles synapseclient dataclasses, legacy `MutableMapping` entities, enums, datetimes, nested lists/dicts. Returning a raw synapseclient object leaks non-JSON-safe types to the MCP wire format.
- **Guard async generators with `collect_async_generator(gen, limit=100)`.** SDK methods like `Folder.walk_async()` or `WikiHeader` iteration return unbounded generators — consuming them directly in a tool can hang the request. The 100-item cap is deliberate; change it only with a reason.
- **Sync generators use `collect_generator` instead.** Same contract, different helper.

## Data flow

```
@mcp.tool / @service_tool (tools.py)
  └─ validate_synapse_id()
  └─ await <Service>().method(ctx, ...)     ← services/ entrypoint
        └─ @error_boundary                    ← catches SDK exceptions
        └─ async with synapse_client(ctx)    ← auth
        └─ SDK call (e.g. operations_get_async)
        └─ collect_async_generator(..., 100) ← if generator
        └─ serialize_model(result)           ← always
        └─ return dict | List[dict]
```

## Constraints

- Do NOT import from `synapse_mcp.tools` or `synapse_mcp.app` here — creates a circular import. Services stay MCP-agnostic.
- Do NOT store a `Synapse` client on `self`. The client is per-request and lives only inside the `synapse_client` context manager.
- Do NOT raise from service methods. `@error_boundary` turns every exception into the standard error dict; raising past it breaks the tool wrapper's contract.

## Anti-Patterns — Do NOT

- Do NOT return a raw synapseclient dataclass. Always pass it through `serialize_model` — because dataclass fields may contain `datetime`, `Enum`, or nested custom types that the MCP JSON serializer chokes on.
- Do NOT omit `error_context_keys` from `@error_boundary`. Even for single-param methods — without it the error response gives the LLM no signal about which entity failed and it will retry blind.
- Do NOT pass `wrap_errors=True` on dict-returning methods. The caller expects a dict, not a one-element list of dicts.
