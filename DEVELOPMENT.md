# Local Development Guide

This guide provides instructions for setting up and running the Synapse MCP server in a local development environment. The server is built using FastMCP framework and is meant to support both PAT authentication (local server) and OAuth2 (remote server).

## 1. Local Setup

```bash
# 1. Clone the repository
git clone https://github.com/SageBionetworks/synapse-mcp.git
cd synapse-mcp

# 2. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows use `.venv\Scripts\activate`

# 3. Install the package in editable mode
pip install --upgrade -e .
```

If you have previously installed the package, it is important to use the `--upgrade` flag to ensure the console script is properly generated.

## 2. Run the Server

### Environment Configuration

You can configure which Synapse platform instance to connect to by setting the `SYNAPSE_ENV` environment variable:

```bash
export SYNAPSE_ENV=prod  # Options: prod (default), staging, dev
```

If not set, the server defaults to `prod` (production Synapse instance at synapse.org).

### Start server with HTTP transport for web development/testing

Currently, the server default is **stdio transport** for local use. For development, it is better to start server with `--http` flag (transport is streamable-http) and `--debug` to see detailed logs:

```bash
export SYNAPSE_PAT=$SYNAPSE_AUTH_TOKEN
synapse-mcp --http --debug
```

**To also test OAuth2**

This is fully intended for **contributors only** -- typical end users should use PAT authentication for local development. OAuth2 requires registering your own OAuth client with Synapse, which involves administrative steps that end users shouldn't need to do. As a contributor, you can also add new tools, etc. and test with the method above without having to register for a development client.

Again, you must have development [OAuth 2.0 client credentials](https://help.synapse.org/docs/Using-Synapse-as-an-OAuth-Server.2048327904.html) registered with Synapse and set these environment variables. Make sure `SYNAPSE_PAT` is unset, since `SYNAPSE_PAT` check takes precedence.

```bash
# Set these values for your current terminal session
export SYNAPSE_OAUTH_CLIENT_ID=$CLIENT_ID
export SYNAPSE_OAUTH_CLIENT_SECRET=$CLIENT_SECRET
export SYNAPSE_OAUTH_REDIRECT_URI="http://127.0.0.1:9000/oauth/callback"
export MCP_SERVER_URL="http://127.0.0.1:9000/mcp"
synapse-mcp --http --debug
```

### 3. Add to local AI client like Claude Code

```bash
claude mcp add --transport http synapse -- http://127.0.0.1:9000/mcp
```

## Running Tests

To run the test suite, use `pytest`:

```bash
# Run all tests
python -m pytest
```

### Redis session storage smoke test

If you have a live Redis instance available, run the smoke test to validate connectivity and TTL behaviour:

```bash
export REDIS_URL="redis://localhost:6379/0"
python scripts/smoke_redis_session_storage.py
```

The script exercises token creation, replacement, expiration, and cleanup. It exits non-zero if anything fails.

## Code Architecture

### Layered design (controller → service → manager)

```
src/synapse_mcp/
├── tools.py              Controller — @mcp.tool registrations + input validation
├── services/
│   ├── tool_service.py   synapse_client_from context manager + @error_boundary
│   └── <resource>_service.py  One per resource domain, called by tools.py
├── managers/
│   └── <resource>_manager.py  Multi-step API orchestration, called by services
├── entities/             Legacy entity operations (predates service/manager pattern)
```

**Layer rules:**

| Layer | Owns | Does NOT own |
|---|---|---|
| **Controller** (`tools.py`) | `@mcp.tool` registration, input validation, delegation to service | Business logic, Synapse API calls, serialization |
| **Service** (`services/`) | Serialization (model → dict), error boundary (`@error_boundary`), simple SDK calls via `synapse_client_from` context manager | Multi-step API orchestration |
| **Manager** (`managers/`) | Multi-step operations that compose several API calls with partial-failure handling. Returns raw model objects. | Serialization, error-to-dict conversion |

**When to use a manager:** Only when an operation requires composing multiple API calls or handling partial failures across sub-operations. Simple one-liner SDK calls (`Model.list(...)`, `Model(...).get(...)`) belong in the service.

**Adding a new tool — follow this template:**

**1. Service** — `services/<resource>_service.py`:

```python
class WidgetService:
    @error_boundary(error_context_keys=("widget_id",))
    def get_widget(self, ctx: Context, widget_id: str) -> Dict[str, Any]:
        with synapse_client_from(ctx) as client:
            widget = Widget(id=widget_id).get(synapse_client=client)
            return _format_widget(widget)
```

**2. Tool** — `tools.py`:

```python
@mcp.tool(title="Get Widget", ...)
def get_widget(widget_id: str, ctx: Context) -> Dict[str, Any]:
    return WidgetService().get_widget(ctx, widget_id)
```

**3. Manager** (only if needed) — `managers/<resource>_manager.py`:

```python
class WidgetManager:
    def __init__(self, synapse_client: synapseclient.Synapse) -> None:
        self.synapse_client = synapse_client

    def get_widget_with_parts(self, widget_id: str) -> Tuple[Widget, Dict]:
        widget = Widget(id=widget_id).get(synapse_client=self.synapse_client)
        parts = {}
        # fetch related resources, handle partial failures
        return widget, parts
```

### Error response conventions

- Auth failures: `{"error": "Authentication required: ...", **context}`
- Other failures: `{"error": "...", "error_type": "ExceptionClassName", **context}`
- Tools returning `List[Dict]` wrap error dicts in a list: `[{"error": ...}]` — the `@error_boundary(wrap_errors=list)` decorator handles this.
- `error_context_keys` should identify the input (e.g. `project_id`, `task_id`, `entity_id`)

### Testing conventions

- **Manager tests** mock `synapseclient.models` classes at the manager module level. Test multi-step orchestration and partial-failure handling.
- **Service tests** mock `get_synapse_client` at the `tool_service` module level. For simple operations, mock SDK models at the service module level. For complex operations, mock the manager class. Test serialization and error boundary behavior.
- **tool_service tests** test `synapse_client_from` and `@error_boundary` in isolation.

### `entities/` vs `managers/`

`entities/` is the older pattern (pre-existing). New resource-specific logic goes in `managers/` (for complex operations) or directly in `services/` (for simple SDK calls). The `entities/` tools have not yet been migrated to the service/manager pattern.

## Deployment

### Docker build and run

```bash
# Build the Docker image
docker build -t synapse-mcp .

# Run the container with PAT
docker run -p 9000:9000 \
  -e SYNAPSE_PAT="your_token_here" \
  -e MCP_TRANSPORT="streamable-http" \
  -e SYNAPSE_ENV="prod" \
  synapse-mcp

# OR run with OAuth
docker run -p 9000:9000 \
  -e SYNAPSE_OAUTH_CLIENT_ID=$SYNAPSE_OAUTH_CLIENT_ID \
  -e SYNAPSE_OAUTH_CLIENT_SECRET=$SYNAPSE_OAUTH_CLIENT_SECRET \
  -e SYNAPSE_OAUTH_REDIRECT_URI="http://127.0.0.1:9000/oauth/callback" \
  -e MCP_SERVER_URL="http://127.0.0.1:9000/mcp" \
  -e MCP_TRANSPORT="streamable-http" \
  -e SYNAPSE_ENV="prod" \
  synapse-mcp
```

### Production Deployment

Production is deployed to AWS ECS via CloudFormation. Infrastructure configuration and deployment instructions are maintained in the separate infrastructure repository:

> **https://github.com/Sage-Bionetworks-IT/synapse-mcp-infra**

The Docker image from this repo is the deployment artifact. See the Docker section above for build instructions.
