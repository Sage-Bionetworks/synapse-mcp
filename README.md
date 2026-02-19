# Synapse MCP Server

![synapse_wordmark](https://github.com/user-attachments/assets/7baf44ab-1b77-482d-b96f-84d3cb1dbdc9)

A Model Context Protocol (MCP) server that enables AI agent access to Synapse entities (Datasets, Projects, Folders, Files, Tables, and more).

You (your AI agent) can:
- Retrieve entities by ID
- Get entity annotations
- List entity children
- Search Synapse entities with path and type filters
- Inspect provenance/activity recorded for an entity version

## Available Tools

| Tool | Friendly Name | Description |
| --- | --- | --- |
| `get_entity(entity_id)` | Fetch Entity | Fetch core metadata for a Synapse entity by ID. |
| `get_entity_annotations(entity_id)` | Fetch Entity Annotations | Return custom annotations associated with an entity. |
| `get_entity_provenance(entity_id, version=None)` | Fetch Entity Provenance | Retrieve provenance (activity) metadata for an entity, optionally scoped to a specific version. |
| `get_entity_children(entity_id)` | List Entity Children | List children for container entities such as projects and folders. |
| `search_synapse(query_term=None, ...)` | Search Synapse | Search Synapse entities by keyword with optional name/type/parent filters. Results are provided by Synapse as data custodian; attribution and licensing follow the source entity metadata. |

## Available Resources

Resources provide ready-to-present context that clients can pull without extra parameters. When you need to search or compute derived results, prefer tools instead.

| Resource | Friendly Name | Description |
| --- | --- | --- |
| `synapse://feeds/blog` | Sage Blog RSS | Live RSS XML for the latest Sage Bionetworks publication posts. |

## ⚠️ Terms of Service Compliance Notice

**Important:** When using this MCP server with external AI services (such as Claude, ChatGPT, or other cloud-based models), please be aware that:

- You will use your personal Synapse access token to retrieve data
- Data sent to external AI services may be stored, logged, or used for model training
- **The Synapse Terms of Service prohibit redistribution of data**, which may include storage or use by third-party AI providers

**Recommended Safe Usage:**
- ✅ Use with enterprise AI deployments with data residency guarantees
- ✅ Use with local/self-hosted AI models
- ✅ Leverage responsible AI use training if provided
- ❌ Avoid use with consumer AI services that may store or train on your data

**You are responsible for ensuring your usage complies with the [Synapse Terms of Service](https://www.synapse.org/TrustCenter:TermsOfService).**

## Getting Started

The Synapse MCP server can be used as a **remote hosted server** (recommended) or installed **locally from source**. Choose the approach that fits your needs.

### Remote Server (Recommended)

The hosted server is available at:

> **https://mcp.synapse.org/mcp**

Authentication uses **OAuth2** -- your MCP client will open a browser window for you to log in to Synapse. No API keys or tokens to manage.

Below are setup instructions for popular AI clients. If your client is not listed, use the generic JSON config.

#### Generic MCP JSON Config

Most MCP-compatible clients accept a JSON configuration block. Add the following to your client's MCP config file:

```json
{
  "mcpServers": {
    "synapse": {
      "url": "https://mcp.synapse.org/mcp",
      "type": "http"
    }
  }
}
```

#### Claude Desktop

Go to **Settings > Connectors > Add custom connector** and enter the URL `https://mcp.synapse.org/mcp`.

<img width="664" height="146" alt="Claude Desktop connector setup" src="https://github.com/user-attachments/assets/fcfe54ba-1c1c-4fa8-9bae-c198cffff6ce" />

#### Claude Code (CLI)

```bash
claude mcp add --transport http synapse -- https://mcp.synapse.org/mcp
```

#### VS Code / GitHub Copilot

VS Code's MCP client does not yet fully support OAuth Dynamic Client Registration (DCR). To connect to the remote server, follow these steps:

**Step 1: Register a client**

Run this command once to register an OAuth client with the MCP server:

```bash
curl -X POST https://mcp.synapse.org/register \
  -H "Content-Type: application/json" \
  -d '{
    "client_name": "vscode-synapse",
    "redirect_uris": ["http://127.0.0.1"],
    "grant_types": ["authorization_code", "refresh_token"],
    "response_types": ["code"],
    "token_endpoint_auth_method": "none"
  }'
```

Save the `client_id` from the response (e.g., `c3dfaf80-126c-4f46-80ab-114747fcc3b3`).

**Step 2: Configure VS Code**

Create or edit `.vscode/mcp.json` in your workspace:

```json
{
  "servers": {
    "synapse": {
      "url": "https://mcp.synapse.org/mcp",
      "type": "http"
    }
  }
}
```

**Step 3: Complete the OAuth flow**

When you start the server, VS Code will open a browser to an authorization URL. Replace the `client_id` value in the URL with your registered client_id from Step 1, then press Enter to continue the Synapse login flow.

For example, change `client_id=100441` to `client_id=YOUR_CLIENT_ID` in the browser address bar.

Alternatively, you can use the [Local Server](#local-server) setup with a Personal Access Token, which does not require OAuth.

#### Cursor

Add to **Cursor Settings > MCP > + Add new global MCP server**, or add to your project's `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "synapse": {
      "url": "https://mcp.synapse.org/mcp",
      "type": "http"
    }
  }
}
```

### Local Server

Run the server locally for development, self-hosting, or offline use. The local server uses **stdio** transport by default, which is what most MCP clients expect for command-based servers.

> **Note:** `synapse-mcp` is not currently published on PyPI. You must install from source.

#### Install

```bash
git clone https://github.com/Sage-Bionetworks/synapse-mcp.git
cd synapse-mcp
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e .
```

After installation, the `synapse-mcp` command is available in your virtual environment.

#### Authentication for Local Server

For local use, authenticate with a **Synapse Personal Access Token (PAT)** by setting the `SYNAPSE_PAT` environment variable:

```bash
export SYNAPSE_PAT="your_synapse_pat_here"
```

To create a PAT, visit your [Synapse Personal Access Tokens page](https://www.synapse.org/#!PersonalAccessTokens:).

#### MCP Client Configuration (Local)

> **Important:** The `synapse-mcp` command must be on your PATH. If you installed in a virtual environment, either activate it first or use the full path to the binary (e.g., `/path/to/.venv/bin/synapse-mcp`).

**Generic JSON config (stdio):**

```json
{
  "mcpServers": {
    "synapse": {
      "command": "/path/to/.venv/bin/synapse-mcp",
      "env": {
        "SYNAPSE_PAT": "your_synapse_pat_here"
      }
    }
  }
}
```

**Claude Code (local):**

```bash
claude mcp add synapse -e SYNAPSE_PAT=your_synapse_pat_here -- /path/to/.venv/bin/synapse-mcp
```

**VS Code / GitHub Copilot (local):**

In `.vscode/mcp.json`:

```json
{
  "servers": {
    "synapse": {
      "command": "/path/to/.venv/bin/synapse-mcp",
      "env": {
        "SYNAPSE_PAT": "your_synapse_pat_here"
      }
    }
  }
}
```

**Cursor (local):**

```json
{
  "mcpServers": {
    "synapse": {
      "command": "/path/to/.venv/bin/synapse-mcp",
      "env": {
        "SYNAPSE_PAT": "your_synapse_pat_here"
      }
    }
  }
}
```

### Configuration

#### Environment Selection

You can configure which Synapse platform instance to connect to by setting the `SYNAPSE_ENV` environment variable:

- `prod` (default) -- Production instance at synapse.org
- `staging` -- Staging instance at staging.synapse.org
- `dev` -- Development instance at dev.synapse.org

If not set, the server defaults to `prod`.

### Authentication

| Method | When to Use | How |
| --- | --- | --- |
| **OAuth2** (default) | Remote server, production use | Browser-based login -- no setup needed |
| **Personal Access Token** | Local development, CI/CD, headless environments | Set `SYNAPSE_PAT` environment variable |

For contributor/development setup details, see [DEVELOPMENT.md](./DEVELOPMENT.md).

### Example Prompts

See [usage examples](./doc/usage.md)

## Contributing

Contributions are welcome! Please see our [Development Guide](./DEVELOPMENT.md) for instructions on setting up a development environment, running tests, and more.

## License

 **MIT**

## Contact

![synapse_icon](https://github.com/user-attachments/assets/b629f426-ae1b-4179-87d2-ac2c73419644)

For issues, please file an issue. For other contact, see https://sagebionetworks.org/contact.

