# Synapse MCP Server

![synapse_wordmark](https://github.com/user-attachments/assets/7baf44ab-1b77-482d-b96f-84d3cb1dbdc9)

A Model Context Protocol (MCP) server that enables AI agent access to Synapse entities (Datasets, Projects, Folders, Files, Tables, and more).

You (your AI agent) can:
- Retrieve entity metadata, annotations, and children, and search across all entity types
- Inspect provenance/lineage for an entity version
- Audit access control (ACLs and your own permissions) across a project subtree
- Read wikis — pages, table of contents, and revision history
- Look up teams (members, invitations, membership status) and user profiles
- Explore challenges: evaluation queues, submissions, and scoring statuses
- Browse JSON schemas and their validation results, plus schema organizations
- List curation tasks and their linked resources, and read form submissions
- Resolve entities by exact name or MD5 hash and validate Synapse IDs

## Available Tools

All tools are **read-only** (no create/update/delete) — the server surfaces Synapse metadata, never mutates it and never downloads file content.

<!-- BEGIN GENERATED TOOLS: run `uv run python scripts/gen_tool_table.py` to update -->

| Tool | Domain | Description |
| --- | --- | --- |
| `get_entity(entity_id)` | entity | Use this when the user wants the metadata, record, details, or info for a specific Synapse entity given its Synapse ID. |
| `get_entity_acl(entity_id)` | entity | Use this when the user wants the sharing settings or access control list (ACL) of one single Synapse entity — who can access it and with what permissions. |
| `get_entity_annotations(entity_id)` | entity | Use this when the user wants the custom annotations (metadata key/value pairs) attached to a Synapse entity. |
| `get_entity_children(entity_id)` | entity | Use this when the user wants to list the files and sub-folders immediately inside a Synapse entity container (one level deep). |
| `get_entity_permissions(entity_id)` | entity | Use this when the user wants to know what the currently authenticated user is allowed to do on a Synapse entity (READ, UPDATE, DELETE, etc.). |
| `get_link(entity_id)` | entity | Use this when the user has a Synapse Link entity (a shortcut that points at another entity) and wants either the Link's own metadata or the target it resolves to. |
| `list_entity_acl(entity_id)` | entity | Use this when the user wants every ACL on a Synapse entity and, with recursive=True, on all its descendants — useful for auditing sharing recursively across a project subtree. |
| `search_synapse()` | search | Use this when the user wants to search for Synapse entities matching a keyword, topic, or subject (e.g. 'brain tissue', 'cancer_type=glioma'). |
| `get_entity_provenance()` | activity | Use this when the user wants to know what produced a Synapse entity — its data lineage, inputs, outputs, code executed, and the activity that generated it. |
| `get_entity_schema(entity_id)` | schema | Use this when the user wants to know which JSON schema (data model / validation contract) is bound to a Synapse entity. |
| `get_entity_schema_derived_keys(entity_id)` | schema | Use this when the user wants the annotation keys a bound JSON schema requires on a Synapse entity. |
| `get_entity_schema_invalid_validations(entity_id)` | schema | Use this when the user wants the list of Synapse entities inside a Folder or Project that currently fail their bound JSON schema — the 'what's broken' view. |
| `get_entity_schema_validation_statistics(entity_id)` | schema | Use this when the user wants an aggregate validation summary for a Synapse entity container (Folder or Project) with a bound JSON schema — how many child entities pass or fail validation. |
| `get_json_schema(organization_name, schema_name)` | schema | Use this when the user wants metadata about a specific Synapse JSON Schema (data model, validation contract). |
| `get_json_schema_body(organization_name, schema_name)` | schema | Use this when the user wants the raw JSON document of a Synapse JSON Schema — the actual data model / validation rules. |
| `list_json_schema_versions(organization_name, schema_name)` | schema | Use this when the user wants every version published for a Synapse JSON Schema. |
| `list_json_schemas(organization_name)` | schema | Use this when the user wants every Synapse JSON Schema (data model, validation contract) owned by an organization. |
| `get_wiki_headers(owner_id)` | wiki | Use this when the user wants the table of contents of a Synapse wiki — the list of pages and sub-pages attached to an entity. |
| `get_wiki_history(owner_id, wiki_id)` | wiki | Use this when the user wants the revision history (edit log) of a specific Synapse wiki page — who changed it and when. |
| `get_wiki_order_hint(owner_id)` | wiki | Use this when the user wants to know the display order of sub-pages in a Synapse wiki — how the wiki navigation is sorted. |
| `get_wiki_page(owner_id)` | wiki | Use this when the user wants to read a Synapse wiki page — its markdown content and metadata — attached to a project, folder, or file. |
| `get_team()` | team | Use this when the user wants a Synapse team by its numeric ID or name. |
| `get_team_members(team_id)` | team | Use this when the user wants the roster of a Synapse team — who is on it. |
| `get_team_membership_status(team_id, user_id)` | team | Use this when the user wants to know whether a specific Synapse user is already a member of, has applied to, or has been invited to a Synapse team. |
| `get_team_open_invitations(team_id)` | team | Use this when the user wants the pending (not yet accepted or rejected) invitations for a Synapse team. |
| `check_user_certified(user_id)` | user | Use this when the user wants to know whether a Synapse user has passed the certification quiz required for uploading human data. |
| `get_user_profile()` | user | Use this when the user wants a Synapse user profile by numeric user ID or username, or the authenticated caller's own profile when called with no arguments. |
| `get_evaluation()` | evaluation | Use this when the user wants a Synapse Evaluation queue — the challenge/competition queue that participants submit models or results to. |
| `get_evaluation_acl(evaluation_id)` | evaluation | Use this when the user wants the resource-level access control list of a Synapse Evaluation queue (challenge queue) — which principals (users and teams) hold which access types on the queue. |
| `get_evaluation_permissions(evaluation_id)` | evaluation | Use this when the user wants to know what the authenticated caller is allowed to do on a Synapse Evaluation queue (challenge queue) — submit, administer, etc. Returns the caller's own effective permission flags. |
| `list_evaluations()` | evaluation | Use this when the user wants to enumerate Synapse Evaluation queues (challenges, competitions, leaderboards) — optionally filtered by project, access type, or active-only. |
| `get_submission(submission_id)` | submission | Use this when the user wants a specific Synapse submission — a challenge entry a participant sent to an Evaluation queue. |
| `get_submission_count(evaluation_id)` | submission | Use this when the user wants only the count of Synapse submissions (challenge entries) in an Evaluation queue, not the submissions themselves. |
| `get_submission_status(submission_id)` | submission | Use this when the user wants the scoring status of a single Synapse submission (challenge entry) — e.g. RECEIVED, EVALUATION_IN_PROGRESS, SCORED. |
| `list_evaluation_submission_bundles(evaluation_id)` | submission | Use this when the user wants Synapse submission plus scoring status together (as bundles) for an Evaluation queue — one call returns both sides. |
| `list_evaluation_submissions(evaluation_id)` | submission | Use this when the user wants ALL submissions (every challenge entry from every participant) sent to a Synapse Evaluation queue — optionally filtered by status (SCORED, INVALID, etc.). |
| `list_my_submission_bundles(evaluation_id)` | submission | Use this when the user wants their own Synapse submission+status bundles for an Evaluation queue — one call returns both submission and scoring status for every entry they made. |
| `list_my_submissions(evaluation_id)` | submission | Use this when the user wants their own submissions (challenge entries) to a Synapse Evaluation queue. |
| `list_submission_statuses(evaluation_id)` | submission | Use this when the user wants the scoring statuses of every Synapse submission in an Evaluation queue — optionally filtered (SCORED, INVALID, etc.). |
| `get_curation_task(task_id)` | curation | Use this when the user wants the details of a single Synapse curation task by its numeric task ID. |
| `get_curation_task_resources(task_id)` | curation | Use this when the user wants the Synapse resources (RecordSets, Folders, EntityViews) linked to a curation task — the data the curator will act on. |
| `list_curation_tasks(project_id)` | curation | Use this when the user wants every Synapse curation task in a project — the queue of data-curation work items attached to that project. |
| `get_schema_organization(organization_name)` | organization | Use this when the user wants a Synapse JSON Schema Organization (namespace that owns a set of JSON schemas / data models) by name or numeric ID. |
| `get_schema_organization_acl(organization_name)` | organization | Use this when the user wants the ACL of a Synapse JSON Schema Organization — who may publish schemas under that namespace. |
| `list_form_data(group_id)` | form | Use this when the user wants the form submissions for a Synapse FormGroup — a collection of structured-data forms submitted by users. |
| `check_synapse_id(syn_id)` | utility | Use this when the user has a string that looks like a Synapse ID (e.g. syn123456) and wants to check whether it exists in Synapse — verifies validity by querying the Synapse backend. |
| `search_entities_by_md5(md5)` | utility | Use this when the user has an MD5 hash of a file and wants the Synapse entities (file entities) whose attached file has that exact MD5 — useful for deduplication and 'is this already in Synapse' checks. |
| `search_entity_by_name(name)` | utility | Use this when the user has a file name or Synapse entity name (and optionally its parent folder or project) but does not know the Synapse ID — resolves an exact name to its Synapse ID. |

<!-- END GENERATED TOOLS -->

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

#### Tool Discovery

To keep the LLM's context small, the server does not expose the full tool catalog on every call. The default view is just two always-visible tools — `get_entity` and `search_synapse` — plus a synthetic `search_tools` / `call_tool` pair. To reach any other tool, the LLM issues a natural-language query to `search_tools` (a BM25-ranked search over tool names, descriptions, synonyms, and siblings) and then invokes the chosen tool via `call_tool`. See [doc/tool-authoring.md](./doc/tool-authoring.md) for the conventions each tool follows.

### Example Prompts

See [usage examples](./doc/usage.md)

## Contributing

Contributions are welcome! Please see our [Development Guide](./DEVELOPMENT.md) for instructions on setting up a development environment, running tests, and more.

## License

 **MIT**

## Contact

![synapse_icon](https://github.com/user-attachments/assets/b629f426-ae1b-4179-87d2-ac2c73419644)

For issues, please file an issue. For other contact, see https://sagebionetworks.org/contact.

