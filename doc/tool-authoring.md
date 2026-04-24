# Authoring MCP tools for synapse-mcp

This repo exposes Synapse capabilities to LLMs through MCP tools. Tool
discovery is driven by **BM25 keyword search over tool names,
descriptions, parameter names, and parameter descriptions** (see
`fastmcp.server.transforms.search.BM25SearchTransform`). Naming and
description decisions directly determine whether the LLM finds the
right tool.

This doc explains the conventions the `@service_tool` decorator
enforces and why. Read it before adding or editing a tool.

## When to add a tool vs extend a service

- **Add a service method** when you need a new Synapse capability (new
  SDK call, new business logic). Service methods live under
  `src/synapse_mcp/services/*.py` and are decorated with
  `@error_boundary`.
- **Add a tool** when that capability needs to be exposed to the LLM.
  Tools live in `src/synapse_mcp/tools.py` and are decorated with
  `@service_tool`. Tool functions should be thin: validate inputs,
  delegate to a service method, return the result.

Do **not** put business logic in tool functions. Keep them as
delegation shims so the service layer stays the single source of
truth.

## Naming

Tool names must start with one of these approved verb prefixes:

| Prefix       | Operation | Example                  |
|--------------|-----------|--------------------------|
| `get_`       | read      | `get_entity`             |
| `list_`      | read      | `list_evaluations`       |
| `search_`    | read      | `search_synapse`         |
| `check_`     | read      | `check_user_certified`   |
| `validate_`  | read      | `validate_submission`    |
| `create_`    | write     | `create_wiki`            |
| `update_`    | write     | `update_entity_annotations` |
| `register_`  | write     | `register_json_schema`   |
| `submit_`    | write     | `submit_to_evaluation`   |
| `delete_`    | destructive | `delete_curation_task` |

Names are `snake_case`, imperative, and descriptive of the Synapse
object type (not the SDK method they wrap). The `@service_tool`
decorator raises `ValueError` at registration time if a name
doesn't start with one of these prefixes.

## The first sentence of `description`

`description` is the LLM-visible text. The first sentence must:

1. Lead with **user intent**, not API mechanics.
   - Good: `"Use this when the user wants to know what produced a
     Synapse entity — its data lineage."`
   - Bad: `"Returns the activity metadata for a Synapse entity."`
2. Name the **concrete Synapse object type** the tool operates on.
   The decorator validates this via the `synapse_object=` argument
   and raises if the first sentence doesn't contain that string
   (case-insensitive).

Recommended pattern:

```
Use this when <user intent>. <Synapse object> <one-line definition>.
```

Example:

```
Use this when the user wants the table of contents for a Synapse wiki
(list of pages in a wiki's hierarchy). A Synapse wiki is the
markdown documentation attached to a project, folder, or entity.
```

## ID parameters must show concrete examples

LLMs infer parameter shapes from descriptions. Always include a
concrete example for every ID parameter:

| Parameter type              | Example to include           |
|-----------------------------|------------------------------|
| Entity ID                   | `syn123456`                  |
| Team ID                     | `"3379097"` (numeric string) |
| Evaluation ID               | `"9600001"`                  |
| Submission ID               | `"9722233"`                  |
| User ID                     | `"1234567"`                  |
| JSON schema `$id`           | `"my.org-MySchema-1.0.0"`    |
| Organization name           | `"my.org"`                   |

Put the example either in the main description or in the parameter
description.

## `synonyms`

Synapse terminology rarely matches user language. Users say:

| Synapse term         | User language                                    |
|----------------------|--------------------------------------------------|
| annotations          | metadata, tags, properties, key-value pairs     |
| provenance           | lineage, history, inputs, outputs, derived from |
| evaluation           | challenge, queue, competition, leaderboard      |
| submission           | submit, entry, challenge entry                  |
| wiki                 | documentation, markdown, page, docs             |
| team                 | group, collaborators, members                   |
| activity             | provenance record, run, execution               |
| schema               | JSON schema, validation, data model             |
| access requirement   | ACT, controlled access, gate, permission        |
| Docker repository    | Synapse Docker repository (NOT container runtime) |
| entity               | project, folder, file, table, view, dataset     |

Pass these as `synonyms=("lineage", "history", ...)` to
`@service_tool`. The decorator appends a `Related terms:` line to
the description so BM25 indexes the aliases without polluting the
primary copy the LLM reads.

## `siblings`

Tools in the same service with high token overlap will rank close
together in BM25 results. The LLM needs explicit disambiguation to
pick correctly.

Pass sibling tool names via `siblings=("get_wiki_history", ...)`.
The decorator appends a `Distinct from:` line so the LLM sees which
tools are close cousins.

Rule of thumb: list every other tool in the same service whose
description discusses the same primary object (wiki page vs wiki
history vs wiki order hint).

## Tags and operation

`operation` drives the default MCP annotations (`readOnlyHint`,
`destructiveHint`, etc.) and informational tags attached to each
tool:

- `read` → tags `{service, "read", "readonly"}`
- `write` → tags `{service, "write", "mutation"}`
- `destructive` → tags `{service, "destructive", "mutation"}`
- `admin` → tags `{service, "admin"}`

When in doubt, prefer the narrower operation — `destructive` over
`write`, `admin` over `destructive` — so the MCP annotations
correctly signal the effect of the call to clients.

## Canonical example

```python
from .app import mcp
from .services import service_tool
from .services import EntityService
from .utils import validate_synapse_id


@service_tool(
    mcp,
    service="activity",
    operation="read",
    synapse_object="Synapse entity",
    title="Get Entity Provenance",
    description=(
        "Use this when the user wants to know what produced a "
        "Synapse entity — its data lineage, inputs, outputs, and "
        "the activity that generated it. Works on any Synapse "
        "entity (project, folder, file, table, view, dataset). "
        "Entity ID example: syn123456. Optionally scope to a "
        "specific version."
    ),
    synonyms=(
        "lineage",
        "history",
        "inputs",
        "outputs",
        "derived from",
        "provenance record",
    ),
    siblings=("get_activity", "get_entity"),
)
async def get_entity_provenance(
    entity_id: str,
    ctx: Context,
    version: Optional[int] = None,
) -> Dict[str, Any]:
    """Return activity metadata for a Synapse entity."""
    if not validate_synapse_id(entity_id):
        return {"error": f"Invalid Synapse ID: {entity_id}"}
    return await ActivityService().get_provenance(ctx, entity_id, version)
```

What this gives you:

- `tags={"activity", "read", "readonly"}` for the Visibility transform.
- Default read-only annotations (`readOnlyHint=True`,
  `idempotentHint=True`, `destructiveHint=False`).
- A description the LLM sees as:

  ```
  Use this when the user wants to know what produced a Synapse entity
  — its data lineage, inputs, outputs, and the activity that
  generated it. Works on any Synapse entity (project, folder, file,
  table, view, dataset). Entity ID example: syn123456. Optionally
  scope to a specific version.

  Related terms: lineage, history, inputs, outputs, derived from,
  provenance record

  Distinct from: get_activity, get_entity
  ```

- Automatic exception handling: any exception inside
  `get_entity_provenance` is converted to
  `{"error": ..., "error_type": ..., "status_code": ...}` before
  MCP serialization.
