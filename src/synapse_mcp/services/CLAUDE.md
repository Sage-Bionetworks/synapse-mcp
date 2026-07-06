<!-- Last reviewed: 2026-05 -->

## Project

Service-layer modules that wrap `synapseclient` SDK calls. Each Synapse domain (entity, wiki, team, user, activity, evaluation, submission, schema, organization, form, curation, utility, search) has one class here. Tool functions in `src/synapse_mcp/tools.py` delegate into these classes via `@service_tool` — they never call `synapseclient` directly.

## Conventions

- **One class per domain.** Name pattern: `<Domain>Service` (e.g. `EntityService`, `WikiService`). Put them in `<domain>_service.py`. Export via `services/__init__.py`.
- **Methods are `async` and `@staticmethod`.** First (and only) framework parameter is `ctx: Context` (from `fastmcp`); then business args. Services hold no state, so there is nothing for `self` to carry. Tool functions call them as `EntityService.method(ctx, ...)` — never `EntityService().method(...)`.
- **Decorator order matters: `@staticmethod` outermost, `@error_boundary` next, then the method.** The `@error_boundary` wrapper is signed `async def wrapper(ctx, *args, **kwargs)` — there is no `self` slot. Reversing the order or adding `self` will cause `ctx` to bind incorrectly.
- **Every method is decorated with `@error_boundary`.** Always pass `error_context_keys=(...)` naming the parameters that should be included in the error response so the caller can tell which entity/team/evaluation failed. Example: `@error_boundary(error_context_keys=("entity_id",))`.
- **Use `wrap_errors=True` when the method returns `List[...]`.** The boundary wraps the error dict in a single-element list so the return-type contract still holds on the error path — without this, a list-typed method returns a bare dict on failure and callers break.
- **Use `async with synapse_client(ctx) as client:` for every SDK call.** Yields an authenticated `synapseclient.Synapse`. Never construct a client directly — `synapse_client` is the only path that threads auth through the request context.
- **Serialize every return value through `serialize_model(...)`.** Handles synapseclient dataclasses, legacy `MutableMapping` entities, enums, datetimes, nested lists/dicts. Returning a raw synapseclient object leaks non-JSON-safe types to the MCP wire format.

## Pagination

Real pagination must reach the wire. There is no generic `collect_async_generator` helper — each call site picks the path that lets `limit`/`offset` (or `nextPageToken`) reach the REST API. Decision tree, in order:

1. **High-level SDK method that already accepts `limit`/`offset`** — e.g. `WikiHeader.get_async`, `WikiHistorySnapshot.get_async`, `Evaluation.get_all_evaluations_async`. Pass the caller's values straight through; cap with an inline `if len(results) >= limit: break` to bound response size.
2. **Lower-level callable in `synapseclient.api.*_services`** — used when the SDK model wrapper exhaustively collects pages but the api-services helper exposes pagination params. Import and call directly.
3. **Last resort: `synapseclient.api.api_client.rest_get_paginated_async`** — call directly with `(uri, limit, offset, synapse_client=client)`. Run each yielded REST dict through the appropriate `<Model>.fill_from_dict` (`TeamMember`, `Submission`, `SubmissionBundle`) so the response shape matches what the high-level SDK wrapper would have produced. Then pass through `serialize_model`.
4. **Token-paginated POST endpoints** — for `/schema/list`, `/schema/version/list`, `/form/data/list[/reviewer]`, the API has no `limit`/`offset`; only a `nextPageToken` round-trip. Issue a single `client.rest_post_async`, return `{"results": [...], "next_page_token": ...}`, and let the MCP caller paginate by passing the token back.

`collect_generator` (sync, `itertools.islice`-based) stays for the few non-REST iterators we still call (e.g. `CurationTask.list_async`).

## Data flow

```
@service_tool (tools.py)
  └─ validate_synapse_id()
  └─ await <Service>.method(ctx, ...)         ← services/ entrypoint (no instance)
        └─ @staticmethod + @error_boundary     ← decorator stack
        └─ async with synapse_client(ctx)     ← auth
        └─ SDK call (paginated if list-shaped)
        └─ serialize_model(result)            ← always
        └─ return dict | List[dict] | {results, next_page_token}
```

## Constraints

- Do NOT import from `synapse_mcp.tools` or `synapse_mcp.app` here — creates a circular import. Services stay MCP-agnostic.
- Do NOT store a `Synapse` client on `self`. There is no `self` — services are stateless `@staticmethod` containers.
- Do NOT raise from service methods. `@error_boundary` turns every exception into the standard error dict; raising past it breaks the tool wrapper's contract.

## Anti-Patterns — Do NOT

- Do NOT call services as `XxxService().method(...)`. Use `XxxService.method(...)`. The `()` instantiation is a leftover from before the static-method conversion and will silently bind the empty instance to `ctx` once `error_boundary` strips its `self` slot.
- Do NOT add a `self` parameter to service methods. The `@error_boundary` wrapper does not allow for it.
- Do NOT collect a generator with a soft cap when the underlying API supports `limit`/`offset`/`nextPageToken`. A soft cap defeats pagination — the caller can never reach record N+1.
- Do NOT return a raw synapseclient dataclass. Always pass it through `serialize_model` — because dataclass fields may contain `datetime`, `Enum`, or nested custom types that the MCP JSON serializer chokes on.
- Do NOT omit `error_context_keys` from `@error_boundary`. Even for single-param methods — without it the error response gives the LLM no signal about which entity failed and it will retry blind.
- Do NOT pass `wrap_errors=True` on dict-returning methods. The caller expects a dict, not a one-element list of dicts.
