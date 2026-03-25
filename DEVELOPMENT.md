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
├── tools.py              Controller — @mcp.tool registrations + input validation only
├── services/
│   ├── tool_service.py   Internal helper (with_synapse_client) used by services, not by tools
│   └── <resource>_service.py  One per resource domain, called by tools.py
├── managers/
│   └── <resource>_manager.py  One per resource domain, called by services
├── entities/             Legacy entity operations (predates service/manager pattern)
```

**Layer rules:**

- **tools.py** imports services, never managers directly. Contains no business logic, no Synapse API calls, no error handling beyond input validation.
- **Services** orchestrate one or more managers. They acquire the Synapse client (via `with_synapse_client`), instantiate the appropriate manager, call it, and handle error-to-dict wrapping. A service method receives a `Context` and domain arguments.
- **Managers** take a `synapseclient.Synapse` in `__init__`. They contain all Synapse API calls and model-to-dict conversion. They raise exceptions naturally — never return error dicts, never catch `ConnectionAuthError`, never touch `Context`.
- `with_synapse_client` in `tool_service.py` is internal infrastructure for services. Tools should not call it directly.

### Adding a new tool (step by step)

**1. Manager** — `managers/<resource>_manager.py`:

```python
class WidgetManager:
    def __init__(self, synapse_client):
        self.synapse_client = synapse_client

    def get_widget(self, widget_id):
        widget = Widget(id=widget_id).get(synapse_client=self.synapse_client)
        return {"id": widget.id, "name": widget.name}
```

**2. Service** — `services/<resource>_service.py`:

```python
from ..managers import WidgetManager
from .tool_service import with_synapse_client

class WidgetService:
    def get_widget(self, ctx, widget_id):
        return with_synapse_client(
            ctx,
            lambda client: WidgetManager(client).get_widget(widget_id),
            error_context={"widget_id": widget_id},
        )
```

**3. Tool** — `tools.py`:

```python
@mcp.tool(title="Get Widget", ...)
def get_widget(widget_id: str, ctx: Context) -> Dict[str, Any]:
    return WidgetService().get_widget(ctx, widget_id)
```

### Error response conventions

- Auth failures: `{"error": "Authentication required: ...", **context}`
- Other failures: `{"error": "...", "error_type": "ExceptionClassName", **context}`
- Tools returning `List[Dict]` wrap error dicts in a list: `[{"error": ...}]` — the service handles this, not the tool.
- `error_context` keys should identify the input (e.g. `project_id`, `task_id`, `entity_id`)

### Testing conventions

- **Manager tests** mock `synapseclient.models` classes at the manager module level. Test data conversion and API call delegation only.
- **Service tests** mock `get_synapse_client` at the `tool_service` module level and mock the manager class at the service module level. Test orchestration: auth errors become error dicts, manager results pass through, list-returning services wrap errors in lists.
- **tool_service tests** test `with_synapse_client` in isolation — success passthrough, auth errors, generic errors, error_context merging.

### `entities/` vs `managers/`

`entities/` is the older pattern (pre-existing). New resource-specific logic goes in `managers/` with a corresponding service in `services/`. Both manager styles take a synapse client in `__init__` and own API calls + formatting. The `entities/` tools have not yet been migrated to the service/manager pattern.

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
