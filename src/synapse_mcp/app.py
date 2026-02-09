"""Core MCP application setup."""

from datetime import datetime, timezone
import json
import logging
import os
from urllib.parse import urlparse

from fastmcp import FastMCP
from starlette.middleware import Middleware as ASGIMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from .oauth import create_oauth_proxy
from .auth_middleware import OAuthTokenMiddleware, PATAuthMiddleware

logger = logging.getLogger("synapse_mcp.app")


# ---------------------------------------------------------------------------
# ASGI middleware: normalise grant_types on POST /register
# ---------------------------------------------------------------------------
# The MCP library validates that grant_types contains *both*
# "authorization_code" and "refresh_token" before our OAuthProxy override
# is called.  Many MCP clients (Claude Code, claude.ai) only send
# "authorization_code".  This middleware rewrites the request body so
# "refresh_token" is always present, allowing registration to succeed.
# ---------------------------------------------------------------------------
class _GrantTypesMiddleware:
    """Raw ASGI middleware that normalises ``grant_types`` for ``POST /register``."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if (
            scope["type"] == "http"
            and scope["method"] == "POST"
            and scope["path"] == "/register"
        ):
            body_parts: list[bytes] = []
            # Buffer the entire request body
            while True:
                msg = await receive()
                body_parts.append(msg.get("body", b""))
                if not msg.get("more_body", False):
                    break

            raw = b"".join(body_parts)
            try:
                data = json.loads(raw)
                grants = data.get("grant_types", [])
                if "authorization_code" in grants and "refresh_token" not in grants:
                    data["grant_types"] = grants + ["refresh_token"]
                    raw = json.dumps(data).encode()
                    logger.debug("Normalised grant_types in /register body")
            except (json.JSONDecodeError, TypeError):
                pass  # forward the original body unchanged

            # Build a one-shot ``receive`` that replays the (possibly rewritten) body.
            body_sent = False

            async def patched_receive():
                nonlocal body_sent
                if not body_sent:
                    body_sent = True
                    return {"type": "http.request", "body": raw, "more_body": False}
                return {"type": "http.disconnect"}

            await self.app(scope, patched_receive, send)
            return

        await self.app(scope, receive, send)


# Expose as a ``starlette.middleware.Middleware`` instance so it can be
# passed directly to ``mcp.run(middleware=[...])`` in ``__main__``.
grant_types_middleware = ASGIMiddleware(_GrantTypesMiddleware)


# Determine authentication mode and configure server accordingly
auth = create_oauth_proxy()
has_pat = bool(os.environ.get("SYNAPSE_PAT"))
has_oauth = bool(
    os.environ.get("SYNAPSE_OAUTH_CLIENT_ID")
    and os.environ.get("SYNAPSE_OAUTH_CLIENT_SECRET")
)

# Server instructions
_INSTRUCTIONS = (
    "Synapse is a collaborative data platform for researchers where data is organized in public or private projects. "
    "Synapse MCP Server helps users discover and understand Synapse data that they can see, providing tools for: "
    "searches, wiki retrieval, metadata retrieval, and project traversal (through projects/folders). "
    "Review entity metadata for attribution and licensing. "
    "Each connection must authenticate with a Synapse."
)

if auth and has_oauth:
    # Production mode: OAuth authentication
    mcp = FastMCP("Synapse MCP Server", instructions=_INSTRUCTIONS, auth=auth)
    mcp.add_middleware(OAuthTokenMiddleware())

    logger.info("Server configured for OAuth authentication (production mode)")
    print("🔐 OAuth authentication configured (production mode)")

    if has_pat:
        logger.warning(
            "Both SYNAPSE_PAT and OAuth credentials detected. "
            "Using OAuth (production mode). "
            "Remove SYNAPSE_OAUTH_CLIENT_ID/SECRET to use PAT mode."
        )
        print("⚠️  Warning: SYNAPSE_PAT ignored in OAuth mode")

elif has_pat:
    # Development mode: PAT authentication
    mcp = FastMCP("Synapse MCP Server", instructions=_INSTRUCTIONS, auth=None)
    mcp.add_middleware(PATAuthMiddleware())

    logger.info("Server configured for PAT authentication (development mode)")
    print("🔧 PAT authentication configured (development mode)")

else:
    # No authentication configured
    raise ValueError(
        "No authentication configured. Set one of:\n"
        "  Production (OAuth): SYNAPSE_OAUTH_CLIENT_ID + SYNAPSE_OAUTH_CLIENT_SECRET\n"
        "  Development (PAT):  SYNAPSE_PAT"
    )


@mcp.custom_route("/health", methods=["GET"])
async def health_check(request: Request) -> JSONResponse:
    """Standard HTTP health check endpoint for Kubernetes and monitoring systems."""
    return JSONResponse(
        {
            "status": "healthy",
            "service": "synapse-mcp",
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "version": "0.2.0",
            "is_oauth_configured": bool(
                os.environ.get("SYNAPSE_OAUTH_CLIENT_ID")
                and os.environ.get("SYNAPSE_OAUTH_CLIENT_SECRET")
            ),
        }
    )


@mcp.custom_route("/.well-known/oauth-protected-resource", methods=["GET"])
async def oauth_protected_resource_root(request: Request) -> JSONResponse:
    """Serve RFC 9728 protected resource metadata at the root path.

    FastMCP serves this at ``/.well-known/oauth-protected-resource/mcp``
    (path-suffixed per the spec), but the ``WWW-Authenticate`` header in 401
    responses advertises the root path without the ``/mcp`` suffix.  This
    route ensures both URLs resolve so that all MCP clients — including
    Claude Code and claude.ai — can complete OAuth discovery.
    """
    raw_server_url = os.environ.get("MCP_SERVER_URL", "http://127.0.0.1:9000")
    parsed = urlparse(raw_server_url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"
    resource_url = raw_server_url.rstrip("/")

    return JSONResponse(
        {
            "resource": resource_url,
            "authorization_servers": [f"{base_url}/"],
            "scopes_supported": ["openid", "view"],
            "bearer_methods_supported": ["header"],
        }
    )


__all__ = ["auth", "mcp", "health_check", "oauth_protected_resource_root"]
